"""Pure core: a combat target's XP per action, counting its upkeep.

USER 2026-10-07: the band target ranks by XP per action, full upkeep. It used to
rank by XP per KILL, so a monster that costs potions and rest every fight looked
as cheap as one that costs nothing. Live, Lor's death_knight grind spent 46% of
5.8h gathering sunflowers for the ~3 small_health_potion each fight used, 40%
resting and 11% fighting.

    key = xp_per_kill / (actions_per_kill + sum(qty_per_kill(c) * price(c)))

`actions_per_kill` is every cycle the grind spent per kill — the fight, the
moves, and the recovery its fighting forced (`LearningStore.recent_goal_cycles`
attributes those). The consumables a fight used are priced at their
acquisition actions per unit. A monster with no measured upkeep counts one
action and no consumables per kill, so it is tried and then measured.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class FightUpkeep:
    """What one kill of a monster has cost, measured."""

    actions_per_kill: Fraction
    consumed_per_kill: Mapping[str, Fraction]


NO_UPKEEP = FightUpkeep(actions_per_kill=Fraction(1), consumed_per_kill={})


def xp_per_action(xp_per_kill: int, upkeep: FightUpkeep,
                  price_of: Callable[[str], Fraction]) -> Fraction:
    """XP per action of farming a monster, upkeep included."""
    actions = upkeep.actions_per_kill + sum(
        (qty * price_of(code) for code, qty in upkeep.consumed_per_kill.items()),
        Fraction(0))
    return Fraction(xp_per_kill) / actions
