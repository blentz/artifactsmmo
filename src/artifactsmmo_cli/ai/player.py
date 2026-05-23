"""GOAP AI player: main sense→plan→act loop."""

import json
import re
import time
from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from typing import Any

import httpx
from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.api.achievements.get_achievement_achievements_code_get import sync as get_achievement
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character
from artifactsmmo_api_client.api.events.get_all_active_events_events_active_get import sync as get_all_active_events
from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync as get_bank_details
from artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get import sync as get_bank_items
from artifactsmmo_api_client.api.my_account.get_pending_items_my_pending_items_get import sync as get_pending_items
from artifactsmmo_api_client.models.achievement_type import AchievementType
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.types import Unset

from artifactsmmo_cli.ai.actions.bank import DepositAllAction, WithdrawItemAction
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS, EquipAction, UnequipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction, CompleteTaskAction, TaskCancelAction, TaskExchangeAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.blockers import BlockerRegistry, seed_documented_blockers
from artifactsmmo_cli.ai.combat import predict_win
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, GoalAttempt, GoalRankEntry
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.projections import PathPlan, cheapest_path_to_level
from artifactsmmo_cli.ai.learning.scalarizer import _max_sell_back_price
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner, _state_key
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal
from artifactsmmo_cli.ai.strategy_driver import (
    FALLBACK_BAND,
    STRATEGY_BAND,
    MetaGoalAdapter,
    strategy_goal,
)
from artifactsmmo_cli.ai.tiers import BalancedPersonality, CharacterObjective, StrategyEngine
from artifactsmmo_cli.ai.tracing import NullTracer, Tracer
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.client_manager import ClientManager

WIN_RATE_THRESHOLD = 0.5
"""Observed win rate at or above which a monster is considered beatable."""
MIN_WIN_SAMPLES = 5
"""Minimum recorded fights before an observed win rate can veto a stat
prediction (below this the sample is too noisy to trust)."""
_BANK_RETRY_SECONDS = 60.0  # retry bank access this long after an HTTP 496 block
_ACHIEVEMENT_CODE_RE = re.compile(r"\((\w+) achievement_unlocked")
_BANK_TILE = None  # resolved from game_data at runtime
_PLAN_PREVIEW = 5  # max distinct steps shown in verbose plan output


def _delete_cost(item_code: str, game_data: "GameData") -> float:
    """Cost weight for deleting an item.

    Ingredient-first ordering: an item that's both a craft ingredient AND sellable
    gets the harsher penalty (50.0), not the milder sellable penalty (25.0).
    """
    is_ingredient = any(item_code in recipe for recipe in game_data._crafting_recipes.values())
    has_sell_price = bool(game_data.npcs_buying_item(item_code))
    if is_ingredient:
        return 50.0
    if has_sell_price:
        return 25.0
    return 5.0


def _format_plan(plan: list[Action]) -> str:
    """Summarise a plan as 'A×N → B → C×M … (+K more)' instead of raw repetition."""
    if not plan:
        return ""
    segments: list[str] = []
    i = 0
    while i < len(plan) and len(segments) < _PLAN_PREVIEW:
        step = repr(plan[i])
        count = 1
        while i + count < len(plan) and repr(plan[i + count]) == step:
            count += 1
        segments.append(f"{step}×{count}" if count > 1 else step)
        i += count
    remaining = len(plan) - i
    suffix = f" … (+{remaining} more)" if remaining > 0 else ""
    return " → ".join(segments) + suffix


