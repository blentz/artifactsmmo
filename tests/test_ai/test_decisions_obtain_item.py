"""Transcription parity: the Decision graph must return exactly what
`objective_step_goal`'s `ObtainItem` arm returns, for every ObtainItem shape
the scenario set produces. `objective_step_goal`'s `ObtainItem` arm IS
`resolve_node(obtain_item_decision(step, root), ...)` (Task 5) -- there is no
longer a second, independent if-pile implementation to transcribe against
(`_legacy_objective_step_goal` was that implementation, kept only for the
Task 4/5 transition and deleted once this parity held). The sweep below
still earns its keep two ways: it pins that the production entry point
forwards its arguments to the graph correctly (a wiring regression a future
edit to `objective_step_goal` could silently break), and it is the only
thing that reaches many of the Decision classes' `resolve` bodies across a
realistic (recipe, material) space for coverage.

Enumerates BOTH `step is root` and `step != root` pairs. The branches at
`decisions/obtain_item.py`'s `IsThisAnIntermediateOnAChain` and its
descendants are only reachable when `root.code != step.code` — a parity
test using only `root=step` would pass while exercising none of them, and
would also leave those Decisions' `resolve` bodies uncovered.

The tests below `test_objective_step_goal_forwards_to_the_graph` cover
branches the bundle-catalog/scenario sweep never reaches: the
`analyze_currency_leaves` funding-target route and the depth-reachable-root
route are both real, live paths (see their docstrings) that happen not to be
triggered by any (scenario, recipe) pair in
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`. The final group pins
`objective_step_goal`'s non-`ObtainItem` branches (`step is None`, an
unrecognized step type, and every `ReachCharLevel` sub-branch) directly --
those live entirely in `strategy_driver.py` and are never reached by the
ObtainItem-only Decision graph at all."""
import dataclasses
import json

import pytest

from artifactsmmo_cli.ai.decision import resolve_node
from artifactsmmo_cli.ai.decisions.obtain_item import obtain_item_decision
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.provision_marginal_fight import ProvisionMarginalFightGoal
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.strategy import actionable_step
from artifactsmmo_cli.audit.drop_wall_census import unwinnable_drop_items
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import (
    _ctx,
    _gd,
    _gd_with_utility_heal,
    _record_fight_wins_with_consumables,
)


def _step_root_pairs(gd):
    """(step_code, root_code) pairs: every recipe paired with itself
    (`step is root`) and with each of its own recipe materials
    (`step != root`, and `root` is a real chain root over `step`)."""
    pairs = []
    for root_code in sorted(gd.crafting_recipes)[:25]:
        pairs.append((root_code, root_code))
        for material_code in sorted(gd.crafting_recipes[root_code]):
            pairs.append((material_code, root_code))
    return pairs


@pytest.mark.parametrize("scenario_name", sorted(SCENARIOS))
def test_objective_step_goal_forwards_to_the_graph(scenario_name, bundle_game_data):
    """`objective_step_goal`'s `ObtainItem` arm must return exactly what
    calling the graph directly returns, for every (scenario, step, root)
    triple the bundle catalog produces -- pinning the production wiring
    (`return resolve_node(obtain_item_decision(step, root), state, game_data,
    ctx, history)`) rather than a second hand-written implementation."""
    gd = bundle_game_data
    state = scenario_state(SCENARIOS[scenario_name], gd)
    for step_code, root_code in _step_root_pairs(gd):
        step = ObtainItem(code=step_code, quantity=1)
        root = ObtainItem(code=root_code, quantity=1)
        production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT,
                                         root=root,
                                         history=None)
        graph = resolve_node(obtain_item_decision(step, root), state, gd,
                             NO_PROFILE_CONTEXT, None)
        assert repr(production) == repr(graph), (
            f"{scenario_name}/step={step_code}/root={root_code}: "
            f"objective_step_goal={production!r} graph={graph!r}")


