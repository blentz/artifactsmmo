"""RateGovernor: a sliding-window throttle for one rate-limit bucket."""

import time
from collections import deque
from collections.abc import Callable

from artifactsmmo_cli.utils.rate_budget import WindowBudget


class RateGovernor:
    """Enforces every declared window of one bucket at once.

    Sliding-window rather than a leaky bucket, because the server's limits are
    literally "N requests per window". Idle time counts toward the window for
    free, so a cooldown-bound bot -- which sleeps 15-25s between actions --
    never sees latency added here. The governor blocks only when a genuine
    burst has drained a window.
    """

    def __init__(
        self,
        budget: WindowBudget,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._windows = budget.as_windows()
        self._clock = clock
        self._sleep = sleep
        self._history: deque[float] = deque()
        self._longest = max(self._windows, default=0.0)

    def acquire(self) -> None:
        """Block until one request may be sent, then record it."""
        while True:
            now = self._clock()
            self._prune(now)
            wait = self._longest_wait(now)
            if wait <= 0.0:
                self._history.append(now)
                return
            self._sleep(wait)

    def _prune(self, now: float) -> None:
        while self._history and now - self._history[0] >= self._longest:
            self._history.popleft()

    def _longest_wait(self, now: float) -> float:
        """Seconds until every window has room. 0.0 when a request may go now."""
        wait = 0.0
        for span, limit in self._windows.items():
            recent = [t for t in self._history if now - t < span]
            if len(recent) >= limit:
                # The oldest request inside this window must age out of it.
                wait = max(wait, recent[-limit] + span - now)
        return wait
