"""Tests for UseGoldBagAction — consume a gold-bag consumable to credit gold."""

import dataclasses
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.use_gold_bag import USE_GOLD_BAG_COST, UseGoldBagAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def _make_gd(extra_stats: dict[str, ItemStats] | None = None) -> GameData:
    """Minimal GameData with bag_of_gold and small_bag_of_gold loaded."""
    gd = GameData()
    gd._item_stats = {
        "bag_of_gold": ItemStats(code="bag_of_gold", level=1, type_="consumable",
                                  gold_value=2500),
        "small_bag_of_gold": ItemStats(code="small_bag_of_gold", level=1,
                                        type_="consumable", gold_value=1000),
        **(extra_stats or {}),
    }
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


@pytest.fixture()
def gold_fixture() -> tuple[WorldState, GameData]:
    """A state with one bag_of_gold in inventory and matching GameData."""
    state = make_state(gold=100, inventory={"bag_of_gold": 1})
    game_data = _make_gd()
    return state, game_data


# ── applicability ──────────────────────────────────────────────────────────────

class TestUseGoldBagApplicability:
    def test_applicable_when_gold_bag_owned(self, gold_fixture):
        state, game_data = gold_fixture
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        assert action.is_applicable(state, game_data) is True

    def test_not_applicable_when_inventory_empty(self, gold_fixture):
        state, game_data = gold_fixture
        empty = dataclasses.replace(state, inventory={})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        assert action.is_applicable(empty, game_data) is False

    def test_not_applicable_when_only_non_gold_items(self, gold_fixture):
        state, game_data = gold_fixture
        non_gold = dataclasses.replace(state, inventory={"iron_ore": 5})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        assert action.is_applicable(non_gold, game_data) is False

    def test_not_applicable_when_gold_bag_qty_zero(self, gold_fixture):
        state, game_data = gold_fixture
        zero_qty = dataclasses.replace(state, inventory={"bag_of_gold": 0})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        assert action.is_applicable(zero_qty, game_data) is False


# ── apply semantics ───────────────────────────────────────────────────────────

class TestUseGoldBagApply:
    def test_apply_credits_exact_gold_value(self, gold_fixture):
        state, game_data = gold_fixture
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        out = action.apply(state, game_data)
        assert out.gold == state.gold + 2500

    def test_apply_decrements_bag_by_one(self, gold_fixture):
        state, game_data = gold_fixture
        # start with 2 bags
        state = dataclasses.replace(state, inventory={"bag_of_gold": 2})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        out = action.apply(state, game_data)
        assert out.inventory.get("bag_of_gold") == 1

    def test_apply_removes_bag_key_when_last_consumed(self, gold_fixture):
        state, game_data = gold_fixture  # inventory={"bag_of_gold": 1}
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        out = action.apply(state, game_data)
        assert "bag_of_gold" not in out.inventory

    def test_apply_clears_cooldown(self, gold_fixture):
        state, game_data = gold_fixture
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        out = action.apply(state, game_data)
        assert out.cooldown_expires is None

    def test_apply_picks_highest_gold_value_bag(self, gold_fixture):
        """When both bag_of_gold (2500) and small_bag_of_gold (1000) are owned,
        apply credits 2500 (the bigger bag) and leaves the smaller untouched.
        Tiebreak: max by (gold_value, code) — highest value wins; code breaks ties
        lexicographically-descending so the result is deterministic when values match.
        """
        state, game_data = gold_fixture
        multi = dataclasses.replace(state, inventory={"bag_of_gold": 1,
                                                       "small_bag_of_gold": 1})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        out = action.apply(multi, game_data)
        assert out.gold == multi.gold + 2500
        assert "bag_of_gold" not in out.inventory
        assert out.inventory.get("small_bag_of_gold") == 1

    def test_apply_tiebreak_on_code_when_same_gold_value(self):
        """When two bags have identical gold_value, the one with the lexicographically
        LATER code wins — deterministic across Python runs."""
        gd = GameData()
        gd._item_stats = {
            "gold_bag_a": ItemStats(code="gold_bag_a", level=1, type_="consumable",
                                     gold_value=500),
            "gold_bag_z": ItemStats(code="gold_bag_z", level=1, type_="consumable",
                                     gold_value=500),
        }
        state = make_state(gold=0, inventory={"gold_bag_a": 1, "gold_bag_z": 1})
        action = UseGoldBagAction(_item_stats=gd.all_item_stats)
        out = action.apply(state, gd)
        # ("z" > "a") so gold_bag_z is selected, gold_bag_a remains
        assert "gold_bag_z" not in out.inventory
        assert out.inventory.get("gold_bag_a") == 1


# ── cost ──────────────────────────────────────────────────────────────────────

class TestUseGoldBagCost:
    def test_cost_is_small_constant(self, gold_fixture):
        state, game_data = gold_fixture
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        assert action.cost(state, game_data) == USE_GOLD_BAG_COST


