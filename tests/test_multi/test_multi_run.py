"""MultiRun: roster discovery, budget split, child argv, headless vs TUI."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.learning_db_path import default_learn_db_path
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


# --- coordination DB path: the fix for "play --all is inert by default" ---
#
# `MultiRun` always supplies a shared on-disk coordination path to every
# child via `--coordination-db`, independent of `--learn`. When `--learn` is
# on, that path IS the learning DB path (children already share that file).
# When `--learn` is off, `MultiRun` generates a supervisor-scoped temp path
# (never `:memory:`, which is private per-connection and could never
# coordinate a sibling — same reasoning `commands/play.py` applies to the
# single-character gate).


def test_child_argv_always_carries_coordination_db():
    """Even with `--learn` off, every child gets SOME coordination path —
    this is the fix for "play --all is inert by default"."""
    budget = split_budget(parse_rate_limits(_RATES), children=1)
    argv = _run(learn=False).child_argv("a", budget)
    assert "--coordination-db" in argv


def test_child_argv_coordination_db_is_the_same_path_for_every_child():
    """Two children opening two different temp files would be the same
    silent no-op this fix exists to close — `child_argv` must hand out the
    SAME memoized path across multiple calls on one MultiRun."""
    budget = split_budget(parse_rate_limits(_RATES), children=2)
    mrun = _run(learn=False)
    argv_a = mrun.child_argv("alice", budget)
    argv_b = mrun.child_argv("bob", budget)
    path_a = argv_a[argv_a.index("--coordination-db") + 1]
    path_b = argv_b[argv_b.index("--coordination-db") + 1]
    assert path_a == path_b


def test_coordination_db_path_reuses_the_learn_db_path_when_learn_is_on():
    mrun = _run(learn=True, learn_db="/tmp/shared-learning.db")
    assert mrun._coordination_db_path() == "/tmp/shared-learning.db"


def test_coordination_db_path_reuses_the_default_learn_db_path_when_unset():
    """`--learn` with no explicit `--learn-db` still resolves to a real,
    persisted, shared file (`default_learn_db_path()`) — not a temp file."""
    mrun = _run(learn=True, learn_db=None)
    assert mrun._coordination_db_path() == default_learn_db_path()


def test_coordination_db_path_generates_a_temp_path_when_learn_is_off():
    mrun = _run(learn=False)
    path = mrun._coordination_db_path()
    assert path != default_learn_db_path()
    assert "artifactsmmo-coordination-" in path


def test_coordination_db_path_is_memoized():
    """Computed ONCE per MultiRun, not once per call — otherwise every
    `child_argv` call (one per character) would generate a DIFFERENT temp
    path, defeating the whole point of a shared board."""
    mrun = _run(learn=False)
    assert mrun._coordination_db_path() == mrun._coordination_db_path()


def test_coordination_db_path_computation_is_pure_no_file_created():
    """Computing the path must not touch the filesystem — only a REAL child
    subprocess's own `CoordinationStore.__init__` should ever create the
    file. This is what keeps `child_argv`/`build_pool` safe to call directly
    from a test without leaking a temp file into the OS temp directory."""
    mrun = _run(learn=False)
    path = mrun._coordination_db_path()
    assert not Path(path).exists()


def test_cleanup_coordination_db_removes_the_temp_file_and_wal_sidecars(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "artifactsmmo_cli.multi.multi_run.tempfile.gettempdir", lambda: str(tmp_path))
    mrun = _run(learn=False)
    path = Path(mrun._coordination_db_path())
    # Simulate a real child's CoordinationStore actually having created the
    # SQLite file plus its WAL-mode sidecars.
    path.write_text("")
    Path(f"{path}-wal").write_text("")
    Path(f"{path}-shm").write_text("")
    mrun._cleanup_coordination_db()
    assert not path.exists()
    assert not Path(f"{path}-wal").exists()
    assert not Path(f"{path}-shm").exists()


def test_cleanup_coordination_db_never_deletes_the_persisted_learn_db(tmp_path):
    """The reused `--learn` DB is a persistent, cross-session file — cleanup
    must never remove it, only a temp file THIS MultiRun generated itself."""
    learn_db = tmp_path / "learning.db"
    learn_db.write_text("real learned data")
    mrun = _run(learn=True, learn_db=str(learn_db))
    mrun._coordination_db_path()  # memoize; reuses learn_db, owns nothing
    mrun._cleanup_coordination_db()
    assert learn_db.exists()
    assert learn_db.read_text() == "real learned data"


def test_cleanup_coordination_db_is_a_noop_when_never_computed():
    """`build_pool`/`child_argv` were never called (e.g. `run()` failed
    before reaching them) — cleanup must not raise."""
    mrun = _run(learn=False)
    mrun._cleanup_coordination_db()  # no raise


# --- build_pool ----------------------------------------------------------


def test_an_empty_roster_fails_loudly():
    with pytest.raises(ValueError, match="no characters"):
        _run().build_pool(characters=[], rates=_RATES)


def test_the_budget_is_split_by_the_actual_child_count():
    pool = _run().build_pool(characters=["a", "b"], rates=_RATES)
    assert pool.characters() == ("a", "b")
    two_way = split_budget(parse_rate_limits(_RATES), children=2).to_json()
    five_way = split_budget(parse_rate_limits(_RATES), children=5).to_json()
    assert two_way != five_way  # otherwise the checks below prove nothing
    for supervisor in (pool._by_name["a"], pool._by_name["b"]):
        assert two_way in supervisor._argv
        assert five_way not in supervisor._argv


def test_children_are_staggered_by_the_account_buckets_own_pace():
    """The stagger comes from /my/rates' ACCOUNT bucket (10/s + 300/hour ->
    one request per 12s), never a guessed constant, because that is the
    tightest bucket and the one every child's unmetered startup game-data load
    pages. The 12.0 also proves the UNDIVIDED limits are used: this pool has
    two children, so the divided account budget would be 150/hour -> 24.0s.
    """
    limits = parse_rate_limits(_RATES)
    pool = _run().build_pool(characters=["a", "b"], rates=_RATES)
    assert pool._stagger_seconds == pytest.approx(12.0)
    assert pool._stagger_seconds == limits.account.sustainable_interval()
    # ...and it is genuinely the account bucket, not either of its siblings.
    assert pool._stagger_seconds != limits.data.sustainable_interval()
    assert pool._stagger_seconds != limits.action.sustainable_interval()


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


def test_on_event_forwards_planning_for_the_focused_character():
    """The design doc says PlanningEvent drives set_planning; before the fix
    MultiRun._on_event handled only SnapshotEvent and silently dropped every
    PlanningEvent, so the map's planning overlay never lit in --all mode."""
    mrun = _run()
    mock_app = Mock()
    mock_app.focused_character = "a"
    mrun._app = mock_app
    mrun._on_event(PlanningEvent(character="a", active=True))
    mock_app.set_planning.assert_called_once_with(True)


