"""Task-material reservation (P0 2026-06-09): unit tests for the pure
`task_reservation` module plus the trace-locked strategy-driver regression.

Production trace: while PursueTask(copper_bar items task 0/11) pooled crafted
bars, the skill-grind step GatherMaterials(copper_helmet) became plannable the
instant bars existed, won the step tier (committed PursueTask is permanently
worth-suppressed for items tasks — it only runs via the bypass pass), and
Craft(copper_helmet) ate 6 bars. Task restarted from zero, forever.
"""

from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.planner import PlanStats
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.task_reservation import consumes_reserved, task_reserved_demand
from artifactsmmo_cli.ai.tiers.means import MeansKind
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    """Trace fixture: copper_helmet <- 6 copper_bar <- 10 copper_ore."""
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6},
                            "copper_bar": {"copper_ore": 10}}
    gd._resource_locations = {"copper_rocks": [(1, 0)]}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    return gd


def _task_state(**overrides):
    base = dict(
        level=5, hp=150, max_hp=150, inventory_max=100,
        task_code="copper_bar", task_type="items",
        task_progress=0, task_total=11,
        skills={"mining": 5, "gearcrafting": 1},
        inventory={"copper_bar": 5},
    )
    base.update(overrides)
    return make_state(**base)


# ---------------------------------------------------------------------------
# task_reserved_demand
# ---------------------------------------------------------------------------

def test_demand_scales_with_remaining():
    """Demand = closure of the task item x remaining (item + transitive inputs)."""
    state = _task_state()
    assert task_reserved_demand(state, _gd()) == {
        "copper_bar": 11, "copper_ore": 110,
    }


def test_demand_shrinks_as_progress_advances():
    """progress up => demand pointwise down (mirrors Lean demand_monotone)."""
    gd = _gd()
    at_zero = task_reserved_demand(_task_state(task_progress=0), gd)
    at_seven = task_reserved_demand(_task_state(task_progress=7), gd)
    assert at_seven == {"copper_bar": 4, "copper_ore": 40}
    assert all(at_seven[k] <= at_zero[k] for k in at_seven)


def test_remaining_zero_reserves_nothing():
    """Task complete => empty demand and nothing suppressed."""
    state = _task_state(task_progress=11)
    gd = _gd()
    assert task_reserved_demand(state, gd) == {}
    assert consumes_reserved({"copper_helmet": 1}, state, gd) is False


def test_non_items_task_reserves_nothing():
    state = _task_state(task_type="monsters", task_code="chicken")
    gd = _gd()
    assert task_reserved_demand(state, gd) == {}
    assert consumes_reserved({"copper_helmet": 1}, state, gd) is False


def test_no_task_reserves_nothing():
    state = _task_state(task_code=None, task_type=None, task_progress=0,
                        task_total=0)
    assert task_reserved_demand(state, _gd()) == {}


def test_recipeless_task_item_reserves_the_raw_item():
    """A raw-gather items task (no recipe) reserves the raw item itself."""
    state = _task_state(task_code="copper_ore", task_total=30,
                        inventory={"copper_ore": 10})
    gd = _gd()
    assert task_reserved_demand(state, gd) == {"copper_ore": 30}
    # A step gathering that same ore (e.g. for a bar) consumes the reserve.
    assert consumes_reserved({"copper_ore": 5}, state, gd) is True


def test_closure_cycle_safe():
    """Cyclic recipes terminate (visited guard) and still record both items."""
    gd = GameData()
    gd._crafting_recipes = {"a": {"b": 2}, "b": {"a": 3}}
    state = _task_state(task_code="a", task_total=2, inventory={})
    demand = task_reserved_demand(state, gd)
    assert demand["a"] == 2
    assert demand["b"] == 4


# ---------------------------------------------------------------------------
# consumes_reserved — surplus boundary + ownership semantics
# ---------------------------------------------------------------------------

def test_owned_at_demand_is_suppressed_owned_above_is_free():
    """Boundary: owned == demand => suppressed (no surplus); owned == demand +
    the step's own need => free (the step eats only surplus)."""
    gd = _gd()
    at_demand = _task_state(inventory={"copper_bar": 11})
    assert consumes_reserved({"copper_helmet": 1}, at_demand, gd) is True
    with_need = _task_state(inventory={"copper_bar": 17})  # 11 demand + 6 need
    assert consumes_reserved({"copper_helmet": 1}, with_need, gd) is False
    just_above = _task_state(inventory={"copper_bar": 12})
    assert consumes_reserved({"copper_helmet": 1}, just_above, gd) is False


