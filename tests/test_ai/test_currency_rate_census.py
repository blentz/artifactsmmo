"""Per-goal currency rates over goal-attributed cycle slices."""

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.audit.currency_rate_census import GoalRates, currency_rates


def _cycle(seconds: float | None, char_xp: int, skill_json: str = "{}",
           gold: int = 0) -> Cycle:
    return Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="s", cycle_index=0,
        character="C3P0", outcome="ok", selected_goal="g",
        actual_cooldown_seconds=seconds, delta_xp=char_xp,
        delta_skill_xp_json=skill_json, delta_gold=gold,
    )


def test_rates_are_totals_over_measured_seconds() -> None:
    # The caller passes the slice recent_goal_cycles returned, which already
    # includes the Rests this goal's fighting forced: 10s fighting + 20s resting.
    rows = currency_rates({"Grind": [_cycle(10.0, 30), _cycle(20.0, 0)]})
    assert rows[0].seconds == 30.0
    assert rows[0].char_xp == 30
    assert rows[0].char_xp_per_second == 1.0


def test_skill_xp_is_summed_per_skill() -> None:
    rows = currency_rates({"Cook": [
        _cycle(5.0, 0, '{"cooking": 12}'),
        _cycle(5.0, 0, '{"cooking": 8, "fishing": 3}'),
    ]})
    assert rows[0].skill_xp == {"cooking": 20, "fishing": 3}
    assert rows[0].skill_xp_per_second == 2.3


def test_a_cycle_with_no_measured_cooldown_is_excluded_not_defaulted() -> None:
    # actual_cooldown_seconds is None when the server reported none. Denominating
    # on a fabricated 0 would make the rate infinite and rank it first.
    assert currency_rates({"Grind": [_cycle(None, 30)]}) == []


def test_a_goal_with_only_unmeasured_cycles_is_dropped_not_zeroed() -> None:
    rows = currency_rates({"Measured": [_cycle(10.0, 10)], "Unmeasured": [_cycle(None, 99)]})
    assert [r.goal for r in rows] == ["Measured"]


def test_ordered_by_char_xp_per_second_descending() -> None:
    rows = currency_rates({"Slow": [_cycle(100.0, 10)], "Fast": [_cycle(10.0, 100)]})
    assert [r.goal for r in rows] == ["Fast", "Slow"]


def test_gold_per_second() -> None:
    rows = currency_rates({"Sell": [_cycle(10.0, 0, "{}", 500)]})
    assert rows[0].gold_per_second == 50.0


def test_goal_rates_is_a_value_object() -> None:
    rates = GoalRates(goal="g", cycles=1, seconds=2.0, char_xp=4,
                      skill_xp={"cooking": 2}, gold=6)
    assert rates.char_xp_per_second == 2.0
    assert rates.skill_xp_per_second == 1.0
    assert rates.gold_per_second == 3.0
