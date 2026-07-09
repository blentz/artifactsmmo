"""pursuit_value: combat-dominant strategic score for the tree's gear pursuit.

The progression tree ranks cross-slot gear candidates by GAIN. Ranking on the
flat ``equip_value`` (``2 * (combat_raw + wisdom + prospecting +
inventory_space + haste) + nonToolBonus``) let a pure-utility item outrank a
combat weapon CROSS-SLOT: a prospecting-201 artifact scored equip_value 403
while a combat_raw-30 weapon scored 61, so the tree chased the artifact over the
weapon (the flat-parity cross-slot bug). ``pursuit_value`` fixes this WITHOUT
zeroing utility: it is ``strategic_value`` with a combat-dominant efficiency
budget.

combat_raw carries the DOMINANT weight ``STRATEGIC_SCALE`` (=1000); the four
efficiency stats carry a small derived per-point rate and their weighted block
is CAPPED at ``EFFICIENCY_BUDGET = STRATEGIC_SCALE - 1`` (=999). Because the
capped efficiency block (<=999) is strictly below one combat_raw point (1000),
any item with ``combat_raw >= 1`` outranks any all-efficiency item cross-slot
(structural dominance), while efficiency still ORDERS gear among
efficiency-bearing / empty utility slots — no bag/rune/artifact regression:
their pursuit_value stays > 0 and orders by efficiency magnitude.

Nonnegativity and combat dominance are structural facts of the proved
``strategic_value`` core (Formal/StrategicValue.lean: nonneg weighted sum) plus
the budget-cap policy documented in ``strategic_value``'s docstring;
``pursuit_value`` is a thin pin of that core's parameters, so it needs no
separate theorem — a witness would restate ``strategicValue``'s nonneg lemma
verbatim (see Task-3 report §Lean).
"""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE, strategic_value

# The four efficiency stats (wisdom, prospecting, inventory_space, haste) each
# carry the derived openapi rate (0.001 * SCALE = 1 unit) — the same rate
# strategic_value derives for wisdom/prospecting. inventory_space/haste have no
# commensurated rate yet, so they share the conservative 1-unit weight (NOT the
# SCALE-parity hold DEFAULT_STRATEGIC_WEIGHTS keeps for them, which would weight
# a bag like a weapon and re-introduce the cross-slot bug). These weights only
# control ORDERING inside the capped block; cross-slot dominance is the budget's
# job, so the exact rate matters only for utility-vs-utility comparisons.
_EFFICIENCY_RATE = 1

# (combat, wisdom, prospecting, inventory, haste) in 1/STRATEGIC_SCALE units.
PURSUIT_WEIGHTS: tuple[int, int, int, int, int] = (
    STRATEGIC_SCALE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
)

# One combat_raw point (× STRATEGIC_SCALE = 1000) must outrank the ENTIRE
# efficiency block. Capping the block at SCALE - 1 (=999) guarantees
# combat_raw >= 1  =>  pursuit_value >= 1000 > 999 >= any all-efficiency item.
EFFICIENCY_BUDGET = STRATEGIC_SCALE - 1


def pursuit_value(stats: ItemStats) -> int:
    """Combat-dominant cross-slot pursuit value of an equippable (the tree's
    gear branch). ``= strategic_value(stats, PURSUIT_WEIGHTS,
    efficiency_budget=EFFICIENCY_BUDGET)`` = ``combat_raw * 1000 +
    min(efficiency_block, 999)``. Nonneg (proved core) and combat-dominant
    (budget < combat weight): any combat item beats any all-efficiency item
    cross-slot, while utility still orders utility slots."""
    return strategic_value(stats, PURSUIT_WEIGHTS, efficiency_budget=EFFICIENCY_BUDGET)
