"""Tests for SellInventoryGoal.

Satisfaction is the KEEP AUTHORITY's licence being spent, not a free-space
fraction (item-protection-authority epic, Task 8): the goal is unsatisfied
exactly while it can build an authority-licensed, executable NpcSell.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.sell_inventory import (
    ACCUM_BASE,
    ACCUM_STEP,
    DISCRETIONARY_CEIL,
    MAX_SELL_DEPTH,
    SellInventoryGoal,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from tests.test_ai.fixtures import make_state

CTX = NO_PROFILE_CONTEXT


def _gd_with_buyer() -> GameData:
    """GameData with a permanent NPC buyer for wooden_shield (tradeable, level 1 shield)."""
    gd = GameData()
    gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
    gd._npc_locations = {"vendor": (1, 1)}
    gd._item_stats = {
        "wooden_shield": ItemStats(
            code="wooden_shield", level=1, type_="shield",
            crafting_skill="gearcrafting", crafting_level=1, tradeable=True,
        )
    }
    gd._crafting_recipes = {}
    return gd


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._npc_sell_prices = kwargs.get("npc_sell_prices", {})
    gd._npc_locations = kwargs.get("npc_locations", {})
    return gd


def _goal(gd: GameData, bank_accessible: bool = True,
          relief: bool = False) -> SellInventoryGoal:
    return SellInventoryGoal(game_data=gd, ctx=CTX,
                             bank_accessible=bank_accessible, relief=relief)


class TestSellInventoryGoal:
    def test_value_zero_when_bank_accessible_and_no_accumulation(self):
        """Bank accessible and item count below the ratio gate -> value 0."""
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}}, npc_locations={"cook": (2, 1)})
        goal = _goal(gd)
        # 4 chickens: below ACCUM_MULT * eff_keep (5*0->1); nothing to sell -> satisfied
        state = make_state(inventory={"chicken": 4}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_zero_when_no_sellable_items(self):
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}}, npc_locations={"cook": (2, 1)})
        goal = _goal(gd, bank_accessible=False)
        state = make_state(inventory={"useless_thing": 20}, inventory_max=20)
        assert goal.value(state, gd) == 0.0

    def test_value_scales_with_inventory_fill_when_locked_and_has_sellable(self):
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}}, npc_locations={"cook": (2, 1)})
        goal = _goal(gd, bank_accessible=False)
        # 18 chickens, keep 0 (no recipe, not equippable) -> 18 licensed, gate cleared.
        state = make_state(inventory={"chicken": 18}, inventory_max=20)
        # used=18/max=20 = 0.9; * 100 = 90 (beats the accumulation ramp)
        assert goal.value(state, gd) == 90.0

    def test_value_caps_at_100_at_full(self):
        gd = make_gd(npc_sell_prices={"cook": {"chicken": 5}}, npc_locations={"cook": (2, 1)})
        goal = _goal(gd, bank_accessible=False)
        state = make_state(inventory={"chicken": 20}, inventory_max=20)
        assert goal.value(state, gd) == 100.0

    def test_is_satisfied_when_nothing_is_licensed_for_sale(self):
        """A bag holding only its keep — no licence, nothing to do."""
        gd = _gd_with_buyer()
        goal = _goal(gd, bank_accessible=False)
        # 1 shield: EQUIPPABLE keep 1 -> 0 licensed.
        state = make_state(inventory={"wooden_shield": 1}, inventory_max=20)
        assert goal.is_satisfied(state) is True

    def test_is_not_satisfied_while_a_licensed_sale_exists(self):
        gd = _gd_with_buyer()
        goal = _goal(gd, bank_accessible=False)
        state = make_state(inventory={"wooden_shield": 18}, inventory_max=20)
        assert goal.is_satisfied(state) is False

    def test_is_satisfied_in_a_slot_full_but_quantity_roomy_bag_only_when_unlicensed(self):
        """The census shape (19/20 SLOTS, 29/116 QUANTITY): the old space-based
        rule called this SATISFIED and no-op'd a fired SELL_RELIEF guard. The
        authority's licence is what decides now."""
        gd = _gd_with_buyer()
        state = make_state(inventory={"wooden_shield": 11}, inventory_max=116,
                           inventory_slots_max=20)
        assert _goal(gd, relief=True).is_satisfied(state) is False

    def test_relevant_actions_are_only_the_licensed_sells(self):
        """The pre-built factory action set is NOT admitted — no Rest, no Fight,
        and no unprotected quantity-1 sale of a held item."""
        gd = _gd_with_buyer()
        goal = _goal(gd)
        state = make_state(inventory={"wooden_shield": 14, "useless": 1})
        actions = [
            RestAction(),
            FightAction(monster_code="goblin", locations=frozenset({(1, 1)})),
            NpcSellAction(npc_code="vendor", item_code="wooden_shield", quantity=1,
                          npc_location=(1, 1)),
            NpcSellAction(npc_code="vendor", item_code="not_in_inventory", quantity=1,
                          npc_location=(1, 1)),
        ]
        relevant = goal.relevant_actions(actions, state, gd)
        assert [repr(a) for a in relevant] == ["NpcSell(wooden_shield×13@vendor)"]

    def test_desired_state_is_the_licence_spent(self):
        goal = _goal(_gd_with_buyer())
        state = make_state(inventory={"wooden_shield": 18}, inventory_max=20)
        assert goal.desired_state(state, GameData()) == {"sellable_surplus_sold": True}

    def test_max_depth_admits_one_sell_per_stack(self):
        assert _goal(GameData()).max_depth == MAX_SELL_DEPTH == 64

    def test_repr(self):
        assert repr(_goal(GameData())) == "SellInventory"


