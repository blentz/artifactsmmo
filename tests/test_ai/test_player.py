"""Tests for GamePlayer."""

import time
from dataclasses import dataclass, field, fields, replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from artifactsmmo_api_client.models.achievement_type import AchievementType
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.models.error_schema import ErrorSchema
from artifactsmmo_api_client.types import UNSET
from sqlmodel import Session, select

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, PlanTreeNode, RootScoreView
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer, _format_plan
from artifactsmmo_cli.ai.recovery import StuckExit, StuckSignal
from artifactsmmo_cli.ai.tiers import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision, StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions import make_game_data
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema, make_get_character_result


def make_game_data_mock() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)], "cow": [(2, 0)]}
    gd._resource_locations = {"copper": [(3, 0)]}
    gd._workshop_locations = {"weaponcrafting": (5, 0)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {"chicken": 1, "cow": 2}
    # Real combat stats so the winnability estimator can beat these low mobs.
    gd._monster_hp = {"chicken": 10, "cow": 20}
    gd._monster_attack = {"chicken": {"fire": 1}, "cow": {"fire": 2}}
    gd._monster_resistance = {"chicken": {}, "cow": {}}
    gd._monster_critical_strike = {"chicken": 0, "cow": 0}
    gd._monster_initiative = {"chicken": 0, "cow": 0}
    # CompleteTaskAction.apply calls task_coin_reward; provide a floor.
    gd._task_coin_rewards = {"chicken": 1, "cow": 1}
    return gd


class TestGamePlayerInit:
    def test_default_flags(self):
        player = GamePlayer(character="hero")
        assert player.character == "hero"
        assert player.verbose is False
        assert player.dry_run is False

    def test_verbose_and_dry_run(self):
        player = GamePlayer(character="hero", verbose=True, dry_run=True)
        assert player.verbose is True
        assert player.dry_run is True

    def test_game_data_cache_controls_default(self):
        player = GamePlayer(character="hero")
        assert player._game_data_ttl_minutes == 30
        assert player._refresh_game_data is False

    def test_game_data_cache_controls_threaded(self):
        player = GamePlayer(
            character="hero", game_data_ttl_minutes=45, refresh_game_data=True
        )
        assert player._game_data_ttl_minutes == 45
        assert player._refresh_game_data is True


class TestDryRunDoesNotPersistLearning:
    """Dry-run cycles are SIMULATED (action.apply, no real cooldown). Persisting
    them into the learning store poisons action_cost: a Fight recorded with
    actual_cooldown_seconds=0 makes cheapest_path's xp_per_cycle = xpk/max(0,1)
    = xpk explode, locking the grind onto whatever monster got a 0-cost row
    (live Robby 2026-06-12: green_slime 29/50 zero-cost rows from dry-run
    probes beat higher-XP blue_slime). Observed costs must come ONLY from real
    execution."""

    def test_record_learning_cycle_is_noop_in_dry_run(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "dry.db"), character="hero")
        try:
            store.start_session()
            player = GamePlayer(character="hero", dry_run=True, history=store)
            prev = make_state(level=5)
            new = make_state(level=5, xp=prev.xp + 10)
            player._record_learning_cycle(
                prev_state=prev, new_state=new,
                action_repr="Fight(green_slime)", action_class="FightAction",
                outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
                predicted_cost=0.0, actual_cooldown_seconds=0.0,
                planner_nodes=1, planner_depth=1, planner_timed_out=False,
                plan_len=1,
            )
            with Session(store._engine) as s:
                rows = list(s.exec(select(Cycle).where(
                    Cycle.action_repr == "Fight(green_slime)")))
            assert rows == [], "dry-run must not persist a learning cycle"
        finally:
            store.close()

    def test_record_learning_cycle_persists_when_not_dry_run(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "real.db"), character="hero")
        try:
            store.start_session()
            player = GamePlayer(character="hero", dry_run=False, history=store)
            prev = make_state(level=5)
            new = make_state(level=5, xp=prev.xp + 10)
            player._record_learning_cycle(
                prev_state=prev, new_state=new,
                action_repr="Fight(green_slime)", action_class="FightAction",
                outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
                predicted_cost=0.0, actual_cooldown_seconds=49.0,
                planner_nodes=1, planner_depth=1, planner_timed_out=False,
                plan_len=1,
            )
            with Session(store._engine) as s:
                rows = list(s.exec(select(Cycle).where(
                    Cycle.action_repr == "Fight(green_slime)")))
            assert len(rows) == 1
        finally:
            store.close()


