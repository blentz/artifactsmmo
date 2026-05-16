"""Tests for MapTransitionAction."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_char_schema, make_api_result


def make_gd(**kwargs) -> GameData:
    gd = GameData()
    gd._transition_tiles = kwargs.get("transition_tiles", set())
    return gd


class TestMapTransitionAction:
    def test_repr(self):
        assert repr(MapTransitionAction()) == "Transition"

    def test_not_applicable_when_not_on_transition_tile(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=0, y=0)
        assert a.is_applicable(state, gd) is False

    def test_applicable_when_on_transition_tile(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        assert a.is_applicable(state, gd) is True

    def test_apply_keeps_position_unchanged(self):
        """Transition's destination depends on server-side response; apply can't predict it."""
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        new_state = a.apply(state, gd)
        assert (new_state.x, new_state.y) == (5, 5)

    def test_cost_is_3(self):
        a = MapTransitionAction()
        gd = make_gd(transition_tiles={(5, 5)})
        state = make_state(x=5, y=5)
        assert a.cost(state, gd) == 3.0

    def test_execute_calls_transition_api(self):
        a = MapTransitionAction()
        char = make_char_schema()
        state = make_state(x=5, y=5)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.actions.transition.action_transition",
                   return_value=make_api_result(char)) as mock_t:
            a.execute(state, client)
        mock_t.assert_called_once_with(client=client, name="testchar")
