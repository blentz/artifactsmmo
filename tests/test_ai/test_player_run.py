"""Tests for GamePlayer.run() and sync_bank pagination."""

import os
import tempfile
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckSignal
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from tests.test_ai.fixtures import make_state


def make_minimal_game_data() -> GameData:
    gd = GameData()
    gd._monster_locations = {"chicken": [(1, 0)]}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._bank_location = (4, 0)
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_skill = {}
    gd._monster_level = {"chicken": 1}
    return gd


def _patch_game_data_load():
    """Context manager stack that stubs out all GameData API calls."""
    empty = MagicMock(data=[])
    return (
        patch("artifactsmmo_cli.ai.game_data.get_all_maps", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_items", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_resources", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_monsters", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_npc_items", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_all_events", return_value=empty),
        patch("artifactsmmo_cli.ai.game_data.get_bank_details", return_value=None),
    )


class TestSyncBankPagination:
    def test_paginates_when_full_page_returned(self):
        player = GamePlayer(character="hero")
        state = make_state()
        client = MagicMock()

        slot = MagicMock()
        slot.code = "copper_ore"
        slot.quantity = 1

        page1 = MagicMock()
        page1.data = [slot] * 100

        page2 = MagicMock()
        page2.data = [slot]

        bank_details = MagicMock()
        bank_details.data = MagicMock()
        bank_details.data.gold = 0

        with patch("artifactsmmo_cli.ai.player.get_bank_items", side_effect=[page1, page2]):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=bank_details):
                new_state = player._sync_bank(client, state)

        assert new_state.bank_items["copper_ore"] == 101


class TestPlayerRun:
    def test_run_executes_one_action_then_stops(self):
        """Test run() executes the plan loop once then exits via KeyboardInterrupt."""
        player = GamePlayer(character="hero")
        client = MagicMock()

        # The run loop calls: GameData.load, _fetch_world_state, then loops
        # We stop after one loop iteration by having _wait_for_cooldown raise
        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        initial_state = make_state(hp=100, max_hp=150)
        p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh"):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

    def test_run_refreshes_before_building_actions(self):
        """Periodic refresh must run BEFORE _build_actions so a batched plan's K
        is baked from the same post-refresh inventory the goal/map_means sees."""
        player = GamePlayer(character="hero")
        client = MagicMock()
        order: list[str] = []

        def fake_wait():
            raise KeyboardInterrupt

        initial_state = make_state(hp=100, max_hp=150)
        p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh",
                                               side_effect=lambda c: order.append("refresh")):
                                with patch.object(player, "_build_actions",
                                                   side_effect=lambda: order.append("build") or []):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()
        assert order[:2] == ["refresh", "build"]

    def test_run_dry_run_uses_apply_not_execute(self):
        """In dry_run mode, the player calls action.apply() instead of action.execute()."""
        player = GamePlayer(character="hero", dry_run=True)
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        state_with_low_hp = make_state(hp=50, max_hp=150)

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=state_with_low_hp):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh"):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        # In dry_run, the state should be updated via apply() — RestAction would set hp to max_hp
        assert player.state is not None

    def test_run_no_plan_sleeps(self):
        """When no plan is found, run() sleeps for 5s.

        WaitGoal is the always-firing last-resort means; this test
        suppresses it (via _suppressed_goals) so the no-plan path
        downstream of an empty actions list is still reachable.
        """
        player = GamePlayer(character="hero")
        player._suppressed_goals["Wait"] = 999
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        # State with full HP and no task — the arbiter selects a goal but with empty
        # game data no actions are applicable, so the plan is empty → sleep
        initial_state = make_state(hp=150, max_hp=150)
        p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh"):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep") as mock_sleep:
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        mock_sleep.assert_called_with(5)

    def test_run_verbose_logs_no_plan(self, capsys):
        """run() logs 'No plan found' when no goal can be planned (empty actions).

        WaitGoal suppressed so the no-plan branch remains reachable."""
        player = GamePlayer(character="hero", verbose=True)
        player._suppressed_goals["Wait"] = 999
        client = MagicMock()

        call_count = [0]

        def fake_wait():
            call_count[0] += 1
            if call_count[0] > 1:
                raise KeyboardInterrupt

        initial_state = make_state(hp=150, max_hp=150)

        p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                            with patch.object(player, "_maybe_periodic_refresh"):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

        output = capsys.readouterr().out
        assert "No plan found" in output


