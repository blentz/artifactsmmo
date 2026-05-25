"""Tests for GamePlayer."""

import time
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import httpx
import pytest
from artifactsmmo_api_client.models.achievement_type import AchievementType
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.models.error_schema import ErrorSchema
from artifactsmmo_api_client.types import UNSET
from sqlmodel import Session

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer, _format_plan
from artifactsmmo_cli.ai.recovery import StuckSignal
from artifactsmmo_cli.ai.tiers import ObtainItem, ReachCharLevel
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import BalancedPersonality
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision, StrategyEngine
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_actions_execute import make_api_result, make_char_schema


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


class TestBuildActions:
    def test_includes_rest_and_deposit(self):
        player = GamePlayer(character="hero")
        player.game_data = make_game_data_mock()
        actions = player._build_actions()
        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
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
        # (recipe demand × batch buffer) exceeds the 20 held, so it is NOT
        # overstock — bag-full routes to DepositInventory, not the discard guard.
        gd._crafting_recipes = {"copper_dagger": {"copper_ore": 20}}
        player = self._with_strategy(gd, level=3,
                                     inventory={"copper_ore": 20}, inventory_max=20)
        player._bank_accessible = True
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

    def test_idle_no_task_selects_accept_task(self):
        player = self._with_strategy(make_game_data_mock(), level=3,
                                     task_type=None, task_code=None)
        decision = player._strategy.decide(player.state, player.game_data)
        actions = player._build_actions()
        goal, _plan, _tried = player._arbiter.select(
            decision, player.state, player.game_data, actions, player._selection_context())
        assert goal is not None and repr(goal) == "AcceptTask"


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
        gd = _winnable_gd({
            "chicken": {"level": 1, "hp": 10, "attack": {"fire": 1}},
            "wolf": {"level": 4, "hp": 10, "attack": {"fire": 1}},
            "titan": {"level": 8, "hp": 100000, "attack": {"fire": 1}},  # unwinnable
        })
        state = make_state(level=10, max_hp=100, attack={"fire": 50}, initiative=50)
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
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                state = player._fetch_world_state(client)
        assert isinstance(state, WorldState)

    def test_preserves_bank_state_from_current_state(self):
        player = GamePlayer(character="hero")
        player.state = make_state(bank_items={"gold": 100}, bank_gold=50)
        char = make_char_schema()
        client = MagicMock()
        empty_events = MagicMock()
        empty_events.data = []
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
            with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                state = player._fetch_world_state(client)
        assert state.bank_items == {"gold": 100}

    def test_raises_on_none_response(self):
        player = GamePlayer(character="hero")
        player.state = None
        client = MagicMock()
        with patch("artifactsmmo_cli.ai.player.get_character", return_value=None):
            with pytest.raises(RuntimeError):
                player._fetch_world_state(client)


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
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:other"

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
                with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                        new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:cooldown"
        assert "Server cooldown (HTTP 499)" in buf.getvalue()

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
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    new_state, outcome = player._execute(action, client)

        assert isinstance(new_state, WorldState)
        assert outcome == "error:network"

    def test_execute_bank_action_syncs_bank(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 5})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
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

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item", return_value=make_api_result(char)):
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
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    new_state, outcome = player._execute(action, client)

        assert outcome == "error:fight_lost"
        assert isinstance(new_state, WorldState)


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
        from artifactsmmo_cli.ai.actions.task import TaskExchangeAction
        actions = player._build_actions()
        exchange_actions = [a for a in actions if isinstance(a, TaskExchangeAction)]
        assert len(exchange_actions) == 1

    def test_build_actions_includes_task_exchange(self):
        player = self._make_player_with_gd()
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.task import TaskExchangeAction
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
        from artifactsmmo_cli.ai.actions.bank import WithdrawItemAction
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
        from artifactsmmo_cli.ai.actions.equipment import EquipAction
        actions = player._build_actions()
        equip_actions = [a for a in actions if isinstance(a, EquipAction) and a.code == "copper_ring"]
        slots = {a.slot for a in equip_actions}
        assert "ring1_slot" in slots
        assert "ring2_slot" in slots


