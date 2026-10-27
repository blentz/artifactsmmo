"""One route policy judges, prices and serves an `L*` piece (plan B Task 2).

`PIECE_POLICY` is the policy `gear_objective.achievable` judges a piece by,
`gear_objective._price` prices it by and `tiers/strategy.actionable_step`
counts a leaf by. Three policies once answered those three questions, and
they disagreed: an event vendor's item was achievable and then declined
`no_step_goal`, because the step graph refused every event NPC; a GE order
was a route to the pricer and not to the objective.

`lich_race_trophy`, the live piece that showed the split, is NOT in the
committed bundle (no item stats, no NPC sells it, and the archaeologist is a
permanent NPC there). The bundle's own event-gated vendor item stands in for it:
`lost_world_map`, an L19 artifact (wisdom 100) that only the event NPC
`nomadic_merchant` sells, for 15000 gold.
"""

import json
from dataclasses import replace
from fractions import Fraction
from math import ceil
from pathlib import Path

import pytest

from artifactsmmo_cli.ai import region_edges
from artifactsmmo_cli.ai.acquisition_cost import (
    _climbs,
    _kill_actions,
    acquisition_options,
    cheapest_route,
    fight_gold_monster,
    route_options,
)
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.decisions.root import IsThisTargetBlocked, RootWalk
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.decisions.which_piece_is_next import piece_target
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import achievable
from artifactsmmo_cli.ai.gear_objective_core import layer_of
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grey_farm import serves_a_demand
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import LEGACY, PIECE_POLICY, Policy
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.region_edges import reachable_regions_now
from artifactsmmo_cli.ai.scenario import (
    FAR_FUTURE,
    SCENARIOS,
    derived_scenario_state,
    scenario_state,
)
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT
from tests.test_ai.shared_world import attached, shared_world

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"

EVENT_ITEM = "lost_world_map"
EVENT_NPC = "nomadic_merchant"
EVENT_SLOT = "artifact1_slot"
EVENT_CELL = "l20_band_entry"
"""A level-20 character whose `L*` takes the event vendor's map while the
event is live."""

GE_CELL = "l12_ge_book_adequate"
AMULET = ObtainItem("fire_and_earth_amulet", 1, slot="amulet_slot")
"""Cell 5's amulet: the busy book sells it at 213 gold, and its craft needs
jewelrycrafting 10 against the character's 5."""

GE_ONLY = frozenset({"iron_pickaxe", "spruce_fishing_rod", "wooden_staff", "iron_axe",
                     "satchel", "leather_gloves"})
"""The level-legal gear cell 5 can have only from the busy book's sell orders."""

CLIMB_CELL = "l10_weapon_upgrade"
LEATHER = ObtainItem("leather_armor", 1, slot="body_armor_slot")
"""`{spruce_plank: 4, cowhide: 4}` at gearcrafting 10; spruce_plank is a
woodcutting-10 craft from woodcutting-10 spruce_wood. The character has 1 in
both."""

MAP_PRICE = 9715
"""The map's price at the live event: its 14900 gold short of the pocket,
fought for at the wolf's exact win cost and rounded once (ruling T2m M1;
14904 when each win was rounded up), plus the wolf's tile, the vendor's tile,
the buy and the equip."""

PIECE_MAP_PRICE = 9780
"""The map's price as a piece of `L*` (ruling T3e m3): its 100-gold pocket sits
under the 100-gold safety floor its buy must keep, so all 15000 gold is fought
for, 25 more wolf wins than `MAP_PRICE`'s 14900."""

RUNE_CELL = "l20_dual_utility"
"""A level-20 character whose `L*` heads with the 20000-gold `lifesteal_rune`."""

MAX_XP = 150
"""The `<skill>_max_xp` the climb tests give the character: the API's xp to the
next level, which a scenario state does not carry."""


