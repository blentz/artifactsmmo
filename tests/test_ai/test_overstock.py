"""Tests for inventory_caps + DiscardOverstockGoal."""

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.discard_overstock import (
    _DISCARD_OVERSTOCK_CRITICAL,
    _DISCARD_OVERSTOCK_HIGH_PRESSURE,
    PRIORITY_WHEN_OVERSTOCKED,
    DiscardOverstockGoal,
)
from artifactsmmo_cli.ai.inventory_caps import (
    BATCH_BUFFER,
    CONSUMABLE_KEEP,
    overstocked_items,
    useful_quantity_cap,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai.fixtures import make_state


def _gd_with_sap_recipes() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "sap": ItemStats(code="sap", level=1, type_="resource"),
        "small_antidote": ItemStats(
            code="small_antidote", level=1, type_="consumable",
            crafting_skill="alchemy", crafting_level=20,
        ),
    }
    gd._crafting_recipes = {
        "small_antidote": {"sap": 1, "small_health_potion": 1},
        "health_potion": {"sap": 1, "minor_health_potion": 1},
    }
    return gd


class TestUsefulQuantityCap:
    def test_cap_uses_recipe_demand_times_batch_buffer(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1)
        cap = useful_quantity_cap("sap", state, gd)
        # max_recipe_demand("sap") = 1; cap = 1 * BATCH_BUFFER = 5
        assert cap == BATCH_BUFFER

    def test_cap_zero_for_unused_item(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1)
        assert useful_quantity_cap("random_junk", state, gd) == 0

    def test_cap_keeps_healing_consumables(self):
        """Trace 2026-06-05 cycle 71: Robby deleted 5 apples because apples
        have no recipe / no active-task use / no equip slot, so cap fell to
        0 and DiscardOverstock nuked them. Apples (hp_restore>0) have real
        survival value — keep up to CONSUMABLE_KEEP regardless of recipe use."""
        gd = GameData()
        gd._item_stats = {
            "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=20),
            "cooked_chicken": ItemStats(code="cooked_chicken", level=1,
                                        type_="consumable", hp_restore=40),
        }
        gd._crafting_recipes = {}
        state = make_state(level=3, inventory={"apple": 5, "cooked_chicken": 12})
        assert useful_quantity_cap("apple", state, gd) == CONSUMABLE_KEEP
        assert useful_quantity_cap("cooked_chicken", state, gd) == CONSUMABLE_KEEP
        # Excess above CONSUMABLE_KEEP is still legitimately overstock.
        excess = overstocked_items(state, gd)
        assert "apple" not in excess  # 5 <= 10 cap → not overstocked
        assert excess.get("cooked_chicken") == 2  # 12 - 10 = 2 excess

    def test_cap_protects_task_chain_inputs(self):
        """Trace 2026-06-05: Robby task=ash_plank(3/13) sat on 67 ash_wood;
        DiscardOverstock would have nuked 62 ash_wood because the cap fell
        to recipe_max*5=5 — useful_quantity_cap didn't expand the task
        chain. The bank's _keep_codes already protects task-chain
        materials; the discard cap must match that discipline or the two
        diverge (bank protects, discard deletes).

        ash_plank<-ash_wood at 1:1, task needs 10 more ash_planks => need
        10 ash_wood to complete the task without re-gathering. Cap should
        be max(recipe_cap=5, task_chain=10) = 10."""
        gd = GameData()
        gd._item_stats = {
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"ash_plank": {"ash_wood": 1}}
        state = make_state(
            level=3, task_code="ash_plank", task_type="items",
            task_total=13, task_progress=3,
            inventory={"ash_wood": 67, "ash_plank": 3},
        )
        cap = useful_quantity_cap("ash_wood", state, gd)
        assert cap >= 10, (
            f"cap should protect 10 ash_wood for the 10 ash_plank task remainder, got {cap}"
        )
        excess = overstocked_items(state, gd)
        # 67 - 10 = 57 truly excess; bot may discard the surplus but the 10
        # needed for task completion must stay.
        assert excess.get("ash_wood", 0) <= 67 - 10

    def test_cap_chain_demand_scales_by_recipe_quantity(self):
        """Deeper chain: wooden_shield<-ash_plank x6, ash_plank<-ash_wood x1.
        Task=wooden_shield(0/2) means 2 shields => 12 ash_plank => 12 ash_wood.
        Cap on ash_wood must scale to 12, not the 5 recipe_max*batch baseline."""
        gd = GameData()
        gd._item_stats = {
            "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
            "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource"),
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield"),
        }
        gd._crafting_recipes = {
            "wooden_shield": {"ash_plank": 6},
            "ash_plank": {"ash_wood": 1},
        }
        state = make_state(
            level=3, task_code="wooden_shield", task_type="items",
            task_total=2, task_progress=0,
        )
        assert useful_quantity_cap("ash_wood", state, gd) >= 12
        assert useful_quantity_cap("ash_plank", state, gd) >= 12

    def test_cap_chain_demand_cycle_safe(self):
        """Self-referential recipe (a uses b, b uses a) must terminate
        without infinite recursion. Returns 0 chain demand for any item
        not reachable from the root via a non-cyclic path."""
        gd = GameData()
        gd._item_stats = {
            "a": ItemStats(code="a", level=1, type_="resource"),
            "b": ItemStats(code="b", level=1, type_="resource"),
            "c": ItemStats(code="c", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"a": {"b": 1}, "b": {"a": 1}}
        state = make_state(task_code="a", task_type="items",
                           task_total=5, task_progress=0)
        # Should terminate. Cap on c (not in chain) is recipe_max*batch + safety = 0.
        cap_c = useful_quantity_cap("c", state, gd)
        assert cap_c == 0
        # b IS reachable from a once: need 5 b for 5 a.
        assert useful_quantity_cap("b", state, gd) >= 5

    def test_cap_zero_for_non_healing_consumable(self):
        """Only hp_restore>0 consumables qualify for the keep cap. A
        consumable with hp_restore=0 (e.g. some buff potion) gets the
        normal recipe/task/equip rules."""
        gd = GameData()
        gd._item_stats = {
            "buff_dust": ItemStats(code="buff_dust", level=1,
                                   type_="consumable", hp_restore=0),
        }
        gd._crafting_recipes = {}
        state = make_state()
        assert useful_quantity_cap("buff_dust", state, gd) == 0

    def test_cap_protects_tasks_coin_at_scale(self):
        """Trace 2026-06-05T02:55: Robby deleted 3 tasks_coin (out of 12)
        because the legacy cap of 9 declared the excess as overstock.
        Tasks_coins stack in a single inventory slot regardless of
        quantity, so the low cap freed zero slots while throwing away
        TaskExchange currency. Cap is now 999 so any plausible
        accumulation is protected — overstock filter should never strip
        them."""
        gd = GameData()
        gd._item_stats = {}
        gd._crafting_recipes = {}
        state = make_state(inventory={TASKS_COIN_CODE: 50})
        assert useful_quantity_cap(TASKS_COIN_CODE, state, gd) >= 50
        assert overstocked_items(state, gd) == {}, (
            "50 tasks_coin must not be flagged overstock — they stack"
        )

    def test_cap_respects_active_task_demand(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, task_code="sap", task_type="items",
                            task_total=50, task_progress=10)
        # Task needs 40 more; recipe cap is 5. Max = 40.
        cap = useful_quantity_cap("sap", state, gd)
        assert cap == 40

    def test_equipped_items_have_floor_of_one(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, equipment={"weapon_slot": "sap"})
        # 'sap' is equipped (silly but valid as test). Cap should be ≥ 1.
        cap = useful_quantity_cap("sap", state, gd)
        assert cap >= 1

    def test_equippable_craftable_capped_at_one(self):
        """Equippable craftables (weapon/armor/ring) cap at 1 — keep a single
        spare for the optimizer's swap pool, discard the rest. We don't need
        a hoard of duplicate daggers."""
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1)}
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}  # not a recipe ingredient
        state = make_state(level=5, inventory={"copper_dagger": 3})
        assert useful_quantity_cap("copper_dagger", state, gd) == 1
        assert overstocked_items(state, gd) == {"copper_dagger": 2}

    def test_equippable_cap_yields_to_active_task(self):
        """...unless a task requires more — task_cap overrides the equippable
        floor so the bot keeps enough to complete an items task."""
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1)}
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}
        state = make_state(level=5, inventory={"copper_dagger": 3},
                           task_code="copper_dagger", task_type="items",
                           task_total=10, task_progress=2)
        # Task needs 8 more → cap 8, nothing overstocked at 3 held.
        assert useful_quantity_cap("copper_dagger", state, gd) == 8
        assert "copper_dagger" not in overstocked_items(state, gd)


