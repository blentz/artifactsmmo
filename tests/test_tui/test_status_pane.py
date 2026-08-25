"""StatusPane rendering tests (no Textual app needed)."""

import io
import time
from datetime import datetime, timezone

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, GoalRankEntry
from artifactsmmo_cli.tui.widgets.status_pane import (
    ETA_WINDOW,
    StatusPane,
    cooldown_expiry_epoch,
    format_eta,
    task_eta_seconds,
)

NOW = 1_780_000_000.0
"""Fixed wall-clock epoch the cooldown tests pin `time.time()` to."""


def _ts(seconds_ago: float = 0.0) -> str:
    """An ISO-8601 UTC timestamp `seconds_ago` before `NOW`.

    Snapshots in these tests are DELIBERATELY aged: the cooldown countdown is
    anchored to the snapshot's own capture time, so a test that always feeds a
    fresh timestamp cannot observe a stale one restarting from full.
    """
    return datetime.fromtimestamp(NOW - seconds_ago, tz=timezone.utc).isoformat()


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1,
        timestamp="2026-05-21T12:00:00Z",
        character="hero",
        x=3,
        y=5,
        level=7,
        xp=200,
        max_xp=1000,
        hp=80,
        max_hp=100,
        gold=42,
        selected_goal="farm_gold",
        action="move(1,2)",
        outcome="ok",
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _render(pane: StatusPane) -> str:
    """Render a pane to a plain string using a no-color Console."""
    buf = io.StringIO()
    c = Console(file=buf, width=100, no_color=True)
    c.print(pane.render())
    return buf.getvalue()


class TestStatusPaneNoSnapshot:
    def test_render_without_snapshot_shows_waiting(self):
        pane = StatusPane()
        assert "Waiting" in str(pane.render())