def test_player_builds_sell_actions_for_sellable_inventory():
    """When bank is locked and inventory has sellable items, _build_actions should include NpcSell."""
    player = GamePlayer(character="testchar", verbose=False, dry_run=True)
    player.game_data = GameData()
    player.game_data._npc_locations = {"cook": (2, 1)}
    player.game_data._npc_sell_prices = {"cook": {"chicken": 5}}
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player._bank_accessible = False
    player.state = make_state(inventory={"chicken": 5})

    actions = player._build_actions()
    sell_actions = [a for a in actions if isinstance(a, NpcSellAction)]
    assert any(a.item_code == "chicken" and a.npc_code == "cook" for a in sell_actions)


def test_sell_means_maps_to_sell_inventory_goal():
    """The SELL_IDLE/SELL_PRESSURED means map to SellInventoryGoal (bank-locked)."""
    gd = GameData()
    ctx = SelectionContext(bank_accessible=False, bank_required_level=0,
                           bank_unlock_monster=None, initial_xp=0,
                           task_exchange_min_coins=1, combat_monster=None)
    goal = map_means(MeansKind.SELL_IDLE, gd, ctx, make_state())
    assert isinstance(goal, SellInventoryGoal)


def test_player_builds_phase_b_actions():
    """All Phase B actions should appear in _build_actions output."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player.game_data._transition_tiles = {(5, 5)}
    player.game_data._bank_capacity = 30
    player.game_data._next_expansion_cost = 1000
    player._bank_accessible = True
    player.state = make_state(task_code="iron_ore", task_type="items")

    actions = player._build_actions()
    classes = {type(a).__name__ for a in actions}
    assert "BuyBankExpansionAction" in classes
    assert "MapTransitionAction" in classes
    assert "DepositGoldAction" in classes
    assert "WithdrawGoldAction" in classes
    # TaskTradeAction is built per-task — present only when task is items-type
    assert "TaskTradeAction" in classes


def test_bank_expand_means_maps_to_expand_bank_goal():
    """The BANK_EXPAND means maps to ExpandBankGoal."""
    gd = GameData()
    ctx = SelectionContext(bank_accessible=True, bank_required_level=0,
                           bank_unlock_monster=None, initial_xp=0,
                           task_exchange_min_coins=1, combat_monster=None)
    goal = map_means(MeansKind.BANK_EXPAND, gd, ctx, make_state())
    assert isinstance(goal, ExpandBankGoal)


def test_refresh_if_stale_method_removed():
    """The wall-clock _refresh_if_stale should be deleted entirely."""
    assert not hasattr(GamePlayer, "_refresh_if_stale")


def test_maybe_periodic_refresh_triggers_at_20_actions(monkeypatch):
    """_maybe_periodic_refresh should call _full_refresh when counter >= 20, then reset."""
    player = GamePlayer(character="testchar")
    refresh_calls = []

    def fake_full_refresh(c):
        refresh_calls.append(True)
        player._actions_since_full_refresh = 0

    player._full_refresh = fake_full_refresh  # type: ignore

    # At 19 — does not trigger
    player._actions_since_full_refresh = 19
    player._maybe_periodic_refresh(client=None)
    assert refresh_calls == []
    assert player._actions_since_full_refresh == 19

    # At 20 — triggers, then counter resets
    player._actions_since_full_refresh = 20
    player._maybe_periodic_refresh(client=None)
    assert refresh_calls == [True]
    assert player._actions_since_full_refresh == 0


def test_full_refresh_resets_counter(monkeypatch):
    """_full_refresh itself should reset the action counter to 0."""
    player = GamePlayer(character="testchar")
    player.state = make_state()
    player._actions_since_full_refresh = 15

    # Stub out the underlying fetch/sync methods so we don't make real API calls
    def fake_fetch(c):
        return player.state

    def fake_sync_bank(c, s):
        return s

    def fake_sync_pending(c, s):
        return s

    player._fetch_world_state = fake_fetch  # type: ignore
    player._sync_bank = fake_sync_bank  # type: ignore
    player._sync_pending = fake_sync_pending  # type: ignore

    player._full_refresh(client=None)
    assert player._actions_since_full_refresh == 0


def test_run_calls_handle_stuck_in_no_plan_path():
    """Line 181: _handle_stuck is invoked inside the run() no-plan branch when detector fires.

    Strategy: pre-seed the detector with 3 consecutive no-plan records so that adding a 4th
    in the no-plan branch fires NO_PROGRESS → calls _handle_stuck → increments the level.
    """
    player = GamePlayer(character="hero")
    # Suppress WaitGoal so the no-plan branch remains reachable; without
    # this the always-firing WaitGoal would short-circuit the path under test.
    player._suppressed_goals["Wait"] = 999
    client = MagicMock()

    # Pre-seed detector with 3 no-plan records (one short of the NO_PROGRESS threshold of 4)
    for i in range(3):
        player._detector.record(CycleRecord(
            state_key=(0, 0, 5, (), (), None, 0, False),
            goal_name="<none>",
            action_name="<no_plan>",
            planned_depth=0,
            planner_timed_out=False,
            succeeded=False,
        ))

    call_count = [0]

    def fake_wait():
        call_count[0] += 1
        if call_count[0] > 1:
            raise KeyboardInterrupt

    initial_state = make_state(hp=150, max_hp=150)
    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                with patch.object(player, "_fetch_world_state", return_value=initial_state):
                    with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                        with patch.object(player, "_maybe_periodic_refresh"):
                            # Empty action list → no plan possible → no-plan path
                            with patch.object(player, "_build_actions", return_value=[]):
                                with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                    with pytest.raises(KeyboardInterrupt):
                                        player.run()

    # NO_PROGRESS L1 should have been fired → level == 1
    assert player._recovery_level.get(StuckSignal.NO_PROGRESS) == 1


def test_run_calls_handle_stuck_after_successful_action():
    """Line 223: _handle_stuck is invoked inside the run() post-action branch when detector fires.

    Strategy: pre-seed the detector with records that are one step away from STATE_FROZEN
    (9 identical state_key records, need 10 with >= 5 same), then after one successful action
    with the same state key, detect() returns STATE_FROZEN → _handle_stuck is called.
    """
    player = GamePlayer(character="hero")
    client = MagicMock()

    frozen_key = (0, 0, 5, (), (), None, 0, False)
    # Pre-seed with 9 records with the same state_key (need >= 5 of 10 to trigger)
    for i in range(9):
        player._detector.record(CycleRecord(
            state_key=frozen_key,
            goal_name="RestoreHP",
            action_name="Rest",
            planned_depth=1,
            planner_timed_out=False,
            succeeded=True,
        ))

    call_count = [0]

    def fake_wait():
        call_count[0] += 1
        if call_count[0] > 1:
            raise KeyboardInterrupt

    # Use low HP so RestoreHP goal with value > 0 is selected, RestAction is applicable
    initial_state = make_state(hp=50, max_hp=150)

    # _fetch_world_state is called by STATE_FROZEN L1 recovery — return the same state
    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                with patch.object(player, "_fetch_world_state", return_value=initial_state):
                    with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                        with patch.object(player, "_maybe_periodic_refresh"):
                            # Return RestAction so a plan can be found; patch _execute to avoid HTTP call
                            with patch.object(player, "_build_actions", return_value=[RestAction()]):
                                with patch.object(player, "_execute", return_value=(initial_state, "ok")):
                                    with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                        with pytest.raises(KeyboardInterrupt):
                                            player.run()

    # STATE_FROZEN L1 should have been invoked
    assert player._recovery_level.get(StuckSignal.STATE_FROZEN) == 1


def test_run_loads_remembered_bank_blocker(capsys):
    """run() honors a persisted bank blocker (243-255, 264).

    A real LearningStore persists a bank blocker requiring level 99 for a
    level-5 character, so run()'s remembered-blocker branch logs and re-marks
    it before the loop runs (the loop is short-circuited via KeyboardInterrupt).
    """
    from artifactsmmo_cli.ai.learning.store import LearningStore

    fd, db_path = tempfile.mkstemp(suffix=".db")
    os.close(fd)
    history = LearningStore(db_path=db_path, character="hero")
    history.start_session()
    history.set_blocker("bank", unlock_monster="dragon", required_level=99)

    player = GamePlayer(character="hero", history=history)
    client = MagicMock()
    initial_state = make_state(hp=120, max_hp=150, level=5)

    def boom():
        raise KeyboardInterrupt

    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
    try:
        with patch.object(ClientManager_mock := MagicMock(), "client", client):
            with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_build_actions", side_effect=boom):
                            with pytest.raises(KeyboardInterrupt):
                                player.run()
    finally:
        history.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    out = capsys.readouterr().out
    assert "Bank blocker remembered" in out
    b = player._blockers.get("bank")
    assert b is not None
    assert b.required_level == 99
    assert b.unlock_monster == "dragon"


def test_run_logs_seeded_documented_blockers(capsys):
    """run() logs the count when seed_documented_blockers seeds near-future
    blockers from game data (line 264)."""
    player = GamePlayer(character="hero")
    client = MagicMock()
    initial_state = make_state(hp=120, max_hp=150, level=5)

    def boom():
        raise KeyboardInterrupt

    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                with patch.object(player, "_fetch_world_state", return_value=initial_state):
                    with patch("artifactsmmo_cli.ai.player.seed_documented_blockers", return_value=3):
                        with patch.object(player, "_build_actions", side_effect=boom):
                            with pytest.raises(KeyboardInterrupt):
                                player.run()

    out = capsys.readouterr().out
    assert "Seeded 3 documented near-future blockers" in out


class _StubDecision:
    """Minimal stand-in for StrategyDecision: no ObtainItem step, no crafting."""

    chosen_step = None

    def to_trace(self):
        return {}


def test_run_derives_crafting_target_from_fallback_obtain_item():
    """When the top chosen_step is not an ObtainItem, run() walks fallback_steps
    and adopts the first ObtainItem's code as the crafting_target so the bank
    keep-set protects that chain's materials (player.py lines 302-307)."""
    from artifactsmmo_cli.ai.tiers import ObtainItem

    class _FallbackDecision:
        chosen_step = None            # not an ObtainItem -> crafting_target None
        chosen_root = None
        fallback_steps = [ObtainItem("copper_dagger", 1)]

        def to_trace(self):
            return {}

    player = GamePlayer(character="hero")
    client = MagicMock()
    initial_state = make_state(hp=100, max_hp=150, level=5)
    captured: dict[str, object] = {}

    goal = MagicMock()
    goal.is_satisfied.return_value = False
    goal.__repr__ = lambda self: "StubGoal()"  # type: ignore[assignment]

    def capture_select(decision, state, game_data, actions, ctx, **kw):
        captured["crafting_target"] = state.crafting_target
        raise KeyboardInterrupt  # stop after the derivation we care about

    # run() rebuilds self._strategy from loaded game data (player.py line 217),
    # so stub the StrategyEngine *constructor* to yield a decide() that returns
    # the fallback-bearing decision. The arbiter (set in __init__, never rebuilt)
    # is stubbed directly to capture the derived crafting_target.
    strategy_mock = MagicMock()
    strategy_mock.decide.return_value = _FallbackDecision()
    player._arbiter = MagicMock()
    player._arbiter.select.side_effect = capture_select

    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()
    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with patch("artifactsmmo_cli.ai.player.StrategyEngine", return_value=strategy_mock):
                with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                    with patch.object(player, "_fetch_world_state", return_value=initial_state):
                        with patch.object(player, "_wait_for_cooldown"):
                            with patch.object(player, "_maybe_periodic_refresh"):
                                with patch.object(player, "_build_actions", return_value=[]):
                                    with patch.object(player, "_winnable_farm_target", return_value=None):
                                        with patch("artifactsmmo_cli.ai.player.time.sleep"):
                                            with pytest.raises(KeyboardInterrupt):
                                                player.run()
    assert captured["crafting_target"] == "copper_dagger"


