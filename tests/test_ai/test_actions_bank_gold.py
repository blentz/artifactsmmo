"""Tests for DepositGoldAction and WithdrawGoldAction."""



from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state


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

    def test_apply_moves_gold_from_bank(self):
        a = WithdrawGoldAction(quantity=100, bank_location=(4, 0), accessible=True)
        gd = make_gd()
        state = make_state(x=0, y=0, gold=10, bank_gold=200)
        new_state = a.apply(state, gd)
        assert new_state.gold == 110
        assert new_state.bank_gold == 100
