"""`per_state` — a one-entry identity memo for whole-state helpers.

The keep authority asks its reasons once per CODE while several of them answer a
question about the WHOLE state, so each rescanned the bag per code: O(codes x
holdings) where O(codes + holdings) does. Measured on a 120-holding bag,
`select_bank_deposits` went 5.52ms -> 0.37ms (14.9x), and the factor GROWS with
holdings because that is the axis being removed.
"""

from dataclasses import replace

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.per_state_memo import per_state
from tests.test_ai.fixtures import make_state


def _counting():
    calls: list[tuple[object, object]] = []

    @per_state
    def helper(state, game_data):
        calls.append((state, game_data))
        return len(state.inventory)

    return helper, calls


def test_the_same_pair_is_computed_once():
    helper, calls = _counting()
    gd, state = GameData(), make_state(inventory={"copper_ore": 3})
    assert helper(state, gd) == helper(state, gd) == 1
    assert len(calls) == 1


def test_an_equal_but_distinct_state_recomputes():
    """IDENTITY, not value — the conservative direction. It is also what makes
    the memo cheaper than the call: a value key would have to hash the bag,
    which is the very O(holdings) cost being removed."""
    helper, calls = _counting()
    gd, state = GameData(), make_state(inventory={"copper_ore": 3})
    helper(state, gd)
    helper(replace(state), gd)
    assert len(calls) == 2


def test_a_different_game_data_recomputes():
    """The catalog decides the answer. A state-only key served one test's items
    to another once already — six `test_bank_selection_diff` failures that
    passed in isolation."""
    helper, calls = _counting()
    state = make_state(inventory={"copper_ore": 3})
    helper(state, GameData())
    helper(state, GameData())
    assert len(calls) == 2


def test_a_changed_state_gets_a_changed_answer():
    """The failure a memo must never cause: answering for a state the caller
    has moved past."""
    helper, _ = _counting()
    gd = GameData()
    one = make_state(inventory={"copper_ore": 3})
    two = make_state(inventory={"copper_ore": 3, "ash_wood": 1})
    assert helper(one, gd) == 1
    assert helper(two, gd) == 2
    assert helper(one, gd) == 1          # and back again, recomputed


def test_one_entry_only():
    """Alternating between two states must not silently grow into a cache that
    holds a search's worth of states alive."""
    helper, calls = _counting()
    gd = GameData()
    one = make_state(inventory={"copper_ore": 3})
    two = make_state(inventory={"ash_wood": 1})
    for _ in range(3):
        helper(one, gd)
        helper(two, gd)
    assert len(calls) == 6               # every alternation is a miss


def test_the_raw_function_is_still_reachable():
    """`wraps` keeps `__wrapped__`, which is how the speed-up was A/B'd against
    the unmemoised code rather than against a benchmark that flattered it."""
    helper, calls = _counting()
    gd, state = GameData(), make_state(inventory={"copper_ore": 3})
    helper(state, gd)
    helper.__wrapped__(state, gd)
    assert len(calls) == 2
