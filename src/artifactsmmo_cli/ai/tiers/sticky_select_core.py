"""Pure core for the Tier-2 root sticky override (mirrors Lean).

This is the executable image of `Formal/Liveness/StickySelect.lean`'s `stickyChoose`
and `nextLast`. The differential harness (`formal/diff/test_sticky_select_diff.py`)
feeds random inputs to BOTH this core and the Lean oracle and asserts they compute the
same function; the Lean side carries the kernel-proved no-zombie theorems
(`sticky_requires_progress`, `no_infinite_sticky_hold`). Keep this byte-faithful to the
Lean defs — any divergence is a differential failure.

`sticky_choose` is the post-sort override at `tiers/strategy.py:582-595`: given the
ranked candidate list (head = top-scored), keep the top unless the previous cycle's
`last_chosen` root survives this cycle and the top does not dominate it by `ratio`.

`next_last` is the progress-gated feedback (the 2026-06-20 fix): the chosen root's repr
is fed back as next cycle's `last_chosen` ONLY when it progressed — replacing the broken
`chosen_step_alive` gate that re-committed a never-executing zombie grind forever.
"""

from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class StickyCand:
    """A ranked objective-root candidate, reduced to the two fields the sticky
    override reads: its `repr_` (identity key vs `last_chosen`) and blended `score`."""

    repr_: str
    score: Fraction


def sticky_choose(
    cands: list[StickyCand], last_chosen: str | None, ratio: Fraction
) -> StickyCand | None:
    """Mirror of Lean `stickyChoose`. `cands` is the decide_key-sorted list (head =
    top). Returns the chosen candidate, or None when the list is empty.

    * empty list -> None;
    * `last_chosen is None` -> top (no sticky, e.g. first cycle or just-released);
    * `last_chosen == top.repr_` -> top (already committed to it);
    * else find the sticky candidate; if it dropped out this cycle -> top; if present
      and `top.score <= ratio * sticky.score` -> KEEP sticky; else top dominates -> top.
    """
    if not cands:
        return None
    top = cands[0]
    if last_chosen is None:
        return top
    if last_chosen == top.repr_:
        return top
    sticky = next((c for c in cands if c.repr_ == last_chosen), None)
    if sticky is None:
        return top
    if top.score <= ratio * sticky.score:
        return sticky
    return top


def next_last(chosen_repr: str | None, progressed: bool) -> str | None:
    """Mirror of Lean `nextLast`. Feed the chosen root's repr back as next cycle's
    `last_chosen` only when it progressed; otherwise release the anchor (None)."""
    if chosen_repr is None:
        return None
    return chosen_repr if progressed else None
