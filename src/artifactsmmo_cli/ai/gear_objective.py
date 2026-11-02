"""The global gear objective `(L*, m*)` from game data (spec 2026-10-18 §2).

`L*` is the best loadout of ACHIEVABLE level-legal gear, chosen for the monster
`m*` it farms best; `missing` lists the pieces of it the character does not hold,
in the order they are pursued. Three questions, each answered from game data:

* What is achievable (§2.1, §2.3)? A monotone fixed point grown in layers by
  `gear_objective_core.achievable_layers`. The universe is every level-legal
  gear item `is_suppliable` admits, plus everything held, worn or banked. An
  item is achievable when `ObtainModel` finds it feasible under
  `PIECE_POLICY` with the DROP fights judged against a projected
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
* Which pieces (§2.8)? A piece's gain is `R(L*)` less `R` of `L*` with its slot
  holding the best item the character owns for it, or nothing (`_gain`). A
  piece that adds nothing to `R` is held-equivalent, never missing: `L*` is
  chosen for fight XP, and a prospecting-only artifact adds none.

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
potion-propped win never hides a gear upgrade (USER 2026-10-10): `R` is the no-potion fight loop (`loop_rate` with an
empty utility loadout), recovering over the character's own food menu, which
is read once (gear in the bag does not change what can be eaten). It is the
MODELLED rate: a measured upkeep belongs to the worn gear, not to a projected
loadout.

`R` COUNTS THE BANK TRIPS (§2.10). The loop's drops fill the bag the fighter's
loadout gives (`_wearing` carries a worn bag's `inventory_space` into
`inventory_max`), less what the real character's keep holds in it
(`inventory_keep.carried_keep`, read once: the fighter's bag is the whole
achievable set, which no deposit keeps). So a bigger bag is a positive gain,
and a monster with heavy drops far from the bank values it more.
"""

from collections import Counter
from collections.abc import Callable, Mapping
from dataclasses import replace
from datetime import datetime
from fractions import Fraction

