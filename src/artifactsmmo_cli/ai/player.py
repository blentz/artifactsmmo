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

from artifactsmmo_cli.ai.actions.api_action_error import ApiActionError
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.blockers import BlockerRegistry, seed_documented_blockers
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
from artifactsmmo_cli.ai.constants import (
    BANK_REFRESH_FORCE_SENTINEL,
    BANK_REFRESH_INTERVAL,
    ERROR_CODE_ALREADY_EQUIPPED,
    ERROR_CODE_COOLDOWN,
    STUCK_DETECTOR_WINDOW,
)
from artifactsmmo_cli.ai.action_kind import action_kind_of
from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, GoalAttempt, GoalRankEntry, RootScoreView
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_latch import GearLatch
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.projections import PathPlan, cheapest_path_to_level
from artifactsmmo_cli.ai.learning.scalarizer import _max_sell_back_price
from artifactsmmo_cli.ai.learning.skill_xp_curve import SkillXpCurve
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.planner import GOAPPlanner, _state_key
from artifactsmmo_cli.ai.player_helpers import delete_cost as _delete_cost  # noqa: F401  (test import target)
from artifactsmmo_cli.ai.player_helpers import format_plan as _format_plan
from artifactsmmo_cli.ai.recovery import (
    SIGNAL_WINDOWS,
    CycleRecord,
    StuckDetector,
    StuckExit,
    StuckSignal,
)
from artifactsmmo_cli.ai.strategy_driver import (
    StrategyArbiter,
    monster_drop_inputs,
    objective_step_goal,
)
from artifactsmmo_cli.ai.task_decision import PURSUE, task_decision
from artifactsmmo_cli.ai.tiers import (
    BalancedPersonality,
    CharacterObjective,
    ObtainItem,
    StrategyDecision,
    StrategyEngine,
)
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.plan_report import PlanReport
from artifactsmmo_cli.ai.should_replan import should_replan
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import MetaGoal
from artifactsmmo_cli.ai.tiers.root_progress import root_progress_value
from artifactsmmo_cli.ai.tiers.sticky_select_core import next_last
from artifactsmmo_cli.ai.tracer import Tracer
from artifactsmmo_cli.ai.winnable_cascade import CascadeInputs, winnable_farm_target_pure
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState
from artifactsmmo_cli.client_manager import ClientManager

