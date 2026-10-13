"""`wait_out_cooldown` is the composite-action idiom, shared by every action
that issues a second API call of its own.

The player loop sleeps out one cooldown per cycle, BETWEEN actions. An action
that calls the API twice is therefore on its own for the first call's cooldown:
`MoveAction` before a composite's secondary call, `OptimizeLoadoutAction`
between the unequip and equip legs of a swap, `DepositAllAction` between
deposit batches. Each of the three learned it from a live 499 livelock.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.actions import cooldown_wait
from artifactsmmo_cli.ai.actions.cooldown_wait import (
    LAG_HOLD_SECONDS,
    MAX_SERVER_LAG_SECONDS,
    SKEW_MARGIN_SECONDS,
    cooldown_margin,
    note_server_cooldown,
    wait_out_cooldown,
)
from tests.test_ai.fixtures import make_state


@pytest.fixture(autouse=True)
def _no_learned_lag():  # type: ignore[no-untyped-def]
    """The lag is process state; every test starts with none learned."""
    cooldown_wait._LAG.update(seconds=0.0, at=float("-inf"))
    yield
    cooldown_wait._LAG.update(seconds=0.0, at=float("-inf"))


def test_no_cooldown_does_not_sleep():
    state = make_state(cooldown_expires=None)
    with patch("artifactsmmo_cli.ai.actions.cooldown_wait.time.sleep") as sleep:
        wait_out_cooldown(state)
    sleep.assert_not_called()


def test_an_already_expired_cooldown_does_not_sleep():
    """The server's cooldown can have run out while the response was in flight
    — a negative remaining must not become a negative sleep."""
    past = datetime.now(tz=timezone.utc) - timedelta(seconds=5.0)
    state = make_state(cooldown_expires=past)
    with patch("artifactsmmo_cli.ai.actions.cooldown_wait.time.sleep") as sleep:
        wait_out_cooldown(state)
    sleep.assert_not_called()


def test_a_live_cooldown_is_slept_out_with_skew_margin():
    future = datetime.now(tz=timezone.utc) + timedelta(seconds=2.0)
    state = make_state(cooldown_expires=future)
    with patch("artifactsmmo_cli.ai.actions.cooldown_wait.time.sleep") as sleep:
        wait_out_cooldown(state)
    slept = sleep.call_args[0][0]
    # Strictly LONGER than the remaining cooldown: a wait landing exactly on
    # the expiry still races the 499 across host/server clock skew.
    assert 2.0 < slept < 2.5, f"expected ~2.1s sleep, got {slept}"


def test_with_no_499_the_margin_is_the_skew_margin():
    assert cooldown_margin(now=1000.0) == SKEW_MARGIN_SECONDS


def test_a_499_widens_the_margin_by_what_the_server_said_was_left():
    """Live 2026-10-13 15:30-16:30Z: 336 of 733 cycles drew 499 with 0.35-0.49 s
    left, though the loop slept the returned expiry + 0.1 s. The server
    enforced each cooldown ~0.5 s past the expiry it returned."""
    note_server_cooldown("The character is in cooldown: 0.37 seconds remaining.", now=1000.0)
    assert cooldown_margin(now=1001.0) == pytest.approx(SKEW_MARGIN_SECONDS + 0.37)


def test_a_second_499_inside_the_hold_adds_to_the_lag():
    """The waits already carried the learned lag, so the leftover is ON TOP of it."""
    note_server_cooldown("The character is in cooldown: 0.37 seconds remaining.", now=1000.0)
    note_server_cooldown("The character is in cooldown: 0.20 seconds remaining.", now=1100.0)
    assert cooldown_margin(now=1101.0) == pytest.approx(SKEW_MARGIN_SECONDS + 0.57)


def test_the_lag_lapses_after_a_quiet_hold():
    note_server_cooldown("The character is in cooldown: 0.37 seconds remaining.", now=1000.0)
    assert cooldown_margin(now=1000.0 + LAG_HOLD_SECONDS - 1) > SKEW_MARGIN_SECONDS
    assert cooldown_margin(now=1000.0 + LAG_HOLD_SECONDS) == SKEW_MARGIN_SECONDS
    # and a lapsed lag is not the base a new one adds to
    note_server_cooldown("The character is in cooldown: 0.20 seconds remaining.", now=1000.0 + LAG_HOLD_SECONDS)
    assert cooldown_margin(now=1000.0 + LAG_HOLD_SECONDS) == pytest.approx(SKEW_MARGIN_SECONDS + 0.20)


def test_the_lag_is_capped():
    """A large remainder is a call that skipped its wait, not server lag; it
    must not stretch every wait for the next ten minutes."""
    note_server_cooldown("The character is in cooldown: 30.00 seconds remaining.", now=1000.0)
    assert cooldown_margin(now=1000.0) == pytest.approx(SKEW_MARGIN_SECONDS + MAX_SERVER_LAG_SECONDS)


def test_a_499_without_a_remainder_learns_nothing():
    note_server_cooldown("The character is in cooldown.", now=1000.0)
    assert cooldown_margin(now=1000.0) == SKEW_MARGIN_SECONDS


def test_the_learned_lag_is_slept_out():
    note_server_cooldown("The character is in cooldown: 0.40 seconds remaining.",
                         now=cooldown_wait.time.monotonic())
    future = datetime.now(tz=timezone.utc) + timedelta(seconds=2.0)
    state = make_state(cooldown_expires=future)
    with patch("artifactsmmo_cli.ai.actions.cooldown_wait.time.sleep") as sleep:
        wait_out_cooldown(state)
    slept = sleep.call_args[0][0]
    assert 2.4 < slept < 2.6, f"expected ~2.5s sleep, got {slept}"
