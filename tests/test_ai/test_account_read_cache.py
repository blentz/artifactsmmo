"""AccountReadCache: one fleet-wide copy of each account-scoped read."""

import time
from collections.abc import Callable, Iterator
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.account_read_cache import IDLE_SHARE, KEYS, AccountReadCache


class _Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


@pytest.fixture
def clock() -> _Clock:
    return _Clock()


@pytest.fixture
def make_cache(tmp_path: Path, clock: _Clock) -> Iterator[Callable[[str], AccountReadCache]]:
    """Caches for named siblings on ONE shared DB file, all closed at teardown."""
    opened: list[AccountReadCache] = []
    db = str(tmp_path / "fleet.db")

    def make(owner: str) -> AccountReadCache:
        cache = AccountReadCache(db, owner, account_interval=12.0, clock=clock)
        opened.append(cache)
        return cache

    yield make
    for cache in opened:
        cache.close()


def test_ttl_spends_at_most_the_idle_share_of_the_account_bucket(
        make_cache: Callable[[str], AccountReadCache]) -> None:
    """Each key gets an equal slice of IDLE_SHARE of the account bucket's
    sustainable rate (one request per 12s): refreshing every key at its TTL
    spends exactly IDLE_SHARE of the bucket, whatever each key costs."""
    cache = make_cache("alice")
    costs = {"ge_open_orders": 1, "bank": 3, "pending_items": 1}
    assert set(costs) == set(KEYS)
    requests_per_second = sum(cost / cache.ttl(cost) for cost in costs.values())
    assert requests_per_second == pytest.approx(IDLE_SHARE / 12.0)
    assert cache.ttl(1) == 72.0


def test_a_cold_key_is_fetched_then_served_to_every_sibling(
        make_cache: Callable[[str], AccountReadCache]) -> None:
    alice, bob = make_cache("alice"), make_cache("bob")
    assert alice.lookup("bank") is None  # cold: alice must fetch
    alice.publish("bank", '{"gold": 1}', cost=2)
    assert bob.lookup("bank") == '{"gold": 1}'


def test_a_stale_key_is_refreshed_by_one_sibling_while_the_rest_are_served_stale(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    alice, bob, carol = make_cache("alice"), make_cache("bob"), make_cache("carol")
    alice.publish("ge_open_orders", "[1]", cost=1)
    clock.now += alice.ttl(1)  # exactly stale
    assert bob.lookup("ge_open_orders") is None  # bob takes the lease
    assert carol.lookup("ge_open_orders") == "[1]"  # carol is served stale
    assert alice.lookup("ge_open_orders") == "[1]"
    bob.publish("ge_open_orders", "[2]", cost=1)
    assert carol.lookup("ge_open_orders") == "[2]"


def test_the_lease_holder_itself_is_not_served_stale(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    """A refresher whose fetch failed (nothing published) must be allowed to
    try again rather than read its own stale lease back."""
    alice = make_cache("alice")
    alice.publish("pending_items", "null", cost=1)
    clock.now += alice.ttl(1)
    assert alice.lookup("pending_items") is None
    assert alice.lookup("pending_items") is None


def test_an_expired_lease_is_taken_over(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    """A refresher that crashed mid-fetch delays the refresh by one lease, not
    forever."""
    alice, bob = make_cache("alice"), make_cache("bob")
    alice.publish("bank", "{}", cost=1)
    clock.now += alice.ttl(1)
    assert alice.lookup("bank") is None  # alice leases, then dies
    clock.now += alice.ttl(1)
    assert bob.lookup("bank") is None  # bob takes over


def test_a_cold_key_under_lease_is_fetched_again_rather_than_waited_on(
        make_cache: Callable[[str], AccountReadCache]) -> None:
    """Nothing stale exists to serve, so a second cold lookup fetches too."""
    alice, bob = make_cache("alice"), make_cache("bob")
    assert alice.lookup("bank") is None
    assert bob.lookup("bank") is None


def test_a_costlier_fetch_stays_fresh_longer(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    alice, bob = make_cache("alice"), make_cache("bob")
    alice.publish("bank", "{}", cost=3)
    clock.now += alice.ttl(1)  # stale at cost 1, fresh at cost 3
    assert bob.lookup("bank") == "{}"


def test_an_unknown_key_is_refused(make_cache: Callable[[str], AccountReadCache]) -> None:
    cache = make_cache("alice")
    with pytest.raises(ValueError, match="unknown account read 'gold'"):
        cache.lookup("gold")
    with pytest.raises(ValueError, match="unknown account read 'gold'"):
        cache.publish("gold", "1", cost=1)


def test_a_future_dated_entry_is_stale_not_fresh_forever(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    """After a reboot (or a backwards clock step) a stored `fetched_at` can lie
    in the future. `now - fetched_at` is then negative, which read as "fresh"
    forever and would have served a stale bank to the fleet indefinitely."""
    alice, bob = make_cache("alice"), make_cache("bob")
    alice.publish("bank", "{}", cost=1)
    clock.now -= 100_000.0
    assert bob.lookup("bank") is None  # refetch, not the ancient payload


def test_a_future_dated_lease_does_not_block_the_refresh(
        make_cache: Callable[[str], AccountReadCache], clock: _Clock) -> None:
    alice, bob = make_cache("alice"), make_cache("bob")
    alice.publish("bank", "{}", cost=1)
    clock.now += alice.ttl(1)
    assert alice.lookup("bank") is None  # alice leases
    clock.now -= 100_000.0
    assert bob.lookup("bank") is None  # the lease is from the old clock: take it over


def test_the_default_clock_is_wall_time() -> None:
    assert AccountReadCache.__init__.__defaults__ is not None
    assert time.time in AccountReadCache.__init__.__defaults__
