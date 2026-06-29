"""Tests for the pure loadout_calibration_report aggregator + formatter."""

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
