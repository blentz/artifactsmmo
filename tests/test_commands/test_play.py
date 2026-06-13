"""Tests for the play command (GOAP AI player wiring)."""

import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
import typer
from typer.testing import CliRunner

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckExit, StuckSignal
from artifactsmmo_cli.commands.play import default_learn_db_path, play

# `play` is a plain command function registered directly on the root app in
# main.py (`app.command("play")(play)`) — it is no longer its own Typer group
# (that double-nesting made `artifactsmmo play <name>` fail with "Missing
# command"). For isolated invocation we register it on a single-command Typer,
# which Typer collapses so `runner.invoke(app, ["hero"])` runs play directly.
app = typer.Typer()
app.command()(play)


@pytest.fixture
def runner():
    """Create a CLI runner for testing."""
    return CliRunner()


class TestDefaultLearnDbPath:
    """Test the default learning DB path helper."""

    def test_default_learn_db_path_under_home_cache(self):
        """Default DB path lives under ~/.cache/artifactsmmo/learning.db."""
        expected = str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")
        assert default_learn_db_path() == expected


class TestMutationLockGuard:
    """Mutate<->play interlock: play must refuse to start while
    formal/diff/mutate.py holds live mutants in src/ (2026-06-09 incident:
    play launched mid-run imported a poisoned predicate and crashed)."""

    def test_active_mutation_lock_blocks_play_before_any_setup(self, runner, tmp_path):
        """Lockfile with a live pid: play exits nonzero with the interlock
        message before constructing the store, player, or any thread."""
        lock = tmp_path / ".mutation-run.lock"
        lock.write_text(f"{os.getpid()}\n2026-06-10T00:00:00+00:00\n")
        with (
            patch("artifactsmmo_cli.commands.play.default_lock_path", return_value=lock),
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            result = runner.invoke(app, ["hero"])

        assert result.exit_code == 2
        assert "mutation run in progress" in result.output
        assert "src/ contains live mutants" in result.output
        # Refused BEFORE any game-data / store / thread setup.
        mock_store_cls.assert_not_called()
        mock_player_cls.assert_not_called()

    def test_stale_mutation_lock_warns_and_continues(self, runner, tmp_path):
        """Lockfile whose pid is dead is debris from a killed run: warn and
        start normally."""
        proc = subprocess.Popen([sys.executable, "-c", ""])
        proc.wait()  # reaped -> pid guaranteed dead
        lock = tmp_path / ".mutation-run.lock"
        lock.write_text(f"{proc.pid}\n2026-06-10T00:00:00+00:00\n")
        with (
            patch("artifactsmmo_cli.commands.play.default_lock_path", return_value=lock),
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player_cls.return_value = Mock()
            mock_store_cls.return_value = Mock()

            result = runner.invoke(app, ["hero"])

        assert result.exit_code == 0
        assert "stale mutation lockfile" in result.output
        mock_player_cls.return_value.run.assert_called_once_with()


class TestPlayCommandWiring:
    """Test that the play command wires its collaborators correctly."""

    def test_plain_run_uses_null_tracer_no_store(self, runner):
        """Without --trace/--learn the player gets a NullTracer and an
        in-memory LearningStore (Phase 20e-v2 prodfix: history is always
        present so history-gated tier predicates can evaluate; with
        ``--learn`` absent the store is ephemeral so no disk persistence)."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player_cls.return_value = mock_player
            with patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls:
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero"])

                assert result.exit_code == 0
                mock_player.run.assert_called_once_with()
                # GamePlayer constructed with NullTracer and an in-memory store.
                kwargs = mock_player_cls.call_args.kwargs
                assert kwargs["character"] == "hero"
                assert isinstance(kwargs["tracer"], NullTracer)
                assert kwargs["history"] is mock_store
                assert kwargs["verbose"] is False
                assert kwargs["dry_run"] is False
                mock_store_cls.assert_called_once_with(
                    db_path=":memory:", character="hero")
                mock_store.start_session.assert_called_once_with()
                mock_store.end_session.assert_called_once_with(exit_reason="normal")
                mock_store.close.assert_called_once_with()

    def test_verbose_and_dry_run_flags_forwarded(self, runner):
        """--verbose and --dry-run are passed through to the GamePlayer."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()

            result = runner.invoke(app, ["hero", "--verbose", "--dry-run"])

            assert result.exit_code == 0
            kwargs = mock_player_cls.call_args.kwargs
            assert kwargs["verbose"] is True
            assert kwargs["dry_run"] is True

    def test_game_data_ttl_threaded_from_config(self, runner):
        """The GamePlayer is constructed with the config's game_data_ttl_minutes
        and refresh_game_data defaults to False."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()

            result = runner.invoke(app, ["hero"])

            assert result.exit_code == 0
            kwargs = mock_player_cls.call_args.kwargs
            assert kwargs["game_data_ttl_minutes"] == 30
            assert kwargs["refresh_game_data"] is False

    def test_refresh_game_data_flag_forwarded(self, runner):
        """--refresh-game-data reaches the GamePlayer as refresh_game_data=True."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()

            result = runner.invoke(app, ["hero", "--refresh-game-data"])

            assert result.exit_code == 0
            assert mock_player_cls.call_args.kwargs["refresh_game_data"] is True

    def test_trace_creates_file_tracer_with_default_path(self, runner):
        """--trace builds a FileTracer with the generated default path."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()
            with patch("artifactsmmo_cli.commands.play.FileTracer") as mock_tracer_cls:
                mock_tracer_cls.return_value = Mock(spec=FileTracer)

                result = runner.invoke(app, ["hero", "--trace"])

                assert result.exit_code == 0
                mock_tracer_cls.assert_called_once()
                used_path = mock_tracer_cls.call_args.args[0]
                assert used_path.startswith("play-trace-hero-")
                assert used_path.endswith(".jsonl")
                # The tracer instance is the one handed to the player.
                assert mock_player_cls.call_args.kwargs["tracer"] is mock_tracer_cls.return_value
                assert f"Tracing to {used_path}" in result.output

    def test_trace_uses_explicit_trace_file(self, runner):
        """--trace-file overrides the generated trace path."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()
            with patch("artifactsmmo_cli.commands.play.FileTracer") as mock_tracer_cls:
                mock_tracer_cls.return_value = Mock(spec=FileTracer)

                result = runner.invoke(
                    app, ["hero", "--trace", "--trace-file", "/tmp/custom.jsonl"]
                )

                assert result.exit_code == 0
                mock_tracer_cls.assert_called_once_with("/tmp/custom.jsonl")
                assert "Tracing to /tmp/custom.jsonl" in result.output

    def test_learn_starts_session_and_closes_store(self, runner):
        """--learn opens a LearningStore, starts a session, and closes on exit."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()
            with patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls:
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(
                    app, ["hero", "--learn", "--learn-db", "/tmp/learn.db"]
                )

                assert result.exit_code == 0
                mock_store_cls.assert_called_once_with(db_path="/tmp/learn.db", character="hero")
                mock_store.start_session.assert_called_once_with()
                # Store handed to player as history.
                assert mock_player_cls.call_args.kwargs["history"] is mock_store
                mock_store.end_session.assert_called_once_with(exit_reason="normal")
                mock_store.close.assert_called_once_with()
                assert "Learning enabled - DB at /tmp/learn.db" in result.output

    def test_learn_uses_default_db_path(self, runner):
        """--learn without --learn-db falls back to the default cache path."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player_cls.return_value = Mock()
            with patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls:
                mock_store_cls.return_value = Mock()

                result = runner.invoke(app, ["hero", "--learn"])

                assert result.exit_code == 0
                expected = str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")
                mock_store_cls.assert_called_once_with(db_path=expected, character="hero")

    def test_player_crash_closes_store_with_crash_reason(self, runner):
        """A crash mid-run still ends/closes the store, reporting exit_reason=crash."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player.run.side_effect = RuntimeError("boom")
            mock_player_cls.return_value = mock_player
            with patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls:
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero", "--learn"])

                # RuntimeError is not caught -> non-zero exit, but finally ran.
                assert result.exit_code != 0
                mock_store.end_session.assert_called_once_with(exit_reason="crash")
                mock_store.close.assert_called_once_with()

    def test_keyboard_interrupt_reports_and_reraises(self, runner):
        """Ctrl-C maps to exit_reason=keyboard_interrupt and re-raises."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player.run.side_effect = KeyboardInterrupt()
            mock_player_cls.return_value = mock_player
            with patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls:
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero", "--learn"])

                assert result.exit_code != 0
                mock_store.end_session.assert_called_once_with(exit_reason="keyboard_interrupt")
                mock_store.close.assert_called_once_with()

    def test_stuck_exit_records_stuck_exit_reason_in_real_store(self, runner, tmp_path):
        """Honest terminal path on real sqlite: the stuck handler's L3
        StuckExit (raised by the REAL GamePlayer._handle_stuck, not a stub
        exception) stops the run cleanly and the session row records
        exit_reason='stuck_exit' — NOT 'crash' (the 2026-06-10 lie where
        the detector's SystemExit(2) was filed as a crash)."""
        db_path = tmp_path / "learn.db"
        # A real player whose recovery state sits at L2 with a genuine
        # failing-flap window: the next fire escalates to L3 -> StuckExit.
        real_player = GamePlayer(character="hero")
        for i in range(8):
            real_player._record_cycle(CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False),
                goal_name="GoalA" if i % 2 == 0 else "GoalB",
                action_name="X", planned_depth=1,
                planner_timed_out=False, succeeded=False,
            ))
        real_player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 2

        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()

            def stuck_run():
                # The bot played real cycles (the session row exists), then
                # the detector's escalation ladder ran out.
                store = mock_player_cls.call_args.kwargs["history"]
                store.record_cycle(Cycle(
                    ts="2026-06-10T16:02:06+00:00",
                    session_id="overwritten", cycle_index=0,
                    character="overwritten", outcome="error:fight_lost",
                ))
                real_player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

            mock_player.run.side_effect = stuck_run
            mock_player_cls.return_value = mock_player

            result = runner.invoke(
                app, ["hero", "--learn", "--learn-db", str(db_path)])

        # Deliberate stop: exit code 2 via typer.Exit, no crash traceback.
        assert result.exit_code == 2
        assert "stopped" in result.output
        assert "manual intervention" in result.output
        conn = sqlite3.connect(db_path)
        rows = conn.execute("SELECT exit_reason, ended_at FROM sessions").fetchall()
        conn.close()
        assert len(rows) == 1
        exit_reason, ended_at = rows[0]
        assert exit_reason == "stuck_exit"
        assert ended_at is not None


