"""RestartPolicy: exit reason + prior attempts -> restart decision."""

from dataclasses import dataclass

BASE_DELAY_SECONDS = 5.0
MAX_DELAY_SECONDS = 300.0
MAX_ATTEMPTS = 5

RESTARTABLE_REASONS = frozenset({"server_unavailable", "crash:network"})
"""Only genuinely transient causes. `stuck_exit` means the AI needs
intervention and a restart re-sticks it; a plain `crash` is a bug that a
restart loop would hide behind apparent health."""


@dataclass(frozen=True)
class RestartDecision:
    restart: bool
    delay_seconds: float


class RestartPolicy:
    def decide(self, reason: str, attempts: int) -> RestartDecision:
        if reason not in RESTARTABLE_REASONS or attempts >= MAX_ATTEMPTS:
            return RestartDecision(restart=False, delay_seconds=0.0)
        delay = min(BASE_DELAY_SECONDS * (2**attempts), MAX_DELAY_SECONDS)
        return RestartDecision(restart=True, delay_seconds=delay)
