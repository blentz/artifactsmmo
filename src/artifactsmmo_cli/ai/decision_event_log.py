"""DecisionEventLog: the per-cycle buffer of compensating-mechanism firings.

Mechanisms live in several objects (the arbiter, the player's recovery code,
the grind expansion), and a cycle may fire dozens of them. They all note into
one shared buffer, and the player writes the buffer to the learning DB in one
batch alongside that cycle's `cycles` row, so events and cycles share a
`cycle_index` and cost one transaction, not one per event.
"""

from artifactsmmo_cli.ai.decision_mechanism import Mechanism
from artifactsmmo_cli.ai.planner import PlanStats


def search_detail(stats: PlanStats, plan_len: int) -> str:
    """One A* search as event detail. `nodes_created` is the memory-relevant
    count; `cycles.planner_nodes` keeps only the last search's EXPLORED count,
    which understated the 2026-09-25 grind blow-up by 15x."""
    return (f"nodes_created={stats.nodes_created} explored={stats.nodes_explored} "
            f"depth={stats.max_depth_reached} timed_out={stats.timed_out} "
            f"node_capped={stats.node_capped} plan_len={plan_len}")


class DecisionEventLog:
    """Buffered `(mechanism, subject, detail)` notes for the current cycle."""

    def __init__(self) -> None:
        self._pending: list[tuple[Mechanism, str, str]] = []

    def note(self, mechanism: Mechanism, subject: str, detail: str = "") -> None:
        """Record that `mechanism` fired on `subject` this cycle."""
        self._pending.append((mechanism, subject, detail))

    def drain(self) -> list[tuple[Mechanism, str, str]]:
        """Return this cycle's notes and start the next cycle empty."""
        pending, self._pending = self._pending, []
        return pending
