"""Tests for UnequipAction, RecycleAction, NpcBuyAction, and GameData NPC support."""

from unittest.mock import MagicMock, patch

import pytest
from artifactsmmo_api_client.models.map_content_type import MapContentType
from artifactsmmo_api_client.models.map_layer import MapLayer
from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOT
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._resource_locations = {}
    gd._workshop_locations = kwargs.get("workshop_locs", {})
    gd._bank_location = (4, 0)
    gd._item_stats = kwargs.get("item_stats", {})
    gd._crafting_recipes = kwargs.get("recipes", {})
    gd._resource_skill = {}
    gd._monster_level = {}
    gd._npc_locations = kwargs.get("npc_locations", {})
    gd._npc_stock = kwargs.get("npc_stock", {})
    return gd


def make_full_equipment() -> dict[str, str | None]:
    return {slot: None for slot in ITEM_TYPE_TO_SLOT.values()}


class TestUnequipAction:
    def test_repr(self):
        assert repr(UnequipAction(slot="weapon_slot")) == "Unequip(weapon_slot)"

    def test_not_applicable_when_slot_empty(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        state = make_state(equipment=equipment)
        assert action.is_applicable(state, make_gd()) is False

    def test_applicable_when_slot_occupied(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment)
        assert action.is_applicable(state, make_gd()) is True

    def test_apply_returns_item_to_inventory(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment, inventory={})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory.get("copper_dagger") == 1
        assert new_state.equipment["weapon_slot"] is None

    def test_apply_accumulates_with_existing_inventory(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(equipment=equipment, inventory={"copper_dagger": 1})
        new_state = action.apply(state, make_gd())
        assert new_state.inventory["copper_dagger"] == 2

    def test_cost_is_1(self):
        action = UnequipAction(slot="weapon_slot")
        assert action.cost(make_state(), make_gd()) == pytest.approx(1.0)

    def test_execute_calls_api(self):
        action = UnequipAction(slot="weapon_slot")
        equipment = make_full_equipment()
        equipment["weapon_slot"] = "copper_dagger"
        char = make_char_schema()
        state = make_state(equipment=equipment)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.unequip.action_unequip",
                   return_value=make_api_result(char)) as mock_api:
            action.execute(state, client)
        mock_api.assert_called_once()


class TestRecycleAction:
    def test_repr(self):
        assert repr(RecycleAction(code="copper_dagger", quantity=2)) == "Recycle(copper_dagger×2)"

    def test_not_applicable_without_workshop(self):
        action = RecycleAction(code="copper_dagger", workshop_location=None)
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_item_not_in_inventory(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_without_recipe(self):
        action = RecycleAction(code="wooden_stick", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="wooden_stick", level=1, type_="weapon")
        state = make_state(inventory={"wooden_stick": 1})
        gd = make_gd(item_stats={"wooden_stick": stats}, recipes={})
        assert action.is_applicable(state, gd) is False

    def test_applicable_when_in_inventory_with_recipe(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is True

    def test_not_applicable_when_stats_missing_crafting_skill(self):
        # Phase 8: server requires the crafting skill metadata to recycle.
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")  # crafting_skill=None
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_skill_below_required_level(self):
        # Phase 8: skill check mirrors CraftAction. Was missing pre-fix.
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=10)
        state = make_state(inventory={"copper_dagger": 1})  # weaponcrafting=1 in default
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_inventory_full_for_recovered_materials(self):
        # Phase 8: slot-floor check. Pre-fix, apply minted materials into a
        # full bag and overflowed inventory_max (probe: used=22, max=20).
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        # Recipe yields 3 ore (net = +2). Full bag has 0 free slots → must refuse.
        state = make_state(inventory={"copper_dagger": 1, "pad": 19})  # used=20, free=0
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.is_applicable(state, gd) is False

    def test_apply_removes_item_and_returns_materials(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        new_state = action.apply(state, gd)
        assert "copper_dagger" not in new_state.inventory
        # 6 // 2 = 3 copper_ore returned
        assert new_state.inventory.get("copper_ore", 0) == 3

    def test_apply_minimum_one_material_returned(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon")
        state = make_state(inventory={"copper_dagger": 1})
        # Recipe with qty=1: max(1, 1//2) = 1
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 1}})
        new_state = action.apply(state, gd)
        assert new_state.inventory.get("copper_ore", 0) == 1

    def test_cost_includes_distance(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        state = make_state(x=0, y=0)
        gd = make_gd()
        assert action.cost(state, gd) == pytest.approx(3.0 + 5)

    def test_execute_moves_to_workshop_then_recycles(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        char = make_char_schema()
        state = make_state(x=0, y=0, inventory={"copper_dagger": 1})
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.recycle.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=5, y=0, inventory={"copper_dagger": 1})
            with patch("artifactsmmo_cli.ai.actions.recycle.action_recycling",
                       return_value=make_api_result(char)) as mock_recycle:
                action.execute(state, client)
        MockMove.assert_called_once_with(x=5, y=0)
        mock_recycle.assert_called_once()

    def test_recycle_blocked_when_it_would_breach_the_bag_floor(self):
        # The working copper_axe alone in the bag, 17 in the bank. bag_floor=1
        # means the LAST BAG COPY IS UNREACHABLE -- GOAP must withdraw first.
        action = RecycleAction(code="copper_axe", quantity=1, workshop_location=(2, 1), bag_floor=1)
        stats = ItemStats(code="copper_axe", level=1, type_="tool",
                          crafting_skill="gearcrafting", crafting_level=1)
        state = make_state(inventory={"copper_axe": 1}, bank_items={"copper_axe": 17})
        gd = make_gd(item_stats={"copper_axe": stats}, recipes={"copper_axe": {"copper": 6}})
        assert action.is_applicable(state, gd) is False

    def test_recycle_allowed_once_a_bank_copy_is_withdrawn(self):
        # After Withdraw, the bag holds 2: recycling one still leaves the floor.
        action = RecycleAction(code="copper_axe", quantity=1, workshop_location=(2, 1), bag_floor=1)
        stats = ItemStats(code="copper_axe", level=1, type_="tool",
                          crafting_skill="gearcrafting", crafting_level=1)
        state = make_state(inventory={"copper_axe": 2}, bank_items={"copper_axe": 16})
        gd = make_gd(item_stats={"copper_axe": stats}, recipes={"copper_axe": {"copper": 6}})
        assert action.is_applicable(state, gd) is True

    def test_recycle_bag_floor_defaults_to_zero(self):
        # Default 0 preserves every existing call site's behavior exactly.
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon", crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats}, recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.bag_floor == 0
        assert action.is_applicable(state, gd) is True

    # --- owned_floor: the PER-APPLICATION half of the destruction licence ---
    # (whole-branch review, CRITICAL 1). `licensed_recycle_quantity` admits a
    # quantity=1 action ONCE; only a floor carried on the action bounds how many
    # times a plan APPLIES it. `bag_floor` cannot: for a spare unequipped
    # equippable, keep_in_bag == 0 while keep_owned >= 1.

    def test_recycle_blocked_when_it_would_breach_the_owned_floor(self):
        # The LAST owned copy (bag+bank) may not cease to exist: keep_owned=1.
        action = RecycleAction(code="copper_ring", quantity=1, workshop_location=(5, 0),
                               owned_floor=1)
        stats = ItemStats(code="copper_ring", level=1, type_="ring",
                          crafting_skill="jewelrycrafting", crafting_level=1)
        state = make_state(inventory={"copper_ring": 1}, bank_items={},
                           skills={"jewelrycrafting": 5})
        gd = make_gd(item_stats={"copper_ring": stats},
                     recipes={"copper_ring": {"copper_bar": 6}})
        assert action.is_applicable(state, gd) is False

    def test_owned_floor_counts_BANK_copies(self):
        # owned = bag + bank, the same dimension `destroyable` is about: the bank
        # copy satisfies the keep, so the bag copy is destroyable. A bag-only
        # `owned` would refuse this and make the licensed recycle unplannable.
        action = RecycleAction(code="copper_ring", quantity=1, workshop_location=(5, 0),
                               owned_floor=1)
        stats = ItemStats(code="copper_ring", level=1, type_="ring",
                          crafting_skill="jewelrycrafting", crafting_level=1)
        state = make_state(inventory={"copper_ring": 1}, bank_items={"copper_ring": 1},
                           skills={"jewelrycrafting": 5})
        gd = make_gd(item_stats={"copper_ring": stats},
                     recipes={"copper_ring": {"copper_bar": 6}})
        assert action.is_applicable(state, gd) is True

    def test_owned_floor_bounds_a_BATCH_quantity_too(self):
        # 3 owned, floor 1: a batch of 2 is the most that may die; 3 is refused.
        stats = ItemStats(code="copper_ring", level=1, type_="ring",
                          crafting_skill="jewelrycrafting", crafting_level=1)
        state = make_state(inventory={"copper_ring": 3}, bank_items={},
                           skills={"jewelrycrafting": 5},
                           inventory_max=100, inventory_slots_max=20)
        gd = make_gd(item_stats={"copper_ring": stats},
                     recipes={"copper_ring": {"copper_bar": 6}})
        ok = RecycleAction(code="copper_ring", quantity=2, workshop_location=(5, 0),
                           owned_floor=1)
        too_many = RecycleAction(code="copper_ring", quantity=3, workshop_location=(5, 0),
                                 owned_floor=1)
        assert ok.is_applicable(state, gd) is True
        assert too_many.is_applicable(state, gd) is False

    def test_recycle_owned_floor_defaults_to_zero(self):
        action = RecycleAction(code="copper_dagger", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                          crafting_skill="weaponcrafting")
        state = make_state(inventory={"copper_dagger": 1})
        gd = make_gd(item_stats={"copper_dagger": stats},
                     recipes={"copper_dagger": {"copper_ore": 6}})
        assert action.owned_floor == 0
        assert action.is_applicable(state, gd) is True

    # --- slot-awareness (whole-branch review, IMPORTANT 3) ---

    def test_recycle_refused_when_the_minted_stack_has_no_SLOT(self):
        # Bag slot-full but quantity-free: 7 fishing_nets, so the SOURCE STACK
        # SURVIVES the recycle (0 slots freed) while the recipe mints ash_plank as
        # a NEW stack -> server HTTP 497. `inventory_free` (the QUANTITY dimension)
        # is blind to this and said True; `inventory_room.has_room` is not.
        action = RecycleAction(code="fishing_net", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="fishing_net", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(inventory={"fishing_net": 7, "a": 1, "b": 1},
                           inventory_max=100, inventory_slots_max=3)
        gd = make_gd(item_stats={"fishing_net": stats},
                     recipes={"fishing_net": {"ash_plank": 4}})
        assert state.inventory_free > 0  # quantity headroom exists...
        assert state.inventory_slots_free == 0  # ...but no SLOT does
        assert action.is_applicable(state, gd) is False

    def test_recycle_allowed_when_the_exhausted_source_slot_pays_for_the_mint(self):
        # The mirror: the last fishing_net's slot IS freed by this recycle, so the
        # minted ash_plank stack has somewhere to go. Not over-refusing is the
        # other half of the property.
        action = RecycleAction(code="fishing_net", quantity=1, workshop_location=(5, 0))
        stats = ItemStats(code="fishing_net", level=1, type_="weapon",
                          crafting_skill="weaponcrafting", crafting_level=1)
        state = make_state(inventory={"fishing_net": 1, "a": 1, "b": 1},
                           inventory_max=100, inventory_slots_max=3)
        gd = make_gd(item_stats={"fishing_net": stats},
                     recipes={"fishing_net": {"ash_plank": 4}})
        assert state.inventory_slots_free == 0
        assert action.is_applicable(state, gd) is True


class TestNpcBuyAction:
    def test_repr(self):
        assert repr(NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=3)) == \
            "NpcBuy(cooked_chicken×3@cook)"

    def test_not_applicable_without_npc_location(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=None)
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_npc_does_not_sell_item(self):
        action = NpcBuyAction(npc_code="cook", item_code="mystery_item", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 50}})
        state = make_state(gold=10)
        assert action.is_applicable(state, gd) is False

    def test_applicable_when_enough_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100)
        assert action.is_applicable(state, gd) is True

    def test_apply_deducts_gold_and_adds_item(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=2, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 10}})
        state = make_state(gold=100, inventory={})
        new_state = action.apply(state, gd)
        assert new_state.gold == 80  # 100 - 2 * 10
        assert new_state.inventory.get("cooked_chicken") == 2

    def test_item_currency_applicable_with_enough_currency_ignores_gold(self):
        """Task #12: a rune sold for sandwhisper_coin is gated on the COIN stack,
        not gold — applicable at 0 gold when the coins are on hand."""
        action = NpcBuyAction(npc_code="trader", item_code="vampiric_rune", quantity=1, npc_location=(3, 3))
        gd = make_gd(npc_stock={"trader": {"vampiric_rune": 100}})
        gd._npc_buy_currency = {"trader": {"vampiric_rune": "sandwhisper_coin"}}
        state = make_state(gold=0, inventory={"sandwhisper_coin": 100}, inventory_max=200)
        assert action.is_applicable(state, gd) is True

    def test_item_currency_not_applicable_without_enough_currency(self):
        """Rich in gold, poor in the pay currency → not applicable (the pre-#12
        bug would have wrongly accepted it on the gold balance)."""
        action = NpcBuyAction(npc_code="trader", item_code="vampiric_rune", quantity=1, npc_location=(3, 3))
        gd = make_gd(npc_stock={"trader": {"vampiric_rune": 100}})
        gd._npc_buy_currency = {"trader": {"vampiric_rune": "sandwhisper_coin"}}
        state = make_state(gold=1_000_000, inventory={"sandwhisper_coin": 50}, inventory_max=200)
        assert action.is_applicable(state, gd) is False

    def test_item_currency_not_applicable_when_no_free_slot(self):
        """Item-currency purchase still needs a free slot for the bought item:
        coins on hand but a full bag must refuse."""
        action = NpcBuyAction(npc_code="trader", item_code="vampiric_rune", quantity=1, npc_location=(3, 3))
        gd = make_gd(npc_stock={"trader": {"vampiric_rune": 100}})
        gd._npc_buy_currency = {"trader": {"vampiric_rune": "sandwhisper_coin"}}
        state = make_state(gold=0, inventory={"sandwhisper_coin": 100}, inventory_max=100)  # free=0
        assert action.is_applicable(state, gd) is False

    def test_apply_item_currency_consumes_currency_not_gold(self):
        """apply draws the currency stack down by price*quantity and leaves gold
        untouched (the server deducts the currency; the projection must match)."""
        action = NpcBuyAction(npc_code="trader", item_code="vampiric_rune", quantity=1, npc_location=(3, 3))
        gd = make_gd(npc_stock={"trader": {"vampiric_rune": 100}})
        gd._npc_buy_currency = {"trader": {"vampiric_rune": "sandwhisper_coin"}}
        state = make_state(gold=500, inventory={"sandwhisper_coin": 150}, inventory_max=200)
        new_state = action.apply(state, gd)
        assert new_state.gold == 500                               # gold untouched
        assert new_state.inventory["sandwhisper_coin"] == 50       # 150 - 100
        assert new_state.inventory.get("vampiric_rune") == 1

    def test_cost_item_currency_has_no_gold_term(self):
        """An item-currency purchase spends no gold, so cost omits the gold term
        (a gold purchase at price 100 would add 100/10 = 10)."""
        action = NpcBuyAction(npc_code="trader", item_code="vampiric_rune", quantity=1, npc_location=(0, 0))
        gd = make_gd(npc_stock={"trader": {"vampiric_rune": 100}})
        gd._npc_buy_currency = {"trader": {"vampiric_rune": "sandwhisper_coin"}}
        state = make_state(gold=0, inventory={"sandwhisper_coin": 100}, inventory_max=200)
        assert action.cost(state, gd) == 2.0

    def test_not_applicable_when_insufficient_inventory_slots(self):
        """REAL BUG #6 regression-pin: pre-fix is_applicable lacked the slot
        check, so apply minted past inventory_max. Post-fix the slot floor
        catches the verified counterexample (inventory_used=9, inventory_max=10,
        quantity=5 — would overflow by 4)."""
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 1}})
        # used=9 (filler), max=10 → only 1 free slot, quantity=5 → must refuse.
        state = make_state(gold=1000, inventory={"filler": 9}, inventory_max=10)
        assert action.is_applicable(state, gd) is False

    def test_applicable_at_quantity_equals_free_boundary(self):
        """Boundary: quantity == inventory_free is accepted (post-fix)."""
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 1}})
        state = make_state(gold=1000, inventory={"filler": 5}, inventory_max=10)
        assert action.is_applicable(state, gd) is True

    def test_apply_asserts_on_precondition_bypass(self):
        """Defense in depth: apply() asserts the slot precondition before
        mutating. If a caller bypasses is_applicable (planner bug, manual
        invocation) the action crashes loudly rather than silently overflowing
        the inventory cap. Phase-3 OptimizeLoadout-shape."""
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=5, npc_location=(2, 1))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 1}})
        state = make_state(gold=1000, inventory={"filler": 9}, inventory_max=10)
        # is_applicable would return False (slot floor), but if a caller skips
        # that check, apply() raises with a clear diagnostic.
        with pytest.raises(AssertionError, match="is_applicable invariant violated"):
            action.apply(state, gd)

    def test_cost_includes_distance_and_gold(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(4, 0))
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 100}})
        state = make_state(x=0, y=0)
        # 2 + dist(4) + 100*1/10 = 2 + 4 + 10 = 16
        assert action.cost(state, gd) == pytest.approx(16.0)

    def test_execute_moves_and_calls_api(self):
        action = NpcBuyAction(npc_code="cook", item_code="cooked_chicken", quantity=1, npc_location=(2, 1))
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=100)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.npc.MoveAction") as MockMove:
            move_instance = MockMove.return_value
            move_instance.execute.return_value = make_state(x=2, y=1, gold=100)
            with patch("artifactsmmo_cli.ai.actions.npc.action_npc_buy",
                       return_value=make_api_result(char)) as mock_buy:
                action.execute(state, client)
        MockMove.assert_called_once_with(x=2, y=1)
        mock_buy.assert_called_once()


