"""MultiRun: roster discovery, budget split, child argv, headless vs TUI."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.multi.child_event import PlanningEvent, SnapshotEvent
from artifactsmmo_cli.multi.multi_run import MultiRun
from artifactsmmo_cli.utils.rate_budget import parse_rate_limits, split_budget

_RATES = {
    "data": {
        "account": {"second": {"limit": 10}, "hour": {"limit": 300}},
        "data": {"second": {"limit": 10}, "minute": {"limit": 200}, "hour": {"limit": 2000}},
        "action": {"second": {"limit": 10}, "minute": {"limit": 100}, "hour": {"limit": 5000}},
    }
}


def _run(**kwargs) -> MultiRun:
    defaults = dict(verbose=False, dry_run=False, trace=False, learn=False,
                     learn_db=None, tui=False, refresh_game_data=False)
    defaults.update(kwargs)
    return MultiRun(**defaults)


def _snap(character: str = "a") -> CycleSnapshot:
    return CycleSnapshot(
        cycle_index=1, timestamp="2026-07-30T12:00:00Z", character=character,
        x=0, y=0, level=1, xp=0, max_xp=150, hp=120, max_hp=120, gold=0,
        selected_goal="ReachLevel(50)", action="Rest()", outcome="ok",
    )


def _characters_response(*names: str) -> SimpleNamespace:
    return SimpleNamespace(data=[SimpleNamespace(name=n) for n in names])


def _rates_response(payload: dict = _RATES) -> SimpleNamespace:
    return SimpleNamespace(to_dict=lambda: payload)


# --- child_argv --------------------------------------------------------


def test_child_argv_carries_emit_events_and_the_budget():
    budget = split_budget(parse_rate_limits(_RATES), children=5)
    argv = _run().child_argv("alice", budget)
    assert "--emit-events" in argv
    assert "alice" in argv
    assert "--rate-budget" in argv
    assert budget.to_json() in argv


def test_child_argv_never_passes_all_to_a_child():
    """A child spawning its own supervisor would fork-bomb the account."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    assert "--all" not in _run().child_argv("alice", budget)


def test_child_argv_propagates_the_run_flags():
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = MultiRun(verbose=True, dry_run=True, trace=True, learn=True,
                    learn_db="/tmp/l.db", tui=False,
                    refresh_game_data=True).child_argv("alice", budget)
    for flag in ("--verbose", "--dry-run", "--trace", "--learn", "--refresh-game-data"):
        assert flag in argv
    assert "/tmp/l.db" in argv


def test_child_argv_never_passes_tui_to_a_child():
    """Only the parent renders; a child TUI would fight for the terminal."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = MultiRun(verbose=False, dry_run=False, trace=False, learn=False,
                    learn_db=None, tui=True, refresh_game_data=False).child_argv("a", budget)
    assert "--tui" not in argv


def test_child_argv_omits_learn_db_when_learn_is_off():
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = _run(learn=False).child_argv("a", budget)
    assert "--learn" not in argv
    assert "--learn-db" not in argv


def test_child_argv_omits_learn_db_flag_when_learn_db_is_none():
    """--learn with no explicit DB lets the child fall back to its own default."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = _run(learn=True, learn_db=None).child_argv("a", budget)
    assert "--learn" in argv
    assert "--learn-db" not in argv


# --- build_pool ----------------------------------------------------------


def test_an_empty_roster_fails_loudly():
    with pytest.raises(ValueError, match="no characters"):
        _run().build_pool(characters=[], rates=_RATES)


def test_the_budget_is_split_by_the_actual_child_count():
    pool = _run().build_pool(characters=["a", "b"], rates=_RATES)
    assert pool.characters() == ("a", "b")


# --- _on_event -------------------------------------------------------------


def test_on_event_forwards_a_snapshot_to_the_attached_app():
    mrun = _run()
    mock_app = Mock()
    mrun._app = mock_app
    event = SnapshotEvent(character="a", payload=_snap())
    mrun._on_event(event)
    mock_app.update_snapshot.assert_called_once_with(event.payload)