def _world(name: str) -> GameData:
    """The world `name` declares (its market and achievements), its event overlay
    seeded from the scenario as `GamePlayer.seed_offline` does."""
    sc = SCENARIOS[name]
    world = shared_world(BUNDLE, with_ge_orders=sc.ge_market,
                         completed_achievements=frozenset(sc.unlocked_achievements))
    world.active_event_codes = set(sc.active_events)
    world.active_raid_codes = {code for code, _boss in sc.raids}
    return world


def _store(*skills: str) -> LearningStore:
    """A store that has watched each skill's grind gain 30 xp a cycle."""
    store = LearningStore(db_path=":memory:", character="piece")
    store.start_session()
    index = 0
    for skill in skills:
        for _ in range(4):
            store.record_cycle(Cycle(
                ts=f"2026-10-20T00:00:{index:02d}+00:00", session_id="s", cycle_index=index,
                character="piece", outcome="ok", action_repr=f"LevelSkill({skill}->10)",
                delta_skill_xp_json=json.dumps({skill: 30})))
            index += 1
    return store


def _event(state: WorldState, world: GameData, live: bool) -> WorldState:
    """`state` with the event vendor's event live or down, and the world's
    overlay to match."""
    events = {EVENT_NPC: FAR_FUTURE} if live else {}
    world.active_event_codes = set(events)
    return replace(state, active_events=events)


# --- the three answers agree ------------------------------------------------

def test_a_layer_zero_piece_is_served_or_climbs() -> None:
    """For every missing piece of every catalogued scenario's objective, a piece
    in the fixed point's first layer is served: the step graph names a step for
    it, or its own crafting skill stands in front (`classify_target`, served as
    the `ReachSkillLevel`). A later-layer piece is a drop from a monster only an
    achievable loadout beats (§2.3), so it waits on the layer that opens it
    (§2.4, dependency first) and the real fighter has no step for it yet."""
    served = 0
    for name, sc in SCENARIOS.items():
        world = _world(name)
        state = derived_scenario_state(sc, world)
        ctx = attached(state, world, TIMED_NO_PROFILE_CONTEXT, None)
        if ctx.gear_objective is None:
            continue
        objective = CharacterObjective.from_game_data(world)
        for piece in ctx.gear_objective.missing:
            if piece.layer != 0:
                continue
            step = actionable_step(ObtainItem(piece.code, 1, slot=piece.slot), state, world,
                                   ctx)
            gated = objective.classify_target(piece.code, state).blocking_skill is not None
            assert step is not None or gated, (name, piece)
            served += 1
    assert served > 100, served


UNSERVED = ("no_step_goal", "infeasible:", "unmapped_step:", "region:")
"""The walk's answers for a step the obtain model calls feasible that no goal
or action serves: the disagreement plan B Task 14a's INTERIM trunk stood in
for. A transient decline (a full bag, low hp) is not one."""


def test_every_layer_zero_piece_the_model_calls_achievable_the_walk_serves() -> None:
    """Plan B Task 14a (ruling T6c): `L*` never names a piece the walk cannot
    serve. The live census of 2026-10-27 found two such classes, both fixed
    rather than filtered out of `L*`: a passive-currency piece mapped to no
    goal (`lich_race_trophy`, ruling T14a-B) and a GE-filled material with no
    walk route (`malefic_crystal`, ruling T14a-C). After them no live piece
    of the five characters is unserved, so this pins the agreement: on every
    catalogued scenario, the walk's own question (`GamePlayer._step_decline`)
    never answers a first-layer piece's step as unserved.

    Two more classes this pin found on the fixtures were ruled and fixed
    (fix round 2): a piece's grey material (`slime_shield`'s wool at L30/L40,
    ruling T14a-D) and a fight-gold monster behind a crossing the character
    cannot pay for (`lifesteal_rune`'s dryad at L48, ruling T14a-E)."""
    unserved: list[tuple[str, str, str]] = []
    asked = 0
    for name, sc in SCENARIOS.items():
        world = _world(name)
        player = GamePlayer(character=sc.name, history=None)
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        player.seed_offline(derived_scenario_state(sc, world), world)
        state = player.state
        assert state is not None
        ctx = player._selection_context()
        if ctx.gear_objective is None:
            continue
        decline = player._step_decline(state, world, ctx, player._build_actions())
        objective = CharacterObjective.from_game_data(world)
        for piece in ctx.gear_objective.missing:
            if piece.layer != 0 or piece.awaits_delivery(state):
                continue
            target = piece_target(piece, objective, state)
            root = IsThisTargetBlocked(piece.slot, target, RootWalk(step_decline=decline)).resolve(
                state, world, ctx, None)
            reason = decline(root)
            if reason is not None and reason.startswith(UNSERVED):
                unserved.append((name, piece.code, reason))
            asked += 1
    assert asked > 100, asked
    assert unserved == []