class TestGameDataNpcSupport:
    def test_npc_location_returns_location(self):
        gd = make_gd(npc_locations={"cook": (2, 1)})
        assert gd.npc_location("cook") == (2, 1)

    def test_npc_location_returns_none_for_unknown(self):
        gd = make_gd()
        assert gd.npc_location("unknown") is None

    def test_npc_sells_item_returns_price(self):
        gd = make_gd(npc_stock={"cook": {"cooked_chicken": 42}})
        assert gd.npc_sells_item("cook", "cooked_chicken") == 42

    def test_npc_sells_item_returns_none_when_missing(self):
        gd = make_gd(npc_stock={"cook": {}})
        assert gd.npc_sells_item("cook", "mystery") is None

    def test_npcs_selling_item_sorted_by_price(self):
        gd = make_gd(npc_stock={"cook": {"bread": 20}, "baker": {"bread": 10}})
        result = gd.npcs_selling_item("bread")
        assert result == [("baker", 10), ("cook", 20)]

    def test_npcs_selling_item_empty_when_none_sell(self):
        gd = make_gd(npc_stock={"cook": {"bread": 10}})
        assert gd.npcs_selling_item("mystery") == []

    def test_load_npcs_indexes_stock(self):
        gd = GameData()
        entry = MagicMock()
        entry.code = "cooked_chicken"
        entry.npc = "cook"
        entry.buy_price = 10

        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=MagicMock(data=[entry])):
            gd._load_npcs(MagicMock())

        assert gd._npc_stock["cook"]["cooked_chicken"] == 10

    def test_load_npcs_skips_null_buy_price(self):
        gd = GameData()
        entry = MagicMock()
        entry.code = "mystery_item"
        entry.npc = "cook"
        entry.buy_price = UNSET

        with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=MagicMock(data=[entry])):
            gd._load_npcs(MagicMock())

        assert "cook" not in gd._npc_stock

    def test_load_maps_indexes_npc_location(self):
        gd = GameData()
        tile = MagicMock()
        tile.x = 2
        tile.y = 1
        tile.layer = MapLayer.OVERWORLD
        tile.interactions.content.type_ = MapContentType.NPC
        tile.interactions.content.code = "cook"

        with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=MagicMock(data=[tile])):
            gd._load_maps(MagicMock())

        assert gd._npc_locations["cook"] == (2, 1)
