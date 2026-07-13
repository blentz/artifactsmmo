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
        "rusty_pickaxe": ItemStats(code="rusty_pickaxe", level=1, type_="weapon",
                                   attack={"earth": 2}, skill_effects={"mining": -5}),
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10}),
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
    """The task item is kept at its REMAINING demand (9 needed, 9 held → none
    bankable) and the coins are kept absolutely (CURRENCY = KEEP_ALL)."""
    gd = _gd()
    state = make_state(inventory={"copper_ore": 9, "tasks_coin": 3, "sap": 1},
                       task_code="copper_ore", task_type="items", task_total=9)
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_task_item_surplus_above_the_remaining_demand_banks():
    """De-blanketing, the other half: the task needs 4 MORE copper_ore (5 of 9
    already delivered), so the 5 spares above that bank while the 4 stay. The old
    code-set kept all 9 forever."""
    gd = _gd()
    state = make_state(inventory={"copper_ore": 9}, task_code="copper_ore",
                       task_type="items", task_total=9, task_progress=5)
    assert select_bank_deposits(state, gd) == [("copper_ore", 5)]


def test_tasks_coin_is_never_banked_at_any_holdable_quantity():
    """KEEP_ALL guard at the deposit boundary. `keep_in_bag("tasks_coin")` is the
    `KEEP_ALL` sentinel (1e6), so the arithmetic a naive consumer would do —
    "how many can I shed" — must not produce an absurd number. `bankable` clamps
    at 0, so the coin yields NO deposit at any quantity the server can put in a
    bag (`inventory_max` is a low-hundreds number even with every bag slot), and
    the sentinel's 1e6 ceiling is never approached."""
    gd = _gd()
    for held in (1, 3, 40, 999, 10_000):
        state = make_state(inventory={"tasks_coin": held, "sap": 1},
                           inventory_max=max(20, held + 1))
        deposits = dict(select_bank_deposits(state, gd))
        assert "tasks_coin" not in deposits
        assert deposits == {"sap": 1}


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
        task_total=1,
    )
    # The one iron_dagger the task still wants needs 6 iron_bar + 2 spruce_plank:
    # those copies are NEVER banked. The SURPLUS above the recipe demand is (that
    # is the fix — the old code-set pinned all 12 bars in the bag).
    deposits = dict(select_bank_deposits(state, gd))
    assert deposits == {"sap": 1, "iron_bar": 6, "spruce_plank": 2}
    assert state.inventory["iron_bar"] - deposits["iron_bar"] == 6
    assert state.inventory["spruce_plank"] - deposits["spruce_plank"] == 2


def test_task_recipe_demand_scales_with_the_remaining_task_quantity():
    """COMMITTED_RECIPE is task-quantity scaled: 3 daggers still owed → 18 bars
    demanded, so all 12 held stay (nothing bankable)."""
    gd = _gd()
    state = make_state(inventory={"iron_bar": 12, "sap": 1}, task_code="iron_dagger",
                       task_type="items", task_total=3)
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
    """A tool never counts as the protected FIGHTING weapon: with a pickaxe and
    a stick in the bag, the stick is the kept weapon (the pickaxe is kept too,
    but by the gathering-tool rule, not the weapon rule — a WORSE tool of the
    same skill proves the distinction by getting banked)."""
    gd = _gd()
    state = make_state(inventory={"copper_pickaxe": 1, "rusty_pickaxe": 1,
                                  "wooden_stick": 1, "sap": 1})
    codes = [c for c, _ in select_bank_deposits(state, gd)]
    assert "rusty_pickaxe" in codes  # outclassed tool -> bankable
    assert "wooden_stick" not in codes  # best fighting weapon -> kept


