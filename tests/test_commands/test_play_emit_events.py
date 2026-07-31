"""`play --emit-events`: stdout is protocol only, human output goes to stderr.

Three corrections versus a naive reading of the task brief (verified
empirically, see task-8-report.md):

1. ``typer.Exit`` is NOT a ``SystemExit`` (its MRO is
   ``[Exit, RuntimeError, Exception, BaseException, object]``), so the
   validation tests use ``pytest.raises(typer.Exit)``.
2. Calling ``play()`` directly as a plain function leaks typer ``OptionInfo``
   objects as the value of any parameter that isn't explicitly passed. The
   three validation tests below only work because their checks short-circuit
   before touching an unpassed parameter; this is preserved deliberately.
3. The ``--all`` branch does not construct ``MultiRun`` (Task 16); it prints
   a "not yet implemented" message and exits 2. That behaviour is pinned by
   ``test_all_flag_without_supervisor_exits_not_implemented`` below.
"""

import json
import subprocess
import sys
from unittest.mock import Mock, patch

import httpx
import pytest
import typer
from typer.testing import CliRunner

from artifactsmmo_cli.ai.recovery import StuckExit, StuckSignal
from artifactsmmo_cli.commands import play as play_module
from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError

app = typer.Typer()
app.command()(play_module.play)


@pytest.fixture
def runner():
    return CliRunner()


def test_emit_events_flag_exists():
    import inspect

    assert "emit_events" in inspect.signature(play_module.play).parameters


def test_network_crash_is_reported_as_crash_network():
    assert play_module.emit_reason_for(play_module.httpx.ConnectError("boom")) == "crash:network"


def test_other_crashes_stay_plain_crash():
    assert play_module.emit_reason_for(RuntimeError("bug")) == "crash"


def test_child_stdout_carries_only_json_lines():
    """End-to-end: a real child process whose bot prints must still emit a
    stdout stream where EVERY line parses as a ChildEvent."""
    script = (
        "import sys, io\n"
        "from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter\n"
        "import contextlib\n"
        "emitter = JsonlEventEmitter('hero', sys.stdout)\n"
        "with contextlib.redirect_stdout(sys.stderr):\n"
        "    print('bot noise that must not corrupt the protocol')\n"
        "    emitter.planning(True)\n"
        "    emitter.emit_exit('normal')\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, check=True
    )
    for line in result.stdout.splitlines():
        assert json.loads(line)["kind"] in {"snapshot", "planning", "exit"}
    assert "bot noise" in result.stderr


# --- Validation ordering (direct calls; correction 1 + 2 apply) -----------


def test_all_and_character_are_mutually_exclusive():
    with pytest.raises(typer.Exit) as excinfo:
        play_module.play(character="hero", all_characters=True)
    assert excinfo.value.exit_code == 2


def test_all_requires_no_explicit_trace_file():
    with pytest.raises(typer.Exit) as excinfo:
        play_module.play(character=None, all_characters=True, trace_file="x.jsonl")
    assert excinfo.value.exit_code == 2


def test_neither_all_nor_character_is_an_error():
    with pytest.raises(typer.Exit) as excinfo:
        play_module.play(character=None, all_characters=False)
    assert excinfo.value.exit_code == 2


# --- The --all branch itself: pinned, not accidental -----------------------


class TestAllFlagStub:
    """``--all`` is otherwise valid (no character named, no --trace-file) but
    the multi-character supervisor (Task 16) does not exist yet. This must
    exit 2 with an explicit message rather than silently falling through to
    ``GamePlayer(character=None)``."""

    def test_all_flag_without_supervisor_exits_not_implemented(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore"),
        ):
            result = runner.invoke(app, ["--all"])

        assert result.exit_code == 2
        assert "not yet implemented" in result.output
        mock_player_cls.assert_not_called()


# --- --emit-events wiring through the real play() body ---------------------


