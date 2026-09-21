"""A Grand Exchange order that vanished from the book must vanish from our index.

The GE order index is loaded ONCE per run (`GameData._load_ge_orders`, called
from `GameData.load`). Every order it holds is a snapshot of the book at
startup, and orders are filled and cancelled by other accounts continuously.
Nothing ever told the index that one of its orders was gone, so a consumed
order stayed the "best" order for its item for the rest of the session:
`GeFillSellOrderAction.is_applicable` kept matching it, the planner kept
emitting the buy, and the server kept answering HTTP 404 "Order not found" at
cooldown 0.0 — a free-spin livelock against the per-IP budget that binds the
whole fleet.

Live 2026-09-21 (Robby, session-20260921-055111-211536): 64 of 424 cycles
(15.1%) were `GeBuy(sunflower×N@6ab05bb12603c103d6331759)` → HTTP 404, in seven
bursts spread over eight hours, the quantity climbing 3 → 6 → 21 → 24 → 33 →
36 → 51 as the unmet demand grew.

The 404 is the freshest and most authoritative statement anyone will ever make
about that order, so it drives a re-read of that ONE item's book (the API's
`code=` filter — one request, on failure only). That both retires the ghost and
discovers the next real order for the item, which blind eviction could not do:
the index keeps one order per item, so dropping it would wall the item for the
session even with five live orders standing.
"""

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
from artifactsmmo_api_client.models.ge_order_type import GEOrderType

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import (
    make_char_schema,
    make_get_character_result,
)


def _order(order_id: str, code: str, price: int, quantity: int) -> SimpleNamespace:
    return SimpleNamespace(id=order_id, code=code, price=price, quantity=quantity)


class _Page:
    def __init__(self, data):
        self.data = data


def _book(pages: dict[tuple[GEOrderType, str | None], list[SimpleNamespace]]):
    """A fake `get_ge_orders` serving `pages` keyed by (side, code filter).

    Records every call so a test can assert the item filter was actually sent —
    an unfiltered re-read would page the WHOLE book, which is the request cost
    this design exists to avoid.
    """
    calls: list[dict] = []

    def fake_sync(client, type_, page, size, **kwargs):
        code = kwargs.get("code")
        calls.append({"side": type_, "code": code, "page": page})
        if page != 1:
            return _Page([])
        return _Page(list(pages.get((type_, code), [])))

    return fake_sync, calls


