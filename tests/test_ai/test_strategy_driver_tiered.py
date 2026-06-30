"""Tiered selection: cheap pass, escalate only when cheap empty, memoize timeouts.

A scripted planner returns a plan for a goal only when given >= its required
budget, letting us assert pass behavior deterministically."""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import CHEAP_BUDGET_SECONDS as CHEAP
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd


class _ScriptedPlanner:
    """Plans `[WaitAction()]` for goal reprs in `cheap_ok` at any budget; for reprs
    in `full_only` only when budget is None (full). Records budgets per goal."""
    def __init__(self, cheap_ok, full_only):
        self.cheap_ok = set(cheap_ok)
        self.full_only = set(full_only)
        self.budgets = []
        self.last_stats = GOAPPlanner().last_stats

    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        r = repr(goal)
        self.budgets.append((r, budget_seconds))
        if r in self.cheap_ok:
            self.last_stats.timed_out = False
            return [WaitAction()]
        if r in self.full_only and budget_seconds is None:
            self.last_stats.timed_out = False
            return [WaitAction()]
        # No plan. A `full_only` goal at the CHEAP budget timed out (it needs more
        # budget — a deterministic exhaustive search that finished empty could
        # never plan with more time); anything else exhausted the space.
        self.last_stats.timed_out = r in self.full_only and budget_seconds is not None
        return []


def test_cheap_budget_is_ten_seconds():
    # Sized above the ~7.5s I/O-bound planning time of a reachable goal under
    # --learn so the cheap pass doesn't starve real goals (live-bot fix).
    assert CHEAP == 10.0


def _arbiter_with(planner):
    a = StrategyArbiter(planner, history=None)
    a.set_cycle(0)
    return a


def test_cheap_pass_selects_cheaply_plannable_and_skips_escalation():
    # A discretionary goal that plans cheap is selected; planner never asked for full budget.
    planner = _ScriptedPlanner(cheap_ok={"AcceptTask"}, full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    decision = _FakeDecision(chosen_step=None)
    goal, _plan, _ = a.select(decision, state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert all(b == CHEAP for (r, b) in planner.budgets if r == "AcceptTask")


def test_escalates_to_full_when_nothing_cheap():
    # AcceptTask only plans at full budget → cheap pass empty → escalation selects it.
    planner = _ScriptedPlanner(cheap_ok=set(), full_only={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    goal, _plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))], _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert any(b is None for (r, b) in planner.budgets if r == "AcceptTask")


def test_timed_out_goal_is_memoized_and_skipped_next_cycle():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())  # nothing ever plans
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    ctx = _ctx(combat_monster="chicken")
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle0 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    planner.budgets.clear()
    a.set_cycle(1)
    a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), actions, ctx)
    calls_cycle1 = len([1 for (r, _) in planner.budgets if r == "AcceptTask"])
    assert calls_cycle0 >= 1
    assert calls_cycle1 == 0, "memoized goal must be skipped on the next cycle"


def test_wait_selected_when_nothing_plans():
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(goal, WaitGoal)
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)


def test_cheap_pass_memoizes_conclusively_failed_goal_passed_over_in_walk():
    """The feather_coat 99%-CPU peg: a goal that EXHAUSTS the search (no plan,
    timed_out=False) in the cheap walk must be memoized even though a LATER goal
    wins cheaply (so escalation never runs). Pre-fix only the full pass marked, so
    a passed-over exhausted goal re-exploded every cycle. `_record_attempt` with
    mark_on_timeout=False marks it conclusively."""
    a = _arbiter_with(_ScriptedPlanner(cheap_ok=set(), full_only=set()))
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    # Conclusive cheap failure (search exhausted, NOT a budget timeout).
    a._record_attempt(goal, [], timed_out=False, state=state,
                      guard_reprs=set(), mark_on_timeout=False)
    assert a._memo.is_doomed(repr(goal), state, 1), \
        "an exhausted cheap-pass failure must be memoized (the feather_coat fix)"


def test_cheap_pass_timeout_is_not_memoized_so_it_can_escalate():
    """A cheap-budget TIMEOUT is inconclusive — more budget may find a plan — so
    the cheap pass must NOT memoize it; it has to remain available for the
    full-budget escalation pass."""
    a = _arbiter_with(_ScriptedPlanner(cheap_ok=set(), full_only=set()))
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=True, state=state,
                      guard_reprs=set(), mark_on_timeout=False)
    assert not a._memo.is_doomed(repr(goal), state, 1), \
        "a cheap-pass timeout must stay retryable (escalation), not be memoized"


