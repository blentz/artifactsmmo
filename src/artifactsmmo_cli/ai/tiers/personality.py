"""Personality seam: how an AI player weights the Tier-1 gap categories.

P1 ships only BalancedPersonality (uniform weights). P5 adds skill-first /
level-first / aligned variants by returning non-uniform category weights.

STRICT-POSITIVITY CONTRACT (proved in `formal/Formal/WeightedRemaining.lean`):
the equivalence `weighted_remaining == 0  ⇔  ObjectiveGap.is_complete` holds
IFF every category weight is STRICTLY POSITIVE. A personality that returns
`0.0` for a category weight makes `weighted_remaining` insensitive to that
category and can report a zero scalar on an INCOMPLETE objective (Lean
witness: `weightedRemaining_zero_not_complete_witness`). Implementers MUST
return `category_weight(c) > 0` for every category. `BalancedPersonality`
satisfies this trivially (all weights = 1.0)."""

from fractions import Fraction
from typing import Protocol

from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap
from artifactsmmo_cli.ai.tiers.objective_completion import weighted_remaining_pure

CATEGORIES = ("char_level", "skills", "gear")


class Personality(Protocol):
    """Weights the three Tier-1 gap categories. Higher = pursue harder.

    CONTRACT: `category_weight(c) > 0` for every `c in CATEGORIES` (see module
    docstring + the Lean strict-positivity equivalence)."""

    def category_weight(self, category: str) -> Fraction: ...


class BalancedPersonality:
    """Weights every gap category equally — the default 'well-rounded' player."""

    def category_weight(self, category: str) -> Fraction:
        return Fraction(1)


def weighted_remaining(gap: ObjectiveGap, personality: Personality) -> Fraction:
    """Single scalar of remaining work (0 when the objective is complete UNDER
    strictly-positive category weights — see module docstring), summing each
    category's normalised fraction times its personality weight. P3's frontier
    search ranks candidate subgoals by how much they reduce this."""
    return weighted_remaining_pure(
        (personality.category_weight("char_level"),
         personality.category_weight("skills"),
         personality.category_weight("gear")),
        (gap.char_level_fraction, gap.skills_fraction, gap.gear_fraction),
    )
