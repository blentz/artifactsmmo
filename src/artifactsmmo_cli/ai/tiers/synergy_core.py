"""PURE synergy core (spec 2026-07-19 §3, Phase 2). No GameData/WorldState —
plain scalars only, mirrored by Formal/Formal/Synergy.lean.

Synergy is the third modulating factor in the tree's selection weight:

    weight = gain * falloff(focus) * synergy
             │       │               │
        magnitude  staleness       purity

`synergy` answers "what fraction of the work this target creates is work I need
anyway" — a dimensionless purity ratio, the demand-weighted overlap of a
candidate's own requirement multiset with the union of the OTHER live roots'
(leave-one-out). Magnitude already lives in `gain`; this factor only rewards
alignment, never size.

The impure assembly layer (progression_tree.py, Phase 3) computes the two
integer arguments — `shared` = demand-weighted units of the candidate's work
that overlap the other roots, `total` = demand-weighted size of the candidate's
own work — and this module maps them to a bounded `Fraction`. Taking two ints
(not two DemandSets) keeps the proven core scalar and its mutation group small,
mirroring `falloff(focus_level: int)`."""

from fractions import Fraction

S_MIN = Fraction(1, 3)
"""Floor of the synergy multiplier (> 0): even a zero-overlap target keeps a
strictly-positive weight, so d'Hondt still awards it a seat eventually
(`interleaveDue_reaches`, resting on `minWeight_pos`). The range S_MAX/S_MIN = 3
is deliberately kept strictly inside `falloff`'s 9:1 (FOCUS_FLOOR = 1/9) so
aging structurally dominates alignment — a high-synergy stuck root still decays
(spec §3.5). This is the ONLY tuning surface; the shape is an affine map into
[S_MIN, 1], pinned by the tests and Synergy.lean."""


def synergy_pure(shared: int, total: int) -> Fraction:
    """Purity multiplier for a candidate whose own work is `total`
    demand-weighted units, of which `shared` overlap the other live roots.

    Affine map of `shared/total` into `[S_MIN, 1]` — same shape as `falloff`.
    Exact `Fraction`, no float in the decision path.

    `total <= 0` means the candidate needs nothing new, which is maximally
    aligned (§3.4) — returns 1, not a division by zero. `shared > total` is
    impossible by construction (an intersection cannot exceed its own set); the
    core ASSERTS rather than clamps, so an assembly-layer bug fails loudly
    instead of being silently corrected."""
    if total <= 0:
        return Fraction(1)
    assert shared <= total, f"shared {shared} exceeds total {total}"
    return S_MIN + (Fraction(1) - S_MIN) * Fraction(shared, total)