from artifactsmmo_cli.ai.acquisition_cost import EQUIP_ACTIONS, cheapest_route
from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.combat import fight_loadout, secure_win
from artifactsmmo_cli.ai.decompose_core import can_obtain
from artifactsmmo_cli.ai.equipment.loadout_picker import _benefit, _ordered_slots
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats, with_totals
from artifactsmmo_cli.ai.equipment.realizable_loadout import ownership
from artifactsmmo_cli.ai.fight_odds_core import win_probability as odds_win
from artifactsmmo_cli.ai.fight_walk import odds_walk, walk_seconds
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_objective_core import achievable_layers, layer_of, piece_order_key
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.gear_value_core import Combat
from artifactsmmo_cli.ai.heal_catalog import POTION
from artifactsmmo_cli.ai.inventory_keep import carried_keep
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loop_rate import FoodOffer, LoopInputs, LoopRate, food_menu, loop_rate
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.obtain_model.gate import Gate, GateKind
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.progression_reserve import spendable_pocket
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.suppliable import is_suppliable
from artifactsmmo_cli.ai.utility_slot import UTILITY_SLOTS, utility_slot_quantity
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
    stat totals carry the swap (`project_loadout_stats`, set by `with_totals`).
    Each code must be owned and known: an unknown piece would project as no
    stats at all."""
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
    return with_totals(replace(state, inventory={code: n for code, n in bag.items() if n > 0}),
                       stats, equipment, hp=stats.max_hp)


def _potions_off(state: WorldState) -> WorldState:
    """`state` with its utility slots emptied into the bag, every unit of their
    stacks with them. The totals do not move: the sheet leaves a worn potion's
    boost out of them (a combat-time effect, `equipment.projection`'s module
    doc), so taking one off strips nothing."""
    bag = Counter(state.inventory)
    for slot in UTILITY_SLOTS:
        code = state.equipment[slot]
        if code is not None:
            bag[code] += utility_slot_quantity(state, slot)
    return replace(state, inventory=dict(bag),
                   equipment={**state.equipment, **dict.fromkeys(UTILITY_SLOTS)},
                   utility1_slot_quantity=0, utility2_slot_quantity=0)


def _bare(state: WorldState, items: frozenset[str], game_data: GameData) -> WorldState:
    """`state` owning `items` (`fighter_owning`) and wearing no gear: every worn
    piece in the bag, its stats stripped from the totals, and no potion worn
    (`_potions_off`).

    The sheet's totals include what it wears, so the stripped totals are the
    character without its gear, never below zero (ruling R). A total below
    zero means the sheet did not include a worn piece: impossible API data,
    which raises naming the stat, never a fighter that wins nothing."""
    bare = _wearing(fighter_owning(_potions_off(state), items, game_data),
                    dict.fromkeys(_GEAR_SLOTS), game_data)
    for stat, value in _totals(bare):
        if value < 0:
            raise ValueError(f"{state.character}: bare {stat} {value} < 0: the sheet's "
                             "totals do not include its worn gear")
    return bare


def _totals(state: WorldState) -> list[tuple[str, int]]:
    """Every combat stat total `_wearing` projects, by name."""
    totals = [("dmg", state.dmg), ("critical_strike", state.critical_strike),
              ("initiative", state.initiative), ("max_hp", state.max_hp),
              ("wisdom", state.wisdom), ("prospecting", state.prospecting),
              ("haste", state.haste), ("inventory_max", state.inventory_max)]
    for name, by_element in (("attack", state.attack), ("dmg_elements", state.dmg_elements),
                             ("resistance", state.resistance)):
        totals.extend((f"{name}.{element}", value) for element, value in by_element.items())
    return totals


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


def _universe(state: WorldState, game_data: GameData, now: datetime) -> frozenset[str]:
    """Level-legal gear (every slot type but the consumables `best_loadout`
    owns) that this character holds, wears or banks, or can ever come to hold:
    `is_suppliable`, which counts a fixed-supply item only while a free copy is
    in the bag or the bank (a copy a sibling wears is in neither)."""
    held = _held(state)
    return frozenset(
        code for code, stats in game_data.items.stats.items()
        if stats.type_ in ITEM_TYPE_TO_SLOTS and stats.type_ != POTION
        and stats.level <= state.level
        and (code in held or is_suppliable(code, state, game_data, now)))


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
    # The cycle clock (ruling T8b): every layer's walk reads one instant.
    now = ctx.now
    open_items = set(_universe(state, game_data, now))

    def unlock(owned: frozenset[str]) -> frozenset[str]:
        model = ObtainModel(state, game_data, ctx, now, fighter=_fighters(state, owned, game_data))
        fresh = set()
        for code in open_items - owned:
            if model.feasible(code, 1, PIECE_POLICY):
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


def achievable_fighter(state: WorldState, game_data: GameData,
                       ctx: SelectionContext) -> Callable[[str], WorldState]:
    """The per-monster achievable fighter (§2.3) once the fixed point has
    converged: owning every achievable item (`achievable`, through
    `fighter_owning`) and, for each monster, wearing that monster's own `L*`
    over them on bare gear at max HP (`_fighters`). It is who the objective
    asks whether a drop's monster can be beaten, so "can this dropper be
    beaten" is asked of it, never of the gear the character happens to wear."""
    return _fighters(state, frozenset(layer_of(achievable(state, game_data, ctx))), game_data)


def _winnable_gate(gate: Gate) -> bool:
    """A WINNABLE gate: the one some fighter's gear could open. Named, so the
    walk's door memo (`ObtainModel._door_open`) shares one entry across the
    layer's items."""
    return gate.kind is GateKind.WINNABLE


def _reachable_by_some_fighter(model: ObtainModel, code: str) -> bool:
    """Would `code` be feasible with every WINNABLE gate open: the most any
    fighter could make of this snapshot?"""
    graph = model.walk_graph(code, PIECE_POLICY, openable=_winnable_gate)
    return can_obtain(code, 1, graph.on_hand, graph.routes)


def _combat(game_data: GameData, monster: str, state: WorldState) -> Combat:
    """The picker's purpose against `monster`, as `fight_loadout` builds it."""
    return Combat(game_data.monster_attack(monster), game_data.monster_resistance(monster),
                  dict(state.attack))