class GamePlayer:
    """Autonomous GOAP AI player for a single character."""

    def __init__(
        self,
        character: str,
        verbose: bool = False,
        dry_run: bool = False,
        tracer: Tracer | None = None,
        history: LearningStore | None = None,
        cycle_observer: "Callable[[CycleSnapshot], None] | None" = None,
    ) -> None:
        self.character = character
        self.verbose = verbose
        self.dry_run = dry_run
        self.planner = GOAPPlanner()
        self.state: WorldState | None = None
        self.game_data: GameData | None = None
        # Generic blocker registry — replaces what used to be ~5 bank-specific
        # player fields. New gates (workshop, taskmaster, transitions) plug in
        # by adding a code to this registry instead of growing player.
        self._blockers = BlockerRegistry()
        self._detector = StuckDetector(history_size=30)
        self._suppressed_goals: dict[str, int] = {}
        self._actions_since_full_refresh: int = 0
        self._recovery_level: dict[StuckSignal, int] = {}
        self._last_goal_name: str | None = None
        self._wildcard_mode: bool = False
        self.tracer: Tracer = tracer or NullTracer()
        self._cycle_counter: int = 0
        self._committed_upgrade_target: tuple[str, str] | None = None
        # Tier-3 strategy engine (built after game-data load); P3a runs it in
        # shadow — its decision is traced each cycle but does not drive the bot.
        self._objective: CharacterObjective | None = None
        self._strategy: StrategyEngine | None = None
        # Sticky goal commitment: the goal repr we keep pursuing across cycles
        # until it is satisfied or can no longer plan, so the selector stops
        # thrashing between near-equal-priority goals every cycle.
        self._committed_goal_name: str | None = None
        # Learned minimum tasks_coin worth attempting a taskmaster exchange. The
        # API does not expose the per-exchange cost as data, so we discover it
        # from HTTP 478 ("missing items") failures: raise the bound past any coin
        # count that failed, and pin it to the exact cost once an exchange
        # succeeds. Starts at 1 (optimistic) — never a hardcoded cost.
        self._task_exchange_min_coins: int = 1
        self._goal_first_selected_at: dict[str, int] = {}
        self.history = history
        self._last_path_plan: PathPlan | None = None
        self._cycle_observer = cycle_observer

    def set_cycle_observer(self, observer: "Callable[[CycleSnapshot], None] | None") -> None:
        """Allow callers (e.g. TUI host) to subscribe after construction."""
        self._cycle_observer = observer

    # === Backward-compatibility shims that delegate to the blocker registry ===
    # These let the rest of player.py keep using the old field names while the
    # registry owns the actual state. Remove the shims (and update callers) in
    # a follow-up pass.

    @property
    def _bank_accessible(self) -> bool:
        return not self._blockers.is_blocked("bank")

    @_bank_accessible.setter
    def _bank_accessible(self, value: bool) -> None:
        """Setter for backward-compat: True clears the blocker; False sets
        one with whatever metadata was previously known (or empty)."""
        if value:
            self._blockers.clear("bank")
        elif not self._blockers.is_blocked("bank"):
            self._blockers.mark_blocked("bank", char_level=0)

    @property
    def _bank_blocked_since(self) -> float | None:
        b = self._blockers.get("bank")
        return b.blocked_since_monotonic if b else None

    @_bank_blocked_since.setter
    def _bank_blocked_since(self, value: float | None) -> None:
        b = self._blockers.get("bank")
        if b is None:
            return
        b.blocked_since_monotonic = value

    @property
    def _bank_blocked_at_level(self) -> int:
        b = self._blockers.get("bank")
        return b.blocked_at_char_level if b else 0

    @property
    def _bank_unlock_monster(self) -> str | None:
        b = self._blockers.get("bank")
        return b.unlock_monster if b else None

    @_bank_unlock_monster.setter
    def _bank_unlock_monster(self, value: str | None) -> None:
        b = self._blockers.get("bank")
        if b is None:
            # Tests sometimes set the monster before any 496 — create an
            # empty blocker so the attribute sticks.
            self._blockers.mark_blocked("bank", char_level=0, unlock_monster=value)
            return
        b.unlock_monster = value

    @property
    def _bank_required_level(self) -> int:
        b = self._blockers.get("bank")
        return b.required_level if b else 0

    def run(self) -> None:
        """Main loop: sense → select goal → plan → act."""
        client_manager = ClientManager()
        client = client_manager.client

        print(f"[{self._now()}] Loading game data...")
        self.game_data = GameData.load(client)
        # Build the Tier-3 strategy engine once (shadow mode — traced only).
        self._objective = CharacterObjective.from_game_data(self.game_data)
        self._strategy = StrategyEngine(self._objective, BalancedPersonality())

        print(f"[{self._now()}] Fetching character state...")
        self.state = self._fetch_world_state(client)

        # Persistent blocker memory: if a previous session learned that the
        # bank requires level N to unlock and we're still below N, mark the
        # bank inaccessible upfront instead of wasting a cycle re-discovering.
        if self.history is not None:
            self._blockers = BlockerRegistry.load(self.history, known_codes=["bank"])
            self._drop_stale_bank_lock()
            b = self._blockers.get("bank")
            if b is not None and self.state.level < b.required_level:
                # Refresh blocked_since/at_level so the retry timer keys off
                # this session's start, not the original discovery.
                self._blockers.mark_blocked(
                    "bank",
                    char_level=self.state.level,
                    unlock_monster=b.unlock_monster,
                    required_level=b.required_level,
                )
                print(f"[{self._now()}] Bank blocker remembered: need level "
                      f"{b.required_level} to fight {b.unlock_monster}; deferring bank goals until then")

        # Seed documented blockers from game_data: near-future combat,
        # equip, craft, gather prereqs the char is close to unlocking. Adds
        # nothing for gates the char has already cleared. Discovered
        # blockers from the learning store (above) take precedence.
        seeded = seed_documented_blockers(self._blockers, self.game_data, self.state)
        if seeded:
            print(f"[{self._now()}] Seeded {seeded} documented near-future blockers from game data")

        print(f"[{self._now()}] Starting play loop for {self.character}")

        try:
            while True:
                actions = self._build_actions()
                self._maybe_periodic_refresh(client)
                self._wait_for_cooldown()

                assert self.state is not None
                assert self.game_data is not None
                state = self.state
                game_data = self.game_data

                goals = self._build_goals()
                # Snapshot all goal priorities ONCE per cycle so the trace
                # records what every goal scored at decision time. Avoids
                # re-calling priority() (some implementations hit the store).
                goal_priorities: list[tuple[Goal, float]] = [
                    (g, g.priority(state, game_data, self.history)) for g in goals
                ]
                goal_priorities.sort(key=lambda gp: gp[1], reverse=True)
                goals = [g for g, _ in goal_priorities]
                # Structured ranking for the trace: every considered goal, sorted.
                goal_rank_trace: list[dict[str, object]] = [
                    {"goal": repr(g), "priority": round(p, 2)}
                    for g, p in goal_priorities
                ]

                if self.verbose:
                    goal_summary = "  ".join(f"{repr(g)}={p:.1f}" for g, p in goal_priorities)
                    print(f"[{self._now()}] Goals: {goal_summary}")

                selected_goal, plan, goals_tried = self._select_goal(
                    state, game_data, actions, goal_priorities
                )
                if selected_goal is not None:
                    self._last_goal_name = repr(selected_goal)
                    self._note_goal_selection(repr(selected_goal), cycle_index=self._cycle_counter)

                if not plan or selected_goal is None:
                    print(f"[{self._now()}] No plan found — waiting 5s")
                    # Record no-plan cycle for NO_PROGRESS detection
                    self._detector.record(self._make_cycle_record(
                        goal_name="<none>",
                        action_name="<no_plan>",
                        planned_depth=0,
                        planner_timed_out=self.planner.last_stats.timed_out,
                        succeeded=False,
                    ))
                    # Surface the last planner stats AND the per-goal attempts
                    # so a no_plan cycle is debuggable from trace alone.
                    last = self.planner.last_stats
                    no_plan_stats: dict[str, object] = {
                        "nodes": last.nodes_explored,
                        "depth": last.max_depth_reached,
                        "timed_out": last.timed_out,
                        "plan_len": 0,
                        "goals_tried": goals_tried,
                        "goal_rank": goal_rank_trace,
                        **self._path_trace_snapshot(),
                    }
                    self._emit_trace(
                        action_name="<no_plan>",
                        goal_name="<none>",
                        outcome="no_plan",
                        planner_stats=no_plan_stats,
                    )
                    self._notify_observer(
                        "<none>", "<no_plan>", "no_plan", goal_rank_trace,
                        planner_stats=no_plan_stats,
                    )
                    self._record_learning_cycle(
                        prev_state=self.state,
                        new_state=self.state,
                        action_repr="<no_plan>",
                        action_class="NoPlan",
                        outcome="no_plan",
                        selected_goal="<none>",
                        predicted_cost=0.0,
                        actual_cooldown_seconds=0.0,
                        planner_nodes=self.planner.last_stats.nodes_explored,
                        planner_depth=self.planner.last_stats.max_depth_reached,
                        planner_timed_out=self.planner.last_stats.timed_out,
                        plan_len=0,
                    )
                    signal = self._detector.detect()
                    if signal is not None:
                        self._handle_stuck(signal, client)
                    time.sleep(5)
                    continue

                if self.verbose:
                    plan_str = _format_plan(plan)
                    relevant = selected_goal.relevant_actions(actions, state, game_data)
                    applicable = [repr(a) for a in relevant if a.is_applicable(state, game_data)]
                    goal_prio = selected_goal.priority(state, game_data, self.history)
                    print(f"[{self._now()}] Goal: {selected_goal}({goal_prio:.1f})  Plan: {plan_str}")
                    print(f"[{self._now()}] Applicable: {applicable}")

                action = plan[0]
                self._log_action(action, selected_goal, plan)

                prev_state_for_learning = self.state
                if self.dry_run:
                    new_state = action.apply(state, game_data)
                    outcome = "ok"
                else:
                    new_state, outcome = self._execute(action, client)

                now = datetime.now(tz=timezone.utc)
                cooldown_remaining = 0.0
                if new_state.cooldown_expires is not None:
                    cooldown_remaining = max(0.0, (new_state.cooldown_expires - now).total_seconds())
                predicted = action.cost(prev_state_for_learning, game_data, self.history)
                cycles_to_satisfy = None
                self._learn_task_exchange_cost(action, prev_state_for_learning, new_state, outcome)
                self._record_task_reward_if_completed(
                    prev_state_for_learning, new_state, type(action).__name__, outcome
                )
                if outcome == "ok" and selected_goal.is_satisfied(new_state):
                    cycles_to_satisfy = self._compute_cycles_to_satisfy(repr(selected_goal), self._cycle_counter)
                    # Goal achieved — release the commitment so the next cycle
                    # is free to select whatever is now most important.
                    if repr(selected_goal) == self._committed_goal_name:
                        self._committed_goal_name = None
                self._record_learning_cycle(
                    prev_state=prev_state_for_learning,
                    new_state=new_state,
                    action_repr=repr(action),
                    action_class=type(action).__name__,
                    outcome=outcome,
                    selected_goal=repr(selected_goal),
                    predicted_cost=predicted,
                    actual_cooldown_seconds=cooldown_remaining,
                    planner_nodes=self.planner.last_stats.nodes_explored,
                    planner_depth=self.planner.last_stats.max_depth_reached,
                    planner_timed_out=self.planner.last_stats.timed_out,
                    plan_len=len(plan),
                    cycles_to_satisfy=cycles_to_satisfy,
                )
                self.state = new_state

                # After action.execute (or dry_run apply), record the cycle for stuck detection
                self._detector.record(self._make_cycle_record(
                    goal_name=repr(selected_goal),
                    action_name=repr(action),
                    planned_depth=len(plan),
                    planner_timed_out=self.planner.last_stats.timed_out,
                    succeeded=(outcome == "ok"),
                ))
                self._actions_since_full_refresh += 1
                self._decrement_suppressions()
                cycle_stats: dict[str, object] = {
                    "nodes": self.planner.last_stats.nodes_explored,
                    "depth": self.planner.last_stats.max_depth_reached,
                    "timed_out": self.planner.last_stats.timed_out,
                    "plan_len": len(plan),
                    "goals_tried": goals_tried,
                    "goal_rank": goal_rank_trace,
                    **self._path_trace_snapshot(),
                }
                self._emit_trace(
                    action_name=repr(action),
                    goal_name=repr(selected_goal),
                    outcome=outcome,
                    planner_stats=cycle_stats,
                )
                self._notify_observer(
                    repr(selected_goal) if selected_goal else "<none>",
                    repr(action), outcome, goal_rank_trace,
                    planner_stats=cycle_stats,
                )
                signal = self._detector.detect()
                if signal is not None:
                    self._handle_stuck(signal, client)
        finally:
            self.tracer.close()

    def _execute(self, action: Action, client: AuthenticatedClient) -> tuple[WorldState, str]:
        """Execute an action. Returns (new_state, outcome_str).

        outcome is "ok" on success, or "error:<kind>" on RuntimeError. Outcome is
        what gets recorded by _record_learning_cycle so learned costs/success rates
        don't conflate wins with losses.
        """
        assert self.state is not None
        try:
            new_state = action.execute(self.state, client)
            # Re-sync bank state after visiting bank
            if isinstance(action, (DepositAllAction, WithdrawItemAction)):
                new_state = self._sync_bank(client, new_state)
            # Re-sync pending items after claiming one
            if isinstance(action, ClaimPendingItemAction):
                new_state = self._sync_pending(client, new_state)
            return new_state, "ok"
        except RuntimeError as e:
            msg = str(e)
            if "HTTP 499" in msg:
                print(f"[{self._now()}] Server cooldown (HTTP 499) — refreshing state")
                outcome = "error:cooldown"
            elif "HTTP 496" in msg and isinstance(action, (DepositAllAction, WithdrawItemAction)):
                # Discover unlock monster + compute required level, then push
                # everything into the blocker registry (which also persists
                # via the learning store when present).
                unlock_monster = self._bank_unlock_monster
                if unlock_monster is None:
                    match = _ACHIEVEMENT_CODE_RE.search(msg)
                    if match:
                        unlock_monster = self._resolve_bank_unlock_monster(client, match.group(1))
                required_level = 0
                if unlock_monster and self.game_data is not None:
                    required_level = max(0, self.game_data.monster_level(unlock_monster) - 1)
                char_level = self.state.level if self.state else 0
                self._blockers.mark_blocked(
                    "bank",
                    char_level=char_level,
                    unlock_monster=unlock_monster,
                    required_level=required_level,
                    store=self.history,
                )
                print(f"[{self._now()}] Bank locked (HTTP 496) — need level {required_level} "
                      f"to fight {unlock_monster or '?'}; remembered for future sessions")
                outcome = "error:bank_locked"
            elif msg.startswith("fight_lost"):
                print(f"[{self._now()}] Fight lost: {msg} — refreshing state")
                outcome = "error:fight_lost"
            elif "HTTP " in msg:
                # Pull the code out for finer-grained learning labels.
                http_match = re.search(r"HTTP (\d+)", msg)
                code = http_match.group(1) if http_match else "unknown"
                print(f"[{self._now()}] Action failed: {msg} — refreshing state")
                outcome = f"error:HTTP_{code}"
            else:
                print(f"[{self._now()}] Action failed: {msg} — refreshing state")
                outcome = "error:other"
            return self._fetch_world_state(client), outcome
        except httpx.HTTPError as e:
            # Transport-level failure (DNS, timeout, connection reset). Treat
            # as transient; refetch state (which also retries) and let the
            # next cycle replan with current truth.
            print(f"[{self._now()}] Network error during {action!r}: {e!r} — refreshing state")
            return self._fetch_world_state(client), "error:network"

    def _fetch_active_events(self, client: AuthenticatedClient) -> dict[str, datetime]:
        """Map of currently-active event code -> expiration. Empty on no/failed data."""
        active: dict[str, datetime] = {}
        page = 1
        while True:
            result = get_all_active_events(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for ev in result.data:
                active[ev.code] = ev.expiration
            if len(result.data) < 100:
                break
            page += 1
        return active

    def _fetch_world_state(self, client: AuthenticatedClient) -> WorldState:
        """Query character state from the API. Retries on transient errors."""
        last_result = None
        backoff = 5.0
        for attempt in range(1, 4):  # 3 attempts: immediate, +5s, +10s
            try:
                last_result = get_character(client=client, name=self.character)
            except httpx.HTTPError as e:
                last_result = None
                if attempt < 3:
                    print(f"[{self._now()}] get_character network error: {e!r}; retry {attempt}/3 in {backoff:.0f}s")
                    time.sleep(backoff)
                    backoff *= 2
                continue
            if (last_result is not None
                    and not isinstance(last_result, ErrorResponseSchema)
                    and hasattr(last_result, "data")
                    and last_result.data is not None):
                break
            if attempt < 3:
                code = "?"
                msg = ""
                if isinstance(last_result, ErrorResponseSchema):
                    code = str(last_result.error.code)
                    msg = last_result.error.message
                print(f"[{self._now()}] get_character returned HTTP {code} ({msg}); "
                      f"retry {attempt}/3 in {backoff:.0f}s")
                time.sleep(backoff)
                backoff *= 2

        if (last_result is None
                or isinstance(last_result, ErrorResponseSchema)
                or not hasattr(last_result, "data")
                or last_result.data is None):
            code = "?"
            msg = "no data"
            if isinstance(last_result, ErrorResponseSchema):
                code = str(last_result.error.code)
                msg = last_result.error.message
            raise RuntimeError(
                f"Could not fetch character '{self.character}' after 3 attempts "
                f"(last response: HTTP {code} - {msg}). "
                f"Verify the character exists at https://artifactsmmo.com/account and that "
                f"your API token belongs to the same account."
            )

        bank_items = self.state.bank_items if self.state else None
        bank_gold = self.state.bank_gold if self.state else None
        pending_items = self.state.pending_items if self.state else None
        active_events = self._fetch_active_events(client)
        state = WorldState.from_character_schema(
            last_result.data,
            bank_items=bank_items,
            bank_gold=bank_gold,
            pending_items=pending_items,
            active_events=active_events,
        )
        self._record_skill_observations(
            state,
            {skill: getattr(last_result.data, f"{skill}_max_xp", 0) for skill in state.skills},
        )
        return state

    def _sync_bank(self, client: AuthenticatedClient, state: WorldState) -> WorldState:
        """Re-fetch bank contents after a bank interaction."""
        bank_items: dict[str, int] = {}
        page = 1
        while True:
            result = get_bank_items(client=client, page=page, size=100)
            if result is None or not result.data:
                break
            for slot in result.data:
                bank_items[slot.code] = bank_items.get(slot.code, 0) + slot.quantity
            if len(result.data) < 100:
                break
            page += 1

        bank_gold: int | None = None
        details = get_bank_details(client=client)
        if details is not None and hasattr(details, "data") and details.data is not None:
            bank_gold = details.data.gold

        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=state.x,
            y=state.y,
            inventory=state.inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=state.cooldown_expires,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=bank_items,
            bank_gold=bank_gold,
            pending_items=state.pending_items,
            active_events=state.active_events,
        )

    def _sync_pending(self, client: AuthenticatedClient, state: WorldState) -> WorldState:
        """Re-fetch pending items after claiming one."""
        result = get_pending_items(client=client)
        pending: tuple[tuple[str, str], ...] | None = None
        if result is not None and result.data:
            pairs: list[tuple[str, str]] = []
            for pi in result.data:
                items = pi.items
                if isinstance(items, Unset) or not items:
                    continue
                for si in items:
                    pairs.append((pi.id, si.code))
            pending = tuple(pairs) if pairs else None
        return WorldState(
            character=state.character,
            level=state.level,
            xp=state.xp,
            max_xp=state.max_xp,
            hp=state.hp,
            max_hp=state.max_hp,
            gold=state.gold,
            skills=state.skills,
            x=state.x,
            y=state.y,
            inventory=state.inventory,
            inventory_max=state.inventory_max,
            equipment=state.equipment,
            cooldown_expires=state.cooldown_expires,
            task_code=state.task_code,
            task_type=state.task_type,
            task_progress=state.task_progress,
            task_total=state.task_total,
            bank_items=state.bank_items,
            bank_gold=state.bank_gold,
            pending_items=pending,
            active_events=state.active_events,
        )

    def _full_refresh(self, client: AuthenticatedClient) -> None:
        """Force a complete state refresh: character, bank, pending items."""
        self.state = self._fetch_world_state(client)
        if self.state is not None:
            self.state = self._sync_bank(client, self.state)
            self.state = self._sync_pending(client, self.state)
        self._actions_since_full_refresh = 0

    def _maybe_periodic_refresh(self, client: AuthenticatedClient) -> None:
        """Force a full refresh every 20 successful actions."""
        if self._actions_since_full_refresh >= 20:
            self._full_refresh(client)

    def _wait_for_cooldown(self) -> None:
        """Sleep until the character's cooldown expires."""
        if self.state is None or self.state.cooldown_expires is None:
            return
        now = datetime.now(tz=timezone.utc)
        remaining = (self.state.cooldown_expires - now).total_seconds()
        if remaining > 0:
            print(f"[{self._now()}] Cooldown: {remaining:.1f}s")
            time.sleep(remaining + 0.1)

    def _drop_stale_bank_lock(self) -> None:
        """Drop a persisted global "bank" lock when the world has an open bank.

        The lock is recorded after probing a gated bank (e.g. the
        achievement-gated desert-island bank returns HTTP 496 on approach), but
        open banks exist — so the global lock is bogus and would otherwise
        disable all banking for every future session."""
        if (
            self.history is not None
            and self._blockers.is_blocked("bank")
            and self.game_data is not None
            and self.game_data.has_open_bank()
        ):
            self._blockers.clear("bank")
            self.history.delete_blocker("bank")
            print(f"[{self._now()}] Cleared stale bank lock — an open bank is available")

    def _resolve_bank_unlock_monster(self, client: AuthenticatedClient, achievement_code: str) -> str | None:
        """Fetch the first combat_kill objective target for an achievement."""
        result = get_achievement(client=client, code=achievement_code)
        if result is None or not hasattr(result, "data") or result.data is None:
            return None
        for obj in result.data.objectives:
            if obj.type_ == AchievementType.COMBAT_KILL and obj.target:
                return str(obj.target)
        return None

    def _decrement_suppressions(self) -> None:
        """Decrement each suppression counter; prune zero entries."""
        self._suppressed_goals = {
            name: n - 1 for name, n in self._suppressed_goals.items() if n > 1
        }

    def _make_cycle_record(self, goal_name: str, action_name: str,
                           planned_depth: int, planner_timed_out: bool, succeeded: bool) -> CycleRecord:
        """Build a CycleRecord from current state and given action/goal info."""
        return CycleRecord(
            state_key=_state_key(self.state) if self.state else (),
            goal_name=goal_name,
            action_name=action_name,
            planned_depth=planned_depth,
            planner_timed_out=planner_timed_out,
            succeeded=succeeded,
        )

    def _emit_trace(self, action_name: str, goal_name: str, outcome: str,
                    planner_stats: dict[str, object], recovery: dict[str, object] | None = None) -> None:
        """Emit one per-cycle record to the tracer."""
        if self.state is None:
            return
        cooldown_remaining = 0.0
        if self.state.cooldown_expires is not None:
            cooldown_remaining = max(0.0,
                (self.state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds())
        record = {
            "ts": datetime.now(tz=timezone.utc).isoformat(),
            "cycle": self._cycle_counter,
            "state": {
                "x": self.state.x, "y": self.state.y,
                "hp": self.state.hp, "max_hp": self.state.max_hp,
                "gold": self.state.gold, "level": self.state.level,
                "inventory_used": self.state.inventory_used,
                "inventory_max": self.state.inventory_max,
                "bank_accessible": self._bank_accessible,
                "task_code": self.state.task_code, "task_type": self.state.task_type,
                "task_progress": self.state.task_progress, "task_total": self.state.task_total,
            },
            "cooldown_remaining_at_cycle_start": cooldown_remaining,
            "selected_goal": goal_name,
            "planner": planner_stats,
            "action": action_name,
            "outcome": outcome,
            "recovery": recovery,
            "suppressed_goals": list(self._suppressed_goals.keys()),
        }
        if self._strategy is not None and self.game_data is not None:
            record["strategy"] = self._strategy.decide(self.state, self.game_data).to_trace()
        self.tracer.write_cycle(record)
        self._cycle_counter += 1

    def _handle_stuck(self, signal: StuckSignal, client: AuthenticatedClient) -> None:
        """Apply recovery action for a stuck signal at its current escalation level."""
        level = self._recovery_level.get(signal, 0) + 1
        self._recovery_level[signal] = level

        if signal == StuckSignal.STATE_FROZEN:
            if level == 1:
                print(f"[{self._now()}] [recovery] STATE_FROZEN L1: forcing full refresh")
                self.state = self._fetch_world_state(client)
            elif level == 2:
                last = self._last_goal_name
                if last:
                    self._suppressed_goals[last] = 5
                    print(f"[{self._now()}] [recovery] STATE_FROZEN L2: suppressing {last} for 5 cycles")
            else:
                # L3 — broaden suppression on already-suppressed goals
                for name in list(self._suppressed_goals):
                    self._suppressed_goals[name] = max(self._suppressed_goals[name], 10)
                print(f"[{self._now()}] [recovery] STATE_FROZEN L3: broadened suppression to 10 cycles")

        elif signal == StuckSignal.GOAL_OSCILLATION:
            history = list(self._detector._history)[-8:]
            # Only suppress goals that were actually failing in the window. A
            # succeeded goal that merely appears in the oscillation window
            # (e.g. AcceptTask that fired once between TaskExchange retries)
            # is not the source of the loop. Also drop "<none>" — it's the
            # no-plan placeholder, not a real goal that can be suppressed.
            distinct = {
                r.goal_name for r in history
                if not r.succeeded and r.goal_name != "<none>"
            }
            if not distinct:
                # Nothing real to suppress; just clear the signal and let the
                # next cycle replan instead of escalating.
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION: no failing goals to suppress; clearing signal")
            elif level == 1:
                suppress_cycles = 5
                for name in distinct:
                    self._suppressed_goals[name] = suppress_cycles
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L1: suppressing {distinct} for 5 cycles")
            elif level == 2:
                suppress_cycles = 15
                for name in distinct:
                    self._suppressed_goals[name] = suppress_cycles
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L2: suppressing {distinct} for 15 cycles")
            else:
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L3: exiting (manual intervention)")
                raise SystemExit(2)

        elif signal == StuckSignal.NO_PROGRESS:
            if level == 1:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L1: forcing full refresh")
                self.state = self._fetch_world_state(client)
            elif level == 2:
                self._wildcard_mode = True
                print(f"[{self._now()}] [recovery] NO_PROGRESS L2: switching to wildcard goals")
            else:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L3: exiting (manual intervention)")
                raise SystemExit(2)

        self._detector.acknowledge(signal)

    def _build_actions(self) -> list[Action]:
        """Build the action list. Each action handles its own movement in execute() and cost()."""
        assert self.game_data is not None

        bank = self.game_data.bank_location()
        taskmaster = self.game_data.taskmaster_location()

        actions: list[Action] = [
            RestAction(),
            UseConsumableAction(_item_stats=self.game_data._item_stats),
            DepositAllAction(bank_location=bank, accessible=self._bank_accessible, game_data=self.game_data),
            AcceptTaskAction(taskmaster_location=taskmaster),
            CompleteTaskAction(taskmaster_location=taskmaster),
            TaskExchangeAction(taskmaster_location=taskmaster, min_coins=self._task_exchange_min_coins),
            TaskCancelAction(taskmaster_location=taskmaster),
            ClaimPendingItemAction(),
        ]

        # Fight and gather actions carry their own locations — no separate move actions needed
        for monster_code, locs in self.game_data._monster_locations.items():
            actions.append(FightAction(monster_code=monster_code, locations=frozenset(locs)))
            actions.append(OptimizeLoadoutAction(target_monster_code=monster_code, game_data=self.game_data))

        for resource_code, locs in self.game_data._resource_locations.items():
            actions.append(GatherAction(resource_code=resource_code, locations=frozenset(locs)))

        # Craft, equip, and withdraw actions carry workshop/bank locations
        materials_to_withdraw: dict[str, int] = {}
        for item_code, recipe in self.game_data._crafting_recipes.items():
            stats = self.game_data.item_stats(item_code)
            if stats is None:
                continue
            workshop_loc = self.game_data.workshop_location(stats.crafting_skill) if stats.crafting_skill else None
            actions.append(CraftAction(code=item_code, quantity=1, workshop_location=workshop_loc))
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                actions.append(EquipAction(code=item_code, slot=slot))
            if ITEM_TYPE_TO_SLOTS.get(stats.type_):
                # Allow withdrawing the crafted item from bank to equip it
                actions.append(WithdrawItemAction(
                    code=item_code, quantity=1, bank_location=bank, accessible=self._bank_accessible))
                for mat_code, mat_qty in recipe.items():
                    if mat_qty > materials_to_withdraw.get(mat_code, 0):
                        materials_to_withdraw[mat_code] = mat_qty

        for mat_code, mat_qty in materials_to_withdraw.items():
            actions.append(WithdrawItemAction(
                code=mat_code, quantity=mat_qty, bank_location=bank, accessible=self._bank_accessible))

        # Allow withdrawing task coins from bank for exchange
        actions.append(WithdrawItemAction(
            code="tasks_coin", quantity=1, bank_location=bank, accessible=self._bank_accessible))

        # Unequip actions: one per equipment slot
        all_slots = {slot for slots in ITEM_TYPE_TO_SLOTS.values() for slot in slots}
        for slot in all_slots:
            actions.append(UnequipAction(slot=slot))

        # Recycle actions: one per craftable equippable item
        for item_code, recipe in self.game_data._crafting_recipes.items():
            stats = self.game_data.item_stats(item_code)
            if stats is None or not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            workshop_loc = self.game_data.workshop_location(stats.crafting_skill) if stats.crafting_skill else None
            actions.append(RecycleAction(code=item_code, quantity=1, workshop_location=workshop_loc))

        # Delete actions: built from current inventory when bank is locked.
        # Cost weights: ingredient=50 (harsher), sellable=25, worthless=5 (cheaper to delete).
        if not self._bank_accessible and self.state is not None:
            equipped = set(self.state.equipment.values()) - {None}
            for item_code, qty in self.state.inventory.items():
                if qty <= 0 or item_code in equipped:
                    continue
                actions.append(DeleteItemAction(
                    code=item_code, quantity=1,
                    cost_weight=_delete_cost(item_code, self.game_data),
                ))

        # NPC buy actions: one per (npc, item) pair for consumables
        for npc_code, stock in self.game_data._npc_stock.items():
            npc_loc = self.game_data.npc_location(npc_code)
            for item_code in stock:
                item_stats = self.game_data.item_stats(item_code)
                if item_stats is not None and item_stats.hp_restore > 0:
                    actions.append(NpcBuyAction(
                        npc_code=npc_code,
                        item_code=item_code,
                        quantity=1,
                        npc_location=npc_loc,
                    ))

        # NPC sell actions: one per (npc, item) pair where the NPC buys the item
        for npc_code, sell_prices in self.game_data._npc_sell_prices.items():
            npc_loc = self.game_data.npc_location(npc_code)
            for item_code in sell_prices:
                actions.append(NpcSellAction(
                    npc_code=npc_code,
                    item_code=item_code,
                    quantity=1,
                    npc_location=npc_loc,
                ))

        # Phase B: bank expansion, transitions, gold management
        actions.append(BuyBankExpansionAction(bank_location=bank, accessible=self._bank_accessible))
        actions.append(MapTransitionAction())
        # Gold deposit/withdraw with typical small quantities; let planner decide
        for q in (50, 100, 500, 1000):
            actions.append(DepositGoldAction(quantity=q, bank_location=bank, accessible=self._bank_accessible))
            actions.append(WithdrawGoldAction(quantity=q, bank_location=bank, accessible=self._bank_accessible))
        # Task trade is built only when current task is items-type
        if self.state is not None and self.state.task_type == "items" and self.state.task_code:
            actions.append(TaskTradeAction(
                code=self.state.task_code,
                quantity=1,
                taskmaster_location=taskmaster,
            ))

        return actions

    def _build_goals(self) -> list[Goal]:
        """Build goal list. FarmMonsterGoal targets the strongest monster the character can beat."""
        assert self.game_data is not None
        assert self.state is not None

        if self._wildcard_mode:
            # Wildcard mode: only the safest goals
            self._wildcard_mode = False  # one-shot
            return [RestoreHPGoal()]

        # Periodically retry bank access after an achievement gate failure (HTTP 496),
        # but only if there's a reasonable chance the unlock actually happened
        # since the last attempt — i.e. character has gained at least one level.
        # Otherwise the flap creates a wasteful Deposit→496→UnlockBank→Deposit loop.
        if not self._bank_accessible and self._bank_blocked_since is not None:
            if (time.monotonic() - self._bank_blocked_since >= _BANK_RETRY_SECONDS
                    and self.state is not None
                    and self.state.level > self._bank_blocked_at_level):
                self._blockers.clear("bank")

        # G-I: under max-level root objective, the cheapest-path projection
        # picks the next monster. The projection maximizes XP/cycle but does NOT
        # consider winnability, so gate it: if the path-aligned pick isn't
        # winnable (or there is no projection), fall back to the conservative
        # winnable picker. When that also yields None, no combat grind is built.
        farm_target = self._path_aligned_monster()
        if farm_target is None or not self._is_winnable(farm_target):
            farm_target = self._pick_winnable_monster()

        # Resolve a STABLE upgrade target. Recomputing the best craftable
        # upgrade every cycle let a transient inventory change flip the target
        # (e.g. wooden_shield → fishing_net) mid-gather, so UpgradeEquipment
        # would craft a different equippable than GatherMaterials was gathering
        # for. Persist the target until it is equipped or stops being an
        # upgrade, and feed the SAME target to both goals.
        probe = UpgradeEquipmentGoal(initial_equipment=self.state.equipment)
        committed = self._committed_upgrade_target
        if committed is not None and not self._upgrade_target_still_valid(probe, committed):
            committed = None
        if committed is None:
            committed = probe.find_upgrade_target(self.state, self.game_data)
        self._committed_upgrade_target = committed
        # Expose the committed crafting target on the state so every consumer of
        # active_gathering_skills (tool relevance, gating-XP, scalarizer) counts
        # the skills the bot gathers for this self-directed craft — e.g. mining
        # copper ore for copper gear marks mining active so a pickaxe is built.
        self.state = replace(
            self.state, crafting_target=committed[0] if committed else None
        )

        goals: list[Goal] = [
            RestoreHPGoal(),
            DepositInventoryGoal(bank_accessible=self._bank_accessible, game_data=self.game_data),
            SellInventoryGoal(bank_accessible=self._bank_accessible),
            ExpandBankGoal(bank_accessible=self._bank_accessible, game_data=self.game_data),
            UnlockBankGoal(bank_locked=not self._bank_accessible, initial_xp=self.state.xp,
                           target_monster=self._bank_unlock_monster),
            ClaimPendingGoal(),
            CompleteTaskGoal(),
            AcceptTaskGoal(),
            TaskExchangeGoal(min_coins=self._task_exchange_min_coins),
            TaskCancelGoal(),
            LowYieldCancelGoal(),
            # If a remembered blocker requires a higher character level than
            # we have, drive the grind to reach it before continuing
            # business-as-usual. Self-disables once level is reached.
            ReachUnlockLevelGoal(target_level=self._bank_required_level),
            DiscardOverstockGoal(game_data=self.game_data),
        ]
        # Tier-3 strategy drives progression: map its chosen step to a goal at a
        # fixed band (replaces the old FarmMonster/GrindXP/UpgradeEquipment/
        # GatherMaterials/LevelSkill/FarmItems goals). A low-priority grind is the
        # safety net so the bot always has a plannable action if the step can't
        # plan. Survival/economy/task goals above retain their priorities and
        # still preempt when urgent.
        decision = self._strategy.decide(self.state, self.game_data) if self._strategy else None
        step = decision.chosen_step if decision is not None else None
        strat = strategy_goal(step, self.state, self.game_data, STRATEGY_BAND, farm_target)
        if strat is not None:
            goals.append(strat)
        if farm_target is not None:
            goals.append(MetaGoalAdapter(
                GrindCharacterXPGoal(target_monster=farm_target, initial_xp=self.state.xp),
                FALLBACK_BAND))

        return [g for g in goals if repr(g) == "TaskCancel" or repr(g) not in self._suppressed_goals]

    def _notify_observer(
        self,
        selected_goal_name: str,
        action_name: str,
        outcome: str,
        goal_rank_trace: list[dict[str, Any]],
        planner_stats: dict[str, object] | None = None,
    ) -> None:
        """Build a CycleSnapshot and hand it to the observer (TUI host).

        ``planner_stats`` carries the same trace internals emitted to the file
        tracer so the log modal can show trace-level detail; when omitted the
        planner fields fall back to their snapshot defaults."""
        if self._cycle_observer is None or self.state is None:
            return
        stats: dict[str, Any] = dict(planner_stats or {})
        raw_attempts = stats.get("goals_tried", [])
        attempts = raw_attempts if isinstance(raw_attempts, list) else []
        goals_tried = [
            GoalAttempt(
                goal=str(g["goal"]), nodes=int(g["nodes"]), depth=int(g["depth"]),
                timed_out=bool(g["timed_out"]), plan_len=int(g["plan_len"]),
            )
            for g in attempts
        ]
        plan = self._last_path_plan
        # Cooldown remaining at snapshot time (post-action; the server-set
        # cooldown the bot will wait through before the next cycle).
        cooldown_remaining = 0.0
        if self.state.cooldown_expires is not None:
            cooldown_remaining = max(
                0.0,
                (self.state.cooldown_expires - datetime.now(tz=timezone.utc)).total_seconds(),
            )
        snap = CycleSnapshot(
            cycle_index=self._cycle_counter,
            timestamp=datetime.now(tz=timezone.utc).isoformat(),
            character=self.character,
            x=self.state.x, y=self.state.y,
            level=self.state.level, xp=self.state.xp, max_xp=self.state.max_xp,
            hp=self.state.hp, max_hp=self.state.max_hp,
            gold=self.state.gold,
            inventory=dict(self.state.inventory),
            inventory_max=self.state.inventory_max,
            equipment=dict(self.state.equipment),
            skills=dict(self.state.skills),
            skill_xp=dict(self.state.skill_xp),
            task_code=self.state.task_code,
            task_type=self.state.task_type,
            task_progress=self.state.task_progress,
            task_total=self.state.task_total,
            cooldown_remaining=cooldown_remaining,
            selected_goal=selected_goal_name,
            action=action_name,
            outcome=outcome,
            goal_rank=[GoalRankEntry(goal=str(e["goal"]), priority=float(e["priority"]))
                       for e in goal_rank_trace],
            path_next_action=plan.next_action_monster if plan else None,
            projected_cycles_to_max=(
                plan.total_cycles if plan and plan.total_cycles != float("inf") else None
            ),
            max_level=self.game_data.max_character_level if self.game_data else 0,
            remaining_levels=max(
                0, (self.game_data.max_character_level if self.game_data else 0) - self.state.level,
            ),
            planner_nodes=int(stats.get("nodes", 0)),
            planner_depth=int(stats.get("depth", 0)),
            planner_timed_out=bool(stats.get("timed_out", False)),
            plan_len=int(stats.get("plan_len", 0)),
            goals_tried=goals_tried,
            suppressed_goals=list(self._suppressed_goals.keys()),
            path_blocked=bool(stats.get("path_blocked", False)),
        )
        self._cycle_observer(snap)

    def _path_trace_snapshot(self) -> dict[str, object]:
        """G-I: small dict of root-objective state to merge into trace records."""
        max_lvl = self.game_data.max_character_level if self.game_data else 0
        cur_lvl = self.state.level if self.state else 0
        snapshot: dict[str, object] = {
            "max_level": max_lvl,
            "remaining_levels": max(0, max_lvl - cur_lvl),
        }
        plan = self._last_path_plan
        if plan is not None:
            snapshot["projected_cycles_to_max"] = (
                round(plan.total_cycles, 1) if plan.total_cycles != float("inf") else "inf"
            )
            snapshot["path_next_action"] = plan.next_action_monster
            snapshot["path_blocked"] = plan.blocked
        return snapshot

    def _path_aligned_monster(self) -> str | None:
        """Return the next-monster recommendation from the cheapest-path
        projection to max character level, or None if no path or no store.

        G-I: this replaces win-rate-based picking when the projection is
        usable. The projection uses observed char_xp/cycle (or the
        documented XP formula) to pick the monster that maximizes
        progression per cycle — which is exactly what the max-level root
        objective wants.
        """
        if self.history is None or self.game_data is None or self.state is None:
            return None
        plan = cheapest_path_to_level(
            self.game_data.max_character_level, self.state, self.history, self.game_data,
        )
        # Cache for trace exposure later in the cycle.
        self._last_path_plan = plan
        # Even when path is blocked at some later level, the FIRST segment
        # is a valid immediate-next action — the bot can keep grinding it
        # until either (a) a new monster opens up after a level-up or
        # (b) UpgradeEquipment / other goals unblock further progression.
        if not plan.segments:
            return None
        return plan.next_action_monster

    def _upgrade_target_still_valid(self, probe: UpgradeEquipmentGoal,
                                    target: tuple[str, str]) -> bool:
        """True if the persisted upgrade target is still worth pursuing.

        Invalid (→ recompute) when the target item is already equipped in its
        slot (we got it), or it is no longer an upgrade over whatever now
        occupies the slot.
        """
        assert self.state is not None and self.game_data is not None
        item_code, slot = target
        if self.state.equipment.get(slot) == item_code:
            return False
        stats = self.game_data.item_stats(item_code)
        if stats is None:
            return False
        current = self.state.equipment.get(slot)
        current_stats = self.game_data.item_stats(current) if current else None
        active = frozenset(self.game_data.active_gathering_skills(self.state.task_code, self.state.crafting_target))
        return probe._is_upgrade_over(item_code, stats, current, current_stats,
                                      self.game_data, active)

    def _is_winnable(self, monster_code: str) -> bool:
        """True when the documented combat-stat prediction says we win AND we
        have not been observed losing this monster (>= MIN_WIN_SAMPLES fights
        under WIN_RATE_THRESHOLD). The learned-loss veto overrides an optimistic
        stat prediction; a cold/absent history defers to the prediction."""
        assert self.state is not None and self.game_data is not None
        if self.history is not None:
            # Gate on our own sample threshold (not success_rate's internal
            # small-sample guard) so the veto fires only on a well-observed loss
            # record; short-circuit avoids the success_rate query when too few.
            samples = self.history.sample_count(f"Fight({monster_code})")
            if (samples >= MIN_WIN_SAMPLES
                    and self.history.success_rate(f"Fight({monster_code})") < WIN_RATE_THRESHOLD):
                return False
        return predict_win(self.state, self.game_data, monster_code)

    def _pick_winnable_monster(self) -> str | None:
        """Highest-level monster that `_is_winnable` (stat prediction not vetoed
        by observed losses). Returns None when no monster is winnable, so the
        caller can suppress combat-driving goals and let upgrade goals dominate.

        No level cap: predict_win's stat math is the gate (the win-rate veto
        corrects any monster the formula over-rates once losses accumulate)."""
        assert self.game_data is not None
        assert self.state is not None
        best: tuple[str, int] | None = None
        for code, level in self.game_data._monster_level.items():
            if not self._is_winnable(code):
                continue
            if best is None or level > best[1]:
                best = (code, level)
        return best[0] if best is not None else None

    def _gating_skill_targets(self, active_skills: set[str]) -> list[tuple[str, int]]:
        """Find (gating_skill, required_level) pairs for craftable items that:
        - apply to a slot (i.e. equipable upgrade)
        - have a positive skill_effect for one of `active_skills`
        - require a gating crafting_skill level Robby hasn't reached

        Phase G-E: enables LevelSkillGoal to pivot to skill grinding when a
        relevant tool is one or two skill levels away.
        """
        assert self.state is not None
        assert self.game_data is not None
        result: list[tuple[str, int]] = []
        seen: set[tuple[str, int]] = set()
        for code, _ in self.game_data._crafting_recipes.items():
            stats = self.game_data.item_stats(code)
            if stats is None or not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            if not any(s in active_skills for s in stats.skill_effects):
                continue
            cskill = stats.crafting_skill
            if not cskill:
                continue
            current = self.state.skills.get(cskill, 0)
            if current >= stats.crafting_level:
                continue  # already qualified
            key = (cskill, stats.crafting_level)
            if key in seen:
                continue
            seen.add(key)
            result.append(key)
        return result

    def _log_action(self, action: Action, goal: Goal, plan: list[Action]) -> None:
        assert self.state is not None
        suffix = f"  [{_format_plan(plan[1:])}]" if len(plan) > 1 else ""
        print(f"[{self._now()}] → {action!r}{suffix}  (goal: {goal!r})")

    def _select_goal(
        self,
        state: WorldState,
        game_data: GameData,
        actions: list[Action],
        goal_priorities: list[tuple[Goal, float]],
    ) -> tuple[Goal | None, list[Action], list[dict[str, object]]]:
        """Choose the goal to pursue this cycle with sticky commitment.

        Order of precedence:
        1. Preemption — a preemptive goal (HP-critical) that outranks the
           committed goal's current priority interrupts the commitment.
        2. Stick — keep the committed goal while it still has positive priority,
           is not satisfied, and yields a plan. This stops the per-cycle goal
           thrashing where near-equal priorities flip the selection every cycle.
        3. Reselect — otherwise pick the highest-priority plannable goal and
           commit to it.

        Returns (selected_goal, plan, goals_tried). goals_tried records the
        planner attempts for the trace, exactly as the old inline loop did.
        """
        goals_tried: list[dict[str, object]] = []

        def attempt(goal: Goal) -> list[Action]:
            plan = self.planner.plan(state, goal, actions, game_data, self.history)
            s = self.planner.last_stats
            goals_tried.append({
                "goal": repr(goal),
                "nodes": s.nodes_explored,
                "depth": s.max_depth_reached,
                "timed_out": s.timed_out,
                "plan_len": len(plan),
            })
            if self.verbose and not plan:
                print(f"[{self._now()}]   No plan for {goal}: nodes={s.nodes_explored} "
                      f"depth={s.max_depth_reached} timeout={s.timed_out}")
            return plan

        committed_priority = -float("inf")
        if self._committed_goal_name is not None:
            for goal, priority in goal_priorities:
                if repr(goal) == self._committed_goal_name:
                    committed_priority = priority
                    break

        # 1. Preemption: a safety goal that outranks the commitment interrupts it.
        if self._committed_goal_name is not None:
            for goal, priority in goal_priorities:
                if priority <= 0:
                    break
                if goal.preemptive and priority > committed_priority and repr(goal) != self._committed_goal_name:
                    plan = attempt(goal)
                    if plan:
                        self._committed_goal_name = repr(goal)
                        return goal, plan, goals_tried

        # 2. Stick with the committed goal while it remains viable.
        if self._committed_goal_name is not None:
            for goal, priority in goal_priorities:
                if repr(goal) != self._committed_goal_name:
                    continue
                if priority > 0 and not goal.is_satisfied(state):
                    plan = attempt(goal)
                    if plan:
                        return goal, plan, goals_tried
                break  # committed goal present but not viable — fall through

        # 3. Reselect: highest-priority plannable goal; commit to it.
        for goal, priority in goal_priorities:
            if priority <= 0:
                break
            plan = attempt(goal)
            if plan:
                self._committed_goal_name = repr(goal)
                return goal, plan, goals_tried

        self._committed_goal_name = None
        return None, [], goals_tried

    def _learn_task_exchange_cost(self, action: Action, prev_state: WorldState,
                                  new_state: WorldState, outcome: str) -> None:
        """Discover the taskmaster exchange cost from outcomes — never hardcoded.

        The API does not expose the per-exchange coin cost as data. HTTP 478
        ("missing items") means the coin count we tried was too low, so raise the
        minimum past it. A success reveals the exact cost via the coin delta, so
        pin the minimum to that.
        """
        if not isinstance(action, TaskExchangeAction):
            return
        before = prev_state.inventory.get("tasks_coin", 0)
        if outcome == "error:HTTP_478":
            self._task_exchange_min_coins = max(self._task_exchange_min_coins, before + 1)
        elif outcome == "ok":
            spent = before - new_state.inventory.get("tasks_coin", 0)
            if spent > 0:
                self._task_exchange_min_coins = spent

    def _record_skill_observations(self, state: WorldState, skill_max_xp: dict[str, int]) -> None:
        """Persist observed XP-to-next-level for each skill at its current level."""
        if self.history is None:
            return
        for skill, level in state.skills.items():
            max_xp = skill_max_xp.get(skill, 0)
            if isinstance(max_xp, int) and max_xp > 0:
                self.history.record_skill_max_xp(skill, level, max_xp)

    def _record_task_reward_if_completed(self, prev_state: WorldState, new_state: WorldState,
                                         action_class: str, outcome: str) -> None:
        """On task completion, record the sell-back gold value of the reward
        items received so the mean reward estimate improves over time."""
        if (self.history is None or self.game_data is None
                or outcome != "ok" or action_class != "CompleteTaskAction"):
            return
        prices = _max_sell_back_price(self.game_data)
        value = 0.0
        for code, qty in new_state.inventory.items():
            gained = qty - prev_state.inventory.get(code, 0)
            if gained > 0:
                value += gained * prices.get(code, 0)
        self.history.record_task_reward_value(value)

    def _note_goal_selection(self, goal_repr: str, cycle_index: int) -> None:
        """Record when a goal was first selected. Idempotent on re-selection."""
        if goal_repr not in self._goal_first_selected_at:
            self._goal_first_selected_at[goal_repr] = cycle_index

    def _compute_cycles_to_satisfy(self, goal_repr: str, current_cycle: int) -> int | None:
        """Return cycles since first selection, then clear. None if never selected."""
        first = self._goal_first_selected_at.pop(goal_repr, None)
        if first is None:
            return None
        return current_cycle - first

    def _record_learning_cycle(
        self,
        prev_state: WorldState,
        new_state: WorldState,
        action_repr: str,
        action_class: str,
        outcome: str,
        selected_goal: str,
        predicted_cost: float,
        actual_cooldown_seconds: float,
        planner_nodes: int,
        planner_depth: int,
        planner_timed_out: bool,
        plan_len: int,
        cycles_to_satisfy: int | None = None,
    ) -> None:
        """Build a Cycle row and persist via LearningStore. No-op when history is None."""
        if self.history is None:
            return
        drops = self._compute_drops(prev_state, new_state)
        # Per-skill XP delta. Sparse: only skills whose XP changed appear.
        # Phase G-B projections read this column to attribute skill-XP yield
        # per cycle, separately from character XP (delta_xp).
        skill_deltas: dict[str, int] = {}
        for skill_name, new_xp in new_state.skill_xp.items():
            prev_xp = prev_state.skill_xp.get(skill_name, 0)
            if new_xp != prev_xp:
                skill_deltas[skill_name] = new_xp - prev_xp
        cycle = Cycle(
            ts=datetime.now(tz=timezone.utc).isoformat(),
            session_id="placeholder",
            cycle_index=getattr(self, "_cycle_counter", 0),
            character=self.character,
            x=new_state.x, y=new_state.y,
            hp=new_state.hp, max_hp=new_state.max_hp,
            gold=new_state.gold, level=new_state.level, xp=new_state.xp,
            inventory_used=new_state.inventory_used,
            inventory_max=new_state.inventory_max,
            bank_accessible=self._bank_accessible,
            task_code=new_state.task_code, task_type=new_state.task_type,
            task_progress=new_state.task_progress, task_total=new_state.task_total,
            selected_goal=selected_goal,
            action_repr=action_repr,
            action_class=action_class,
            outcome=outcome,
            predicted_cost=predicted_cost,
            actual_cooldown_seconds=actual_cooldown_seconds,
            planner_nodes=planner_nodes, planner_depth=planner_depth,
            planner_timed_out=planner_timed_out, plan_len=plan_len,
            delta_gold=new_state.gold - prev_state.gold,
            delta_xp=new_state.xp - prev_state.xp,
            delta_hp=new_state.hp - prev_state.hp,
            delta_inv_used=new_state.inventory_used - prev_state.inventory_used,
            drops_json=json.dumps(drops, ensure_ascii=False) if drops else None,
            delta_skill_xp_json=json.dumps(skill_deltas, ensure_ascii=False, sort_keys=True),
            cycles_to_satisfy=cycles_to_satisfy,
        )
        self.history.record_cycle(cycle)

    @staticmethod
    def _compute_drops(prev_state: WorldState, new_state: WorldState) -> dict[str, int]:
        """Items that appeared (positive deltas only)."""
        drops: dict[str, int] = {}
        for code, qty in new_state.inventory.items():
            prev_qty = prev_state.inventory.get(code, 0)
            if qty > prev_qty:
                drops[code] = qty - prev_qty
        return drops

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%H:%M:%S")