def test_full_pass_memoizes_on_timeout():
    """The full (last-resort) pass keeps the pre-existing behavior: mark on ANY
    no-plan, timeout included — a full-budget timeout is the pragmatic backoff
    trigger (the exponential window re-probes later)."""
    a = _arbiter_with(_ScriptedPlanner(cheap_ok=set(), full_only=set()))
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=True, state=state,
                      guard_reprs=set(), mark_on_timeout=True)
    assert a._memo.is_doomed(repr(goal), state, 1)


def test_record_attempt_clears_memo_on_success():
    """A found plan clears any prior doomed mark (the goal became plannable)."""
    a = _arbiter_with(_ScriptedPlanner(cheap_ok=set(), full_only=set()))
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._memo.mark(repr(goal), state, 0)
    assert a._memo.is_doomed(repr(goal), state, 1)
    a._record_attempt(goal, [WaitAction()], timed_out=False, state=state,
                      guard_reprs=set(), mark_on_timeout=False)
    assert not a._memo.is_doomed(repr(goal), state, 1)


def test_record_attempt_never_memoizes_a_guard():
    """Guards always get the full budget and bypass the memo — never marked."""
    a = _arbiter_with(_ScriptedPlanner(cheap_ok=set(), full_only=set()))
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=False, state=state,
                      guard_reprs={repr(goal)}, mark_on_timeout=True)
    assert not a._memo.is_doomed(repr(goal), state, 1)


def test_objective_combat_goal_exempt_from_memo_skip():
    """The objective combat goal (GrindCharacterXPGoal) plans cheaply, but its
    plannability flips on fast-churning HP / inventory-free that the memo's
    signature (char level, skill levels) cannot track. A transient no-plan must
    NOT suppress it for the 20-160-cycle re-probe window — that stranded the bot
    in a jewelrycraft skill-grind detour under a ReachCharLevel root (2026-06-30).
    It is memo-exempt: even pre-doomed, the arbiter still attempts and selects it."""
    combat = GrindCharacterXPGoal(target_monster="green_slime", initial_xp=10**9)
    planner = _ScriptedPlanner(cheap_ok={repr(combat)}, full_only=set())
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    a._memo.mark(repr(combat), state, 0)        # a prior transient no-plan poisoned the memo
    a.set_cycle(1)
    cands = [Candidate(goal=combat, is_means=True, repr_=repr(combat))]
    goal, plan, _ = a._arbitrate(cands, set(), set(), state, _make_planner_gd(), [])
    assert repr(goal) == repr(combat), "memo-exempt combat goal must be selected despite the doom mark"
    assert len(plan) == 1


def test_objective_combat_goal_no_plan_does_not_poison_memo():
    """The complement: when the objective combat goal yields no plan (a transient
    HP/inventory state), the arbiter must NOT memoize it — otherwise the stale doom
    survives the transient (HP recovers but the signature is unchanged) and skips
    the only char-XP source for up to 160 cycles."""
    combat = GrindCharacterXPGoal(target_monster="green_slime", initial_xp=10**9)
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())   # nothing plans
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    cands = [Candidate(goal=combat, is_means=True, repr_=repr(combat))]
    a._arbitrate(cands, set(), set(), state, _make_planner_gd(), [])
    assert not a._memo.is_doomed(repr(combat), state, 1), \
        "the objective combat goal must never be memoized (its no-plan is HP/inventory-transient)"


def test_plans_short_circuits_wait_goal_without_invoking_planner():
    """_plans special-cases WaitGoal: it returns a single-WaitAction plan and
    records a zero-node goals_tried entry WITHOUT calling the planner (which
    would never terminate on the no-op WaitAction) — lines 308-317."""
    planner = _ScriptedPlanner(cheap_ok=set(), full_only=set())
    a = _arbiter_with(planner)
    state = make_state()
    plan = a._plans(WaitGoal(), state, _make_planner_gd(), [])
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)
    # Planner was never consulted for the Wait goal.
    assert planner.budgets == []
    # A diagnostic goals_tried entry was recorded for the Wait attempt.
    assert any(entry["goal"] == repr(WaitGoal()) and entry["nodes"] == 0
               for entry in a.goals_tried)
