"""The rate budget actually throttles outbound requests.

Task 17: `--rate-budget` was parsed by `play` and handed to `MultiRun`/its
children but never consulted, so the budget was decorative. These tests
prove two things: (1) a lone `play <character>` — no governor set — stays
completely unthrottled, and (2) each real outbound-read call site
(`_fetch_world_state`'s `get_character`, `_fetch_active_events`,
`_fetch_raids`, `_sync_bank`, `_fetch_open_orders`) and the action-dispatch
site in `_execute` actually CONSULT the governor when one is wired in.

Whole-branch review finding: `_sync_bank` (bank items + bank details) and
`_fetch_open_orders` (GE orders) hit `/my/*` endpoints that are NOT
`/my/{name}/action/*`, so per docs.artifactsmmo.com they are ACCOUNT-scoped
reads (300/hour total -- the tightest bucket of the three) rather than
data-scoped (2000/hour). They were wrongly charged against the data governor
and the account bucket -- the one this whole epic exists to protect -- went
completely unenforced. The `..._not_data` tests below pin the fix: they
assert the account governor was consulted AND the data governor was NOT.
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
    assert player._account_governor is None


def test_a_data_read_acquires_from_the_data_governor():
    fake = _FakeTime()
    player = GamePlayer(character="hero")
    governor = RateGovernor(
        WindowBudget(second=1, minute=None, hour=None, day=None),
        clock=fake.clock, sleep=fake.sleep,
    )
    player.set_rate_governors(data=governor, action=governor, account=governor)
    player._acquire_data()
    player._acquire_data()
    assert fake.slept == [1.0]


def test_wiring_governors_prices_the_planner_in_requests():
    """Wiring a governor IS the statement "this process gets one action per
    `sustainable_interval()` seconds", so it is also when the planner must stop
    pricing actions at their cooldown alone. The ACTION bucket is the binding
    one: every planner action is a `/my/{name}/action/*` call. 300/hour = 12s
    per request."""
    fake = _FakeTime()
    player = GamePlayer(character="hero")
    action_governor = RateGovernor(
        WindowBudget(second=10, minute=None, hour=300, day=None),
        clock=fake.clock, sleep=fake.sleep,
    )
    other = RateGovernor(
        WindowBudget(second=None, minute=None, hour=6000, day=None),
        clock=fake.clock, sleep=fake.sleep,
    )
    player.set_rate_governors(data=other, action=action_governor, account=other)
    assert player.planner.action_floor_seconds == 12.0


def test_an_ungoverned_player_leaves_the_planner_unpriced():
    """Every single-character run: no governor, no floor, and the planner is
    byte-identical to its pre-change self."""
    assert GamePlayer(character="hero").planner.action_floor_seconds == 0.0


def test_acquiring_without_a_governor_is_a_no_op():
    GamePlayer(character="hero")._acquire_data()
    GamePlayer(character="hero")._acquire_action()
    GamePlayer(character="hero")._acquire_account()


class TestGovernorConsultedOnRealDataReadPaths:
    """A no-op-when-unset test alone cannot distinguish 'wired correctly' from
    'never reached' — these drive the governor through the real call sites
    the brief names, with a MagicMock governor so each acquire() call is
    individually observable."""

    def test_fetch_world_state_acquires_for_character_events_and_raids(self):
        player = GamePlayer(character="hero")
        governor = MagicMock()
        player.set_rate_governors(data=governor, action=MagicMock(), account=MagicMock())
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
        player.set_rate_governors(data=governor, action=MagicMock(), account=MagicMock())
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
        player.set_rate_governors(data=governor, action=MagicMock(), account=MagicMock())
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
        player.set_rate_governors(data=governor, action=MagicMock(), account=MagicMock())
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
        player.set_rate_governors(data=governor, action=MagicMock(), account=MagicMock())
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=_empty_page()):
            player._fetch_raids(client)
        assert governor.acquire.call_count == 1


class TestAccountScopedReadsUseTheAccountGovernor:
    """`/my/bank`, `/my/bank/items`, and `/my/grandexchange/orders` are
    account-scoped (`/my/*`, not `/my/{name}/action/*`); the account bucket
    is 300/hour total -- the tightest of the three -- so these must draw
    from `_account_governor`, never `_data_governor`."""

    def test_sync_bank_acquires_from_the_account_governor_not_data(self):
        player = GamePlayer(character="hero")
        data_governor = MagicMock()
        account_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=MagicMock(), account=account_governor)
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
        assert account_governor.acquire.call_count == 3
        assert data_governor.acquire.call_count == 0

    def test_fetch_open_orders_acquires_from_the_account_governor_not_data(self):
        player = GamePlayer(character="hero")
        data_governor = MagicMock()
        account_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=MagicMock(), account=account_governor)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_my_ge_orders", return_value=_empty_page()):
            player._fetch_open_orders(client)
        assert account_governor.acquire.call_count == 1
        assert data_governor.acquire.call_count == 0

    def test_sync_pending_acquires_from_the_account_governor_not_data(self):
        """`/my/pending_items` is tagged "My account" in the OpenAPI spec,
        the same tag as `/my/bank` and `/my/bank/items` -- so it must draw
        from `_account_governor`, never `_data_governor`. Previously
        `_sync_pending` charged no governor at all, undercounting the
        tightest bucket by roughly half at the periodic-refresh site where
        it runs immediately after `_sync_bank`."""
        player = GamePlayer(character="hero")
        data_governor = MagicMock()
        account_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=MagicMock(), account=account_governor)
        state = make_state()
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_pending_items", return_value=_empty_page()):
            player._sync_pending(client, state)
        assert account_governor.acquire.call_count == 1
        assert data_governor.acquire.call_count == 0


class TestAchievementLookupUsesTheDataGovernor:
    """`/achievements/{code}` is tagged "Achievements" in the OpenAPI spec
    (not "My account"), so `_resolve_bank_unlock_monster` is a data-scoped
    public read like `get_character`/`get_all_active_events`, and must draw
    from `_data_governor`, never `_account_governor`."""

    def test_resolve_bank_unlock_monster_acquires_from_the_data_governor_not_account(self):
        player = GamePlayer(character="hero")
        data_governor = MagicMock()
        account_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=MagicMock(), account=account_governor)
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
            player._resolve_bank_unlock_monster(client, "some_achievement")
        assert data_governor.acquire.call_count == 1
        assert account_governor.acquire.call_count == 0


class TestGovernorConsultedBeforeActionDispatch:
    def test_execute_acquires_from_the_action_governor_once_and_not_the_data_governor(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        data_governor = MagicMock()
        action_governor = MagicMock()
        player.set_rate_governors(data=data_governor, action=action_governor, account=MagicMock())
        client = MagicMock()
        action = MoveAction(x=3, y=5)
        char = make_char_schema(x=3, y=5)
        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            _new_state, outcome = player._execute(action, client)
        assert outcome == "ok"
        assert action_governor.acquire.call_count == 1
        assert data_governor.acquire.call_count == 0