def xp_rate(rate: LoopRate) -> Fraction:
    """The global objective's purpose: XP a second (`LoopRate.xp_per_second`)."""
    return rate.xp_per_second


def task_rate(rate: LoopRate) -> Fraction:
    """A pinned monsters task's purpose: its progress a second, the same
    loop's kills a second (`LoopRate.kills_per_second`, ruling C2-grey). A grey
    task monster pays no XP, so its XP rate is 0 whatever is worn; its kills
    still come faster in better gear."""
    return rate.kills_per_second


def _rate(fighter: WorldState, game_data: GameData, monster: str,
          food: tuple[FoodOffer, ...], loop: LoopInputs,
          per: Callable[[LoopRate], Fraction]) -> Fraction:
    """`R`: the rate `per` reads (`xp_rate` or `task_rate`: one loop model,
    the numerator chosen by the objective's purpose) of farming `monster` in
    `fighter`'s worn gear with no potion, recovering over `food`, each fight
    lasting its learned seconds (spec §2.9) and carrying its share of the bank
    trips its drops force (§2.10; see the module doc's `R`). The no-potion loop
    drinks nothing, so it has no potion price and always has a rate; with no
    room in the bag for its drops it does not run and earns nothing
    (`LoopRate.runnable`, `R = 0`)."""
    rate = loop_rate(fighter, game_data, monster, (), food, {}, loop.timing, loop.drops,
                     loop.carried)
    if rate is None:
        raise RuntimeError(f"the no-potion loop against {monster} did not run")
    return per(rate)


def _rated(targets: Mapping[str, tuple[WorldState, dict[str, str]]], game_data: GameData,
           food: tuple[FoodOffer, ...], loop: LoopInputs) -> list[tuple[str, Fraction]]:
    """`(m, R)` for every candidate that can be the argmax, in candidate order.

    A candidate is a fight the executor will take once `L*(m)` is worn: the
    fighter wearing it, at full hp, passes the WINNABLE verdict every fight gate
    and the drop gate read (`drop_fight_winnable`: the learned record does not
    refuse it, and its bare odds or a stockable potion loadout's clear this
    character's threshold, `combat.win_threshold` through
    `fight_odds_core.odds_clear`). A monster it fails is no `m*`: the objective
    would read "held" while every fight against it is refused.

    `R` is the no-potion loop's win odds times a kill's XP over the fight's
    seconds (`walk_seconds`, the same the loop reads) plus a non-negative
    recovery, walk back and bank-trip share (`loop_rate`; 0 when the loop does
    not run), so it never exceeds the odds times
    the XP over the fight alone. Candidates are
    rated in falling order of that bound, and the walk stops at the first whose
    bound is below the best `R` found: it and every later one can neither reach
    nor tie it. The answer is the one rating them all gives; only the work
    differs (the recovery programme is most of the objective's time)."""
    bound = {code: odds_win(odds_walk(fighter, game_data, code, ())[0])
             * game_data.xp_per_kill(code, fighter.level, fighter.wisdom)
             / walk_seconds(fighter, game_data, code, (), loop.timing)
             for code, (fighter, _) in targets.items()}
    rates: dict[str, Fraction] = {}
    for code in sorted(targets, key=bound.__getitem__, reverse=True):
        if rates and bound[code] < max(rates.values()):
            break
        if not drop_fight_winnable(targets[code][0], game_data, code):
            continue
        rates[code] = _rate(targets[code][0], game_data, code, food, loop, xp_rate)
    return [(code, rates[code]) for code in targets if code in rates]


def _candidates(state: WorldState, game_data: GameData) -> list[str]:
    """The monsters `FightAction` would fight for XP now, solo, in catalogue
    order: at most `FIGHT_LEVEL_GAP_CEILING` above the character, paying XP,
    and with a tile the fight pool reaches on any layer (`monster_spawn_known`:
    a static tile in a reachable region, interiors and the underground
    included, for which the action factory builds a `FightAction`, or a live
    event tile). A drop route asks that predicate AND the walk's reach from
    here now (`drop_routes.monster_reached`, ruling T14a-E); a candidate here
    does not, so a monster behind a crossing the character cannot pay for yet
    may still be `m*`."""
    ceiling = state.level + FIGHT_LEVEL_GAP_CEILING
    return [code for code, kind in game_data.monsters.types.items()
            if kind not in PARTY_ONLY_TYPES and game_data.monster_levels[code] <= ceiling
            and game_data.xp_per_kill(code, state.level) > 0
            and game_data.monster_spawn_known(code)]