def test_on_event_ignores_planning_for_a_non_focused_character():
    """set_planning drives ONE overlay; a background child's planning state
    must not fight the overlay for whichever character is actually focused."""
    mrun = _run()
    mock_app = Mock()
    mock_app.focused_character = "a"
    mrun._app = mock_app
    mrun._on_event(PlanningEvent(character="b", active=True))
    mock_app.set_planning.assert_not_called()


def test_on_event_planning_is_a_noop_with_no_app_attached():
    mrun = _run()
    assert mrun._app is None
    mrun._on_event(PlanningEvent(character="a", active=True))  # no raise


# --- _on_stderr: headless streams it, TUI stays quiet -----------------------


def test_on_stderr_prints_to_stderr_with_the_character_name_in_headless_mode(capsys):
    mrun = _run(tui=False)
    mrun._on_stderr("alice", "bot log line")
    captured = capsys.readouterr()
    assert captured.err == "[alice] bot log line\n"


def test_on_stderr_is_silent_in_tui_mode(capsys):
    """Printing to the real stderr while Textual owns the alternate screen
    would corrupt the TUI -- the same reason the bot's own stdout is
    redirected under --emit-events."""
    mrun = _run(tui=True)
    mrun._on_stderr("alice", "bot log line")
    captured = capsys.readouterr()
    assert captured.err == ""


