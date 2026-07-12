from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import (
    KEEP_ALL,
    KeepReason,
    bankable,
    destroyable,
    keep_in_bag,
    keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=50),
    }
    gd._crafting_recipes = {"copper_axe": {"copper_bar": 6}}
    gd._workshop_locations = {"weaponcrafting": (3, 1)}
    return gd


def test_working_kit_keeps_ONE_in_bag_not_the_hoard():
    """The axe bug, at the authority level: kit is a QUANTITY of 1, so 18 held
    leaves 17 bankable. A blanket would leave 0."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 17


def test_currency_is_the_only_blanket():
    gd = _gd()
    state = make_state(level=10, inventory={"tasks_coin": 40})
    ctx = _ctx()
    assert keep_owned("tasks_coin", state, gd, ctx) == KEEP_ALL
    assert destroyable("tasks_coin", state, gd, ctx) == 0


def test_destroyable_counts_bank_copies_toward_owned():
    """keep_owned is about OWNERSHIP, so bank copies satisfy it: holding 1 in the
    bag and 5 in the bank with a gear demand of 2 leaves 4 destroyable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1},
                       bank_items={"copper_axe": 5})
    ctx = _ctx(gear_keep={"copper_axe": 2})
    assert keep_owned("copper_axe", state, gd, ctx) == 2
    assert destroyable("copper_axe", state, gd, ctx) == 4


def test_caps_are_never_negative():
    gd = _gd()
    state = make_state(level=10, inventory={})
    ctx = _ctx()
    assert bankable("copper_axe", state, gd, ctx) == 0
    assert destroyable("copper_axe", state, gd, ctx) == 0


def test_active_task_keeps_remaining_qty_not_the_whole_stack():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 30},
                       task_code="copper_bar", task_type="items",
                       task_total=10, task_progress=4)
    ctx = _ctx()
    assert reason_quantity(KeepReason.ACTIVE_TASK, "copper_bar", state, gd, ctx) == 6


def test_healing_consumable_caps_at_stock_target_not_the_whole_stack():
    """Instance #5 of the blanket bug, fixed: the real cap is the stock
    target, so surplus above it is bankable rather than hoarded forever."""
    gd = _gd()
    state = make_state(level=10, inventory={"cooked_chicken": 40})
    ctx = _ctx()
    assert reason_quantity(KeepReason.HEALING_CONSUMABLE, "cooked_chicken",
                           state, gd, ctx) == 5
    assert bankable("cooked_chicken", state, gd, ctx) == 35


def test_committed_recipe_keeps_crafting_target_materials():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 20},
                       crafting_target="copper_axe")
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 6
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "cooked_chicken",
                           state, gd, ctx) == 0


def test_committed_recipe_keeps_items_task_materials():
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 20},
                       task_code="copper_axe", task_type="items",
                       task_total=1, task_progress=0)
    ctx = _ctx()
    assert reason_quantity(KeepReason.COMMITTED_RECIPE, "copper_bar",
                           state, gd, ctx) == 6