def test_an_event_vendor_counts_only_while_live() -> None:
    """Live: the map is achievable in the first layer, a missing piece of `L*`,
    and the step graph serves it as itself (a buy, not a decline). Down: it is
    neither achievable nor in `L*`, and the step graph has no step for it."""
    world = _world(EVENT_CELL)
    base = derived_scenario_state(SCENARIOS[EVENT_CELL], world)
    node = ObtainItem(EVENT_ITEM, 1, slot=EVENT_SLOT)

    live = _event(base, world, True)
    assert layer_of(achievable(live, world, TIMED_NO_PROFILE_CONTEXT))[EVENT_ITEM] == 0
    objective = attached(live, world, TIMED_NO_PROFILE_CONTEXT, None).gear_objective
    assert objective is not None
    assert objective.loadout[EVENT_SLOT] == EVENT_ITEM
    assert [(p.code, p.layer, p.price) for p in objective.missing if p.code == EVENT_ITEM] == [
        (EVENT_ITEM, 0, Fraction(PIECE_MAP_PRICE))]
    assert actionable_step(node, live, world, TIMED_NO_PROFILE_CONTEXT) == node

    down = _event(base, world, False)
    assert EVENT_ITEM not in layer_of(achievable(down, world, TIMED_NO_PROFILE_CONTEXT))
    objective = attached(down, world, TIMED_NO_PROFILE_CONTEXT, None).gear_objective
    assert objective is not None
    assert EVENT_ITEM not in objective.loadout.values()
    assert actionable_step(node, down, world, TIMED_NO_PROFILE_CONTEXT) is None


def test_a_standing_order_is_a_route_while_it_stands() -> None:
    """USER 2026-10-19: a live sell order is a route, just like an event. With
    the order the amulet prices through `GE_FILL` (a hop, the fill, the equip)
    and the step graph serves it as itself. The same character with the order
    gone reprices it through its next route, the craft behind its
    jewelrycrafting climb, and the step graph descends to the recipe: no fill is
    planned against a vanished order. The craft's price moved 113 -> 111 with
    plan B Task 12a: its drop-fed materials are priced exactly, rounded once a
    route instead of once a unit. It moved 111 -> 115 with ruling T14a-B': the
    bank holds 3 of the 4 iron_bar, so the 4th is smelted (the smelt and the
    mining hop) from 2 more gathered ore (the gathers and the rocks hop)."""
    busy = shared_world(BUNDLE, with_ge_orders=True)
    quiet = shared_world(BUNDLE)
    ctx = TIMED_NO_PROFILE_CONTEXT
    with_order = scenario_state(SCENARIOS[GE_CELL], busy)
    gone = scenario_state(SCENARIOS[GE_CELL], quiet)

    order = busy.ge_best_sell_order(AMULET.code)
    assert order is not None
    assert [(r.kind, r.venue, r.inputs) for r in route_options(
        AMULET.code, with_order, busy, ctx, None, policy=PIECE_POLICY)] == [
        ("ge_fill", order[0], {"gold": 213})]
    assert route_price(AMULET, with_order, busy, ctx, None, policy=PIECE_POLICY) == 3
    assert actionable_step(AMULET, with_order, busy, ctx) == AMULET

    assert quiet.ge_best_sell_order(AMULET.code) is None
    store = _store("jewelrycrafting")
    climbing = replace(gone, skill_max_xp={"jewelrycrafting": MAX_XP})
    assert [(r.kind, r.unlock, r.unlock_actions) for r in route_options(
        AMULET.code, climbing, quiet, ctx, store, policy=PIECE_POLICY)] == [
        ("craft", "skill:jewelrycrafting:10", 25)]
    assert route_price(AMULET, climbing, quiet, ctx, store, policy=PIECE_POLICY) == 115
    assert actionable_step(AMULET, gone, quiet, ctx) == ObtainItem("iron_bar", 4)


