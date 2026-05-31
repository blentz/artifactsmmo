"""Tests for the play command (GOAP AI player wiring)."""

from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from typer.testing import CliRunner

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.commands.play import app, default_learn_db_path, play


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
                # Game data preloaded on the main thread from the live client.
                mock_game_data.load.assert_called_once_with(mock_client)
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


class TestPlayCallableDirect:
    """Direct invocation guards (no Typer/Click layer)."""

    def test_play_function_is_registered_command(self):
        """The play function is exported and callable as a command body."""
        assert callable(play)
