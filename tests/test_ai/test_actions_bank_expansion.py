"""Tests for BuyBankExpansionAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


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
