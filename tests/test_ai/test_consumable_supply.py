from artifactsmmo_cli.ai.consumable_supply import consumable_craft_quantity
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "small_health_potion": ItemStats(code="small_health_potion", level=1, type_="utility",
                                          crafting_skill="alchemy", crafting_level=5),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "apple_pie": ItemStats(code="apple_pie", level=1, type_="consumable",
                               crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {
        "cooked_chicken": {"raw_chicken": 1},
        "small_health_potion": {"sunflower": 3},
        "copper_dagger": {"copper_bar": 6},
        "apple_pie": {"apple": 4, "egg": 2},
    }
    return gd


class TestConsumableCraftQuantity:
    def test_cooks_the_whole_held_pile(self):
        gd = _gd()
        state = make_state(inventory={"raw_chicken": 9})
        # recipe raw_chicken:1, yield 1 -> 9 runs from held; planned 1 -> 9
        assert consumable_craft_quantity("cooked_chicken", 1, state, gd) == 9

    def test_no_raws_held_returns_planned(self):
        gd = _gd()
        state = make_state(inventory={})
        assert consumable_craft_quantity("cooked_chicken", 1, state, gd) == 1

    def test_utility_potion_batches(self):
        gd = _gd()
        state = make_state(inventory={"sunflower": 12})  # 12//3 = 4 runs
        assert consumable_craft_quantity("small_health_potion", 1, state, gd) == 4

    def test_non_consumable_unchanged(self):
        gd = _gd()
        state = make_state(inventory={"copper_bar": 60})  # 60//6 = 10, but weapon
        assert consumable_craft_quantity("copper_dagger", 1, state, gd) == 1

    def test_multi_ingredient_bounded_by_scarcest(self):
        gd = _gd()
        # apple_pie needs apple:4, egg:2. Hold apple=20 (20//4=5 runs) but
        # egg=6 (6//2=3 runs) -> min over ingredients = 3. A wrong impl using
        # only the first ingredient would return 5, so this proves the min().
        state = make_state(inventory={"apple": 20, "egg": 6})
        assert consumable_craft_quantity("apple_pie", 1, state, gd) == 3

    def test_never_shrinks_below_planned(self):
        gd = _gd()
        state = make_state(inventory={"raw_chicken": 2})  # 2 runs from held
        assert consumable_craft_quantity("cooked_chicken", 5, state, gd) == 5

    def test_unknown_code_returns_planned(self):
        gd = _gd()
        assert consumable_craft_quantity("nonexistent", 3, make_state(), gd) == 3

    def test_no_recipe_returns_planned(self):
        gd = _gd()
        gd._item_stats["raw_egg"] = ItemStats(code="raw_egg", level=1, type_="consumable")
        # type_ consumable but no crafting recipe -> planned
        assert consumable_craft_quantity("raw_egg", 4, make_state(), gd) == 4
