"""RateGovernor: a fleet-wide sliding-window throttle for one rate-limit bucket."""

import time
from collections.abc import Callable

from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.request_log import RequestLog


class RateGovernor:
    """Enforces every declared window of one bucket at once, across the fleet.

    Sliding-window rather than a leaky bucket, because the server's limits are
    literally "N requests per window". Idle time counts toward the window for
    free, so a cooldown-bound bot -- which sleeps 15-25s between actions --
    never sees latency added here. The governor blocks only when a genuine
    burst has drained a window.

    `budget` is the WHOLE per-IP budget, not a slice of it: the request history
    lives in a `RequestLog` every sibling shares, so the window counts are the
    fleet's. `sharers` is how many children share it, which matters only for
    `sustainable_interval`.
    """

    def __init__(
        self,
        budget: WindowBudget,
        sharers: int,
        log: RequestLog,
        bucket: str,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if sharers < 1:
            raise ValueError(f"sharers must be >= 1, got {sharers}")
        self._budget = budget
        self._sharers = sharers
        self._windows = budget.as_windows()
        self._log = log
        self._bucket = bucket
        self._clock = clock
        self._sleep = sleep

    def sustainable_interval(self) -> float:
        """Seconds per request ONE child can sustain indefinitely: its fair
        share, `budget.divided_by(sharers)`.

        The fleet-wide window lets a child burst past its share, but on average
        `sharers` children split the budget, and that average is what the
        planner needs to price an action at what a request actually costs (see
        `GOAPPlanner.action_floor_seconds`). The formula (`max(span / limit)`,
        and why the LONGEST spacing is the binding one) is documented and tested
        in `WindowBudget.sustainable_interval`, not recomputed here."""
        return self._budget.divided_by(self._sharers).sustainable_interval()

    def acquire(self) -> None:
        """Block until one request may be sent, then record it."""
        while True:
            wait = self._log.try_record(self._bucket, self._clock(), self._windows)
            if wait <= 0.0:
                return
            self._sleep(wait)
