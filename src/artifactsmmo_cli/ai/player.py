"""GOAP AI player: main sense→plan→act loop."""

import re
import time
from datetime import datetime, timezone

from artifactsmmo_api_client import AuthenticatedClient
from artifactsmmo_api_client.types import Unset
from artifactsmmo_api_client.api.achievements.get_achievement_achievements_code_get import sync as get_achievement
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character
from artifactsmmo_api_client.models.achievement_type import AchievementType
from artifactsmmo_api_client.api.my_account.get_bank_details_my_bank_get import sync as get_bank_details
from artifactsmmo_api_client.api.my_account.get_bank_items_my_bank_items_get import sync as get_bank_items
from artifactsmmo_api_client.api.my_account.get_pending_items_my_pending_items_get import sync as get_pending_items

from artifactsmmo_cli.ai.actions.bank import DepositAllAction, WithdrawItemAction
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.bank_gold import DepositGoldAction, WithdrawGoldAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS, EquipAction, UnequipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task import AcceptTaskAction, CompleteTaskAction, TaskCancelAction, TaskExchangeAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal, FarmMonsterGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.farm_items import FarmItemsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner, _state_key
from artifactsmmo_cli.ai.recovery import CycleRecord, StuckDetector, StuckSignal
from artifactsmmo_cli.ai.tracing import NullTracer, Tracer
from artifactsmmo_cli.ai.world_state import WorldState
from artifactsmmo_cli.client_manager import ClientManager

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

    def __init__(self, character: str, verbose: bool = False, dry_run: bool = False,
                 tracer: Tracer | None = None) -> None:
        self.character = character
        self.verbose = verbose
        self.dry_run = dry_run
        self.planner = GOAPPlanner()
        self.state: WorldState | None = None
        self.game_data: GameData | None = None
        self._bank_accessible: bool = True
        self._bank_blocked_since: float | None = None
        self._bank_unlock_monster: str | None = None
        self._detector = StuckDetector(history_size=30)
        self._suppressed_goals: dict[str, int] = {}
        self._actions_since_full_refresh: int = 0
        self._recovery_level: dict[StuckSignal, int] = {}
        self._last_goal_name: str | None = None
        self._wildcard_mode: bool = False
        self.tracer: Tracer = tracer or NullTracer()
        self._cycle_counter: int = 0

    def run(self) -> None:
        """Main loop: sense → select goal → plan → act."""
        client_manager = ClientManager()
        client = client_manager.client

        print(f"[{self._now()}] Loading game data...")
        self.game_data = GameData.load(client)

        print(f"[{self._now()}] Fetching character state...")
        self.state = self._fetch_world_state(client)

        print(f"[{self._now()}] Starting play loop for {self.character}")

        try:
            while True:
                actions = self._build_actions()
                self._maybe_periodic_refresh(client)
                self._wait_for_cooldown()

                goals = self._build_goals()
                goals.sort(key=lambda g: g.priority(self.state, self.game_data), reverse=True)

                plan: list[Action] = []
                selected_goal: Goal | None = None

                if self.verbose:
                    goal_summary = "  ".join(
                        f"{g}={g.priority(self.state, self.game_data):.1f}" for g in goals
                    )
                    print(f"[{self._now()}] Goals: {goal_summary}")

                for goal in goals:
                    if goal.priority(self.state, self.game_data) <= 0:
                        break
                    plan = self.planner.plan(self.state, goal, actions, self.game_data)
                    if self.verbose and not plan:
                        s = self.planner.last_stats
                        print(f"[{self._now()}]   No plan for {goal}: nodes={s.nodes_explored} depth={s.max_depth_reached} timeout={s.timed_out}")
                    if plan:
                        selected_goal = goal
                        self._last_goal_name = repr(selected_goal)
                        break

                if not plan or selected_goal is None:
                    print(f"[{self._now()}] No plan found — waiting 5s")
                    # Record no-plan cycle for NO_PROGRESS detection
                    self._detector.record(self._make_cycle_record(
                        goal_name="<none>",
                        action_name="<no_plan>",
                        planned_depth=0,
                        planner_timed_out=self.planner.last_stats.timed_out if self.state else False,
                        succeeded=False,
                    ))
                    self._emit_trace(
                        action_name="<no_plan>",
                        goal_name="<none>",
                        outcome="no_plan",
                        planner_stats={"nodes": 0, "depth": 0, "timed_out": False, "plan_len": 0},
                    )
                    signal = self._detector.detect()
                    if signal is not None:
                        self._handle_stuck(signal, client)
                    time.sleep(5)
                    continue

                if self.verbose:
                    plan_str = _format_plan(plan)
                    relevant = selected_goal.relevant_actions(actions, self.state, self.game_data)
                    applicable = [repr(a) for a in relevant if a.is_applicable(self.state, self.game_data)]
                    print(f"[{self._now()}] Goal: {selected_goal}({selected_goal.priority(self.state, self.game_data):.1f})  Plan: {plan_str}")
                    print(f"[{self._now()}] Applicable: {applicable}")

                action = plan[0]
                self._log_action(action, selected_goal, plan)

                if self.dry_run:
                    self.state = action.apply(self.state, self.game_data)
                else:
                    self.state = self._execute(action, client)

                # After action.execute (or dry_run apply), record the cycle for stuck detection
                self._detector.record(self._make_cycle_record(
                    goal_name=repr(selected_goal),
                    action_name=repr(action),
                    planned_depth=len(plan),
                    planner_timed_out=self.planner.last_stats.timed_out,
                    succeeded=True,
                ))
                self._actions_since_full_refresh += 1
                self._decrement_suppressions()
                self._emit_trace(
                    action_name=repr(action),
                    goal_name=repr(selected_goal),
                    outcome="ok",
                    planner_stats={
                        "nodes": self.planner.last_stats.nodes_explored,
                        "depth": self.planner.last_stats.max_depth_reached,
                        "timed_out": self.planner.last_stats.timed_out,
                        "plan_len": len(plan),
                    },
                )
                signal = self._detector.detect()
                if signal is not None:
                    self._handle_stuck(signal, client)
        finally:
            self.tracer.close()

    def _execute(self, action: Action, client: AuthenticatedClient) -> WorldState:
        """Execute an action and return the updated WorldState."""
        try:
            new_state = action.execute(self.state, client)
            # Re-sync bank state after visiting bank
            if isinstance(action, (DepositAllAction, WithdrawItemAction)):
                new_state = self._sync_bank(client, new_state)
            # Re-sync pending items after claiming one
            if isinstance(action, ClaimPendingItemAction):
                new_state = self._sync_pending(client, new_state)
            return new_state
        except RuntimeError as e:
            msg = str(e)
            if "HTTP 499" in msg:
                print(f"[{self._now()}] Server cooldown (HTTP 499) — refreshing state")
            elif "HTTP 496" in msg and isinstance(action, (DepositAllAction, WithdrawItemAction)):
                self._bank_accessible = False
                self._bank_blocked_since = time.monotonic()
                if self._bank_unlock_monster is None:
                    match = _ACHIEVEMENT_CODE_RE.search(msg)
                    if match:
                        self._bank_unlock_monster = self._resolve_bank_unlock_monster(client, match.group(1))
                print(f"[{self._now()}] Bank locked (HTTP 496) — fighting {self._bank_unlock_monster or '?'} to unlock; retrying in {_BANK_RETRY_SECONDS:.0f}s")
            else:
                print(f"[{self._now()}] Action failed: {msg} — refreshing state")
            return self._fetch_world_state(client)

    def _fetch_world_state(self, client: AuthenticatedClient) -> WorldState:
        """Query character state from the API."""
        result = get_character(client=client, name=self.character)
        if result is None or not hasattr(result, "data") or result.data is None:
            raise RuntimeError(f"Could not fetch character '{self.character}'")

        bank_items = self.state.bank_items if self.state else None
        bank_gold = self.state.bank_gold if self.state else None
        pending_items = self.state.pending_items if self.state else None
        return WorldState.from_character_schema(result.data, bank_items=bank_items, bank_gold=bank_gold, pending_items=pending_items)

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
        self.tracer.write_cycle(record)
        self._cycle_counter += 1

    def _handle_stuck(self, signal: StuckSignal, client) -> None:
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
            distinct = {r.goal_name for r in history}
            if level == 1:
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
            DepositAllAction(bank_location=bank, accessible=self._bank_accessible),
            AcceptTaskAction(taskmaster_location=taskmaster),
            CompleteTaskAction(taskmaster_location=taskmaster),
            TaskExchangeAction(taskmaster_location=taskmaster),
            TaskCancelAction(taskmaster_location=taskmaster),
            ClaimPendingItemAction(),
        ]

        # Fight and gather actions carry their own locations — no separate move actions needed
        for monster_code, locs in self.game_data._monster_locations.items():
            actions.append(FightAction(monster_code=monster_code, locations=frozenset(locs)))

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
                actions.append(WithdrawItemAction(code=item_code, quantity=1, bank_location=bank, accessible=self._bank_accessible))
                for mat_code, mat_qty in recipe.items():
                    if mat_qty > materials_to_withdraw.get(mat_code, 0):
                        materials_to_withdraw[mat_code] = mat_qty

        for mat_code, mat_qty in materials_to_withdraw.items():
            actions.append(WithdrawItemAction(code=mat_code, quantity=mat_qty, bank_location=bank, accessible=self._bank_accessible))

        # Allow withdrawing task coins from bank for exchange
        actions.append(WithdrawItemAction(code="tasks_coin", quantity=1, bank_location=bank, accessible=self._bank_accessible))

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

        # Periodically retry bank access after an achievement gate failure (HTTP 496).
        if not self._bank_accessible and self._bank_blocked_since is not None:
            if time.monotonic() - self._bank_blocked_since >= _BANK_RETRY_SECONDS:
                self._bank_accessible = True
                self._bank_blocked_since = None

        # Pick a suitable monster to farm: highest level at or below character level
        farm_target = "chicken"  # safe fallback
        best_level = 0
        for code, level in self.game_data._monster_level.items():
            if level <= self.state.level and level > best_level:
                best_level = level
                farm_target = code

        upgrade_goal = UpgradeEquipmentGoal(initial_equipment=self.state.equipment)
        goals: list[Goal] = [
            RestoreHPGoal(),
            DepositInventoryGoal(bank_accessible=self._bank_accessible),
            SellInventoryGoal(bank_accessible=self._bank_accessible),
            ExpandBankGoal(bank_accessible=self._bank_accessible),
            UnlockBankGoal(bank_locked=not self._bank_accessible, initial_xp=self.state.xp, target_monster=self._bank_unlock_monster),
            ClaimPendingGoal(),
            CompleteTaskGoal(),
            AcceptTaskGoal(),
            TaskExchangeGoal(),
            TaskCancelGoal(),
            FarmMonsterGoal(monster_code=farm_target, initial_xp=self.state.xp),
            upgrade_goal,
        ]

        if self.state.task_type == "items" and self.state.task_code:
            goals.append(FarmItemsGoal())

        # If upgrade needs materials, add a gather goal to drive material collection.
        # Use the FULL recipe quantity (not remaining needed) so GatherMaterials and
        # UpgradeEquipment both check the same threshold (inventory+bank >= recipe_qty).
        # Using a partial quantity causes GatherMaterials to satisfy early when existing
        # items were deposited to the bank, while UpgradeEquipment still sees insufficient
        # total materials.
        target = upgrade_goal.find_upgrade_target(self.state, self.game_data)
        if target is not None:
            item_code, _slot = target
            recipe = self.game_data._crafting_recipes.get(item_code)
            if recipe:
                gm_goal = GatherMaterialsGoal(target_item=item_code, needed=dict(recipe))
                if not gm_goal.is_satisfied(self.state):
                    goals.append(gm_goal)

        return [g for g in goals if repr(g) not in self._suppressed_goals]

    def _log_action(self, action: Action, goal: Goal, plan: list[Action]) -> None:
        assert self.state is not None
        suffix = f"  [{_format_plan(plan[1:])}]" if len(plan) > 1 else ""
        print(f"[{self._now()}] → {action!r}{suffix}  (goal: {goal!r})")

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%H:%M:%S")
