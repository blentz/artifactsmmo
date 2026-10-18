"""The global gear objective `(L*, m*)` from game data (spec 2026-10-18 §2).

`L*` is the best loadout of ACHIEVABLE level-legal gear, chosen for the monster
`m*` it farms best; `missing` lists the pieces of it the character does not hold,
in the order they are pursued. Three questions, each answered from game data:

* What is achievable (§2.1, §2.3)? A monotone fixed point grown in layers by
  `gear_objective_core.achievable_layers`. The universe is every level-legal
  gear item `is_suppliable` admits (that already includes everything held or
  banked). An item is achievable when `ObtainModel` finds it feasible under
  `GEAR_OBJECTIVE_POLICY` with the DROP fights judged against a projected
  fighter: the character owning one copy of every item achievable so far (two
  of a ring). So a drop opens as soon as SOME achievable loadout beats its
  monster, never because of what is worn.
* Which monster (§2.2)? `m*` is the argmax of the advancement rate `R` over the
  monsters `FightAction` would fight now. For each, `L*(m)` is the picker's
  fight loadout over the whole achievable set, taken as a fixed point of
  "wear the pick, pick again" from a fighter wearing NOTHING: the picker's
  purpose reads the wearer's attack (`fight_loadout`'s `Combat(...,
  state.attack)`), so a pick made in the worn gear would lean toward it, and a
  pick that changes the weapon would not be the loadout the fight is fought in.
  At the fixed point the fighter wearing `L*` picks `L*`, which is what
  `FightAction` will wear; `R(L*, m)` is read on that fighter.
* In what order (§2.4)? Dependency (the layer) first, then gain in `R` per unit
  of acquisition price (`gear_objective_core.piece_order_key`). The price only
  orders the pieces; it never changes `L*`.

The unlock fighters are `dataclasses.replace(state, inventory=...)`: level,
skills, stat totals and the learned record (`lost_fights`) stay the real
character's, and the picker chooses from the owned set, as `combat_deficit`'s
"owning, not wearing" projection does. The `L*` fighters move gear between bag
and slots with the stat totals carried by `project_loadout_stats`, the server's
own "totals less the old piece plus the new" arithmetic.
"""

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction
from functools import partial

from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.best_loadout import best_loadout
from artifactsmmo_cli.ai.combat import fight_loadout
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.equipment.loadout_picker import _benefit, _ordered_slots
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_core import achievable_layers, layer_of, piece_order_key
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import GEAR_OBJECTIVE_POLICY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.band_target import rank_rate
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import is_suppliable
from artifactsmmo_cli.ai.world_state import WorldState

PARTY_ONLY_TYPES = frozenset({"boss", "raid_boss"})
"""Monster types never farmed solo: the party path owns them."""

_SLOT_GROUPS: tuple[tuple[str, ...], ...] = tuple(
    tuple(slots) for kind, slots in ITEM_TYPE_TO_SLOTS.items() if kind != POTION)
"""The equipment slots grouped by the item type that fills them: slots of one
type (the ring and artifact slots) are interchangeable for "is it held"."""

_GEAR_SLOTS: tuple[str, ...] = tuple(slot for slots in _SLOT_GROUPS for slot in slots)
"""Every slot `L*` fills: all but the consumables' utility slots."""

RING_COPIES = 2
"""Copies of a ring a fighter owns: one code may fill both ring slots, and the
picker's occupancy cap allows it only with two owned copies."""


def _stats(code: str, game_data: GameData) -> ItemStats:
    stats = game_data.item_stats(code)
    if stats is None:
        raise KeyError(f"no item stats for {code}")
    return stats


def fighter_owning(state: WorldState, items: frozenset[str], game_data: GameData) -> WorldState:
    """`state` owning one copy of every item in `items`, two of a ring; a copy
    already held (bag or worn) counts toward it. Only the inventory changes."""
    inventory = dict(state.inventory)
    for code in items:
        wanted = RING_COPIES if _stats(code, game_data).type_ in DUPLICATE_SLOT_TYPES else 1
        short = wanted - ownership(code, inventory, state.equipment)
        if short > 0:
            inventory[code] = inventory.get(code, 0) + short
    return replace(state, inventory=inventory)


def _wearing(state: WorldState, loadout: Mapping[str, str | None],
             game_data: GameData) -> WorldState:
    """`state` with `loadout` worn (slot -> code, None empties the slot): every
    replaced piece goes to the bag before any new one comes out of it, and the
    stat totals carry the swap (`project_loadout_stats`). Each code must be
    owned and known: an unknown piece would project as no stats at all."""
    for code in {*loadout.values(), *(state.equipment[slot] for slot in loadout)}:
        if code is not None:
            _stats(code, game_data)
    stats = project_loadout_stats(state, dict(loadout), game_data)
    bag = Counter(state.inventory)
    equipment = dict(state.equipment)
    for slot, code in loadout.items():
        worn = equipment[slot]
        if worn is not None and worn != code:
            bag[worn] += 1
    for slot, code in loadout.items():
        if code is not None and equipment[slot] != code:
            assert bag[code] > 0, f"{code} is not owned to wear in {slot}"
            bag[code] -= 1
        equipment[slot] = code
    return replace(state, inventory={code: n for code, n in bag.items() if n > 0},
                   equipment=equipment, attack=stats.attack, dmg=stats.dmg,
                   dmg_elements=stats.dmg_elements, resistance=stats.resistance,
                   critical_strike=stats.critical_strike, initiative=stats.initiative,
                   max_hp=stats.max_hp, hp=stats.max_hp, wisdom=stats.wisdom,
                   prospecting=stats.prospecting)