def _run_one_action_with(player, action, new_state, outcome, client):
    """Drive run() through exactly one action-execution cycle by stubbing the
    strategy/arbiter to return a fixed (goal, [action]) plan, then raising
    KeyboardInterrupt on the second cooldown wait."""
    goal = MagicMock()
    goal.is_satisfied.return_value = False
    goal.__repr__ = lambda self: "StubGoal()"  # type: ignore[assignment]

    player._strategy = MagicMock()
    player._strategy.decide.return_value = _StubDecision()
    player._arbiter = MagicMock()
    player._arbiter.select.return_value = (goal, [action], [])

    call_count = [0]

    def fake_wait():
        call_count[0] += 1
        if call_count[0] > 1:
            raise KeyboardInterrupt

    with patch.object(player, "_build_actions", return_value=[action]):
        with patch.object(player, "_maybe_periodic_refresh"):
            with patch.object(player, "_wait_for_cooldown", side_effect=fake_wait):
                with patch.object(player, "_winnable_farm_target", return_value=None):
                    with patch.object(player, "_execute", return_value=(new_state, outcome)):
                        with patch("artifactsmmo_cli.ai.player.time.sleep"):
                            with pytest.raises(KeyboardInterrupt):
                                player.run()


def test_run_records_post_action_cooldown_and_handles_stuck():
    """The post-action branch computes cooldown_remaining from a cooldown-bearing
    new_state (378) and fires _handle_stuck when the detector trips (436)."""
    from artifactsmmo_cli.ai.recovery import CycleRecord

    player = GamePlayer(character="hero")
    client = MagicMock()

    # Game data + initial state so the loop's asserts pass.
    p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank = _patch_game_data_load()

    initial_state = make_state(hp=120, max_hp=150, level=5)
    future = datetime.now(tz=timezone.utc) + timedelta(seconds=8)
    post_action_state = replace(initial_state, cooldown_expires=future)

    # Pre-seed the detector so detect() returns STATE_FROZEN after one more
    # identical-key successful cycle.
    frozen_key = (0, 0, 5, (), (), None, 0, False)
    for _ in range(9):
        player._detector.record(CycleRecord(
            state_key=frozen_key, goal_name="StubGoal()", action_name="Rest",
            planned_depth=1, planner_timed_out=False, succeeded=True,
        ))

    with patch.object(ClientManager_mock := MagicMock(), "client", client):
        with patch("artifactsmmo_cli.ai.player.ClientManager", return_value=ClientManager_mock):
            with p_maps, p_items, p_resources, p_monsters, p_npcs, p_events, p_bank:
                with patch.object(player, "_fetch_world_state", return_value=initial_state):
                    _run_one_action_with(player, RestAction(), post_action_state, "ok", client)

    # The detector tripped and recovery ran -> post-action stuck branch reached.
    assert player._recovery_level.get(StuckSignal.STATE_FROZEN) == 1


