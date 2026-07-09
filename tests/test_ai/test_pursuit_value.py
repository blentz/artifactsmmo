"""Calibration pins for pursuit_value — the combat-dominant efficiency-budget
scorer that replaces flat equip_value on the tree's gear-pursuit path.

These are the bug-gone proof (a weapon must outrank a prospecting artifact
cross-slot) and the no-regression guarantees (utility gear still pursued, still
ordered by efficiency). Each pin also asserts equip_value gets the cross-slot
comparison WRONG, so the fix is non-vacuous.
"""
from artifactsmmo_cli.ai.game_data import ItemStats
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.pursuit_value import (
    EFFICIENCY_BUDGET,
    PURSUIT_WEIGHTS,
    pursuit_value,
)
from artifactsmmo_cli.ai.tiers.strategic_value import STRATEGIC_SCALE


def _weapon(combat_raw: int) -> ItemStats:
    """A pure-combat weapon whose combat_raw is `combat_raw` (all attack)."""
    return ItemStats(code="wpn", level=2, type_="weapon", attack={"earth": combat_raw})


def _artifact(prospecting: int) -> ItemStats:
    """A pure-utility prospecting artifact (combat_raw 0)."""
    return ItemStats(code="art", level=2, type_="artifact", prospecting=prospecting)


def _bag(inventory_space: int) -> ItemStats:
    return ItemStats(code="bag", level=2, type_="bag", inventory_space=inventory_space)


def test_budget_constants():
    """One combat_raw point (× SCALE) must strictly exceed the whole capped
    efficiency block, so combat dominance is structural."""
    assert PURSUIT_WEIGHTS == (STRATEGIC_SCALE, 1, 1, 1, 1)
    assert EFFICIENCY_BUDGET == STRATEGIC_SCALE - 1
    assert EFFICIENCY_BUDGET < STRATEGIC_SCALE  # combat_raw==1 beats any efficiency


def test_weapon_outranks_prospecting_artifact_pursuit():
    """THE bug-gone pin. combat_raw 30 weapon vs prospecting-201 artifact:
    pursuit_value(weapon) = 30*1000 = 30000; pursuit_value(artifact) =
    min(201, 999) = 201. Weapon wins cross-slot."""
    weapon = _weapon(30)
    artifact = _artifact(201)
    assert pursuit_value(weapon) == 30 * STRATEGIC_SCALE
    assert pursuit_value(artifact) == 201
    assert pursuit_value(weapon) > pursuit_value(artifact)


def test_equip_value_gets_cross_slot_backwards():
    """Non-vacuity: the OLD flat scorer ranked the artifact ABOVE the weapon.
    equip_value(weapon) = 2*30 + 1(nonTool) = 61;
    equip_value(artifact) = 2*201 + 1 = 403. Artifact wrongly wins."""
    weapon = _weapon(30)
    artifact = _artifact(201)
    assert equip_value(weapon) == 61
    assert equip_value(artifact) == 403
    assert equip_value(artifact) > equip_value(weapon)  # the bug


def test_bag_still_pursued_no_regression():
    """A bag (inventory_space > 0, combat_raw 0) keeps a positive pursuit_value
    so the tree still pursues it — the bug was utility outranking COMBAT, never
    utility being dropped. 20 slots → min(20, 999) = 20."""
    bag = _bag(20)
    assert pursuit_value(bag) == 20
    assert pursuit_value(bag) > 0


def test_two_artifacts_order_by_efficiency():
    """Within the efficiency block (both under the 999 cap), a bigger
    prospecting artifact outranks a smaller one — utility slots stay ordered."""
    small = _artifact(50)
    big = _artifact(100)
    assert pursuit_value(big) == 100
    assert pursuit_value(small) == 50
    assert pursuit_value(big) > pursuit_value(small)


def test_combat_beats_any_efficiency_magnitude():
    """Structural dominance via the budget: a 1-combat-point item beats an
    all-efficiency item no matter how large its efficiency stats — the block is
    capped at 999 < 1000."""
    minimal_combat = _weapon(1)
    huge_efficiency = _artifact(1_000_000)
    assert pursuit_value(minimal_combat) == STRATEGIC_SCALE  # 1000
    assert pursuit_value(huge_efficiency) == EFFICIENCY_BUDGET  # 999 (capped)
    assert pursuit_value(minimal_combat) > pursuit_value(huge_efficiency)


def test_efficiency_block_caps_at_budget():
    """The summed efficiency block is capped, not per-stat: wisdom + prospecting
    + inventory + haste = 400+400+400+400 = 1600 → capped to 999."""
    stats = ItemStats(code="mega", level=2, type_="artifact",
                      wisdom=400, prospecting=400, inventory_space=400, haste=400)
    assert pursuit_value(stats) == EFFICIENCY_BUDGET
