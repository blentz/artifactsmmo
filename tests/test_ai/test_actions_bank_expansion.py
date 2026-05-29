"""Tests for BuyBankExpansionAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank_expansion import (
    BANK_EXPANSION_SLOTS,
    BuyBankExpansionAction,
)
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._bank_location = kwargs.get("bank_location", (4, 0))
    gd._bank_capacity = kwargs.get("bank_capacity", 30)
    gd._next_expansion_cost = kwargs.get("next_expansion_cost", 1000)
    return gd


class TestBuyBankExpansionAction:
    def test_repr(self):
        assert repr(BuyBankExpansionAction(bank_location=(4, 0), accessible=True)) == "BuyBankExpansion"

    def test_not_applicable_when_bank_inaccessible(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=False)
        gd = make_gd()
        state = make_state(x=4, y=0, gold=2000)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=500)
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_gold_and_accessible(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=2000)
        assert a.is_applicable(state, gd) is True

    def test_apply_deducts_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=2000)
        new_state = a.apply(state, gd)
        assert new_state.gold == 1000

    def test_apply_increments_bank_capacity_from_state(self):
        """Post-fix Phase-8b: apply mints +BANK_EXPANSION_SLOTS into
        state.bank_capacity so ExpandBankGoal.is_satisfied can flip."""
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(bank_capacity=999, next_expansion_cost=1000)  # game_data is a decoy
        state = make_state(x=4, y=0, gold=2000, bank_capacity=30)
        new_state = a.apply(state, gd)
        assert new_state.bank_capacity == 30 + BANK_EXPANSION_SLOTS

    def test_apply_seeds_bank_capacity_from_game_data_when_state_none(self):
        """When state.bank_capacity is None (bank not yet visited), apply
        seeds from game_data._bank_capacity (the cycle snapshot) so the
        projection still produces a faithful post-buy capacity."""
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=1000)
        state = make_state(x=4, y=0, gold=2000, bank_capacity=None)
        new_state = a.apply(state, gd)
        assert new_state.bank_capacity == 30 + BANK_EXPANSION_SLOTS

    def test_apply_chained_increments_compound(self):
        """N applies → capacity grows by N * SLOTS. This is the GOAP
        projection contract that closes the BLOCKED projection gap."""
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(bank_capacity=30, next_expansion_cost=100)
        state = make_state(x=4, y=0, gold=10000, bank_capacity=30)
        for _ in range(3):
            state = a.apply(state, gd)
        assert state.bank_capacity == 30 + 3 * BANK_EXPANSION_SLOTS

    def test_cost_includes_distance_and_gold(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        gd = make_gd(next_expansion_cost=1000)
        state = make_state(x=0, y=0, gold=2000)
        # 5 + dist(4) + 1000/100 = 19
        assert a.cost(state, gd) == pytest.approx(19.0)

    def test_execute_moves_and_calls_api(self):
        a = BuyBankExpansionAction(bank_location=(4, 0), accessible=True)
        char = make_char_schema()
        state = make_state(x=0, y=0, gold=2000)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.bank_expansion.MoveAction") as MockMove:
            MockMove.return_value.execute.return_value = make_state(x=4, y=0, gold=2000)
            with patch("artifactsmmo_cli.ai.actions.bank_expansion.action_buy_bank_expansion",
                       return_value=make_api_result(char)) as mock_exp:
                a.execute(state, client)
        MockMove.assert_called_once_with(x=4, y=0)
        mock_exp.assert_called_once_with(client=client, name="testchar")
