"""Tests for GamePlayer._fetch_active_events and active_events in _fetch_world_state."""

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import httpx

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.test_actions_execute import make_char_schema, make_get_character_result


class TestFetchActiveEvents:
    def test_returns_empty_on_none_response(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=None):
            result = player._fetch_active_events(client)
        assert result == {}

    def test_returns_empty_on_empty_data(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        page = MagicMock()
        page.data = []
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=page):
            result = player._fetch_active_events(client)
        assert result == {}

    def test_maps_code_to_expiration(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        ev = MagicMock()
        ev.code = "gemstone_merchant"
        ev.expiration = expiry

        page = MagicMock()
        page.data = [ev]

        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=page):
            result = player._fetch_active_events(client)

        assert result == {"gemstone_merchant": expiry}

    def test_paginates_when_full_page_returned(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        expiry1 = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        expiry2 = datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc)

        def make_ev(code, expiry):
            ev = MagicMock()
            ev.code = code
            ev.expiration = expiry
            return ev

        page1 = MagicMock()
        page1.data = [make_ev(f"event_{i}", expiry1) for i in range(100)]

        page2 = MagicMock()
        page2.data = [make_ev("gemstone_merchant", expiry2)]

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            side_effect=[page1, page2],
        ):
            result = player._fetch_active_events(client)

        assert len(result) == 101
        assert result["gemstone_merchant"] == expiry2

    def test_stops_after_partial_page(self):
        """Stops pagination when page returns fewer than 100 items."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        ev = MagicMock()
        ev.code = "festival"
        ev.expiration = expiry

        page = MagicMock()
        page.data = [ev]  # less than 100 → no next page

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            return_value=page,
        ) as mock_api:
            result = player._fetch_active_events(client)

        mock_api.assert_called_once()
        assert result == {"festival": expiry}

    def test_retries_transient_httperror_then_succeeds(self):
        """A one-off ReadTimeout is retried, not fatal — matches get_character resilience."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        ev = MagicMock()
        ev.code = "gemstone_merchant"
        ev.expiration = expiry
        page = MagicMock()
        page.data = [ev]

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            side_effect=[httpx.ReadTimeout("timed out"), page],
        ) as mock_api:
            with patch("artifactsmmo_cli.ai.player.time.sleep"):
                result = player._fetch_active_events(client)

        assert mock_api.call_count == 2
        assert result == {"gemstone_merchant": expiry}

    def test_returns_empty_when_httperror_persists(self):
        """A persistent transient error returns empty (events are non-critical), never raises."""
        player = GamePlayer(character="hero")
        client = MagicMock()

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            side_effect=httpx.ReadTimeout("timed out"),
        ):
            with patch("artifactsmmo_cli.ai.player.time.sleep"):
                result = player._fetch_active_events(client)

        assert result == {}


class TestFetchWorldStateActiveEvents:
    def test_active_events_in_returned_world_state(self):
        """_fetch_world_state passes active_events into WorldState."""
        player = GamePlayer(character="hero")
        player.state = None
        char = make_char_schema()
        client = MagicMock()

        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        ev = MagicMock()
        ev.code = "gemstone_merchant"
        ev.expiration = expiry

        events_page = MagicMock()
        events_page.data = [ev]

        empty_raids = MagicMock()
        empty_raids.data = []

        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=events_page):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_raids):
                    state = player._fetch_world_state(client)

        assert isinstance(state, WorldState)
        assert state.active_events == {"gemstone_merchant": expiry}

    def test_active_events_empty_when_no_events(self):
        """_fetch_world_state yields empty active_events when API returns nothing."""
        player = GamePlayer(character="hero")
        player.state = None
        char = make_char_schema()
        client = MagicMock()

        empty_page = MagicMock()
        empty_page.data = []

        empty_raids = MagicMock()
        empty_raids.data = []

        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_page):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_raids):
                    state = player._fetch_world_state(client)

        assert state.active_events == {}
