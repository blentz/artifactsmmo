from dataclasses import dataclass

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction, TaskCancelAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.level_skill import LevelSkillGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import (
    FALLBACK_BAND,
    STRATEGY_BAND,
    MetaGoalAdapter,
    StrategyArbiter,
    map_guard,
    map_means,
    objective_step_goal,
    strategy_goal,
)
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from tests.test_ai.fixtures import make_state


def _gd():
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   resistance={"earth": 5}, crafting_skill="gearcrafting", crafting_level=1),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"wooden_shield": {"ash_plank": 6}, "ash_plank": {"ash_wood": 1}}
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    return gd


def _ctx(**kw):
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


# ---------------------------------------------------------------------------
# Existing tests (legacy MetaGoalAdapter / strategy_goal)
# ---------------------------------------------------------------------------

def test_adapter_delegates_and_fixes_priority():
    inner = GatherMaterialsGoal(target_item="ash_plank", needed={"ash_plank": 6})
    adapter = MetaGoalAdapter(inner, STRATEGY_BAND)
    s = make_state(inventory={"ash_plank": 6})
    assert adapter.is_satisfied(s) == inner.is_satisfied(s)
    assert adapter.desired_state(s, _gd()) == inner.desired_state(s, _gd())
    assert adapter.priority(make_state(), _gd()) == STRATEGY_BAND
    assert adapter.max_depth == inner.max_depth
    assert "GatherMaterials" in repr(adapter)
    gd = _gd()
    s2 = make_state()
    assert adapter.value(s2, gd) == inner.value(s2, gd)                       # delegates heuristic
    assert adapter.relevant_actions([], s2, gd) == inner.relevant_actions([], s2, gd)


def test_material_obtain_maps_to_gather_materials():
    g = strategy_goal(ObtainItem("ash_plank", 6), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g, MetaGoalAdapter)
    assert isinstance(g._inner, GatherMaterialsGoal)
    assert g._inner._needed == {"ash_plank": 6}


def test_gear_obtain_maps_to_upgrade_equipment_with_committed_target():
    g = strategy_goal(ObtainItem("wooden_shield", 1), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, UpgradeEquipmentGoal)
    assert g._inner._committed_target == ("wooden_shield", "shield_slot")


def test_skill_maps_to_level_skill():
    g = strategy_goal(ReachSkillLevel("mining", 50), make_state(), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, LevelSkillGoal)
    assert g._inner._skill_name == "mining" and g._inner._target_level == 50


def test_char_level_maps_to_grind_with_initial_xp_and_monster():
    g = strategy_goal(ReachCharLevel(50), make_state(xp=120), _gd(), STRATEGY_BAND, "chicken")
    assert isinstance(g._inner, GrindCharacterXPGoal)
    assert g._inner._target_monster == "chicken" and g._inner._initial_xp == 120


def test_char_level_none_when_no_monster():
    assert strategy_goal(ReachCharLevel(50), make_state(), _gd(), STRATEGY_BAND, None) is None


def test_strategy_goal_none_for_none_step():
    assert strategy_goal(None, make_state(), _gd(), STRATEGY_BAND, "chicken") is None


def test_fallback_band_below_strategy_band():
    assert FALLBACK_BAND < STRATEGY_BAND


# ---------------------------------------------------------------------------
# map_guard unit tests
# ---------------------------------------------------------------------------

def test_map_guard_hp_critical():
    assert isinstance(map_guard(GuardKind.HP_CRITICAL, GameData(), _ctx()), RestoreHPGoal)


