"""Tests for inventory_caps + DiscardOverstockGoal."""

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.discard_overstock import (
    _DISCARD_OVERSTOCK_CRITICAL,
    _DISCARD_OVERSTOCK_HIGH_PRESSURE,
    DiscardOverstockGoal,
)
from artifactsmmo_cli.ai.inventory_caps import (
    BATCH_BUFFER,
    CONSUMABLE_KEEP,
    SAFETY_FLOOR,
    _equip_value,
    _is_dominated_pure,
    _is_equippable_dominated,
    _task_chain_demand_pure,
    overstocked_items,
    reachable_recipe_demand,
    useful_quantity_cap,
    useful_quantity_cap_excl_equipped,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai.fixtures import make_state


def test_equip_value_counts_utility_stats_so_artifact_not_discarded():
    """The dominance value includes hp_bonus + wisdom + prospecting, so a
    utility-only artifact (novice_guide: combat stats 0, wisdom/prospecting/hp 25)
    is valued 75 — not 0 — and is therefore not trivially dominated and discarded
    as worthless overstock (the Delete(novice_guide×4) trace bug)."""
    art = ItemStats(code="novice_guide", level=10, type_="artifact",
                    hp_bonus=25, wisdom=25, prospecting=25)
    assert _equip_value(art) == 75
    # A combat peer with a small attack no longer out-values it.
    weak = ItemStats(code="w", level=1, type_="weapon", attack={"fire": 10})
    assert _equip_value(art) > _equip_value(weak)
    # A bag's inventory_space also counts → not valued 0 / discarded.
    bag = ItemStats(code="backpack", level=10, type_="bag", inventory_space=35)
    assert _equip_value(bag) == 35
    # Haste (cooldown reduction) also counts.
    legs = ItemStats(code="haste_legs", level=1, type_="leg_armor", haste=8)
    assert _equip_value(legs) == 8
    # Lifesteal (combat sustain) also counts.
    ring = ItemStats(code="vampiric_ring", level=1, type_="ring", lifesteal=15)
    assert _equip_value(ring) == 15
    # Combat-buff potions count so they aren't discarded as worthless (PLAN #3a).
    pot = ItemStats(code="enchanted_boost_potion", level=1, type_="utility", combat_buff=20)
    assert _equip_value(pot) == 20


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
        """Trace 2026-06-05 cycle 71: Robby deleted 5 apples; second
        trace at 16:13 deleted 19 apples in a single Delete(apple×19).
        Apples (hp_restore>0) STACK in one inventory slot regardless
        of count, so capping low frees zero slots while throwing away
        healing stock. Post-fix CONSUMABLE_KEEP = 999 so any plausible
        accumulation is protected — symmetric to the tasks_coin fix."""
        gd = GameData()
        gd._item_stats = {
            "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=20),
            "cooked_chicken": ItemStats(code="cooked_chicken", level=1,
                                        type_="consumable", hp_restore=40),
        }
        gd._crafting_recipes = {}
        state = make_state(level=3, inventory={"apple": 29, "cooked_chicken": 50})
        assert useful_quantity_cap("apple", state, gd) == CONSUMABLE_KEEP
        assert useful_quantity_cap("cooked_chicken", state, gd) == CONSUMABLE_KEEP
        # 29 apples / 50 chicken both well under the cap → not overstocked.
        excess = overstocked_items(state, gd)
        assert excess == {}, (
            f"healing consumables must not be flagged overstock; got {excess}"
        )

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

    def test_cap_protects_non_healing_consumable(self):
        """EVERY `type == "consumable"` item is kept, not just hp_restore>0
        ones: a non-healing consumable (teleport potion, gold-bag potion, buff
        dust) is used deliberately and must never be auto-deleted/bank-drained
        as junk. API `type`-driven keep-floor (CONSUMABLE_KEEP), so the cap is
        999 even with hp_restore=0 — the prior `== 0` was the bug (recall_potion
        / forest_bank_potion / bag_of_gold fell to cap 0 and were delete-eligible)."""
        gd = GameData()
        gd._item_stats = {
            "buff_dust": ItemStats(code="buff_dust", level=1,
                                   type_="consumable", hp_restore=0),
        }
        gd._crafting_recipes = {}
        state = make_state()
        assert useful_quantity_cap("buff_dust", state, gd) == 999

    def test_cap_protects_every_currency_type(self):
        """EVERY `type == "currency"` item is protected (cap 999), not just
        tasks_coin by hardcoded code. The live server defines event_ticket,
        corrupted_gem, sandwhisper_coin — all economic currency that must never
        be auto-deleted/bank-drained. API `type`-driven so future currencies are
        covered too."""
        gd = GameData()
        gd._item_stats = {
            "event_ticket": ItemStats(code="event_ticket", level=1, type_="currency"),
            "sandwhisper_coin": ItemStats(code="sandwhisper_coin", level=1, type_="currency"),
        }
        gd._crafting_recipes = {}
        state = make_state()
        assert useful_quantity_cap("event_ticket", state, gd) == 999
        assert useful_quantity_cap("sandwhisper_coin", state, gd) == 999

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
        """Equippable craftables (weapon/armor/ring) keep a useful floor of 1 —
        a single spare for the optimizer's swap pool. Post-spec-2026-06-07 the
        useful_quantity_cap is the SPACE-DRIVEN floor, not a dump trigger: with
        free slots (low pressure) the surplus is NOT overstock. The floor only
        decides excess once the bag is genuinely full."""
        gd = GameData()
        gd._item_stats = {"copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1)}
        gd._crafting_recipes = {"copper_dagger": {"copper_bar": 6}}  # not a recipe ingredient
        # useful floor unchanged (1) — but with free slots nothing is overstock.
        state = make_state(level=5, inventory={"copper_dagger": 3}, inventory_max=20)
        assert useful_quantity_cap("copper_dagger", state, gd) == 1
        assert overstocked_items(state, gd) == {}, (
            "free slots → no space pressure → surplus is not overstock"
        )
        # Under genuine space pressure (bag near-full) the useful floor binds:
        # 19/20 = 0.95 >= watermark → 3 held - floor 1 = 2 excess.
        full = make_state(level=5, inventory={"copper_dagger": 3, "junk": 16},
                          inventory_max=20)
        assert overstocked_items(full, gd).get("copper_dagger") == 2

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
    def test_no_value_when_free_slots(self):
        """Space-driven (spec 2026-06-07): with free slots (low pressure) the
        surplus is NOT overstock, so the goal is satisfied and value is 0 —
        even at 50 sap. The player uses its inventory; the per-item cap is no
        longer a space-blind dump trigger."""
        gd = _gd_with_sap_recipes()
        goal = DiscardOverstockGoal(game_data=gd)
        # Large inventory_max so pressure is low (50/200=25%): no overstock.
        state = make_state(level=1, inventory={"sap": 50}, inventory_max=200)
        assert goal.value(state, gd) == 0.0
        assert goal.is_satisfied(state) is True

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

    def test_relevant_actions_delete_when_only_buyer_is_dormant(self):
        """Buyer in price table but npc_location is None (dormant event merchant,
        spawn window closed) → Delete IS emitted.

        Pre-branch behaviour left the item untouched (treating any price-table
        buyer as protection), causing a permanent bag-full livelock because
        NpcSellAction.is_applicable also rejects buyers with None location.
        The fix: only a buyer with a non-None location prevents deletion."""
        gd = _gd_with_sap_recipes()
        gd._npc_sell_prices = {"event_merchant": {"sap": 2}}  # buyer in table
        gd._npc_locations = {}  # location NOT loaded → dormant
        goal = DiscardOverstockGoal(game_data=gd)
        state = make_state(level=1, inventory={"sap": 50})
        relevant = goal.relevant_actions([], state, gd)
        # Dormant buyer → Delete emitted so the slot is freed.
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


    def test_sellable_overstock_not_deleted(self):
        """A reachable-buyer overstock item is NOT deleted (NpcSellAction emitted
        instead). A truly-worthless item (no buyer, no GE order) IS deleted."""
        gd = GameData()
        gd._item_stats = {
            "junk": ItemStats(code="junk", level=1, type_="resource"),
            "rock": ItemStats(code="rock", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        # 'junk' has a reachable NPC buyer; 'rock' does not.
        gd._npc_sell_prices = {"vendor1": {"junk": 5}}
        gd._npc_locations = {"vendor1": (1, 2)}  # reachable now
        goal = DiscardOverstockGoal(game_data=gd)
        # Both items overstocked (no recipe use → cap 0; high inventory pressure).
        state = make_state(level=1,
                           inventory={"junk": 50, "rock": 50},
                           inventory_max=105)
        relevant = goal.relevant_actions([], state, gd)
        deleted_codes = {a.code for a in relevant if isinstance(a, DeleteItemAction)}
        # 'rock' has no buyer → Delete(rock) is emitted.
        assert "rock" in deleted_codes, "worthless rock must be deleted"
        # 'junk' has a reachable NPC buyer → NpcSellAction, never DeleteItemAction.
        assert "junk" not in deleted_codes, "sellable junk must not be deleted"

    def test_dormant_buyer_overstock_is_deleted(self):
        """Bank-full + the ONLY NPC buyer is a dormant event merchant (npc_location
        None) → Delete IS emitted, freeing the slot.

        Pre-branch: the old `not buyers` guard left the item untouched even when
        the only buyer was unreachable, causing a permanent bag-full livelock
        (SELL_RELIEF fired, but SellInventoryGoal produced an empty plan because
        NpcSellAction.is_applicable rejected npc_location=None; DISCARD refused
        to delete because `buyers` was truthy; bank full → DEPOSIT_FULL off).
        Fix: protect from deletion ONLY when npc_location is not None."""
        gd = GameData()
        gd._item_stats = {
            "festival_token": ItemStats(code="festival_token", level=1,
                                        type_="resource"),
        }
        gd._crafting_recipes = {}
        # Event merchant in price table but NOT in _npc_locations → dormant.
        gd._npc_sell_prices = {"event_merchant": {"festival_token": 10}}
        # No entry in _npc_locations → npc_location returns None.
        goal = DiscardOverstockGoal(game_data=gd)
        # inventory_max=55 → 50/55 ≈ 91% ≥ DISCARD_WATERMARK (0.85) → overstock detected.
        state = make_state(level=1,
                           inventory={"festival_token": 50},
                           inventory_max=55)
        relevant = goal.relevant_actions([], state, gd)
        assert len(relevant) == 1
        assert isinstance(relevant[0], DeleteItemAction)
        assert relevant[0].code == "festival_token"


class TestEquippableDominance:
    """Equippable cap drops to 0 when a strictly-better same-slot peer is
    owned — discard ladder picks the dominated item first."""

    def test_wooden_stick_dominated_by_copper_dagger(self):
        """Trace pattern: bot crafts copper_dagger (attack 12) but
        wooden_stick (attack 0) remains protected at EQUIPPABLE_KEEP=1.
        User asked: when forced to discard, drop the redundant one.
        Post-fix: dagger present → stick cap=0 → discard-eligible."""
        gd = GameData()
        gd._item_stats = {
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={}),
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                        attack={"fire": 12}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"wooden_stick": 1, "copper_dagger": 1})
        assert useful_quantity_cap("wooden_stick", state, gd) == 0, (
            "wooden_stick should be delete-eligible when copper_dagger is owned"
        )
        # And the dominator must stay protected.
        assert useful_quantity_cap("copper_dagger", state, gd) == 1

    def test_equipped_weapon_protected_from_discard_when_equipped(self):
        """Equipped items are floor-1 in useful_quantity_cap regardless of
        dominance — losing the item Robby is wearing is never OK."""
        gd = GameData()
        gd._item_stats = {
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={}),
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                        attack={"fire": 12}),
        }
        gd._crafting_recipes = {}
        state = make_state(
            inventory={"wooden_stick": 1, "copper_dagger": 1},
            equipment={"weapon_slot": "wooden_stick"},
        )
        # wooden_stick is EQUIPPED; useful_quantity_cap floor returns >=1.
        assert useful_quantity_cap("wooden_stick", state, gd) >= 1

    def test_tool_not_dominated_by_higher_attack_combat_weapon(self):
        """copper_pickaxe (weapon_slot, low attack, skill_effects[mining])
        is NOT dominated by copper_dagger (weapon_slot, attack 12, no
        skill_effects) because the dagger doesn't cover the pickaxe's
        mining bonus. Each must stay protected."""
        gd = GameData()
        gd._item_stats = {
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                        attack={"fire": 12}),
            "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                         attack={"fire": 3},
                                         skill_effects={"mining": -10}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"copper_dagger": 1, "copper_pickaxe": 1})
        assert useful_quantity_cap("copper_pickaxe", state, gd) == 1
        assert useful_quantity_cap("copper_dagger", state, gd) == 1

    def test_tool_dominates_lower_magnitude_same_skill_tool(self):
        """iron_pickaxe (mining -20) dominates copper_pickaxe (mining -10)
        when iron has higher equip_value too."""
        gd = GameData()
        gd._item_stats = {
            "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                         attack={"fire": 3},
                                         skill_effects={"mining": -10}),
            "iron_pickaxe": ItemStats(code="iron_pickaxe", level=5, type_="weapon",
                                       attack={"fire": 8},
                                       skill_effects={"mining": -20}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"copper_pickaxe": 1, "iron_pickaxe": 1})
        assert useful_quantity_cap("copper_pickaxe", state, gd) == 0, (
            "copper_pickaxe dominated by iron_pickaxe (higher attack + better mining)"
        )

    def test_no_dominance_when_peer_lower_equip_value(self):
        """copper_helmet (level 1, attack defense 5) is NOT dominated by
        wooden_helmet (defense 0). Strictly-higher equip_value required."""
        gd = GameData()
        gd._item_stats = {
            "wooden_helmet": ItemStats(code="wooden_helmet", level=1, type_="helmet",
                                        resistance={}),
            "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                        resistance={"fire": 5}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"wooden_helmet": 1, "copper_helmet": 1})
        # wooden_helmet dominated by copper.
        assert useful_quantity_cap("wooden_helmet", state, gd) == 0
        # copper_helmet has no dominator.
        assert useful_quantity_cap("copper_helmet", state, gd) == 1

    def test_dominance_considers_bank_items(self):
        """Banked copper_dagger should dominate inventory wooden_stick
        same as inventory copper_dagger would — owned via bank counts."""
        gd = GameData()
        gd._item_stats = {
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={}),
            "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                        attack={"fire": 12}),
        }
        gd._crafting_recipes = {}
        state = make_state(
            inventory={"wooden_stick": 1},
            bank_items={"copper_dagger": 1},
        )
        assert useful_quantity_cap("wooden_stick", state, gd) == 0