def test_a_standing_order_makes_its_item_achievable() -> None:
    """The objective counts what only the book sells: the same character holds
    six more level-legal pieces in its first layer in the busy book than in the
    quiet one, each sold by a standing order and by no other route it has."""
    busy = shared_world(BUNDLE, with_ge_orders=True)
    quiet = shared_world(BUNDLE)
    with_book = layer_of(achievable(scenario_state(SCENARIOS[GE_CELL], busy), busy,
                                    TIMED_NO_PROFILE_CONTEXT))
    without = layer_of(achievable(scenario_state(SCENARIOS[GE_CELL], quiet), quiet,
                                  TIMED_NO_PROFILE_CONTEXT))
    assert frozenset(with_book) - frozenset(without) == GE_ONLY
    assert {code: with_book[code] for code in GE_ONLY} == dict.fromkeys(GE_ONLY, 0)
    assert all(busy.ge_best_sell_order(code) is not None for code in GE_ONLY)


# --- pricing every route the policy admits ----------------------------------

def test_a_climb_is_priced_though_the_policy_admits_the_craft() -> None:
    """Ruling T2c: a route whose own skill requirement exceeds the character's
    skill costs the climb, whether or not the policy refuses it. `PIECE_POLICY`
    admits the gearcrafting and woodcutting routes as ready, and the price still
    carries both climbs: the price with both skills already at 10, plus each
    grind, exactly as `LEGACY` (which refuses the routes) prices it. The
    ready price moved 214 -> 213 with plan B Task 12a: a drop farm is priced
    exactly, rounded once a route instead of once a unit."""
    world = _world(CLIMB_CELL)
    ctx = TIMED_NO_PROFILE_CONTEXT
    state = replace(derived_scenario_state(SCENARIOS[CLIMB_CELL], world),
                    skill_max_xp={"gearcrafting": MAX_XP, "woodcutting": MAX_XP})
    store = _store("gearcrafting", "woodcutting")
    skilled = replace(state, skills={**state.skills, "gearcrafting": 10, "woodcutting": 10})
    rates = {skill: store.skill_grind_rate(skill) for skill in ("gearcrafting", "woodcutting")}
    assert rates == {"gearcrafting": 30.0, "woodcutting": 30.0}
    climbs = sum(skill_grind_cycles(1, 0, MAX_XP, 10, 30.0) for _ in rates)

    assert route_price(LEATHER, skilled, world, ctx, store, policy=PIECE_POLICY) == 213
    assert climbs == 90
    assert route_price(LEATHER, state, world, ctx, store, policy=PIECE_POLICY) == 213 + 90
    assert route_price(LEATHER, state, world, ctx, store, policy=LEGACY) == 213 + 90


def test_an_unpriceable_climb_leaves_the_piece_unpriced() -> None:
    """No grind rate (no store): the climb cannot be priced, so the gated craft
    is no priced route (`_gated_skill_option`'s decline), never a free one."""
    world = _world(CLIMB_CELL)
    state = derived_scenario_state(SCENARIOS[CLIMB_CELL], world)
    assert route_price(LEATHER, state, world, TIMED_NO_PROFILE_CONTEXT, None,
                       policy=PIECE_POLICY) == UNOBTAINABLE_PER_UNIT + 1


