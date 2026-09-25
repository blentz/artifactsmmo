"""RateGovernor: fleet-wide sliding-window throttle that only blocks on a real burst."""

import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import pytest

from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.rate_governor import RateGovernor
from artifactsmmo_cli.utils.request_log import RequestLog


class _FakeTime:
    """A clock whose sleeps advance it, so tests never actually wait."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _budget(**windows: Any) -> WindowBudget:
    return WindowBudget(
        second=windows.get("second"),
        minute=windows.get("minute"),
        hour=windows.get("hour"),
        day=None,
    )


@pytest.fixture
def make_log() -> Iterator[Callable[[str], RequestLog]]:
    """Open request logs and close every one at teardown."""
    opened: list[RequestLog] = []

    def make(db: str = ":memory:") -> RequestLog:
        log = RequestLog(db)
        opened.append(log)
        return log

    yield make
    for log in opened:
        log.close()


def _governor(fake: _FakeTime, make_log: Callable[[str], RequestLog], **windows: Any) -> RateGovernor:
    return RateGovernor(_budget(**windows), sharers=1, log=make_log(":memory:"),
                        bucket="account", clock=fake.clock, sleep=fake.sleep)


def test_sustainable_interval_reports_the_binding_windows_pace(make_log: Callable[[str], RequestLog]) -> None:
    """The governor is what the bot holds at runtime, so it is where the planner
    reads the pace a request actually costs. 300/hour is one request per 12s;
    10/second permits far faster bursts but is not sustainable, so the HOUR
    window binds — the same rule `WindowBudget.sustainable_interval` documents."""
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=10, hour=300)
    assert governor.sustainable_interval() == 12.0


def test_sustainable_interval_is_zero_when_no_window_is_declared(make_log: Callable[[str], RequestLog]) -> None:
    """No declared limit means no pacing required, NOT pace infinitely slowly —
    and a zero floor is exactly the pre-change planner."""
    fake = _FakeTime()
    assert _governor(fake, make_log).sustainable_interval() == 0.0


def test_requests_under_the_limit_never_block(make_log: Callable[[str], RequestLog]) -> None:
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=2)
    governor.acquire()
    governor.acquire()
    assert fake.slept == []


def test_exceeding_a_window_sleeps_until_the_oldest_request_ages_out(make_log: Callable[[str], RequestLog]) -> None:
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [1.0]


def test_the_tightest_window_wins(make_log: Callable[[str], RequestLog]) -> None:
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=10, minute=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [60.0]


def test_time_spent_on_cooldown_refills_the_window(make_log: Callable[[str], RequestLog]) -> None:
    """The bot sleeps out an action cooldown between requests. That idle time
    must count toward the window, so a cooldown-bound bot never sees latency
    added by the governor."""
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=1)
    governor.acquire()
    fake.now += 25.0  # a fight cooldown
    governor.acquire()
    assert fake.slept == []


def test_a_budget_with_no_declared_windows_never_blocks(make_log: Callable[[str], RequestLog]) -> None:
    fake = _FakeTime()
    governor = _governor(fake, make_log)
    for _ in range(100):
        governor.acquire()
    assert fake.slept == []


def test_longest_wait_ages_out_the_oldest_request_not_the_newest(make_log: Callable[[str], RequestLog]) -> None:
    """Pins the `recent[-limit]` index in `request_log.longest_wait`. With limit=3 and
    three unevenly-spaced prior requests, the wait must be computed from the
    OLDEST request in the window (recent[0]), not the newest (recent[-1]).
    Using timestamps 0, 0.3, 0.6 makes the two choices diverge: oldest-based
    wait is 0.4s, newest-based wait would be 1.0s. A wrong index here would
    make the governor sleep far longer than necessary on every burst."""
    fake = _FakeTime()
    governor = _governor(fake, make_log, second=3)
    governor.acquire()  # t=0.0
    fake.now = 0.3
    governor.acquire()  # t=0.3
    fake.now = 0.6
    governor.acquire()  # t=0.6, window now has 3 requests: [0.0, 0.3, 0.6]
    governor.acquire()  # must wait for t=0.0 to age out: 0.0 + 1.0 - 0.6 = 0.4
    assert fake.slept == [0.4]


def test_sustainable_interval_is_one_childs_fair_share(make_log: Callable[[str], RequestLog]) -> None:
    """The window is fleet-wide, but the planner prices an action at what ONE
    child can sustain: 300/hour shared by 5 children is one request per 60s."""
    fake = _FakeTime()
    governor = RateGovernor(_budget(second=10, hour=300), sharers=5,
                            log=make_log(":memory:"), bucket="account",
                            clock=fake.clock, sleep=fake.sleep)
    assert governor.sustainable_interval() == 60.0


def test_sharers_must_be_positive(make_log: Callable[[str], RequestLog]) -> None:
    with pytest.raises(ValueError, match="sharers must be >= 1"):
        RateGovernor(_budget(second=1), sharers=0, log=make_log(":memory:"),
                     bucket="account")


def test_siblings_share_one_window(tmp_path: Path, make_log: Callable[[str], RequestLog]) -> None:
    """Two children on one DB file draw from ONE budget: the second child's
    request waits on the first child's, which a per-process history never saw."""
    db = str(tmp_path / "fleet.db")
    fake = _FakeTime()
    first = RateGovernor(_budget(second=1), sharers=2, log=make_log(db),
                         bucket="account", clock=fake.clock, sleep=fake.sleep)
    second = RateGovernor(_budget(second=1), sharers=2, log=make_log(db),
                          bucket="account", clock=fake.clock, sleep=fake.sleep)
    first.acquire()
    second.acquire()
    assert fake.slept == [1.0]