def _missing(game_data: GameData, monster: str, target: WorldState, loadout: dict[str, str],
             own: dict[str, str]) -> list[tuple[str, str, str]]:
    """The `(slot, code, at)` pieces of `loadout` the character does not hold
    (§2.4.1), `at` being the `L*` slot that names `code`. They are compared
    against `own`, the loadout it would wear for `monster` from what it owns
    (ruling Q): from the real state, wear the fight loadout and pick again
    until the pick is worn (`_target`), as the fight-loadout gate
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

    def benefit(code: str) -> int:
        return _benefit(_stats(code, game_data), purpose)

    missing: list[tuple[str, str, str]] = []
    for slots in _SLOT_GROUPS:
        free = list(slots)
        unplaced: list[tuple[str, str]] = []
        # Strongest target first against the strongest unmatched owned item: the
        # greedy pairing that holds the most targets.
        wanted = [(slot, loadout[slot]) for slot in slots if slot in loadout]
        for at, code in sorted(wanted, key=lambda pair: benefit(pair[1]), reverse=True):
            strongest = max((slot for slot in free if slot in own),
                            key=lambda slot: benefit(own[slot]), default=None)
            if strongest is not None and benefit(own[strongest]) >= benefit(code):
                free.remove(strongest)
            else:
                unplaced.append((at, code))
        # Every pairing removed one free slot and settled one target, so the
        # free slots outnumber the unplaced targets or match them.
        missing.extend((slot, code, at)
                       for slot, (at, code) in zip(free, unplaced, strict=False))
    return missing


def _without(state: WorldState, target: WorldState, game_data: GameData,
             at: str) -> WorldState:
    """`target` (the fighter wearing `L*`) with `L*`'s slot `at` taken off and
    holding only what `state`, the real character, owns for that slot: of every
    item that fits `at`, the bag keeps no more copies than the character holds
    (bag or worn, never the bank, as `_missing` reads it) beyond those `target`
    still wears in another slot.

    Every fight re-picks its loadout from what the fighter holds
    (`combat._fight_projection`), and `target` carries the whole achievable set.
    Taken off into its bag, the piece went straight back into the slot and read
    every combat gain as 0; dropped alone, the slot was filled from the next
    achievable item, which is not owned either (ruling ZA). The re-pick may
    still move another slot among what the fighter holds."""
    fighter = _wearing(target, {at: None}, game_data)
    bag = Counter(fighter.inventory)
    for item in list(bag):
        if at in ITEM_TYPE_TO_SLOTS.get(_stats(item, game_data).type_, []):
            elsewhere = sum(1 for code in fighter.equipment.values() if code == item)
            owned = ownership(item, state.inventory, state.equipment) - elsewhere
            bag[item] = min(bag[item], max(owned, 0))
    return replace(fighter, inventory={item: n for item, n in bag.items() if n > 0})


def _gain(state: WorldState, target: WorldState, game_data: GameData, monster: str,
          food: tuple[FoodOffer, ...], loop: LoopInputs, rate: Fraction,
          at: str, per: Callable[[LoopRate], Fraction]) -> Fraction:
    """A piece's gain (§2.8): `rate`, `R(L*)` on `target` (the fighter wearing
    `L*`), less `R` of `target` with `L*`'s slot `at` holding the best item the
    character owns for it, or nothing (`_without`), each fight lasting its
    learned seconds (§2.9: a faster kill is a gain) and carrying its bank trips
    (§2.10: a bigger bag fills less often, so a bag is a gain), in the unit
    `per` reads."""
    return rate - _rate(_without(state, target, game_data, at), game_data, monster, food,
                        loop, per)


def _candidate_ctx(ctx: SelectionContext, monster: str, loadout: dict[str, str],
                   rate: Fraction, fighter: WorldState) -> SelectionContext:
    """`ctx` carrying `monster`'s provisional objective (no pieces yet): what
    the pricer reads `m*` and its fighter from while the objective is still
    being chosen (`attach_gear_objective` prices before it attaches one)."""
    return replace(ctx, gear_objective=GearObjective(monster, loadout, rate, (), fighter=fighter))


def _price(state: WorldState, game_data: GameData, ctx: SelectionContext,
           history: LearningStore | None, code: str) -> tuple[Fraction, SourceKind | None]:
    """`(price, route)` of wearing `code`: its `cheapest_route` under
    `PIECE_POLICY`, the policy the piece was judged achievable by and is served
    by, plus the equip (the price `route_price` gives the slotted `ObtainItem`),
    and the route that price takes, the one the piece is served by (plan B
    Task 3).

    Priced from the character's OWN state (ruling T14d-3): the price is paid
    from now, with the gear the character holds, so a drop route's chance is
    read at the prospecting of the loadout the attempt is made in from that
    gear (spec 2026-10-18 §2.8, `attempt_prospecting`, ruling T12n). It used to
    swap the character's own gear on top of the `L*` fighter's prospecting
    total, a mixed basis.

    Held gold is credited only above the reserve the piece's buy must keep
    (`spendable_pocket`, ruling T3e m3): the gold the executor's buy refuses
    to spend (`can_spend`) is priced as gold to fight for, the same pocket the
    served fight counts toward (`gold_funded_buy`)."""
    price, route = cheapest_route(code, 1, state, game_data, ctx, history, policy=PIECE_POLICY,
                                  pocket=spendable_pocket(state, game_data, frozenset({code})))
    return Fraction(price + EQUIP_ACTIONS), route


def _inputs(state: WorldState, game_data: GameData, ctx: SelectionContext,
            history: LearningStore | None) -> tuple[dict[str, int], tuple[FoodOffer, ...],
                                                     LoopInputs]:
    """What every `L*(m)` is read against, whichever `m`: each achievable
    item's layer (§2.3, `achievable`), the food menu and the loop's timing,
    drops and carried keep (see the module doc's `R`)."""
    return (layer_of(achievable(state, game_data, ctx)),
            *_food_and_loop(state, game_data, ctx, history))


def _food_and_loop(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   history: LearningStore | None) -> tuple[tuple[FoodOffer, ...], LoopInputs]:
    """The food menu and the loop's timing, drops and carried keep: what `R`
    reads beside the achievable set."""
    food = food_menu(state, game_data, ctx, history)
    loop = LoopInputs(ctx.timing(), ctx.drops(), carried_keep(state, game_data, ctx))
    return food, loop


def _objective(state: WorldState, game_data: GameData, ctx: SelectionContext,
               history: LearningStore | None, monster: str,
               target: tuple[WorldState, dict[str, str]], rate: Fraction,
               depth: Mapping[str, int], food: tuple[FoodOffer, ...],
               loop: LoopInputs, per: Callable[[LoopRate], Fraction]) -> GearObjective:
    """`L*(monster)` as an objective: `target` is its fighter and loadout
    (`_target`), `rate` its `R` in the unit `per` reads. A piece is missing per `_missing`, and only
    while its gain (`_gain`) is above 0 (§2.8: a piece that adds nothing is
    held-equivalent, so it is neither missing nor priced); the missing are
    priced (`_price`) and put in pursuit order (`piece_order_key`)."""
    fighter, loadout = target
    own = _target(state, game_data, monster)[1]
    pieces: list[GearPiece] = []
    for slot, code, at in _missing(game_data, monster, fighter, loadout, own):
        gain = _gain(state, fighter, game_data, monster, food, loop, rate, at, per)
        if gain > 0:
            price, route = _price(state, game_data, ctx, history, code)
            pieces.append(GearPiece(slot, code, depth[code], gain, price, route))
    rank = _ordered_slots()
    pieces.sort(key=lambda piece: piece_order_key(piece.layer, piece.gain, piece.price,
                                                  rank.index(piece.slot)))
    return GearObjective(monster, loadout, rate, tuple(pieces), fighter=fighter)


def _task_free(state: WorldState, game_data: GameData) -> WorldState:
    """`state` with its held task cleared when nothing `L*` reads can see it.

    `L*` reads the task only through the keep (`inventory_keep._active_task`,
    the copies of the task's code; an items task's root closure), and both
    read an item code: a task whose code names no item (a monsters task)
    reads 0 there. Such a task is cleared, so a task-worth probe of the same
    character (`task_worth_for`) and the character itself are one key. A task
    on an item code stays, so its probe is its own key."""
    if state.task_code is not None and game_data.item_stats(state.task_code) is not None:
        return state
    return replace(state, task_code=None, task_type=None, task_progress=0, task_total=0)


def _pinned[T](name: str, monster: str | None, state: WorldState, game_data: GameData,
               ctx: SelectionContext, history: LearningStore | None,
               compute: Callable[[], T]) -> T:
    """`compute()`, once per `search_cache` episode (ruling C2-perf) for one
    task-free state (`_task_free`), catalogue and context. The episode's entry
    for `(name, monster, character, level)` lists what it answered, each answer
    pinned to its state by value and to its catalogue and context by
    reference (memory: a cache key must pin its object): an answer is served
    only to an equal state under the very catalogue and context it answered,
    and any other asker's answer joins the list. Without a store, afresh."""
    if history is None:
        return compute()
    key_state = _task_free(state, game_data)
    answers: list[tuple[WorldState, GameData, SelectionContext, T]] = history.cached(
        (name, monster, state.character, state.level), list)
    for held_state, held_data, held_ctx, value in answers:
        if held_data is game_data and held_ctx is ctx and held_state == key_state:
            return value
    value = compute()
    answers.append((key_state, game_data, ctx, value))
    return value


def _cycle_inputs(state: WorldState, game_data: GameData, ctx: SelectionContext,
                  history: LearningStore | None
                  ) -> tuple[dict[str, int], tuple[FoodOffer, ...], LoopInputs]:
    """`_inputs`, once per episode for every monster a cycle pins: they do not
    read the monster, and the task horizon pins one per task it reads. The
    achievable set is `_cycle_depth`'s, shared with the readers that need no
    loop (a fighter's pick reads no timing)."""
    def compute() -> tuple[dict[str, int], tuple[FoodOffer, ...], LoopInputs]:
        return (_cycle_depth(state, game_data, ctx, history),
                *_food_and_loop(state, game_data, ctx, history))

    return _pinned("gear_objective_inputs", None, state, game_data, ctx, history, compute)


def _cycle_depth(state: WorldState, game_data: GameData, ctx: SelectionContext,
                 history: LearningStore | None) -> dict[str, int]:
    """Each achievable item's layer (`achievable`), once per episode."""
    return _pinned("gear_objective_depth", None, state, game_data, ctx, history,
                   lambda: layer_of(achievable(state, game_data, ctx)))


def _pinned_target(depth: Mapping[str, int], monster: str, state: WorldState,
                   game_data: GameData) -> tuple[WorldState, dict[str, str]]:
    """`L*(monster)`'s fighter and loadout, picked over the achievable set
    `depth` from the fighter wearing nothing: `gear_objective_for`'s own."""
    return _target(_bare(state, frozenset(depth), game_data), game_data, monster)


def gear_fighter_for(monster: str, state: WorldState, game_data: GameData,
                     ctx: SelectionContext, history: LearningStore | None) -> WorldState:
    """The fighter wearing `L*(monster)` on bare gear at max HP
    (`gear_objective_for(...).fighter`), without pricing a piece (ruling
    C2-perf). It reads no loop: only the achievable set and the picker."""
    depth = _cycle_depth(state, game_data, ctx, history)
    return _pinned_target(depth, monster, state, game_data)[0]


def gear_closes_for(monster: str, state: WorldState, game_data: GameData,
                    ctx: SelectionContext, history: LearningStore | None) -> bool:
    """Whether gear closes the fight against `monster`: the fighter wearing
    `L*(monster)` `secure_win`s (on bare gear at max HP, the bar
    `combat_deficit.has_combat_deficit` reads) and `L*` has a missing piece
    (`gear_objective_for(..., task_rate).missing` is not empty: an unheld
    piece, `_missing`, whose gain in task progress a second is above 0,
    `_gain`, ruling C2-grey). Gains are read only once the fighter secures the
    fight and only until the first that is above 0; no piece is priced (ruling
    C2-perf)."""
    depth, food, loop = _cycle_inputs(state, game_data, ctx, history)
    fighter, loadout = _pinned_target(depth, monster, state, game_data)
    if not secure_win(fighter, game_data, monster):
        return False
    own = _target(state, game_data, monster)[1]
    unheld = _missing(game_data, monster, fighter, loadout, own)
    if not unheld:
        return False
    rate = _rate(fighter, game_data, monster, food, loop, task_rate)
    return any(_gain(state, fighter, game_data, monster, food, loop, rate, at, task_rate) > 0
               for _slot, _code, at in unheld)


def gear_objective_for(monster: str, state: WorldState, game_data: GameData,
                       ctx: SelectionContext, history: LearningStore | None,
                       per: Callable[[LoopRate], Fraction]) -> GearObjective:
    """`L*(monster)`: the objective `gear_objective` reads for a candidate
    `m`, with `m` pinned (plan C Task 2). The same achievable fixed point, the
    same loadout walk from the fighter wearing nothing and the same missing,
    gained, priced and ordered pieces (`_objective`), so there is one
    implementation; only the argmax over monsters is not asked.

    `R` is read in the unit `per` names, the objective's purpose: `xp_rate`
    for a candidate of the global objective, `task_rate` (kills a second) for
    a held monsters task, which pays per kill (ruling C2-grey: a grey task
    monster pays no XP, so in XP every piece of its `L*` gained 0).

    `monster` need not be a candidate (`_candidates`, `_rated`): a held task's
    monster is pinned whatever its level gap, XP or fight verdict, so its fighter
    may still lose. Whether `L*(monster)` wins is the
    caller's question, asked of `GearObjective.fighter`. Once per episode
    for one monster, state and context (`_pinned`, ruling C2-perf)."""
    def compute() -> GearObjective:
        depth, food, loop = _cycle_inputs(state, game_data, ctx, history)
        target = _pinned_target(depth, monster, state, game_data)
        rate = _rate(target[0], game_data, monster, food, loop, per)
        return _objective(state, game_data, ctx, history, monster, target, rate, depth, food,
                          loop, per)

    return _pinned(f"gear_objective_for:{per.__name__}", monster, state, game_data, ctx,
                   history, compute)


def gear_objective(state: WorldState, game_data: GameData, ctx: SelectionContext,
                   history: LearningStore | None) -> GearObjective | None:
    """`(L*, m*)` and the missing pieces of `L*` in pursuit order, or None when
    no candidate monster the executor would fight in its `L*` (see `_rated`)
    has `R > 0`, even owning the whole achievable set.

    `m*` is the max-`R` monster; a tie goes to the higher monster level, then to
    the lower total acquisition price of its missing pieces, then to catalogue
    order — never to a code. Each tied candidate's objective is `_objective`,
    the one `gear_objective_for` gives with that candidate pinned."""
    depth, food, loop = _inputs(state, game_data, ctx, history)
    targets = _targets(state, game_data, frozenset(depth))
    rated = _rated(targets, game_data, food, loop)
    if not rated or max(rate for _, rate in rated) <= 0:
        return None
    best = max((rate, game_data.monster_levels[code]) for code, rate in rated)
    # Each candidate's pieces are priced with ITS objective on the context, so
    # the gold they spend is charged at what a second of fighting it in its
    # `L*` earns (`gold_rate.gold_per_second`, ruling AL's `m*` fallback,
    # S-046): the rate the cycle prices gold at once that candidate is `m*`.
    tied = [_objective(state, game_data,
                       _candidate_ctx(ctx, code, targets[code][1], best[0], targets[code][0]),
                       history, code, targets[code], best[0], depth, food, loop, xp_rate)
            for code, rate in rated if (rate, game_data.monster_levels[code]) == best]
    # `min` keeps the first of equal totals: catalogue order, as `_candidates` lists.
    return min(tied, key=lambda objective: sum((piece.price for piece in objective.missing),
                                               Fraction(0)))