class FakeWatchApp:
    """Minimal WatchApp stand-in: run() blocks until exit() like Textual,
    call_from_thread executes the callback inline (callers are other
    threads), and exit calls are recorded for assertions."""

    def __init__(self, character: str | None = None, game_data=None) -> None:
        self._done = threading.Event()
        self.exit_calls: list[tuple[tuple, dict]] = []

    def update_snapshot(self, snap) -> None:
        """No-op observer target (handed to ThreadSafeBridge)."""

    def call_from_thread(self, callback, *args, **kwargs):
        return callback(*args, **kwargs)

    def exit(self, *args, **kwargs) -> None:
        self.exit_calls.append((args, kwargs))
        self._done.set()

    def run(self) -> None:
        # Block like Textual's app.run; the timeout keeps a regressed
        # (never-exiting) implementation from hanging the test run.
        self._done.wait(timeout=10)


class FakeTornDownApp(FakeWatchApp):
    """A WatchApp whose thread-safe channel is already unusable — Textual's
    call_from_thread raises RuntimeError once the app is no longer running."""

    def call_from_thread(self, callback, *args, **kwargs):
        self._done.set()  # let run() return; the channel itself is dead
        raise RuntimeError("App is not running")


class TestRunWithTui:
    """Test the TUI worker-thread wiring via the --tui flag."""

    def test_tui_preloads_game_data_spawns_worker_and_runs_app(self, runner):
        """--tui preloads game data, wires the bridge, starts the bot thread, runs the app."""
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player_cls.return_value = mock_player

            with (
                patch("artifactsmmo_cli.commands.play.ClientManager") as mock_cm,
                patch("artifactsmmo_cli.commands.play.GameData") as mock_game_data,
                patch("artifactsmmo_cli.commands.play.WatchApp") as mock_watch_app_cls,
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge") as mock_bridge_cls,
                patch("artifactsmmo_cli.commands.play.threading") as mock_threading,
            ):
                mock_client = Mock()
                mock_cm.return_value.client = mock_client
                loaded_data = Mock()
                mock_game_data.load.return_value = loaded_data
                mock_app = Mock()
                mock_watch_app_cls.return_value = mock_app
                mock_bridge = Mock()
                mock_bridge_cls.return_value = mock_bridge
                mock_thread = Mock()
                mock_threading.Thread.return_value = mock_thread

                result = runner.invoke(app, ["hero", "--tui"])

                assert result.exit_code == 0
                # Game data preloaded on the main thread from the live client,
                # threaded with the cache TTL and refresh flag.
                mock_game_data.load.assert_called_once_with(
                    mock_client, ttl_minutes=30, force_refresh=False)
                assert mock_player.game_data is loaded_data
                # App created with the character and preloaded data.
                mock_watch_app_cls.assert_called_once_with(
                    character="hero", game_data=loaded_data
                )
                # Bridge wraps the app's update callback and feeds the cycle observer.
                mock_bridge_cls.assert_called_once_with(mock_app, mock_app.update_snapshot)
                mock_player.set_cycle_observer.assert_called_once_with(mock_bridge.notify)
                # Bot runs in a daemon worker thread.
                mock_threading.Thread.assert_called_once_with(
                    target=mock_player.run, daemon=True
                )
                mock_thread.start.assert_called_once_with()
                # The Textual app runs on the main thread (not player.run directly).
                mock_app.run.assert_called_once_with()
                mock_player.run.assert_not_called()

    def test_tui_worker_crash_exits_app_and_records_crash(self, runner):
        """A worker-thread crash must not die silently (2026-06-10 incident:
        bare daemon thread died, TUI ghosted for hours, exit_reason lied
        "normal"). threading.excepthook captures it, the app is told to exit
        with a fatal message, the traceback is re-raised on the main thread
        after teardown, and the session ends with exit_reason=crash."""
        fake_app = FakeWatchApp()
        hook_before = threading.excepthook
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player.run.side_effect = RuntimeError("485 aftermath boom")
            mock_player_cls.return_value = mock_player
            with (
                patch("artifactsmmo_cli.commands.play.ClientManager"),
                patch("artifactsmmo_cli.commands.play.GameData"),
                patch("artifactsmmo_cli.commands.play.WatchApp", return_value=fake_app),
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge"),
                patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
            ):
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero", "--tui"])

                # The crash propagated out of play() (visible, non-zero exit).
                assert result.exit_code != 0
                assert isinstance(result.exception, RuntimeError)
                assert "485 aftermath boom" in str(result.exception)
                # The app was torn down via its thread-safe channel with a
                # fatal message.
                assert len(fake_app.exit_calls) == 1
                _, exit_kwargs = fake_app.exit_calls[0]
                assert exit_kwargs["return_code"] == 1
                assert "crashed" in exit_kwargs["message"]
                # The traceback is printed AFTER Textual teardown.
                assert "Bot worker thread for 'hero' crashed" in result.output
                # The session recorded the truthful exit reason.
                mock_store.end_session.assert_called_once_with(exit_reason="crash")
                mock_store.close.assert_called_once_with()
        # The process-global hook was restored.
        assert threading.excepthook is hook_before

    def test_tui_worker_crash_records_crash_in_real_store(self, runner, tmp_path):
        """Pin the 2026-06-10 observed shape end-to-end on real sqlite: the
        worker records cycles (the session row exists), then dies mid-run.
        Pre-fix the sessions row kept its defaults (cycle_count=0,
        exit_reason=None) while the TUI ghosted and was then closed as
        exit_reason='normal' on quit; post-fix the app exits immediately and
        the row records exit_reason='crash' with the true cycle count."""
        db_path = tmp_path / "learn.db"
        fake_app = FakeWatchApp()
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player_cls.return_value = mock_player

            def crash_run():
                store = mock_player_cls.call_args.kwargs["history"]
                for i in range(2):
                    store.record_cycle(Cycle(
                        ts=f"2026-06-10T12:49:3{6 + i}+00:00",
                        session_id="overwritten", cycle_index=i,
                        character="overwritten",
                        outcome="error:already_equipped",
                    ))
                raise RuntimeError("worker died mid-run")

            mock_player.run.side_effect = crash_run
            with (
                patch("artifactsmmo_cli.commands.play.ClientManager"),
                patch("artifactsmmo_cli.commands.play.GameData"),
                patch("artifactsmmo_cli.commands.play.WatchApp", return_value=fake_app),
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge"),
            ):
                result = runner.invoke(
                    app, ["hero", "--tui", "--learn", "--learn-db", str(db_path)]
                )

        assert result.exit_code != 0
        assert isinstance(result.exception, RuntimeError)
        conn = sqlite3.connect(db_path)
        rows = conn.execute(
            "SELECT exit_reason, cycle_count, ended_at FROM sessions"
        ).fetchall()
        conn.close()
        assert len(rows) == 1
        exit_reason, cycle_count, ended_at = rows[0]
        assert exit_reason == "crash"
        assert cycle_count == 2
        assert ended_at is not None

    def test_tui_worker_stuck_exit_tears_down_and_records_stuck_exit(self, runner):
        """A worker StuckExit is supervised like a crash (the TUI must not
        ghost) but reported honestly: the app exits with a 'stopped' (not
        'crashed') message, no traceback is dumped, and the session ends
        with exit_reason='stuck_exit' and exit code 2."""
        fake_app = FakeWatchApp()
        hook_before = threading.excepthook
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player.run.side_effect = StuckExit(StuckSignal.GOAL_OSCILLATION)
            mock_player_cls.return_value = mock_player
            with (
                patch("artifactsmmo_cli.commands.play.ClientManager"),
                patch("artifactsmmo_cli.commands.play.GameData"),
                patch("artifactsmmo_cli.commands.play.WatchApp", return_value=fake_app),
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge"),
                patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
            ):
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero", "--tui"])

                assert result.exit_code == 2
                # The app was torn down through the thread-safe channel with
                # an honest "stopped" message (not "crashed").
                assert len(fake_app.exit_calls) == 1
                _, exit_kwargs = fake_app.exit_calls[0]
                assert "Bot stopped" in exit_kwargs["message"]
                assert "crashed" not in exit_kwargs["message"]
                assert "stuck recovery exhausted" in exit_kwargs["message"]
                # Post-teardown terminal output: honest stop, no traceback.
                assert "Bot for 'hero' stopped" in result.output
                assert "crashed; traceback" not in result.output
                # The session recorded the truthful exit reason.
                mock_store.end_session.assert_called_once_with(exit_reason="stuck_exit")
                mock_store.close.assert_called_once_with()
        assert threading.excepthook is hook_before

    def test_tui_worker_crash_with_app_already_torn_down(self, runner):
        """If the app's thread-safe channel is already dead (RuntimeError from
        call_from_thread), the crash is still recorded and re-raised — the
        notification is best-effort, the propagation is not."""
        fake_app = FakeTornDownApp()
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()
            mock_player.run.side_effect = RuntimeError("crash with dead app")
            mock_player_cls.return_value = mock_player
            with (
                patch("artifactsmmo_cli.commands.play.ClientManager"),
                patch("artifactsmmo_cli.commands.play.GameData"),
                patch("artifactsmmo_cli.commands.play.WatchApp", return_value=fake_app),
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge"),
                patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
            ):
                mock_store = Mock()
                mock_store_cls.return_value = mock_store

                result = runner.invoke(app, ["hero", "--tui"])

                assert result.exit_code != 0
                assert isinstance(result.exception, RuntimeError)
                assert "crash with dead app" in str(result.exception)
                assert fake_app.exit_calls == []  # the channel was dead
                mock_store.end_session.assert_called_once_with(exit_reason="crash")

    def test_tui_foreign_thread_exception_is_delegated(self, runner):
        """The supervision hook only claims the bot worker's exceptions; an
        unrelated thread's crash is delegated to the previous hook and the
        session still ends normally when the user quits."""
        fake_app = FakeWatchApp()
        delegated: list[threading.ExceptHookArgs] = []
        with patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls:
            mock_player = Mock()

            def run_with_rogue_thread():
                def rogue():
                    raise ValueError("not the bot's failure")
                t = threading.Thread(target=rogue, daemon=True)
                t.start()
                t.join()
                fake_app.exit()  # the user quits the TUI normally

            mock_player.run.side_effect = run_with_rogue_thread
            mock_player_cls.return_value = mock_player
            with (
                patch("artifactsmmo_cli.commands.play.ClientManager"),
                patch("artifactsmmo_cli.commands.play.GameData"),
                patch("artifactsmmo_cli.commands.play.WatchApp", return_value=fake_app),
                patch("artifactsmmo_cli.commands.play.ThreadSafeBridge"),
                patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
            ):
                mock_store = Mock()
                mock_store_cls.return_value = mock_store
                hook_before = threading.excepthook
                threading.excepthook = delegated.append
                try:
                    result = runner.invoke(app, ["hero", "--tui"])
                finally:
                    threading.excepthook = hook_before

                assert result.exit_code == 0
                assert len(delegated) == 1
                assert isinstance(delegated[0].exc_value, ValueError)
                mock_store.end_session.assert_called_once_with(exit_reason="normal")


class TestPlayCallableDirect:
    """Direct invocation guards (no Typer/Click layer)."""

    def test_play_function_is_registered_command(self):
        """The play function is exported and callable as a command body."""
        assert callable(play)