def test_deposit_banks_the_kit_tool_spares_not_the_working_tool():
    """THE live hoard (Robby 2026-07-12): 18 copper_axe in the bag — the axe is
    the best woodcutting tool, so the old `_keep_codes` code-SET blanket-kept the
    whole CODE and DepositAll banked ZERO of them while the weaponcrafting grind
    kept manufacturing more. A code-set can only say "keep ALL copies"; the keep
    authority says WORKING_KIT wants exactly ONE. Bank 17, keep the 1 the gather
    re-arm will equip."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    deposits = dict(select_bank_deposits(state, gd))
    assert deposits["copper_axe"] == 17
    assert state.inventory["copper_axe"] - deposits["copper_axe"] == 1


def test_keeps_best_gathering_tool_per_skill():
    """Regression (trace 2026-07-05): copper_pickaxe was deposited and Robby
    mined 261/300 cycles bare-handed. The best owned tool per gathering skill
    is working kit — deposit must never bank it."""
    gd = _gd()
    state = make_state(inventory={"copper_pickaxe": 1, "sap": 1})
    assert select_bank_deposits(state, gd) == [("sap", 1)]


def test_keeps_only_the_best_tool_for_a_skill():
    gd = _gd()
    state = make_state(inventory={"copper_pickaxe": 1, "rusty_pickaxe": 1, "sap": 1})
    codes = [c for c, _ in select_bank_deposits(state, gd)]
    assert "copper_pickaxe" not in codes
    assert "rusty_pickaxe" in codes


def test_best_tool_considers_equipped_slot():
    gd = _gd()
    state = make_state(inventory={"rusty_pickaxe": 1, "sap": 1},
                       equipment={"weapon_slot": "copper_pickaxe"})
    codes = [c for c, _ in select_bank_deposits(state, gd)]
    assert "rusty_pickaxe" in codes


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
    # twin_blade wants shared_bar through BOTH hilts → a transitive demand of 2.
    # Those 2 stay; the 2 spares bank.
    deposits = dict(select_bank_deposits(state, gd))
    assert deposits == {"sap": 1, "shared_bar": 2}


def test_empty_when_everything_kept():
    gd = _gd()
    state = make_state(inventory={"tasks_coin": 1, "copper_ore": 5},
                       task_code="copper_ore", task_type="items", task_total=5)
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
        task_code="iron_dagger", task_type="items", task_total=2, inventory_max=20,
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
                       task_code="copper_ore", task_type="items", task_total=5,
                       inventory_max=20)
    assert state.inventory_free > 0
    assert select_bank_deposits(state, gd) == []


def test_last_resort_prefers_non_critical_then_lowest_value():
    """When the full bag is ALL keep-set, shed a recipe material (non-critical)
    before the weapon / HP consumable / task item; tie broken by code asc."""
    gd = _gd()  # iron_dagger recipe = {iron_bar: 6, spruce_plank: 2}
    state = make_state(
        inventory={"iron_dagger": 1, "copper_dagger": 1, "cooked_chicken": 1,
                   "iron_bar": 15, "spruce_plank": 2},
        task_code="iron_dagger", task_type="items", task_total=3, inventory_max=20,
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


def test_last_resort_frees_a_slot_when_slots_full_but_quantity_headroom():
    """SLOT-AWARE last-resort (follow-up 2026-07-09): all inventory SLOTS occupied
    by keep-set stacks (slots_free==0) with plenty of QUANTITY headroom
    (inventory_free>0). The bag still cannot admit another item — combat needs a
    free slot — so one non-critical keep stack is shed. The same state with slot
    headroom banks NOTHING (proving the slot condition, not quantity, drives it)."""
    gd = _gd()  # iron_dagger recipe = {iron_bar: 6, spruce_plank: 2}
    # 4 keep-set stacks (task item, coins, two recipe mats), each low count.
    inventory = {"iron_dagger": 1, "tasks_coin": 1, "iron_bar": 1, "spruce_plank": 1}
    slots_full = make_state(
        inventory=inventory, task_code="iron_dagger", task_type="items", task_total=1,
        inventory_max=100, inventory_slots_max=4,
    )
    assert slots_full.inventory_free > 0       # quantity cap NOT hit
    assert slots_full.inventory_slots_free == 0  # every slot occupied
    result = select_bank_deposits(slots_full, gd)
    assert len(result) == 1  # last-resort frees exactly one slot
    code, _ = result[0]
    assert code in {"iron_bar", "spruce_plank"}       # non-critical recipe mat shed
    assert code not in {"iron_dagger", "tasks_coin"}  # task item / coins protected

    # Same bag, but with a free slot → keep-set untouched (non-vacuous contrast).
    slots_slack = make_state(
        inventory=inventory, task_code="iron_dagger", task_type="items", task_total=1,
        inventory_max=100, inventory_slots_max=5,
    )
    assert slots_slack.inventory_free > 0
    assert slots_slack.inventory_slots_free > 0
    assert select_bank_deposits(slots_slack, gd) == []


def test_last_resort_never_sheds_the_weapon_kit_heals_or_task_item_first():
    """The last-resort criticality ranking, made discriminating. The bag is full and
    NOTHING is bankable (every code sits exactly at its keep cap), so one protected
    stack must go. The recipe material is the ONLY non-critical stack — and it is
    shed even though it is by far the most VALUABLE thing in the bag (sell 50 vs 0),
    because criticality outranks sell value.

    Drop any one of the four criticality arms — task item, HP consumable, best
    fighting weapon, working kit — and that stack becomes the cheap non-critical
    pick instead, shedding the very thing the bot cannot act without."""
    gd = _gd()
    gd._npc_sell_prices = {"merchant": {"iron_bar": 50}}  # the material is the RICH one
    state = make_state(
        inventory={"iron_dagger": 1,      # task item        (ACTIVE_TASK = 1)
                   "cooked_chicken": 5,   # heal stock       (HEALING_CONSUMABLE = 5)
                   "copper_dagger": 1,    # fighting weapon  (COMBAT_WEAPON = 1)
                   "copper_pickaxe": 1,   # working kit      (WORKING_KIT = 1)
                   "iron_bar": 6},        # task recipe input (COMMITTED_RECIPE = 6)
        task_code="iron_dagger", task_type="items", task_total=1,
        inventory_max=14,
    )
    assert state.inventory_free == 0
    result = select_bank_deposits(state, gd)
    assert len(result) == 1, "nothing is bankable, so exactly one stack is shed"
    assert result[0][0] == "iron_bar", (
        "the recoverable, non-critical material sheds first — never the weapon, the "
        "working tool, the heal stock or the task item"
    )


def test_last_resort_sheds_critical_only_as_final_fallback():
    """If the full bag is ALL hard-critical items, still free a slot (recoverable)
    rather than stall — the lowest-value critical item is banked."""
    gd = _gd()
    # Full bag of only HP consumables + task coins, with NOTHING above its keep cap:
    # the heal stock target is 5 and exactly 5 chickens are held, the coins are
    # KEEP_ALL. Every stack is hard-critical, so criticality cannot break the tie —
    # lowest sell value then code ascending picks the chicken.
    state = make_state(
        inventory={"cooked_chicken": 5, "tasks_coin": 15},
        inventory_max=20,
    )
    assert state.inventory_free == 0
    result = select_bank_deposits(state, gd)
    assert len(result) == 1  # frees a slot even though everything is critical
    assert result[0][0] == "cooked_chicken"
