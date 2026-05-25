"""Tests for DepositGoldAction and WithdrawGoldAction."""

from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.deposit_gold import DepositGoldAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._bank_location = kwargs.get("bank_location", (4, 0))
    return gd


class TestDepositGoldAction:
    def test_repr(self):
        assert repr(DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)) == "DepositGold(100)"

    def test_not_applicable_when_inaccessible(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=False)
        gd = make_gd()
        state = make_state(gold=200)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_gold(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(gold=50)
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_enough_gold(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(gold=200)
        assert a.is_applicable(state, gd) is True

    def test_apply_moves_gold_to_bank(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0, gold=200, bank_gold=50)
        new_state = a.apply(state, gd)
        assert new_state.gold == 100
        assert new_state.bank_gold == 150
        assert (new_state.x, new_state.y) == (4, 0)

    def test_execute_moves_then_deposits_and_returns_server_state(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=0, y=0, gold=200, bank_gold=50)
        client = MagicMock()
        # Server reports gold drained to 100 after the deposit.
        char = make_char_schema(x=4, y=0, gold=100)
        move_char = make_char_schema(x=4, y=0, gold=200)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.deposit_gold.action_deposit_gold",
                       return_value=make_api_result(char)) as mock_dep:
                new_state = a.execute(state, client)

        assert new_state.gold == 100
        assert (new_state.x, new_state.y) == (4, 0)
        body = mock_dep.call_args.kwargs["body"]
        assert body.quantity == 100

    def test_execute_skips_move_when_already_at_bank(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=4, y=0, gold=200)
        client = MagicMock()
        char = make_char_schema(x=4, y=0, gold=100)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
            with patch("artifactsmmo_cli.ai.actions.deposit_gold.action_deposit_gold",
                       return_value=make_api_result(char)):
                new_state = a.execute(state, client)

        mock_move.assert_not_called()
        assert new_state.gold == 100

    def test_execute_raises_on_missing_response(self):
        a = DepositGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=4, y=0, gold=200)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.deposit_gold.action_deposit_gold",
                   return_value=None):
            with pytest.raises(RuntimeError):
                a.execute(state, client)


class TestWithdrawGoldAction:
    def test_repr(self):
        assert repr(WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)) == "WithdrawGold(100)"

    def test_not_applicable_when_bank_gold_unknown(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=None)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_insufficient_bank_gold(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=50)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_inaccessible(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=False)
        gd = make_gd()
        state = make_state(bank_gold=500)
        assert a.is_applicable(state, gd) is False

    def test_not_applicable_when_bank_location_unknown(self):
        a = WithdrawGoldAction(quantity=100, bank_location=None, accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=500)
        assert a.is_applicable(state, gd) is False

    def test_applicable_with_enough_bank_gold(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(bank_gold=500)
        assert a.is_applicable(state, gd) is True

    def test_cost_includes_distance(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0)
        # 2.0 + dist(4) = 6.0
        assert a.cost(state, gd) == pytest.approx(6.0)

    def test_apply_moves_gold_from_bank(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0, gold=10, bank_gold=200)
        new_state = a.apply(state, gd)
        assert new_state.gold == 110
        assert new_state.bank_gold == 100

    def test_execute_moves_then_withdraws_and_returns_server_state(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=0, y=0, gold=10, bank_gold=200)
        client = MagicMock()
        # Server reports gold raised to 110 after the withdrawal.
        char = make_char_schema(x=4, y=0, gold=110)
        move_char = make_char_schema(x=4, y=0, gold=10)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(move_char)):
            with patch("artifactsmmo_cli.ai.actions.withdraw_gold.action_withdraw_gold",
                       return_value=make_api_result(char)) as mock_wd:
                new_state = a.execute(state, client)

        assert new_state.gold == 110
        assert (new_state.x, new_state.y) == (4, 0)
        body = mock_wd.call_args.kwargs["body"]
        assert body.quantity == 100

    def test_execute_skips_move_when_already_at_bank(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=4, y=0, gold=10, bank_gold=200)
        client = MagicMock()
        char = make_char_schema(x=4, y=0, gold=110)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move") as mock_move:
            with patch("artifactsmmo_cli.ai.actions.withdraw_gold.action_withdraw_gold",
                       return_value=make_api_result(char)):
                new_state = a.execute(state, client)

        mock_move.assert_not_called()
        assert new_state.gold == 110

    def test_execute_raises_on_missing_response(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        state = make_state(x=4, y=0, bank_gold=200)
        client = MagicMock()

        with patch("artifactsmmo_cli.ai.actions.withdraw_gold.action_withdraw_gold",
                   return_value=None):
            with pytest.raises(RuntimeError):
                a.execute(state, client)