class TestEquippableDominanceArmorAndAccessories:
    """Dominance gate extended-coverage across all equippable categories
    (armor, shield, accessory) and across multi-slot types (ring,
    artifact, utility) where the dominator must own enough copies to
    fill every slot before the dominated item becomes redundant."""

    def test_armor_tier_dominance(self):
        """body_armor: iron (resistance 12) dominates copper (resistance 5)."""
        gd = GameData()
        gd._item_stats = {
            "copper_armor": ItemStats(code="copper_armor", level=1, type_="body_armor",
                                       resistance={"fire": 5}),
            "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor",
                                     resistance={"fire": 12}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"copper_armor": 1, "iron_armor": 1})
        assert useful_quantity_cap("copper_armor", state, gd) == 0
        assert useful_quantity_cap("iron_armor", state, gd) == 1

    def test_shield_tier_dominance(self):
        """shield: copper (resistance 5) dominates wooden (resistance 0)."""
        gd = GameData()
        gd._item_stats = {
            "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                        resistance={}),
            "copper_shield": ItemStats(code="copper_shield", level=1, type_="shield",
                                        resistance={"fire": 5}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"wooden_shield": 1, "copper_shield": 1})
        assert useful_quantity_cap("wooden_shield", state, gd) == 0

    def test_boots_tier_dominance(self):
        gd = GameData()
        gd._item_stats = {
            "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                       resistance={"fire": 4}),
            "iron_boots": ItemStats(code="iron_boots", level=5, type_="boots",
                                     resistance={"fire": 10}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"copper_boots": 1, "iron_boots": 1})
        assert useful_quantity_cap("copper_boots", state, gd) == 0

    def test_ring_multi_slot_one_better_does_not_dominate(self):
        """ring has TWO slots — bot wears 2 rings. 1 iron_ring + 1
        copper_ring: the copper is still needed to fill the 2nd slot.
        copper must NOT be dominated until 2+ iron_rings are owned."""
        gd = GameData()
        gd._item_stats = {
            "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                      attack={"fire": 3}),
            "iron_ring": ItemStats(code="iron_ring", level=5, type_="ring",
                                    attack={"fire": 8}),
        }
        gd._crafting_recipes = {}
        # Only 1 iron — bot still wants copper for ring2_slot.
        state = make_state(inventory={"copper_ring": 1, "iron_ring": 1})
        assert useful_quantity_cap("copper_ring", state, gd) == 1, (
            "copper_ring is the 2nd-best ring and the bot wears 2 rings; "
            "with only 1 iron_ring owned it can't yet dominate"
        )
        # Two irons — copper is now redundant.
        state2 = make_state(inventory={"copper_ring": 1, "iron_ring": 2})
        assert useful_quantity_cap("copper_ring", state2, gd) == 0, (
            "2 iron_rings can fill both ring slots; copper is dominated"
        )

    def test_artifact_multi_slot_dominance_requires_three(self):
        """artifact has THREE slots — need 3 dominator copies to flush."""
        gd = GameData()
        gd._item_stats = {
            "copper_artifact": ItemStats(code="copper_artifact", level=1, type_="artifact",
                                          attack={"fire": 2}),
            "iron_artifact": ItemStats(code="iron_artifact", level=5, type_="artifact",
                                        attack={"fire": 7}),
        }
        gd._crafting_recipes = {}
        # 2 irons — copper still needed for 3rd slot.
        state2 = make_state(inventory={"copper_artifact": 1, "iron_artifact": 2})
        assert useful_quantity_cap("copper_artifact", state2, gd) == 1
        # 3 irons — copper redundant.
        state3 = make_state(inventory={"copper_artifact": 1, "iron_artifact": 3})
        assert useful_quantity_cap("copper_artifact", state3, gd) == 0

    def test_amulet_single_slot_dominance(self):
        gd = GameData()
        gd._item_stats = {
            "copper_amulet": ItemStats(code="copper_amulet", level=1, type_="amulet",
                                        attack={"fire": 3}),
            "iron_amulet": ItemStats(code="iron_amulet", level=5, type_="amulet",
                                      attack={"fire": 8}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"copper_amulet": 1, "iron_amulet": 1})
        assert useful_quantity_cap("copper_amulet", state, gd) == 0

    def test_higher_tier_pickaxe_dominates_lower_tier_across_bank(self):
        """Tool dominance with the dominator banked — bot has copper_pickaxe
        equipped, iron_pickaxe in bank. copper still equipped (wrapper
        floor keeps it >= 1) but the dominance rule itself classifies it
        as dominated — once swapped to iron via OptimizeLoadout, the
        copper drops to inv and becomes discard-eligible."""
        gd = GameData()
        gd._item_stats = {
            "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                         attack={"fire": 3},
                                         skill_effects={"mining": -10}),
            "iron_pickaxe": ItemStats(code="iron_pickaxe", level=5, type_="weapon",
                                       attack={"fire": 8},
                                       skill_effects={"mining": -20}),
        }
        gd._crafting_recipes = {}
        # Equipped — wrapper floor keeps copper at >=1
        state = make_state(
            inventory={},
            bank_items={"iron_pickaxe": 1},
            equipment={"weapon_slot": "copper_pickaxe"},
        )
        assert useful_quantity_cap("copper_pickaxe", state, gd) >= 1
        # After hypothetical swap: iron equipped, copper in inv. Now copper is dominated.
        state2 = make_state(
            inventory={"copper_pickaxe": 1},
            equipment={"weapon_slot": "iron_pickaxe"},
        )
        assert useful_quantity_cap("copper_pickaxe", state2, gd) == 0


