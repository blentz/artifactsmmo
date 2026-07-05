"""MapTransitionAction.execute walks to the portal tile before transitioning."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


def test_execute_walks_to_portal_first_when_not_there() -> None:
    a = MapTransitionAction(portal_x=-4, portal_y=9, dest_x=-4, dest_y=8,
                            dest_layer="underground", conditions=(),
                            travel_region="overworld")
    char = make_char_schema()
    state = make_state(x=0, y=0)  # NOT at the portal: the move leg must fire
    client = MagicMock()
    moved = make_state(x=-4, y=9)
    with patch("artifactsmmo_cli.ai.actions.transition.MoveAction") as mock_move_cls, \
         patch("artifactsmmo_cli.ai.actions.transition.action_transition",
               return_value=make_api_result(char)) as mock_t:
        mock_move_cls.return_value.execute.return_value = moved
        a.execute(state, client)
    mock_move_cls.assert_called_once_with(x=-4, y=9)
    mock_move_cls.return_value.execute.assert_called_once_with(state, client)
    mock_t.assert_called_once_with(client=client, name="testchar")