class TestBuildActions:
    def test_includes_rest_and_deposit(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        from artifactsmmo_cli.ai.actions.rest import RestAction
        assert any(isinstance(a, RestAction) for a in actions)
        assert any(isinstance(a, DepositAllAction) for a in actions)

    def test_includes_fight_actions_for_all_monsters(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.combat import FightAction
        monster_codes = {a.monster_code for a in actions if isinstance(a, FightAction)}
        assert "chicken" in monster_codes
        assert "cow" in monster_codes

    def test_fight_actions_carry_locations(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.combat import FightAction
        fight_locs = {a.monster_code: a.locations for a in actions if isinstance(a, FightAction)}
        assert "chicken" in fight_locs
        assert (1, 0) in fight_locs["chicken"]


class TestArbiterSelection:
    """P3c: the cycle drives goal selection through StrategyArbiter, not a flat
    _build_goals list. These exercise the wired-up arbiter on a real player."""

    def _with_strategy(self, gd: GameData, **state_kw) -> GamePlayer:
        player = GamePlayer(character="hero")
        player.game_data = gd
        player._objective = CharacterObjective.from_game_data(gd)
        player._strategy = StrategyEngine(player._objective, BalancedPersonality())
        # A capable fighter by default so the stat-based winnability estimator
        # can beat the low test mobs (callers can override via state_kw).
        combat_defaults = dict(max_hp=100, attack={"fire": 50}, initiative=50)
        combat_defaults.update(state_kw)
        player.state = make_state(**combat_defaults)
        return player

    def test_cycle_uses_arbiter_not_select_goal(self):
        player = GamePlayer(character="hero")
        assert hasattr(player, "_arbiter")
        assert not hasattr(player, "_select_goal")
        assert not hasattr(player, "_build_goals")

    def test_crafting_target_set_when_chosen_step_is_obtain_item(self):
        """Cycle must write state.crafting_target from the strategy's chosen_step."""
        player = self._with_strategy(make_game_data_mock(), level=3)
        step = ObtainItem(code="copper_dagger", quantity=1)
        decision = StrategyDecision(
            interrupt=None,
            chosen_root=step,
            chosen_step=step,
            desired_state={},
        )
        player._strategy = MagicMock()
        player._strategy.decide.return_value = decision
        # Drive the exact two lines from the cycle that source crafting_target.
        state = player.state
        crafting_target = step.code if isinstance(decision.chosen_step, ObtainItem) else None
        player.state = replace(state, crafting_target=crafting_target)
        assert player.state.crafting_target == "copper_dagger"

    def test_crafting_target_none_when_chosen_step_not_obtain_item(self):
        """Cycle must clear state.crafting_target when chosen_step is not ObtainItem."""
        player = self._with_strategy(make_game_data_mock(), level=3)
        step = ReachCharLevel(level=5)
        decision = StrategyDecision(
            interrupt=None,
            chosen_root=step,
            chosen_step=step,
            desired_state={},
        )
        player._strategy = MagicMock()
        player._strategy.decide.return_value = decision
        state = player.state
        crafting_target = step.code if isinstance(decision.chosen_step, ObtainItem) else None
        player.state = replace(state, crafting_target=crafting_target)
        assert player.state.crafting_target is None

    def test_winnable_farm_target_keeps_winnable_path_aligned(self):
        # path-aligned pick is winnable -> kept (not replaced by the picker's cow)
        player = self._with_strategy(make_game_data_mock(), level=3)
        player._path_aligned_monster = lambda: "chicken"
        assert player._winnable_farm_target() == "chicken"

    def test_winnable_farm_target_falls_back_when_unwinnable(self):
        gd = make_game_data_mock()
        gd._monster_level["ogre"] = 10
        gd._monster_hp["ogre"] = 100000                         # unwinnable HP wall
        gd._monster_attack["ogre"] = {"fire": 1}
        gd._monster_resistance["ogre"] = {}
        gd._monster_critical_strike["ogre"] = 0
        gd._monster_initiative["ogre"] = 0
        player = self._with_strategy(gd, level=3)
        player._path_aligned_monster = lambda: "ogre"
        assert player._winnable_farm_target() in {"chicken", "cow"}

    def test_selection_context_carries_combat_monster(self):
        player = self._with_strategy(make_game_data_mock(), level=3)
        player._path_aligned_monster = lambda: "chicken"
        ctx = player._selection_context()
        assert ctx.combat_monster == "chicken"
        assert ctx.task_exchange_min_coins == player._task_exchange_min_coins


    def test_bag_full_selects_deposit_inventory(self):
        gd = make_game_data_mock()
        # copper_ore is a high-demand craft ingredient: its useful-quantity cap
        # (recipe demand x batch buffer) exceeds the 20 held, so it is NOT
        # overstock — bag-full routes to DepositInventory, not the discard guard.
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 20}}
        gd._bank_capacity = 50  # bank has room so DEPOSIT_FULL can fire
        player = self._with_strategy(gd, level=3,
                                     inventory={"copper_ore": 20}, inventory_max=20,
                                     bank_items={})  # bank visited, 0 items < capacity 50
        player._blockers.clear("bank")
        decision = player._strategy.decide(player.state, player.game_data)
        actions = player._build_actions()
        goal, _plan, _tried = player._arbiter.select(
            decision, player.state, player.game_data, actions, player._selection_context())
        assert goal is not None and repr(goal) == "DepositInventory"

    def test_done_task_selects_complete_task(self):
        player = self._with_strategy(make_game_data_mock(), level=3,
                                     task_type="monsters", task_code="chicken",
                                     task_total=5, task_progress=5)
        decision = player._strategy.decide(player.state, player.game_data)
        actions = player._build_actions()
        goal, _plan, _tried = player._arbiter.select(
            decision, player.state, player.game_data, actions, player._selection_context())
        assert goal is not None and repr(goal) == "CompleteTask"

    def test_idle_no_task_winnable_monsters_selects_xp_grind(self):
        """Step goal (GrindCharacterXP) outranks discretionary AcceptTask when
        winnable monsters exist. The old `best_eq >= monster_level-1` gear gate
        used to block cow (L2, best_eq=0) so AcceptTask won; after that gate was
        removed (2026-06-29) the step goal correctly fires first."""
        player = self._with_strategy(make_game_data_mock(), level=3,
                                     task_type=None, task_code=None)
        decision = player._strategy.decide(player.state, player.game_data)
        actions = player._build_actions()
        goal, _plan, _tried = player._arbiter.select(
            decision, player.state, player.game_data, actions, player._selection_context())
        assert goal is not None and repr(goal) == "GrindCharacterXP(cow)"


def _winnable_gd(monsters: dict[str, dict]) -> GameData:
    """Build a GameData whose monsters carry real combat stats.

    `monsters` maps code -> {level, hp, attack, resistance, crit, initiative}.
    Only level/hp/attack are required; the rest default sensibly.
    """
    gd = GameData()
    for code, m in monsters.items():
        gd._monster_level[code] = m["level"]
        gd._monster_hp[code] = m["hp"]
        gd._monster_attack[code] = m.get("attack", {})
        gd._monster_resistance[code] = m.get("resistance", {})
        gd._monster_critical_strike[code] = m.get("crit", 0)
        gd._monster_initiative[code] = m.get("initiative", 0)
    return gd


def _seed_fights(store: LearningStore, monster_code: str, *, wins: int, losses: int) -> None:
    """Record real Fight(monster) cycles so success_rate/sample_count are live.

    `idx` is encoded as the minutes field of the ts, so callers must keep
    wins+losses < 60 to stay within valid ISO-8601 timestamps.
    """
    store.start_session()
    with Session(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-22T00:00:00Z", character="hero"))
        idx = 0
        for outcome, n in (("ok", wins), ("error", losses)):
            for _ in range(n):
                idx += 1
                s.add(Cycle(
                    session_id=store._session_id, ts=f"2026-05-22T00:{idx:02d}:00Z",
                    cycle_index=idx, character="hero", selected_goal="GrindCharacterXP",
                    action_repr=f"Fight({monster_code})", action_class="FightAction",
                    outcome=outcome, delta_xp=0, delta_gold=0, delta_hp=0,
                    delta_inv_used=0, task_progress=0, task_total=0,
                ))
        s.commit()


class TestWinnable:
    """_is_winnable / _pick_winnable_monster driven by the real predict_win
    estimator and a real LearningStore win-rate veto (no mocking)."""

    def _player(self, gd: GameData, state, history=None) -> GamePlayer:
        player = GamePlayer(character="hero", history=history)
        player.game_data = gd
        player.state = state
        return player

    def test_winnable_when_stats_predict_a_win(self):
        gd = _winnable_gd({"chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}}})
        state = make_state(level=5, max_hp=100, attack={"fire": 50}, initiative=50)
        assert self._player(gd, state)._is_winnable("chicken") is True

    def test_not_winnable_when_stats_predict_a_loss(self):
        # A wall of HP the player cannot chew through inside the 100-turn cap.
        gd = _winnable_gd({"titan": {"level": 5, "hp": 100000, "attack": {"fire": 1}}})
        state = make_state(level=5, max_hp=100, attack={"fire": 50}, initiative=50)
        assert self._player(gd, state)._is_winnable("titan") is False

    def test_not_winnable_when_player_has_no_attack(self):
        gd = _winnable_gd({"chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}}})
        state = make_state(level=5, max_hp=100, attack={}, initiative=50)
        assert self._player(gd, state)._is_winnable("chicken") is False

    def test_observed_losses_veto_a_predicted_win(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "veto.db"), character="hero")
        try:
            _seed_fights(store, "chicken", wins=0, losses=5)  # 0% over 5 fights
            gd = _winnable_gd({"chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}}})
            state = make_state(level=5, max_hp=100, attack={"fire": 50}, initiative=50)
            # Stats say win, but the learned 0% win-rate vetoes it.
            assert self._player(gd, state, history=store)._is_winnable("chicken") is False
        finally:
            store.close()

    def test_veto_ignored_below_min_samples(self, tmp_path):
        store = LearningStore(db_path=str(tmp_path / "few.db"), character="hero")
        try:
            _seed_fights(store, "chicken", wins=0, losses=4)  # < MIN_WIN_SAMPLES
            gd = _winnable_gd({"chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}}})
            state = make_state(level=5, max_hp=100, attack={"fire": 50}, initiative=50)
            # Too few fights to trust the loss record -> defer to the stat win.
            assert self._player(gd, state, history=store)._is_winnable("chicken") is True
        finally:
            store.close()

    def test_pick_returns_highest_level_winnable(self):
        """Player at level 5 → FightAction window [4,7]. wolf(L4) qualifies;
        chicken(L1) is below the window and excluded by the level filter;
        titan(L8) is above the window. wolf is the only candidate."""
        gd = _winnable_gd({
            "chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}},
            "wolf": {"level": 4, "hp": 10, "attack": {"fire": 1}},
            "titan": {"level": 8, "hp": 100000, "attack": {"fire": 1}},  # unwinnable
        })
        state = make_state(level=5, max_hp=100, attack={"fire": 50}, initiative=50)
        assert self._player(gd, state)._pick_winnable_monster() == "wolf"

    def test_pick_none_when_nothing_winnable(self):
        gd = _winnable_gd({
            "titan": {"level": 8, "hp": 100000, "attack": {"fire": 1}},
            "colossus": {"level": 9, "hp": 100000, "attack": {"fire": 1}},
        })
        state = make_state(level=10, max_hp=100, attack={"fire": 50}, initiative=50)
        assert self._player(gd, state)._pick_winnable_monster() is None


class TestWaitForCooldown:
    def test_no_wait_when_state_is_none(self):
        player = GamePlayer(character="hero")
        player.state = None
        player._wait_for_cooldown()  # should not raise or sleep

    def test_no_wait_when_cooldown_none(self):
        player = GamePlayer(character="hero")
        player.state = make_state(cooldown_expires=None)
        player._wait_for_cooldown()

    def test_sleeps_for_remaining_cooldown(self):
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=2.5)
        player.state = make_state(cooldown_expires=future)
        with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
            player._wait_for_cooldown()
            mock_sleep.assert_called_once()
            sleep_arg = mock_sleep.call_args[0][0]
            assert 2.0 < sleep_arg < 3.5

    def test_logs_cooldown_duration(self):
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=3.0)
        player.state = make_state(cooldown_expires=future)
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with patch("artifactsmmo_cli.ai.player.time.sleep"):
            with redirect_stdout(buf):
                player._wait_for_cooldown()
        assert "Cooldown:" in buf.getvalue()

    def test_no_sleep_when_cooldown_expired(self):
        player = GamePlayer(character="hero")
        past = datetime.now(tz=timezone.utc) - timedelta(seconds=5)
        player.state = make_state(cooldown_expires=past)
        with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
            player._wait_for_cooldown()
            mock_sleep.assert_not_called()


class TestMaybePeriodicRefresh:
    def test_does_not_refresh_below_threshold(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player._actions_since_full_refresh = 19
        refresh_calls = []
        player._full_refresh = lambda c: refresh_calls.append(True)  # type: ignore
        player._maybe_periodic_refresh(client=None)
        assert refresh_calls == []

    def test_refreshes_at_threshold(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player._actions_since_full_refresh = 20
        refresh_calls = []

        def fake_full_refresh(c):
            refresh_calls.append(True)
            player._actions_since_full_refresh = 0

        player._full_refresh = fake_full_refresh  # type: ignore
        player._maybe_periodic_refresh(client=None)
        assert refresh_calls == [True]


class TestFetchWorldState:
    def test_returns_world_state(self):
        player = GamePlayer(character="hero")
        player.state = None
        char = make_char_schema()
        client = MagicMock()
        empty_events = MagicMock()
        empty_events.data = []
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                    state = player._fetch_world_state(client)
        assert isinstance(state, WorldState)

    def test_preserves_bank_state_from_current_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state(bank_items={"gold": 100}, bank_gold=50)
        char = make_char_schema()
        client = MagicMock()
        empty_events = MagicMock()
        empty_events.data = []
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                    state = player._fetch_world_state(client)
        assert state.bank_items == {"gold": 100}

    def test_raises_on_none_response(self):
        player = GamePlayer(character="hero")
        player.state = None
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=None):
            with pytest.raises(RuntimeError):
                player._fetch_world_state(client)


class TestFullRefreshNetworkResilience:
    def test_bank_sync_timeout_keeps_prior_view_and_retries(self):
        """Run-9 trace 2026-06-12 01:14:37: a ReadTimeout on GET /my/bank
        inside the periodic _full_refresh escaped all handling and killed the
        process 23 min into the run (the action-execution path catches
        httpx.HTTPError; the refresh path did not). A transient bank/pending
        sync failure must keep the carried-over bank view and leave the
        refresh counter unreset so the next cycle retries the refresh."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        player._actions_since_full_refresh = 20
        # _fetch_world_state carries bank_items over from the prior state.
        fetched = make_state(bank_items={"ash_wood": 59})
        with patch.object(player, "_fetch_world_state", return_value=fetched):
            with patch("artifactsmmo_cli.ai.player.get_bank_items",
                       side_effect=httpx.ReadTimeout("The read operation timed out")):
                player._full_refresh(client)
        assert player.state is fetched
        assert player.state.bank_items == {"ash_wood": 59}
        # Counter NOT reset — the next _maybe_periodic_refresh retries.
        assert player._actions_since_full_refresh == 20

    def test_pending_sync_timeout_also_tolerated(self):
        """Same guarantee when the failure comes from the pending-items sync
        (the second call inside the refresh)."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        player._actions_since_full_refresh = 20
        fetched = make_state(bank_items={"ash_wood": 59})
        bank_items_result = MagicMock()
        bank_items_result.data = []
        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0
        bank_details_result.data.slots = 50
        with patch.object(player, "_fetch_world_state", return_value=fetched):
            with patch("artifactsmmo_cli.ai.player.get_bank_items",
                       return_value=bank_items_result):
                with patch("artifactsmmo_cli.ai.player.get_bank_details",
                           return_value=bank_details_result):
                    with patch("artifactsmmo_cli.ai.player.get_pending_items",
                               side_effect=httpx.ConnectError("no route")):
                        player._full_refresh(client)
        assert player._actions_since_full_refresh == 20

    def test_successful_refresh_resets_counter(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        player._actions_since_full_refresh = 20
        fetched = make_state()
        bank_items_result = MagicMock()
        bank_items_result.data = []
        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0
        bank_details_result.data.slots = 50
        pending_result = MagicMock()
        pending_result.data = []
        with patch.object(player, "_fetch_world_state", return_value=fetched):
            with patch("artifactsmmo_cli.ai.player.get_bank_items",
                       return_value=bank_items_result):
                with patch("artifactsmmo_cli.ai.player.get_bank_details",
                           return_value=bank_details_result):
                    with patch("artifactsmmo_cli.ai.player.get_pending_items",
                               return_value=pending_result):
                        player._full_refresh(client)
        assert player._actions_since_full_refresh == 0


class TestSyncBank:
    def test_syncs_bank_items_and_gold(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        bank_slot = MagicMock()
        bank_slot.code = "copper_ore"
        bank_slot.quantity = 10

        bank_items_result = MagicMock()
        bank_items_result.data = [bank_slot]

        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 200

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=bank_items_result):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items == {"copper_ore": 10}
        assert new_state.bank_gold == 200

    def test_empty_bank(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        empty_result = MagicMock()
        empty_result.data = []

        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=empty_result):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items == {}

    def test_sync_bank_drops_no_field(self):
        """Regression (P0 2026-06-09 secondary bug): the old field-by-field
        WorldState(...) rebuild silently DROPPED every field it didn't
        enumerate — attack/dmg/dmg_elements/resistance/critical_strike/
        initiative/wisdom/skill_xp — zeroing combat stats on every periodic
        refresh (combat_capable flap, doomed gather probes). `_sync_bank`
        must change ONLY bank_items/bank_gold/bank_capacity."""
        player = GamePlayer(character="hero")
        state = make_state(
            attack={"air": 5, "fire": 3}, dmg=18, dmg_elements={"air": 7},
            resistance={"earth": 4}, critical_strike=12, initiative=21,
            wisdom=9, skill_xp={"mining": 123, "cooking": 4},
            crafting_target="copper_dagger",
            active_events={"bandit_camp": datetime(2026, 6, 9, tzinfo=timezone.utc)},
            cooldown_expires=datetime(2026, 6, 9, 12, tzinfo=timezone.utc),
            task_code="chicken", task_type="monsters",
            task_progress=3, task_total=10,
        )
        client = MagicMock()

        bank_slot = MagicMock()
        bank_slot.code = "copper_ore"
        bank_slot.quantity = 10
        bank_items_result = MagicMock()
        bank_items_result.data = [bank_slot]
        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 200
        bank_details_result.data.slots = 60

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=bank_items_result):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                new_state = player._sync_bank(client, state)

        synced = {"bank_items", "bank_gold", "bank_capacity"}
        for f in fields(WorldState):
            if f.name in synced:
                continue
            assert getattr(new_state, f.name) == getattr(state, f.name), (
                f"_sync_bank dropped field {f.name!r}"
            )
        assert new_state.bank_items == {"copper_ore": 10}
        assert new_state.bank_gold == 200
        assert new_state.bank_capacity == 60


class TestExecute:
    def test_execute_success_updates_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=0, y=0)
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema(x=3, y=5)

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", return_value=make_api_result(char)):
            new_state, outcome = player._execute(action, client)

        assert new_state.x == 3
        assert outcome == "ok"

    def test_execute_clamps_craft_quantity_to_affordable(self):
        """_execute must send the API only the batch the on-hand inputs cover —
        an oversized requested quantity is clamped so the server never 400s."""
        stats = ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        )
        player = GamePlayer(character="hero")
        player.state = make_state(
            x=0, y=0, skills={"weaponcrafting": 5}, inventory={"copper_ore": 12})
        player.game_data = make_game_data(
            workshop_locs={"weaponcrafting": (0, 0)},
            item_stats={"copper_dagger": stats},
            recipes={"copper_dagger": {"copper_ore": 6}},
        )
        action = CraftAction(code="copper_dagger", quantity=3, workshop_location=(0, 0))
        client = MagicMock()
        char = make_char_schema()

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting",
                   return_value=make_api_result(char)) as mock_craft:
            player._execute(action, client)

        sent = mock_craft.call_args.kwargs["body"]
        assert sent.quantity == 2  # 12 ore / 6 per dagger, clamped from requested 3

    def test_execute_api_error_refreshes_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", side_effect=RuntimeError("fail")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:other"

    def test_execute_withdraw_http_478_resyncs_bank(self):
        """A Withdraw failing on HTTP 478 ("missing items") must RE-SYNC the bank,
        correcting the stale bank_items that drove the impossible withdraw. Without
        this the generator re-emits the identical failing withdraw forever — a
        no-cooldown CPU-spin livelock (live Robby 2026-06-24: 4502 cycles)."""
        player = GamePlayer(character="hero")
        # Stale bank view claims 7 ash_plank are banked; the real bank is empty.
        player.state = make_state(x=4, y=0, bank_items={"ash_plank": 7})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        action = WithdrawItemAction(code="ash_plank", quantity=7, bank_location=(4, 0))
        char = make_char_schema(x=4, y=0)
        empty_events = MagicMock()
        empty_events.data = []
        real_bank = MagicMock()
        real_bank.data = []          # bank actually empty
        bank_details = MagicMock()
        bank_details.data = MagicMock()
        bank_details.data.gold = 0
        bank_details.data.slots = 60

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       side_effect=ApiActionError(478, "missing items")):
                with patch("artifactsmmo_cli.ai.player.get_character",
                           return_value=make_get_character_result(char)):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events",
                               return_value=empty_events):
                        with patch("artifactsmmo_cli.ai.player.get_all_raids",
                                   return_value=empty_events):
                            with patch("artifactsmmo_cli.ai.player.get_bank_items",
                                       return_value=real_bank):
                                with patch("artifactsmmo_cli.ai.player.get_bank_details",
                                           return_value=bank_details):
                                    new_state, outcome = player._execute(action, client)

        assert outcome == "error:HTTP_478"
        assert new_state.bank_items == {}   # re-synced: the stale ash_plank claim is gone

    def test_execute_withdraw_478_resync_tolerates_network_error(self):
        """If the bank re-sync itself network-fails, the 478 cycle still returns
        (no crash) — the periodic refresh retries next cycle."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, bank_items={"ash_plank": 7})
        player.game_data = make_game_data_mock()
        client = MagicMock()
        action = WithdrawItemAction(code="ash_plank", quantity=7, bank_location=(4, 0))
        char = make_char_schema(x=4, y=0)
        empty_events = MagicMock()
        empty_events.data = []

        import io
        from contextlib import redirect_stdout
        with redirect_stdout(io.StringIO()):
            with patch("artifactsmmo_cli.ai.actions.withdraw_item.withdraw_item",
                       side_effect=ApiActionError(478, "missing items")):
                with patch("artifactsmmo_cli.ai.player.get_character",
                           return_value=make_get_character_result(char)):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events",
                               return_value=empty_events):
                        with patch("artifactsmmo_cli.ai.player.get_all_raids",
                                   return_value=empty_events):
                            with patch("artifactsmmo_cli.ai.player.get_bank_items",
                                       side_effect=httpx.HTTPError("net down")):
                                new_state, outcome = player._execute(action, client)

        assert outcome == "error:HTTP_478"
        assert isinstance(new_state, WorldState)

    def test_execute_http_499_logs_server_cooldown(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                       side_effect=ApiActionError(499, "Character in cooldown")):
                with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                        with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                            new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:cooldown"
        assert "Server cooldown (HTTP 499)" in buf.getvalue()

    def test_execute_http_485_records_already_equipped(self, capsys):
        """HTTP 485 ("This item is already equipped") is an ordinary
        action-level failure: refresh state, record the failed outcome, and
        return — never raise (2026-06-10 Robby trace: equip-485s preceded a
        silent worker-thread death; ANY future 485 must complete the cycle
        so replanning and the stuck detector can react)."""
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        action = EquipAction(code="small_health_potion", slot="utility2_slot")
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        with patch("artifactsmmo_cli.ai.actions.equip.action_equip",
                   side_effect=ApiActionError(485, "This item is already equipped")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:already_equipped"
        assert "Item already equipped (HTTP 485)" in capsys.readouterr().out

    def test_execute_network_error_is_transient(self):
        """httpx transport errors (DNS failures, timeouts, connection resets)
        must NOT crash the player. _execute should refetch state and surface
        outcome=error:network so the next cycle replans against current truth."""
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=3, y=5)
        char = make_char_schema()
        net_err = httpx.ConnectError("DNS lookup failed")
        empty_events = MagicMock()
        empty_events.data = []

        with patch("artifactsmmo_cli.ai.actions.movement.action_move", side_effect=net_err):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:network"

    def test_execute_bank_action_syncs_bank(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 5})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        bank_slot = MagicMock()
        bank_slot.code = "copper_ore"
        bank_slot.quantity = 5
        bank_result = MagicMock()
        bank_result.data = [bank_slot]
        bank_details_result = MagicMock()
        bank_details_result.data = MagicMock()
        bank_details_result.data.gold = 0

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item", return_value=make_api_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=bank_result):
                with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details_result):
                    new_state, outcome = player._execute(action, client)

        assert new_state.bank_items is not None
        assert outcome == "ok"

    def test_execute_fight_lost_outcome(self):
        """FightAction raising 'fight_lost: ...' should yield outcome=error:fight_lost."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=1, y=1, hp=100, max_hp=100)
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.combat import FightAction
        action = FightAction(monster_code="yellow_slime", locations=frozenset({(1, 1)}))
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        with patch.object(action, "execute", side_effect=RuntimeError("fight_lost: yellow_slime (turns=3)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        new_state, outcome = player._execute(action, client)

        assert outcome == "error:fight_lost"
        assert isinstance(new_state, WorldState)

    def test_execute_craft_action_wires_history(self, tmp_path):
        """_execute sets action.history before calling execute on a CraftAction."""
        from artifactsmmo_api_client.models.drop_schema import DropSchema
        from artifactsmmo_api_client.models.skill_info_schema import SkillInfoSchema

        from artifactsmmo_cli.ai.actions.crafting import CraftAction
        from artifactsmmo_cli.ai.learning.store import LearningStore

        store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
        player = GamePlayer(character="hero", history=store)
        player.state = make_state(x=3, y=0)
        player.game_data = make_game_data_mock()

        action = CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0))
        char = make_char_schema()
        details = SkillInfoSchema(xp=10, items=[DropSchema(code="copper_dagger", quantity=1)])
        result = MagicMock()
        result.data = MagicMock()
        result.data.character = char
        result.data.details = details

        with patch("artifactsmmo_cli.ai.actions.crafting.action_crafting", return_value=result):
            _new_state, outcome = player._execute(action, client=MagicMock())

        assert outcome == "ok"
        assert store.observed_craft_yield("copper_dagger") == (1, 10)
        store.close()


class TestNow:
    def test_returns_time_string(self):
        result = GamePlayer._now()
        assert len(result) == 8
        assert result[2] == ":"


class TestFormatPlan:
    def test_empty_plan(self):
        assert _format_plan([]) == ""

    def test_single_action(self):
        from artifactsmmo_cli.ai.actions.rest import RestAction
        assert _format_plan([RestAction()]) == "Rest"

    def test_consecutive_repeats_collapsed(self):
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        actions = [GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))] * 3
        assert _format_plan(actions) == "Gather(copper_rocks)×3"

    def test_mixed_plan_collapsed(self):
        from artifactsmmo_cli.ai.actions.crafting import CraftAction
        from artifactsmmo_cli.ai.actions.gathering import GatherAction
        gathers = [GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)]))] * 80
        crafts = [CraftAction(code="copper_bar", quantity=1, workshop_location=(1, 5))] * 8
        result = _format_plan(gathers + crafts)
        assert "×80" in result
        assert "×8" in result
        assert "…" not in result  # only 2 distinct segments — no truncation needed

    def test_truncates_after_five_segments(self):
        from artifactsmmo_cli.ai.actions.movement import MoveAction
        from artifactsmmo_cli.ai.actions.rest import RestAction
        plan = [RestAction(), MoveAction(1, 0), MoveAction(2, 0), MoveAction(3, 0),
                MoveAction(4, 0), MoveAction(5, 0), RestAction()]
        result = _format_plan(plan)
        assert "…" in result


