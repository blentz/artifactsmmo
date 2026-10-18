"""The global gear objective `(L*, m*)` from game data (spec 2026-10-18 §2).

`L*` is the best loadout of ACHIEVABLE level-legal gear, chosen for the monster
`m*` it farms best; `missing` lists the pieces of it the character does not hold,
in the order they are pursued. Three questions, each answered from game data:

* What is achievable (§2.1, §2.3)? A monotone fixed point grown in layers by
  `gear_objective_core.achievable_layers`. The universe is every level-legal
  gear item `is_suppliable` admits, plus everything held, worn or banked. An
  item is achievable when `ObtainModel` finds it feasible under
  `GEAR_OBJECTIVE_POLICY` with the DROP fights judged against a projected
  fighter: the character owning one copy of every item achievable so far (two
  of a ring), stripped of what it wears and, for each dropping monster,
  wearing that monster's own `L*` over those holdings (`_fighters`). So a drop
  opens as soon as an achievable loadout beats its monster, never because of
  what is worn.
* Which monster (§2.2)? `m*` is the argmax of the advancement rate `R` over the
  monsters the fight pool reaches now on any layer. For each, `L*(m)` is the
  picker's fight loadout over the whole achievable set, taken as a fixed point
  of "wear the pick, pick again" from the fighter wearing nothing. At the fixed
  point the fighter wearing `L*` picks `L*`, which is what `FightAction` will
  wear; `R(L*, m)` is read on that fighter.
* In what order (§2.4)? Dependency (the layer) first, then gain in `R` per unit
  of acquisition price (`gear_objective_core.piece_order_key`). The price only
  orders the pieces; it never changes `L*`.

WHY EVERY FIGHTER WEARS NOTHING TO START. The picker's purpose reads the
wearer's attack (`fight_loadout`'s `Combat(..., state.attack)`) and keeps a worn
item against an equal one, so a fighter built by adding items to the bag of the
real, dressed character picks toward the worn gear: the same holdings worn or
carried gave a different `L*`, and a different achievable set (a level-10
character in a leather set reached `forest_staff`; carrying the set, it did
not). The bare fighter moves the worn gear to the bag with its stats stripped
(`_wearing`, the server's own "totals less the old piece plus the new"
arithmetic in `project_loadout_stats`); level, skills and the learned record
(`lost_fights`) stay the real character's.

`R` IS THE BARE-GEAR RATE. Every gear decision judges bare gear, so a
potion-propped win never hides a gear upgrade (USER 2026-10-10; `band_target`'s
`BandTarget.bare_fight`): `R` is the no-potion fight loop (`loop_rate` with an
empty utility loadout), recovering over the character's own food menu, which
is read once (gear in the bag does not change what can be eaten). It is the
MODELLED rate: a measured upkeep belongs to the worn gear, not to a projected
loadout.
"""

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import fight_loadout
from artifactsmmo_cli.ai.consumable_price import FIGHT_SECONDS
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.decompose_core import can_obtain
from artifactsmmo_cli.ai.equipment.loadout_picker import _benefit, _ordered_slots
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_walk import odds_walk
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_core import achievable_layers, layer_of, piece_order_key
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate import FoodOffer, food_menu, loop_rate
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.obtain_model.gate import GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import GEAR_OBJECTIVE_POLICY
from artifactsmmo_cli.ai.selection_context import SelectionContext
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

CONVERGE_PASSES = len(_GEAR_SLOTS) + 1
"""Passes of "wear the pick, pick again" before `L*` must have converged: one
per gear slot, plus the pass that finds the pick worn. Measured on the bundle
(406 character x monster cases, levels 3-41): never more than 3."""

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
            if bag[code] <= 0:
                raise RuntimeError(f"{code} is not owned to wear in {slot}")
            bag[code] -= 1
        equipment[slot] = code
    return replace(state, inventory={code: n for code, n in bag.items() if n > 0},
                   equipment=equipment, attack=stats.attack, dmg=stats.dmg,
                   dmg_elements=stats.dmg_elements, resistance=stats.resistance,
                   critical_strike=stats.critical_strike, initiative=stats.initiative,
                   max_hp=stats.max_hp, hp=stats.max_hp, wisdom=stats.wisdom,
                   prospecting=stats.prospecting)


def _bare(state: WorldState, items: frozenset[str], game_data: GameData) -> WorldState:
    """`state` owning `items` (`fighter_owning`) and wearing no gear: every worn
    piece in the bag, its stats stripped from the totals."""
    return _wearing(fighter_owning(state, items, game_data), dict.fromkeys(_GEAR_SLOTS),
                    game_data)