class TestRefreshGeOrdersForItem:
    def test_replaces_a_vanished_order_with_the_next_real_one(self, monkeypatch):
        """The ghost goes AND the still-standing order takes its place. Blind
        eviction would leave the item with no GE source for the session."""
        fake_sync, _calls = _book({
            (GEOrderType.SELL, "sunflower"): [_order("live-2", "sunflower", 9, 40)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("ghost-1", 6, 99)}

        gd.refresh_ge_orders_for_item(client=None, item_code="sunflower")

        assert gd.ge_best_sell_order("sunflower") == ("live-2", 9, 40)

    def test_drops_the_item_when_the_book_has_no_order_left(self, monkeypatch):
        """Every order for the item is gone: absence must be encoded as None,
        not as the last order we happened to see."""
        fake_sync, _calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("ghost-1", 6, 99)}

        gd.refresh_ge_orders_for_item(client=None, item_code="sunflower")

        assert gd.ge_best_sell_order("sunflower") is None

    def test_asks_the_api_for_that_item_only(self, monkeypatch):
        """One request per side, carrying the `code` filter. Re-paging the whole
        book on every 404 would cost more budget than the livelock it fixes."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()

        gd.refresh_ge_orders_for_item(client=None, item_code="sunflower")

        assert [(c["side"], c["code"]) for c in calls] == [
            (GEOrderType.BUY, "sunflower"),
            (GEOrderType.SELL, "sunflower"),
        ]

    def test_leaves_other_items_untouched(self, monkeypatch):
        """The 404 spoke about one order for one item and says nothing about
        the rest of the book."""
        fake_sync, _calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("ghost-1", 6, 99), "apple": ("a-1", 3, 5)}

        gd.refresh_ge_orders_for_item(client=None, item_code="sunflower")

        assert gd.ge_best_sell_order("apple") == ("a-1", 3, 5)

    def test_refreshes_the_buy_side_too(self, monkeypatch):
        """A fill of a standing BUY order 404s for exactly the same reason, and
        the sell-side index is no more authoritative than the buy-side one."""
        fake_sync, _calls = _book({
            (GEOrderType.BUY, "sunflower"): [_order("buy-2", "sunflower", 12, 7)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_buy_orders = {"sunflower": ("ghost-b", 20, 99)}

        gd.refresh_ge_orders_for_item(client=None, item_code="sunflower")

        assert gd.ge_best_buy_order("sunflower") == ("buy-2", 12, 7)


class TestLoadGeOrdersEvicts:
    def test_a_reload_forgets_an_item_the_book_no_longer_lists(self, monkeypatch):
        """`_load_ge_orders` merged each fresh index into the old one, so an
        item whose every order was gone kept its stale entry forever. Merging is
        indistinguishable from replacing on the startup call (the index starts
        empty), which is why the fault survived: only a SECOND load exposes it."""
        first, _c1 = _book({
            (GEOrderType.SELL, None): [_order("s-1", "sunflower", 6, 99)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", first)
        gd = GameData()
        gd._load_ge_orders(client=None)
        assert gd.ge_best_sell_order("sunflower") == ("s-1", 6, 99)

        second, _c2 = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", second)
        gd._load_ge_orders(client=None)

        assert gd.ge_best_sell_order("sunflower") is None


class TestPlayerRefreshesOn404:
    """The player loop is where the 404 is seen, so it is where the index learns."""

    @staticmethod
    def _run_fill_against_404(gd: GameData | None):
        player = GamePlayer(character="hero")
        player.state = make_state(x=5, y=1)
        player.game_data = gd
        action = GeFillSellOrderAction(
            order_id="ghost-1", item_code="sunflower", price=6,
            quantity=51, ge_location=(5, 1),
        )
        char = make_char_schema(x=5, y=1)
        empty = MagicMock()
        empty.data = []
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.action_ge_buy",
                       side_effect=ApiActionError(404, "Order not found.")), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty):
                _state, outcome = player._execute(action, MagicMock())
        return outcome

    def test_a_404_on_a_ge_fill_retires_the_ghost_order(self, monkeypatch):
        """Without this the identical impossible buy is re-planned every cycle:
        `is_applicable` reads the index, and only the index can stop it."""
        fake_sync, _calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("ghost-1", 6, 99)}

        outcome = self._run_fill_against_404(gd)

        assert outcome == "error:HTTP_404"
        assert gd.ge_best_sell_order("sunflower") is None

    def test_a_404_with_no_game_data_still_completes_the_cycle(self, monkeypatch):
        """`game_data` is None before the first load; the refresh must not be
        the thing that crashes a run."""
        fake_sync, _calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)

        assert self._run_fill_against_404(None) == "error:HTTP_404"

    def test_a_transport_failure_during_the_refresh_does_not_kill_the_cycle(
        self, monkeypatch
    ):
        """The re-read is a repair, not the cycle's purpose. A transport error
        while attempting it leaves the ghost indexed — the next 404 retries the
        repair — but the cycle still reports the outcome it actually got."""
        def explode(client, type_, page, size, **kwargs):
            raise httpx.ConnectError("connection reset")

        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", explode)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("ghost-1", 6, 99)}

        outcome = self._run_fill_against_404(gd)

        assert outcome == "error:HTTP_404"
        assert gd.ge_best_sell_order("sunflower") == ("ghost-1", 6, 99)
