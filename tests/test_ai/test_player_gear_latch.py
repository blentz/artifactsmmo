"""Player updates the gear-review edge each cycle and feeds its NARROW flag
(`level_up_pending`) into the selection context."""
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _make_planner_gd


def test_player_constructs_a_gear_latch():
    p = GamePlayer(character="hero")
    assert isinstance(p._gear_latch, GearLatch)


def test_selection_context_carries_the_narrow_level_up_flag():
    """`gear_review_active` is fed by `level_up_pending`, NOT by the raw edge.

    The guard's one surviving arm maps `HORIZON_LEVEL_UP` and nothing else, so a
    bare `_active` would fire a guard that cannot answer. `_active` still drives
    plan invalidation through `.active`; the two readers are deliberately
    different and this pins which one reaches the context."""
    p = GamePlayer(character="hero")
    p._gear_latch._active = True
    p.state = make_state()
    p.game_data = _make_planner_gd()
    assert p._selection_context(combat_monster=None).gear_review_active is False

    p._gear_latch._level_up_pending = True
    assert p._selection_context(combat_monster=None).gear_review_active is True