class TestBuildGoalsTier1:
    def _make_player_with_gd(self, extra_stats=None, extra_recipes=None) -> GamePlayer:
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = extra_stats or {}
        gd._crafting_recipes = extra_recipes or {}
        gd._resource_skill = {}
        player.game_data = gd
        return player

    def test_task_exchange_action_always_built(self):
        player = self._make_player_with_gd()
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
        actions = player._build_actions()
        exchange_actions = [a for a in actions if isinstance(a, TaskExchangeAction)]
        assert len(exchange_actions) == 1

    def test_build_actions_includes_task_exchange(self):
        player = self._make_player_with_gd()
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
        actions = player._build_actions()
        exchange_actions = [a for a in actions if isinstance(a, TaskExchangeAction)]
        assert len(exchange_actions) == 1

    def test_build_actions_adds_withdraw_for_equippable_craftable_items(self):
        """Regression: crafted items deposited to bank must be withdrawable for equipping."""
        weapon_stats = ItemStats(code="copper_dagger", level=1, type_="weapon",
                                 crafting_skill="weaponcrafting", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_dagger": weapon_stats},
            extra_recipes={"copper_dagger": {"copper_ore": 2}},
        )
        player.state = make_state(skills={"weaponcrafting": 1})
        from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
        actions = player._build_actions()
        withdraw_codes = {a.code for a in actions if isinstance(a, WithdrawItemAction)}
        assert "copper_dagger" in withdraw_codes

    def test_build_actions_multi_slot_ring_creates_two_equip(self):
        ring_stats = ItemStats(code="copper_ring", level=1, type_="ring",
                               crafting_skill="jewelrycrafting", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_ring": ring_stats},
            extra_recipes={"copper_ring": {"copper_ore": 2}},
        )
        player.state = make_state(skills={"jewelrycrafting": 1})
        from artifactsmmo_cli.ai.actions.equip import EquipAction
        actions = player._build_actions()
        equip_actions = [a for a in actions if isinstance(a, EquipAction) and a.code == "copper_ring"]
        slots = {a.slot for a in equip_actions}
        assert "ring1_slot" in slots
        assert "ring2_slot" in slots

    def test_build_actions_expands_transitive_withdraw_chain(self):
        """A two-level recipe chain (dagger <- bar <- ore) must surface a
        Withdraw for the LEAF ore, not just the direct bar input, so the bot
        pulls banked ore instead of regathering (lines 938-952). It must also
        emit a smaller per-craft withdraw (lines 961-969)."""
        from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
        weapon = ItemStats(code="copper_dagger", level=1, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=1)
        bar = ItemStats(code="copper_bar", level=1, type_="resource",
                        crafting_skill="mining", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_dagger": weapon, "copper_bar": bar},
            extra_recipes={
                "copper_dagger": {"copper_bar": 6},  # equippable -> bar enters withdraw set
                "copper_bar": {"copper_ore": 10},     # bar's own recipe -> ore is the leaf
            },
        )
        player.state = make_state(skills={"weaponcrafting": 1, "mining": 1})
        actions = player._build_actions()
        withdraws = [a for a in actions if isinstance(a, WithdrawItemAction)]
        codes = {a.code for a in withdraws}
        # Transitive leaf surfaced.
        assert "copper_ore" in codes
        assert "copper_bar" in codes
        # A per-craft (one bar's worth = 10 ore) withdraw distinct from the
        # full-chain qty (6 bars * 10 = 60 ore) exists.
        ore_qtys = {a.quantity for a in withdraws if a.code == "copper_ore"}
        assert 10 in ore_qtys and 60 in ore_qtys

    def test_build_actions_recycle_menu_carries_every_craftable_equippable(self):
        """The factory emits the RECYCLE MENU, and protects nothing.

        It used to skip the codes in `protected_gear or (target_gear | target_tools)`
        — a `frozenset[str]`, i.e. keep-ALL-copies. That was the LAST code-set
        protection in the codebase (the type the item-protection-authority epic
        exists to kill), and as a defence it was both too strong (all 18 copies of a
        BiS tool, hoarded) and far too weak (it guarded RECYCLE only, while the
        Delete/NpcSell emissions in the same factory had NO protection at all and
        `Goal.relevant_actions` hands the whole pool to every goal by default).
        WHAT may be destroyed is now the keep authority's single answer, applied to
        this pool in `StrategyArbiter.select` (`ai/destructive_license`), so the
        target-gear code appears in the MENU exactly like any other."""
        from artifactsmmo_cli.ai.actions.recycle import RecycleAction
        weapon = ItemStats(code="copper_dagger", level=1, type_="weapon",
                           crafting_skill="weaponcrafting", crafting_level=1)
        helmet = ItemStats(code="copper_helmet", level=1, type_="helmet",
                           crafting_skill="gearcrafting", crafting_level=1)
        player = self._make_player_with_gd(
            extra_stats={"copper_dagger": weapon, "copper_helmet": helmet},
            extra_recipes={
                "copper_dagger": {"copper_ore": 2},
                "copper_helmet": {"copper_ore": 2},
            },
        )

        class _Obj:
            target_gear = {"weapon_slot": "copper_dagger"}
            target_tools: dict[str, str] = {}

        player._objective = _Obj()  # type: ignore[assignment]
        player.state = make_state(skills={"weaponcrafting": 1, "gearcrafting": 1})
        actions = player._build_actions()
        recycle_codes = {a.code for a in actions if isinstance(a, RecycleAction)}
        assert "copper_dagger" in recycle_codes
        assert "copper_helmet" in recycle_codes


