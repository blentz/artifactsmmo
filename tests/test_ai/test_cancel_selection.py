"""Tests for the pure GE cancel-selection helper `cancel_targets`: the on-need
(gold-short BUY, needed-item SELL) and TTL (age > TTL_CYCLES) cancel triggers.

`cancel_targets` decides purely from `state` + demand, so `game_data` here is a bare
`GameData()` (the construction pattern used across the pure `ai/` tests)."""

import pytest

from artifactsmmo_cli.ai.cancel_selection import cancel_targets
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.ge_order_config import TTL_CYCLES
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from tests.test_ai.fixtures import make_state


@pytest.fixture
def game_data() -> GameData:
    return GameData()


def _buy(id_, code, qty, price, age=0):
    return OpenOrder(id_, code, qty, price, OrderSide.BUY, age)


def _sell(id_, code, qty, price, age=0):
    return OpenOrder(id_, code, qty, price, OrderSide.SELL, age)


def test_an_order_a_sibling_is_already_cancelling_is_not_a_target(game_data):
    """The 2026-08-10 race, closed. GE orders are ACCOUNT-scoped, so every
    `play --all` child reads the same list and ages the same order past
    TTL_CYCLES; six of twenty ids were attacked by two or more characters and
    the losers each paid an action-bucket request for HTTP 404 "Order not
    found". A sibling's live claim removes the id from this character's targets
    entirely, so the wasted request is never planned."""
    state = make_state(open_orders=(_sell("s2", "iron", 3, 19, age=TTL_CYCLES + 1),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset(),
                         sibling_claims=frozenset({"s2"}))
    assert ids == ()


def test_a_sibling_claim_on_another_order_leaves_this_one_a_target(game_data):
    """Exclusion is per-id, not a blanket suppression of the whole cancel
    channel — the liveness escape has to keep working for every order nobody
    else has taken."""
    state = make_state(open_orders=(
        _sell("s2", "iron", 3, 19, age=TTL_CYCLES + 1),
        _sell("s3", "ash", 3, 19, age=TTL_CYCLES + 1),
    ))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset(),
                         sibling_claims=frozenset({"s2"}))
    assert ids == ("s3",)


def test_a_claimed_buy_order_does_not_count_toward_the_gold_shortfall(game_data):
    """A claimed BUY must not be silently credited against `need_gold`: the
    SIBLING is freeing that escrow, not us, so counting it here would leave this
    character believing its shortfall is already covered and cancelling nothing.

    Sized so the two readings DIVERGE. The shortfall is 20 and each order holds
    27, so one order covers it: crediting the claimed b1 drives `gold_short` to
    -7 and b2 is never taken, while skipping b1 outright leaves the full 20
    outstanding and b2 is. An earlier version used a 50 shortfall, where b2 was
    taken under both readings and the assertion proved nothing — a surviving
    mutant caught it."""
    state = make_state(gold=0, open_orders=(
        _buy("b1", "iron", 3, 9),
        _buy("b2", "ash", 3, 9),
    ))
    ids = cancel_targets(state, game_data, need_gold=20, needed_items=frozenset(),
                         sibling_claims=frozenset({"b1"}))
    assert ids == ("b2",)


def test_no_sibling_claims_is_the_default_and_changes_nothing(game_data):
    """The single-character path: `sibling_claims` defaults empty, so every
    caller that does not pass it gets byte-identical pre-coordination
    behaviour."""
    state = make_state(open_orders=(_sell("s2", "iron", 3, 19, age=TTL_CYCLES + 1),))
    assert cancel_targets(state, game_data, need_gold=0,
                          needed_items=frozenset()) == ("s2",)


def test_cancels_buy_order_when_gold_needed(game_data):
    state = make_state(gold=5, open_orders=(_buy("b1", "iron", 3, 9, age=0),))
    ids = cancel_targets(state, game_data, need_gold=20, needed_items=frozenset())
    assert "b1" in ids  # frees 27 gold to cover the 15-short of 20


def test_cancels_sell_order_when_item_needed(game_data):
    state = make_state(open_orders=(_sell("s1", "iron", 3, 19, age=0),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset({"iron"}))
    assert "s1" in ids


def test_cancels_stale_order_past_ttl(game_data):
    state = make_state(open_orders=(_sell("s2", "iron", 3, 19, age=TTL_CYCLES + 1),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset())
    assert "s2" in ids


def test_keeps_fresh_unneeded_order(game_data):
    state = make_state(gold=999, open_orders=(_sell("s3", "iron", 3, 19, age=0),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset())
    assert ids == ()


def test_no_orders_returns_empty(game_data):
    state = make_state(gold=0, open_orders=())
    ids = cancel_targets(state, game_data, need_gold=100, needed_items=frozenset({"iron"}))
    assert ids == ()


def test_gold_already_sufficient_keeps_buy(game_data):
    state = make_state(gold=50, open_orders=(_buy("b1", "iron", 3, 9, age=0),))
    ids = cancel_targets(state, game_data, need_gold=20, needed_items=frozenset())
    assert ids == ()


def test_stops_cancelling_buys_once_shortfall_covered(game_data):
    # First buy frees 27 (>= 20 short of gold=0) so the second must be kept.
    state = make_state(
        gold=0,
        open_orders=(
            _buy("b1", "iron", 3, 9, age=0),
            _buy("b2", "copper", 3, 9, age=0),
        ),
    )
    ids = cancel_targets(state, game_data, need_gold=20, needed_items=frozenset())
    assert ids == ("b1",)


def test_buy_not_cancelled_for_item_need(game_data):
    # needed_items only cancels SELL orders (getting the listed item back), not BUYs.
    state = make_state(gold=999, open_orders=(_buy("b1", "iron", 3, 9, age=0),))
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset({"iron"}))
    assert ids == ()


def test_ttl_takes_precedence_and_dedups(game_data):
    # A stale needed-item SELL is picked once by the TTL arm, not duplicated.
    state = make_state(
        open_orders=(_sell("s1", "iron", 3, 19, age=TTL_CYCLES + 5),),
    )
    ids = cancel_targets(state, game_data, need_gold=0, needed_items=frozenset({"iron"}))
    assert ids == ("s1",)


def test_deterministic_multi_trigger_order(game_data):
    state = make_state(
        gold=0,
        open_orders=(
            _sell("s_old", "wood", 1, 5, age=TTL_CYCLES + 1),  # TTL
            _buy("b_need", "iron", 2, 10, age=0),  # gold-short (20 short)
            _sell("s_need", "copper", 1, 5, age=0),  # needed item
        ),
    )
    ids = cancel_targets(
        state, game_data, need_gold=20, needed_items=frozenset({"copper"})
    )
    assert ids == ("s_old", "b_need", "s_need")
