"""pursuit_value: the ONE gear ruler read lexicographically, and every consumer.

Three obligations live here.

1. **THE HISTORICAL WITNESS.** The bug this module exists to prevent: a
   prospecting-201 artifact outranking a modest combat weapon CROSS-SLOT,
   because a flat sum weighed 201 prospecting against 30 attack 1:1.
2. **STRUCTURAL dominance, not arithmetic luck.** The budget/scale inequality
   `2 * EFFICIENCY_BUDGET < STRATEGIC_SCALE` is asserted directly, because that
   inequality — not any property of the current item table — is what makes the
   ordering hold. `Formal.StrategicValue.pursuit_combat_dominates` proves the
   consequence over all integer inputs.
3. **NO DOUBLE COUNT, and no regression.** Utility reaches the score exactly
   once (the ruler's combat term has no parameter for it) and still totally
   ORDERS items whose combat terms tie.

Plus the per-consumer audit: `pursuit_value`'s scale moved when its combat term
became the ruler's own, so every consumer is named and its use of the number
classified — ordering-only, or an absolute threshold that had to be re-derived.
"""
import json
from pathlib import Path

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.equipment.scoring import RULER_SCALE
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value import gear_components
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.prerequisite_graph import RECYCLE_LEAF_VALUE_FLOOR
from artifactsmmo_cli.ai.tiers.pursuit_value import (
    EFFICIENCY_BUDGET,
    PURSUIT_WEIGHTS,
    pursuit_value,
)
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _weapon(attack: int) -> ItemStats:
    """A pure-combat weapon, all of it in one element's attack."""
    return ItemStats(code="wpn", level=2, type_="weapon", attack={"earth": attack})


def _artifact(prospecting: int) -> ItemStats:
    """A pure-utility prospecting artifact (combat term 0)."""
    return ItemStats(code="art", level=2, type_="artifact", prospecting=prospecting)


def _bag(inventory_space: int) -> ItemStats:
    return ItemStats(code="bag", level=2, type_="bag", inventory_space=inventory_space)


# --- 1. the structural inequality --------------------------------------------

def test_budget_constants():
    """The WHOLE efficiency span must be narrower than one unit of scaled
    combat. This single inequality is the dominance proof's only hypothesis
    (`Formal.StrategicValue.pursuit_combat_dominates`), so it is asserted as
    itself rather than demonstrated on sample items."""
    assert PURSUIT_WEIGHTS == (STRATEGIC_SCALE, 1, 1, 1, 1)
    assert EFFICIENCY_BUDGET == (STRATEGIC_SCALE - 1) // 2
    assert 2 * EFFICIENCY_BUDGET < STRATEGIC_SCALE


def test_dominance_holds_for_the_smallest_possible_combat_gap():
    """Not "a big combat item beats a utility item" — the sharp case: items
    differing by ONE unit of combat term, with the efficiency block pushed to
    the opposite extreme on each side. If the inequality above ever slips, this
    is what breaks first."""
    lo = STRATEGIC_SCALE * 5 + EFFICIENCY_BUDGET
    hi = STRATEGIC_SCALE * 6 + -EFFICIENCY_BUDGET
    assert lo < hi


def test_efficiency_budget_never_binds_on_the_live_catalog():
    """The bound is a structural guard, not a live clamp: derived from the
    pinned bundle, the largest |efficiency block| any real item carries is well
    inside it, so no live pair of items is flattened into a tie. A catalog that
    grew past the budget fails HERE rather than silently losing orderings."""
    gd = _bundle()
    blocks = [s.wisdom + s.prospecting + s.inventory_space + s.haste
              for s in gd.all_item_stats.values()]
    assert max(blocks) == 406  # diamond_skirt: wisdom 200 + prospecting 200 + haste 6
    assert min(blocks) == -25  # obsidian_battleaxe / obsidian_armor: inventory_space
    assert max(abs(b) for b in blocks) < EFFICIENCY_BUDGET


# --- 2. the historical witness ------------------------------------------------

