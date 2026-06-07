"""The three `_nearest` call sites and MoveTo.apply/execute resolve their
destination through the shared, proven ai/nearest_tile.py primitive. These tests
pin the wiring: the normal Manhattan-nearest pick, the lex tie-break agreement
between MoveTo.apply and the selector, and the empty-destination error guards (the
old `min()` raised on an empty set; the new code raises an explicit ValueError).
"""
import pytest

from artifactsmmo_cli.ai.actions.combat import _nearest as combat_nearest
from artifactsmmo_cli.ai.actions.gathering import _nearest as gather_nearest
from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions import make_game_data


def test_gather_nearest_picks_manhattan_nearest():
    state = make_state(x=0, y=0)
    assert gather_nearest(frozenset([(5, 0), (1, 0)]), state) == (1, 0)


def test_combat_nearest_picks_manhattan_nearest():
    state = make_state(x=0, y=0)
    assert combat_nearest(frozenset([(5, 0), (1, 0)]), state) == (1, 0)


def test_gather_nearest_lex_tiebreak_on_equal_distance():
    # (3, 0) and (0, 3) both distance 3 from origin; lex-min (x, y) wins -> (0, 3).
    state = make_state(x=0, y=0)
    assert gather_nearest(frozenset([(3, 0), (0, 3)]), state) == (0, 3)


def test_gather_nearest_raises_on_empty():
    state = make_state(x=0, y=0)
    with pytest.raises(ValueError, match="no gather locations"):
        gather_nearest(frozenset(), state)


def test_combat_nearest_raises_on_empty():
    state = make_state(x=0, y=0)
    with pytest.raises(ValueError, match="no combat locations"):
        combat_nearest(frozenset(), state)


def test_moveto_apply_and_execute_agree_on_tie():
    # Manhattan-nearest is (5, 0) (dist 5); (1, 9) is the raw min(tuple) (dist 10).
    # apply must land on the SAME tile execute would move to: (5, 0).
    action = MoveTo(name="monster:x", destinations=frozenset([(1, 9), (5, 0)]))
    state = make_state(x=0, y=0)
    new_state = action.apply(state, make_game_data())
    assert (new_state.x, new_state.y) == (5, 0)


def test_moveto_apply_raises_on_empty():
    action = MoveTo(name="empty", destinations=frozenset())
    state = make_state(x=0, y=0)
    with pytest.raises(ValueError, match="no destinations"):
        action.apply(state, make_game_data())


def test_moveto_execute_raises_on_empty():
    action = MoveTo(name="empty", destinations=frozenset())
    state = make_state(x=0, y=0)
    with pytest.raises(ValueError, match="no destinations"):
        action.execute(state, client=None)