def test_map_guard_discard_critical():
    g = map_guard(GuardKind.DISCARD_CRITICAL, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_discard_high():
    g = map_guard(GuardKind.DISCARD_HIGH, GameData(), _ctx())
    assert isinstance(g, DiscardOverstockGoal)


def test_map_guard_bank_unlock():
    ctx = _ctx(bank_accessible=False, bank_unlock_monster="chicken", initial_xp=100)
    g = map_guard(GuardKind.BANK_UNLOCK, GameData(), ctx)
    assert isinstance(g, UnlockBankGoal)


def test_map_guard_reach_unlock_level():
    ctx = _ctx(bank_required_level=5)
    g = map_guard(GuardKind.REACH_UNLOCK_LEVEL, GameData(), ctx)
    assert isinstance(g, ReachUnlockLevelGoal)


def test_map_guard_deposit_full():
    g = map_guard(GuardKind.DEPOSIT_FULL, GameData(), _ctx())
    assert isinstance(g, DepositInventoryGoal)


def test_map_guard_unknown_raises():
    with pytest.raises(ValueError):
        map_guard("bogus", GameData(), _ctx())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# map_means unit tests
# ---------------------------------------------------------------------------

def test_map_means_claim_pending():
    assert isinstance(map_means(MeansKind.CLAIM_PENDING, GameData(), _ctx()), ClaimPendingGoal)


def test_map_means_complete_task():
    assert isinstance(map_means(MeansKind.COMPLETE_TASK, GameData(), _ctx()), CompleteTaskGoal)


def test_map_means_sell_pressured():
    assert isinstance(map_means(MeansKind.SELL_PRESSURED, GameData(), _ctx()), SellInventoryGoal)


def test_map_means_sell_idle():
    assert isinstance(map_means(MeansKind.SELL_IDLE, GameData(), _ctx()), SellInventoryGoal)


def test_map_means_low_yield_cancel():
    assert isinstance(map_means(MeansKind.LOW_YIELD_CANCEL, GameData(), _ctx()), LowYieldCancelGoal)


def test_map_means_task_cancel():
    assert isinstance(map_means(MeansKind.TASK_CANCEL, GameData(), _ctx()), TaskCancelGoal)


def test_map_means_accept_task():
    assert isinstance(map_means(MeansKind.ACCEPT_TASK, GameData(), _ctx()), AcceptTaskGoal)


def test_map_means_task_exchange():
    g = map_means(MeansKind.TASK_EXCHANGE, GameData(), _ctx(task_exchange_min_coins=3))
    assert isinstance(g, TaskExchangeGoal)


def test_map_means_bank_expand():
    assert isinstance(map_means(MeansKind.BANK_EXPAND, GameData(), _ctx()), ExpandBankGoal)


def test_map_means_unknown_raises():
    with pytest.raises(ValueError):
        map_means("bogus", GameData(), _ctx())  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# objective_step_goal unit tests
# ---------------------------------------------------------------------------

def test_objective_step_obtain_gear():
    gd = _gd()
    step = ObtainItem("wooden_shield", 1)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, UpgradeEquipmentGoal)
    assert g._committed_target == ("wooden_shield", "shield_slot")


def test_objective_step_obtain_material():
    gd = _gd()
    step = ObtainItem("ash_plank", 6)
    g = objective_step_goal(step, make_state(), gd, _ctx())
    assert isinstance(g, GatherMaterialsGoal)
    assert g._needed == {"ash_plank": 6}


def test_objective_step_reach_skill_level():
    step = ReachSkillLevel("mining", 10)
    g = objective_step_goal(step, make_state(), _gd(), _ctx())
    assert isinstance(g, LevelSkillGoal)
    assert g._skill_name == "mining" and g._target_level == 10


def test_objective_step_reach_char_level_with_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(xp=50), _gd(), _ctx(combat_monster="chicken"))
    assert isinstance(g, GrindCharacterXPGoal)
    assert g._target_monster == "chicken" and g._initial_xp == 50


def test_objective_step_reach_char_level_no_monster():
    step = ReachCharLevel(10)
    g = objective_step_goal(step, make_state(), _gd(), _ctx(combat_monster=None))
    assert g is None


def test_objective_step_none_step():
    g = objective_step_goal(None, make_state(), _gd(), _ctx())
    assert g is None


# ---------------------------------------------------------------------------
# Helper stub for StrategyDecision (only chosen_step is used by StrategyArbiter)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class _FakeDecision:
    chosen_step: ObtainItem | ReachCharLevel | ReachSkillLevel | None


def _make_planner_gd() -> GameData:
    """Minimal GameData that lets the planner resolve Accept/Fight/Rest actions."""
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    return gd


# ---------------------------------------------------------------------------
# StrategyArbiter integration tests
# ---------------------------------------------------------------------------

def test_select_guard_preempts_means():
    """HP-critical guard fires: even if AcceptTask means is queued, RestoreHP wins."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # state: no task (AcceptTask fires), but HP is critical
    state = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    actions = [
        RestAction(),
        AcceptTaskAction(taskmaster_location=(2, 1)),
    ]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, RestoreHPGoal), f"expected RestoreHPGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_returns_objective_step_when_calm():
    """No guards, no collect-reward means; chosen_step→GrindCharacterXP plans."""
    planner = GOAPPlanner()
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    # Level 1 char with HP full, no task (so AcceptTask would fire as discretionary,
    # but chosen_step goal (GrindCharacterXP) appears before discretionary).
    # Use xp=0 and initial_xp=0 to make GrindXP not satisfied.
    state = make_state(level=1, hp=150, max_hp=150, xp=0, max_xp=500, task_code=None, task_total=0)
    actions = [FightAction(monster_code="chicken", locations=frozenset([(1, 0)]))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, GrindCharacterXPGoal), f"expected GrindCharacterXPGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_falls_through_unplannable_to_next():
    """No guard fires; chosen_step can't plan (no FightAction); AcceptTask CAN → returns AcceptTask."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # Calm state: HP full, no bag pressure, no task (so AcceptTask fires as discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    # Provide AcceptTaskAction but NO FightAction → ReachCharLevel (GrindCharacterXP) cannot plan,
    # AcceptTaskGoal CAN plan via AcceptTaskAction.
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    # chosen_step is ReachCharLevel → maps to GrindCharacterXPGoal which needs FightAction
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal, AcceptTaskGoal), f"expected AcceptTaskGoal, got {goal!r}"
    assert len(plan) >= 1