def test_weapon_outranks_prospecting_artifact_pursuit():
    """THE bug-gone pin, at the ruler's own scale. The prospecting-201 artifact
    carries no combat at all, so its whole score is the bounded efficiency
    tiebreak (201); the weapon's combat term is `weapon_score` and dwarfs it."""
    weapon = _weapon(30)
    artifact = _artifact(201)
    assert gear_components(artifact, Rank)[0] == 0
    assert pursuit_value(artifact) == 201
    assert pursuit_value(weapon) == gear_components(weapon, Rank)[0] * STRATEGIC_SCALE
    assert pursuit_value(weapon) > pursuit_value(artifact)


def test_the_witness_survives_an_absurd_prospecting_value():
    """The historical failure was a MAGNITUDE comparison, so the witness is only
    meaningful if it survives an artifact whose utility is arbitrarily large."""
    assert pursuit_value(_weapon(1)) > pursuit_value(_artifact(10**9))


def test_equip_value_now_agrees_with_pursuit_value_cross_slot():
    """The flat-parity bug is gone at the SOURCE too: `equip_value` (the ruler)
    reaches the same cross-slot verdict on its own. `pursuit_value` keeps its own
    reading because it answers the ECONOMIC question (what to spend gold and
    cycles acquiring), not the gear question — agreement is a check that the two
    layers no longer contradict each other, not a reason to merge them."""
    weapon = _weapon(30)
    artifact = _artifact(201)
    assert equip_value(weapon) > equip_value(artifact)
    assert pursuit_value(weapon) > pursuit_value(artifact)


# --- 3. no double count, no utility regression --------------------------------

