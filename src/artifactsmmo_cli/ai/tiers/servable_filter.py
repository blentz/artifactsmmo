"""Pure core: keep only objective-root candidates whose actionable step is servable.

When at least one candidate root has a plannable step THIS cycle, the unservable
ones are dropped before ranking/sticky — so `chosen_root` is a root the bot can
actually work on, never a top-scored-but-unbuildable objective (the feather_coat
mismatch: committed to a woodcutting-skill-gated body armor while the bot
char-grinds slimes under-geared). When NO candidate is servable, all are kept
(graceful fallback — the arbiter's own fallback walk still runs).

Mirrored in Lean (`Formal/Liveness/ServableFilter.lean`): the filter and the
"chosen root is servable when any servable exists" theorem; the differential binds
this function to the oracle. `servable` is the production plannability witness
(objective_step_goal + Goal.is_plannable), a model<->code boundary like
`root_progress`.
"""

from typing import TypeVar

T = TypeVar("T")


def keep_servable(items: list[T], servable: list[bool]) -> list[T]:
    """Return the servable subset of `items`; if none are servable, return all of
    them unchanged. `servable[i]` is whether `items[i]`'s actionable step yields a
    plannable goal this cycle. Lengths must match."""
    if len(items) != len(servable):
        raise ValueError("items and servable must have equal length")
    kept = [it for it, ok in zip(items, servable, strict=True) if ok]
    return kept if kept else list(items)
