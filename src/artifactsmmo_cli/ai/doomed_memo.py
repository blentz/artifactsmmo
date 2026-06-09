"""Remembers goals that timed out (no plan) so the arbiter skips re-planning them
until their plannability signature changes or a re-probe window elapses. This is
the steady-state half of the tiered-budget fix: width-unfindable goals are tried
once, then skipped, instead of burning the budget every cycle."""

from artifactsmmo_cli.ai.plannability_signature import Signature, plannability_signature
from artifactsmmo_cli.ai.world_state import WorldState


class DoomedMemo:
    """Per-session record of goals that produced no plan. Keyed by `repr(goal)`."""

    def __init__(self, retry_after_cycles: int = 20) -> None:
        self._retry_after = retry_after_cycles
        self._entries: dict[str, tuple[Signature, int]] = {}

    def mark(self, goal_repr: str, state: WorldState, cycle: int) -> None:
        """Record that `goal_repr` produced no plan at this state/cycle."""
        self._entries[goal_repr] = (plannability_signature(state), cycle)

    def clear(self, goal_repr: str) -> None:
        """Forget a goal (called when it plans successfully)."""
        self._entries.pop(goal_repr, None)

    def is_doomed(self, goal_repr: str, state: WorldState, cycle: int) -> bool:
        """True => skip planning this goal this cycle. False once the signature
        changes (new plannability) or the re-probe window has elapsed."""
        entry = self._entries.get(goal_repr)
        if entry is None:
            return False
        sig, set_at = entry
        if sig != plannability_signature(state):
            return False
        return not cycle - set_at >= self._retry_after
