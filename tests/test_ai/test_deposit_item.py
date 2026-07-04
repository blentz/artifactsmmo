"""DepositItemAction: single-code bank deposit (the disposal-route DEPOSIT arm)."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_character_schema, make_state

BANK_LOC = (4, 1)


def _gd(bank_capacity=50) -> GameData:
    gd = GameData()
    gd._bank_capacity = bank_capacity
    return gd


class TestIsApplicable:
    def test_applicable_when_holding_and_bank_has_room(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 16}, bank_items={})
        assert action.is_applicable(state, _gd())

    def test_not_applicable_when_inaccessible(self):
        action = DepositItemAction(code="emerald_stone", quantity=16,
                                   bank_location=BANK_LOC, accessible=False)
        state = make_state(inventory={"emerald_stone": 16}, bank_items={})
        assert not action.is_applicable(state, _gd())

    def test_not_applicable_when_bank_unvisited(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 16}, bank_items=None)
        assert not action.is_applicable(state, _gd())

    def test_not_applicable_when_holding_too_few(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 3}, bank_items={})
        assert not action.is_applicable(state, _gd())

    def test_not_applicable_when_bank_full(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 16},
                           bank_items={"a": 1, "b": 1})
        assert not action.is_applicable(state, _gd(bank_capacity=2))


class TestApply:
    def test_moves_items_from_inventory_to_bank(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 16, "sap": 2},
                           bank_items={"emerald_stone": 4})
        new_state = action.apply(state, _gd())
        assert "emerald_stone" not in new_state.inventory
        assert new_state.inventory["sap"] == 2
        assert new_state.bank_items == {"emerald_stone": 20}
        assert (new_state.x, new_state.y) == BANK_LOC
        assert new_state.cooldown_expires is None

    def test_partial_deposit_keeps_remainder(self):
        action = DepositItemAction(code="emerald_stone", quantity=10, bank_location=BANK_LOC)
        state = make_state(inventory={"emerald_stone": 16}, bank_items={})
        new_state = action.apply(state, _gd())
        assert new_state.inventory["emerald_stone"] == 6
        assert new_state.bank_items == {"emerald_stone": 10}


class TestExecute:
    def test_calls_api_and_returns_new_state(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(x=BANK_LOC[0], y=BANK_LOC[1],
                           inventory={"emerald_stone": 16}, bank_items={})
        client = MagicMock()
        result = MagicMock()
        result.data.character = make_character_schema(x=BANK_LOC[0], y=BANK_LOC[1])
        with patch("artifactsmmo_cli.ai.actions.deposit_item.deposit_item",
                   return_value=result) as mock_api:
            new_state = action.execute(state, client)
        assert isinstance(new_state, WorldState)
        mock_api.assert_called_once()
        body = mock_api.call_args.kwargs["body"]
        assert body[0].code == "emerald_stone"
        assert body[0].quantity == 16

    def test_moves_to_bank_before_depositing(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        state = make_state(x=0, y=0, inventory={"emerald_stone": 16}, bank_items={})
        client = MagicMock()
        move_result = MagicMock()
        move_result.data.character = make_character_schema(x=BANK_LOC[0], y=BANK_LOC[1])
        dep_result = MagicMock()
        dep_result.data.character = make_character_schema(x=BANK_LOC[0], y=BANK_LOC[1])
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=move_result):
            with patch("artifactsmmo_cli.ai.actions.deposit_item.deposit_item",
                       return_value=dep_result):
                new_state = action.execute(state, client)
        assert isinstance(new_state, WorldState)

    def test_cost_scales_with_distance(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        at_bank = make_state(x=BANK_LOC[0], y=BANK_LOC[1])
        far = make_state(x=0, y=0)
        assert action.cost(at_bank, _gd()) == 2.0
        assert action.cost(far, _gd()) == 2.0 + 5

    def test_repr(self):
        action = DepositItemAction(code="emerald_stone", quantity=16, bank_location=BANK_LOC)
        assert repr(action) == "DepositItem(emerald_stone×16)"

    def test_tags(self):
        assert "bank" in DepositItemAction.tags
        assert "deposit" in DepositItemAction.tags