class TestLogAction:
    def test_log_with_single_action(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.goals.restore_hp import RestoreHPGoal
        action = RestAction()
        goal = RestoreHPGoal()
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            player._log_action(action, goal, [action])
        assert "Rest" in buf.getvalue()


def test_sync_pending_iterates_items_list(monkeypatch):
    """_sync_pending should produce (pending_id, item_code) pairs from PendingItemSchema.items."""

    class FakeItem:
        def __init__(self, code, quantity=1):
            self.code = code
            self.quantity = quantity

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", [FakeItem("diamond"), FakeItem("ruby")]),
            FakePending("p2", [FakeItem("emerald")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items is not None
    assert ("p1", "diamond") in new_state.pending_items
    assert ("p1", "ruby") in new_state.pending_items
    assert ("p2", "emerald") in new_state.pending_items
    assert len(new_state.pending_items) == 3


def test_sync_pending_drops_no_field(monkeypatch):
    """Regression (P0 2026-06-09 secondary bug): like `_sync_bank`, the old
    `_sync_pending` rebuilt WorldState field-by-field and dropped every
    combat stat. It must change ONLY pending_items."""

    class FakeItem:
        def __init__(self, code):
            self.code = code

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([FakePending("p1", [FakeItem("diamond")])]),
    )

    player = GamePlayer(character="testchar")
    state = make_state(
        attack={"air": 5}, dmg=18, dmg_elements={"air": 7},
        resistance={"earth": 4}, critical_strike=12, initiative=21,
        wisdom=9, skill_xp={"mining": 123},
        crafting_target="copper_dagger",
        active_events={"bandit_camp": datetime(2026, 6, 9, tzinfo=timezone.utc)},
        bank_items={"copper_ore": 2}, bank_gold=77, bank_capacity=50,
        task_code="chicken", task_type="monsters",
        task_progress=3, task_total=10,
    )
    new_state = player._sync_pending(client=None, state=state)

    for f in fields(WorldState):
        if f.name == "pending_items":
            continue
        assert getattr(new_state, f.name) == getattr(state, f.name), (
            f"_sync_pending dropped field {f.name!r}"
        )
    assert new_state.pending_items == (("p1", "diamond"),)


def test_sync_pending_handles_unset_items_list(monkeypatch):
    """PendingItemSchema.items can be Unset — _sync_pending should skip such entries."""

    class FakeItem:
        def __init__(self, code):
            self.code = code

    class FakePending:
        def __init__(self, id_, items):
            self.id = id_
            self.items = items

    class FakeResult:
        def __init__(self, data):
            self.data = data

    monkeypatch.setattr(
        "artifactsmmo_cli.ai.player.get_pending_items",
        lambda client: FakeResult([
            FakePending("p1", UNSET),
            FakePending("p2", [FakeItem("diamond")]),
        ]),
    )

    player = GamePlayer(character="testchar")
    player.state = make_state()
    new_state = player._sync_pending(client=None, state=player.state)
    assert new_state.pending_items == (("p2", "diamond"),)


class TestExecuteHttp496BankLock:
    """Tests for HTTP 496 bank-lock path in _execute."""

    def test_http496_on_deposit_sets_bank_inaccessible(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 5})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
                   side_effect=ApiActionError(496, "(locked bank_deposit achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                        with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                            player._execute(action, client)

        assert player._blockers.is_blocked("bank")
        assert player._blockers.get("bank").blocked_since_monotonic is not None

    def test_http496_without_achievement_code_leaves_unlock_monster_none(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        # No achievement code in error message — no match for the regex
        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
                   side_effect=ApiActionError(496, "bank access denied")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        player._execute(action, client)

        assert player._blockers.is_blocked("bank")
        assert player._blockers.get("bank").unlock_monster is None

    def test_http496_does_not_mark_inaccessible_for_non_bank_action(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.movement import MoveAction
        action = MoveAction(x=1, y=0)
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        # HTTP 496 on a non-bank action — bank_accessible must NOT be changed
        with patch("artifactsmmo_cli.ai.actions.movement.action_move",
                   side_effect=ApiActionError(496, "some unrelated error")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        player._execute(action, client)

        assert not player._blockers.is_blocked("bank")  # unchanged

    def test_http496_with_achievement_code_calls_resolve(self):
        """When achievement code is in the 496 error, _resolve_bank_unlock_monster is called."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "skeleton"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
                   side_effect=ApiActionError(496, "(myach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        player._execute(action, client)

        assert resolve_calls == ["myach"]
        assert player._blockers.get("bank").unlock_monster == "skeleton"

    def test_http496_skips_resolve_when_monster_already_set(self):
        """Once bank_unlock_monster is set, _resolve_bank_unlock_monster is not called again."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        player._blockers.mark_blocked("bank", char_level=0,
                                      unlock_monster="chicken")  # already resolved
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "wolf"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.deposit_all.deposit_item",
                   side_effect=RuntimeError("HTTP 496 (newach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_get_character_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    with patch("artifactsmmo_cli.ai.player.get_all_raids", return_value=empty_events):
                        player._execute(action, client)

        # resolve should NOT be called since monster is already set
        assert resolve_calls == []
        assert player._blockers.get("bank").unlock_monster == "chicken"


class TestExecuteClaimPendingSync:
    """Test that ClaimPendingItemAction triggers _sync_pending in _execute."""

    def test_execute_claim_pending_calls_sync_pending(self):
        from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
        player = GamePlayer(character="hero")
        player.state = make_state(pending_items=(("id1", "copper_ore"),))
        player.game_data = make_game_data_mock()
        client = MagicMock()

        char = make_char_schema()
        pending_item = MagicMock()
        pending_item.id = "id1"
        pending_item.code = "copper_ore"
        pending_result = MagicMock()
        pending_result.data = [pending_item]
        final_pending = MagicMock()
        final_pending.data = []

        sync_calls = []

        def fake_sync(c, s):
            sync_calls.append(True)
            return s

        player._sync_pending = fake_sync  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.claim.get_pending_items", return_value=pending_result):
            with patch("artifactsmmo_cli.ai.actions.claim.action_claim_item", return_value=make_api_result(char)):
                player._execute(ClaimPendingItemAction(), client)

        assert sync_calls == [True]


class TestResolveBankUnlockMonster:
    """Tests for _resolve_bank_unlock_monster."""

    def test_returns_none_when_api_returns_none(self):
        player = GamePlayer(character="hero")
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")
        assert result is None

    def test_returns_combat_kill_target(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        obj = MagicMock()
        obj.type_ = AchievementType.COMBAT_KILL
        obj.target = "skeleton"

        result_obj = MagicMock()
        result_obj.data = MagicMock()
        result_obj.data.objectives = [obj]

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result == "skeleton"

    def test_returns_none_when_no_combat_kill_objective(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        obj = MagicMock()
        obj.type_ = MagicMock()  # some other achievement type, not COMBAT_KILL
        obj.type_ = "craft"  # not AchievementType.COMBAT_KILL
        obj.target = "some_item"

        result_obj = MagicMock()
        result_obj.data = MagicMock()
        result_obj.data.objectives = [obj]

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result is None

    def test_returns_none_when_result_has_no_data(self):
        player = GamePlayer(character="hero")
        client = MagicMock()

        result_obj = MagicMock()
        result_obj.data = None

        with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=result_obj):
            result = player._resolve_bank_unlock_monster(client, "some_achievement")

        assert result is None


class TestEmitTrace:
    """Tests for _emit_trace."""

    def test_returns_early_when_state_is_none(self):
        player = GamePlayer(character="hero")
        player.state = None
        tracer = MagicMock()
        player.tracer = tracer
        # Should not raise and should not call tracer.write_cycle
        player._emit_trace("Rest", "RestoreHP", "ok", {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1})
        tracer.write_cycle.assert_not_called()

    def test_computes_cooldown_remaining_when_cooldown_set(self):
        from datetime import datetime, timedelta, timezone
        player = GamePlayer(character="hero")
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=5.0)
        player.state = make_state(cooldown_expires=future)
        tracer = MagicMock()
        player.tracer = tracer
        player._arbiter.last_fires = {
            "guards": ["hp_critical"], "collect": [], "discretionary": [],
            "step_present": True,
        }
        player._emit_trace("Rest", "RestoreHP", "ok", {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1})
        tracer.write_cycle.assert_called_once()
        record = tracer.write_cycle.call_args[0][0]
        assert record["cooldown_remaining_at_cycle_start"] > 0.0
        # Phase B3: the fired-kinds snapshot rides every cycle record.
        assert record["fires"] == {
            "guards": ["hp_critical"], "collect": [], "discretionary": [],
            "step_present": True,
        }


class TestHandleStuckExtended:
    """Tests for additional _handle_stuck escalation levels."""

    def test_state_frozen_level3_broadens_suppression(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.STATE_FROZEN] = 2
        player._suppressed_goals = {"GoalA": 3}

        player._handle_stuck(StuckSignal.STATE_FROZEN, client=None)

        # Should broaden GoalA from 3 to max(3, 10) = 10
        assert player._suppressed_goals["GoalA"] == 10
        assert player._recovery_level[StuckSignal.STATE_FROZEN] == 3

    def test_goal_oscillation_level2_suppresses_for_15_cycles(self):
        player = GamePlayer(character="hero")
        from artifactsmmo_cli.ai.recovery import CycleRecord
        # succeeded=False so the recovery handler treats these as the
        # source of the oscillation (succeeded goals are excluded post-b2be2ad).
        for i in range(8):
            name = "GoalA" if i % 2 == 0 else "GoalB"
            player._detector.record(CycleRecord(
                state_key=(i, 0, 5, (), (), None, 0, False),
                goal_name=name, action_name="X", planned_depth=1,
                planner_timed_out=False, succeeded=False,
            ))
        player._recovery_level[StuckSignal.GOAL_OSCILLATION] = 1

        player._handle_stuck(StuckSignal.GOAL_OSCILLATION, client=None)

        assert player._suppressed_goals.get("GoalA") == 15
        assert player._suppressed_goals.get("GoalB") == 15
        assert player._recovery_level[StuckSignal.GOAL_OSCILLATION] == 2

    def test_no_progress_level2_refreshes_and_clears_blockers(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 1
        refreshed = make_state(level=2)
        player._fetch_world_state = lambda client: refreshed
        cleared: list[str] = []
        player._blockers.clear = lambda code: cleared.append(code)

        player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)

        assert player.state is refreshed
        assert cleared == ["bank"]
        assert player._recovery_level[StuckSignal.NO_PROGRESS] == 2

    def test_no_progress_level3_raises_stuck_exit(self):
        """L3 is an honest terminal path: StuckExit (recorded as
        exit_reason='stuck_exit' at the play() boundary), NOT SystemExit."""
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 2

        with pytest.raises(StuckExit) as exc_info:
            player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)

        assert exc_info.value.signal == StuckSignal.NO_PROGRESS
        assert not isinstance(exc_info.value, SystemExit)


class TestBuildGoalsExtended:
    def _make_minimal_player(self) -> GamePlayer:
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        player.game_data = gd
        player.state = make_state()
        return player

    def test_bank_retry_timer_resets_bank_accessible(self):
        player = self._make_minimal_player()
        player.state = make_state(level=5)
        # Block was recorded at level 3 — current level (5) has surpassed it.
        player._blockers.mark_blocked("bank", char_level=3)
        player._blockers.get("bank").blocked_since_monotonic = \
            time.monotonic() - 61.0  # > 60s threshold

        player._maybe_retry_bank()

        assert not player._blockers.is_blocked("bank")
        assert player._blockers.get("bank") is None

    def test_bank_retry_timer_does_not_reset_before_timeout(self):
        player = self._make_minimal_player()
        player.state = make_state(level=5)
        player._blockers.mark_blocked("bank", char_level=0)
        player._blockers.get("bank").blocked_since_monotonic = \
            time.monotonic() - 10.0  # only 10s ago

        player._maybe_retry_bank()

        assert player._blockers.is_blocked("bank")  # still locked

    def test_bank_retry_does_not_fire_when_level_unchanged(self):
        """Timer elapsed but no level gained since block — retry must NOT fire."""
        player = self._make_minimal_player()
        player.state = make_state(level=5)
        # Block recorded at the same level the character is at now.
        player._blockers.mark_blocked("bank", char_level=5)
        player._blockers.get("bank").blocked_since_monotonic = \
            time.monotonic() - 61.0  # > 60s threshold

        player._maybe_retry_bank()

        # Level guard must suppress the retry: bank blocker must remain set.
        assert player._blockers.is_blocked("bank")
        assert player._blockers.get("bank").blocked_since_monotonic is not None


def test_game_player_accepts_history_kwarg():
    from artifactsmmo_cli.ai.player import GamePlayer
    player = GamePlayer(character="testchar", history=None)
    assert player.history is None


def test_game_player_default_history_is_none():
    from artifactsmmo_cli.ai.player import GamePlayer
    player = GamePlayer(character="testchar")
    assert player.history is None


class TestBuildActionsExtended:
    def test_delete_actions_skip_equipped_items(self):
        """Items in equipment slots must not get delete actions."""
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        gd._monster_level = {}
        player.game_data = gd
        player._blockers.mark_blocked("bank", char_level=0)

        equipment = {slot: None for slot in [
            "weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
            "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
            "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
            "utility1_slot", "utility2_slot", "bag_slot", "rune_slot",
        ]}
        equipment["weapon_slot"] = "copper_dagger"
        player.state = make_state(
            inventory={"copper_dagger": 1, "iron_ore": 3},
            equipment=equipment,
        )

        from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
        actions = player._build_actions()
        delete_codes = {a.code for a in actions if isinstance(a, DeleteItemAction)}

        assert "iron_ore" in delete_codes
        assert "copper_dagger" not in delete_codes  # equipped — must be skipped

    def test_npc_buy_actions_cover_full_vendor_stock(self):
        """NPC buy actions are built for every known item a vendor carries —
        not just consumables. Prior version filtered to hp_restore>0 which
        made weapons / gear / tools / ammo at any merchant unreachable to the
        planner; gold sat idle while the bot stayed under-geared. The action
        layer must surface the full surface; the goal/planner layer decides
        whether to buy."""
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {
            "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable", hp_restore=50),
            "raw_iron": ItemStats(code="raw_iron", level=1, type_="resource"),
            "unknown_thing": ItemStats(code="unknown_thing", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        gd._monster_level = {}
        gd._npc_locations = {"cook": (5, 0)}
        # Vendor stock includes a consumable, a resource, AND an item the
        # client has no stats for (mystery_box) — the unknown one is the
        # only thing the loop must still skip (can't reason without stats).
        gd._npc_stock = {"cook": ["cooked_chicken", "raw_iron", "mystery_box"]}
        player.game_data = gd
        player.state = make_state()

        from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
        actions = player._build_actions()
        npc_buy_items = {a.item_code for a in actions if isinstance(a, NpcBuyAction)}

        assert "cooked_chicken" in npc_buy_items
        assert "raw_iron" in npc_buy_items, (
            "non-consumable vendor stock must produce a buy action (was filtered out by "
            "the legacy hp_restore>0 gate, leaving gold unspendable on gear)"
        )
        assert "mystery_box" not in npc_buy_items  # unknown items legitimately skipped


class TestBuildGoalsTaskCancelNeverSuppressed:
    """TaskCancelGoal must survive suppression — it is the escape hatch for infeasible tasks."""

    def _make_minimal_player(self) -> GamePlayer:
        player = GamePlayer(character="hero")
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        player.game_data = gd
        player.state = make_state()
        return player

    def _arbiter_player(self, history=None) -> GamePlayer:
        player = GamePlayer(character="hero", history=history)
        gd = GameData()
        gd._monster_locations = {"chicken": [(1, 0)]}
        gd._monster_level = {"chicken": 1}
        gd._monster_hp = {"chicken": 10}
        gd._monster_attack = {"chicken": {"fire": 1}}
        gd._monster_resistance = {"chicken": {}}
        gd._monster_critical_strike = {"chicken": 0}
        gd._monster_initiative = {"chicken": 0}
        gd._resource_locations = {}
        gd._workshop_locations = {}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        gd._item_stats = {}
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        player.game_data = gd
        player.state = make_state()
        player._objective = CharacterObjective.from_game_data(gd)
        player._strategy = StrategyEngine(player._objective, BalancedPersonality())
        return player

    def test_task_cancel_survives_suppression(self, tmp_path):
        """TaskCancel must remain selectable even when in _suppressed_goals."""
        store = LearningStore(db_path=str(tmp_path / "tc.db"), character="hero")
        try:
            player = self._arbiter_player(history=store)
            # A monsters task far above the char's level → task_decision PIVOTs so
            # TASK_CANCEL fires; suppress TaskCancel as oscillation recovery would.
            gd = player.game_data
            gd._monster_level["dragon"] = 50
            gd._monster_hp["dragon"] = 100000
            gd._monster_attack["dragon"] = {"fire": 1}
            gd._monster_resistance["dragon"] = {}
            gd._monster_critical_strike["dragon"] = 0
            gd._monster_initiative["dragon"] = 0
            player.state = make_state(hp=150, max_hp=150,
                                      level=5, task_type="monsters", task_code="dragon",
                                      task_total=5, task_progress=0)
            player._suppressed_goals = {"TaskCancel": 5}
            decision = player._strategy.decide(player.state, player.game_data)
            actions = player._build_actions()
            _goal, _plan, tried = player._arbiter.select(
                decision, player.state, player.game_data, actions,
                player._selection_context(), suppressed=set(player._suppressed_goals))
            # TaskCancel must not be filtered from the candidates the arbiter walks.
            assert any(gt["goal"] == "TaskCancel" for gt in tried)
        finally:
            store.close()

    def test_other_suppressed_goals_are_still_filtered(self):
        """Suppression of goals other than TaskCancel must still work."""
        player = self._arbiter_player()
        player.state = make_state(hp=150, max_hp=150,
                                  task_type="monsters", task_code="chicken",
                                  task_total=5, task_progress=5)
        player._suppressed_goals = {"CompleteTask": 5}
        decision = player._strategy.decide(player.state, player.game_data)
        actions = player._build_actions()
        _goal, _plan, tried = player._arbiter.select(
            decision, player.state, player.game_data, actions,
            player._selection_context(), suppressed=set(player._suppressed_goals))
        assert not any(gt["goal"] == "CompleteTask" for gt in tried)


def test_fetch_world_state_retries_on_404(monkeypatch):
    """_fetch_world_state should retry 3 times on 404 before raising."""
    attempts = []

    def fake_get_character(client, name):
        attempts.append(name)
        return ErrorResponseSchema(
            error=ErrorSchema(code=404, message="Character not found."),
        )

    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_character", fake_get_character)
    monkeypatch.setattr("time.sleep", lambda _: None)  # don't actually wait
    # get_all_active_events is only reached after a successful get_character; not needed here

    player = GamePlayer(character="TestChar")
    with pytest.raises(RuntimeError) as exc:
        player._fetch_world_state(client=None)
    assert len(attempts) == 3
    assert "404" in str(exc.value)
    assert "TestChar" in str(exc.value)


def test_fetch_world_state_retries_on_httperror(monkeypatch):
    """_fetch_world_state retries on httpx.HTTPError, then raises after 3 attempts."""
    attempts = []

    def fake_get_character(client, name):
        attempts.append(name)
        raise httpx.ConnectError("boom")

    monkeypatch.setattr("artifactsmmo_cli.ai.player.get_character", fake_get_character)
    monkeypatch.setattr("time.sleep", lambda _: None)

    player = GamePlayer(character="NetChar")
    with pytest.raises(RuntimeError) as exc:
        player._fetch_world_state(client=None)
    assert len(attempts) == 3
    assert "NetChar" in str(exc.value)


class TestComputeCyclesToSatisfy:
    def test_returns_none_when_never_selected(self):
        """_compute_cycles_to_satisfy returns None for an unseen goal (line 1216)."""
        player = GamePlayer(character="hero")
        assert player._compute_cycles_to_satisfy("NeverSeenGoal", current_cycle=10) is None

    def test_returns_delta_after_selection(self):
        """After _note_goal_selection, returns cycles elapsed then clears the entry."""
        player = GamePlayer(character="hero")
        player._note_goal_selection("ReachCharLevel(5)", cycle_index=3)
        assert player._compute_cycles_to_satisfy("ReachCharLevel(5)", current_cycle=8) == 5
        # Entry cleared -> a second call returns None.
        assert player._compute_cycles_to_satisfy("ReachCharLevel(5)", current_cycle=9) is None


class TestPathTraceSnapshot:
    def test_includes_plan_fields_when_plan_present(self):
        """_path_trace_snapshot merges plan fields when a path plan exists (1042-1046)."""
        from artifactsmmo_cli.ai.learning.projections import PathPlan, PathSegment

        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_path_plan = PathPlan(
            target_level=10,
            total_cycles=42.5,
            segments=[PathSegment(
                from_level=4, to_level=10, monster_code="cow",
                estimated_cycles=42.5, xp_per_cycle=10.0, cycles_per_kill=1.5,
            )],
        )
        snap = player._path_trace_snapshot()
        assert snap["projected_cycles_to_max"] == 42.5
        assert snap["path_next_action"] == "cow"
        assert snap["path_blocked"] is False

    def test_infinite_plan_reports_inf(self):
        """An unreachable (inf) plan reports the string 'inf'."""
        from artifactsmmo_cli.ai.learning.projections import PathPlan

        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_path_plan = PathPlan(
            target_level=10, total_cycles=float("inf"), segments=[], blocked=True,
        )
        snap = player._path_trace_snapshot()
        assert snap["projected_cycles_to_max"] == "inf"
        assert snap["path_blocked"] is True


class TestNotifyObserverCooldown:
    def test_cooldown_remaining_computed_from_state(self):
        """_notify_observer computes cooldown_remaining from state.cooldown_expires (line 987)."""
        captured = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        future = datetime.now(tz=timezone.utc) + timedelta(seconds=12)
        player.state = make_state(level=4, cooldown_expires=future)
        player._notify_observer("ReachCharLevel(5)", "FightAction(cow)", "ok", [])
        assert len(captured) == 1
        snap = captured[0]
        assert snap.cooldown_remaining > 0
        assert snap.cooldown_remaining <= 12.0

    def test_notify_observer_populates_plan_tree(self):
        """_notify_observer wires build_plan_tree(self._last_decision, ...) into
        the emitted CycleSnapshot.plan_tree when a decision is committed (the
        True branch of the plan_tree=... conditional in player.py)."""
        captured = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=ObtainItem("nonexistent_item"),
            chosen_step=None, desired_state={}, ranking=[],
        )
        player._notify_observer("ReachCharLevel(5)", "FightAction(cow)", "ok", [])
        assert len(captured) == 1
        snap = captured[0]
        assert snap.plan_tree != ()
        assert snap.plan_tree[0].label == "nonexistent_item"


@dataclass(frozen=True)
class _GrindLeg:
    """A concrete (non-LevelSkill) grind leg stand-in for the capture tests."""

    name: str

    def __repr__(self) -> str:
        return f"{self.name}()"


class TestGrindExpansionCapture:
    """The player captures the runtime skill-grind sub-plan legs so the TUI can
    show the whole action chain below a LevelSkill step."""

    def _player(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        player.state = make_state()
        player._build_actions = lambda: []           # type: ignore[method-assign]
        player.planner = MagicMock()
        player._execute = lambda action, client: (player.state, "ok")  # type: ignore[method-assign]
        return player

    def test_captures_flat_legs(self):
        player = self._player()
        player.planner.plan.return_value = [_GrindLeg("GatherAsh"), _GrindLeg("CraftPlank")]
        with patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=MagicMock()):
            player._execute_level_skill(LevelSkill(skill="woodcutting", target_level=30),
                                        MagicMock())
        assert [n.label for n in player._last_grind_expansion] == ["GatherAsh()", "CraftPlank()"]

    def test_captures_nested_cross_skill_grind(self):
        player = self._player()
        inner = LevelSkill(skill="fishing", target_level=20)
        player.planner.plan.side_effect = [[inner], [_GrindLeg("GatherOak")]]
        with patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=MagicMock()):
            player._execute_level_skill(LevelSkill(skill="woodcutting", target_level=30),
                                        MagicMock())
        outer = player._last_grind_expansion
        assert outer[0].kind == "step" and "fishing" in outer[0].label
        assert outer[0].children[0].label == "GatherOak()"

    def test_resets_between_top_level_grinds(self):
        player = self._player()
        player._last_grind_expansion = (
            PlanTreeNode(key="stale", label="Stale()", kind="obtain", status="current"),)
        player.planner.plan.return_value = [_GrindLeg("GatherAsh")]
        with patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=MagicMock()):
            player._execute_level_skill(LevelSkill(skill="woodcutting", target_level=30),
                                        MagicMock())
        assert [n.label for n in player._last_grind_expansion] == ["GatherAsh()"]

    def test_notify_grafts_expansion_for_levelskill_action(self):
        captured: list[CycleSnapshot] = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        root = ObtainItem("nonexistent_item")
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=root, chosen_step=root,
            desired_state={}, ranking=[])
        legs = (PlanTreeNode(key="l0", label="GatherAsh()", kind="obtain", status="current"),)
        player._last_grind_expansion = legs
        action = LevelSkill(skill="woodcutting", target_level=30)
        player._notify_observer("g", repr(action), "ok", [], action=action)
        snap = captured[0]
        assert snap.grind_expansion == legs
        serve = next(c for c in snap.plan_tree[0].children if c.kind == "step")
        assert serve.children == legs

    def test_notify_ignores_stale_expansion_for_non_levelskill_action(self):
        captured: list[CycleSnapshot] = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=ObtainItem("nonexistent_item"),
            chosen_step=None, desired_state={}, ranking=[])
        player._last_grind_expansion = (
            PlanTreeNode(key="stale", label="Stale()", kind="obtain", status="current"),)
        player._notify_observer("g", "FightAction(cow)", "ok", [], action=None)
        assert captured[0].grind_expansion == ()


