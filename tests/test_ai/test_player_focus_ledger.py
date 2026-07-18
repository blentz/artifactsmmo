"""GamePlayer owns the per-cycle gear-focus aging ledger (arbiter
anti-starvation epic, Task 6): bump the chosen gear root each cycle a
decision is made, reset the whole ledger on real progress (level-up or a
successful craft of a non-consumable EQUIPPABLE item)."""
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers import ObtainItem, StrategyDecision
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel


def _bare_player() -> GamePlayer:
    return GamePlayer(character="hero")


def _obtain_item(code: str, slot: str) -> ObtainItem:
    return ObtainItem(code=code, quantity=1, slot=slot)


def _reach_char_level(level: int) -> ReachCharLevel:
    return ReachCharLevel(level=level)


def _decision_with_root(root: ObtainItem) -> StrategyDecision:
    return StrategyDecision(
        interrupt=None, chosen_root=root, chosen_step=root, desired_state={},
    )


def _craft_action(code: str) -> CraftAction:
    return CraftAction(code=code, quantity=1, workshop_location=(3, 0))


def _game_data_with_items() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "iron_ring": ItemStats(code="iron_ring", level=10, type_="ring"),
        "small_health_potion": ItemStats(
            code="small_health_potion", level=1, type_="utility"),
    }
    return gd


def _player_with_items() -> GamePlayer:
    p = _bare_player()
    p.game_data = _game_data_with_items()
    return p


def test_gear_root_key_extracts_slot_code():
    key = GamePlayer._gear_root_key(_obtain_item("iron_ring", "ring2_slot"))
    assert key == ("ring2_slot", "iron_ring")


def test_gear_root_key_none_for_non_gear_root():
    assert GamePlayer._gear_root_key(_reach_char_level(20)) is None


def test_bump_increments_chosen_gear_root():
    p = _bare_player()
    p._gear_focus = {}
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    p._bump_focus(_decision_with_root(_obtain_item("wolf_ears", "helmet_slot")))
    assert p._gear_focus[("helmet_slot", "wolf_ears")] == 2


def test_reset_on_level_up_clears_ledger():
    p = _bare_player()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    p._maybe_reset_focus(prev_level=14, cur_level=15, executed_action=None, outcome="ok")
    assert p._gear_focus == {}


def test_reset_on_equippable_craft_clears_ledger():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")  # iron_ring is a ring (equippable)
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {}


def test_no_reset_on_consumable_craft():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("small_health_potion")  # utility/consumable -> NOT a reset
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="ok")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}


def test_no_reset_on_failed_craft():
    p = _player_with_items()
    p._gear_focus = {("helmet_slot", "wolf_ears"): 40}
    craft = _craft_action("iron_ring")
    p._maybe_reset_focus(prev_level=15, cur_level=15, executed_action=craft, outcome="error")
    assert p._gear_focus == {("helmet_slot", "wolf_ears"): 40}
