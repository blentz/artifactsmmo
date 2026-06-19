"""Tests for select_bank_deposits — the bank keep-set + sell-value ordering."""

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd(**overrides) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = {
        "merchant": {"gold_ore": 50, "copper_ore": 8, "sap": 3},
        "trader": {"gold_ore": 60},  # higher buy-back for gold_ore
    }
    gd._item_stats = {
        "gold_ore": ItemStats(code="gold_ore", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=25),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon", attack={"fire": 12}),
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon", attack={"air": 4}),
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10}),
        "iron_bar": ItemStats(code="iron_bar", level=1, type_="resource"),
        "spruce_plank": ItemStats(code="spruce_plank", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"iron_dagger": {"iron_bar": 6, "spruce_plank": 2}}
    for k, v in overrides.items():
        setattr(gd, k, v)
    return gd


def test_orders_by_sell_value_desc_then_code():
    gd = _gd()
    state = make_state(inventory={"gold_ore": 1, "copper_ore": 2, "sap": 5})
    assert select_bank_deposits(state, gd) == [("gold_ore", 1), ("copper_ore", 2), ("sap", 5)]


def test_unknown_price_sorts_last():
    gd = _gd()
    state = make_state(inventory={"sap": 1, "mystery": 9})  # mystery has no buy-back
    assert select_bank_deposits(state, gd) == [("sap", 1), ("mystery", 9)]


def test_keeps_task_item_and_task_coins():
    gd = _gd()
    state = make_state(inventory={"copper_ore": 9, "tasks_coin": 3, "sap": 1},
                       task_code="copper_ore", task_type="items")
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_items_task_recipe_materials():
    """Materials needed to craft the active items-task item must not be banked.

    Regression: depositing the task item's own crafting inputs (e.g. iron_bar
    for an iron_dagger task) starved the PursueTask loop, freezing progress.
    """
    gd = _gd()  # iron_dagger recipe = {iron_bar: 6, spruce_plank: 2}
    state = make_state(
        inventory={"iron_bar": 12, "spruce_plank": 4, "sap": 1},
        task_code="iron_dagger",
        task_type="items",
    )
    # iron_bar + spruce_plank are task-recipe inputs -> kept; only sap is bankable.
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_hp_consumables():
    gd = _gd()
    state = make_state(inventory={"cooked_chicken": 4, "sap": 1})
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_best_fighting_weapon_deposits_worse_one():
    gd = _gd()
    state = make_state(inventory={"copper_dagger": 1, "wooden_stick": 1, "sap": 1})
    result = select_bank_deposits(state, gd)
    codes = [c for c, _ in result]
    assert "copper_dagger" not in codes
    assert "wooden_stick" in codes and "sap" in codes


def test_best_weapon_considers_equipped_slot():
    gd = _gd()
    state = make_state(inventory={"wooden_stick": 1},
                       equipment={"weapon_slot": "copper_dagger"})
    assert ("wooden_stick", 1) in select_bank_deposits(state, gd)


def test_tool_is_not_treated_as_fighting_weapon():
    gd = _gd()
    state = make_state(inventory={"copper_pickaxe": 1, "wooden_stick": 1})
    codes = [c for c, _ in select_bank_deposits(state, gd)]
    assert "copper_pickaxe" in codes
    assert "wooden_stick" not in codes


def test_keeps_crafting_target_materials():
    gd = _gd()
    state = make_state(inventory={"iron_bar": 6, "spruce_plank": 2, "sap": 1},
                       crafting_target="iron_dagger")
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_materials_via_shared_submaterial():
    """A material reachable through two recipe branches is visited once."""
    gd = _gd()
    gd._crafting_recipes = {
        "twin_blade": {"left_hilt": 1, "right_hilt": 1},
        "left_hilt": {"shared_bar": 1},
        "right_hilt": {"shared_bar": 1},  # shared_bar reached twice → visited guard
    }
    state = make_state(inventory={"shared_bar": 4, "sap": 1}, crafting_target="twin_blade")
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_empty_when_everything_kept():
    gd = _gd()
    state = make_state(inventory={"tasks_coin": 1, "copper_ore": 5}, task_code="copper_ore")
    assert select_bank_deposits(state, gd) == []


def test_ignores_zero_quantity():
    gd = _gd()
    state = make_state(inventory={"sap": 0, "copper_ore": 2})
    assert select_bank_deposits(state, gd) == [("copper_ore", 2)]


def test_last_resort_frees_a_slot_when_full_of_kept_items():
    """A bag with ZERO free slots, full of keep-set items, banks one least-
    critical stack so a slot frees (else FightAction stalls — combat needs >=1
    free slot). The task item / coins are kept; the recipe material is shed."""
    gd = _gd()  # iron_dagger recipe = {iron_bar: 6, spruce_plank: 2}
    # max=20, used=20 → free==0; everything is keep-set (task item, coins, recipe mats).
    state = make_state(
        inventory={"iron_dagger": 1, "tasks_coin": 5, "iron_bar": 12, "spruce_plank": 2},
        task_code="iron_dagger", task_type="items", inventory_max=20,
    )
    assert state.inventory_free == 0
    result = select_bank_deposits(state, gd)
    assert len(result) == 1  # exactly one stack, to free a single slot
    code, _ = result[0]
    # Shed a recipe material (recoverable), never the task item or coins.
    assert code in {"iron_bar", "spruce_plank"}
    assert code not in {"iron_dagger", "tasks_coin"}


def test_last_resort_inactive_while_slack_remains():
    """With even one free slot, the keep-set is untouched (no last-resort)."""
    gd = _gd()
    state = make_state(inventory={"tasks_coin": 1, "copper_ore": 5},
                       task_code="copper_ore", inventory_max=20)
    assert state.inventory_free > 0
    assert select_bank_deposits(state, gd) == []


def test_last_resort_prefers_non_critical_then_lowest_value():
    """When the full bag is ALL keep-set, shed a recipe material (non-critical)
    before the weapon / HP consumable / task item; tie broken by code asc."""
    gd = _gd()  # iron_dagger recipe = {iron_bar: 6, spruce_plank: 2}
    state = make_state(
        inventory={"iron_dagger": 1, "copper_dagger": 1, "cooked_chicken": 1,
                   "iron_bar": 15, "spruce_plank": 2},
        task_code="iron_dagger", task_type="items", inventory_max=20,
    )
    assert state.inventory_free == 0
    result = select_bank_deposits(state, gd)
    assert len(result) == 1
    code, _ = result[0]
    # recipe mats are non-critical → shed before weapon/consumable/task item;
    # iron_bar before spruce_plank (both sell-value 0, code asc).
    assert code == "iron_bar"


def test_last_resort_noop_on_empty_bag():
    """Degenerate: a zero-capacity bag reads inventory_free == 0 but has nothing
    to shed — last-resort returns nothing rather than indexing an empty list."""
    gd = _gd()
    state = make_state(inventory={}, inventory_max=0)
    assert state.inventory_free == 0
    assert select_bank_deposits(state, gd) == []


def test_last_resort_sheds_critical_only_as_final_fallback():
    """If the full bag is ALL hard-critical items, still free a slot (recoverable)
    rather than stall — the lowest-value critical item is banked."""
    gd = _gd()
    # full bag of only HP consumables + task coins (all hard-critical).
    state = make_state(
        inventory={"cooked_chicken": 15, "tasks_coin": 5},
        inventory_max=20,
    )
    assert state.inventory_free == 0
    result = select_bank_deposits(state, gd)
    assert len(result) == 1  # frees a slot even though everything is critical
