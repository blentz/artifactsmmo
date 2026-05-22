"""Personality seam: how an AI player weights the Tier-1 gap categories.

P1 ships only BalancedPersonality (uniform weights). P5 adds skill-first /
level-first / aligned variants by returning non-uniform category weights."""

from typing import Protocol

from artifactsmmo_cli.ai.tiers.objective import ObjectiveGap

CATEGORIES = ("char_level", "skills", "gear")


class Personality(Protocol):
    """Weights the three Tier-1 gap categories. Higher = pursue harder."""

    def category_weight(self, category: str) -> float: ...


class BalancedPersonality:
    """Weights every gap category equally — the default 'well-rounded' player."""

    def category_weight(self, category: str) -> float:
        return 1.0


def weighted_remaining(gap: ObjectiveGap, personality: Personality) -> float:
    """Single scalar of remaining work (0 when the objective is complete),
    summing each category's normalised fraction times its personality weight.
    P3's frontier search ranks candidate subgoals by how much they reduce this."""
    return (
        personality.category_weight("char_level") * gap.char_level_fraction
        + personality.category_weight("skills") * gap.skills_fraction
        + personality.category_weight("gear") * gap.gear_fraction
    )
