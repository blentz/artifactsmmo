"""RestartPolicy: which child deaths are worth retrying."""

import pytest

from artifactsmmo_cli.multi.restart_policy import MAX_ATTEMPTS, RestartPolicy


@pytest.mark.parametrize("reason", ["server_unavailable", "crash:network"])
def test_transient_reasons_restart(reason):
    assert RestartPolicy().decide(reason, attempts=0).restart is True


@pytest.mark.parametrize(
    "reason", ["stuck_exit", "crash", "keyboard_interrupt", "normal"]
)
def test_non_transient_reasons_stay_dead(reason):
    assert RestartPolicy().decide(reason, attempts=0).restart is False


def test_backoff_doubles_from_five_seconds():
    policy = RestartPolicy()
    delays = [policy.decide("crash:network", attempts=n).delay_seconds for n in range(4)]
    assert delays == [5.0, 10.0, 20.0, 40.0]


def test_backoff_is_capped_at_five_minutes():
    assert RestartPolicy().decide("crash:network", attempts=20).delay_seconds <= 300.0


def test_a_flapping_child_stops_being_restarted():
    """An endlessly restarting child is a bug report, not a working system."""
    assert RestartPolicy().decide("crash:network", attempts=MAX_ATTEMPTS).restart is False


def test_an_unknown_reason_stays_dead():
    """Fail closed: a reason the policy does not recognise is not restarted."""
    assert RestartPolicy().decide("reason_from_the_future", attempts=0).restart is False


def test_an_outage_is_restarted_however_long_it_lasts():
    """The API being down says nothing about the bot: a cap on
    server_unavailable left HAL and Robby dead after the server came back."""
    decision = RestartPolicy().decide("server_unavailable", attempts=MAX_ATTEMPTS * 100)
    assert decision.restart is True
    assert decision.delay_seconds == 300.0


def test_the_outage_delay_still_backs_off_from_five_seconds():
    policy = RestartPolicy()
    delays = [policy.decide("server_unavailable", attempts=n).delay_seconds for n in range(3)]
    assert delays == [5.0, 10.0, 20.0]
