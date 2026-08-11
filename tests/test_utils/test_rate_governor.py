"""RateGovernor: sliding-window throttle that only blocks on a real burst."""

from typing import Any

from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.rate_governor import RateGovernor


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


def _governor(fake: _FakeTime, **windows: Any) -> RateGovernor:
    budget = WindowBudget(
        second=windows.get("second"),
        minute=windows.get("minute"),
        hour=windows.get("hour"),
        day=None,
    )
    return RateGovernor(budget, clock=fake.clock, sleep=fake.sleep)


def test_sustainable_interval_reports_the_binding_windows_pace() -> None:
    """The governor is what the bot holds at runtime, so it is where the planner
    reads the pace a request actually costs. 300/hour is one request per 12s;
    10/second permits far faster bursts but is not sustainable, so the HOUR
    window binds — the same rule `WindowBudget.sustainable_interval` documents."""
    fake = _FakeTime()
    governor = _governor(fake, second=10, hour=300)
    assert governor.sustainable_interval() == 12.0


def test_sustainable_interval_is_zero_when_no_window_is_declared() -> None:
    """No declared limit means no pacing required, NOT pace infinitely slowly —
    and a zero floor is exactly the pre-change planner."""
    fake = _FakeTime()
    assert _governor(fake).sustainable_interval() == 0.0


def test_requests_under_the_limit_never_block() -> None:
    fake = _FakeTime()
    governor = _governor(fake, second=2)
    governor.acquire()
    governor.acquire()
    assert fake.slept == []


def test_exceeding_a_window_sleeps_until_the_oldest_request_ages_out() -> None:
    fake = _FakeTime()
    governor = _governor(fake, second=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [1.0]


def test_the_tightest_window_wins() -> None:
    fake = _FakeTime()
    governor = _governor(fake, second=10, minute=2)
    governor.acquire()
    governor.acquire()
    governor.acquire()
    assert fake.slept == [60.0]


def test_time_spent_on_cooldown_refills_the_window() -> None:
    """The bot sleeps out an action cooldown between requests. That idle time
    must count toward the window, so a cooldown-bound bot never sees latency
    added by the governor."""
    fake = _FakeTime()
    governor = _governor(fake, second=1)
    governor.acquire()
    fake.now += 25.0  # a fight cooldown
    governor.acquire()
    assert fake.slept == []


def test_a_budget_with_no_declared_windows_never_blocks() -> None:
    fake = _FakeTime()
    governor = _governor(fake)
    for _ in range(100):
        governor.acquire()
    assert fake.slept == []


def test_longest_wait_ages_out_the_oldest_request_not_the_newest() -> None:
    """Pins the `recent[-limit]` index in `_longest_wait`. With limit=3 and
    three unevenly-spaced prior requests, the wait must be computed from the
    OLDEST request in the window (recent[0]), not the newest (recent[-1]).
    Using timestamps 0, 0.3, 0.6 makes the two choices diverge: oldest-based
    wait is 0.4s, newest-based wait would be 1.0s. A wrong index here would
    make the governor sleep far longer than necessary on every burst."""
    fake = _FakeTime()
    governor = _governor(fake, second=3)
    governor.acquire()  # t=0.0
    fake.now = 0.3
    governor.acquire()  # t=0.3
    fake.now = 0.6
    governor.acquire()  # t=0.6, window now has 3 requests: [0.0, 0.3, 0.6]
    governor.acquire()  # must wait for t=0.0 to age out: 0.0 + 1.0 - 0.6 = 0.4
    assert fake.slept == [0.4]
