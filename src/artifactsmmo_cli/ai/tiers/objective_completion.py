"""Pure cores for the personality-weighted gap scalar and the objective-complete
predicate (the formal target for `WeightedRemaining.lean`).

Production extracts the three category fractions from `ObjectiveGap`
(`char_level_fraction`, `skills_fraction`, `gear_fraction`) and the three
category weights from `Personality.category_weight("char_level"/"skills"/"gear")`,
then computes Σ w * f. `is_complete` asks all three fractions to be exactly 0.0.

These pure helpers take the (weights, fractions) tuples DIRECTLY so the Lean
oracle can mirror them bit-for-bit over `Rat` (fed as exact `fractions.Fraction`
in the differential test). Production behavior is unchanged: `personality.py`
and `objective.py` call these cores with the same inputs they used inline.

STRICT-POSITIVITY CONTRACT (latent-bug surface, see Lean
`weightedRemaining_zero_iff_complete_of_positive` + the bug-teeth
`weightedRemaining_zero_not_complete_witness`): the equivalence
`weighted_remaining == 0  ⇔  is_complete` holds IFF every personality weight is
STRICTLY POSITIVE. A future personality that returns `0.0` for a category
weight would make `weighted_remaining` insensitive to that category and could
report a zero scalar on an INCOMPLETE objective. P1 ships only
`BalancedPersonality` (all weights = 1.0), so the latent defect is unreachable
today. The contract is documented in `Personality.category_weight`; no runtime
assert is added by this refactor (a behavioral change is deferred to an
explicit decision)."""


def weighted_remaining_pure(
    weights: tuple[float, float, float],
    fractions: tuple[float, float, float],
) -> float:
    """Σ_i weights[i] * fractions[i] over the three Tier-1 categories
    (char_level, skills, gear), in that order."""
    return (weights[0] * fractions[0]
            + weights[1] * fractions[1]
            + weights[2] * fractions[2])


def is_complete_pure(fractions: tuple[float, float, float]) -> bool:
    """The objective is complete iff EVERY category fraction is exactly 0.0."""
    return (fractions[0] == 0.0
            and fractions[1] == 0.0
            and fractions[2] == 0.0)
