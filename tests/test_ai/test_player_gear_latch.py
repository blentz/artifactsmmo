"""Player updates the gear latch each cycle and feeds gear_review_active into the
selection context."""
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_player_constructs_a_gear_latch():
    p = GamePlayer(character="hero")
    assert isinstance(p._gear_latch, GearLatch)


def test_selection_context_carries_latch_state():
    p = GamePlayer(character="hero")
    p._gear_latch._active = True
    p.state = make_state()
    p.game_data = _make_planner_gd()
    ctx = p._selection_context(combat_monster=None)
    assert ctx.gear_review_active is True
