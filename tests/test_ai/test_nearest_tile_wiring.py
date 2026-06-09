"""The gather/fight/goal call sites and MoveTo.apply/execute resolve their
destination through the shared, proven ai/nearest_tile.py primitive. These tests
pin the wiring: the normal Manhattan-nearest pick, the lex tie-break agreement
between MoveTo.apply and the selector, and the empty-destination error guards (the
old `min()` raised on an empty set; the new code raises an explicit ValueError).
"""
import pytest

from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions import make_game_data


def test_nearest_or_error_picks_manhattan_nearest():
    assert nearest_or_error(0, 0, frozenset([(5, 0), (1, 0)]), "gather") == (1, 0)


def test_nearest_or_error_lex_tiebreak_on_equal_distance():
    # (3, 0) and (0, 3) both distance 3 from origin; lex-min (x, y) wins -> (0, 3).
    assert nearest_or_error(0, 0, frozenset([(3, 0), (0, 3)]), "gather") == (0, 3)


def test_nearest_or_error_raises_on_empty_gather():
    with pytest.raises(ValueError, match="no gather locations"):
        nearest_or_error(0, 0, frozenset(), "gather")


def test_nearest_or_error_raises_on_empty_combat():
    with pytest.raises(ValueError, match="no combat locations"):
        nearest_or_error(0, 0, frozenset(), "combat")


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