def _target(bare: WorldState, game_data: GameData,
            monster: str) -> tuple[WorldState, dict[str, str]]:
    """`L*(monster)` (its gear slots: the utility slots are the consumables',
    which no gear decision reads) and the fighter wearing it: from `bare`,
    wear the fight loadout and pick again until the pick is what is worn. Each
    step swaps a slot only for a strictly better item under the wearer's own
    purpose. `CONVERGE_PASSES` bounds the walk: a pick still moving after it is
    a cycle the picker has no rule to break, so it raises rather than return a
    loadout the fight would not be fought in."""
    fighter = bare
    for _ in range(CONVERGE_PASSES):
        picked = fight_loadout(fighter, game_data, monster)
        loadout = {slot: picked.get(slot) for slot in _GEAR_SLOTS}
        if loadout == {slot: fighter.equipment[slot] for slot in _GEAR_SLOTS}:
            return fighter, {slot: code for slot, code in loadout.items() if code is not None}
        fighter = _wearing(fighter, loadout, game_data)
    raise RuntimeError(f"the fight loadout for {monster} has not converged in "
                       f"{CONVERGE_PASSES} passes")


def _targets(state: WorldState, game_data: GameData,
             achieved: frozenset[str]) -> dict[str, tuple[WorldState, dict[str, str]]]:
    """`L*(m)` and its fighter for every candidate `m`, owning `achieved`, each
    picked from the same fighter wearing nothing."""
    bare = _bare(state, achieved, game_data)
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
    owning everything so far newly opens (drops of monsters it now beats).

    Only a drop's WINNABLE gate reads the fighter; every other gate (spawns,
    vendors, workshops, a grey dropper, gold fights judged on the real state)
    is the same for every fighter. So an item a walk cannot reach even with
    every WINNABLE gate open (`_reachable_by_some_fighter`) is out of reach of
    every later layer too, and later walks skip it: the layers are the ones
    walking it again would give."""
    open_items = set(_universe(state, game_data))
    now = datetime.now(UTC)

    def unlock(owned: frozenset[str]) -> frozenset[str]:
        model = ObtainModel(state, game_data, ctx, now, fighter=_fighters(state, owned, game_data))
        fresh = set()
        for code in open_items - owned:
            if model.feasible(code, 1, GEAR_OBJECTIVE_POLICY):
                fresh.add(code)
            elif not _reachable_by_some_fighter(model, code):
                open_items.discard(code)
        return owned | frozenset(fresh)

    return achievable_layers(unlock(frozenset(open_items) & _held(state)), unlock)


def _fighters(state: WorldState, owned: frozenset[str],
              game_data: GameData) -> Callable[[str], WorldState]:
    """The unlock fighter, per drop monster: owning `owned` and wearing that
    monster's own `L*` over it (`_target` from the bare fighter), so a drop is
    achievable when SOME achievable loadout beats its monster (§2.3), not only
    the loadout one pick would wear for every monster. Memoized per monster for
    this layer's holdings."""
    bare = _bare(state, owned, game_data)
    worn: dict[str, WorldState] = {}

    def fighter(monster: str) -> WorldState:
        if monster not in worn:
            worn[monster] = _target(bare, game_data, monster)[0]
        return worn[monster]

    return fighter


def _reachable_by_some_fighter(model: ObtainModel, code: str) -> bool:
    """Would `code` be feasible with every WINNABLE gate open: the most any
    fighter could make of this snapshot?"""
    graph = model.walk_graph(code, GEAR_OBJECTIVE_POLICY,
                             openable=lambda gate: gate.kind is GateKind.WINNABLE)
    return can_obtain(code, 1, graph.on_hand, graph.routes)


def _combat(game_data: GameData, monster: str, state: WorldState) -> Combat:
    """The picker's purpose against `monster`, as `fight_loadout` builds it."""
    return Combat(game_data.monster_attack(monster), game_data.monster_resistance(monster),
                  dict(state.attack))


def _rate(fighter: WorldState, game_data: GameData, monster: str,
          food: tuple[FoodOffer, ...]) -> Fraction:
    """`R`: XP per second of farming `monster` in `fighter`'s worn gear with no
    potion, recovering over `food` (see the module doc's `R`). The no-potion
    loop drinks nothing, so it has no potion price and always runs."""
    loop = loop_rate(fighter, game_data, monster, (), food, {})
    if loop is None:
        raise RuntimeError(f"the no-potion loop against {monster} did not run")
    return loop.xp_per_second