def test_buckets_are_independent(tmp_path: Path, make_log: Callable[[str], RequestLog]) -> None:
    db = str(tmp_path / "fleet.db")
    fake = _FakeTime()
    account = RateGovernor(_budget(second=1), sharers=1, log=make_log(db),
                           bucket="account", clock=fake.clock, sleep=fake.sleep)
    data = RateGovernor(_budget(second=1), sharers=1, log=make_log(db),
                        bucket="data", clock=fake.clock, sleep=fake.sleep)
    account.acquire()
    data.acquire()
    assert fake.slept == []


def test_the_log_forgets_requests_older_than_the_longest_window(
        tmp_path: Path, make_log: Callable[[str], RequestLog]) -> None:
    db = str(tmp_path / "fleet.db")
    log = make_log(db)
    assert log.try_record("account", 0.0, {1.0: 5}) == 0.0
    assert log.try_record("account", 10.0, {1.0: 5}) == 0.0
    rows = make_log(db)._conn.execute("SELECT ts FROM rate_requests").fetchall()
    assert rows == [(10.0,)]


def test_racing_siblings_never_overfill_a_window(tmp_path: Path) -> None:
    """The count and the insert share one write-locked transaction, so siblings
    racing on separate connections cannot both see the last free slot."""
    db = str(tmp_path / "fleet.db")
    RequestLog(db).close()  # create the schema before the race
    granted: list[int] = []

    def sibling() -> None:
        log = RequestLog(db)
        granted.append(sum(1 for _ in range(25) if log.try_record("account", 5.0, {1000.0: 50}) == 0.0))
        log.close()

    threads = [threading.Thread(target=sibling) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert sum(granted) == 50


def test_entries_from_a_previous_boot_do_not_block(tmp_path: Path,
                                                   make_log: Callable[[str], RequestLog]) -> None:
    """Live 2026-09-25 17:03Z: after a reboot the log held timestamps from the
    previous boot's monotonic clock (~255,000) while the new clock read ~680, so
    every entry lay in the future, counted inside every window, and never aged
    out. All five children blocked in `_initialize` forever. A timestamp later
    than now cannot be a real past request; it is dropped."""
    db = str(tmp_path / "fleet.db")
    log = make_log(db)
    assert log.try_record("data", 255_000.0, {3600.0: 1}) == 0.0
    assert log.try_record("data", 680.0, {3600.0: 1}) == 0.0
    rows = make_log(db)._conn.execute("SELECT ts FROM rate_requests").fetchall()
    assert rows == [(680.0,)]


def test_the_default_clock_is_wall_time() -> None:
    """Wall-clock time survives a reboot; the monotonic clock restarts at zero."""
    assert RateGovernor.__init__.__defaults__ is not None
    assert time.time in RateGovernor.__init__.__defaults__
