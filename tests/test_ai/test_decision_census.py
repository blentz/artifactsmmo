"""Phase 0 decision census: the yardstick every redesign phase is measured with."""

import pytest

from artifactsmmo_cli.ai.learning.models import Cycle, DecisionEvent, Session
from artifactsmmo_cli.audit.decision_census import census, classify_error


def _cycle(outcome: str = "ok", *, action: str | None = "Fight(pig)", action_class: str | None = "FightAction",
           goal: str | None = "GrindCharacterXP(pig)", error: str | None = None, nodes: int | None = None,
           timed_out: bool | None = None, xp: int | None = 0, skill: str = "{}",
           cooldown: float | None = None) -> Cycle:
    return Cycle(ts="2026-09-24T00:00:00+00:00", session_id="s", cycle_index=0, character="Robby",
                 outcome=outcome, action_repr=action, action_class=action_class, selected_goal=goal,
                 error_text=error, planner_nodes=nodes, planner_timed_out=timed_out, delta_xp=xp,
                 delta_skill_xp_json=skill, actual_cooldown_seconds=cooldown)


@pytest.mark.parametrize(("outcome", "text", "expected"), [
    ("error:HTTP_404", "HTTP 404: Order not found.", "http_404"),
    ("error:other", "LevelSkill(gearcrafting) grind sub-plan EXHAUSTED the 15.0s planning budget",
     "grind_budget_exhausted"),
    ("error:other", "LevelSkill(x) grind produced no leg — goal=...", "grind_dead_end"),
    ("error:other", "LevelSkill(x) has no grind rung at execution", "grind_other"),
    ("error:other", "cyclic skill-grind dependency for x", "grind_other"),
    ("error:fight_lost", "fight_lost: pig (turns=28)", "fight_lost"),
    ("error:other", "Fight red_slime: no response data", "no_response"),
    ("error:other", "Could not fetch character 'C3P0' after 3 attempts", "no_response"),
    ("error:network", "The read operation timed out", "transport"),
    ("error:other", "something new", "other"),
    ("error:other", None, "other"),
])
def test_classify_error(outcome: str, text: str | None, expected: str) -> None:
    assert classify_error(outcome, text) == expected


def test_census_measures_throughput_quality_and_progress() -> None:
    cycles = [
        _cycle(nodes=10, timed_out=False, xp=30, cooldown=1800.0),
        _cycle("error:other", action="LevelSkill(x->2)", action_class="LevelSkill", goal="ReachSkill(x->2)",
               error="LevelSkill(x) grind sub-plan EXHAUSTED", nodes=100, timed_out=True),
        _cycle("error:other", action="LevelSkill(x->2)", action_class="LevelSkill", goal="ReachSkill(x->2)",
               error="LevelSkill(x) grind sub-plan EXHAUSTED", nodes=1000, timed_out=True),
        _cycle(action="Wait", action_class="WaitAction", goal="Wait", skill='{"mining": 5, "cooking": 3}',
               xp=None),
    ]
    sessions = [Session(session_id="a", started_at="x", character="Robby", exit_reason="crash"),
                Session(session_id="b", started_at="x", character="Robby", exit_reason=None)]

    events = [DecisionEvent(ts="t", session_id="s", character="Robby", cycle_index=i, mechanism=m, subject="g")
              for i, m in enumerate(["doomed_mark", "doomed_skip", "doomed_skip"])]

    c = census("Robby", cycles, sessions, events, window_hours=2.0)

    assert c.cycles == 4 and c.cycles_per_hour == 2.0
    assert c.ok_share == 0.5
    assert c.error_classes == {"grind_budget_exhausted": 2}
    assert c.level_skill_share == 0.5
    assert c.wait_cycles == 1
    assert c.timed_out_share == pytest.approx(2 / 3)
    assert (c.nodes_p50, c.nodes_p95, c.nodes_max) == (100, 1000, 1000)
    assert c.goal_switch_share == pytest.approx(2 / 3)
    assert c.longest_failure_streak == 2
    assert c.char_xp_per_hour == 15.0
    assert c.skill_xp_per_hour == 4.0
    assert c.cooldown_share == 0.25
    assert c.session_exits == {"crash": 1, "running": 1}
    assert c.mechanisms == {"doomed_mark": 1, "doomed_skip": 2}


def test_a_failure_streak_breaks_on_success_and_on_a_different_failure() -> None:
    fail_a = _cycle("error:HTTP_404", action="GeCancel(a)")
    fail_b = _cycle("error:HTTP_404", action="GeCancel(b)")
    cycles = [fail_a, fail_a, _cycle(), fail_a, fail_b, fail_b, fail_b]
    assert census("Robby", cycles, [], [], 1.0).longest_failure_streak == 3


def test_an_empty_window_reports_undefined_shares_not_zeros() -> None:
    c = census("HAL", [], [], [], window_hours=24.0)
    assert (c.cycles, c.cycles_per_hour) == (0, 0.0)
    assert c.ok_share is None and c.level_skill_share is None and c.timed_out_share is None
    assert c.goal_switch_share is None
    assert (c.nodes_p50, c.nodes_p95, c.nodes_max) == (None, None, None)
    assert c.longest_failure_streak == 0
    assert c.mechanisms == {}


def test_the_window_must_have_length() -> None:
    with pytest.raises(ValueError, match="window_hours must be positive"):
        census("HAL", [], [], [], window_hours=0.0)