def test_build_pool_wires_on_stderr_to_the_character(capsys):
    """End-to-end through build_pool: the supervisor's on_stderr callback
    must actually be MultiRun._on_stderr bound to ITS character, not a
    shared closure that reports every child under the same name (the classic
    late-binding-in-a-loop bug)."""
    mrun = _run(tui=False)
    pool = mrun.build_pool(characters=["alice", "bob"], rates=_RATES)
    pool._by_name["alice"]._on_stderr("alice said this")
    pool._by_name["bob"]._on_stderr("bob said this")
    captured = capsys.readouterr()
    assert captured.err == "[alice] alice said this\n[bob] bob said this\n"


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


# --- run(): coordination temp-file cleanup ----------------------------------


def test_run_cleans_up_the_temp_coordination_db_on_normal_headless_exit(tmp_path, monkeypatch):
    """The temp file is removed on normal supervisor exit."""
    monkeypatch.setattr(
        "artifactsmmo_cli.multi.multi_run.tempfile.gettempdir", lambda: str(tmp_path))
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

        mrun = _run(tui=False, learn=False)

        def _build(characters, rates):
            # Simulate a real child's own CoordinationStore.__init__ having
            # created the file at the path child_argv handed it.
            Path(mrun._coordination_db_path()).write_text("")
            return fake_pool

        with patch.object(mrun, "build_pool", side_effect=_build):
            mrun.run()

        coord_path = Path(mrun._coordination_db)
    assert fake_pool.ran is True
    assert not coord_path.exists()


def test_run_cleans_up_the_temp_coordination_db_even_when_the_pool_run_raises(tmp_path, monkeypatch):
    """Abnormal exit: a supervisor pool failure must not skip cleanup."""
    monkeypatch.setattr(
        "artifactsmmo_cli.multi.multi_run.tempfile.gettempdir", lambda: str(tmp_path))

    class _RaisingPool:
        async def run(self) -> None:
            raise RuntimeError("a supervisor crashed")

    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = _characters_response("a")
        mock_api.get_rate_limits.return_value = _rates_response()
        mock_api_cls.return_value = mock_api

        mrun = _run(tui=False, learn=False)

        def _build(characters, rates):
            Path(mrun._coordination_db_path()).write_text("")
            return _RaisingPool()

        with patch.object(mrun, "build_pool", side_effect=_build):
            with pytest.raises(RuntimeError, match="supervisor crashed"):
                mrun.run()

        coord_path = Path(mrun._coordination_db)
    assert not coord_path.exists()


def test_run_cleans_up_even_when_the_roster_call_fails_after_a_path_was_prepared(tmp_path, monkeypatch):
    """Abnormal exit before `build_pool` is ever reached: the `finally` wraps
    the WHOLE method body, not just the happy path past the API guards."""
    monkeypatch.setattr(
        "artifactsmmo_cli.multi.multi_run.tempfile.gettempdir", lambda: str(tmp_path))
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = None
        mock_api_cls.return_value = mock_api

        mrun = _run(learn=False)
        coord_path = Path(mrun._coordination_db_path())
        coord_path.write_text("")

        with pytest.raises(RuntimeError, match="characters"):
            mrun.run()

    assert not coord_path.exists()


def test_run_does_not_delete_the_persisted_learn_db_on_exit(tmp_path):
    """When `--learn` is on, coordination reuses the learning DB path — that
    file must survive `run()`'s cleanup, since it holds real learned data
    the NEXT session reads."""
    fake_pool = _FakePool()
    learn_db = tmp_path / "learning.db"
    learn_db.write_text("real learned data")
    with (
        patch("artifactsmmo_cli.multi.multi_run.Config"),
        patch("artifactsmmo_cli.multi.multi_run.ClientManager"),
        patch("artifactsmmo_cli.multi.multi_run.APIWrapper") as mock_api_cls,
    ):
        mock_api = Mock()
        mock_api.get_my_characters.return_value = _characters_response("a")
        mock_api.get_rate_limits.return_value = _rates_response()
        mock_api_cls.return_value = mock_api

        mrun = _run(tui=False, learn=True, learn_db=str(learn_db))
        with patch.object(mrun, "build_pool", return_value=fake_pool):
            mrun.run()

    assert learn_db.exists()
    assert learn_db.read_text() == "real learned data"
