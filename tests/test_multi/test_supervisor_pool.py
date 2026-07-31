"""SupervisorPool: N children, run concurrently, states readable."""

import asyncio
import sys

import pytest

from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool

_EXIT_NORMAL = (
    "import sys\n"
    "sys.stdout.write('{{\"kind\":\"exit\",\"character\":\"{name}\","
    "\"reason\":\"normal\"}}\\n')\n"
    "sys.stdout.flush()\n"
)


def _supervisor(name: str, seen: list) -> CharacterSupervisor:
    return CharacterSupervisor(
        character=name,
        argv=[sys.executable, "-c", _EXIT_NORMAL.format(name=name)],
        on_event=seen.append,
    )


@pytest.mark.asyncio
async def test_every_child_runs_and_reports():
    seen: list = []
    names = ["alice", "bob", "carol"]
    pool = SupervisorPool([_supervisor(n, seen) for n in names])
    await asyncio.wait_for(pool.run(), timeout=10.0)
    assert {event.character for event in seen} == set(names)


@pytest.mark.asyncio
async def test_children_run_concurrently_not_serially():
    """Three children that each sleep 1.0s must finish in well under 2.0s.

    The brief's literal numbers (0.3s sleep, <0.9s threshold) left almost no
    gap between the concurrent case (~0.9s) and the serial-bug floor
    (~0.9s+), so the assertion could pass against a `SupervisorPool.run()`
    that awaited each supervisor in a plain `for` loop instead of
    `asyncio.gather` -- exactly the defect this test exists to catch.

    Raising the per-child sleep to 1.0s widens the *gap* instead of the
    threshold: concurrent execution finishes in ~1.0-1.3s (one sleep plus
    process startup), while a serial implementation takes ~3.0-3.3s (three
    sleeps plus three startups). Asserting <2.0s leaves ~0.7s of slack
    above the concurrent case and a full 1.0s below the serial floor, so
    the test stays robust on a loaded machine while still failing against
    a serial `run()`.
    """
    body = (
        "import sys, time\n"
        "time.sleep(1.0)\n"
        "sys.stdout.write('{\"kind\":\"exit\",\"character\":\"x\",\"reason\":\"normal\"}\\n')\n"
        "sys.stdout.flush()\n"
    )
    supervisors = [
        CharacterSupervisor(
            character=f"c{i}",
            argv=[sys.executable, "-c", body],
            on_event=lambda _e: None,
        )
        for i in range(3)
    ]
    start = asyncio.get_running_loop().time()
    await asyncio.wait_for(SupervisorPool(supervisors).run(), timeout=10.0)
    assert asyncio.get_running_loop().time() - start < 2.0


@pytest.mark.asyncio
async def test_state_reports_each_child():
    seen: list = []
    pool = SupervisorPool([_supervisor("alice", seen)])
    await asyncio.wait_for(pool.run(), timeout=10.0)
    state = pool.state("alice")
    assert state.character == "alice"
    assert state.alive is False
    assert state.restarts == 0
    assert state.last_reason == "normal"


@pytest.mark.asyncio
async def test_state_rejects_an_unknown_character():
    pool = SupervisorPool([_supervisor("alice", [])])
    with pytest.raises(KeyError):
        pool.state("nobody")


def test_characters_preserves_roster_order():
    pool = SupervisorPool([_supervisor(n, []) for n in ["carol", "alice", "bob"]])
    assert pool.characters() == ("carol", "alice", "bob")


@pytest.mark.asyncio
async def test_a_spawn_failure_does_not_orphan_the_other_children():
    """A bad argv (create_subprocess_exec raising OSError, e.g. ENOENT) must
    not abandon the other children mid-flight: every supervisor must still be
    tracked to its own natural completion, and the failure must surface.

    Against a bare ``asyncio.gather(...)`` (no ``return_exceptions``), the
    ghost's OSError surfaces near-instantly -- well before "alice"'s real
    subprocess has had time to spawn, run, and exit -- so it would propagate
    out of ``pool.run()`` immediately, leaving alice's supervisor task
    scheduled but unawaited: an orphaned Task with a live subprocess nothing
    is tracking. The fixed ``run()`` awaits every supervisor to completion
    before raising, so alice's state is deterministically settled by the
    time the exception is caught -- this assertion cannot pass by accident.
    """
    seen: list = []
    alice = _supervisor("alice", seen)
    ghost = CharacterSupervisor(
        character="ghost",
        argv=["/nonexistent/path/for-sure-does-not-exist-xyz"],
        on_event=lambda _e: None,
    )
    pool = SupervisorPool([alice, ghost])
    with pytest.raises(OSError):
        await asyncio.wait_for(pool.run(), timeout=10.0)
    assert pool.state("alice").last_reason == "normal"
    assert {event.character for event in seen} == {"alice"}


@pytest.mark.asyncio
async def test_multiple_spawn_failures_are_reported_together():
    """More than one simultaneous failure is not allowed to shadow the
    others: every failure is collected, not just the first."""
    ghosts = [
        CharacterSupervisor(
            character=f"ghost{i}",
            argv=["/nonexistent/path/for-sure-does-not-exist-xyz"],
            on_event=lambda _e: None,
        )
        for i in range(2)
    ]
    pool = SupervisorPool(ghosts)
    with pytest.raises(ExceptionGroup) as excinfo:
        await asyncio.wait_for(pool.run(), timeout=10.0)
    assert len(excinfo.value.exceptions) == 2