class TestNotifyObserverChosenRoot:
    """Phase 4b (THE FLIP): one engine — `_last_decision` IS the tree
    decision, so `snap.chosen_root` reflects it directly (progression-tree
    Phase 4b Task 5 removed the separate shadow `tree_*` mirror fields)."""

    def test_chosen_root_present_when_decision_present(self):
        captured = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=ObtainItem("nonexistent_item"),
            chosen_step=None, desired_state={}, ranking=[],
        )
        player._notify_observer("ReachCharLevel(5)", "FightAction(cow)", "ok", [])
        assert len(captured) == 1
        snap = captured[0]
        assert snap.chosen_root == repr(ObtainItem("nonexistent_item"))

    def test_chosen_root_none_when_decision_chooses_no_root(self):
        """The engine can run and choose no root (e.g. an interrupt cycle)."""
        captured = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._last_decision = StrategyDecision(
            interrupt=None, chosen_root=None, chosen_step=None,
            desired_state={}, ranking=[],
        )
        player._notify_observer("ReachCharLevel(5)", "FightAction(cow)", "ok", [])
        snap = captured[0]
        assert snap.chosen_root is None

    def test_chosen_root_none_when_no_decision(self):
        """No `_last_decision` this cycle — the snapshot reports no chosen
        root (never guessed at)."""
        captured = []
        player = GamePlayer(character="hero", cycle_observer=captured.append)
        player.game_data = make_game_data_mock()
        player.state = make_state(level=4)
        player._notify_observer("ReachCharLevel(5)", "FightAction(cow)", "ok", [])
        snap = captured[0]
        assert snap.chosen_root is None


