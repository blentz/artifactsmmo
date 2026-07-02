from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                              crafting_skill="mining", crafting_level=1),
                      "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource")}
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    return gd


def test_intermediate_rebatched_to_demand():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    # demand 6 bars, ample inventory -> batched to 6 (< BATCH_CAP)
    state = make_state(inventory={"copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 6


def test_intermediate_subtracts_held():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    state = make_state(inventory={"copper_bar": 2, "copper_ore": 100}, inventory_max=200)
    out = size_intermediate_craft(a, {"copper_bar": 6}, state, gd)
    assert out.quantity == 4   # 6 demand - 2 held


def test_intermediate_absent_from_chain_unchanged():
    gd = _gd()
    a = CraftAction(code="copper_bar", quantity=1, workshop_location=(0, 0))
    out = size_intermediate_craft(a, {}, make_state(), gd)
    assert out.quantity == 1   # no demand -> floors at 1, action returned as-is
