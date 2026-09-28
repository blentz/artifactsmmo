"""RestartPolicy: exit reason + prior attempts -> restart decision."""

from dataclasses import dataclass

BASE_DELAY_SECONDS = 5.0
MAX_DELAY_SECONDS = 300.0
MAX_ATTEMPTS = 5

RESTARTABLE_REASONS = frozenset({"server_unavailable", "crash:network"})
"""Only genuinely transient causes. `stuck_exit` means the AI needs
intervention and a restart re-sticks it; a plain `crash` is a bug that a
restart loop would hide behind apparent health."""

UNCAPPED_REASONS = frozenset({"server_unavailable"})
"""Reasons restarted however many times they recur. The game API being down
says nothing about the bot, and an outage lasts as long as it lasts: a cap
turned a long outage into a character that stayed dead after the server came
back (HAL and Robby, 2026-09-28). The delay stays capped, so a long outage
costs one probe every `MAX_DELAY_SECONDS`."""


@dataclass(frozen=True)
class RestartDecision:
    restart: bool
    delay_seconds: float


class RestartPolicy:
    def decide(self, reason: str, attempts: int) -> RestartDecision:
        if reason not in RESTARTABLE_REASONS:
            return RestartDecision(restart=False, delay_seconds=0.0)
        if attempts >= MAX_ATTEMPTS and reason not in UNCAPPED_REASONS:
            return RestartDecision(restart=False, delay_seconds=0.0)
        # The exponent is bounded so an uncapped count cannot overflow the float.
        delay = min(BASE_DELAY_SECONDS * (2 ** min(attempts, 16)), MAX_DELAY_SECONDS)
        return RestartDecision(restart=True, delay_seconds=delay)