class TestDominanceEdgeCases:
    def test_not_dominated_when_item_has_no_stats(self):
        """An item with no game-data stats can't be reasoned about as
        equippable -> never dominated (line 102-103)."""
        gd = GameData()
        gd._item_stats = {}
        state = make_state(inventory={"unknown_item": 1})
        assert _is_equippable_dominated("unknown_item", state, gd) is False

    def test_not_dominated_when_item_type_has_no_slots(self):
        """A non-equippable type (no entry in ITEM_TYPE_TO_SLOTS) is never
        dominated (line 104-106)."""
        gd = GameData()
        gd._item_stats = {
            "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        }
        state = make_state(inventory={"copper_ore": 5})
        assert _is_equippable_dominated("copper_ore", state, gd) is False

    def test_peer_with_no_stats_is_skipped(self):
        """A peer code owned but absent from game data is skipped, so it can't
        count as a dominator (line 120-121); the item stays undominated."""
        gd = GameData()
        gd._item_stats = {
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={}),
            # ghost_weapon owned but has NO stats entry.
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"wooden_stick": 1, "ghost_weapon": 1})
        assert _is_equippable_dominated("wooden_stick", state, gd) is False

    def test_peer_in_different_slot_does_not_dominate(self):
        """A higher-value peer that fits a DIFFERENT slot can't substitute, so
        it isn't a dominator (line 122-125)."""
        gd = GameData()
        gd._item_stats = {
            "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                       attack={}),
            # A shield scores higher but occupies shield_slot, not weapon_slot.
            "iron_shield": ItemStats(code="iron_shield", level=5, type_="shield",
                                      attack={"fire": 99}),
        }
        gd._crafting_recipes = {}
        state = make_state(inventory={"wooden_stick": 1, "iron_shield": 1})
        assert _is_equippable_dominated("wooden_stick", state, gd) is False

    def test_overstocked_skips_zero_quantity_entries(self):
        """A zero-quantity inventory entry is skipped by overstocked_items
        (line 244-245) and never reported as excess."""
        gd = GameData()
        gd._item_stats = {
            "junk": ItemStats(code="junk", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        # junk has cap 0 (no recipe/task use) but qty 0 -> skipped entirely.
        state = make_state(inventory={"junk": 0})
        assert overstocked_items(state, gd) == {}


class TestPureCores:
    """P3b pure-core seams: the fuel-bounded chain demand and the
    extracted-from wrappers (mechanical extraction, Bridges4.lean)."""

    def test_chain_demand_pure_fuel_zero_base(self):
        """The fuel-0 base case answers 0 (unreachable from the wrappers:
        the `len(recipes) + 1` seed exceeds every path, which marks a
        distinct key per recursing frame — pinned in Lean as
        `chain_demand_fuel_zero`)."""
        assert _task_chain_demand_pure(0, "a", "b", 5, {}, {}) == 0

    def test_chain_demand_pure_visited_blocks_revisit(self):
        """A root already in the per-path visited map contributes 0 (the
        cycle guard — pinned in Lean as `chain_demand_visited_blocked`)."""
        recipes = {"b": {"a": 1}}
        assert _task_chain_demand_pure(3, "a", "b", 5, recipes, {"b": 1}) == 0

    def test_chain_demand_pure_target_hit_returns_quantity(self):
        """target == root short-circuits to the demanded quantity before the
        visited guard (pinned in Lean as `chain_demand_target_self`)."""
        assert _task_chain_demand_pure(1, "a", "a", 7, {}, {"a": 1}) == 7

    def test_excl_equipped_wrapper_omits_equipped_floor(self):
        """`useful_quantity_cap_excl_equipped` is the cap WITHOUT the
        equipped floor: an equipped no-demand item caps at 0 (the full cap
        floors it at 1)."""
        gd = GameData()
        gd._item_stats = {
            "trinket": ItemStats(code="trinket", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        state = make_state(equipment={"weapon_slot": "trinket"})
        assert useful_quantity_cap_excl_equipped("trinket", state, gd) == 0
        assert useful_quantity_cap("trinket", state, gd) == 1

    def test_is_dominated_pure_threshold_boundary(self):
        """The dominance fold credits only fully-qualifying peers and
        compares the total to the slot count once (order-independent; the
        hand model's `isDominatedBy`)."""
        # One criterion false anywhere -> no credit.
        assert _is_dominated_pure([(False, True, True, 5)], 1) is False
        assert _is_dominated_pure([(True, False, True, 5)], 1) is False
        assert _is_dominated_pure([(True, True, False, 5)], 1) is False
        # Credits sum across peers; threshold is >=.
        assert _is_dominated_pure([(True, True, True, 1), (True, True, True, 1)], 2) is True
        assert _is_dominated_pure([(True, True, True, 1)], 2) is False


def _gem_gd() -> GameData:
    """A gemstone (cut at mining@20) and a near-term bar (mining@1)."""
    gd = GameData()
    gd._item_stats = {
        "topaz_stone": ItemStats(code="topaz_stone", level=20, type_="resource"),
        "topaz": ItemStats(code="topaz", level=20, type_="resource",
                           crafting_skill="mining", crafting_level=20),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
    }
    gd._crafting_recipes = {"topaz": {"topaz_stone": 24}, "copper_bar": {"copper_ore": 10}}
    return gd


def test_reachable_recipe_demand_zeroes_skill_gated_material():
    """topaz_stone's only consumer (topaz) needs mining@20; a mining-10 bot can't
    reach it, so its near-term demand is 0 (deposit-eligible). copper_ore's
    consumer (copper_bar) is mining@1 — reachable — so its demand is unchanged."""
    gd = _gem_gd()
    low = make_state(skills={"mining": 10})
    assert reachable_recipe_demand("topaz_stone", low, gd) == 0
    assert reachable_recipe_demand("copper_ore", low, gd) == gd.max_recipe_demand("copper_ore")
    assert gd.max_recipe_demand("copper_ore") > 0  # sanity: the reachable one is non-zero


def test_reachable_recipe_demand_returns_full_once_skill_in_reach():
    """At mining 20 (>= 20) the topaz recipe is reachable, so topaz_stone's full
    transitive demand returns — keep them for cutting, no longer deposit-bait."""
    gd = _gem_gd()
    high = make_state(skills={"mining": 20})
    assert reachable_recipe_demand("topaz_stone", high, gd) == gd.max_recipe_demand("topaz_stone")
    assert gd.max_recipe_demand("topaz_stone") > 0
    # within the +2 horizon: mining 18 already counts as reachable
    near = make_state(skills={"mining": 18})
    assert reachable_recipe_demand("topaz_stone", near, gd) == gd.max_recipe_demand("topaz_stone")


def test_skill_gated_material_keeps_none_for_low_level_bot():
    """The end effect: a low-level bot's useful_quantity_cap for the gemstone is
    0 (keep none — fully bank-eligible under pressure; the SAFETY_FLOOR only
    applies to items with reachable recipe use), while a skilled bot keeps the
    full batch cap so the gems aren't shed once they're usable."""
    gd = _gem_gd()
    low = make_state(skills={"mining": 10})
    assert useful_quantity_cap("topaz_stone", low, gd) == 0
    high = make_state(skills={"mining": 20})
    assert useful_quantity_cap("topaz_stone", high, gd) > SAFETY_FLOOR


def test_skill_gated_gem_is_overstock_under_pressure_reachable_material_protected():
    """End-to-end: under real space pressure a low-level bot's unusable gemstones
    are flagged overstock (-> banked, keeping the bag lean) while a near-term
    reachable material stays protected by its cap."""
    gd = _gem_gd()
    full = make_state(
        skills={"mining": 10},
        inventory={"topaz_stone": 15, "copper_ore": 5},
        inventory_max=20,  # 20/20 used -> above the 0.85 watermark
    )
    excess = overstocked_items(full, gd)
    assert excess.get("topaz_stone") == 15  # all gems sheddable (deposit-eligible)
    assert "copper_ore" not in excess       # reachable material protected by its cap