class TestStatusPaneBasicFields:
    def test_render_shows_character_name(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "hero" in _render(pane)

    def test_render_shows_level(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "L7" in _render(pane)

    def test_render_shows_hp(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "80/100" in _render(pane)

    def test_render_shows_xp(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "200/1000" in _render(pane)

    def test_render_shows_gold(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "42" in _render(pane)

    def test_render_shows_position(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "(3,5)" in _render(pane)

    def test_render_shows_goal(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "farm_gold" in _render(pane)

    def test_render_shows_action(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "move(1,2)" in _render(pane)

    def test_render_shows_outcome(self):
        pane = StatusPane()
        pane.update_snapshot(_snap())
        assert "ok" in _render(pane)


class TestStatusPaneCooldown:
    def test_cooldown_ready_when_zero(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(cooldown_remaining=0.0))
        assert "ready" in _render(pane)

    def test_cooldown_shows_seconds_when_positive(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=5.5))
        assert "6s" in _render(pane)

    def test_cooldown_high_value(self, monkeypatch):
        """Values >= 10 are colored red, still displays correctly."""
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=15.0))
        assert "15s" in _render(pane)


class TestStatusPaneTask:
    def test_task_shows_none_when_absent(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code=None))
        assert "none" in _render(pane)

    def test_task_shows_code_and_progress(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="kill_chicken", task_progress=3, task_total=10))
        plain = _render(pane)
        assert "kill_chicken" in plain
        assert "3/10" in plain


class TestStatusPanePath:
    def test_path_shows_max_level(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(max_level=40))
        assert "L40" in _render(pane)

    def test_projected_cycles_none(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(projected_cycles_to_max=None))
        assert "?" in _render(pane)

    def test_projected_cycles_shown(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(projected_cycles_to_max=123.7))
        assert "124" in _render(pane)

    def test_path_next_action_none(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(path_next_action=None))
        assert "?" in _render(pane)

    def test_path_next_action_shown(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(path_next_action="craft_iron_sword"))
        assert "craft_iron_sword" in _render(pane)


class TestStatusPaneGoalRank:
    def test_goal_rank_empty(self):
        """No goal rank rows — no crash, no top section."""
        pane = StatusPane()
        pane.update_snapshot(_snap(goal_rank=[]))
        # Should not raise
        _render(pane)

    def test_goal_rank_shown(self):
        pane = StatusPane()
        entries = [
            GoalRankEntry(goal="farm_gold", priority=10.0),
            GoalRankEntry(goal="level_up", priority=7.5),
        ]
        pane.update_snapshot(_snap(goal_rank=entries))
        assert "farm_gold" in _render(pane)

    def test_goal_rank_zero_priority_excluded(self):
        """Entries with priority == 0 should be filtered out of the display."""
        pane = StatusPane()
        entries = [
            GoalRankEntry(goal="zero_goal", priority=0.0),
        ]
        pane.update_snapshot(_snap(goal_rank=entries))
        assert "zero_goal" not in _render(pane)

    def test_goal_rank_top_3_only(self):
        """Only the top 3 entries are shown."""
        pane = StatusPane()
        entries = [GoalRankEntry(goal=f"goal_{i}", priority=float(10 - i)) for i in range(5)]
        pane.update_snapshot(_snap(goal_rank=entries))
        plain = _render(pane)
        assert "goal_0" in plain
        assert "goal_1" in plain
        assert "goal_2" in plain
        assert "goal_4" not in plain


class TestStatusPaneHpColors:
    def test_hp_critical_below_25pct(self):
        """HP < 25% should produce a red bar — no crash."""
        pane = StatusPane()
        pane.update_snapshot(_snap(hp=10, max_hp=100))
        _render(pane)

    def test_hp_yellow_between_25_and_50(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(hp=40, max_hp=100))
        _render(pane)

    def test_hp_green_above_50(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(hp=75, max_hp=100))
        _render(pane)

    def test_max_hp_zero_no_division_error(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(hp=0, max_hp=0))
        _render(pane)


class TestStatusPaneOutcomeColors:
    def test_outcome_no_plan(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(outcome="no_plan"))
        _render(pane)

    def test_outcome_error(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(outcome="error"))
        _render(pane)


class TestStatusPaneUpdateSnapshot:
    def test_update_snapshot_sets_snapshot(self):
        pane = StatusPane()
        snap = _snap()
        pane.update_snapshot(snap)
        assert pane.snapshot == snap


class TestTaskEta:
    def test_none_with_fewer_than_two_samples(self):
        assert task_eta_seconds([], remaining=5) is None
        assert task_eta_seconds([(0.0, 0)], remaining=5) is None

    def test_none_when_no_time_span(self):
        assert task_eta_seconds([(10.0, 0), (10.0, 2)], remaining=5) is None

    def test_none_when_rate_not_positive(self):
        assert task_eta_seconds([(0.0, 3), (60.0, 3)], remaining=5) is None  # no progress
        assert task_eta_seconds([(0.0, 5), (60.0, 3)], remaining=5) is None  # went down

    def test_steady_progress(self):
        # 2 progress over 60s = 0.0333/s; remaining 4 -> 120s
        assert task_eta_seconds([(0.0, 0), (60.0, 2)], remaining=4) == 120.0

    def test_format_eta_sub_minute(self):
        assert format_eta(45.0) == "~45s"

    def test_format_eta_minutes(self):
        assert format_eta(250.0) == "~4m 10s"


class TestStatusPaneEtaWindow:
    def test_eta_samples_trimmed_to_window(self):
        """Feeding > ETA_WINDOW snapshots for the same task keeps only the last ETA_WINDOW."""
        pane = StatusPane()
        for i in range(ETA_WINDOW + 5):
            # build a simple ISO timestamp string by using offset minutes
            minutes, secs = divmod(i * 30, 60)
            hours, minutes = divmod(minutes, 60)
            ts_str = f"2026-05-21T{12 + hours:02d}:{minutes:02d}:{secs:02d}Z"
            pane.update_snapshot(_snap(
                task_code="trim_test",
                task_type="items",
                task_progress=i,
                task_total=ETA_WINDOW + 10,
                timestamp=ts_str,
            ))
        assert len(pane._eta_samples) == ETA_WINDOW


class TestStatusEtaRow:
    def test_eta_dash_before_enough_samples(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=0, task_total=10,
                                   timestamp="2026-05-21T12:00:00Z"))
        assert "ETA" in _render(pane)
        assert "—" in _render(pane)

    def test_eta_shows_estimate_with_progress(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=0, task_total=10,
                                   timestamp="2026-05-21T12:00:00Z"))
        pane.update_snapshot(_snap(task_code="t", task_type="items",
                                   task_progress=2, task_total=10,
                                   timestamp="2026-05-21T12:01:00Z"))
        out = _render(pane)
        assert "ETA" in out and "~" in out and "m" in out  # 8 remaining at 2/60s

    def test_eta_resets_on_task_change(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code="a", task_total=5, task_progress=1,
                                   timestamp="2026-05-21T12:00:00Z"))
        pane.update_snapshot(_snap(task_code="b", task_total=5, task_progress=0,
                                   timestamp="2026-05-21T12:00:30Z"))
        # only 1 sample for task b -> dash
        assert "—" in _render(pane)

    def test_no_eta_row_without_task(self):
        pane = StatusPane()
        pane.update_snapshot(_snap(task_code=None))
        assert "ETA" not in _render(pane)


