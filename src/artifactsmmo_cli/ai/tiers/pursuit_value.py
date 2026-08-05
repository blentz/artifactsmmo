"""pursuit_value: the ONE gear ruler read LEXICOGRAPHICALLY for acquisition.

The progression tree ranks cross-slot gear candidates by GAIN. Ranking on a
flat stat sum let a pure-utility item outrank a combat weapon CROSS-SLOT: a
prospecting-201 artifact scored 403 while a combat weapon scored 61, so the
tree chased the artifact over the weapon (the flat-parity cross-slot bug).
``pursuit_value`` fixes this WITHOUT zeroing utility.

ONE ALGORITHM. It computes no score of its own. ``gear_components(stats, Rank)``
partitions the single gear ruler ``gear_value(stats, Rank)`` into its COMBAT
term and its EFFICIENCY term (``combat + efficiency == gear_value``, exactly,
for every item), and ``pursuit_value`` reads that pair LEXICOGRAPHICALLY —
combat first, efficiency as the tiebreak::

    pursuit_value(stats) = combat * STRATEGIC_SCALE + clamp(efficiency_block)

Utility therefore enters ONCE. The ruler's combat term literally cannot contain
it: ``equipment/scoring.armor_score_combat_pure`` has no wisdom / prospecting /
inventory_space / haste parameter to pass it through.

WHY LEXICOGRAPHIC IS STRUCTURAL. With ``|clamp(e)| <= EFFICIENCY_BUDGET`` and
``2 * EFFICIENCY_BUDGET < STRATEGIC_SCALE``, the whole efficiency range spans
strictly less than one unit of scaled combat. So for integer combat terms
``c_a > c_b``::

    pursuit(a) - pursuit(b) = SCALE*(c_a - c_b) + (e_a - e_b)
                           >= SCALE - 2*EFFICIENCY_BUDGET  >= 1  > 0

No efficiency stats of any magnitude can reverse a combat difference of even
one unit. That is a fact about the arithmetic for ALL integer inputs — it does
not depend on what today's catalog happens to contain. Conversely, items whose
combat terms TIE are ordered entirely by efficiency, so bags / runes / artifacts
and every other utility slot keep a total ranking (no regression: the earlier
failure mode was utility outranking COMBAT, never utility being dropped).

WHAT CHANGED, AND WHY IT HAD TO. The combat term used to be ``combat_raw``, a
flat 8-stat sum (attack + resistance + hp_restore + hp_bonus + dmg +
critical_strike + lifesteal + combat_buff) defined ALONGSIDE the ruler. It added
a resistance PERCENTAGE to an HP amount to a damage figure 1:1 — the exact
category error the Rank/Combat unification had just removed from the gear ruler,
surviving one layer up. On the ruler's own term, one point of per-element
resistance is worth 33 ``hp_restore`` (the canonical duel's exchange rate), not
one. ``combat_raw`` is deleted, not merely bypassed.

SCALE. For an item with no efficiency stats — which is every weapon, every
potion and most armor — ``pursuit_value == 1000 * equip_value`` exactly, so the
verdicts this ruler reached before the combat term changed are preserved
wherever it is compared against ``equip_value``-derived quantities. One absolute
threshold consumes the magnitude (``prerequisite_graph.RECYCLE_LEAF_VALUE_FLOOR``)
and it is re-derived from the same catalog witnesses; every other consumer
compares pursuit values with each other. See
``tests/test_ai/test_pursuit_value.py`` for the named per-consumer audit.
"""

from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE, strategic_value

# The four efficiency stats (wisdom, prospecting, inventory_space, haste) each
# carry the derived openapi rate (0.001 * SCALE = 1 unit) — the same rate
# strategic_value derives for wisdom/prospecting. inventory_space/haste have no
# commensurated rate yet, so they share the conservative 1-unit weight (NOT the
# SCALE-parity hold DEFAULT_STRATEGIC_WEIGHTS keeps for them, which would weight
# a bag like a weapon and re-introduce the cross-slot bug). Equal weights also
# make this block ORDER-IDENTICAL to the ruler's own efficiency term, which is
# `200 * (wisdom + prospecting + inventory_space + haste)`: same four stats,
# same relative weights, 200x apart. These weights only control ORDERING inside
# the bounded block; cross-slot dominance is the budget's job.
_EFFICIENCY_RATE = 1

# (combat, wisdom, prospecting, inventory, haste) in 1/STRATEGIC_SCALE units.
PURSUIT_WEIGHTS: tuple[int, int, int, int, int] = (
    STRATEGIC_SCALE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
    _EFFICIENCY_RATE,
)

# The efficiency block is bounded to [-EFFICIENCY_BUDGET, +EFFICIENCY_BUDGET],
# so its SPAN is 2*EFFICIENCY_BUDGET = 998 < 1000 = one unit of scaled combat.
# That inequality — not any property of the current item table — is what makes
# combat dominance structural; `test_pursuit_value.py` asserts it directly.
#
# SYMMETRIC because efficiency stats are genuinely negative on live items
# (obsidian_battleaxe inventory_space -25). Bounding only above would leave the
# span unbounded below and the embedding would not be an embedding.
#
# The bound never BINDS on the live catalog: the largest |efficiency block| over
# all 522 items is 406 (diamond_skirt: wisdom 200 + prospecting 200 + haste 6),
# comfortably inside 499, so no real pair of items is flattened into a tie by
# it. `test_pursuit_value.py` re-derives that headroom from the pinned bundle,
# so a catalog that grew past the budget would fail the suite rather than
# silently start losing utility orderings.
EFFICIENCY_BUDGET = (STRATEGIC_SCALE - 1) // 2


def pursuit_value(stats: ItemStats) -> int:
    """Combat-dominant cross-slot pursuit value of an equippable (the tree's
    gear branch and the objective's per-slot pick).

    ``= strategic_value(stats, PURSUIT_WEIGHTS, efficiency_budget=
    EFFICIENCY_BUDGET)`` = ``gear_components(stats, Rank)[0] * 1000 +
    clamp(wisdom + prospecting + inventory_space + haste, ±499)`` — the one gear
    ruler's own two terms, read lexicographically. See the module docstring."""
    return strategic_value(stats, PURSUIT_WEIGHTS, efficiency_budget=EFFICIENCY_BUDGET)
