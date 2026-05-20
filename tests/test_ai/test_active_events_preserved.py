"""active_events must survive action.apply() so multi-step plans keep the snapshot."""
from datetime import datetime, timezone

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from tests.test_ai.fixtures import make_state


def test_move_apply_preserves_active_events():
    exp = {"gemstone_merchant": datetime(2026, 5, 20, 22, 30, tzinfo=timezone.utc)}
    state = make_state(x=0, y=0, active_events=exp)
    new = MoveAction(x=1, y=0).apply(state, GameData())
    assert new.active_events == exp
