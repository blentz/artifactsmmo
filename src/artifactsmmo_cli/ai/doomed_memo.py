"""Remembers goals that timed out (no plan) so the arbiter skips re-planning them
until their plannability signature changes or a re-probe window elapses. This is
the steady-state half of the tiered-budget fix: width-unfindable goals are tried
once, then skipped, instead of burning the budget every cycle.

The re-probe window ESCALATES: each consecutive failure of the same goal under
the same signature doubles the TTL (base 20 → 40 → 80, capped at 160 cycles), so
a goal that keeps timing out on every re-probe is retried geometrically less
often instead of re-burning a full planning budget every fixed K cycles. The
counter resets when the goal plans successfully (`clear`) or when its
plannability signature changes (new levels = genuinely new plannability)."""

from artifactsmmo_cli.ai.plannability_signature import Signature, plannability_signature
from artifactsmmo_cli.ai.world_state import WorldState


class DoomedMemo:
    """Per-session record of goals that produced no plan. Keyed by `repr(goal)`."""

    def __init__(self, retry_after_cycles: int = 20,
                 max_retry_after_cycles: int = 160) -> None:
        self._base_retry = retry_after_cycles
        self._max_retry = max_retry_after_cycles
        # goal_repr -> (signature at mark time, cycle marked, consecutive failures)
        self._entries: dict[str, tuple[Signature, int, int]] = {}

    def mark(self, goal_repr: str, state: WorldState, cycle: int) -> None:
        """Record that `goal_repr` produced no plan at this state/cycle.

        A re-mark under the SAME signature is a consecutive failure (the
        re-probe also found no plan) and escalates the TTL; a mark under a
        new signature starts the failure count over at 1."""
        sig = plannability_signature(state)
        prev = self._entries.get(goal_repr)
        failures = prev[2] + 1 if prev is not None and prev[0] == sig else 1
        self._entries[goal_repr] = (sig, cycle, failures)

    def clear(self, goal_repr: str) -> None:
        """Forget a goal (called when it plans successfully)."""
        self._entries.pop(goal_repr, None)

    def _ttl(self, failures: int) -> int:
        """Re-probe window for the Nth consecutive failure: doubles each time,
        capped at `max_retry_after_cycles`."""
        return min(self._base_retry << (failures - 1), self._max_retry)

    def is_doomed(self, goal_repr: str, state: WorldState, cycle: int) -> bool:
        """True => skip planning this goal this cycle. False once the signature
        changes (new plannability) or the escalating re-probe window has
        elapsed."""
        entry = self._entries.get(goal_repr)
        if entry is None:
            return False
        sig, set_at, failures = entry
        if sig != plannability_signature(state):
            return False
        return cycle - set_at < self._ttl(failures)