class TestEmitEventsWiring:
    """Drives the real CLI machinery (CliRunner) so no parameter leaks a
    typer OptionInfo default; only GamePlayer/LearningStore are mocked."""

    def test_normal_run_separates_stdout_from_bot_prints_and_emits_exit(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = lambda: print("bot noise that must not corrupt the protocol")
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code == 0
        # Bot's own print landed on stderr, not on the protocol stream.
        assert "bot noise" in result.stderr
        assert "bot noise" not in result.stdout
        # The emitter was wired to the player's observers before the run.
        cycle_arg = mock_player.set_cycle_observer.call_args.args[0]
        planning_arg = mock_player.set_planning_observer.call_args.args[0]
        assert isinstance(cycle_arg.__self__, JsonlEventEmitter)
        assert isinstance(planning_arg.__self__, JsonlEventEmitter)
        # stdout carries only the protocol: the final line is the exit event.
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        assert lines, "expected at least the exit event on stdout"
        last_event = json.loads(lines[-1])
        assert last_event == {"kind": "exit", "character": "hero", "reason": "normal"}
        mock_store.end_session.assert_called_once_with(exit_reason="normal")

    def test_network_crash_emits_crash_network_but_records_plain_crash(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = httpx.ConnectError("boom")
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code != 0
        assert isinstance(result.exception, httpx.ConnectError)
        # The learning store's vocabulary is unchanged: plain "crash".
        mock_store.end_session.assert_called_once_with(exit_reason="crash")
        # The supervisor-facing protocol gets the network refinement.
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        last_event = json.loads(lines[-1])
        assert last_event["reason"] == "crash:network"

    def test_stuck_exit_records_and_emits_stuck_exit_reason(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = StuckExit(StuckSignal.GOAL_OSCILLATION)
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code == 2
        mock_store.end_session.assert_called_once_with(exit_reason="stuck_exit")
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        last_event = json.loads(lines[-1])
        assert last_event["reason"] == "stuck_exit"

    def test_server_unavailable_records_and_emits_server_unavailable_reason(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = ServerUnavailableError(
                "Down for maintenance", url="https://api.example.com/")
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code != 0
        assert isinstance(result.exception, ServerUnavailableError)
        mock_store.end_session.assert_called_once_with(exit_reason="server_unavailable")
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        last_event = json.loads(lines[-1])
        assert last_event["reason"] == "server_unavailable"

    def test_keyboard_interrupt_records_and_emits_keyboard_interrupt_reason(self, runner):
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = KeyboardInterrupt()
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code != 0
        mock_store.end_session.assert_called_once_with(exit_reason="keyboard_interrupt")
        lines = [ln for ln in result.stdout.splitlines() if ln.strip()]
        last_event = json.loads(lines[-1])
        assert last_event["reason"] == "keyboard_interrupt"

    def test_broken_pipe_on_emit_exit_does_not_mask_the_original_crash(self, runner):
        """A supervisor that has already killed this child leaves the emitter
        writing into a closed pipe. emit_exit() then raises BrokenPipeError
        from inside the `finally` block — which, unguarded, REPLACES whatever
        exception was propagating. The real crash (here a RuntimeError) must
        be what escapes play(), not the broken-pipe error."""
        with (
            patch("artifactsmmo_cli.commands.play.GamePlayer") as mock_player_cls,
            patch("artifactsmmo_cli.commands.play.LearningStore") as mock_store_cls,
            patch("artifactsmmo_cli.commands.play.JsonlEventEmitter") as mock_emitter_cls,
        ):
            mock_player = Mock()
            mock_player.run.side_effect = RuntimeError("real crash, must survive")
            mock_player_cls.return_value = mock_player
            mock_store = Mock()
            mock_store_cls.return_value = mock_store
            mock_emitter = Mock()
            mock_emitter.emit_exit.side_effect = BrokenPipeError("pipe closed by supervisor")
            mock_emitter_cls.return_value = mock_emitter

            result = runner.invoke(app, ["hero", "--emit-events"])

        assert result.exit_code != 0
        assert isinstance(result.exception, RuntimeError), (
            f"expected the original RuntimeError to survive, got {result.exception!r}"
        )
        assert "real crash, must survive" in str(result.exception)
        # The store still recorded the honest reason despite the broken pipe.
        mock_store.end_session.assert_called_once_with(exit_reason="crash")
