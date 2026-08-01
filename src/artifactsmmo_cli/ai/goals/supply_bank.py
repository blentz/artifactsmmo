"""Produce a material a SIBLING needs and bank it.

This is the goal that turns the demand board into actual production. Without
it, bank-first sourcing changes nothing: each character gathers exactly what
its own plan demands, crafts it, and leaves the bank empty, so a consumer
preferring WITHDRAW still finds nothing there.

`desired_state` targets BANKED quantity, not held quantity — the distinction
that keeps sibling demand from being consumed by the producer's own craft. That
separation is the whole reason this is a distinct goal rather than an inflation
of the character's own closure demand.

Priority is the clamped demand lift, the same construction `scalar_priority`
and `grind_character_xp` use: the band ceiling sits below the survival floor of
70, so a supply goal can NEVER outrank a survival guard by construction rather
than by tuning.
"""

from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.priority_band import clamp_into_band
from artifactsmmo_cli.ai.world_state import WorldState

SUPPLY_PRIORITY_FLOOR = 30.0
"""Minimum priority when active. Matches GrindCharacterXpGoal's floor so a
zero-demand supply goal never outranks ordinary progression."""

SUPPLY_PRIORITY_CEILING = 50.0
"""Upper bound. Stays under ReachSkillGoal (55) and the survival floor (70).
Deliberately overlaps GrindCharacterXpGoal's [30, 45] band so heavy sibling
demand CAN outrank marginal char-xp grinding, but never a skill gate."""

SUPPLY_DEMAND_GAIN = 1.0
"""Priority points per unit of unmet sibling demand."""


class SupplyBankGoal(Goal):
    """Bank `quantity` of `item_code` for the siblings that asked for it."""

    # Exempt from the doomed-memo (Goal.memo_exempt): this goal's plannability
    # and satisfaction both hinge on dimensions the memo's (char level, skill
    # levels) signature cannot see. `is_satisfied` reads bank CONTENTS
    # directly, and the memo key is `repr(goal)` — `SupplyBank({item_code}x
    # {quantity})` — which does NOT include `demand`, so two constructions for
    # the SAME item/quantity but DIFFERENT (rising) sibling demand collide on
    # one memo entry. A transient no-plan (e.g. the gather/craft chain briefly
    # unreachable — missing ingredient, cooldown, bank full) would then be
    # memoized as doomed under the unchanged (level, skills) signature and
    # suppress this means for up to 160 cycles, even after a sibling's demand
    # spikes or the blocking material lands in the bank from ANOTHER
    # character's cycle — neither of which bumps the signature. This is the
    # same class of problem GrindCharacterXPGoal solved (HP/inventory churn
    # invisible to the signature); see Goal.memo_exempt.
    memo_exempt = True

    def __init__(self, item_code: str, quantity: int, demand: int) -> None:
        self._item_code = item_code
        self._quantity = quantity
        self._demand = demand

    def __repr__(self) -> str:
        return f"SupplyBank({self._item_code}x{self._quantity})"

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        bonus = Fraction(self._demand) * Fraction(SUPPLY_DEMAND_GAIN)
        clamped = clamp_into_band(Fraction(SUPPLY_PRIORITY_FLOOR),
                                  Fraction(SUPPLY_PRIORITY_CEILING), bonus)
        return float(clamped)

    def is_satisfied(self, state: WorldState) -> bool:
        bank = state.bank_items
        if bank is None:
            return False
        return bank.get(self._item_code, 0) >= self._quantity

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"banked": {self._item_code: self._quantity}}