def test_a_skill_gated_root_raises_the_skill_by_one(bundle_game_data):
    """Robby's live case. gold_sword is weaponcrafting 30 and he has 10. The
    branch used to return GatherMaterials for the step — gather the materials
    for a craft that cannot run — so nothing ever demanded the skill and
    weaponcrafting sat at 10 fleet-wide from 2026-08-16.

    The increment is +1, not the target: the graph re-derives every cycle, so
    planning the whole 10->30 climb is both unnecessary and enormous."""
    gd = bundle_game_data
    root = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    step = ObtainItem(code="gold_bar", quantity=8)
    state = make_state(level=30, skills={"weaponcrafting": 10})

    goal = resolve_node(obtain_item_decision(step, root), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert repr(goal) == "ReachSkill(weaponcrafting->11)"


def test_a_skill_gated_step_that_is_itself_the_equippable_raises_the_skill(
        bundle_game_data):
    """THE SIBLING of the test above, and the half that was missing.

    `CanICraftCurrentTier` sits behind `IsThisAnIntermediateOnAChain`, which is
    only reached when the step is NOT equippable.
    `IsTheStepTheEquippableItself` runs FIRST and, for any equippable step,
    routed straight to `_equippable_goal` without ever asking whether the craft
    can run — so the gate was enforced on the intermediate path and skipped on
    this one.

    Live cost (Robby, 39.6h to 2026-08-27): `elderwood_staff` is
    weaponcrafting 30 and he had 11. The step resolved to the staff itself, so
    this branch returned a gather goal for its materials; the planner then
    spent 1,677 of 2,030 cycles on `LevelSkill(woodcutting->30)` — chasing
    `dead_wood_plank` for a craft 19 weaponcrafting levels out of reach — while
    weaponcrafting never moved off 11 and the character gained 0 xp.

    Same shape as the 2026-07-13 ash_plank case `prerequisites` documents
    ("~56 cycles of WOODCUTTING xp while the weaponcrafting grind it was
    serving stayed frozen"), one tier up."""
    gd = bundle_game_data
    step = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    state = make_state(level=30, skills={"weaponcrafting": 10})

    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert repr(goal) == "ReachSkill(weaponcrafting->11)"


def test_a_skill_gated_equippable_ALREADY_OWNED_is_not_ground_for(
        bundle_game_data):
    """The over-reach the new gate must not commit.

    Holding the item means the craft never has to run — the only step left is
    the equip. Gating on the craft skill alone would send a character who
    already owns the sword away to grind weaponcrafting for a craft it will
    never perform, which is a worse stall than the one being fixed."""
    gd = bundle_game_data
    step = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    state = make_state(level=30, skills={"weaponcrafting": 10},
                       inventory={"gold_sword": 1})

    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert "ReachSkill" not in repr(goal), (
        "owned gear needs equipping, not a skill grind")


def test_a_skill_gated_equippable_held_in_the_BANK_is_not_ground_for(
        bundle_game_data):
    """Same rule, bank side — the copy is one withdraw away, so the craft skill
    is still irrelevant."""
    gd = bundle_game_data
    step = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    state = make_state(level=30, skills={"weaponcrafting": 10},
                       inventory={}, bank_items={"gold_sword": 1})

    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert "ReachSkill" not in repr(goal)


def test_a_skill_gated_equippable_a_VENDOR_SELLS_is_not_ground_for():
    """The second over-reach: the gate must fire only when CRAFTING is the
    route. A ready non-craft source means the skill is irrelevant to getting
    the item, so grinding for it is pure delay.

    BUILT ON A FAKE CATALOGUE DELIBERATELY. The real bundle cannot express this
    case: only 2 of its 271 craftable equippables have any vendor at all
    (`minor_health_potion`, `small_antidote`), and both are sold by
    `nomadic_merchant` — an EVENT npc, so `obtain_sources` correctly returns
    `[]` while the event sleeps and the gate SHOULD fire there. 0 craftable
    equippables are monster drops. So the guard's live surface today is empty,
    and a bundle-based test would assert the opposite of what it looks like it
    asserts."""
    gd = GameData()
    gd._crafting_recipes = {"gold_sword": {"gold_bar": 6}}
    gd._item_stats = {
        "gold_sword": ItemStats(code="gold_sword", level=30, type_="weapon",
                                crafting_skill="weaponcrafting",
                                crafting_level=30),
    }
    gd._npc_stock = {"smith": {"gold_sword": 500}}
    gd._npc_locations = {"smith": (1, 1)}
    step = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    state = make_state(level=30, skills={"weaponcrafting": 10}, gold=10_000,
                       inventory={}, bank_items={})

    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert "ReachSkill" not in repr(goal), (
        "a permanent vendor sells it — buy it rather than grinding 20 levels")


def test_a_dormant_event_vendor_does_not_suppress_the_skill_gate(
        bundle_game_data):
    """The other side, and the reason the test above needs a fake catalogue.

    `minor_health_potion` is alchemy@20 and its ONLY seller is the event npc
    `nomadic_merchant`. While that event sleeps there is no route but the
    craft, so the gate must still fire — a sleeping shop is not an
    alternative."""
    gd = bundle_game_data
    step = ObtainItem(code="minor_health_potion", quantity=1,
                      slot="utility1_slot")
    state = make_state(level=30, skills={"alchemy": 1}, gold=10_000)

    assert obtain_sources("minor_health_potion", state, gd,
                          NO_PROFILE_CONTEXT) == []
    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert repr(goal) == "ReachSkill(alchemy->2)"


def test_an_equippable_step_whose_skill_is_adequate_still_routes_to_gear(
        bundle_game_data):
    """The other side of the new gate: when the craft CAN run, nothing changes.

    Without this the fix could satisfy its sibling by sending every equippable
    step to a skill grind, which would stall gear acquisition entirely."""
    gd = bundle_game_data
    step = ObtainItem(code="gold_sword", quantity=1, slot="weapon_slot")
    state = make_state(level=30, skills={"weaponcrafting": 30})

    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)

    assert "ReachSkill" not in repr(goal)


