from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import (
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    owned_count,
)
from artifactsmmo_cli.ai.tiers.owned_count import owned_count_pure
from tests.test_ai.fixtures import make_state

GD = GameData()


def test_reach_char_level_satisfaction():
    assert ReachCharLevel(10).is_satisfied(make_state(level=10), GD) is True
    assert ReachCharLevel(10).is_satisfied(make_state(level=9), GD) is False


def test_reach_skill_level_satisfaction():
    s = make_state(skills={"mining": 5})
    assert ReachSkillLevel("mining", 5).is_satisfied(s, GD) is True
    assert ReachSkillLevel("mining", 6).is_satisfied(s, GD) is False
    # default skill level is 1 when absent
    assert ReachSkillLevel("cooking", 2).is_satisfied(s, GD) is False
    assert ReachSkillLevel("cooking", 1).is_satisfied(s, GD) is True


def test_owned_count_inventory_bank_equipped():
    s = make_state(inventory={"copper_ore": 3}, bank_items={"copper_ore": 4},
                   equipment={"weapon_slot": "copper_dagger"})
    assert owned_count(s, "copper_ore") == 7
    assert owned_count(s, "copper_dagger") == 1   # equipped counts as 1
    assert owned_count(s, "absent") == 0


def test_owned_count_without_bank_visited():
    # bank_items None (bank not yet visited) ⇒ bank branch contributes nothing.
    s = make_state(inventory={"copper_ore": 2}, bank_items=None,
                   equipment={"weapon_slot": "copper_dagger"})
    assert owned_count(s, "copper_ore") == 2
    assert owned_count(s, "copper_dagger") == 1


def test_owned_count_pure_disjointness_no_double_count():
    # The API/model invariant: an equipped code is NOT also in inventory, so the
    # equipped +1 never double-counts. Mirror it directly on the pure core.
    assert owned_count_pure({"copper_ore": 5}, {"copper_ore": 2},
                            ["copper_dagger"], "copper_dagger") == 1
    assert owned_count_pure({"copper_ore": 5}, None, [], "copper_ore") == 5


def test_obtain_item_satisfaction_against_quantity():
    s = make_state(inventory={"copper_ore": 3}, bank_items={"copper_ore": 4})
    assert ObtainItem("copper_ore", 7).is_satisfied(s, GD) is True
    assert ObtainItem("copper_ore", 8).is_satisfied(s, GD) is False
    assert ObtainItem("copper_ore").is_satisfied(s, GD) is True  # default qty 1


def test_nodes_are_hashable():
    # frozen dataclasses → usable in visited-sets during P3 traversal
    assert {ReachCharLevel(5), ReachSkillLevel("mining", 3), ObtainItem("x", 2)}
    assert ObtainItem("x", 2) == ObtainItem("x", 2)


def test_obtain_item_resource_satisfied_when_owned():
    """Non-equippable items (resources) are satisfied by owned_count alone —
    the legacy semantic for crafting-input goals."""
    gd = GameData()
    gd._item_stats = {"ash_wood": ItemStats(code="ash_wood", level=1, type_="resource")}
    state = make_state(inventory={"ash_wood": 6})
    assert ObtainItem("ash_wood", 6).is_satisfied(state, gd) is True
    assert ObtainItem("ash_wood", 7).is_satisfied(state, gd) is False


def test_obtain_item_equippable_requires_equipped_not_owned():
    """Trace 2026-06-05T03:37: Robby crafted wooden_shield, owned_count went
    to 1, ObtainItem(wooden_shield).is_satisfied returned True, the meta-
    objective root dropped, and the shield sat in inventory forever
    without ever equipping. For equippable types (anything with an
    ITEM_TYPE_TO_SLOTS entry), satisfaction must REQUIRE the item to be
    in an equipment slot — owning a spare doesn't count."""
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield"),
    }
    # Owned but NOT equipped → NOT satisfied (the bug we're closing).
    state_owned = make_state(inventory={"wooden_shield": 1}, equipment={"shield_slot": None})
    assert ObtainItem("wooden_shield").is_satisfied(state_owned, gd) is False
    # Equipped → satisfied.
    state_equipped = make_state(inventory={}, equipment={"shield_slot": "wooden_shield"})
    assert ObtainItem("wooden_shield").is_satisfied(state_equipped, gd) is True
    # Owned AND equipped (spare in bag) → satisfied (equipped occupies the slot).
    state_both = make_state(inventory={"wooden_shield": 1},
                            equipment={"shield_slot": "wooden_shield"})
    assert ObtainItem("wooden_shield").is_satisfied(state_both, gd) is True


def test_obtain_item_tool_satisfied_when_owned_not_required_equipped():
    """Trace 2026-06-06 session 01:24-04:57 (278 cycles, 0 fights): Robby
    owned copper_pickaxe + copper_axe (mining/woodcutting tools) but wore
    fishing_net. ObtainItem(copper_pickaxe) was unsatisfied (slot != code)
    → ranked #1 → step short-circuited → bootstrap ReachCharLevel(5) never
    reached → discretionary PursueTask ran forever. Tools (subtype='tool')
    ROTATE through weapon_slot per the active gathering task — owning the
    tool IS the goal; OptimizeLoadout owns the per-fight slot. Distinct
    from real gear (wooden_shield etc.) which still requires equip."""
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(
            code="copper_pickaxe", level=1, type_="weapon", subtype="tool",
            skill_effects={"mining": -10},
        ),
    }
    # Tool owned, weapon_slot holds a combat weapon → STILL satisfied.
    state_owned = make_state(
        inventory={"copper_pickaxe": 1},
        equipment={"weapon_slot": "copper_dagger"},
    )
    assert ObtainItem("copper_pickaxe").is_satisfied(state_owned, gd) is True
    # Not owned anywhere → not satisfied.
    state_missing = make_state(inventory={}, equipment={"weapon_slot": "copper_dagger"})
    assert ObtainItem("copper_pickaxe").is_satisfied(state_missing, gd) is False
    # Tool equipped also satisfies (owned_count includes equipped copy).
    state_equipped = make_state(inventory={}, equipment={"weapon_slot": "copper_pickaxe"})
    assert ObtainItem("copper_pickaxe").is_satisfied(state_equipped, gd) is True


def test_obtain_item_equippable_unknown_stats_falls_back_to_owned():
    """When stats aren't loaded for a code, we can't classify it as
    equippable — fall back to the legacy owned_count check rather than
    deadlocking the goal."""
    gd = GameData()  # no item_stats entries
    state = make_state(inventory={"mystery_thing": 1})
    assert ObtainItem("mystery_thing").is_satisfied(state, gd) is True
