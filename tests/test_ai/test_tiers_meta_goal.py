from artifactsmmo_cli.ai.game_data import GameData
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