def test_select_returns_none_when_nothing_plans():
    """No plannable goal → (None, [], goals_tried)."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code="chicken", task_type="monster",
                       task_progress=0, task_total=5)
    actions: list = []  # no actions at all
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)
    goal, plan, goals_tried = arbiter.select(decision, state, gd, actions, ctx)
    assert goal is None
    assert plan == []


def test_select_skips_suppressed_means():
    """A means whose repr is in `suppressed` is skipped, falling through."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx(combat_monster="chicken")
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=ReachCharLevel(5))
    # Without suppression AcceptTask would be selected; suppress it.
    goal, plan, tried = arbiter.select(
        decision, state, gd, actions, ctx, suppressed={"AcceptTask"})
    assert goal is None or repr(goal) != "AcceptTask"
    assert not any(gt["goal"] == "AcceptTask" for gt in tried)


def test_select_never_suppresses_task_cancel(tmp_path):
    """TaskCancel is the escape hatch and must never be filtered by suppression."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # A monsters task far above the character's level → task_decision PIVOTs, so
    # TASK_CANCEL fires (requires a non-None history). No FightAction is given so
    # nothing else plans, forcing the walk to reach the (suppressed) TaskCancel.
    gd._monster_level["dragon"] = 50
    store = LearningStore(db_path=str(tmp_path / "tc.db"), character="hero")
    try:
        state = make_state(level=5, hp=150, max_hp=150, task_code="dragon",
                           task_type="monsters", task_progress=0, task_total=5)
        actions = [TaskCancelAction(taskmaster_location=(2, 1))]
        ctx = _ctx()
        arbiter = StrategyArbiter(planner, history=store)
        decision = _FakeDecision(chosen_step=None)
        _goal, _plan, tried = arbiter.select(
            decision, state, gd, actions, ctx, suppressed={"TaskCancel"})
        assert any(gt["goal"] == "TaskCancel" for gt in tried), (
            "TaskCancel must not be skipped even when suppressed"
        )
    finally:
        store.close()


def test_select_sticky_keeps_committed_means():
    """If a means committed on cycle 1 still fires and plans, cycle 2 returns same repr."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires (discretionary)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    goal1, plan1, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal), f"cycle 1: expected AcceptTask, got {goal1!r}"

    # Cycle 2: state unchanged, AcceptTask still fires and plans
    goal2, plan2, _ = arbiter.select(decision, state, gd, actions, ctx)
    assert repr(goal2) == repr(goal1), f"cycle 2: expected sticky {goal1!r}, got {goal2!r}"


def test_select_no_double_count_when_committed_becomes_unplannable():
    """Fix 1: committed means unplannable on cycle 2 must not appear twice in goals_tried."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    # No task: AcceptTask fires as discretionary; AcceptTaskAction enables it to plan.
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions_with_accept = [AcceptTaskAction(taskmaster_location=(2, 1))]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: AcceptTask commits
    goal1, plan1, _ = arbiter.select(decision, state, gd, actions_with_accept, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: remove AcceptTaskAction so the committed goal can't plan;
    # provide no other plannable action either → expect (None, [])
    goal2, plan2, tried2 = arbiter.select(decision, state, gd, [], ctx)
    assert goal2 is None

    # AcceptTask repr must appear at most once in goals_tried (not double-counted)
    accept_reprs = [e["goal"] for e in tried2 if e["goal"] == repr(AcceptTaskGoal())]
    assert len(accept_reprs) <= 1, f"double-counted: {tried2}"


def test_select_guard_clears_committed_repr():
    """Fix 2: when a guard fires and plans, _committed_repr is cleared (not left stale)."""
    planner = GOAPPlanner()
    gd = _make_planner_gd()
    state_calm = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [
        AcceptTaskAction(taskmaster_location=(2, 1)),
        RestAction(),
    ]
    ctx = _ctx()
    arbiter = StrategyArbiter(planner, history=None)
    decision = _FakeDecision(chosen_step=None)

    # Cycle 1: calm state — AcceptTask commits
    goal1, _, _ = arbiter.select(decision, state_calm, gd, actions, ctx)
    assert isinstance(goal1, AcceptTaskGoal)
    assert arbiter._committed_repr is not None

    # Cycle 2: HP now critical — RestoreHP guard fires and plans
    state_low_hp = make_state(hp=10, max_hp=150, task_code=None, task_total=0)
    goal2, plan2, _ = arbiter.select(decision, state_low_hp, gd, actions, ctx)
    assert isinstance(goal2, RestoreHPGoal), f"expected RestoreHPGoal, got {goal2!r}"
    assert len(plan2) >= 1
    # commitment must be cleared after a guard return
    assert arbiter._committed_repr is None
