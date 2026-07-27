"""PURE achievability core. No GameData/WorldState — plain scalars only,
mirrored by formal/Formal/Achievability.lean.

Achievability is the fourth modulating factor in the tree's selection weight:

    weight = gain * falloff(focus) * synergy * achievability
             │       │               │         │
        magnitude  staleness       purity   effort-to-reach

It answers "how much work is left before I can have this", so a large but
distant upgrade stops starving a smaller one I could build now. Live at L21,
lich_race_trophy (gain 25050, 1000 event_tickets away) outranked life_ring
(gain 21020, craftable from gatherable materials) on magnitude alone.

The impure assembly layer (progression_tree.py) computes the two integers —
`effort`, the candidate's UNMET demand, and `min_effort`, the cheapest
candidate's — and this module maps them to a bounded `Fraction`. Taking two
ints keeps the proven core scalar and its mutation group small, mirroring
`synergy_pure(shared, total)` and `falloff(focus_level)`.
"""

from fractions import Fraction

A_MIN = Fraction(1, 2)
"""Floor of the achievability multiplier (> 0): even an enormously distant
target keeps a strictly-positive weight, so d'Hondt still awards it a seat
eventually (`interleaveDue_reaches`, resting on `minWeight_pos`). The range
1/A_MIN = 2 is deliberately kept strictly inside `synergy`'s 3:1 (S_MIN = 1/3),
which is itself inside `falloff`'s 9:1 — so aging dominates alignment dominates
effort. A maximally distant candidate can therefore only lose to a maximally
close one when the gain gap is under 2x; a genuinely enormous upgrade still
wins. One of TWO tuning surfaces (see `EFFORT_SCALE`); the shape is an affine
map into [A_MIN, 1], pinned by the tests and Achievability.lean."""

EFFORT_SCALE = 100
"""How much unmet work counts as a MEANINGFUL difference, in demand units.

Added to both sides of the effort ratio, so the multiplier answers "how does
this compare to the cheapest option, on a scale where 100 units matters" rather
than "what is the bare ratio".

This is an ABSOLUTE constant, and the design deliberately tried to avoid one —
the factor was originally scored purely relative to the cheapest candidate, with
a `+1` present only to avoid dividing by zero. Live 2026-07-27 proved pure
self-scaling cannot work, because effort is unbounded below: a
`small_health_potion` in the utility slot costs ~0 unmet units and appears in
most real decisions, which pinned the reference at 0 and collapsed every
candidate onto the floor TOGETHER —

    +1  scale, potion live:  spread 1.03:1  -> raw gain wins, trophy retakes top
    +100 scale, potion live: spread 1.35:1  -> life_ring 18472 > trophy 13664

Anchoring on the most DISTANT candidate instead was tried and rejected: it has
the mirror-image flaw, manufacturing a full 2:1 spread from trivial differences
(a 1-unit candidate is floored merely for being the pool maximum), which broke
the reversibility witness. A scale constant is the honest fix — the quantity is
real and nameable, and pretending it does not exist is what produced the
collapse. Pinned by a test and a mutation anchor; recalibrate against a live
trace, the way FOCUS_FLOOR was."""


def achievability_pure(effort: int, min_effort: int) -> Fraction:
    """Effort multiplier for a candidate needing `effort` unmet units, where the
    cheapest live candidate needs `min_effort`.

    Affine map of `(min_effort + EFFORT_SCALE) / (effort + EFFORT_SCALE)` into
    `[A_MIN, 1]` — same shape as `synergy_pure` and `falloff`. Exact `Fraction`,
    no float in the decision path.

    Relative to the cheapest candidate, but on a fixed SCALE: `EFFORT_SCALE` is
    what stops an already-held candidate (effort 0) from dragging the reference
    down and collapsing everyone else onto the floor together. See that
    constant's docstring for the live failure that put it there — with a scale
    of 1 the factor was self-disabling in most real decisions.

    `effort <= 0` means the candidate needs nothing new, which is immediately
    achievable — returns 1, not a division by zero. `effort < min_effort`
    (when effort > 0) is impossible by construction (min_effort is the minimum
    over a set containing effort); the core ASSERTS rather than clamps, so an
    assembly-layer bug fails loudly instead of being silently corrected."""
    if effort <= 0:
        return Fraction(1)
    assert effort >= min_effort >= 0, f"effort {effort} below min {min_effort}"
    return A_MIN + (Fraction(1) - A_MIN) * Fraction(
        min_effort + EFFORT_SCALE, effort + EFFORT_SCALE)
