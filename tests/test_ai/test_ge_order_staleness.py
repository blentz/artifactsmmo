"""A Grand Exchange order that vanished from the book must vanish from our index.

The GE order index used to be loaded ONCE per run (`GameData.load_ge_orders`,
called from `GameData.load`). Every order it held was a snapshot of the book at
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

That covers orders that GO. `TestPeriodicReload` covers the other direction:
the 404 hook can only ever shrink the index, so an order another account posts
after startup was invisible for the rest of the run until the whole book is
re-read on a wall-clock interval.
"""

import io
from contextlib import redirect_stdout
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import httpx
import pytest
from artifactsmmo_api_client.models.ge_order_type import GEOrderType

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.ge_fill_sell import GeFillSellOrderAction
from artifactsmmo_cli.ai.constants import (
    GE_ORDER_REFRESH_INTERVAL_SECONDS,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import (
    make_char_schema,
    make_get_character_result,
)
from tests.test_ai.test_player_run import _patch_game_data_load


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
        """`load_ge_orders` merged each fresh index into the old one, so an
        item whose every order was gone kept its stale entry forever. Merging is
        indistinguishable from replacing on the startup call (the index starts
        empty), which is why the fault survived: only a SECOND load exposes it."""
        first, _c1 = _book({
            (GEOrderType.SELL, None): [_order("s-1", "sunflower", 6, 99)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", first)
        gd = GameData()
        gd.load_ge_orders(client=None)
        assert gd.ge_best_sell_order("sunflower") == ("s-1", 6, 99)

        second, _c2 = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", second)
        gd.load_ge_orders(client=None)

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
                _state, outcome, _executed = player._execute(action, MagicMock())
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


class TestPeriodicReload:
    """Retiring a ghost on its 404 only ever SHRINKS the index. Orders posted
    after startup stayed invisible for the whole run, so a route the book could
    supply was priced as if no order existed. The book is re-read on a wall-clock
    interval, which is the only thing that can make the index grow again.

    Measured 2026-09-21 against the live book: 32 buy orders on 1 page, 1575
    sell orders on 16 — 17 requests per reload, four reloads an hour. The
    endpoint answers `x-ratelimit-limit-hour: 2000`, i.e. the DATA bucket, so
    that is ~17% of one child's divided data share at five children, and it is
    metered through the data governor rather than taken for free.
    """

    @staticmethod
    def _player_at(gd: GameData | None, elapsed: float | None):
        """A player whose GE clock last ticked `elapsed` seconds ago (None = the
        clock has never been set, i.e. the first cycle of a run)."""
        player = GamePlayer(character="hero")
        player.game_data = gd
        if elapsed is not None:
            player._ge_orders_reloaded_at = 1000.0 - elapsed
        return player

    def test_the_first_cycle_only_starts_the_clock(self, monkeypatch):
        """The startup load happened seconds ago, so cycle 1 owes nothing. What
        it must do is record WHEN, or the interval has no origin to measure from."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        gd = GameData()
        player = self._player_at(gd, elapsed=None)

        player._maybe_refresh_ge_orders(MagicMock())

        assert calls == []
        assert player._ge_orders_reloaded_at == 1000.0

    def test_does_not_reload_before_the_interval(self, monkeypatch):
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        player = self._player_at(GameData(), elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS - 1)

        player._maybe_refresh_ge_orders(MagicMock())

        assert calls == []

    def test_reloads_once_the_interval_has_elapsed(self, monkeypatch):
        """An order posted after startup becomes reachable — the whole point.
        Before this the index could only ever lose entries."""
        fake_sync, _calls = _book({
            (GEOrderType.SELL, None): [_order("posted-later", "sunflower", 5, 60)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        gd = GameData()
        player = self._player_at(gd, elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS)

        player._maybe_refresh_ge_orders(MagicMock())

        assert gd.ge_best_sell_order("sunflower") == ("posted-later", 5, 60)

    def test_a_reload_re_arms_the_clock(self, monkeypatch):
        """Without re-arming, every later cycle is overdue and the book is paged
        on EVERY cycle — 17 requests a cycle instead of 17 a quarter hour."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        player = self._player_at(GameData(), elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS)

        player._maybe_refresh_ge_orders(MagicMock())
        after_first = len(calls)
        player._maybe_refresh_ge_orders(MagicMock())

        assert player._ge_orders_reloaded_at == 1000.0
        assert len(calls) == after_first

    def test_does_nothing_before_the_first_game_data_load(self, monkeypatch):
        """`game_data` is None until the initial load completes."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        player = self._player_at(None, elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS)

        player._maybe_refresh_ge_orders(MagicMock())

        assert calls == []

    def test_a_transport_failure_keeps_the_previous_book(self, monkeypatch):
        """A half-read book must not replace a whole one, and a failing endpoint
        must not be re-paged every cycle — the clock re-arms either way."""
        def explode(client, type_, page, size, **kwargs):
            raise httpx.ConnectError("connection reset")

        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", explode)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("s-1", 6, 99)}
        player = self._player_at(gd, elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS)

        with redirect_stdout(io.StringIO()):
            player._maybe_refresh_ge_orders(MagicMock())

        assert gd.ge_best_sell_order("sunflower") == ("s-1", 6, 99)
        assert player._ge_orders_reloaded_at == 1000.0

    def test_every_page_is_charged_to_the_data_bucket(self, monkeypatch):
        """17 requests taken for free would silently overdraw the budget the
        whole fleet divides. One acquire per REQUEST, not one per reload.

        The sell side must span more than one page or the two rules are
        indistinguishable — the real book needed 16 pages when this was
        measured, and a single-page fake would pass either way.
        """
        calls: list[int] = []

        def fake_sync(client, type_, page, size, **kwargs):
            calls.append(page)
            if type_ is not GEOrderType.SELL:
                return _Page([])
            if page == 1:
                return _Page([_order(f"s{i}", f"item{i}", 3, 1) for i in range(100)])
            return _Page([_order("tail", "last_item", 3, 1)])

        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        monkeypatch.setattr("artifactsmmo_cli.ai.player.time.monotonic", lambda: 1000.0)
        player = self._player_at(GameData(), elapsed=GE_ORDER_REFRESH_INTERVAL_SECONDS)
        acquired: list[int] = []
        player._data_governor = SimpleNamespace(
            acquire=lambda: acquired.append(1),
            sustainable_interval=lambda: 0.0,
        )

        player._maybe_refresh_ge_orders(MagicMock())

        assert calls == [1, 1, 2], "the sell side must really paginate"
        assert len(acquired) == len(calls)

    def test_the_startup_load_is_still_unmetered(self, monkeypatch):
        """`GameData.load` runs before any governor is wired; charging it would
        need a bucket that does not exist yet."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()

        gd.load_ge_orders(client=None)

        assert len(calls) > 0


def test_the_run_loop_actually_calls_the_periodic_reload():
    """Runtime activation: a timer nothing drives is dead code. The reload must
    fire from run()'s own cycle, not merely be callable."""
    player = GamePlayer(character="hero")
    client = MagicMock()
    seen: list[str] = []

    def stop_after_one_cycle():
        raise KeyboardInterrupt

    manager = MagicMock()
    with patch.object(manager, "client", client), \
            patch("artifactsmmo_cli.ai.player.ClientManager", return_value=manager), \
            _patch_game_data_load(), \
            patch.object(player, "_fetch_world_state", return_value=make_state(hp=100, max_hp=150)), \
            patch.object(player, "_wait_for_cooldown", side_effect=stop_after_one_cycle), \
            patch.object(player, "_reconcile_open_orders"), \
            patch.object(player, "_maybe_periodic_refresh"), \
            patch.object(player, "_maybe_refresh_ge_orders",
                         side_effect=lambda c: seen.append("ge")), \
            patch.object(player, "_build_actions", side_effect=lambda: []), \
            patch("artifactsmmo_cli.ai.player.time.sleep"), \
            redirect_stdout(io.StringIO()):
        with pytest.raises(KeyboardInterrupt):
            player.run()

    assert seen == ["ge"]


class TestOfferShortRefresh:
    """HTTP 434 is the PARTIAL twin of the 404: the order still stands, but
    other accounts have drained it below what our snapshot recorded.

    Every build site gates on the cached quantity — `craft_ladder.py:50`
    (`order[2] < qty`), `goals/gathering.py:632` and `goals/progression.py:534`
    — and none of them clamps the ask, so a 434 can only mean that cached
    number is wrong. The order id stays perfectly valid while its quantity
    drains, so the 404 hook never fires and the stale quantity ages forever.

    Live 2026-09-21 (Robby): order 6ab0c9cdc215f6bd0f9d7912 was down to 2 units
    while Robby asked it for 51, 24, 12, 6, 6, 6 — 8 cycles at cooldown 0.0, on
    top of 70 404s, for 17.4% of a 448-cycle session.
    """

    @staticmethod
    def _run_fill_against(code: int, message: str, gd: GameData | None):
        player = GamePlayer(character="hero")
        player.state = make_state(x=5, y=1)
        player.game_data = gd
        action = GeFillSellOrderAction(
            order_id="drained-1", item_code="sunflower", price=5,
            quantity=51, ge_location=(5, 1),
        )
        char = make_char_schema(x=5, y=1)
        empty = MagicMock()
        empty.data = []
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.ge_fill_sell.action_ge_buy",
                       side_effect=ApiActionError(code, message)), \
                 patch("artifactsmmo_cli.ai.player.get_character",
                       return_value=make_get_character_result(char)), \
                 patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty), \
                 patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty):
                _state, outcome, _executed = player._execute(action, MagicMock())
        return outcome

    def test_a_434_corrects_the_stale_quantity(self, monkeypatch):
        """The order SURVIVES the refusal — what must change is the quantity we
        believe it holds, or the identical over-sized buy is planned again."""
        fake_sync, _calls = _book({
            (GEOrderType.SELL, "sunflower"): [_order("drained-1", "sunflower", 5, 2)],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("drained-1", 5, 99)}

        outcome = self._run_fill_against(
            434, "This offer does not contain that many items.", gd)

        assert outcome == "error:HTTP_434"
        assert gd.ge_best_sell_order("sunflower") == ("drained-1", 5, 2)

    def test_a_434_can_promote_a_bigger_standing_order(self, monkeypatch):
        """Re-reading the ITEM, not the one order, is what makes this a repair
        rather than a retreat: a sibling order may hold what the drained one
        no longer does (live: 46 units at the same price 5)."""
        fake_sync, _calls = _book({
            (GEOrderType.SELL, "sunflower"): [
                _order("drained-1", "sunflower", 5, 2),
                _order("roomier-2", "sunflower", 5, 46),
            ],
        })
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("drained-1", 5, 99)}

        self._run_fill_against(434, "This offer does not contain that many items.", gd)

        assert gd.ge_best_sell_order("sunflower") == ("roomier-2", 5, 46)

    def test_an_unrelated_structured_error_leaves_the_index_alone(self, monkeypatch):
        """Only the two codes that speak about the ORDER may rewrite the book.
        A 492 (insufficient gold) says nothing about what the order holds."""
        fake_sync, calls = _book({})
        monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_ge_orders", fake_sync)
        gd = GameData()
        gd._ge_sell_orders = {"sunflower": ("drained-1", 5, 99)}

        outcome = self._run_fill_against(492, "Insufficient gold.", gd)

        assert outcome == "error:HTTP_492"
        assert calls == []
        assert gd.ge_best_sell_order("sunflower") == ("drained-1", 5, 99)
