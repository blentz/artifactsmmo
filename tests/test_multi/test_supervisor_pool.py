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
async def test_a_child_waits_its_stagger_before_spawning():
    """The boot-burst fix: child i must not spawn until i * stagger has passed.

    `sleep` is injected, so nothing here waits 12 real seconds. The fake gates
    every NON-zero delay on an Event that this test controls, which pins the
    pool at "alice has spawned, bob and carol have not" -- an ordering that a
    stagger applied AFTER `supervisor.run()` (or not at all) cannot produce,
    because all three children would then reach the API together, which is the
    whole defect.
    """
    seen: list = []
    delays: list[float] = []
    gate = asyncio.Event()

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)
        if delay:
            await gate.wait()

    pool = SupervisorPool(
        [_supervisor(n, seen) for n in ("alice", "bob", "carol")],
        stagger_seconds=12.0,
        sleep=fake_sleep,
    )
    task = asyncio.ensure_future(pool.run())
    try:
        # Every child's delay is computed and awaited before any subprocess
        # can finish, so the schedule is settled by the first poll. The poll
        # is BOUNDED so that a regression which gates child 0 too (nothing
        # ever spawns) fails this test instead of hanging the suite.
        async with asyncio.timeout(10.0):
            while not seen:
                await asyncio.sleep(0.01)
        assert delays == [0.0, 12.0, 24.0]
        assert {event.character for event in seen} == {"alice"}
    finally:
        gate.set()
        await asyncio.wait_for(task, timeout=10.0)
    assert {event.character for event in seen} == {"alice", "bob", "carol"}


@pytest.mark.asyncio
async def test_the_only_child_of_a_pool_is_never_delayed():
    """`play` on a single character must keep booting instantly: there is no
    sibling to collide with, so index 0 waits 0.0s even at a 12s stagger."""
    delays: list[float] = []

    async def fake_sleep(delay: float) -> None:
        delays.append(delay)

    pool = SupervisorPool(
        [_supervisor("alice", [])], stagger_seconds=12.0, sleep=fake_sleep
    )
    await asyncio.wait_for(pool.run(), timeout=10.0)
    assert delays == [0.0]


# --- on_stagger: the hold is announced at pool start, not at spawn ---------


@pytest.mark.asyncio
async def test_every_staggered_child_is_announced_before_it_sleeps():
    """The whole point is to make the silence visible: each child with a
    non-zero wait must be announced with its own name and duration, and the
    announcement must land BEFORE the sleep it describes -- i.e. at pool
    start, not once the child eventually gets to run."""
    seen: list = []
    announced: list[tuple[str, float]] = []
    gate = asyncio.Event()

    async def fake_sleep(delay: float) -> None:
        if delay:
            await gate.wait()

    pool = SupervisorPool(
        [_supervisor(n, seen) for n in ("alice", "bob", "carol")],
        stagger_seconds=12.0,
        sleep=fake_sleep,
        on_stagger=lambda character, wait: announced.append((character, wait)),
    )
    task = asyncio.ensure_future(pool.run())
    try:
        # Bob and carol are announced immediately: nothing has spawned yet,
        # so this can only be true if the announcement happens at pool start.
        # (alice, index 0, has no delay and may finish before this poll
        # notices -- that race is fine and irrelevant to what this test
        # checks, so `seen` is never asserted on here.)
        async with asyncio.timeout(10.0):
            while len(announced) < 2:
                await asyncio.sleep(0.01)
        assert announced == [("bob", 12.0), ("carol", 24.0)]
    finally:
        gate.set()
        await asyncio.wait_for(task, timeout=10.0)
    assert announced == [("bob", 12.0), ("carol", 24.0)]


@pytest.mark.asyncio
async def test_the_zero_wait_child_is_never_announced():
    """Index 0 (and any pool with no stagger at all) waits 0.0s -- announcing
    a `holding 0s` would misreport a delay that never happens."""
    announced: list[tuple[str, float]] = []
    pool = SupervisorPool(
        [_supervisor("alice", [])],
        stagger_seconds=12.0,
        on_stagger=lambda character, wait: announced.append((character, wait)),
    )
    await asyncio.wait_for(pool.run(), timeout=10.0)
    assert announced == []


@pytest.mark.asyncio
async def test_no_stagger_pool_never_announces_either():
    """A pool built with no stagger at all (single-character, or a
    `--rate-budget`-less run) must stay silent for every child, not just
    index 0."""
    announced: list[tuple[str, float]] = []
    pool = SupervisorPool(
        [_supervisor(n, []) for n in ("alice", "bob")],
        on_stagger=lambda character, wait: announced.append((character, wait)),
    )
    await asyncio.wait_for(pool.run(), timeout=10.0)
    assert announced == []


@pytest.mark.asyncio
async def test_on_stagger_defaults_to_none_and_is_never_called():
    """The default pool (no `on_stagger` passed) must not crash when a child
    is genuinely staggered -- this is the branch that guards the callback."""
    gate = asyncio.Event()

    async def fake_sleep(delay: float) -> None:
        if delay:
            await gate.wait()

    pool = SupervisorPool(
        [_supervisor(n, []) for n in ("alice", "bob")],
        stagger_seconds=12.0,
        sleep=fake_sleep,
    )
    task = asyncio.ensure_future(pool.run())
    await asyncio.sleep(0.05)
    gate.set()
    await asyncio.wait_for(task, timeout=10.0)  # no raise


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