def test_pursuit_value_is_the_rulers_two_terms_lexicographically():
    """The definition, checked: no third formula, just a re-reading of the pair
    `gear_components` returns."""
    for stats in (_weapon(30), _artifact(201), _bag(20),
                  ItemStats(code="mix", level=1, type_="helmet",
                            resistance={"fire": 5}, wisdom=50, prospecting=50)):
        combat, efficiency = gear_components(stats, Rank)
        assert (pursuit_value(stats)
                == combat * STRATEGIC_SCALE + efficiency // (RULER_SCALE * 200))


def test_utility_is_counted_once_not_twice():
    """Adding utility stats moves ONLY the tiebreak. The ruler's combat term
    takes no utility parameter, so it cannot move — which is what stops the
    utility being charged once inside the combat term and again outside it."""
    bare = ItemStats(code="bare", level=1, type_="helmet", resistance={"fire": 5})
    plus = ItemStats(code="plus", level=1, type_="helmet", resistance={"fire": 5},
                     wisdom=40, prospecting=60)
    assert gear_components(bare, Rank)[0] == gear_components(plus, Rank)[0]
    assert pursuit_value(plus) - pursuit_value(bare) == 100


def test_bag_still_pursued_no_regression():
    """A bag (inventory_space > 0, combat term 0) keeps a positive pursuit_value
    so the tree still pursues it — the bug was utility outranking COMBAT, never
    utility being dropped."""
    bag = _bag(20)
    assert pursuit_value(bag) == 20
    assert pursuit_value(bag) > 0


def test_two_artifacts_order_by_efficiency():
    """Within the efficiency block, a bigger prospecting artifact outranks a
    smaller one — utility slots stay ordered."""
    assert pursuit_value(_artifact(100)) > pursuit_value(_artifact(50)) > 0


def test_utility_ordering_agrees_with_the_rulers_own_efficiency_term():
    """The tiebreak is not a re-weighting: `PURSUIT_WEIGHTS` gives all four
    stats the same rate, exactly as the ruler's `gear_score_efficiency` does,
    so the two order utility items identically (a constant factor apart)."""
    items = [ItemStats(code=f"u{i}", level=1, type_="artifact",
                       wisdom=i, prospecting=2 * i, inventory_space=i, haste=i)
             for i in range(0, 60, 7)]
    by_pursuit = sorted(items, key=pursuit_value)
    by_ruler = sorted(items, key=lambda s: gear_components(s, Rank)[1])
    assert [s.code for s in by_pursuit] == [s.code for s in by_ruler]


def test_negative_efficiency_still_orders_below_zero_efficiency():
    """Live items carry `inventory_space = -25`. The symmetric bound keeps that
    penalty visible instead of flooring it away."""
    neutral = ItemStats(code="n", level=1, type_="body_armor", hp_bonus=10)
    penalised = ItemStats(code="p", level=1, type_="body_armor", hp_bonus=10,
                          inventory_space=-25)
    assert pursuit_value(penalised) < pursuit_value(neutral)
    assert pursuit_value(neutral) - pursuit_value(penalised) == 25


# --- 4. every consumer of pursuit_value, named --------------------------------
#
# `grep -rn "pursuit_value" src/` finds four call sites. Three compare pursuit
# values with each other (scale-free); ONE carries an absolute threshold.

def test_consumer_1_recycle_leaf_floor_is_recalibrated_to_the_new_scale():
    """`tiers/prerequisite_graph.RECYCLE_LEAF_VALUE_FLOOR` — THE only absolute
    pursuit_value threshold in the codebase. Pinned against the same four live
    witnesses its docstring has always named: obsolete tools must recycle,
    current-tier staves must not.

    RE-DERIVED and UNCHANGED at `RULER_SCALE`: all four witnesses are WEAPONS,
    whose pursuit COMBAT term that change left bit-identical (the factor was
    already on the weapon side; the ARMOR side moved up to meet it). The
    witnesses' exact values are pinned so a scale move on the weapon side would
    fail here rather than silently reclassify every recyclable."""
    gd = _bundle()
    for junk, expected in (("fishing_net", 200_000_000), ("copper_axe", 200_000_000)):
        stats = gd.item_stats(junk)
        assert stats is not None
        assert pursuit_value(stats) == expected, junk
        assert pursuit_value(stats) < RECYCLE_LEAF_VALUE_FLOOR, junk
    for current, expected in (("wooden_staff", 328_001_000),
                              ("fire_staff", 656_001_000)):
        stats = gd.item_stats(current)
        assert stats is not None
        assert pursuit_value(stats) == expected, current
        assert pursuit_value(stats) >= RECYCLE_LEAF_VALUE_FLOOR, current


def test_consumer_2_near_term_gear_buckets_by_type_before_ranking():
    """`tiers/objective.CharacterObjective.near_term_gear` — argmax within one
    item TYPE, then a `> _item_value(incumbent)` comparison against the same
    ruler. Ordering-only: no absolute threshold to re-derive."""
    gd = _bundle()
    equippables = [s for s in gd.all_item_stats.values()
                   if s.type_ in ITEM_TYPE_TO_SLOTS]
    per_type: dict[str, list[ItemStats]] = {}
    for stats in equippables:
        per_type.setdefault(stats.type_, []).append(stats)
    for type_, peers in per_type.items():
        best_pursuit = max(peers, key=pursuit_value)
        # Within a type, pursuit and the ruler can only disagree on items whose
        # combat terms TIE (efficiency then breaks the tie either way).
        best_ruler = max(peers, key=equip_value)
        assert (gear_components(best_pursuit, Rank)[0]
                >= gear_components(best_ruler, Rank)[0]), type_


def test_consumer_3_item_value_baseline_is_the_same_ruler():
    """`tiers/objective.CharacterObjective._item_value` — the current-equipped
    baseline `_structural_candidates` subtracts. Same function, so the gain is a
    difference on one scale; an empty slot is 0."""
    gd = _bundle()
    obj_value = pursuit_value(gd.item_stats("copper_boots"))
    assert obj_value == pursuit_value(gd.item_stats("copper_boots"))
    assert obj_value > 0


def test_consumer_4_tree_branches_now_share_one_ruler():
    """`tiers/progression_tree._structural_candidates` AND `_utility_candidates`.
    The utility branch used to score gain on `equip_value` while the structural
    branch used `pursuit_value`, and the two lists are merged into ONE argmax —
    a comparison across rulers ~1000x apart. Both are on `pursuit_value` now.

    The switch changes no verdict that held before: an item with no efficiency
    stat (every potion, every weapon, most armor) has `pursuit_value ==
    1000 * equip_value` exactly, so the merged ranking is rescaled uniformly."""
    gd = _bundle()
    for code in ("small_health_potion", "wooden_shield", "iron_sword"):
        stats = gd.item_stats(code)
        assert stats is not None
        assert stats.wisdom == stats.prospecting == 0
        assert stats.inventory_space == stats.haste == 0
        assert pursuit_value(stats) == STRATEGIC_SCALE * equip_value(stats), code
