"""A 429 is a throttle to wait out, not an unexplained action failure.

Task 18 investigation finding: the brief's premise — that a 429 surfaces as
an `ApiActionError` with `.code == 429` and a `.headers` mapping — does not
hold. The generated OpenAPI client's `_parse_response` only recognizes
status codes the spec documents per endpoint; 429 is undocumented for every
endpoint (action and data alike), so with `raise_on_unexpected_status=False`
`sync()` silently collapses a 429 to `None` before `Action._raise_for_error`
ever runs, discarding the status code and headers. `ApiActionError` is never
constructed with code 429 by any code path.

Detection instead happens in a new httpx response event-hook
(`rate_limit_detector.detect_rate_limited_response`, wired into
`client_manager.py` alongside the existing maintenance-page hook), which
raises `RateLimitedError` — a `httpx.HTTPError` subclass carrying the raw
response headers — directly from within the request. `GamePlayer._execute`
catches that one new exception type ahead of its existing generic
`except httpx.HTTPError` clause; every OTHER `except httpx.HTTPError`
retry loop already in this codebase (`_fetch_world_state`,
`_fetch_active_events`, `_fetch_raids`) absorbs a 429 as a transient
condition for free, with no code changes, because RateLimitedError IS one.
"""

from unittest.mock import MagicMock, patch

import pytest
from sqlmodel import Session as SqlSession
from sqlmodel import select

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.rate_limited_error import RateLimitedError
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema, make_get_character_result
from tests.test_ai.test_player_run import _patch_game_data_load


def test_429_is_classified_as_rate_limited():
    assert GamePlayer.is_rate_limited(429) is True
    assert GamePlayer.is_rate_limited(478) is False


def test_the_rate_limited_outcome_is_named():
    assert GamePlayer.RATE_LIMITED_OUTCOME == "error:rate_limited"


class TestExecuteHandlesRateLimitedError:
    """Drives GamePlayer._execute directly (not the full run() loop) with a
    RateLimitedError raised from inside action.execute(), the same shape a
    real 429 takes once the httpx hook raises it."""

    def test_outcome_is_rate_limited_and_state_is_unchanged(self):
        player = GamePlayer(character="hero")
        state = make_state(x=0, y=0)
        player.state = state
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=RateLimitedError({"Retry-After": "5"})):
            with patch("artifactsmmo_cli.ai.player.time.sleep") as sleep_mock:
                new_state, outcome = player._execute(action, client)
        assert outcome == GamePlayer.RATE_LIMITED_OUTCOME
        # A 429 means the request never reached game logic — no refetch, no
        # state change; the character is still exactly where it started.
        assert new_state is state
        sleep_mock.assert_called_once_with(5.0)

    def test_a_missing_retry_after_header_falls_back_to_backoff(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=RateLimitedError({})):
            with patch("artifactsmmo_cli.ai.player.time.sleep") as sleep_mock:
                _new_state, outcome = player._execute(action, client)
        assert outcome == GamePlayer.RATE_LIMITED_OUTCOME
        sleep_mock.assert_called_once_with(1.0)  # BASE_BACKOFF_SECONDS * 2**0

    def test_consecutive_rate_limits_ramp_the_backoff(self):
        """_rate_limit_attempts persists across calls with no success between
        them, so retry_after_seconds sees attempt=0, then attempt=1, ..."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=RateLimitedError({})):
            with patch("artifactsmmo_cli.ai.player.time.sleep") as sleep_mock:
                player._execute(action, client)
                player._execute(action, client)
                player._execute(action, client)
        assert [c.args[0] for c in sleep_mock.call_args_list] == [1.0, 2.0, 4.0]
        assert player._rate_limit_attempts == 3

    def test_a_successful_action_resets_the_rate_limit_counter(self):
        """A throttled action followed by a successful one must not keep the
        ramped-up backoff — an isolated 429 or two must not slow the bot down
        for the rest of the session."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=RateLimitedError({})):
            with patch("artifactsmmo_cli.ai.player.time.sleep"):
                player._execute(action, client)
        assert player._rate_limit_attempts == 1
        char = make_char_schema(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   return_value=make_api_result(char)):
            _new_state, outcome = player._execute(action, client)
        assert outcome == "ok"
        assert player._rate_limit_attempts == 0

    def test_a_429_during_a_data_read_is_absorbed_by_the_existing_retry_loop(self):
        """RateLimitedError deliberately subclasses httpx.HTTPError (see
        rate_limited_error.py) so _fetch_world_state's existing transient-retry
        loop — unmodified by Task 18 — already treats a 429 on get_character
        as a retryable condition, same as a timeout, with zero new code."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        char = make_char_schema()
        with patch("artifactsmmo_cli.ai.player.get_character",
                   side_effect=[RateLimitedError({}), make_get_character_result(char)]):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events",
                       return_value=MagicMock(data=[])):
                with patch("artifactsmmo_cli.ai.player.get_all_raids",
                           return_value=MagicMock(data=[])):
                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                        state = player._fetch_world_state(client)
        assert state.character == "testchar"


def test_run_survives_a_429_and_keeps_cycling():
    """A RateLimitedError raised by action.execute must not kill the run
    loop, must record outcome=error:rate_limited (not error:other), and must
    NOT sleep a second time via the outer no-cooldown exponential backoff —
    _execute's retry_after_seconds sleep already waited out this exact 429."""
    history = LearningStore(db_path=":memory:", character="hero")
    history.start_session()
    player = GamePlayer(character="hero", history=history)
    client = MagicMock()

    call_count = [0]

    def fake_wait():
        call_count[0] += 1
        if call_count[0] > 1:  # let ONE full 429 cycle run, then stop
            raise KeyboardInterrupt

    initial_state = make_state(hp=50, max_hp=150)
    goal = WaitGoal()

    try:
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with _patch_game_data_load():
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh"), \
                                    patch.object(player, "_reconcile_open_orders"):
                                with patch.object(player, "_build_actions", return_value=[RestAction()]):
                                    with patch.object(
                                        player._arbiter, "select",
                                        return_value=(goal, [RestAction()], []),
                                    ):
                                        with patch(
                                            "artifactsmmo_cli.ai.actions.rest.action_rest",
                                            side_effect=RateLimitedError({"Retry-After": "2"}),
                                        ):
                                            with patch(
                                                "artifactsmmo_cli.ai.player.time.sleep"
                                            ) as sleep_mock:
                                                with pytest.raises(KeyboardInterrupt):
                                                    player.run()

        # Exactly ONE sleep call for the one completed cycle — proves the
        # outer no-cooldown backoff (run()'s `elif cooldown_remaining == 0.0`
        # branch) did NOT ALSO sleep for this outcome.
        assert sleep_mock.call_count == 1
        sleep_mock.assert_called_once_with(2.0)
        with SqlSession(history._engine) as s:
            outcomes = [c.outcome for c in s.exec(select(Cycle)).all()]
        assert outcomes == ["error:rate_limited"]
    finally:
        history.close()