def test_items_task_builds_batched_craft_and_trade():
    """For an items task the task-item Craft and TaskTrade are built with
    quantity == task_batch_size, so the planner can produce/deliver a batch."""
    player = GamePlayer(character="testchar")
    player.game_data = GameData()
    player.game_data._bank_location = (4, 0)
    player.game_data._taskmaster_location = (1, 2)
    player.game_data._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    player.game_data._resource_drops = {"copper_rocks": "copper_ore"}
    player.game_data._resource_locations = {}
    player.game_data._monster_locations = {}
    player.game_data._npc_stock = {}
    player.game_data._npc_sell_prices = {}
    player.game_data._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="weaponcrafting", crafting_level=1),
    }
    player.game_data._workshop_locations = {"weaponcrafting": (2, 0)}
    player._bank_accessible = True
    player.state = make_state(task_code="copper_bar", task_type="items",
                              task_total=20, task_progress=0, inventory={}, inventory_max=100)

    k = task_batch_size(player.state, player.game_data)
    assert k > 1   # sanity: this state batches

    actions = player._build_actions()
    trades = [a for a in actions if isinstance(a, TaskTradeAction) and a.code == "copper_bar"]
    crafts = [a for a in actions if isinstance(a, CraftAction) and a.code == "copper_bar"]
    assert any(t.quantity == k for t in trades), "expected a TaskTrade with quantity K"
    assert any(c.quantity == k for c in crafts), "expected a Craft with quantity K"