def test_unowned_reserved_item_does_not_suppress():
    """owned(r) == 0 => nothing to steal yet => not suppressed this cycle."""
    state = _task_state(inventory={})
    assert consumes_reserved({"copper_helmet": 1}, state, _gd()) is False


def test_unrelated_closure_does_not_suppress():
    """A step whose closure shares nothing with the task chain passes."""
    gd = _gd()
    gd._crafting_recipes["wooden_shield"] = {"ash_wood": 6}
    state = _task_state(inventory={"copper_bar": 5, "ash_wood": 2})
    assert consumes_reserved({"wooden_shield": 1}, state, gd) is False


def test_bank_counts_toward_owned():
    """Surplus split across inventory + bank is still surplus."""
    state = _task_state(inventory={"copper_bar": 5},
                        bank_items={"copper_bar": 95})
    assert consumes_reserved({"copper_helmet": 1}, state, _gd()) is False


def test_bank_none_is_conservative():
    """bank_items None reads as 0 — same on-hand stock defers (never assumes
    unseen bank surplus)."""
    state = _task_state(inventory={"copper_bar": 5}, bank_items=None)
    assert consumes_reserved({"copper_helmet": 1}, state, _gd()) is True


# ---------------------------------------------------------------------------
# Strategy-driver wiring — _TrivialPlanner harness for the reservation units
# ---------------------------------------------------------------------------

class _TrivialPlanner:
    """Constructor-injected GOAPPlanner stand-in: plans every goal as a single
    WaitAction so the arbiter tests exercise SELECTION (suppression/worth/
    bypass), not A* search. Arrives through the existing constructor param —
    the unit under test is never patched."""

    def __init__(self) -> None:
        self.last_stats = PlanStats()

    def plan(self, state, goal, actions, game_data, history, budget_seconds=None):
        return [WaitAction()]


# ---------------------------------------------------------------------------
# _suppress_step_for_task — reservation clause unit coverage
# ---------------------------------------------------------------------------

def _arbiter() -> StrategyArbiter:
    return StrategyArbiter(_TrivialPlanner(), history=None)


def test_suppress_task_complete_allows_step():
    """remaining == 0 => the reservation is inert and the step passes."""
    state = _task_state(task_progress=11)
    goal = GatherMaterialsGoal(target_item="copper_helmet",
                               needed={"copper_helmet": 1})
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is goal


def test_suppress_upgrade_equipment_consuming_reserved_inputs():
    """A committed UpgradeEquipment whose craft consumes reserved bars is
    deferred (the craft+equip plan would eat the task pool)."""
    state = _task_state()
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                committed_target=("copper_helmet", "helmet_slot"))
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is None


def test_owned_upgrade_target_is_one_action_equip_never_deferred():
    """The helmet already owned => equip consumes nothing => step passes
    (preserves the trace-2026-06-06 ready-to-equip priority)."""
    state = _task_state(inventory={"copper_bar": 5, "copper_helmet": 1})
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                committed_target=("copper_helmet", "helmet_slot"))
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is goal


def test_uncommitted_upgrade_equipment_passes():
    """No committed target => no known consumption => step passes."""
    state = _task_state()
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment)
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is goal


def test_recipeless_committed_target_passes():
    """A committed target with no recipe consumes no materials => passes."""
    state = _task_state()
    goal = UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                committed_target=("copper_ore", "helmet_slot"))
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is goal


def test_trade_ready_clause_still_fires_on_surplus():
    """With SURPLUS bars (reservation passes) the pre-existing trade-ready
    rule still defers a gather targeting the task item itself: task 20/21,
    2 bars held (demand 1) — trade now instead of gathering more."""
    state = _task_state(task_progress=20, task_total=21,
                        inventory={"copper_bar": 2})
    goal = GatherMaterialsGoal(target_item="copper_bar",
                               needed={"copper_bar": 8})
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is None


def test_non_consuming_goal_type_passes():
    """ReachSkill (no craft closure) is a sustained goal — never deferred."""
    state = _task_state()
    goal = ReachSkillGoal(skill_name="gearcrafting", target_level=5)
    out = _arbiter()._suppress_step_for_task(
        goal, [MeansKind.PURSUE_TASK], state, _gd())
    assert out is goal
