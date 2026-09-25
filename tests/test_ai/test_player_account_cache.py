"""`play --all` children read account-scoped resources through ONE fleet cache.

Live 2026-09-25: every child polled `/my/grandexchange/orders` every cycle and
synced the bank after every bank action, each against a static 1/5 slice of the
300/hour account bucket. Three children then sat in `_acquire_account` for 18
minutes. These tests drive the real `GamePlayer` read paths against a real
`AccountReadCache` on one shared DB file, with only the API calls mocked.
"""

from collections.abc import Callable, Iterator
from pathlib import Path
from unittest.mock import MagicMock, patch

import httpx
import pytest

from artifactsmmo_cli.ai.account_read_cache import AccountReadCache
from artifactsmmo_cli.ai.actions.ge_cancel_order import GeCancelOrderAction
from artifactsmmo_cli.ai.open_order import OpenOrder, OrderSide
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema
from tests.test_ai.test_player import make_game_data_mock


def _order_row(id_: str, code: str) -> MagicMock:
    row = MagicMock()
    row.id, row.code, row.quantity, row.price = id_, code, 8, 2
    row.type_ = MagicMock(value="sell")
    return row


def _page(*rows: MagicMock) -> MagicMock:
    page = MagicMock()
    page.data = list(rows)
    return page


def _bank_details(gold: int) -> MagicMock:
    details = MagicMock()
    details.data.gold = gold
    details.data.slots = 50
    details.data.next_expansion_cost = 7000
    return details


@pytest.fixture
def make_player(tmp_path: Path) -> Iterator[Callable[[str], GamePlayer]]:
    """Players on one shared cache DB file, as `play --all` children are."""
    caches: list[AccountReadCache] = []
    db = str(tmp_path / "fleet.db")

    def make(name: str) -> GamePlayer:
        player = GamePlayer(character=name)
        player.state = make_state(character=name)
        cache = AccountReadCache(db, name, account_interval=12.0)
        caches.append(cache)
        player.set_account_read_cache(cache)
        return player

    yield make
    for cache in caches:
        cache.close()


def test_a_siblings_order_poll_serves_the_fleet(make_player: Callable[[str], GamePlayer]) -> None:
    alice, bob = make_player("alice"), make_player("bob")
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders",
               return_value=_page(_order_row("o1", "raw_chicken"))) as api:
        alice._reconcile_open_orders(MagicMock())
        bob._reconcile_open_orders(MagicMock())
    assert api.call_count == 1
    assert bob.state is not None
    assert [o.id for o in bob.state.open_orders] == ["o1"]


def test_ages_still_advance_per_cycle_on_a_cached_list(
        make_player: Callable[[str], GamePlayer]) -> None:
    """The TTL cancel reads each order's age in THIS character's cycles, so a
    cache hit must age the orders exactly as a fresh read does."""
    alice = make_player("alice")
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders",
               return_value=_page(_order_row("o1", "raw_chicken"))) as api:
        for _ in range(3):
            alice._reconcile_open_orders(MagicMock())
    assert api.call_count == 1
    assert alice.state is not None
    assert [o.age for o in alice.state.open_orders] == [2]


def test_after_its_own_cancel_a_character_reads_the_orders_fresh(
        make_player: Callable[[str], GamePlayer]) -> None:
    """A cached list still holding the order this character just cancelled
    would re-target it for an HTTP 404; the fresh read is published so every
    sibling drops it too."""
    alice, bob = make_player("alice"), make_player("bob")
    alice.game_data = make_game_data_mock()
    alice.state = make_state(character="alice", x=5, y=1, open_orders=(
        OpenOrder(id="o1", code="raw_chicken", qty=8, price=2, side=OrderSide.SELL, age=30),))
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders",
               return_value=_page(_order_row("o1", "raw_chicken"))):
        alice._reconcile_open_orders(MagicMock())
    with patch("artifactsmmo_cli.ai.actions.ge_cancel_order.action_ge_cancel_order",
               return_value=make_api_result(make_char_schema(x=5, y=1))):
        alice._execute(GeCancelOrderAction(order_id="o1", ge_location=(5, 1)), MagicMock())
    assert alice._ge_orders_dirty is True
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders", return_value=_page()) as api:
        alice._reconcile_open_orders(MagicMock())
        bob._reconcile_open_orders(MagicMock())
    assert api.call_count == 1
    assert alice._ge_orders_dirty is False
    assert bob.state is not None and bob.state.open_orders == ()


def test_a_failed_forced_read_stays_dirty_and_publishes_nothing(
        make_player: Callable[[str], GamePlayer]) -> None:
    alice, bob = make_player("alice"), make_player("bob")
    alice._ge_orders_dirty = True
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders",
               side_effect=httpx.ReadTimeout("timed out")):
        with patch("artifactsmmo_cli.ai.player.time.sleep"):
            alice._reconcile_open_orders(MagicMock())
    assert alice._ge_orders_dirty is True
    with patch("artifactsmmo_cli.ai.player.get_my_ge_orders",
               return_value=_page(_order_row("o2", "shrimp"))) as api:
        bob._reconcile_open_orders(MagicMock())
    assert api.call_count == 1  # nothing was cached, so bob had to ask


def test_a_forced_bank_sync_is_what_siblings_then_read(
        make_player: Callable[[str], GamePlayer]) -> None:
    alice, bob = make_player("alice"), make_player("bob")
    items = _page(MagicMock(code="copper_ore", quantity=10))
    with (patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=items),
          patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=_bank_details(5))):
        assert alice.state is not None and bob.state is not None
        alice._sync_bank(MagicMock(), alice.state)
    after_deposit = _page(MagicMock(code="copper_ore", quantity=30))
    with (patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=after_deposit) as items_api,
          patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=_bank_details(5))):
        # Fresh cache, but alice just deposited: force bypasses it.
        synced = alice._sync_bank(MagicMock(), alice.state, force=True)
        seen_by_bob = bob._sync_bank(MagicMock(), bob.state)
    assert items_api.call_count == 1
    assert synced.bank_items == seen_by_bob.bank_items == {"copper_ore": 30}
    assert seen_by_bob.bank_capacity == 50


def test_pending_items_are_shared_too(make_player: Callable[[str], GamePlayer]) -> None:
    alice, bob = make_player("alice"), make_player("bob")
    entry = MagicMock()
    entry.id = "p1"
    entry.items = [MagicMock(code="gift")]
    with patch("artifactsmmo_cli.ai.player.get_pending_items",
               return_value=_page(entry)) as api:
        assert alice.state is not None and bob.state is not None
        alice._sync_pending(MagicMock(), alice.state)
        seen_by_bob = bob._sync_pending(MagicMock(), bob.state)
    assert api.call_count == 1
    assert seen_by_bob.pending_items == (("p1", "gift"),)