def test_objective_step_goal_funds_the_currency_leaf():
    """Covers the `analyze_currency_leaves` funding-target branch (`return
    ReachCurrencyGoal(...)`) in both `objective_step_goal` and
    `CanIAffordTheCurrencyLeaf` — the live satchel<-jasper_crystal routing
    (C4 Task 6, see `strategy_driver.py`'s DEMAND ROUTING comment), which no
    (scenario, recipe) pair in the bundle catalog happens to trigger."""
    gd = GameData()
    gd._crafting_recipes = {"satchel": {"jasper_crystal": 1}}
    gd._item_stats = {
        "satchel": ItemStats(code="satchel", level=1, type_="bag",
                             crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._npc_stock = {"tasks_trader": {"jasper_crystal": 8}}
    gd._npc_buy_currency = {"tasks_trader": {"jasper_crystal": "tasks_coin"}}
    gd._task_coin_rewards = {"chicken": 1}
    gd._npc_locations = {"tasks_trader": (4, 1)}
    state = make_state(skills={"gearcrafting": 5}, inventory={}, bank_items={}, x=0, y=0)
    step = ObtainItem("satchel", 1)
    production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=step)
    graph = resolve_node(obtain_item_decision(step, step), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(production, ReachCurrencyGoal)
    assert repr(graph) == repr(production)


def test_objective_step_goal_returns_the_reachable_root_chunk():
    """Covers the `_gather_step_target_is_root` positive branch (`return
    upgrade`) in both `objective_step_goal` and `DoesTheChainFitTheDepthBudget`
    — never hit by the bundle-catalog sweep above because none of its (recipe,
    material) pairs happens to be depth-reachable from empty holdings within
    the default `max_depth`."""
    gd = _gd()  # wooden_shield <- ash_plank x6 <- ash_wood: shallow chain
    state = make_state()
    step = ObtainItem("ash_plank", 6)
    root = ObtainItem("wooden_shield", 1)
    production = objective_step_goal(step, state, gd, NO_PROFILE_CONTEXT, root=root)
    graph = resolve_node(obtain_item_decision(step, root), state, gd,
                         NO_PROFILE_CONTEXT, None)
    assert isinstance(production, UpgradeEquipmentGoal)
    assert repr(graph) == repr(production)


def test_objective_step_goal_returns_none_for_step_none():
    """`step is None` -> `None`, unreached by the ObtainItem-only Decision
    graph (it has no node for a missing step at all)."""
    assert objective_step_goal(None, make_state(), _gd(), _ctx()) is None


def test_objective_step_goal_returns_none_for_unrecognized_step():
    """Covers the final `return None` fallback for a step that is neither
    `ObtainItem` nor `ReachCharLevel`."""
    class _UnknownStep:
        pass

    assert objective_step_goal(_UnknownStep(), make_state(), _gd(), _ctx()) is None  # type: ignore[arg-type]


def test_objective_step_goal_returns_none_for_reach_char_level_no_monster():
    """`ctx.combat_monster is None` -> early `return None`."""
    step = ReachCharLevel(10)
    ctx = _ctx(combat_monster=None)
    assert objective_step_goal(step, make_state(), _gd(), ctx) is None


def test_objective_step_goal_stands_down_for_reach_char_level_items_task():
    """Items-task stand-down: `objective_step_is_fight_pure` False -> None
    for the long-haul ReachCharLevel(50) step."""
    state = make_state(level=3, task_code="copper_bar", task_type="items",
                       task_total=20, task_progress=0)
    step = ReachCharLevel(50)
    ctx = _ctx(combat_monster="chicken")
    assert objective_step_goal(step, state, GameData(), ctx) is None


def test_objective_step_goal_grinds_for_reach_char_level():
    """No provision goal available -> falls through to GrindCharacterXPGoal."""
    step = ReachCharLevel(10)
    state = make_state(xp=50)
    ctx = _ctx(combat_monster="chicken")
    goal = objective_step_goal(step, state, _gd(), ctx)
    assert isinstance(goal, GrindCharacterXPGoal)


def test_objective_step_goal_provisions_for_reach_char_level(tmp_path):
    """`_marginal_provision_goal` returns a goal -> `return provision`."""
    state = make_state(level=3, inventory={"small_health_potion": 100})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    history = LearningStore(db_path=str(tmp_path / "l.db"), character="r")
    _record_fight_wins_with_consumables(
        history, "green_slime", 8, json.dumps({"small_health_potion": 2}))
    ctx = _ctx(combat_monster="green_slime")
    step = ReachCharLevel(level=5)
    goal = objective_step_goal(step, state, gd, ctx, history=history)
    assert isinstance(goal, ProvisionMarginalFightGoal)
    history.close()


# --- the unwinnable-dropper wall: gear, not a doomed gather ------------------

def _grind_store(skill: str = "weaponcrafting", xp_per_cycle: int = 40
                 ) -> LearningStore:
    """A real store carrying an observed grind rate for `skill`.

    The node prices its gear target through `route_price`, and a skill-gated
    craft cannot be priced without an observed rate — so without this the node
    declines every case in the committed set, exactly as
    `acquisition_cost._gated_drop_option` does. Store-fed is the production
    shape; `test_without_a_grind_rate_the_node_declines` pins the other half."""
    store = LearningStore(db_path=":memory:", character="wall_probe")
    store.start_session()
    for i in range(5):
        store.record_cycle(Cycle(
            ts=f"2026-08-08T00:00:{i:02d}+00:00", session_id="s", cycle_index=i,
            character="wall_probe", outcome="ok",
            action_repr=f"LevelSkill({skill}->10)",
            delta_skill_xp_json=json.dumps({skill: xp_per_cycle})))
    return store


def _with_skill_xp(state):
    """`scenario_state` leaves `skill_xp`/`skill_max_xp` empty; a real
    `WorldState` always carries them, and the grind price needs them."""
    return dataclasses.replace(
        state, skill_xp={s: 0 for s in state.skills},
        skill_max_xp={s: 1000 for s in state.skills})


def test_a_material_walled_by_an_unbeatable_dropper_routes_to_the_GEAR(
        bundle_game_data) -> None:
    """THE DECISION-SIDE HALF of the drop wall, and the whole reason the census
    was built.

    `cowhide` drops only from `cow`, which this character loses to, so
    `obtain_sources` serves NOTHING and the graph emitted
    `GatherMaterials(cowhide, {cowhide:5})` — a gather goal for a material with
    no gather, which cannot plan on any cycle it is selected. Measured on the
    committed bundle before this node: 10 such cells, each emitting exactly that.
    It is the same silence the gold wall had, one layer down.

    `combat_deficit` closes `cow` with `iron_sword`, so the honest answer is the
    sword. The node re-enters the graph AT the gear step rather than choosing a
    goal itself, so the craft-skill gate and the chunking arms apply to the sword
    exactly as if it had been the step all along — which is why the answer here
    is the weaponcrafting climb the sword needs, not the sword."""
    gd = bundle_game_data
    state = _with_skill_xp(scenario_state(SCENARIOS["l12_deep_chain_grind"], gd))
    step = ObtainItem(code="cowhide", quantity=5)
    assert not obtain_sources("cowhide", state, gd, NO_PROFILE_CONTEXT)
    store = _grind_store()
    try:
        goal = resolve_node(obtain_item_decision(step, step), state, gd,
                            NO_PROFILE_CONTEXT, store)
        assert "cowhide" not in repr(goal), (
            f"still routing to the walled material itself: {goal!r}")
        assert "weaponcrafting" in repr(goal) or "iron_sword" in repr(goal), (
            f"expected the gear that opens the cow, got {goal!r}")
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_without_a_grind_rate_the_node_declines(bundle_game_data) -> None:
    """UNREACHABLE GEAR DECLINES, and an unpriceable one is unreachable as far as
    this node can tell.

    Same rule `_gated_craft_option` states and the same live reason: a target
    that looks free does not merely fail to prune, it CAPTURES the bot. Declining
    leaves the honest wall in place, which is worse to look at and better to
    have."""
    gd = bundle_game_data
    state = _with_skill_xp(scenario_state(SCENARIOS["l12_deep_chain_grind"], gd))
    step = ObtainItem(code="cowhide", quantity=5)
    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)
    assert repr(goal) == "GatherMaterials(cowhide, {cowhide:5})"


def test_a_material_with_a_route_is_untouched(bundle_game_data) -> None:
    """The node must fire ONLY on the wall: an item something can serve keeps
    today's answer, whatever its drop table says."""
    gd = bundle_game_data
    state = scenario_state(SCENARIOS["l12_deep_chain_grind"], gd)
    step = ObtainItem(code="copper_ore", quantity=5)
    assert obtain_sources("copper_ore", state, gd, NO_PROFILE_CONTEXT)
    goal = resolve_node(obtain_item_decision(step, step), state, gd,
                        NO_PROFILE_CONTEXT, None)
    assert "copper_ore" in repr(goal)


def test_an_unreachable_closing_chain_keeps_the_honest_wall(
        bundle_game_data) -> None:
    """`mushroom` is the case, and it is the circularity the 2026-08-09 audit
    feared rather than a hypothetical: `mushmush` is closed by `forest_whip`,
    whose recipe wants `king_slimeball` — guarded by `king_slime`, a monster this
    character also cannot beat. Pricing that needs a FIXED POINT, so the price
    says unobtainable and the node declines."""
    gd = bundle_game_data
    state = _with_skill_xp(scenario_state(SCENARIOS["l20_boost_stock"], gd))
    step = ObtainItem(code="mushroom", quantity=4)
    store = _grind_store()
    try:
        assert not obtain_sources("mushroom", state, gd, NO_PROFILE_CONTEXT)
        goal = resolve_node(obtain_item_decision(step, step), state, gd,
                            NO_PROFILE_CONTEXT, store)
        assert repr(goal) == "GatherMaterials(mushroom, {mushroom:4})"
    finally:
        store.end_session(exit_reason="normal")
        store.close()


def test_where_the_wall_is_reached_and_why_no_cycle_acts_on_it(
        bundle_game_data) -> None:
    """CORPUS-WIDE, and it pins the limit as hard as the feature.

    Ten cells over the committed scenarios reach a drop-walled material as a
    step. Where the closing gear is priceable the node answers with it; where it
    is not, the honest wall stays.

    ⚠️ ALL TEN REACH IT AS AN *ALTERNATIVE*, never as the chosen root, so no
    cycle in the committed corpus acts on this node: `_servable_promotion` walks
    the alternatives only when the CHOSEN root is unservable, and the root walk
    always has another servable rung — a blocked gear target returns a skill
    climb (`IsThisTargetBlocked`) rather than confronting the wall. Measured
    through `plan_from_state` over all 44 scenarios, with and without the node:
    **0 cells select a different goal**. The node is the right answer for a state
    the corpus does not reach, and the second assertion below fails the day one
    does — which is the day this docstring needs rewriting."""
    gd = bundle_game_data
    store = _grind_store()
    reached: list[tuple[str, bool]] = []
    try:
        for name, scenario in SCENARIOS.items():
            state = _with_skill_xp(scenario_state(scenario, gd))
            resolution = resolve_root(state, gd,
                                      CharacterObjective.from_game_data(gd),
                                      NO_PROFILE_CONTEXT, store)
            walled = set(unwinnable_drop_items(state, gd))
            for root in [c for c in (resolution.root, *resolution.alternatives)
                         if c is not None]:
                step = actionable_step(root, state, gd, NO_PROFILE_CONTEXT) or root
                if (not isinstance(step, ObtainItem) or step.code not in walled
                        or obtain_sources(step.code, state, gd, NO_PROFILE_CONTEXT)):
                    continue
                reached.append((name, root is resolution.root))
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    assert len(reached) >= 10, (
        f"only {len(reached)} walled steps reached — the fixture set moved and "
        "this test now measures less than it claims")
    assert not any(is_chosen for _name, is_chosen in reached), (
        "a walled step is now on a CHOSEN root's path — this node finally acts "
        "on a live cycle, and the docstring above needs rewriting")
