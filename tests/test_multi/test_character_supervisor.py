"""CharacterSupervisor: one child process, driven by real subprocesses."""

import asyncio
import os
import sys

import pytest

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_event import ExitEvent, PlanningEvent
from artifactsmmo_cli.multi.restart_policy import RestartPolicy


def _child_argv(body: str) -> list[str]:
    """A real child process emitting canned protocol lines."""
    return [sys.executable, "-c", body]


_EMIT_AND_EXIT = (
    "import sys\n"
    "sys.stdout.write('{\"kind\":\"planning\",\"character\":\"hero\",\"active\":true}\\n')\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"normal\"}\\n')\n"
    "sys.stdout.flush()\n"
)

_NOISY_STDERR = (
    "import sys\n"
    "sys.stderr.write('bot log line\\n')\n"
    "sys.stderr.write('Traceback: boom\\n')\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"crash\"}\\n')\n"
    "sys.stdout.flush()\n"
)


async def _run_with_timeout(supervisor: CharacterSupervisor) -> None:
    """Guard against a hung suite: a bug in run() must surface as a test
    failure, never as a wedged pytest process."""
    await asyncio.wait_for(supervisor.run(), timeout=10.0)


@pytest.mark.asyncio
async def test_events_reach_the_callback():
    seen = []
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_EMIT_AND_EXIT), on_event=seen.append
    )
    await _run_with_timeout(supervisor)
    assert [type(e) for e in seen] == [PlanningEvent, ExitEvent]


@pytest.mark.asyncio
async def test_a_clean_exit_is_not_restarted():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_EMIT_AND_EXIT), on_event=lambda _e: None
    )
    await _run_with_timeout(supervisor)
    assert supervisor.restarts == 0
    assert supervisor.alive is False


@pytest.mark.asyncio
async def test_stderr_is_captured_for_the_dead_panel():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_NOISY_STDERR), on_event=lambda _e: None
    )
    await _run_with_timeout(supervisor)
    assert "Traceback: boom" in supervisor.stderr_tail


@pytest.mark.asyncio
async def test_a_transient_exit_restarts_then_gives_up():
    """The child always reports crash:network, so the policy restarts it up to
    MAX_ATTEMPTS and then leaves it dead rather than flapping forever."""
    body = (
        "import sys\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\","
        "\"reason\":\"crash:network\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None,
        policy=RestartPolicy(), sleep=lambda _s: asyncio.sleep(0),
    )
    await _run_with_timeout(supervisor)
    assert supervisor.restarts == 5
    assert supervisor.alive is False


@pytest.mark.asyncio
async def test_a_child_that_dies_without_an_exit_event_is_treated_as_a_crash():
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv("raise SystemExit(9)"),
        on_event=lambda _e: None,
    )
    await _run_with_timeout(supervisor)
    assert supervisor.last_reason == "crash"
    assert supervisor.restarts == 0


@pytest.mark.asyncio
async def test_a_blank_stdout_line_is_ignored():
    """A stray blank line on the event stream (e.g. an extra newline from a
    flush) is not a protocol violation and must not be forwarded."""
    body = (
        "import sys\n"
        "sys.stdout.write('\\n')\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\","
        "\"reason\":\"normal\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    seen = []
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=seen.append
    )
    await _run_with_timeout(supervisor)
    assert [type(e) for e in seen] == [ExitEvent]


@pytest.mark.asyncio
async def test_an_unparseable_complete_line_surfaces_as_an_error():
    """A complete-but-invalid line means the protocol drifted. It must be
    visible, not silently dropped."""
    body = (
        "import sys\n"
        "sys.stdout.write('{\"kind\":\"nonsense\"}\\n')\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\","
        "\"reason\":\"normal\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None
    )
    await _run_with_timeout(supervisor)
    assert any("protocol" in line for line in supervisor.stderr_tail)


# --- Finding 1: the child must always be reaped, not merely un-watched -----


@pytest.mark.asyncio
async def test_cancelling_the_supervisor_kills_and_reaps_the_child():
    """Simulates Textual cancelling the "supervisors" worker when the
    operator presses 'q'. Before the fix, `_run_once` awaited the readers
    with no try/finally: cancelling the gather propagated straight out,
    `process.wait()` never ran, and the child (a live game-bot subprocess)
    was left running with nobody watching it.

    This proves the process is actually gone -- not merely that
    supervisor.run() raised CancelledError without error -- by checking the
    real OS pid after cancellation.
    """
    body = "import time\ntime.sleep(30)\n"
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None
    )
    task = asyncio.create_task(supervisor.run())
    async with asyncio.timeout(10.0):
        while supervisor.pid is None:
            await asyncio.sleep(0.01)
    pid = supervisor.pid

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(10.0):
            await task

    # await task only returns once every await inside _run_once's finally
    # block (terminate + wait()) has actually completed, so the process must
    # already be reaped here -- no extra sleep needed.
    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_a_child_that_ignores_sigterm_is_force_killed():
    """Graceful termination alone is not enough: a child that traps SIGTERM
    (or is simply too busy to act on it) must still be gone by the time
    _terminate returns. `terminate_timeout` is set tiny here purely so the
    test does not have to wait out the real 5s production ceiling.

    The child signals readiness over stderr (via `on_stderr`) once its
    SIG_IGN handler is actually installed, so cancellation cannot race the
    child's own startup -- without that rendezvous, terminate() could land
    before the handler exists and kill the child via the DEFAULT SIGTERM
    action, never exercising the force-kill path at all.
    """
    body = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "sys.stderr.write('ready\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(30)\n"
    )
    ready = asyncio.Event()

    def _on_stderr(line: str) -> None:
        if line == "ready":
            ready.set()

    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None,
        on_stderr=_on_stderr, terminate_timeout=0.2,
    )
    task = asyncio.create_task(supervisor.run())
    async with asyncio.timeout(10.0):
        await ready.wait()
    pid = supervisor.pid
    assert pid is not None

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(10.0):
            await task

    with pytest.raises(ProcessLookupError):
        os.kill(pid, 0)


