"""The arbiter's ONE-BUDGET walk and its doomed-memo policy.

This module used to test a cheap/full TWO-PASS budget scheme. That scheme is
deleted: the escalation ran only `if chosen is None`, `select_pure` takes the
first candidate that plans, and a fallback combat grind always plans in 2-3
nodes — so the escalation was unreachable in practice and the 10s "cheap"
budget was the real budget for every objective. Everything here now asserts the
single walk: one budget (`planner._SEARCH_BUDGET_SECONDS`, passed as None), and
ANY no-plan marks the goal doomed.

A scripted planner returns a plan only for the goal reprs it is told to, letting
us assert walk behaviour deterministically."""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.arbiter_select import Candidate
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd


class _ScriptedPlanner:
    """Plans `[WaitAction()]` for goal reprs in `plannable`; everything else gets
    no plan, reported as a budget TIMEOUT when the repr is in `timing_out` and as
    an exhausted search otherwise. Records the budget it was handed per goal."""
    def __init__(self, plannable=(), timing_out=()):
        self.plannable = set(plannable)
        self.timing_out = set(timing_out)
        self.budgets = []
        self.last_stats = GOAPPlanner().last_stats

    def plan(self, state, goal, actions, game_data, history=None, *, budget_seconds=None):
        r = repr(goal)
        self.budgets.append((r, budget_seconds))
        if r in self.plannable:
            self.last_stats.timed_out = False
            return [WaitAction()]
        self.last_stats.timed_out = r in self.timing_out
        return []


def _arbiter_with(planner):
    a = StrategyArbiter(planner, history=None)
    a.set_cycle(0)
    return a


def test_every_candidate_is_planned_at_the_one_budget():
    """The walk selects the plannable candidate, and the planner is handed None —
    the one budget — for it. A resurrected cheap first pass would show up here as
    a numeric budget."""
    planner = _ScriptedPlanner(plannable={"AcceptTask"})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    decision = _FakeDecision(chosen_step=None)
    goal, _plan, _ = a.select(decision, state, _make_planner_gd(),
                              [AcceptTaskAction(taskmaster_location=(2, 1))],
                              _ctx(combat_monster="chicken"))
    assert repr(goal) == "AcceptTask"
    assert planner.budgets, "the planner must actually have been consulted"
    assert all(b is None for (_r, b) in planner.budgets), planner.budgets


def test_timed_out_goal_is_memoized_and_skipped_next_cycle():
    """A goal that TIMED OUT (not merely exhausted) is doomed from the single
    walk and is not re-searched on the next cycle. Pre-fix the cheap pass passed
    mark_on_timeout=False and the marking pass was unreachable, so R2D2 re-ran
    the same 3873-node search on 955 consecutive cycles."""
    planner = _ScriptedPlanner(timing_out={"AcceptTask"})
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
    assert calls_cycle1 == 0, "a timed-out goal must be skipped on the next cycle"


def test_wait_selected_when_nothing_plans():
    planner = _ScriptedPlanner()
    a = _arbiter_with(planner)
    state = make_state(task_code="chicken", task_type="monsters", task_progress=0, task_total=5)
    goal, plan, _ = a.select(_FakeDecision(chosen_step=None), state, _make_planner_gd(), [], _ctx())
    assert isinstance(goal, WaitGoal)
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)


def test_exhausted_goal_passed_over_in_the_walk_is_memoized():
    """The feather_coat 99%-CPU peg: a goal that EXHAUSTS the search (no plan,
    timed_out=False) must be memoized even though a LATER goal wins, so it is not
    re-explored every cycle."""
    a = _arbiter_with(_ScriptedPlanner())
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=False, state=state, guard_reprs=set())
    assert a._memo.is_doomed(repr(goal), state, 1), \
        "an exhausted no-plan must be memoized (the feather_coat fix)"


def test_timeout_is_memoized_too():
    """THE Task-11 defect. The cheap pass exempted TIMEOUTS from marking so they
    stayed available for a full-budget escalation — an escalation that only ran
    when NOTHING planned, i.e. never, because the fallback grind always plans.
    The carve-out therefore only ever meant "never mark", and the same exploding
    search re-ran every cycle for 31 hours."""
    a = _arbiter_with(_ScriptedPlanner())
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=True, state=state, guard_reprs=set())
    assert a._memo.is_doomed(repr(goal), state, 1), \
        "a timed-out no-plan must be memoized — there is no escalation to save it for"