def test_on_event_is_a_noop_with_no_app_attached():
    """Headless mode never attaches an app; a snapshot event must not crash."""
    mrun = _run()
    assert mrun._app is None
    mrun._on_event(SnapshotEvent(character="a", payload=_snap()))  # no raise


def test_on_event_ignores_non_snapshot_events():
    mrun = _run()
    mock_app = Mock()
    mrun._app = mock_app
    mrun._on_event(PlanningEvent(character="a", active=True))
    mock_app.update_snapshot.assert_not_called()


# --- run(): headless vs TUI, and loud failure on bad API data --------------
#
# run() itself needs a real API token and network to exercise for real; every
# collaborator it touches (Config, ClientManager, APIWrapper, GameData,
# WatchApp) is patched here so the method body's OWN logic — roster/rate
# fetch, the None-guards, and which branch runs — is what's under test.


class _FakePool:
    """Stands in for a real SupervisorPool: cheap, and its `run()` completion
    is directly observable, so these tests prove the coroutine was actually
    awaited (not merely constructed)."""

    def __init__(self) -> None:
        self.ran = False

    async def run(self) -> None:
        self.ran = True


def test_run_headless_awaits_the_built_pool():
    fake_pool = _FakePool()
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = _characters_response("a")
        mock_api.get_rate_limits.return_value = _rates_response()
        mock_api_cls.return_value = mock_api

        mrun = _run(tui=False)
        with patch.object(mrun, "build_pool", return_value=fake_pool) as mock_build:
            mrun.run()

        mock_build.assert_called_once_with(["a"], _RATES)
    assert fake_pool.ran is True


def test_run_tui_preloads_game_data_attaches_the_pool_and_runs_the_app():
    fake_pool = _FakePool()
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config") as mock_config_cls,
        patch("artifactsmmo_cli.multi.multi_run.ClientManager") as mock_cm_cls,
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
        patch("artifactsmmo_cli.multi.multi_run.GameData") as mock_game_data_cls,
        patch("artifactsmmo_cli.multi.multi_run.WatchApp") as mock_watch_app_cls,
    ):
        mock_config_cls.from_token_file.return_value = SimpleNamespace(game_data_ttl_minutes=30)
        mock_client = Mock()
        mock_cm_cls.return_value.client = mock_client
        mock_api = Mock()
        mock_api.get_my_characters.return_value = _characters_response("a", "b")
        mock_api.get_rate_limits.return_value = _rates_response()
        mock_api_cls.return_value = mock_api
        loaded_data = Mock()
        mock_game_data_cls.load.return_value = loaded_data
        mock_app = Mock()
        mock_watch_app_cls.return_value = mock_app

        mrun = _run(tui=True)
        with patch.object(mrun, "build_pool", return_value=fake_pool):
            mrun.run()

        mock_game_data_cls.load.assert_called_once_with(
            mock_client, ttl_minutes=30, force_refresh=False)
        mock_watch_app_cls.assert_called_once_with(
            characters=["a", "b"], game_data=loaded_data, api=mock_api)
        mock_app.attach_pool.assert_called_once_with(fake_pool)
        mock_app.run.assert_called_once_with()
        assert mrun._app is mock_app


def test_run_fails_loudly_when_the_roster_call_returns_nothing():
    """get_my_characters() can return None (raise_on_unexpected_status=False);
    a missing roster must fail loudly, never silently become an empty one."""
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = None
        mock_api_cls.return_value = mock_api

        with pytest.raises(RuntimeError, match="characters"):
            _run().run()


def test_run_fails_loudly_when_the_rate_limits_call_returns_nothing():
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = _characters_response("a")
        mock_api.get_rate_limits.return_value = None
        mock_api_cls.return_value = mock_api

        with pytest.raises(RuntimeError, match="rate"):
            _run().run()
