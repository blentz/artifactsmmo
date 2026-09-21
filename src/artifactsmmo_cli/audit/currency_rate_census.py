"""What each goal actually paid, per currency, per second.

THE DENOMINATOR IS THE WHOLE POINT, and production already solves it. The
arbiter files the Rests a grind forces under `RestoreHP` because it preempts the
grind to take them; measured on 36,455 live cycles, `GrindCharacterXP(green_slime)`
is 100% FightAction with 0% Rest while `RestoreHP` holds 5,668 Rests. Grouping
the raw stream by `selected_goal` would report XP per FIGHT and call it XP per
loop action — about 2.4x too high, a defect this branch has had before at ~29x.

`LearningStore.recent_goal_cycles` already attributes forced recovery to the goal
that caused it (`store.py:575`). This census consumes the slices it returns, so
the attribution rule has exactly one implementation and this is not it.

A cycle whose `actual_cooldown_seconds` is None is EXCLUDED. The server did not
report a cooldown for it, and denominating a rate on a fabricated zero produces
an infinite rate — the census would then rank an unmeasured goal first.
"""

import json
from dataclasses import dataclass, field

from artifactsmmo_cli.ai.learning.models import Cycle


@dataclass(frozen=True)
class GoalRates:
    """One goal's measured totals over the window, and the rates derived from them."""

    goal: str
    cycles: int
    seconds: float
    char_xp: int
    skill_xp: dict[str, int] = field(default_factory=dict)
    gold: int = 0

    @property
    def char_xp_per_second(self) -> float:
        """Character XP per second. `seconds` is positive by construction: a
        goal with no measured cycle never becomes a row."""
        return self.char_xp / self.seconds

    @property
    def skill_xp_per_second(self) -> float:
        """All skill XP per second, summed across skills. Under the character
        leaderboard's `total_xp` ruler one point of skill XP and one point of
        character XP weigh the same, so they are summed, not weighted."""
        return sum(self.skill_xp.values()) / self.seconds

    @property
    def gold_per_second(self) -> float:
        """Gold per second. Carried because `cycles` already records it and the
        frontier needs a third axis to be a frontier rather than a line."""
        return self.gold / self.seconds


def currency_rates(cycles_by_goal: dict[str, list[Cycle]]) -> list[GoalRates]:
    """Per-goal currency totals, ordered by character XP per second, descending.

    Each value is the slice `LearningStore.recent_goal_cycles` returned for that
    goal — already carrying the recovery cycles the goal's own fighting forced.
    A goal whose every cycle lacks a measured cooldown is DROPPED, not reported
    as zero: "not measured" and "measured as nothing" are different findings.
    """
    rows: list[GoalRates] = []
    for goal, cycles in cycles_by_goal.items():
        measured = [c for c in cycles if c.actual_cooldown_seconds is not None]
        seconds = sum(c.actual_cooldown_seconds or 0.0 for c in measured)
        if seconds <= 0.0:
            continue
        skill_xp: dict[str, int] = {}
        for cycle in measured:
            for skill, gained in json.loads(cycle.delta_skill_xp_json).items():
                skill_xp[skill] = skill_xp.get(skill, 0) + gained
        rows.append(GoalRates(
            goal=goal,
            cycles=len(measured),
            seconds=seconds,
            char_xp=sum(c.delta_xp or 0 for c in measured),
            skill_xp=skill_xp,
            gold=sum(c.delta_gold or 0 for c in measured),
        ))
    rows.sort(key=lambda r: r.char_xp_per_second, reverse=True)
    return rows
