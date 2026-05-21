"""LogPane tests (no Textual app needed)."""

from unittest.mock import patch

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.widgets.log_pane import LogPane


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=5,
        timestamp="2026-05-21T14:30:45Z",
        character="hero",
        x=0,
        y=0,
        level=3,
        xp=30,
        max_xp=300,
        hp=100,
        max_hp=100,
        gold=0,
        selected_goal="farm_wood",
        action="harvest(ash_tree)",
        outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


class TestLogPaneInit:
    def test_instantiates_without_error(self):
        pane = LogPane()
        assert pane is not None

    def test_auto_scroll_enabled(self):
        pane = LogPane()
        assert pane.auto_scroll is True

    def test_markup_enabled(self):
        pane = LogPane()
        assert pane.markup is True

    def test_wrap_disabled(self):
        pane = LogPane()
        assert pane.wrap is False


class TestLogPaneUpdateSnapshot:
    def test_update_snapshot_calls_write(self):
        pane = LogPane()
        with patch.object(pane, "write") as mock_write:
            snap = _snap()
            pane.update_snapshot(snap)
            mock_write.assert_called_once()

    def test_update_snapshot_contains_timestamp(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap())
        assert len(captured) == 1
        # The HH:MM:SS slice is 11:19 of the ISO timestamp
        assert "14:30:45" in captured[0]

    def test_update_snapshot_contains_cycle_index(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(cycle_index=42))
        assert "42" in captured[0]

    def test_update_snapshot_contains_goal(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(selected_goal="level_mining"))
        assert "level_mining" in captured[0]

    def test_update_snapshot_contains_action(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(action="move(3,4)"))
        assert "move(3,4)" in captured[0]

    def test_update_snapshot_contains_outcome(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="ok"))
        assert "ok" in captured[0]

    def test_outcome_no_plan_in_line(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="no_plan"))
        assert "no_plan" in captured[0]

    def test_outcome_error_in_line(self):
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(outcome="api_error"))
        assert "api_error" in captured[0]

    def test_short_timestamp_uses_full_string(self):
        """Timestamps shorter than 19 chars use the whole string."""
        pane = LogPane()
        captured = []
        with patch.object(pane, "write", side_effect=captured.append):
            pane.update_snapshot(_snap(timestamp="short"))
        assert "short" in captured[0]
