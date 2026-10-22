"""Tests for GamePlayer._fetch_active_events and active_events in _fetch_world_state."""

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.live_event import LiveEvent
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.test_actions_execute import make_char_schema, make_get_character_result


def _event(code, expiry, x=10, y=1, layer="overworld"):
    """An active-event row: its code, expiry, and the one map it stands on."""
    ev = MagicMock()
    ev.code = code
    ev.expiration = expiry
    ev.map_ = MagicMock(x=x, y=y, layer=layer)
    return ev


class TestFetchActiveEvents:
    def test_returns_empty_on_none_response(self):
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=None):
            result = player._fetch_active_events(client)
        assert result == {}

    def test_returns_empty_on_empty_data(self):
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        page = MagicMock()
        page.data = []
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=page):
            result = player._fetch_active_events(client)
        assert result == {}

    def test_maps_code_to_expiration(self):
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        page = MagicMock()
        page.data = [_event("gemstone_merchant", expiry)]

        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=page):
            result = player._fetch_active_events(client)

        assert result == {"gemstone_merchant": LiveEvent(expiry, ((10, 1, "overworld"),))}

    def test_an_event_standing_on_two_maps_keeps_both(self):
        """Two rows of one event (two instances) are one event on both maps,
        live until the later expiry."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        early = datetime(2026, 10, 18, 2, 0, tzinfo=timezone.utc)
        late = datetime(2026, 10, 18, 2, 30, tzinfo=timezone.utc)
        page = MagicMock()
        page.data = [_event("corrupted_owlbear", early, 10, 1),
                     _event("corrupted_owlbear", late, 10, 2)]
        with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=page):
            result = player._fetch_active_events(MagicMock())
        assert result == {"corrupted_owlbear": LiveEvent(
            late, ((10, 1, "overworld"), (10, 2, "overworld")))}

    def test_paginates_when_full_page_returned(self):
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        expiry1 = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)
        expiry2 = datetime(2026, 5, 20, 13, 0, 0, tzinfo=timezone.utc)

        page1 = MagicMock()
        page1.data = [_event(f"event_{i}", expiry1) for i in range(100)]

        page2 = MagicMock()
        page2.data = [_event("gemstone_merchant", expiry2)]

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            side_effect=[page1, page2],
        ):
            result = player._fetch_active_events(client)

        assert len(result) == 101
        assert result["gemstone_merchant"].expiration == expiry2

    def test_stops_after_partial_page(self):
        """Stops pagination when page returns fewer than 100 items."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        page = MagicMock()
        page.data = [_event("festival", expiry)]  # less than 100 → no next page

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            return_value=page,
        ) as mock_api:
            result = player._fetch_active_events(client)

        mock_api.assert_called_once()
        assert result == {"festival": LiveEvent(expiry, ((10, 1, "overworld"),))}

    def test_retries_transient_httperror_then_succeeds(self):
        """A one-off ReadTimeout is retried, not fatal — matches get_character resilience."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        client = MagicMock()
        expiry = datetime(2026, 5, 20, 12, 0, 0, tzinfo=timezone.utc)

        page = MagicMock()
        page.data = [_event("gemstone_merchant", expiry)]

        with patch(
            "artifactsmmo_cli.ai.player.get_all_active_events",
            side_effect=[httpx.ReadTimeout("timed out"), page],
        ) as mock_api:
            with patch("artifactsmmo_cli.ai.player.time.sleep"):
                result = player._fetch_active_events(client)

        assert mock_api.call_count == 2
        assert result == {"gemstone_merchant": LiveEvent(expiry, ((10, 1, "overworld"),))}

    def test_returns_empty_when_httperror_persists(self):
        """A persistent transient error returns empty (events are non-critical), never raises."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
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
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        player.state = None
        char = make_char_schema()
        client = MagicMock()

        expiry = datetime.now(timezone.utc) + timedelta(hours=1)

        events_page = MagicMock()
        events_page.data = [_event("gemstone_merchant", expiry)]

        empty_raids = MagicMock()
        empty_raids.data = []

        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=events_page):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_raids):
                    state = player._fetch_world_state(client)

        assert isinstance(state, WorldState)
        assert state.active_events == {"gemstone_merchant": expiry}

    def test_the_live_events_maps_reach_game_data(self):
        """Each world fetch hands the planner the tiles the live events stand
        on; an expired one (a cached read up to a TTL stale) stands nowhere."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        player.state = None
        player.game_data = GameData()
        now = datetime.now(timezone.utc)
        events_page = MagicMock()
        events_page.data = [_event("corrupted_owlbear", now + timedelta(hours=1), 10, 1),
                            _event("bandit_camp", now - timedelta(minutes=1), 10, 0)]
        empty = MagicMock()
        empty.data = []
        with patch("artifactsmmo_cli.ai.player.get_character",
                   return_value=make_get_character_result(make_char_schema())):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=events_page):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty):
                    state = player._fetch_world_state(MagicMock())
        assert set(state.active_events) == {"corrupted_owlbear"}
        assert player.game_data.active_event_codes == {"corrupted_owlbear"}
        assert player.game_data.active_event_maps == {"corrupted_owlbear": [(10, 1, "overworld")]}

    def test_the_learned_recycle_totals_reach_game_data(self):
        """Recycle totals and craft yields are learned fleet-wide; each world
        fetch refreshes them onto the planner's GameData."""
        history = MagicMock()
        history.fleet_recycle_totals.return_value = {"copper_helmet": 2}
        history.fleet_craft_yields.return_value = {"copper_bar": 1}
        player = GamePlayer(character="hero", history=history)
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
        player.state = None
        player.game_data = GameData()
        empty_page = MagicMock()
        empty_page.data = []
        with patch("artifactsmmo_cli.ai.player.get_character",
                   return_value=make_get_character_result(make_char_schema())):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_page):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_page):
                    player._fetch_world_state(MagicMock())
        assert dict(player.game_data.recycle_totals) == {"copper_helmet": 2}
        assert dict(player.game_data.learned_craft_yields) == {"copper_bar": 1}

    def test_active_events_empty_when_no_events(self):
        """_fetch_world_state yields empty active_events when API returns nothing."""
        player = GamePlayer(character="hero")
        player._offline_timing = committed_timing()
        player._learned_drops = LearnedDrops.empty()
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