class TestSellInventoryAccumulation:
    """Idle sell-down when accumulated multiples exceed the authority's keep."""

    def test_value_positive_unpressured_when_accumulated(self):
        """14 wooden_shields, keep 1 → steps=3 → min(18+9, 48) = 27.0 regardless
        of bank access — and the goal is NOT satisfied, so it can actually act
        (the old space-based rule reported satisfied and the sell never ran)."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        goal = _goal(gd)
        assert goal.is_satisfied(state) is False
        expected = min(ACCUM_BASE + 3 * ACCUM_STEP, 48.0)  # min(27.0, 48.0) = 27.0
        assert goal.value(state, gd) == expected

    def test_value_tops_discretionary_band_when_severe(self):
        """40 wooden_shields → steps=5 == SEVERE_STEPS → value jumps to the
        discretionary ceiling (48), still strictly below progression (50)."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 40}, inventory_max=200)
        goal = _goal(gd)
        assert goal.value(state, gd) == DISCRETIONARY_CEIL
        assert DISCRETIONARY_CEIL < 50.0

    def test_value_zero_when_below_accum_threshold(self):
        """Held below ACCUM_MULT * keep → the ratio gate holds it back; with a bank
        route open there is nothing to sell, so the goal is satisfied at value 0."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 4}, inventory_max=50)
        goal = _goal(gd)
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_relief_lifts_the_ratio_gate(self):
        """Bank full / locked (GuardKind.SELL_RELIEF): the ratio gate's whole point
        is "bank it instead", so with no bank route the WHOLE licence is offered —
        4 shields keep 1, sell 3."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 4}, inventory_max=50)
        goal = _goal(gd, relief=True)
        assert goal.is_satisfied(state) is False
        sells = [a for a in goal.relevant_actions([], state, gd)
                 if isinstance(a, NpcSellAction)]
        assert len(sells) == 1 and sells[0].quantity == 3

    def test_relief_sell_below_the_ratio_gate_carries_no_accumulation_urgency(self):
        """Relief mode is the only way to be UNSATISFIED with `steps == 0`: the
        licence is real but the hoard ratio is not, so the accumulation term is 0
        and the value falls back to the bank-locked / window terms (both 0 here).
        The guard, not the value, is what selects it."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 4}, inventory_max=50)
        goal = _goal(gd, relief=True)
        assert goal.is_satisfied(state) is False
        assert goal.value(state, gd) == 0.0

    def test_satisfied_when_no_accumulation_and_nothing_licensed(self):
        """1 shield (at the keep) → satisfied and value 0.0."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 1}, inventory_max=50)
        goal = _goal(gd)
        assert goal.is_satisfied(state) is True
        assert goal.value(state, gd) == 0.0

    def test_relevant_actions_sell_down_to_the_authority_keep(self):
        """14 shields → one NpcSellAction with quantity 13 (keep the 1 the
        authority protects)."""
        gd = _gd_with_buyer()
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        acts = _goal(gd).relevant_actions([], state, gd)
        sells = [a for a in acts if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
        assert len(sells) == 1
        assert sells[0].quantity == 13

    def test_relevant_actions_picks_reachable_buyer_when_top_price_dormant(self):
        """The highest-price buyer is a dormant event merchant (no location); the
        sell still emits via the lower-price REACHABLE buyer, not skipped."""
        gd = GameData()
        # dormant pays 9 (no tile); reachable_vendor pays 2 (has a tile).
        gd._npc_sell_prices = {"dormant": {"wooden_shield": 9},
                               "reachable_vendor": {"wooden_shield": 2}}
        gd._npc_locations = {"reachable_vendor": (3, 4)}  # dormant absent → None
        gd._item_stats = {"wooden_shield": ItemStats(
            code="wooden_shield", level=1, type_="shield", tradeable=True)}
        gd._crafting_recipes = {}
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        sells = [a for a in _goal(gd).relevant_actions([], state, gd)
                 if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
        assert len(sells) == 1
        assert sells[0].npc_code == "reachable_vendor"
        assert sells[0].quantity == 13

    def test_no_sell_and_satisfied_when_the_only_buyer_is_an_unplaced_npc(self):
        """No location → no executable sale → nothing to plan, so SATISFIED (an
        unsatisfied goal with no action is a doomed-memo pollutant)."""
        gd = GameData()
        gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
        # no _npc_locations entry for "vendor" → npc_location returns None
        gd._item_stats = {
            "wooden_shield": ItemStats(
                code="wooden_shield", level=1, type_="shield",
                crafting_skill="gearcrafting", crafting_level=1, tradeable=True,
            )
        }
        gd._crafting_recipes = {}
        state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
        goal = _goal(gd)
        assert goal.relevant_actions([], state, gd) == []
        assert goal.is_satisfied(state) is True

    def test_value_zero_when_inventory_max_zero(self):
        """inventory_max == 0 edge case -> value 0.0 (no division by zero)."""
        gd = _gd_with_buyer()
        state = make_state(inventory={}, inventory_max=0)
        goal = _goal(gd, bank_accessible=False)
        assert goal.value(state, gd) == 0.0
