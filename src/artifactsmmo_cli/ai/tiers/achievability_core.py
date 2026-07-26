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
wins. This is the ONLY tuning surface; the shape is an affine map into
[A_MIN, 1], pinned by the tests and Achievability.lean."""


def achievability_pure(effort: int, min_effort: int) -> Fraction:
    """Effort multiplier for a candidate needing `effort` unmet units, where the
    cheapest live candidate needs `min_effort`.

    Affine map of `(min_effort + 1) / (effort + 1)` into `[A_MIN, 1]` — same
    shape as `synergy_pure` and `falloff`. Exact `Fraction`, no float in the
    decision path.

    RELATIVE, not absolute: the factor is scored against the cheapest candidate
    in the same decision, so there is no tuned effort scale to drift — the same
    self-scaling argument the requirement multiset's token weights make.

    The `+1` on both sides is not cosmetic. It keeps a zero-effort candidate
    from dividing by zero, and keeps ONE fully-held candidate from slamming
    every other candidate to the floor: with raw ratios, min_effort = 0 sends
    every other ratio to 0 regardless of whether they need 2 units or 2000.

    `effort < min_effort` cannot happen by construction (min_effort is the
    minimum over a set containing effort); the core ASSERTS rather than clamps,
    so an assembly-layer bug fails loudly instead of being silently corrected."""
    if effort <= 0:
        return Fraction(1)
    assert effort >= min_effort >= 0, f"effort {effort} below min {min_effort}"
    return A_MIN + (Fraction(1) - A_MIN) * Fraction(min_effort + 1, effort + 1)