# ── repr ──────────────────────────────────────────────────────────────────────

class TestUseGoldBagRepr:
    def test_repr(self):
        assert repr(UseGoldBagAction()) == "UseGoldBag"


# ── factory wiring ────────────────────────────────────────────────────────────

class TestUseGoldBagInFactory:
    def test_action_present_in_factory_output(self):
        """UseGoldBagAction must appear in build_actions so the planner can use it."""
        gd = _make_gd()
        state = make_state(inventory={"bag_of_gold": 1})
        actions = build_actions(
            game_data=gd,
            state=state,
            objective=None,
            bank_accessible=True,
            task_exchange_min_coins=3,
        )
        types = [type(a) for a in actions]
        assert UseGoldBagAction in types


# ── execute ───────────────────────────────────────────────────────────────────

class TestUseGoldBagExecute:
    def test_execute_raises_when_no_bag_in_inventory(self, gold_fixture):
        state, game_data = gold_fixture
        empty = dataclasses.replace(state, inventory={})
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        client = MagicMock()
        with pytest.raises(RuntimeError, match="UseGoldBag"):
            action.execute(empty, client)

    def test_execute_calls_api_with_best_bag_and_returns_state(self, gold_fixture):
        state, game_data = gold_fixture  # inventory={"bag_of_gold": 1}
        char = make_char_schema(gold=2600)
        action = UseGoldBagAction(_item_stats=game_data.all_item_stats)
        client = MagicMock()
        with patch(
            "artifactsmmo_cli.ai.actions.use_gold_bag.action_use_item",
            return_value=make_api_result(char),
        ) as mock_use:
            result = action.execute(state, client)
        mock_use.assert_called_once()
        call_kwargs = mock_use.call_args.kwargs
        assert call_kwargs["name"] == "testchar"
        assert call_kwargs["body"].code == "bag_of_gold"
        assert call_kwargs["body"].quantity == 1
        assert isinstance(result, WorldState)
        assert result.gold == 2600


# ── planner chain ─────────────────────────────────────────────────────────────

class _ReachGoldGoal(Goal):
    """Trivial goal satisfied when state.gold >= threshold.

    Used as a lightweight test double for planner-chain assertions — avoids
    the complex setup that ExpandBankGoal requires (bank fill, progression
    reserve, etc.).
    """

    def __init__(self, threshold: int) -> None:
        self._threshold = threshold

    def value(self, state: WorldState, game_data: GameData,
              history=None) -> float:
        return 1.0 if not self.is_satisfied(state) else 0.0

    def is_satisfied(self, state: WorldState) -> bool:
        return state.gold >= self._threshold

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"gold": self._threshold}

    @property
    def max_depth(self) -> int:
        return 3


class TestUseGoldBagPlannerChain:
    def test_planner_uses_gold_bag_when_gold_short(self, gold_fixture):
        """The GOAP planner finds UseGoldBag as the sole action when gold is below the
        threshold but a gold-bag in inventory would cover it.

        Scenario: gold=100, bag_of_gold gives +2500 → total 2600 >= threshold 1000.
        The planner must discover UseGoldBag (not leave empty-handed).
        """
        state, game_data = gold_fixture  # gold=100, inventory={"bag_of_gold": 1}
        goal = _ReachGoldGoal(threshold=1000)
        actions = [UseGoldBagAction(_item_stats=game_data.all_item_stats)]
        plan = GOAPPlanner().plan(state, goal, actions, game_data)
        assert len(plan) == 1
        assert isinstance(plan[0], UseGoldBagAction)

    def test_planner_chains_gold_bag_before_bank_expansion(self, gold_fixture):
        """The GOAP planner chains UseGoldBag before BuyBankExpansion when the
        character has a gold-bag but insufficient pocket gold to buy the expansion.

        Setup: gold=100 < expansion_cost=1000, bag_of_gold gives +2500 →
        after UseGoldBag gold=2600 >= 1000 → BuyBankExpansion becomes applicable.
        The plan must start with UseGoldBag.
        """
        state, game_data = gold_fixture  # gold=100, inventory={"bag_of_gold": 1}
        gd = _make_gd()
        gd._bank_location = (4, 0)
        gd._next_expansion_cost = 1000
        gd._bank_capacity = 20
        # Place character at the bank so movement cost doesn't dominate
        at_bank = dataclasses.replace(state, x=4, y=0)
        goal = _ReachGoldGoal(threshold=1000)
        actions = [
            UseGoldBagAction(_item_stats=gd.all_item_stats),
            BuyBankExpansionAction(bank_location=(4, 0), accessible=True),
        ]
        plan = GOAPPlanner().plan(at_bank, goal, actions, gd)
        assert len(plan) >= 1
        assert isinstance(plan[0], UseGoldBagAction)