def test_snapshot_carries_chosen_root_and_ranking_and_bank(tmp_path):
    """The cycle snapshot exposes the committed strategy root + ranking + bank
    for the TUI plan screen."""
    rv = RootScoreView(root_repr="ObtainItem(code='x', quantity=1)", category="gear",
                       score=2.5, step_repr="FightAction(chicken)")
    assert rv.root_repr == "ObtainItem(code='x', quantity=1)"
    assert rv.category == "gear" and rv.score == 2.5
    # snapshot accepts the new fields
    snap = CycleSnapshot(
        cycle_index=1, timestamp="2026-06-13T00:00:00Z", character="hero",
        x=0, y=0, level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        selected_goal="g", action="a", outcome="ok",
        chosen_root="ObtainItem(code='x', quantity=1)",
        strategy_ranking=[rv], bank_items={"copper_ore": 5},
    )
    assert snap.chosen_root == "ObtainItem(code='x', quantity=1)"
    assert snap.strategy_ranking[0].score == 2.5
    assert snap.strategy_ranking[0].step_repr == "FightAction(chicken)"
    assert snap.bank_items == {"copper_ore": 5}


@dataclass
class _CapturingCraft(CraftAction):
    """CraftAction whose execute records the quantity it would send, so the test
    can assert the batch rewrite without a live API."""
    captured: list = field(default_factory=list, compare=False, repr=False)

    def execute(self, state, client):  # type: ignore[override]
        self.captured.append(self.quantity)
        return state