class TestLogAction:
    def test_log_with_single_action(self):
        player = GamePlayer(character="hero")
        player.state = make_state()
        from artifactsmmo_cli.ai.actions.rest import RestAction
        from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
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

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=ApiActionError(496, "(locked bank_deposit achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_achievement", return_value=None):
                    with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                        player._execute(action, client)

        assert player._bank_accessible is False
        assert player._bank_blocked_since is not None

    def test_http496_without_achievement_code_leaves_unlock_monster_none(self):
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        # No achievement code in error message — no match for the regex
        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=ApiActionError(496, "bank access denied")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    player._execute(action, client)

        assert player._bank_accessible is False
        assert player._bank_unlock_monster is None

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
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    player._execute(action, client)

        assert player._bank_accessible is True  # unchanged

    def test_http496_with_achievement_code_calls_resolve(self):
        """When achievement code is in the 496 error, _resolve_bank_unlock_monster is called."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "skeleton"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=ApiActionError(496, "(myach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    player._execute(action, client)

        assert resolve_calls == ["myach"]
        assert player._bank_unlock_monster == "skeleton"

    def test_http496_skips_resolve_when_monster_already_set(self):
        """Once bank_unlock_monster is set, _resolve_bank_unlock_monster is not called again."""
        player = GamePlayer(character="hero")
        player.state = make_state(x=4, y=0, inventory={"copper_ore": 1})
        player.game_data = make_game_data_mock()
        player._bank_unlock_monster = "chicken"  # already resolved
        client = MagicMock()

        from artifactsmmo_cli.ai.actions.bank import DepositAllAction
        action = DepositAllAction(bank_location=(4, 0), game_data=GameData())
        char = make_char_schema()
        empty_events = MagicMock()
        empty_events.data = []

        resolve_calls = []

        def fake_resolve(c, code):
            resolve_calls.append(code)
            return "wolf"

        player._resolve_bank_unlock_monster = fake_resolve  # type: ignore

        with patch("artifactsmmo_cli.ai.actions.bank.deposit_item",
                   side_effect=RuntimeError("HTTP 496 (newach achievement_unlocked)")):
            with patch("artifactsmmo_cli.ai.player.get_character", return_value=make_api_result(char)):
                with patch("artifactsmmo_cli.ai.player.get_all_active_events", return_value=empty_events):
                    player._execute(action, client)

        # resolve should NOT be called since monster is already set
        assert resolve_calls == []
        assert player._bank_unlock_monster == "chicken"


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
        player._emit_trace("Rest", "RestoreHP", "ok", {"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 1})
        tracer.write_cycle.assert_called_once()
        record = tracer.write_cycle.call_args[0][0]
        assert record["cooldown_remaining_at_cycle_start"] > 0.0


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

    def test_no_progress_level3_exits(self):
        player = GamePlayer(character="hero")
        player._recovery_level[StuckSignal.NO_PROGRESS] = 2

        with pytest.raises(SystemExit) as exc_info:
            player._handle_stuck(StuckSignal.NO_PROGRESS, client=None)

        assert exc_info.value.code == 2


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
        player._bank_blocked_since = time.monotonic() - 61.0  # > 60s threshold

        player._maybe_retry_bank()

        assert player._bank_accessible is True
        assert player._bank_blocked_since is None

    def test_bank_retry_timer_does_not_reset_before_timeout(self):
        player = self._make_minimal_player()
        player.state = make_state(level=5)
        player._bank_accessible = False
        player._bank_blocked_since = time.monotonic() - 10.0  # only 10s ago

        player._maybe_retry_bank()

        assert player._bank_accessible is False  # still locked

    def test_bank_retry_does_not_fire_when_level_unchanged(self):
        """Timer elapsed but no level gained since block — retry must NOT fire."""
        player = self._make_minimal_player()
        player.state = make_state(level=5)
        # Block recorded at the same level the character is at now.
        player._blockers.mark_blocked("bank", char_level=5)
        player._bank_blocked_since = time.monotonic() - 61.0  # > 60s threshold

        player._maybe_retry_bank()

        # Level guard must suppress the retry: bank blocker must remain set.
        assert player._bank_accessible is False
        assert player._bank_blocked_since is not None


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
        player._bank_accessible = False

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

    def test_npc_buy_actions_include_consumables_only(self):
        """NPC buy actions are only built for items with hp_restore > 0."""
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
        }
        gd._crafting_recipes = {}
        gd._resource_skill = {}
        gd._monster_level = {}
        gd._npc_locations = {"cook": (5, 0)}
        gd._npc_stock = {"cook": ["cooked_chicken", "raw_iron"]}
        player.game_data = gd
        player.state = make_state()

        from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
        actions = player._build_actions()
        npc_buy_items = {a.item_code for a in actions if isinstance(a, NpcBuyAction)}

        assert "cooked_chicken" in npc_buy_items
        assert "raw_iron" not in npc_buy_items  # no hp_restore


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
            player.state = make_state(level=5, task_type="monsters", task_code="dragon",
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
        player.state = make_state(task_type="monsters", task_code="chicken",
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