@pytest.mark.asyncio
async def test_a_second_cancel_mid_ladder_does_not_abort_the_kill():
    """`asyncio.shield` regression pin: Textual's 'q' shutdown path calls
    `workers.cancel_all()` without awaiting the workers, so a SECOND
    cancellation can land while `_terminate`'s ladder is still awaiting
    `process.wait()`. Before the shield fix, that second cancel aborted the
    ladder mid-flight -- `process.kill()` and the final `process.wait()`
    never ran -- so a SIGTERM-ignoring child (and `sup.alive`) survived the
    shutdown entirely. This is the same SIGTERM-ignoring child as the
    single-cancel test above, but cancelled TWICE.
    """
    body = (
        "import signal, sys, time\n"
        "signal.signal(signal.SIGTERM, signal.SIG_IGN)\n"
        "sys.stderr.write('ready\\n')\n"
        "sys.stderr.flush()\n"
        "time.sleep(30)\n"
    )
    ready = asyncio.Event()

    def _on_stderr(line: str) -> None:
        if line == "ready":
            ready.set()

    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(body), on_event=lambda _e: None,
        on_stderr=_on_stderr, terminate_timeout=1.0,
    )
    task = asyncio.create_task(supervisor.run())
    async with asyncio.timeout(10.0):
        await ready.wait()
    pid = supervisor.pid
    assert pid is not None

    task.cancel()
    # Give the first cancel time to unwind out of the gather and into
    # `_terminate`'s `wait_for(process.wait(), ...)` -- comfortably inside
    # the 1.0s terminate_timeout above -- before delivering the second
    # cancel there.
    await asyncio.sleep(0.1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        async with asyncio.timeout(10.0):
            await task

    # The nested `finally` clears `alive` the instant the second cancel is
    # delivered -- it does not wait for the shielded ladder to finish.
    assert supervisor.alive is False

    # The shielded ladder itself keeps running in the background even
    # though `task` already raised CancelledError above, so give it time to
    # escalate to SIGKILL and reap the child before checking it is gone.
    async with asyncio.timeout(10.0):
        while True:
            try:
                os.kill(pid, 0)
            except ProcessLookupError:
                break
            await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_a_clean_exit_still_reaps_the_process():
    """The non-cancelled path must also leave nothing behind: `alive` and
    `pid` both clear once the child has actually exited."""
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_EMIT_AND_EXIT), on_event=lambda _e: None
    )
    await _run_with_timeout(supervisor)
    assert supervisor.alive is False
    assert supervisor.pid is None


# --- Finding 2: an over-limit line must not silently kill the character ----


_OVERLONG_LINE_THEN_EXIT = (
    "import sys\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"'"
    " + 'x' * 5000 + '\"}\\n')\n"
    "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"hero\",\"reason\":\"normal\"}\\n')\n"
    "sys.stdout.flush()\n"
)


@pytest.mark.asyncio
async def test_an_overlong_line_is_reported_and_the_supervisor_survives():
    """asyncio's own default StreamReader limit (65536 bytes) is too tight for
    a real late-game SnapshotEvent (measured 51,725 bytes); readline() raises
    ValueError past whatever limit is configured, which the old code did not
    catch, so the character silently froze (alive stayed True, no restart, no
    error surfaced). A small `stream_limit` here reproduces the same failure
    mode with a short line instead of an actual 64KiB+ one.
    """
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_OVERLONG_LINE_THEN_EXIT),
        on_event=lambda _e: None, stream_limit=1024,
    )
    await _run_with_timeout(supervisor)
    assert supervisor.last_reason == "normal"
    assert any("protocol error" in line for line in supervisor.stderr_tail)
    assert any("stream limit" in line for line in supervisor.stderr_tail)


# --- Finding 3: stderr lines are forwarded live, not just buffered ---------


@pytest.mark.asyncio
async def test_stderr_lines_are_forwarded_to_on_stderr_as_they_arrive():
    seen: list[str] = []
    supervisor = CharacterSupervisor(
        character="hero", argv=_child_argv(_NOISY_STDERR), on_event=lambda _e: None,
        on_stderr=seen.append,
    )
    await _run_with_timeout(supervisor)
    assert "bot log line" in seen
    assert "Traceback: boom" in seen
