"""CharacterSupervisor: one child process, driven by real subprocesses."""

import asyncio
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