def test_record_attempt_clears_memo_on_success():
    """A found plan clears any prior doomed mark (the goal became plannable)."""
    a = _arbiter_with(_ScriptedPlanner())
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._memo.mark(repr(goal), state, 0)
    assert a._memo.is_doomed(repr(goal), state, 1)
    a._record_attempt(goal, [WaitAction()], timed_out=False, state=state, guard_reprs=set())
    assert not a._memo.is_doomed(repr(goal), state, 1)


def test_record_attempt_never_memoizes_a_guard():
    """Guards bypass the memo — never marked, even on a timeout."""
    a = _arbiter_with(_ScriptedPlanner())
    state = make_state(task_code=None, task_total=0)
    goal = GatherMaterialsGoal("feather_coat", {"feather_coat": 1})
    a._record_attempt(goal, [], timed_out=True, state=state, guard_reprs={repr(goal)})
    assert not a._memo.is_doomed(repr(goal), state, 1)


def test_objective_combat_goal_exempt_from_memo_skip():
    """The objective combat goal (GrindCharacterXPGoal) plans cheaply, but its
    plannability flips on fast-churning HP / inventory-free that the memo's
    signature (char level, skill levels) cannot track. A transient no-plan must
    NOT suppress it for the 20-160-cycle re-probe window — that stranded the bot
    in a jewelrycraft skill-grind detour under a ReachCharLevel root (2026-06-30).
    It is memo-exempt: even pre-doomed, the arbiter still attempts and selects it."""
    combat = GrindCharacterXPGoal(target_monster="green_slime", initial_xp=10**9)
    planner = _ScriptedPlanner(plannable={repr(combat)})
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    a._memo.mark(repr(combat), state, 0)        # a prior transient no-plan poisoned the memo
    a.set_cycle(1)
    cands = [Candidate(goal=combat, is_means=True, repr_=repr(combat), band=2)]
    goal, plan, _ = a._arbitrate(cands, set(), set(), state, _make_planner_gd(), [], _ctx())
    assert repr(goal) == repr(combat), "memo-exempt combat goal must be selected despite the doom mark"
    assert len(plan) == 1


def test_objective_combat_goal_no_plan_does_not_poison_memo():
    """The complement: when the objective combat goal yields no plan (a transient
    HP/inventory state), the arbiter must NOT memoize it — otherwise the stale doom
    survives the transient (HP recovers but the signature is unchanged) and skips
    the only char-XP source for up to 160 cycles."""
    combat = GrindCharacterXPGoal(target_monster="green_slime", initial_xp=10**9)
    planner = _ScriptedPlanner()   # nothing plans
    a = _arbiter_with(planner)
    state = make_state(task_code=None, task_total=0)
    cands = [Candidate(goal=combat, is_means=True, repr_=repr(combat), band=2)]
    a._arbitrate(cands, set(), set(), state, _make_planner_gd(), [], _ctx())
    assert not a._memo.is_doomed(repr(combat), state, 1), \
        "the objective combat goal must never be memoized (its no-plan is HP/inventory-transient)"


def test_plans_short_circuits_wait_goal_without_invoking_planner():
    """_plans special-cases WaitGoal: it returns a single-WaitAction plan and
    records a zero-node goals_tried entry WITHOUT calling the planner (which
    would never terminate on the no-op WaitAction)."""
    planner = _ScriptedPlanner()
    a = _arbiter_with(planner)
    state = make_state()
    plan = a._plans(WaitGoal(), state, _make_planner_gd(), [], _ctx())
    assert len(plan) == 1 and isinstance(plan[0], WaitAction)
    # Planner was never consulted for the Wait goal.
    assert planner.budgets == []
    # A diagnostic goals_tried entry was recorded for the Wait attempt.
    assert any(entry["goal"] == repr(WaitGoal()) and entry["nodes"] == 0
               for entry in a.goals_tried)