def _target(bare: WorldState, game_data: GameData,
            monster: str) -> tuple[WorldState, dict[str, str]]:
    """`L*(monster)` and the fighter wearing it: from `bare` (wearing nothing),
    wear the fight loadout and pick again until the pick is what is worn. Each
    step swaps a slot only for a strictly better item under the wearer's own
    purpose; a pick seen before that is not the worn one would be a cycle, which
    the picker has no rule to break, so it is refused rather than guessed."""
    fighter = bare
    seen: list[dict[str, str | None]] = []
    while True:
        picked = fight_loadout(fighter, game_data, monster)
        loadout = {slot: picked.get(slot) for slot in _GEAR_SLOTS}
        if loadout == {slot: fighter.equipment[slot] for slot in _GEAR_SLOTS}:
            return fighter, picked
        assert loadout not in seen, f"the fight loadout for {monster} cycles: {seen}"
        seen.append(loadout)
        fighter = _wearing(fighter, loadout, game_data)


def _targets(state: WorldState, game_data: GameData,
             achieved: frozenset[str]) -> dict[str, tuple[WorldState, dict[str, str]]]:
    """`L*(m)` and its fighter for every candidate `m`, owning `achieved`: each
    picked from the same fighter wearing nothing, so what is worn now cannot
    lean the pick (the picker keeps a worn item against an equal one)."""
    bare = _wearing(fighter_owning(state, achieved, game_data),
                    dict.fromkeys(_GEAR_SLOTS), game_data)
    return {code: _target(bare, game_data, code) for code in _candidates(state, game_data)}


def _universe(state: WorldState, game_data: GameData) -> frozenset[str]:
    """Level-legal gear (every slot type but the consumables `best_loadout`
    owns) that this character holds, wears or banks, or can ever come to hold:
    `is_suppliable`, which counts a fixed-supply item only while a free copy is
    in the bag or the bank (a copy a sibling wears is in neither)."""
    held = _held(state)
    return frozenset(
        code for code, stats in game_data.items.stats.items()
        if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.type_ != POTION
        and stats.level <= state.level
        and (code in held or is_suppliable(code, state, game_data)))


def _held(state: WorldState) -> frozenset[str]:
    """Every code in the bag, worn, or banked."""
    bank = state.bank_items or {}
    return frozenset({code for code, n in state.inventory.items() if n > 0}
                     | {code for code in state.equipment.values() if code}
                     | {code for code, n in bank.items() if n > 0})


def achievable(state: WorldState, game_data: GameData,
               ctx: SelectionContext) -> tuple[frozenset[str], ...]:
    """The achievable gear in fixed-point layers (§2.3). Layer 0 is the held
    gear and what the character, owning it, can obtain; each later layer is what
    owning everything so far newly opens (drops of monsters it now beats)."""
    universe = _universe(state, game_data)
    now = datetime.now(UTC)

    def unlock(owned: frozenset[str]) -> frozenset[str]:
        model = ObtainModel(state, game_data, ctx, now,
                            fighter=fighter_owning(state, owned, game_data))
        return owned | frozenset(code for code in universe - owned
                                 if model.feasible(code, 1, GEAR_OBJECTIVE_POLICY))

    return achievable_layers(unlock(universe & _held(state)), unlock)


def _combat(game_data: GameData, monster: str, state: WorldState) -> Combat:
    """The picker's purpose against `monster`, as `fight_loadout` builds it."""
    return Combat(game_data.monster_attack(monster), game_data.monster_resistance(monster),
                  dict(state.attack))


def _rate(fighter: WorldState, game_data: GameData, ctx: SelectionContext,
          history: LearningStore | None, monster: str,
          price_of: Callable[[str], Fraction]) -> Fraction:
    """`R`: XP per second of farming `monster` owning `fighter`'s items, at full
    hp. The MODELLED rate (`rank_rate` with no upkeep): a measured upkeep
    belongs to the worn gear, not to a projected loadout. The kill's XP carries
    the wisdom of the loadout the fight is fought in."""
    rested = replace(fighter, hp=fighter.max_hp)
    wisdom = project_loadout_stats(
        rested, dict(fight_loadout(rested, game_data, monster)), game_data).wisdom
    return rank_rate(game_data.xp_per_kill(monster, rested.level, wisdom), None,
                     partial(best_loadout, rested, game_data, ctx, monster, history), price_of)


