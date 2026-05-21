"""Skill XP-to-level curve: observed where possible, estimated beyond.

The API exposes only the CURRENT level's requirement (CharacterSchema.<skill>_max_xp,
"XP required to level up the skill"). The full curve is not published, so levels
beyond those observed are estimated as a learned multiple of the current gap:
required_xp(level+k) ~= last_observed_max_xp * growth_ratio**k, where growth_ratio
is the mean ratio between observed consecutive levels (DEFAULT_GROWTH_RATIO until
two levels are observed). Never a hardcoded curve — estimates refine as more
levels are observed. See spec citations.
"""

from dataclasses import dataclass, field

DEFAULT_GROWTH_RATIO = 1.5
"""Fallback per-level XP growth multiplier until >=2 levels are observed for a
skill. Documented default (not sourced from the API); replaced by the observed
mean ratio as soon as two consecutive observed levels exist."""


@dataclass
class SkillXpCurve:
    """XP-to-next-level for one skill. `observed` is {level: max_xp}."""

    observed: dict[int, int] = field(default_factory=dict)

    def growth_ratio(self) -> float:
        ratios = [
            self.observed[lvl + 1] / self.observed[lvl]
            for lvl in self.observed
            if lvl + 1 in self.observed and self.observed[lvl] > 0
        ]
        return sum(ratios) / len(ratios) if ratios else DEFAULT_GROWTH_RATIO

    def required_xp(self, level: int) -> int:
        if level in self.observed:
            return self.observed[level]
        if not self.observed:
            return 0
        highest = max(self.observed)
        steps = level - highest
        return int(self.observed[highest] * (self.growth_ratio() ** steps))

    def total_xp_to_reach(self, current_level: int, target_level: int) -> int:
        return sum(self.required_xp(lvl) for lvl in range(current_level, target_level))

    def cycles_to_level(self, current_level: int, target_level: int,
                        xp_per_cycle: float) -> float:
        if target_level <= current_level:
            return 0.0
        if xp_per_cycle <= 0:
            return float("inf")
        return self.total_xp_to_reach(current_level, target_level) / xp_per_cycle

    def is_confident(self, current_level: int, target_level: int) -> bool:
        """True only if every level in the gap was directly observed."""
        return all(lvl in self.observed for lvl in range(current_level, target_level))