class TestOverstockedItems:
    def test_only_returns_items_over_cap(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, inventory={"sap": 50, "other_thing": 2})
        excess = overstocked_items(state, gd)
        # sap cap is 5; 50 > 5 → excess 45
        assert excess == {"sap": 50 - BATCH_BUFFER, "other_thing": 2}

    def test_empty_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        state = make_state(level=1, inventory={"sap": 3})
        assert overstocked_items(state, gd) == {}


class TestDiscardOverstockGoal:
    def test_fires_high_when_overstocked(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        # Large inventory_max so pressure is low (50/200=25%); checks baseline tier.
        state = make_state(level=1, inventory={"sap": 50}, inventory_max=200)
        assert goal.value(state, gd) == PRIORITY_WHEN_OVERSTOCKED

    def test_priority_escalates_under_high_pressure(self):
        """Inventory pressure >= 0.85 → DISCARD_OVERSTOCK_HIGH_PRESSURE (55)."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50}, inventory_max=55)  # 50/55 = 0.91
        assert goal.value(state, gd) == _DISCARD_OVERSTOCK_HIGH_PRESSURE

    def test_priority_escalates_under_critical_pressure(self):
        """Inventory pressure >= 0.95 → DISCARD_OVERSTOCK_CRITICAL (85)."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50}, inventory_max=52)  # 50/52 = 0.96
        assert goal.value(state, gd) == _DISCARD_OVERSTOCK_CRITICAL

    def test_high_pressure_beats_gather_materials(self):
        """At high pressure (>=0.85), overstock outranks GatherMaterials (50)."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50}, inventory_max=55)
        assert goal.value(state, gd) > 50.0  # GATHER_MATERIALS was 50.0

    def test_zero_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 3})
        assert goal.value(state, gd) == 0.0

    def test_satisfied_when_no_overstock(self):
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        assert goal.is_satisfied(make_state(level=1, inventory={"sap": 3})) is True
        assert goal.is_satisfied(make_state(level=1, inventory={"sap": 50})) is False

    def test_relevant_actions_constructs_batch_sell(self):
        """Single batch action drains the entire excess in one cycle."""
        gd = _gd_with_sap_recipes()
        gd._npc_sell_prices = {"npc1": {"sap": 2}}
        gd._npc_locations = {"npc1": (3, 3)}
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        relevant = goal.relevant_actions([], state, gd)
        # Exactly one batch NpcSell with the full excess quantity.
        assert len(relevant) == 1
        sell = relevant[0]
        assert isinstance(sell, NpcSellAction)
        assert sell.item_code == "sap"
        assert sell.quantity == 50 - BATCH_BUFFER  # 45
        assert sell.npc_code == "npc1"
        assert sell.npc_location == (3, 3)

    def test_active_task_item_never_overstocked(self):
        """Regression: while gathering a batch for a task, the task_code item
        must NOT appear in overstocked_items even at large counts — otherwise
        DiscardOverstock would race FarmItems and delete the gathered batch
        before TaskTrade fires."""
        gd = GameData()
        gd._item_stats = {"gudgeon": ItemStats(code="gudgeon", level=1, type_="resource")}
        gd._crafting_recipes = {}  # no recipes — only task_cap protects it
        goal = DiscardOverstockGoal(game_data=gd)
        # Holding 30 gudgeon mid-batch toward a 353 task
        state = make_state(level=1,
                            inventory={"gudgeon": 30, "junk": 50},
                            inventory_max=104,
                            task_code="gudgeon", task_type="items",
                            task_total=353, task_progress=121)
        excess = overstocked_items(state, gd)
        # gudgeon protected (task_cap=232 >= 30); junk still overstocked
        assert "gudgeon" not in excess
        relevant = goal.relevant_actions([], state, gd)
        codes = {a.code if hasattr(a, "code") else a.item_code for a in relevant}
        assert "gudgeon" not in codes

    def test_relevant_actions_delete_when_buyer_location_unknown(self):
        """Buyer known but location not loaded → must fall back to Delete,
        otherwise NpcSell is_applicable=False and the goal becomes
        unsatisfiable (plan_len=0)."""
        gd = _gd_with_sap_recipes()
        gd._npc_sell_prices = {"npc1": {"sap": 2}}  # buyer known
        gd._npc_locations = {}  # location NOT loaded
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], DeleteItemAction)
        assert relevant[0].code == "sap"

    def test_relevant_actions_falls_back_to_batch_delete(self):
        """No NPC buys → batch DeleteItem with full excess quantity."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        delete = relevant[0]
        assert isinstance(delete, DeleteItemAction)
        assert delete.code == "sap"
        assert delete.quantity == 50 - BATCH_BUFFER  # 45

    def test_relevant_actions_one_per_overstocked_item(self):
        """Multiple overstocked items → multiple batch actions, one each."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50, "extra": 99})
        relevant = goal.relevant_actions([], state, gd)
        # One batch per overstocked code (sap + extra)
        codes = {a.code if isinstance(a, DeleteItemAction) else a.item_code for a in relevant}
        assert codes == {"sap", "extra"}
