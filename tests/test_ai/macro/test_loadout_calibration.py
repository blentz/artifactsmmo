"""Tests for the pure loadout_calibration_report aggregator + formatter."""

from fractions import Fraction

from artifactsmmo_cli.ai.learning.store import CombatLoadoutOutcomeRow
from artifactsmmo_cli.ai.macro.loadout_calibration import loadout_calibration_report


def _row(task: str, loadout: dict[str, str], pred: bool, act: bool) -> CombatLoadoutOutcomeRow:
    return CombatLoadoutOutcomeRow("Robby", task, loadout, pred, act)


def test_report_calibration_buckets() -> None:
    rows = [
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, False),  # predicted-win but lost
        _row("combat:wolf", {"weapon_slot": "sword"}, False, True),     # predicted-loss but won
    ]
    report = loadout_calibration_report(rows)
    assert "combat:chicken" in report
    assert "predicted-win but lost" in report.lower() or "over-estimate" in report.lower()
    # chicken: 2 fights, predicted-win 100%, actual-win 50%, 1 over-estimate
    assert "combat:wolf" in report


def test_report_per_loadout_tally() -> None:
    rows = [
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "axe"}, True, False),
    ]
    report = loadout_calibration_report(rows)
    assert "stick" in report and "axe" in report  # both worn loadouts surfaced with tallies


def test_report_empty_rows() -> None:
    assert isinstance(loadout_calibration_report([]), str)  # no crash, empty-state message


def test_report_ranked_worst_calibration_first() -> None:
    """Worst calibrated task (largest over-estimate rate) appears before better-calibrated ones."""
    rows = [
        # bad_monster: 3 predicted-win, all actually lost (100% over-estimate)
        _row("combat:bad_monster", {"weapon_slot": "stick"}, True, False),
        _row("combat:bad_monster", {"weapon_slot": "stick"}, True, False),
        _row("combat:bad_monster", {"weapon_slot": "stick"}, True, False),
        # good_monster: 2 predicted-win, both actually won (0% over-estimate)
        _row("combat:good_monster", {"weapon_slot": "sword"}, True, True),
        _row("combat:good_monster", {"weapon_slot": "sword"}, True, True),
    ]
    report = loadout_calibration_report(rows)
    bad_pos = report.index("bad_monster")
    good_pos = report.index("good_monster")
    assert bad_pos < good_pos, "worst-calibrated task should appear first in report"


def test_report_under_estimate_bucket() -> None:
    """Under-estimate bucket (predicted-loss but actually won) is reported."""
    rows = [
        _row("combat:wolf", {"weapon_slot": "sword"}, False, True),   # under-estimate
        _row("combat:wolf", {"weapon_slot": "sword"}, False, True),
    ]
    report = loadout_calibration_report(rows)
    assert "under-estimate" in report.lower() or "predicted-loss but won" in report.lower()


def test_report_per_loadout_win_loss_counts() -> None:
    """Win/loss tally per distinct loadout is surfaced numerically."""
    rows = [
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, True),
        _row("combat:chicken", {"weapon_slot": "stick"}, True, False),
    ]
    report = loadout_calibration_report(rows)
    # 2 wins and 1 loss for stick loadout — the exact tally row must appear
    assert "| weapon_slot=stick | 2 | 1 |" in report


def _odds_row(p: float | None, won: bool) -> CombatLoadoutOutcomeRow:
    return CombatLoadoutOutcomeRow("Robby", "combat:owl", {}, True, won, p)


def test_report_buckets_win_odds_against_observed() -> None:
    rows = [_odds_row(0.05, False), _odds_row(0.63, True), _odds_row(0.66, False),
            _odds_row(0.97, True), _odds_row(None, True)]
    report = loadout_calibration_report(rows)
    assert "## P(win) calibration" in report
    assert "| bucket | fights | mean predicted | observed |" in report
    assert "| 0.0-0.1 | 1 | 5% | 0% |" in report
    assert "| 0.6-0.7 | 2 | 64.5% | 50% |" in report
    assert "| 0.9-1.0 | 1 | 97% | 100% |" in report
    assert "No P(win) recorded yet." not in report


def test_report_a_certain_win_lands_in_the_top_bucket() -> None:
    report = loadout_calibration_report([_odds_row(1.0, True)])
    assert "| 0.9-1.0 | 1 | 100% | 100% |" in report


def test_report_without_recorded_odds_says_so() -> None:
    report = loadout_calibration_report([_odds_row(None, True)])
    assert "No P(win) recorded yet." in report


def test_report_names_thresholds_beyond_the_liveness_bound() -> None:
    """Liveness is proved for θ <= 99/100 and θ is never capped (USER
    2026-10-16), so the report names every (character, monster) above it."""
    rows = [_row("combat:imp", {}, True, True)]
    report = loadout_calibration_report(
        rows, {"Robby": [("imp", Fraction(999, 1000))], "HAL": []})
    assert "## Win thresholds beyond the liveness bound (θ > 0.99)" in report
    assert "| Robby | imp | 0.999 |" in report
    assert "HAL" not in report


def test_report_says_when_no_threshold_is_beyond_the_bound() -> None:
    report = loadout_calibration_report([_row("combat:imp", {}, True, True)], {"HAL": []})
    assert "None: every measured threshold is within the liveness bound." in report
