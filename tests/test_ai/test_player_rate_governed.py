"""The rate budget actually throttles outbound requests.

Task 17: `--rate-budget` was parsed by `play` and handed to `MultiRun`/its
children but never consulted, so the budget was decorative. These tests
prove two things: (1) a lone `play <character>` — no governor set — stays
completely unthrottled, and (2) each real outbound-read call site
(`_fetch_world_state`'s `get_character`, `_fetch_active_events`,
`_fetch_raids`, `_sync_bank`, `_fetch_open_orders`) and the action-dispatch
site in `_execute` actually CONSULT the governor when one is wired in.
"""

from unittest.mock import MagicMock, patch

import httpx

from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.utils.rate_budget import WindowBudget
from artifactsmmo_cli.utils.rate_governor import RateGovernor
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema, make_get_character_result


class _FakeTime:
    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def clock(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


def _empty_page() -> MagicMock:
    page = MagicMock()
    page.data = []
    return page


def test_governors_default_to_none_so_single_character_play_is_unthrottled():
    player = GamePlayer(character="hero")
    assert player._data_governor is None
    assert player._action_governor is None


def test_a_data_read_acquires_from_the_data_governor():
    fake = _FakeTime()
    player = GamePlayer(character="hero")
    governor = RateGovernor(
        WindowBudget(second=1, minute=None, hour=None, day=None),
        clock=fake.clock, sleep=fake.sleep,
    )
    player.set_rate_governors(data=governor, action=governor)
    player._acquire_data()
    player._acquire_data()
    assert fake.slept == [1.0]


def test_acquiring_without_a_governor_is_a_no_op():
    GamePlayer(character="hero")._acquire_data()
    GamePlayer(character="hero")._acquire_action()


class TestGovernorConsultedOnRealDataReadPaths:
    """A no-op-when-unset test alone cannot distinguish 'wired correctly' from
    'never reached' — these drive the governor through the real call sites
    the brief names, with a MagicMock governor so each acquire() call is
    individually observable."""

    def test_fetch_world_state_acquires_for_character_events_and_raids(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()
        char = make_char_schema()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=_empty_page()):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=_empty_page()):
                    player._fetch_world_state(client)
        # 1 character read + 1 events page (cache miss) + 1 raids page (cache miss)
        assert governor.acquire.call_count == 3

    def test_a_global_reads_cache_hit_does_not_re_acquire(self):
        """The task brief is explicit: acquire() must sit inside the fetch
        function (the side that actually sends a request), not at the
        GlobalReadsCache.get_or_fetch call site — otherwise a cache HIT,
        which sends no request, would still spend a budget token it never
        used. Calling _fetch_world_state twice inside the cache TTL proves
        this: the character read (never cached) acquires again, but the
        events/raids fetch functions are not even invoked."""
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()
        char = make_char_schema()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events",
                       return_value=_empty_page()) as mock_events:
                with patch("artifactsmmo_cli.ai.player.get_all_raids",
                           return_value=_empty_page()) as mock_raids:
                    player._fetch_world_state(client)
                    governor.reset_mock()
                    player._fetch_world_state(client)
        assert mock_events.call_count == 1  # not called again: cache HIT
        assert mock_raids.call_count == 1   # not called again: cache HIT
        assert governor.acquire.call_count == 1  # only the character read

    def test_fetch_active_events_acquires_once_per_page(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()

        def make_ev(code):
            ev = MagicMock()
            ev.code = code
            ev.expiration = MagicMock()
            return ev

        page1 = MagicMock()
        page1.data = [make_ev(f"event_{i}") for i in range(100)]
        page2 = MagicMock()
        page2.data = [make_ev("gemstone_merchant")]
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", side_effect=[page1, page2]):
            player._fetch_active_events(client)
        assert governor.acquire.call_count == 2

    def test_fetch_active_events_acquires_again_on_a_retried_attempt(self):
        """A retried attempt is itself a real outbound request (the first
        attempt's bytes went out even though it timed out), so it must also
        consult the governor — acquire() is not just a once-per-page gate."""
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()
        ev = MagicMock()
        ev.code = "gemstone_merchant"
        ev.expiration = MagicMock()
        page = MagicMock()
        page.data = [ev]
        with patch("artifactsmmo_cli.ai.player.get_all_active_events",
                   side_effect=[httpx.ReadTimeout("timed out"), page]):
            with patch("artifactsmmo_cli.ai.player.time.sleep"):
                player._fetch_active_events(client)
        assert governor.acquire.call_count == 2

    def test_fetch_raids_acquires_once_per_page(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=_empty_page()):
            player._fetch_raids(client)
        assert governor.acquire.call_count == 1

    def test_sync_bank_acquires_once_per_items_page_plus_once_for_details(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        state = make_state()
        client = MagicMock()

        def make_slot(code):
            slot = MagicMock()
            slot.code = code
            slot.quantity = 1
            return slot

        page1 = MagicMock()
        page1.data = [make_slot(f"item_{i}") for i in range(100)]
        page2 = MagicMock()
        page2.data = [make_slot("last_item")]
        details = MagicMock()
        details.data = MagicMock()
        details.data.gold = 0
        details.data.slots = 50
        with patch("artifactsmmo_cli.ai.player.get_bank_items", side_effect=[page1, page2]):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=details):
                player._sync_bank(client, state)
        # 2 bank_items pages + 1 bank_details call
        assert governor.acquire.call_count == 3

    def test_fetch_open_orders_acquires_once_per_page(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock())
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_my_ge_orders", return_value=_empty_page()):
            player._fetch_open_orders(client)
        assert governor.acquire.call_count == 1


class TestGovernorConsultedBeforeActionDispatch:
    def test_execute_acquires_from_the_action_governor_once_and_not_the_data_governor(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        data_governor = MagicMock()
        action_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=action_governor)
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        char = make_char_schema(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            _new_state, outcome = player._execute(action, client)
        assert outcome == "ok"
        assert action_governor.acquire.call_count == 1
        assert data_governor.acquire.call_count == 0