def test_fight_gold_is_priced_per_kill_at_the_mean_gold() -> None:
    """Ruling T2a: a GOLD_DROP route is one win, paying the API's mean gold
    `(min_gold + max_gold) // 2`, priced as a drop farm's kill is
    (`_kill_actions`: the learned fight seconds, the forced rest, the learned
    losses)."""
    world = _world(EVENT_CELL)
    ctx = TIMED_NO_PROFILE_CONTEXT
    state = derived_scenario_state(SCENARIOS[EVENT_CELL], world)
    options = route_options("gold", state, world, ctx, None, policy=PIECE_POLICY)
    assert options
    assert {option.kind for option in options} == {"gold_drop"}
    for option in options:
        low, high = world.monster_min_gold(option.venue), world.monster_max_gold(option.venue)
        assert option.yield_per == max(1, (low + high) // 2), option.venue
        assert option.actions_per_application == _kill_actions(
            option.venue, state, world, ctx.timing(), ctx.fight_records), option.venue
        assert isinstance(option.actions_per_application, Fraction), option.venue
    assert any(world.monster_min_gold(option.venue) < world.monster_max_gold(option.venue)
               for option in options)
    assert route_options("gold", state, world, ctx, None) == []


def test_a_task_reward_is_achievable_and_priced_last() -> None:
    """Ruling T2b: no API datum gives a task's length, so a TASK_REWARD route is
    priced at the unpriced sentinel. It is still a route: the coin is
    achievable."""
    world = _world(EVENT_CELL)
    ctx = TIMED_NO_PROFILE_CONTEXT
    state = derived_scenario_state(SCENARIOS[EVENT_CELL], world)
    assert ObtainModel(state, world, ctx, FAR_FUTURE).feasible("tasks_coin", 1, PIECE_POLICY)
    assert [(r.kind, r.actions_per_application, r.yield_per) for r in route_options(
        "tasks_coin", state, world, ctx, None, policy=PIECE_POLICY)] == [
        ("task_reward", UNOBTAINABLE_PER_UNIT, 1)]


@pytest.mark.parametrize("policy", [LEGACY, PIECE_POLICY])
def test_route_price_forwards_its_policy(policy) -> None:  # type: ignore[no-untyped-def]
    """`route_price` prices under the policy it is given, `LEGACY` by default:
    under `PIECE_POLICY` the live event vendor sells the map and its 15000 gold
    is earned by fighting; `LEGACY` refuses every event vendor (and holds gold to
    the pocket's 100), so the map has no route."""
    world = _world(EVENT_CELL)
    live = _event(derived_scenario_state(SCENARIOS[EVENT_CELL], world), world, True)
    node = ObtainItem(EVENT_ITEM, 1, slot=EVENT_SLOT)
    price = route_price(node, live, world, TIMED_NO_PROFILE_CONTEXT, None, policy=policy)
    assert price == {LEGACY: UNOBTAINABLE_PER_UNIT + 1, PIECE_POLICY: MAP_PRICE}[policy]
    if policy is LEGACY:
        assert route_price(node, live, world, TIMED_NO_PROFILE_CONTEXT, None) == price


def test_a_gold_funded_piece_is_achievable_and_served() -> None:
    """Ruling T2h, served by plan B Task 15: the 20000-gold `lifesteal_rune` is
    achievable under `PIECE_POLICY` (its gold earned by fighting), priced and
    first in `L*`'s order, and no longer declined: its root is the rune itself
    (Task 3 routes it as its BUY) and its goal fights for the gold
    (`test_gold_funded_piece`)."""
    world = _world(RUNE_CELL)
    player = GamePlayer(character=RUNE_CELL, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(scenario_state(SCENARIOS[RUNE_CELL], world), world)
    report = player.plan_from_state()
    rune = ObtainItem("lifesteal_rune", 1, slot="rune_slot")
    objective = attached(player.state, world, TIMED_NO_PROFILE_CONTEXT, None).gear_objective
    assert objective is not None
    assert (objective.missing[0].slot, objective.missing[0].code) == (rune.slot, rune.code)
    assert objective.missing[0].price < UNOBTAINABLE_PER_UNIT
    assert report.decision.declined == ()
    assert report.decision.chosen_root == rune
    assert repr(report.selected_goal) == "GatherMaterials(lifesteal_rune, {lifesteal_rune:1})"


# --- plan B Task 3: the price's route, held gold, exact fights --------------

def test_fight_gold_is_rounded_once_per_route() -> None:
    """Ruling T2m M1: the map's 14900 gold short is farmed off the monster whose
    exact win cost per gold is least (the wolf: about 2.61 actions for 4 gold),
    not off the first that rounds to one action a gold, and its wins are rounded
    up once: ceil(3725 wins x the exact cost), then the two tiles, the buy and
    the equip."""
    world = _world(EVENT_CELL)
    ctx = TIMED_NO_PROFILE_CONTEXT
    live = _event(derived_scenario_state(SCENARIOS[EVENT_CELL], world), world, True)
    gold = acquisition_options(EVENT_ITEM, live, world, ctx, None, policy=PIECE_POLICY)["gold"]
    best = min(gold, key=lambda r: Fraction(r.actions_per_application) / r.yield_per)
    assert best.venue == "wolf"
    short = 15000 - live.gold
    wins = -(-short // best.yield_per)
    assert ceil(wins * best.actions_per_application) + 4 == MAP_PRICE
    assert wins * ceil(best.actions_per_application) + 4 > MAP_PRICE
    node = ObtainItem(EVENT_ITEM, 1, slot=EVENT_SLOT)
    assert route_price(node, live, world, ctx, None, policy=PIECE_POLICY) == MAP_PRICE


def test_held_gold_is_free_up_to_the_pocket() -> None:
    """Ruling T2k ("free until used up", as held potions): cell 5's 213-gold
    fill, which the pocket covers, costs a hop, the fill and the equip with a
    store as without one, under either policy; with a store the priced climb
    no longer outbids it. Only gold beyond the pocket costs its production:
    200 held leaves 13 to fight for under `PIECE_POLICY`, while `LEGACY`, with
    no gold route, takes the climbed craft.

    The 13 are 7 yellow_slime wins (11 actions, rounded once): ruling T15a
    takes the level-15 highwayman, whose gold per action was the cheapest, out
    of a level-12 character's gold routes (above its fight ceiling), and its
    4 wins cost 12. The LEGACY craft moved 38 -> 42 with ruling T14a-B': the
    bank holds 3 of its 4 iron_bar, and the 4th is smelted from gathered ore
    (smelt, gathers, two hops)."""
    busy = shared_world(BUNDLE, with_ge_orders=True)
    ctx = TIMED_NO_PROFILE_CONTEXT
    climbing = replace(scenario_state(SCENARIOS[GE_CELL], busy),
                       skill_max_xp={"jewelrycrafting": MAX_XP})
    store = _store("jewelrycrafting")
    assert climbing.gold >= 213
    for policy in (PIECE_POLICY, LEGACY):
        for history in (None, store):
            assert route_price(AMULET, climbing, busy, ctx, history, policy=policy) == 3
    assert cheapest_route(AMULET.code, 1, climbing, busy, ctx, store, policy=PIECE_POLICY,
                          pocket=climbing.gold) == (
        2, SourceKind.GE_FILL)
    short = replace(climbing, gold=200)
    assert route_price(AMULET, short, busy, ctx, store, policy=PIECE_POLICY) == 15
    assert cheapest_route(AMULET.code, 1, short, busy, ctx, store, policy=LEGACY,
                          pocket=short.gold) == (
        42, SourceKind.CRAFT)


def test_an_unpriced_climb_is_served_as_its_craft() -> None:
    """Offline (no store) a climbed craft has no priced route: its price is
    the no-route sentinel and its route the craft the climb opens, so the walk
    still classifies it behind its crafting gate. An item with no route at all
    has none."""
    world = _world(EVENT_CELL)
    ctx = TIMED_NO_PROFILE_CONTEXT
    state = derived_scenario_state(SCENARIOS[CLIMB_CELL], world)
    for policy in (PIECE_POLICY, LEGACY):
        assert cheapest_route(LEATHER.code, 1, state, world, ctx, None, policy=policy,
                              pocket=state.gold) == (
            UNOBTAINABLE_PER_UNIT, SourceKind.CRAFT)
    assert cheapest_route("tasks_coin", 1, state, world, ctx, None, policy=LEGACY,
                          pocket=state.gold) == (
        UNOBTAINABLE_PER_UNIT, None)


def test_a_policy_without_price_climbs_drops_no_climb() -> None:
    """Ruling T2m M2: a policy that does not price climbs has none to drop,
    though the craft's skill gate is unmet; `PIECE_POLICY` names the climbed
    craft."""
    world = _world(EVENT_CELL)
    state = derived_scenario_state(SCENARIOS[CLIMB_CELL], world)
    model = ObtainModel(state, world, TIMED_NO_PROFILE_CONTEXT, FAR_FUTURE)
    assert _climbs(LEATHER.code, model, LEGACY) == frozenset()
    assert {kind for kind, _ in _climbs(LEATHER.code, model, PIECE_POLICY)} == {SourceKind.CRAFT}


def test_every_policy_states_price_climbs() -> None:
    """Ruling T2m M3: `price_climbs` has no default, so a new policy chooses."""
    fields = {name: getattr(LEGACY, name) for name in Policy.__dataclass_fields__
              if name != "price_climbs"}
    with pytest.raises(TypeError, match="price_climbs"):
        Policy(**fields)


# --- ruling T14a-D: an `L*` piece's material walk may farm a grey dropper ----

SHIELD_CELL = "l30_rune_fill"
"""A level-30 sheet whose `L*` holds `slime_shield`: its cloth is bought for
`wool`, which only `sheep` (level 5, grey at 30) drops."""


def _shield_step(name: str) -> tuple[GamePlayer, GatherMaterialsGoal]:
    sc = SCENARIOS[name]
    world = _world(name)
    player = GamePlayer(character=sc.name, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(derived_scenario_state(sc, world), world)
    state = player.state
    assert state is not None
    ctx = player._selection_context()
    assert ctx.gear_objective is not None
    piece = next(p for p in ctx.gear_objective.missing if p.code == "slime_shield")
    root = ObtainItem(piece.code, 1, slot=piece.slot)
    step = actionable_step(root, state, world, ctx)
    assert step == ObtainItem("cloth", 3)
    goal = objective_step_goal(step, state, world, ctx, root=root)
    assert isinstance(goal, GatherMaterialsGoal)
    return player, goal


@pytest.mark.parametrize("name", [SHIELD_CELL, "l40_band_entry"])
def test_a_piece_s_grey_material_is_farmed(name: str) -> None:
    """Ruling T14a-D: `L*`'s argmax (§2.2) already arbitrated `slime_shield`
    against every same-family alternative, as the tree's argmax did for an
    upgrade's own target (GAP-6), so the grey-farm directive's next-tier
    suppression is not consulted for its material walk; its demand gate
    (the wool buys the cloth the shield's recipe consumes) still holds. The
    walk farms the grey sheep instead of declining
    `infeasible:cloth:no_route:wool`."""
    player, goal = _shield_step(name)
    assert goal.piece_material is True
    state, world = player.state, player.game_data
    assert state is not None and world is not None
    ctx = player._selection_context()
    actions = player._build_actions()
    declined: list[str] = []
    plan = decompose(goal, state, world, actions, ctx, declined)
    assert plan is not None, declined
    # Not a piece's material: the directive stands, as before.
    plain = GatherMaterialsGoal(goal.target_item, goal.needed)
    refused: list[str] = []
    assert decompose(plain, state, world, actions, ctx, refused) is None
    assert refused == ["infeasible:cloth:no_route:wool"]
    # The search's edges agree: only the piece's goal admits the sheep fight.

    def sheep(g: GatherMaterialsGoal) -> list[object]:
        return [a for a in g.relevant_actions(actions, state, world)
                if isinstance(a, FightAction) and a.monster_code == "sheep"]

    assert sheep(goal) and not sheep(plain)


def test_the_piece_exemption_keeps_the_demand_gate() -> None:
    """Condition 1 holds for a piece's walk: a drop that serves no recipe and
    buys nothing (`golden_egg`, only from the grey `chicken` at 30) is never
    grey-farmed, piece or not."""
    world = _world(SHIELD_CELL)
    assert serves_a_demand("wool", world)
    assert not serves_a_demand("slime_shield", world)
    player, _goal = _shield_step(SHIELD_CELL)
    state = player.state
    assert state is not None
    egg = GatherMaterialsGoal("golden_egg", {"golden_egg": 1}, piece_material=True)
    declined: list[str] = []
    assert decompose(egg, state, world, player._build_actions(),
                     player._selection_context(), declined) is None
    assert declined == ["infeasible:golden_egg:no_route:golden_egg"]


def test_only_a_piece_s_gather_is_marked() -> None:
    """The seam marks the gather only when its root is a missing `L*` piece:
    the same cloth step asked for itself is an ordinary gather."""
    player, _goal = _shield_step(SHIELD_CELL)
    state, world = player.state, player.game_data
    assert state is not None and world is not None
    goal = objective_step_goal(ObtainItem("cloth", 3), state, world, player._selection_context())
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.piece_material is False


# --- ruling T14a-E: one reachability authority for a fight's monster ----------

RUNE_CELLS = ["l48_band_adequate", "l48_capstone_approach", "l48_event_active",
              "l48_raid_active"]
"""Level-48 sheets whose `L*` holds `lifesteal_rune`, bought for gold. The
pricer's cheapest gold fight was `dryad`, behind the 5000-gold crossing into
`restricted:overworld:-5,8`, which the walk cannot pay for from here."""


def _seeded(name: str) -> GamePlayer:
    sc = SCENARIOS[name]
    world = _world(name)
    player = GamePlayer(character=sc.name, history=None)
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player.seed_offline(derived_scenario_state(sc, world), world)
    return player


@pytest.mark.parametrize("name", RUNE_CELLS)
def test_a_gold_fight_is_one_the_walk_can_reach(name: str) -> None:
    """Ruling T14a-E: the pricer's fight-gold monster is chosen from monsters
    the walk reaches (`region_edges.reachable_regions_now`), so the rune's
    step is served, not declined `region:overworld->restricted:...`."""
    player = _seeded(name)
    state, world = player.state, player.game_data
    assert state is not None and world is not None
    ctx = player._selection_context()
    assert state.gold < 5000
    assert fight_gold_monster(state, world, ctx, policy=PIECE_POLICY) != "dryad"
    decline = player._step_decline(state, world, ctx, player._build_actions())
    assert decline(ObtainItem("lifesteal_rune", 1, slot="rune_slot")) is None


def test_a_monster_behind_a_crossing_the_character_can_pay_is_reachable() -> None:
    """The gate reads the crossing as the walk does: with the 5000-gold fee in
    the pocket, `dryad` is reachable again."""
    player = _seeded(RUNE_CELLS[0])
    state, world = player.state, player.game_data
    assert state is not None and world is not None
    poor = reachable_regions_now(state, world)
    rich = reachable_regions_now(replace(state, gold=6000), world)
    assert "restricted:overworld:-5,8" not in poor
    assert "restricted:overworld:-5,8" in rich
    assert world.state_region(state) in poor


def test_the_reach_memo_is_scoped_per_catalogue_and_bounded() -> None:
    """A walk is remembered per catalogue (`CatalogueScope`) and per what a
    crossing reads, at most `REACH_MEMO_SIZE` of them, the least recently
    used evicted first."""
    player = _seeded(RUNE_CELLS[0])
    state, world = player.state, player.game_data
    assert state is not None and world is not None
    region_edges._REACH.clear()
    reachable_regions_now(state, world)
    reachable_regions_now(state, world)
    memo = region_edges._REACH.cache_for(world)
    assert list(memo) == [region_edges._reach_key(state, world)]
    region_edges._REACH.max_entries = 1
    try:
        reachable_regions_now(replace(state, gold=6000), world)
        assert list(memo) == [region_edges._reach_key(replace(state, gold=6000), world)]
    finally:
        region_edges._REACH.max_entries = region_edges.REACH_MEMO_SIZE