class TestStatusPaneLiveCooldown:
    def test_update_snapshot_sets_expiry_from_remaining(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=45.0))
        assert pane._cooldown_expiry == NOW + 45.0

    def test_update_snapshot_zero_remaining_clears_expiry(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=0.0))
        assert pane._cooldown_expiry is None

    def test_remaining_decreases_as_time_advances(self, monkeypatch):
        clock = {"t": NOW}
        monkeypatch.setattr(time, "time", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=45.0))
        clock["t"] = NOW + 30.0
        assert pane._cooldown_remaining() == 15.0
        clock["t"] = NOW + 100.0
        assert pane._cooldown_remaining() == 0.0

    def test_remaining_zero_when_no_expiry(self):
        assert StatusPane()._cooldown_remaining() == 0.0

    def test_render_shows_live_countdown_not_frozen_snapshot(self, monkeypatch):
        clock = {"t": NOW}
        monkeypatch.setattr(time, "time", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=45.0))
        clock["t"] = NOW + 20.5
        out = _render(pane)
        assert "25s" in out and "45" not in out

    def test_render_ready_when_countdown_elapsed(self, monkeypatch):
        clock = {"t": NOW}
        monkeypatch.setattr(time, "time", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=5.0))
        clock["t"] = NOW + 10.0
        assert "ready" in _render(pane)

    def test_tick_clears_expiry_once_elapsed(self, monkeypatch):
        clock = {"t": NOW}
        monkeypatch.setattr(time, "time", lambda: clock["t"])
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(), cooldown_remaining=5.0))
        clock["t"] = NOW + 10.0
        pane._tick()
        assert pane._cooldown_expiry is None


class TestStatusPaneStaleSnapshotCooldown:
    """The reported bug: toggling characters restarted the visible countdown.

    `CycleSnapshot.cooldown_remaining` is the value AS OF the snapshot's
    `timestamp`. The pane used to anchor it at DISPLAY time, so re-binding to a
    snapshot captured minutes ago replayed its whole cooldown from full. Every
    snapshot in this class is deliberately AGED — a test that feeds a fresh
    timestamp cannot observe the defect at all.
    """

    def test_stale_snapshot_counts_the_elapsed_time_off(self, monkeypatch):
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(120.0), cooldown_remaining=300.0))
        assert pane._cooldown_remaining() == 180.0
        assert "180s" in _render(pane)

    def test_rebind_to_a_stale_snapshot_does_not_restart_the_countdown(self, monkeypatch):
        """Toggling to another character and back re-binds the SAME stored
        snapshot. It must read the same elapsed-adjusted value, not full."""
        monkeypatch.setattr(time, "time", lambda: NOW)
        stale = _snap(timestamp=_ts(120.0), cooldown_remaining=300.0)
        pane = StatusPane()
        pane.update_snapshot(stale)
        pane.rebind(None)
        assert pane._cooldown_remaining() == 0.0
        pane.rebind(stale)
        assert pane._cooldown_remaining() == 180.0
        assert "300s" not in _render(pane)

    def test_snapshot_older_than_its_cooldown_reads_ready(self, monkeypatch):
        """A character idle for ten minutes is not still on a 5-minute cooldown."""
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(600.0), cooldown_remaining=300.0))
        assert pane._cooldown_expiry is None
        assert "ready" in _render(pane)

    def test_clock_skew_cannot_print_more_than_the_published_cooldown(self, monkeypatch):
        """The timestamp comes from the bot process; the TUI may run elsewhere.
        A TUI clock running behind makes `now < timestamp`, and an unclamped
        subtraction would inflate the countdown past the server's own value."""
        monkeypatch.setattr(time, "time", lambda: NOW)
        pane = StatusPane()
        pane.update_snapshot(_snap(timestamp=_ts(-3600.0), cooldown_remaining=30.0))
        assert pane._cooldown_remaining() == 30.0


class TestCooldownExpiryEpoch:
    def test_fresh_snapshot_expires_a_full_cooldown_out(self):
        assert cooldown_expiry_epoch(_ts(), 45.0, NOW) == NOW + 45.0

    def test_elapsed_time_comes_off_the_expiry(self):
        assert cooldown_expiry_epoch(_ts(20.0), 45.0, NOW) == NOW + 25.0

    def test_expired_cooldown_is_none(self):
        assert cooldown_expiry_epoch(_ts(45.0), 45.0, NOW) is None

    def test_zero_cooldown_is_none(self):
        assert cooldown_expiry_epoch(_ts(), 0.0, NOW) is None

    def test_future_timestamp_is_clamped_to_the_full_cooldown(self):
        assert cooldown_expiry_epoch(_ts(-500.0), 45.0, NOW) == NOW + 45.0