_BANK_RETRY_SECONDS = 60.0  # retry bank access this long after an HTTP 496 block
_ACHIEVEMENT_CODE_RE = re.compile(r"\((\w+) achievement_unlocked")
_BANK_TILE = None  # resolved from game_data at runtime


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
        game_data_ttl_minutes: int = 30,
        refresh_game_data: bool = False,
    ) -> None:
        self.character = character
        self.verbose = verbose
        self.dry_run = dry_run
        self._game_data_ttl_minutes = game_data_ttl_minutes
        self._refresh_game_data = refresh_game_data
        self.planner = GOAPPlanner()
        self._arbiter = StrategyArbiter(self.planner, history)
        self._last_decision: StrategyDecision | None = None
        self.state: WorldState | None = None
        self.game_data: GameData | None = None
        # Generic blocker registry — replaces what used to be ~5 bank-specific
        # player fields. New gates (workshop, taskmaster, transitions) plug in
        # by adding a code to this registry instead of growing player.
        self._blockers = BlockerRegistry()
        self._detector = StuckDetector(history_size=STUCK_DETECTOR_WINDOW)
        self._suppressed_goals: dict[str, int] = {}
        self._actions_since_full_refresh: int = 0
        self._recovery_level: dict[StuckSignal, int] = {}
        # Escalation decay bookkeeping (see _record_cycle/_handle_stuck): per
        # signal, the current and the maximum run of CONSECUTIVE
        # counter-evidence cycles observed since that signal last fired. When
        # the max run reaches the signal's own detection window, prior
        # escalation history is stale and resets (trace 2026-06-10: 67
        # productive cycles between L2 and L3 bought nothing; L3 then exited).
        self._healthy_streak: dict[StuckSignal, int] = {s: 0 for s in StuckSignal}
        self._max_healthy_streak: dict[StuckSignal, int] = {s: 0 for s in StuckSignal}
        self._prev_cycle_state_key: tuple[object, ...] | None = None
        self._last_goal_name: str | None = None
        self.tracer: Tracer = tracer or NullTracer()
        self._cycle_counter: int = 0
        # Tier-3 strategy engine (built after game-data load); P3a runs it in
        # shadow — its decision is traced each cycle but does not drive the bot.
        self._objective: CharacterObjective | None = None
        self._strategy: StrategyEngine | None = None
        # Tier-2 sticky commitment: previous cycle's chosen_root repr.
        # Threaded into StrategyEngine.decide so a transient flip in
        # is_reachable (e.g. combat_capable=False for one cycle from a
        # pick_loadout shift) doesn't demote the active objective.
        self._last_strategy_root: str | None = None
        # Progress-gated sticky release (2026-06-20): the committed root's progress
        # value recorded last cycle. The anchor is re-fed only when this cycle's value
        # strictly exceeds it (the root advanced on its own axis). Replaces the broken
        # `chosen_step_alive` gate that re-committed a never-executing zombie grind
        # forever (weaponcrafting 1028-cycle hold). See
        # Formal/Liveness/StickySelect.lean + docs/PLAN_zombie_progress_gate.md.
        self._sticky_progress_value: int | None = None
        # Per-cycle servable-filter diagnostic (2026-06-20): whether the committed
        # chosen_root's step is plannable now. Emitted in the trace so a live run can
        # confirm the filter demotes unservable top roots (feather_coat) instead of
        # committing to them while char-grinding. See _step_servable / servable_filter.
        self._last_servability_diag: dict[str, object] = {}
        # Learned minimum tasks_coin worth attempting a taskmaster exchange. The
        # API does not expose the per-exchange cost as data, so we discover it
        # from HTTP 478 ("missing items") failures: raise the bound past any coin
        # count that failed, and pin it to the exact cost once an exchange
        # succeeds. Persisted via history.set_learned_int so a restart doesn't
        # re-pay the discovery climb (trace 2026-05/06: 42 HTTP 478s across
        # ~10 sessions = ~4 rejections per re-discovery).
        self._task_exchange_min_coins: int = (
            history.get_learned_int("task_exchange_min_coins", 1)
            if history is not None else 1
        )
        self._goal_first_selected_at: dict[str, int] = {}
        self.history = history
        self._last_path_plan: PathPlan | None = None
        self._cycle_observer = cycle_observer
        self._planning_observer: Callable[[bool], None] | None = None
        # Event-driven gear prioritization: the latch (set on level-up or a
        # predicted-winnable fight loss, cleared when gear is level-appropriate)
        # is updated once per cycle BEFORE selection and read into the
        # SelectionContext to fire the GEAR_REVIEW guard.
        self._gear_latch = GearLatch()
        self._prev_level: int | None = None
        self._last_outcome: str | None = None
        self._plan_cache: PlanCache | None = None
        self._last_decide_crafting_target: str | None = None

    def set_cycle_observer(self, observer: "Callable[[CycleSnapshot], None] | None") -> None:
        """Allow callers (e.g. TUI host) to subscribe after construction."""
        self._cycle_observer = observer

    def set_planning_observer(self, observer: "Callable[[bool], None] | None") -> None:
        self._planning_observer = observer

    def _notify_planning(self, active: bool) -> None:
        if self._planning_observer is not None:
            self._planning_observer(active)

    def _decide_band(
        self,
        state: "WorldState",
        game_data: GameData,
        actions: "list[Action]",
        ctx_combat_monster: "str | None",
    ) -> "tuple[Goal | None, list[Action], list[Any]]":
        """Run the full Tier-3 decision + GOAP selection. The expensive band —
        invoked only when should_replan is True. Returns (selected_goal, plan,
        goals_tried). Side effects (sticky anchor, crafting_target on state) match
        the pre-extraction loop body."""
        assert self._strategy is not None
        combat_monster = ctx_combat_monster
        ctx = self._selection_context(combat_monster)
        servable_pred = self._step_servable(state, game_data, ctx)
        self._notify_planning(True)
        decision = self._strategy.decide(
            state, game_data,
            history=self.history,
            combat_monster=combat_monster,
            last_chosen_root=self._last_strategy_root,
            step_servable=servable_pred,
        )
        self._last_decision = decision
        cr, cs = decision.chosen_root, decision.chosen_step
        self._last_servability_diag = {
            "chosen_root_servable": bool(
                cr is not None and cs is not None and servable_pred(cr, cs)),
            "chosen_root": repr(cr) if cr is not None else None,
        }
        step = decision.chosen_step
        crafting_target = step.code if isinstance(step, ObtainItem) else None
        if crafting_target is None:
            for alt in getattr(decision, "fallback_steps", []):
                if isinstance(alt, ObtainItem):
                    crafting_target = alt.code
                    break
        self.state = state = replace(state, crafting_target=crafting_target)
        selected_goal, plan, goals_tried = self._arbiter.select(
            decision, state, game_data, actions, ctx,
            suppressed=set(self._suppressed_goals),
            objective=self._objective,
        )
        self._update_sticky_anchor(
            decision.chosen_root, state, game_data, self._arbiter.chosen_step_alive)
        self._last_decide_crafting_target = crafting_target
        return selected_goal, plan, goals_tried

    def _plan_or_reuse(
        self,
        state: "WorldState",
        game_data: GameData,
        actions: "list[Action]",
        ctx_combat_monster: "str | None",
    ) -> "tuple[Goal | None, list[Action], list[Any], bool]":
        """Reuse the cached plan unless should_replan fires. Returns
        (selected_goal, plan, goals_tried, replanned)."""
        cache = self._plan_cache
        step = cache.current() if cache is not None else None
        goal_satisfied = cache is not None and cache.selected_goal.is_satisfied(state)
        step_applicable = step is not None and step.is_applicable(state, game_data)
        if should_replan(
            cache, self._last_outcome, self._gear_latch.active,
            goal_satisfied, step_applicable, BANK_REFRESH_INTERVAL,
        ):
            selected_goal, plan, goals_tried = self._decide_band(
                state, game_data, actions, ctx_combat_monster)
            if plan and selected_goal is not None:
                self._plan_cache = PlanCache(
                    selected_goal=selected_goal,
                    plan=list(plan),
                    crafting_target=self._last_decide_crafting_target,
                    latch_active=self._gear_latch.active,
                    goal_repr=repr(selected_goal),
                )
            else:
                self._plan_cache = None
            return selected_goal, plan, goals_tried, True
        # cache hit
        assert cache is not None
        self.state = replace(state, crafting_target=cache.crafting_target)
        self._notify_planning(False)
        return cache.selected_goal, cache.plan[cache.cursor:], [], False

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

    def _initialize(self, client: AuthenticatedClient) -> None:
        """Load game data, build the strategy engine, fetch state, and seed blocker
        memory + the cycle-0 full-bank-refresh sentinel. Shared by `run()` and the
        one-shot `plan_once()` so both sense the world identically before planning."""
        print(f"[{self._now()}] Loading game data...")
        self.game_data = GameData.load(
            client,
            ttl_minutes=self._game_data_ttl_minutes,
            force_refresh=self._refresh_game_data,
        )
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

        # Seed the refresh counter so the FIRST loop cycle forces a full bank
        # load (via `_maybe_periodic_refresh` → `_full_refresh`) BEFORE the first
        # plan. `_fetch_world_state` carries `bank_items` from the prior state
        # (None on cycle 0) and the periodic full refresh otherwise only fires
        # every BANK_REFRESH_INTERVAL actions — so without this the planner
        # sees an EMPTY bank for ~20 cycles and re-gathers materials already
        # banked (the bank-aware regather penalty / shopping_list credit /
        # withdraw applicability are all inert when `bank_items` is None). Any
        # value at/above the periodic threshold triggers the refresh on cycle 0.
        self._actions_since_full_refresh = BANK_REFRESH_FORCE_SENTINEL

    def plan_once(self) -> PlanReport:
        """Sense the world and compute ONE planning cycle WITHOUT executing — the
        `plan` CLI command. Mirrors run()'s per-cycle decide+select (same refresh,
        gear-latch, combat target, servable filter, crafting-target keep-set) so the
        printed plan is exactly what the bot would do this cycle. No cooldown wait, no
        action execution, no state mutation on the server."""
        client = ClientManager().client
        self._initialize(client)
        self._maybe_periodic_refresh(client)
        assert self.state is not None and self.game_data is not None
        assert self._strategy is not None
        state = self.state
        game_data = self.game_data
        self._maybe_retry_bank()
        prev = self._prev_level if self._prev_level is not None else state.level
        self._gear_latch.update(prev, state, self._last_outcome, game_data)
        self._prev_level = state.level
        self._arbiter.set_cycle(self._cycle_counter)
        combat_monster = self._winnable_farm_target()
        ctx = self._selection_context(combat_monster)
        decision = self._strategy.decide(
            state, game_data, history=self.history, combat_monster=combat_monster,
            last_chosen_root=self._last_strategy_root,
            step_servable=self._step_servable(state, game_data, ctx))
        step = decision.chosen_step
        crafting_target = step.code if isinstance(step, ObtainItem) else None
        if crafting_target is None:
            for alt in getattr(decision, "fallback_steps", []):
                if isinstance(alt, ObtainItem):
                    crafting_target = alt.code
                    break
        self.state = state = replace(state, crafting_target=crafting_target)
        actions = self._build_actions()
        selected_goal, plan, goals_tried = self._arbiter.select(
            decision, state, game_data, actions, ctx,
            suppressed=set(self._suppressed_goals), objective=self._objective)
        # For the chosen objective's recipe, report each monster-drop input's live
        # winnability — an unwinnable drop (e.g. chicken too strong) makes the gear
        # unbuildable, which is the difference between "hunts chickens" and "can't".
        drop_inputs: list[dict[str, object]] = []
        root = decision.chosen_root
        if isinstance(root, ObtainItem):
            for leaf in monster_drop_inputs(root.code, game_data):
                droppers = [m for m, *_ in game_data.monsters_dropping(leaf)]
                winnable = sorted(
                    m for m in droppers
                    if is_winnable(state, game_data, m, self.history)
                    and game_data.monster_locations(m))
                drop_inputs.append({"item": leaf, "droppers": sorted(droppers),
                                    "winnable": winnable})
        return PlanReport(decision=decision, selected_goal=selected_goal,
                          plan=list(plan), goals_tried=goals_tried,
                          drop_inputs=drop_inputs)

    def run(self) -> None:
        """Main loop: sense → select goal → plan → act."""
        client_manager = ClientManager()
        client = client_manager.client
        self._initialize(client)

        print(f"[{self._now()}] Starting play loop for {self.character}")

        try:
            while True:
                # Refresh BEFORE building actions so a batched PursueTask plan
                # bakes its unit count K from the same post-refresh inventory the
                # goal/map_means later computes K from (else K can diverge on the
                # ~1-in-20 refresh cycle).
                self._maybe_periodic_refresh(client)
                actions = self._build_actions()
                self._wait_for_cooldown()

                assert self.state is not None
                assert self.game_data is not None
                state = self.state
                game_data = self.game_data

                self._maybe_retry_bank()

                # Update the gear-review latch BEFORE selection so the
                # GEAR_REVIEW guard sees this cycle's state. prev is the
                # character level from the previous cycle (or the current level
                # on the very first cycle, so no spurious level-up trigger).
                prev = self._prev_level if self._prev_level is not None else state.level
                self._gear_latch.update(prev, state, self._last_outcome, game_data)
                self._prev_level = state.level
                self._arbiter.set_cycle(self._cycle_counter)

                assert self._strategy is not None
                combat_monster = self._winnable_farm_target()
                selected_goal, plan, goals_tried, replanned = self._plan_or_reuse(
                    state, game_data, actions, combat_monster)
                state = self.state  # _plan_or_reuse may have replaced crafting_target
                goal_rank_trace: list[dict[str, object]] = [
                    {"goal": gt["goal"], "priority": 0.0} for gt in goals_tried
                ]

                if self.verbose:
                    print(f"[{self._now()}] Selected: {selected_goal!r}")

                if selected_goal is not None:
                    self._last_goal_name = repr(selected_goal)
                    self._note_goal_selection(repr(selected_goal), cycle_index=self._cycle_counter)

                if not plan or selected_goal is None:
                    print(f"[{self._now()}] No plan found — waiting 5s")
                    # Record no-plan cycle for NO_PROGRESS detection
                    self._record_cycle(self._make_cycle_record(
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
                self._record_learning_cycle(
                    prev_state=prev_state_for_learning,
                    new_state=new_state,
                    action_repr=repr(action),
                    action_class=type(action).__name__,
                    outcome=outcome,
                    selected_goal=repr(selected_goal),
                    predicted_cost=predicted,
                    actual_cooldown_seconds=cooldown_remaining,
                    planner_nodes=self.planner.last_stats.nodes_explored if replanned else 0,
                    planner_depth=self.planner.last_stats.max_depth_reached if replanned else 0,
                    planner_timed_out=self.planner.last_stats.timed_out if replanned else False,
                    plan_len=len(plan),
                    cycles_to_satisfy=cycles_to_satisfy,
                )
                # Record the action outcome so the next cycle's gear-latch
                # update can detect a fight loss ("error:fight_lost"). Only set
                # on the action-execution path — no_plan cycles leave the
                # previous value intact (they continue before reaching here).
                self._last_outcome = outcome
                self.state = new_state
                if outcome == "ok" and self._plan_cache is not None:
                    self._plan_cache.advance()
                    self._plan_cache.cycles_since_replan += 1

                # After action.execute (or dry_run apply), record the cycle
                # for stuck detection. `error:cooldown` is treated as
                # SUCCEEDED for stuck-tracking purposes because it's a
                # transient server-timing rejection (action submitted before
                # cooldown elapsed), not a goal failure. Counting it as a
                # failure caused the stuck-detector to flag
                # GOAL_OSCILLATION after a single cooldown rejection on
                # GrindCharacterXP and suppress the goal for 5 cycles —
                # bot abandoned combat after one server-timing miss
                # (trace 2026-06-06 cycles 0+1: cooldown → suppression →
                # PursueTask for the rest of the session). The action's
                # intent was correct; only the timing was off.
                outcome_for_stuck = (
                    outcome == "ok" or outcome == "error:cooldown"
                )
                self._record_cycle(self._make_cycle_record(
                    goal_name=repr(selected_goal),
                    action_name=repr(action),
                    planned_depth=len(plan),
                    planner_timed_out=self.planner.last_stats.timed_out if replanned else False,
                    succeeded=outcome_for_stuck,
                ))
                self._actions_since_full_refresh += 1
                self._decrement_suppressions()
                cycle_stats: dict[str, object] = {
                    "nodes": self.planner.last_stats.nodes_explored if replanned else 0,
                    "depth": self.planner.last_stats.max_depth_reached if replanned else 0,
                    "timed_out": self.planner.last_stats.timed_out if replanned else False,
                    "replanned": replanned,
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
                    planner_stats=cycle_stats, action=action,
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
        except ApiActionError as e:
            if e.code == ERROR_CODE_COOLDOWN:
                print(f"[{self._now()}] Server cooldown (HTTP 499) — refreshing state")
                outcome = "error:cooldown"
            elif e.code == 496 and isinstance(action, (DepositAllAction, WithdrawItemAction)):
                # Discover unlock monster + compute required level, then push
                # everything into the blocker registry (which also persists
                # via the learning store when present).
                unlock_monster = self._bank_unlock_monster
                if unlock_monster is None:
                    match = _ACHIEVEMENT_CODE_RE.search(str(e))
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
            elif e.code == ERROR_CODE_ALREADY_EQUIPPED:
                # HTTP 485 ("This item is already equipped"). The plan-time
                # gate in EquipAction.is_applicable keeps planned equips from
                # ever reaching this, but any future 485 must stay an
                # ordinary failed-cycle outcome: record it, refresh state,
                # and let the cycle complete so replanning and the stuck
                # detector can react (2026-06-10 Robby trace: utility2
                # equip-485 livelock preceded a silent worker-thread death).
                print(f"[{self._now()}] Item already equipped (HTTP 485) — refreshing state")
                outcome = "error:already_equipped"
            else:
                # Finer-grained learning label keyed on the structured code.
                print(f"[{self._now()}] Action failed: {e} — refreshing state")
                outcome = f"error:HTTP_{e.code}"
            return self._fetch_world_state(client), outcome
        except RuntimeError as e:
            msg = str(e)
            if msg.startswith("fight_lost"):
                print(f"[{self._now()}] Fight lost: {msg} — refreshing state")
                outcome = "error:fight_lost"
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
        bank_capacity = self.state.bank_capacity if self.state else None
        pending_items = self.state.pending_items if self.state else None
        active_events = self._fetch_active_events(client)
        state = WorldState.from_character_schema(
            last_result.data,
            bank_items=bank_items,
            bank_gold=bank_gold,
            bank_capacity=bank_capacity,
            pending_items=pending_items,
            active_events=active_events,
        )
        self._record_skill_observations(
            state,
            {skill: getattr(last_result.data, f"{skill}_max_xp", 0) for skill in state.skills},
        )
        # PLAN #4 visibility slice: surface this cycle's live event monster/resource
        # spawns into the planner's location accessors. Set before objective selection
        # and action-building, both of which read game_data this cycle.
        if self.game_data is not None:
            self.game_data.active_event_codes = set(active_events)
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
        bank_capacity: int | None = state.bank_capacity
        details = get_bank_details(client=client)
        if details is not None and hasattr(details, "data") and details.data is not None:
            bank_gold = details.data.gold
            bank_capacity = details.data.slots

        # `dataclasses.replace` so every untouched field carries over. The old
        # field-by-field WorldState(...) rebuild silently DROPPED every field
        # it didn't enumerate (attack/dmg/dmg_elements/resistance/
        # critical_strike/initiative/wisdom/skill_xp) — zeroed combat stats on
        # every periodic refresh, flapping combat_capable and dooming combat
        # planning until the next character fetch.
        return replace(
            state,
            bank_items=bank_items,
            bank_gold=bank_gold,
            bank_capacity=bank_capacity,
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
        # `dataclasses.replace`: only pending_items changes; every other field
        # (combat stats included) carries over. See `_sync_bank` for the
        # stat-dropping bug the explicit rebuild caused.
        return replace(state, pending_items=pending)

    def _full_refresh(self, client: AuthenticatedClient) -> None:
        """Force a complete state refresh: character, bank, pending items.

        Bank/pending sync tolerates transport failures: run-9 trace 2026-06-12
        01:14:37, a ReadTimeout on GET /my/bank inside the periodic refresh
        escaped all handling and killed the process 23 min into the run (the
        action path catches httpx.HTTPError; this path did not). On failure
        the carried-over bank view stays and the counter is NOT reset, so the
        next cycle retries the refresh. _fetch_world_state retries internally;
        _sync_bank/_sync_pending have no handling of their own — this is their
        single handling level."""
        self.state = self._fetch_world_state(client)
        if self.state is not None:
            try:
                self.state = self._sync_bank(client, self.state)
                self.state = self._sync_pending(client, self.state)
            except httpx.HTTPError as e:
                print(f"[{self._now()}] Bank/pending refresh network error: {e!r} "
                      "— keeping prior bank view; retrying next cycle")
                return
        self._actions_since_full_refresh = 0

    def _maybe_periodic_refresh(self, client: AuthenticatedClient) -> None:
        """Force a full refresh every BANK_REFRESH_INTERVAL successful actions."""
        if self._actions_since_full_refresh >= BANK_REFRESH_INTERVAL:
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
                # Item 13 prep: xp/max_xp + per-skill xp enable server-axiom
                # replay to gate on LIV-001 (xpToNextLevel curve consistency).
                "xp": self.state.xp, "max_xp": self.state.max_xp,
                "skill_xp": dict(self.state.skill_xp),
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
            "servability": self._last_servability_diag,
        }
        if self._strategy is not None and self.game_data is not None:
            decision = self._last_decision or self._strategy.decide(
                self.state, self.game_data, history=self.history,
                combat_monster=self._winnable_farm_target())
            record["strategy"] = decision.to_trace()
        self.tracer.write_cycle(record)
        self._cycle_counter += 1

    def _record_cycle(self, record: CycleRecord) -> None:
        """Record one cycle for stuck detection AND track per-signal
        counter-evidence streaks for escalation decay.

        A cycle is counter-evidence for a signal when it refutes that signal's
        stuck hypothesis: a real plan refutes NO_PROGRESS, a succeeded action
        refutes GOAL_OSCILLATION (the flap is failure-driven), and a CHANGED
        state key refutes STATE_FROZEN (frozen loops can "succeed" while the
        state stays put, so success alone proves nothing there).
        """
        self._detector.record(record)
        counter_evidence = {
            StuckSignal.NO_PROGRESS: record.action_name != "<no_plan>",
            StuckSignal.GOAL_OSCILLATION: record.succeeded,
            StuckSignal.STATE_FROZEN: (
                self._prev_cycle_state_key is not None
                and record.state_key != self._prev_cycle_state_key
            ),
        }
        self._prev_cycle_state_key = record.state_key
        for sig, healthy in counter_evidence.items():
            if healthy:
                self._healthy_streak[sig] += 1
                if self._healthy_streak[sig] > self._max_healthy_streak[sig]:
                    self._max_healthy_streak[sig] = self._healthy_streak[sig]
            else:
                self._healthy_streak[sig] = 0

    def _handle_stuck(self, signal: StuckSignal, client: AuthenticatedClient) -> None:
        """Apply recovery action for a stuck signal at its current escalation level."""
        # Escalation decay: N = the signal's own detection window. A full
        # window of CONSECUTIVE counter-evidence since the last fire is
        # exactly the span the detector itself would call healthy, so any
        # earlier escalation history is stale — reset to L0 before counting
        # this fire. A genuine livelock can never produce such a span: the
        # refill window that re-fires the signal necessarily contains the
        # evidence (failures / no-plans / frozen states) that breaks the
        # streak. Trace 2026-06-10: 67 productive cycles between L2 and L3
        # must clear history; this does (67 >= 8).
        if self._max_healthy_streak.get(signal, 0) >= SIGNAL_WINDOWS[signal]:
            self._recovery_level[signal] = 0
        self._max_healthy_streak[signal] = 0
        self._healthy_streak[signal] = 0
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
                print(f"[{self._now()}] [recovery] GOAL_OSCILLATION L3: recovery exhausted — "
                      "stopping run (manual intervention)")
                raise StuckExit(signal)

        elif signal == StuckSignal.NO_PROGRESS:
            if level == 1:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L1: forcing full refresh")
                self.state = self._fetch_world_state(client)
            elif level == 2:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L2: forcing full refresh + clearing blockers")
                self.state = self._fetch_world_state(client)
                self._blockers.clear("bank")
            else:
                print(f"[{self._now()}] [recovery] NO_PROGRESS L3: recovery exhausted — "
                      "stopping run (manual intervention)")
                raise StuckExit(signal)

        self._detector.acknowledge(signal)

    def _build_actions(self) -> list[Action]:
        """Build the action list (delegates to the actions factory)."""
        assert self.game_data is not None
        return build_actions(
            game_data=self.game_data,
            state=self.state,
            objective=self._objective,
            bank_accessible=self._bank_accessible,
            task_exchange_min_coins=self._task_exchange_min_coins,
        )

    def _notify_observer(
        self,
        selected_goal_name: str,
        action_name: str,
        outcome: str,
        goal_rank_trace: list[dict[str, Any]],
        planner_stats: dict[str, object] | None = None,
        action: object | None = None,
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
        action_kind, action_target = action_kind_of(action) if action is not None else ("other", None)
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
            action_kind=action_kind,
            action_target=action_target,
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
            chosen_root=(repr(self._last_decision.chosen_root)
                         if self._last_decision is not None
                         and self._last_decision.chosen_root is not None else None),
            strategy_ranking=[
                RootScoreView(root_repr=r.root_repr, category=r.category,
                              score=float(r.score), step_repr=r.step_repr)
                for r in (self._last_decision.ranking if self._last_decision is not None else [])
            ],
            bank_items=(dict(self.state.bank_items)
                        if self.state.bank_items is not None else None),
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

    def _is_winnable(self, monster_code: str) -> bool:
        """Target-selection beatability: can the bot beat this monster AFTER
        a normal HP recovery (Rest / consumable)? The planner inserts the
        recovery step before FightAction when state.hp is below max. Without
        projecting to max_hp here, a single mid-damage cycle (hp=58%, the
        critical-HP guard's threshold is 25% so RestoreHP doesn't preempt)
        narrows the winnable set to the lowest-level monsters → the FightAction
        action-layer level filter (`monster_level >= state.level-1`) rejects
        those too → no monster picked → bootstrap step plans nothing →
        discretionary PursueTask wins forever. Trace 2026-06-06 session
        01:24-04:57: Robby parked at hp=76/130 for 278 cycles, 0 fights.
        Per-cycle HP veto is FightAction.is_applicable's job (uses real hp);
        target selection asks the strategic question."""
        assert self.state is not None and self.game_data is not None
        projected = replace(self.state, hp=self.state.max_hp)
        return is_winnable(projected, self.game_data, monster_code, self.history)

    def _pick_winnable_monster(self) -> str | None:
        """Window-preferred winnable monster, with a liveness fallback.

        PREFERRED: highest-level `_is_winnable` monster inside the
        FightAction level window [max(1, char_level-1), char_level+2].
        Trace 2026-06-06 16:34: picker returned yellow_slime (lvl 2) for
        Robby (lvl 4); FightAction.is_applicable rejected it (below the
        old hard window) and the dead target cascaded into an empty plan.
        Honoring the window at picker time prevents that cascade.

        FALLBACK (P0 no-combat deadlock, 2026-06-09 live repro): at
        level 4 the only stat-winnable monsters were chicken (L1) and
        yellow_slime (L2) — both below the window, so the picker returned
        None forever and no combat goal was ever constructed. When the
        window holds no winnable monster, fall back to the highest-level
        winnable monster that still grants XP (`xp_per_kill > 0`; the
        documented curve zeroes out at char_level - monster_level >= 10)
        and is under the char_level+2 suicide guard.
        FightAction.is_applicable enforces the SAME xp>0 lower gate, so
        any fallback target is level-applicable. Returns None only when
        nothing winnable grants XP — then gear progression is the only
        path, which is correct. Decision logic lives in the pure core
        `combat_picker.pick_winnable_monster_pure` (Lean-diff-locked).
        """
        assert self.game_data is not None
        assert self.state is not None
        game_data = self.game_data
        char_level = self.state.level
        return pick_winnable_monster_pure(
            char_level,
            list(game_data.monster_levels.items()),
            self._is_winnable,
            lambda code: game_data.xp_per_kill(code, char_level) > 0,
        )

    def _task_aligned_monster(self) -> str | None:
        """The active task's monster when it's a PURSUE monster-task; else None.

        A PURSUE monster-task has cleared the level-margin feasibility gate
        (task_decision returns PIVOT for combat-gated tasks), so the objective-step
        grind can advance it directly once retargeted here. This bypasses the
        non-task _is_winnable fallback; a borderline-margin monster is still picked
        because the task forces the target. A persistent loss loop is caught by the
        stuck/recovery backstop, not here.
        """
        s = self.state
        if s is None or self.game_data is None or s.task_type != "monsters" or not s.task_code:
            return None
        if s.task_total == 0 or s.task_progress >= s.task_total:
            return None
        if task_decision(s, self.game_data, self.history) != PURSUE:
            return None
        return s.task_code

    def _winnable_farm_target(self) -> str | None:
        # Lazy short-circuit preserved: task wins outright; otherwise we
        # only consult the path projection / global winnable scan.
        task_monster = self._task_aligned_monster()
        if task_monster is not None:
            return winnable_farm_target_pure(CascadeInputs(
                task_monster=task_monster,
                path_monster=None,
                path_winnable=False,
                pick_winnable=None,
            ))
        path_monster = self._path_aligned_monster()
        path_winnable = path_monster is not None and self._is_winnable(path_monster)
        # `pick_winnable` is only consulted when the path tier fails — match
        # the original eager-but-short-circuited evaluation.
        pick = self._pick_winnable_monster() if not path_winnable else None
        return winnable_farm_target_pure(CascadeInputs(
            task_monster=None,
            path_monster=path_monster,
            path_winnable=path_winnable,
            pick_winnable=pick,
        ))

    def _step_servable(
        self, state: WorldState, game_data: GameData, ctx: SelectionContext
    ) -> Callable[[MetaGoal, MetaGoal], bool]:
        """Build the per-root plannability predicate decide() uses to demote roots
        whose actionable step can't be served this cycle. A root is servable when its
        step routes to a goal (objective_step_goal) that is plannable now — the same
        objective_step_goal the arbiter will resolve, so decide()'s servability matches
        what select() can actually serve. Closes the feather_coat mismatch: a body
        armor whose woodcutting-gated step yields an unplannable GatherMaterials is
        demoted below the plannable ReachCharLevel grind."""
        def servable(root: MetaGoal, step: MetaGoal) -> bool:
            goal = objective_step_goal(step, state, game_data, ctx,
                                       root=root, committed_root=root)
            return goal is not None and goal.is_plannable(state, game_data, self.history)
        return servable

    def _update_sticky_anchor(
        self, chosen_root: MetaGoal | None, state: WorldState,
        game_data: GameData, chosen_step_alive: bool) -> None:
        """Progress-gated Tier-2 sticky release (2026-06-20). Re-feed `chosen_root` as
        next cycle's sticky anchor ONLY when it yielded a goal this cycle AND advanced
        on its own progress axis since last cycle; otherwise release it so the
        highest-value plannable root wins next cycle. A freshly-chosen root gets one
        cycle to act before the progress gate can release it. Mirrors
        `Formal/Liveness/StickySelect.lean::nextLast`; the frozen-axis release kills the
        weaponcrafting zombie (1028-cycle hold)."""
        if chosen_root is None:
            self._last_strategy_root = None
            self._sticky_progress_value = None
            return
        cur_value = root_progress_value(chosen_root, state, game_data)
        if repr(chosen_root) == self._last_strategy_root:
            # Same root as last cycle: the value was recorded then (set in lockstep
            # with the anchor), so it is non-None here. Progress = it advanced.
            assert self._sticky_progress_value is not None
            progressed = cur_value > self._sticky_progress_value
        else:
            # Freshly chosen this cycle: one cycle to act before the gate can release.
            progressed = True
        progressed = progressed and chosen_step_alive
        self._last_strategy_root = next_last(repr(chosen_root), progressed)
        self._sticky_progress_value = cur_value

    def _maybe_retry_bank(self) -> None:
        """Periodically retry bank access after an achievement gate failure
        (HTTP 496), but only if the character has gained at least one level
        since the last attempt — otherwise the flap creates a wasteful
        Deposit→496→UnlockBank→Deposit loop."""
        assert self.state is not None
        if (not self._bank_accessible and self._bank_blocked_since is not None
                and time.monotonic() - self._bank_blocked_since >= _BANK_RETRY_SECONDS
                and self.state.level > self._bank_blocked_at_level):
            self._blockers.clear("bank")

    def _selection_context(self, combat_monster: str | None = None) -> SelectionContext:
        assert self.state is not None
        if combat_monster is None:
            combat_monster = self._winnable_farm_target()
        # Build per-skill SkillXpCurve from observed learning history; empty
        # dict if no history (no projection-based satisfaction available —
        # LevelSkillGoal falls back to the server-snapshot path).
        skill_xp_curves: dict[str, SkillXpCurve] = {}
        if self.history is not None:
            for skill in self.state.skills:
                observed = self.history.skill_max_xp_observations(skill)
                if observed:
                    skill_xp_curves[skill] = SkillXpCurve(observed=observed)
        # CRAFT_RELIEF guard needs the long-term gear / tool targets so it
        # can score craftable-from-inventory candidates that advance the
        # equipment chain (not just the active task item).
        target_gear: frozenset[str] = frozenset()
        target_tools: frozenset[str] = frozenset()
        if self._objective is not None:
            target_gear = frozenset(self._objective.target_gear.values())
            target_tools = frozenset(self._objective.target_tools.values())
        return SelectionContext(
            bank_accessible=self._bank_accessible,
            bank_required_level=self._bank_required_level,
            bank_unlock_monster=self._bank_unlock_monster,
            initial_xp=self.state.xp,
            task_exchange_min_coins=self._task_exchange_min_coins,
            combat_monster=combat_monster,
            skill_xp_curves=skill_xp_curves,
            target_gear=target_gear,
            target_tools=target_tools,
            gear_review_active=self._gear_latch.active,
        )

    def _log_action(self, action: Action, goal: Goal, plan: list[Action]) -> None:
        assert self.state is not None
        suffix = f"  [{_format_plan(plan[1:])}]" if len(plan) > 1 else ""
        print(f"[{self._now()}] → {action!r}{suffix}  (goal: {goal!r})")

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
        before = prev_state.inventory.get(TASKS_COIN_CODE, 0)
        prev = self._task_exchange_min_coins
        if outcome == "error:HTTP_478":
            self._task_exchange_min_coins = max(self._task_exchange_min_coins, before + 1)
        elif outcome == "ok":
            spent = before - new_state.inventory.get(TASKS_COIN_CODE, 0)
            if spent > 0:
                self._task_exchange_min_coins = spent
        # Persist any change so the next session doesn't re-discover the same
        # minimum via fresh HTTP 478 rejections.
        if self.history is not None and self._task_exchange_min_coins != prev:
            self.history.set_learned_int(
                "task_exchange_min_coins", self._task_exchange_min_coins,
            )

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
        """Build a Cycle row and persist via LearningStore. No-op when history is
        None or in dry_run.

        Dry-run cycles are SIMULATED (action.apply, no real cooldown), so their
        actual_cooldown_seconds is 0 and their state deltas are projections, not
        observations. Persisting them poisons the learned cost model: a Fight
        stored with cooldown 0 makes cheapest_path's xp_per_cycle = xpk/max(0,1)
        = xpk blow up, locking the grind onto whatever monster collected the
        zero-cost rows (live Robby 2026-06-12: 29/50 zero-cost green_slime rows
        from dry-run probes out-ranked higher-XP blue_slime). Observed costs
        must come ONLY from real execution."""
        if self.history is None or self.dry_run:
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