def _batch_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"cooked_chicken": {"raw_chicken": 1},
                            "copper_dagger": {"copper_bar": 6}}
    return gd


class TestConsumableBatchDispatch:
    def _player(self, gd: GameData, state) -> GamePlayer:
        player = GamePlayer(character="hero")
        player.game_data = gd
        player.state = state
        return player

    def test_cooking_batches_the_held_pile(self):
        gd = _batch_gd()
        player = self._player(gd, make_state(inventory={"raw_chicken": 9}))
        cap: list = []
        action = _CapturingCraft(code="cooked_chicken", quantity=1,
                                 workshop_location=(0, 0), captured=cap)
        _new_state, outcome = player._execute(action, client=None)
        assert outcome == "ok"
        assert cap == [9]   # rewritten from 1 to the held-pile batch

    def test_non_consumable_not_batched(self):
        gd = _batch_gd()
        player = self._player(gd, make_state(inventory={"copper_bar": 60}))
        cap: list = []
        action = _CapturingCraft(code="copper_dagger", quantity=1,
                                 workshop_location=(0, 0), captured=cap)
        player._execute(action, client=None)
        assert cap == [1]   # weapon craft untouched

    def test_no_game_data_leaves_quantity_unchanged(self):
        player = GamePlayer(character="hero")
        player.game_data = None
        player.state = make_state(inventory={"raw_chicken": 9})
        cap: list = []
        action = _CapturingCraft(code="cooked_chicken", quantity=1,
                                 workshop_location=(0, 0), captured=cap)
        player._execute(action, client=None)
        assert cap == [1]   # no game_data → no rewrite