def _candidates(state: WorldState, game_data: GameData) -> list[str]:
    """The monsters `FightAction` would fight for XP now, solo, in catalogue
    order: spawning now, at most `FIGHT_LEVEL_GAP_CEILING` above the character,
    paying XP."""
    ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    return [code for code, kind in game_data.monsters.types.items()
            if kind not in PARTY_ONLY_TYPES and game_data.monster_levels[code] <= ceiling
            and game_data.xp_per_kill(code, state.level) > 0
            and game_data.monster_locations(code)]


def _missing(state: WorldState, game_data: GameData, monster: str,
             target: WorldState, loadout: dict[str, str]) -> list[tuple[str, str]]:
    """The `(slot, code)` pieces of `loadout` the character does not hold
    (§2.4.1), compared against its own fight loadout for `monster` (what it
    owns, as `FightAction` would wear it).

    Slots of one item type are compared as a GROUP: three artifact slots or two
    ring slots are interchangeable, so a target worn one slot over is held, not
    missing. Within a group a target is held by an owned item the picker's own
    `_benefit` ranks at least as high under the purpose that chose the target
    (`target`, the fighter wearing it): the same code, or an equal item, which
    is not worth an acquisition. "Equal" is the argmax's own measure, never a
    code. The target is the argmax over a superset of what is owned, so an owned
    item cannot rank above it; `>=` reads that edge as held. A missing piece is
    placed in a group slot the owned loadout leaves unmatched, so its equip
    displaces nothing that is held."""
    purpose = _combat(game_data, monster, target)
    own = fight_loadout(state, game_data, monster)

    def benefit(code: str) -> int:
        return _benefit(_stats(code, game_data), purpose)

    missing: list[tuple[str, str]] = []
    for slots in _SLOT_GROUPS:
        free = list(slots)
        unplaced: list[str] = []
        # Strongest target first against the strongest unmatched owned item: the
        # greedy pairing that holds the most targets.
        wanted = [loadout[slot] for slot in slots if slot in loadout]
        for code in sorted(wanted, key=benefit, reverse=True):
            strongest = max((slot for slot in free if slot in own),
                            key=lambda slot: benefit(own[slot]), default=None)
            if strongest is not None and benefit(own[strongest]) >= benefit(code):
                free.remove(strongest)
            else:
                unplaced.append(code)
        # Every pairing removed one free slot and settled one target, so the
        # free slots outnumber the unplaced targets or match them.
        missing.extend(zip(free, unplaced, strict=False))
    return missing


def _price(state: WorldState, game_data: GameData, ctx: SelectionContext,
           history: LearningStore | None, slot: str, code: str) -> Fraction:
    """Acquisition price of wearing `code` in `slot`: `route_price` of the slotted
    `ObtainItem` (its equip included)."""
    return Fraction(route_price(ObtainItem(code, 1, slot=slot), state, game_data, ctx, history))


def gear_objective(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   history: LearningStore | None,
                   price_of: Callable[[str], Fraction]) -> GearObjective | None:
    """`(L*, m*)` and the missing pieces of `L*` in pursuit order, or None when
    no candidate monster has `R > 0` even owning the whole achievable set.

    `m*` is the max-`R` monster; a tie goes to the higher monster level, then to
    the lower total acquisition price of its missing pieces, then to catalogue
    order — never to a code."""
    layers = achievable(state, game_data, ctx)
    depth = layer_of(layers)
    targets = _targets(state, game_data, frozenset(depth))
    rated = [(code, _rate(fighter, game_data, ctx, history, code, price_of))
             for code, (fighter, _) in targets.items()]
    if not rated or max(rate for _, rate in rated) <= 0:
        return None
    best = max((rate, game_data.monster_levels[code]) for code, rate in rated)
    tied = [code for code, rate in rated if (rate, game_data.monster_levels[code]) == best]
    loadouts = {code: targets[code][1] for code in tied}
    pieces_of = {code: _missing(state, game_data, code, targets[code][0], loadouts[code])
                 for code in tied}
    prices = {code: [_price(state, game_data, ctx, history, slot, item)
                     for slot, item in pieces_of[code]] for code in tied}
    # `min` keeps the first of equal totals: catalogue order, as `_candidates` lists.
    monster = min(tied, key=lambda code: sum(prices[code], Fraction(0)))
    owned = _rate(state, game_data, ctx, history, monster, price_of)
    gains: dict[str, Fraction] = {}
    for _, code in pieces_of[monster]:
        if code not in gains:
            gains[code] = _rate(fighter_owning(state, frozenset({code}), game_data), game_data,
                                ctx, history, monster, price_of) - owned
    rank = _ordered_slots()
    pieces = [GearPiece(slot, code, depth[code], gains[code], price)
              for (slot, code), price in zip(pieces_of[monster], prices[monster], strict=True)]
    # A piece whose modelled gain is negative is still an `L*` piece; it orders
    # as zero gain, last within its layer (ruling E: no floor above zero).
    pieces.sort(key=lambda piece: piece_order_key(piece.layer, max(piece.gain, Fraction(0)),
                                                  piece.price, rank.index(piece.slot)))
    return GearObjective(monster, loadouts[monster], best[0], tuple(pieces))