def _rated(targets: Mapping[str, tuple[WorldState, dict[str, str]]], game_data: GameData,
           food: tuple[FoodOffer, ...]) -> list[tuple[str, Fraction]]:
    """`(m, R)` for every candidate that can be the argmax, in candidate order.

    A candidate is a fight the executor will take once `L*(m)` is worn: the
    fighter wearing it, at full hp, passes the WINNABLE verdict every fight gate
    and the drop gate read (`drop_fight_winnable`: the learned record does not
    refuse it, and its bare odds or a stockable potion loadout's clear this
    character's threshold, `combat.win_threshold` through
    `fight_odds_core.odds_clear`). A monster it fails is no `m*`: the objective
    would read "held" while every fight against it is refused.

    `R` is the no-potion loop's win odds times a kill's XP over the fight's
    seconds plus a non-negative recovery and walk back (`loop_rate`), so it
    never exceeds the odds times the XP over the fight alone. Candidates are
    rated in falling order of that bound, and the walk stops at the first whose
    bound is below the best `R` found: it and every later one can neither reach
    nor tie it. The answer is the one rating them all gives; only the work
    differs (the recovery programme is most of the objective's time)."""
    bound = {code: odds_win(odds_walk(fighter, game_data, code, ())[0])
             * game_data.xp_per_kill(code, fighter.level, fighter.wisdom) / FIGHT_SECONDS
             for code, (fighter, _) in targets.items()}
    rates: dict[str, Fraction] = {}
    for code in sorted(targets, key=bound.__getitem__, reverse=True):
        if rates and bound[code] < max(rates.values()):
            break
        if not drop_fight_winnable(targets[code][0], game_data, code):
            continue
        rates[code] = _rate(targets[code][0], game_data, code, food)
    return [(code, rates[code]) for code in targets if code in rates]


def _candidates(state: WorldState, game_data: GameData) -> list[str]:
    """The monsters `FightAction` would fight for XP now, solo, in catalogue
    order: at most `FIGHT_LEVEL_GAP_CEILING` above the character, paying XP,
    and with a tile the fight pool reaches on any layer (`monster_spawn_known`:
    a static tile in a reachable region, interiors and the underground
    included, for which the action factory builds a `FightAction`, or a live
    event tile), the same predicate `GEAR_OBJECTIVE_POLICY`'s drops ask."""
    ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    return [code for code, kind in game_data.monsters.types.items()
            if kind not in PARTY_ONLY_TYPES and game_data.monster_levels[code] <= ceiling
            and game_data.xp_per_kill(code, state.level) > 0
            and game_data.monster_spawn_known(code)]


def _missing(state: WorldState, game_data: GameData, monster: str,
             target: WorldState, loadout: dict[str, str]) -> list[tuple[str, str]]:
    """The `(slot, code)` pieces of `loadout` the character does not hold
    (§2.4.1), compared against the loadout it would wear for `monster` from
    what it owns (ruling Q): from the real state, wear the fight loadout and
    pick again until the pick is worn (`_target`), as the fight-loadout gate
    re-arms before every fight (`FightAction`'s optimal-loadout precondition,
    sequenced by `OptimizeLoadout`). A piece in the bag is therefore held, an
    equip and not an acquisition. The bank is not owned here: the picker and
    the gate read only the bag and the worn slots, and nothing withdraws a
    piece to wear it before a fight.

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
    own = _target(state, game_data, monster)[1]

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
                   history: LearningStore | None) -> GearObjective | None:
    """`(L*, m*)` and the missing pieces of `L*` in pursuit order, or None when
    no candidate monster the executor would fight in its `L*` (see `_rated`)
    has `R > 0`, even owning the whole achievable set.

    `m*` is the max-`R` monster; a tie goes to the higher monster level, then to
    the lower total acquisition price of its missing pieces, then to catalogue
    order — never to a code. A piece's gain is `R` on `m*` of the character
    owning it against owning only what it holds, each on its own `L*(m*)`."""
    layers = achievable(state, game_data, ctx)
    depth = layer_of(layers)
    food = food_menu(state, game_data, ctx, history)
    targets = _targets(state, game_data, frozenset(depth))
    rated = _rated(targets, game_data, food)
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

    def rate_owning(items: frozenset[str]) -> Fraction:
        fighter, _ = _target(_bare(state, items, game_data), game_data, monster)
        return _rate(fighter, game_data, monster, food)

    owned = rate_owning(frozenset())
    gains = {code: rate_owning(frozenset({code})) - owned for _, code in pieces_of[monster]}
    rank = _ordered_slots()
    pieces = [GearPiece(slot, code, depth[code], gains[code], price)
              for (slot, code), price in zip(pieces_of[monster], prices[monster], strict=True)]
    # A piece whose modelled gain is negative is still an `L*` piece; it orders
    # as zero gain, last within its layer (ruling E: no floor above zero).
    pieces.sort(key=lambda piece: piece_order_key(piece.layer, max(piece.gain, Fraction(0)),
                                                  piece.price, rank.index(piece.slot)))
    return GearObjective(monster, loadouts[monster], best[0], tuple(pieces))
