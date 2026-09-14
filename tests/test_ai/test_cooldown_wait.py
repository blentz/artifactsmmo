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

from artifactsmmo_cli.ai.actions.cooldown_wait import wait_out_cooldown
from tests.test_ai.fixtures import make_state


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
