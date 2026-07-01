"""Tests for GamePlayer._plan_or_reuse (plan-cache gating of the expensive decide band)."""

from dataclasses import dataclass
from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


@dataclass
class _Goal:
    satisfied: bool = False

    def is_satisfied(self, state):
        return self.satisfied

    def __repr__(self):
        return "FakeGoal()"


@dataclass
class _Act:
    applicable: bool = True

    def is_applicable(self, state, game_data):
        return self.applicable

    def __repr__(self):
        return "FakeAct()"


def _player_with_stub_plan(plan, goal):
    player = GamePlayer(character="hero", dry_run=True)
    player._gear_latch._active = False
    calls = {"n": 0}

    def _fake_decide(state, game_data, actions, ctx_combat_monster):
        calls["n"] += 1
        return goal, list(plan), [{"goal": repr(goal)}]

    # Replace only the expensive band, the collaborator — not the unit under test.
    player._decide_band = _fake_decide  # type: ignore[attr-defined]
    return player, calls


def test_first_call_replans_and_caches():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is True
    assert calls["n"] == 1
    assert player._plan_cache is not None
    assert sel is goal


def test_second_call_reuses_without_replanning():
    goal = _Goal()
    plan = [_Act(), _Act(), _Act()]
    player, calls = _player_with_stub_plan(plan, goal)
    state = make_state()
    player._plan_or_reuse(state, None, [], None)        # cycle 1: replan, cache
    player._plan_cache.advance()                         # simulate a successful execute
    player._last_outcome = "ok"
    sel, returned_plan, _tried, replanned = player._plan_or_reuse(state, None, [], None)
    assert replanned is False
    assert calls["n"] == 1                               # decide NOT called again
    assert returned_plan[0] is plan[1]                   # serves the next step


def test_replan_persists_body_and_commitment(tmp_path):
    goal = _Goal()
    plan = [_Act(), _Act()]
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    player = GamePlayer(character="hero", dry_run=True, history=store)
    player._gear_latch._active = False

    def _fake_decide(state, game_data, actions, ctx_combat_monster):
        return goal, list(plan), [{"goal": repr(goal)}]

    player._decide_band = _fake_decide  # type: ignore[attr-defined]
    player._plan_or_reuse(make_state(), None, [], None)

    assert len(store.plan_bodies_for_goal("FakeGoal()")) == 1
    assert store.load_plan_commitment() is not None


def test_advance_with_history_persists_cursor(tmp_path):
    """player.run() persists the cursor after each ok execute cycle (line 641 coverage)."""
    from artifactsmmo_cli.ai.actions.rest import RestAction
    from artifactsmmo_cli.ai.game_data import GameData

    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    player = GamePlayer(character="hero", dry_run=True, history=store)

    initial_state = make_state(hp=20, max_hp=150)
    call_count = [0]

    def fake_wait():
        call_count[0] += 1
        if call_count[0] > 1:
            raise KeyboardInterrupt

    class _NoopCache:
        def __init__(self, *a, **k): pass
        def read(self, ttl_minutes, now=None): return None
        def write(self, raw_pages, now=None): return None

    rest = RestAction()

    # Pre-seed history with a commitment at cursor=0 so update_commitment_cursor
    # has a row to update.
    store.save_plan_commitment("FakeGoal()", '{"type":"GatherMaterialsGoal","target_item":"copper_ring","needed":{}}',
                               [repr(rest), repr(rest)], 0, None, False)

    with patch.object(MagicMock(), "client", MagicMock()) as _cm:
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=MagicMock(client=MagicMock())):
            with patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=MagicMock(data=[])):
                with patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=MagicMock(data=[])):
                    with patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=MagicMock(data=[])):
                        with patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=MagicMock(data=[])):
                            with patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=MagicMock(data=[])):
                                with patch("artifactsmmo_cli.ai.game_data.get_all_tasks", return_value=MagicMock(data=[])):
                                    with patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=MagicMock(data=[])):
                                        with patch("artifactsmmo_cli.ai.game_data.get_all_effects", return_value=MagicMock(data=[])):
                                            with patch("artifactsmmo_cli.ai.game_data.get_ge_orders", return_value=MagicMock(data=[])):
                                                with patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None):
                                                    with patch("artifactsmmo_cli.ai.game_data.GameDataCache", _NoopCache):
                                                        with patch.object(player, "_fetch_world_state", return_value=initial_state):
                                                            with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                                                                with patch.object(player, "_maybe_periodic_refresh"):
                                                                    with patch.object(player, "_build_actions", return_value=[rest]):
                                                                        import pytest
                                                                        with pytest.raises(KeyboardInterrupt):
                                                                            player.run()

    # After one dry_run ok cycle, the cursor in the DB must have advanced.
    loaded = store.load_plan_commitment()
    # The commitment is written fresh by _plan_or_reuse on replan (cursor=0),
    # then line 641 updates it to cursor=1 after advance().
    assert loaded is not None
    assert loaded.cursor == 1
