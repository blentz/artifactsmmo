# GOAP Robustness Layer — Design Spec
**Date:** 2026-05-15
**Status:** Draft (pending review)
**Predecessor:** `docs/superpowers/specs/2026-05-12-goap-ai-player-design.md` (v1)

## Overview

The v1 GOAP AI player is functionally complete (434 AI tests passing, 94% coverage on the AI module, CLI wired as `artifactsmmo play <character>`). Real-play iteration with Robby has surfaced behavioral gaps that block long-running autonomy: the bot can lose value via `DeleteItemAction` when bank-locked, gets stuck in oscillating goal cycles, and lacks API capabilities (NPC sell, bank expansion, map transition, task trade, gold management) that close those recovery paths.

This spec defines a **robustness layer** that:
1. Fills the missing API-action surface (5 new actions, 2 new goals).
2. Adds a stuck-state detector with an escalating recovery ladder.
3. Rebases all "is the bot healthy?" decisions on action counts instead of wall-clock.
4. Adds JSONL trace observability for postmortem analysis.
5. Cleans up the 67 mypy errors and 4% coverage gap.

It also lays the data-capture groundwork for a future phase (Phase F) of autoregressive planning that learns from past traces, without committing to that work in this cycle.

## Context

**Current GOAP architecture** (unchanged by this spec):
- `WorldState` is a frozen dataclass built from API responses; mutated only by the player loop, never by the planner.
- `GameData` is loaded once at startup (maps, items, monsters, resources, NPCs).
- `Action` ABC: `is_applicable`, `apply` (pure), `cost`, `execute` (API call).
- `Goal` ABC: `value`, `priority`, `is_satisfied`, `desired_state`, `relevant_actions`, `max_depth`.
- `GOAPPlanner.plan` is forward A* with a 2-second search budget.
- `GamePlayer.run` is the sense → select goal → plan → act loop, one action per cycle, refresh-on-error.

**Implemented beyond v1**:
- Tier 2/3 actions: Claim, Delete, NPC buy, Recycle, Use consumable, Task variants (accept/complete/exchange/cancel).
- Tier 2/3 goals: ClaimPending, FarmItems, GatherMaterials, UnlockBank, TaskCancel, TaskExchange, AcceptTask.
- HTTP 496 bank-lockout handling with achievement-gate parsing and `UnlockBankGoal`.
- Bank accessibility flag propagated across bank actions.

**Known gaps (closed by this spec)**:
- No `NpcSellAction` — bot destroys items via `DeleteItemAction` when bank-locked.
- No stuck-state detection — bot can spin in goal-oscillation or no-plan loops indefinitely.
- Wall-clock staleness check (`_refresh_if_stale`) fires spuriously during long cooldowns.
- 67 mypy errors, primarily around API-response `Union` types and untyped containers.
- 4% coverage gap in `player.py` error paths, `delete.py`, `unlock_bank.py`, `consumable.py`.
- `_sync_pending` accesses `PendingItemSchema.code` which doesn't exist (real runtime bug).

## Goals & Non-goals

### Goals
- Bot runs autonomously for hours without intervention.
- Every recoverable stuck state has a non-Delete recovery path.
- Unknown stuck states are detected and either recovered from or surfaced as a clean exit (not a silent spin).
- Trace data sufficient to drive future autoregressive planning is captured every cycle.
- `uv run mypy src/artifactsmmo_cli/ai/` reports 0 errors.
- AI module coverage ≥ 98%.

### Non-goals
- No online learning, statistics accumulation in `WorldState`/`GameData`, or model training in this cycle.
- No grand-exchange (5 endpoints), multi-character give/transfer, or skin-change support.
- No re-architecting of `Goal`/`Action`/`WorldState` contracts.
- No live-API integration tests in the test suite (manual `--dry-run` continues to be the live-validation tool).

## Architecture

The robustness layer adds three concerns to the existing player loop, without changing the loop's shape:

```
existing:  build_actions → wait_cooldown → build_goals → sort → plan → execute
                                                                  ↑       ↓
                                                                  └───────┘
                                                                 (record cycle)
                                                                       ↓
new:                                                       StuckDetector.detect()
                                                                       ↓
                                                                  (recovery?)
                                                                       ↓
                                                                  Tracer.write(...)
```

**New modules**:
- `src/artifactsmmo_cli/ai/recovery.py` — `CycleRecord`, `StuckDetector`, `StuckSignal`, recovery-ladder logic.
- `src/artifactsmmo_cli/ai/tracing.py` — `Tracer` interface, `NullTracer`, `FileTracer` (JSONL).
- `src/artifactsmmo_cli/ai/actions/npc_sell.py`, `bank_expansion.py`, `transition.py`, `task_trade.py`, `bank_gold.py`.
- `src/artifactsmmo_cli/ai/goals/sell_inventory.py`, `expand_bank.py`.

**Modified modules**:
- `player.py` — counter for actions-since-refresh, detector integration, tracer wiring, deletion of `_refresh_if_stale`.
- `game_data.py` — `_npc_sell_prices`, `_transition_tiles`, `_bank_capacity`, `_next_expansion_cost`.
- `goals/farm_items.py` — wire `TaskTradeAction` into `relevant_actions`.
- `actions/delete.py`, `actions/gathering.py` — cost-weight updates.
- Every `actions/*.py` `execute()` method — consistent use of `_raise_for_error` for mypy cleanup.
- `commands/play.py` — `--trace` / `--trace-file` flags.

## Phase A — NPC Sell foundation

### New API capabilities (action table)

| Action | Body | Applicable when | Apply effect | Key error codes |
|---|---|---|---|---|
| `NpcSellAction(npc, code, qty)` | `{code, quantity}` | At NPC tile; inventory has ≥qty; `sell_price > 0` for code | `inventory[code] -= qty; gold += sell_price × qty` | 404, 442 (not at NPC), 478 (insufficient), 486, 497, 498, 499 |

### GameData additions
- `_npc_sell_prices: dict[str, dict[str, int]]` — `npc_code -> {item_code: sell_price}`. Loaded from the same `get_all_npc_items` pagination that already populates `_npc_stock`; the API's `simple_npc_item` schema carries both `buy_price` and `sell_price`.
- `npc_buys_item(npc_code, item_code) -> int | None` — sell price lookup, mirrors existing `npc_sells_item`.
- `npcs_buying_item(item_code) -> list[tuple[str, int]]` — `(npc_code, price)` cheapest first, mirrors `npcs_selling_item`.

### New goal: `SellInventoryGoal`
- `value`: `0` when `bank_accessible`. When bank locked and any inventory item has `sell_price > 0`: `(inventory_used / inventory_max) × 70`.
- `priority`: returns `value()` (no override needed — sits naturally between `UnlockBankGoal` (~60) and `DepositInventoryGoal`).
- `is_satisfied`: `state.inventory_free >= MIN_FREE_SLOTS` (same threshold as `DepositInventoryGoal`).
- `relevant_actions`: returns `RestAction`, `MoveAction` (implicit via action carrying locations), `NpcSellAction` for each sellable item in inventory.

### DeleteItemAction cost re-weighting

Cost is computed at action-construction time in `_build_actions` from item facts:

```python
def _delete_cost(item_code: str, game_data: GameData) -> float:
    is_ingredient = any(item_code in recipe for recipe in game_data._crafting_recipes.values())
    has_sell_price = bool(game_data.npcs_buying_item(item_code))  # any NPC will buy?
    if is_ingredient:
        return 50.0                  # destroying a craft input is the worst case
    if has_sell_price:
        return 25.0                  # we're throwing away gold we could've recovered
    return 5.0                       # truly worthless item — last resort but cheap
```

The order is intentional: an item that's BOTH a sellable crafting ingredient gets `50.0` (the harsher penalty) — `is_ingredient` is checked first. Sell strictly dominates Delete for items NPCs buy. Delete remains the only path for items no NPC will buy AND that aren't crafting ingredients (typical case: monster loot with no recipe and no merchant).

## Phase B — Remaining API capabilities

### Action table

| Action | Body | Applicable when | Apply effect | Key error codes |
|---|---|---|---|---|
| `BuyBankExpansionAction` | none | At bank; `bank_accessible`; `gold ≥ next_expansion_cost` | `bank_capacity += slots_per_expansion; gold -= cost` | 422, 486, 492 (insufficient gold), 498, 499 |
| `MapTransitionAction` | none | On a tile in `GameData._transition_tiles` | New `(x, y)` from response; cooldown set | 478, 486, 492 (level gate), 496 (achievement gate) |
| `TaskTradeAction(code, qty)` | `{code, quantity}` | At taskmaster; `task_type == "items"`; inventory has qty of code | `inventory[code] -= qty; task_progress += qty` | 474/475 (task mismatch), 478 |
| `DepositGoldAction(qty)` | `{quantity}` | At bank; `bank_accessible`; `gold ≥ qty` | `gold -= qty; bank_gold += qty` | standard bank errors |
| `WithdrawGoldAction(qty)` | `{quantity}` | At bank; `bank_accessible`; `bank_gold ≥ qty` | `gold += qty; bank_gold -= qty` | standard bank errors |

### GameData additions
- `_transition_tiles: set[tuple[int, int]]` — tiles where `tile.transition` (from map schema) is non-null. Populated in `_load_maps`.
- `_bank_capacity: int`, `_next_expansion_cost: int`, `_slots_per_expansion: int` — fetched from `get_bank_details` at startup; the response schema and `BankExtensionTransactionResponseSchema` (returned by the expansion endpoint) provide these. Refreshed in-place after each successful `BuyBankExpansionAction.execute`. If the API doesn't expose `slots_per_expansion` directly, derive it from `(new_capacity - old_capacity)` after the first expansion and cache.

### New goal: `ExpandBankGoal`
- `value`: `40` when `(bank_items_used / bank_capacity) ≥ 0.95` AND `gold ≥ next_expansion_cost`. `0` otherwise.
- `is_satisfied`: `(bank_items_used / bank_capacity) < 0.90`.
- `desired_state`: `{"bank_capacity": bank_capacity + slots_per_expansion}`.

### FarmItemsGoal update
- `relevant_actions` adds `TaskTradeAction` (filtered to the current task_code) so the plan ends with a trade step, not just gathering.
- Recipe traversal stays identical — only the terminal action changes.

## Phase C — Stuck-state detection & recovery

### Module: `recovery.py`

```python
from enum import Enum
from dataclasses import dataclass

class StuckSignal(Enum):
    STATE_FROZEN = "state_frozen"
    GOAL_OSCILLATION = "goal_oscillation"
    NO_PROGRESS = "no_progress"

@dataclass(frozen=True)
class CycleRecord:
    state_key: tuple             # coarsened WorldState key (see below)
    goal_name: str               # repr of selected goal, or "<none>"
    action_name: str             # repr of action taken, or "<no_plan>"
    planned_depth: int
    planner_timed_out: bool
    succeeded: bool

class StuckDetector:
    def __init__(self, history_size: int = 30) -> None: ...
    def record(self, cycle: CycleRecord) -> None: ...
    def detect(self) -> StuckSignal | None: ...
    def acknowledge(self, signal: StuckSignal) -> None: ...
```

### Detection rules (cycle-counted, never wall-clock)

| Signal | Trigger |
|---|---|
| `STATE_FROZEN` | Same `state_key` appears ≥ 5 times in the last 10 cycles |
| `GOAL_OSCILLATION` | Last 8 cycles alternate between exactly 2 goals with neither satisfied |
| `NO_PROGRESS` | Last 4 cycles all have `action_name == "<no_plan>"` |

### Coarsened state_key

The planner's `_state_key` is fine-grained (every HP/XP tick is a different key). The detector needs a coarser key so a back-and-forth fight doesn't trip `STATE_FROZEN`:

```python
def _detector_state_key(state: WorldState) -> tuple:
    return (
        state.x, state.y, state.level,
        tuple(sorted(state.inventory.items())),
        tuple(sorted(state.equipment.items())),
        state.task_code, state.task_progress // 10,   # bucketed
        state.bank_items is None,                      # known/unknown
    )
```

HP, gold, xp, exact task_progress, and cooldown are excluded — they fluctuate normally during productive play. **Open implementation question**: validate bucketing granularity (`task_progress // 10`) against real traces; tune if false positives observed.

### Recovery ladder (`GamePlayer._handle_stuck`)

| Signal | Level 1 | Level 2 | Level 3 |
|---|---|---|---|
| `STATE_FROZEN` | Force full refresh | Suppress current goal for **5 cycles** | Suppress top-3 goals for **10 cycles** |
| `GOAL_OSCILLATION` | Suppress both oscillating goals **5 cycles** | Suppress both **15 cycles** | Exit non-zero |
| `NO_PROGRESS` | Force full refresh | Try "wildcard" goal list (`RestoreHPGoal` + safe-monster `FarmMonsterGoal`) | Exit non-zero |

**Force full refresh** during Phase C calls the existing trio (`_fetch_world_state` + `_sync_bank` + `_sync_pending`) directly. Phase D consolidates these into a single `_full_refresh(client)` method on `GamePlayer`; Phase C's call sites are updated then.

### `acknowledge` semantics

After `_handle_stuck` runs a recovery action, it calls `detector.acknowledge(signal)`. Acknowledge **resets the detection window** for that signal — specifically, it marks the current cycle index, and `detect()` only counts records *strictly after* that marker for the acknowledged signal's rule. This prevents the same signal from immediately retriggering on the next cycle while the recovery action (suppression, refresh) is still propagating its effect. Other signals' windows are unaffected.

### Player-loop state

New fields on `GamePlayer`:
- `_detector: StuckDetector`
- `_suppressed_goals: dict[str, int]` — goal_name → cycles remaining suppression. Decremented each cycle; zero entries pruned.
- `_recovery_level: dict[StuckSignal, int]` — escalation tracker per signal. Reset on signal acknowledge or successful progress.

Goal-list filtering: before sorting, `_build_goals` excludes goals with `repr(goal)` in `_suppressed_goals`.

## Phase D — State refresh & observability

### Refresh triggers (action-counted)

| Trigger | Fires when | Scope |
|---|---|---|
| API error (existing) | Any `RuntimeError` from `action.execute()` | Character + bank if relevant |
| Periodic | Every 20 successful action executions | Character + bank + pending items |
| Stuck signal | `STATE_FROZEN` / `NO_PROGRESS` Level 1 | Character + bank + pending items |

### Changes to GamePlayer

- **Delete** `_refresh_if_stale` and its 60-second wall-clock check.
- **Delete** `_last_action_time` (replaced by counter below).
- **Add** `_actions_since_full_refresh: int`, incremented on each successful `action.execute`.
- **Add** `_full_refresh(client)` — fetches character, bank items, bank details (for capacity + next expansion cost), and pending items; resets counter to 0.

The one remaining wall-clock sleep is the "no plan found → sleep" backoff in the main loop. Shrunk from 10s to **5s** (typical cooldown duration) since the stuck detector now escalates before this matters. This is a polite-poll interval, not a health decision.

### Tracer interface

```python
class Tracer:
    def write_cycle(self, record: dict) -> None: ...
    def close(self) -> None: ...

class NullTracer(Tracer): ...
class FileTracer(Tracer):
    def __init__(self, path: str) -> None: ...
```

### JSONL record shape

```json
{
  "ts": "2026-05-15T10:23:01.234Z",
  "cycle": 1432,
  "state": {"x": 4, "y": 1, "hp": 87, "max_hp": 150, "gold": 1240, "level": 12,
            "inventory_used": 42, "inventory_max": 104, "bank_accessible": true,
            "task_code": "yellow_slime", "task_progress": 12, "task_total": 25},
  "cooldown_remaining_at_cycle_start": 0.0,
  "goals": [{"name": "FarmMonster(yellow_slime)", "priority": 47.3},
            {"name": "UpgradeEquipment", "priority": 35.0}],
  "selected_goal": "FarmMonster(yellow_slime)",
  "planner": {"nodes": 142, "depth": 4, "timed_out": false, "plan_len": 3},
  "action": "Fight(yellow_slime)",
  "outcome": "ok",
  "recovery": null,
  "suppressed_goals": []
}
```

When recovery fires: `recovery = {"signal": "GOAL_OSCILLATION", "level": 1, "action_taken": "deprioritize_goals", "details": {"goals": ["GoalA", "GoalB"], "cycles": 5}}`.

When stuck on a no-plan cycle: `action = "<no_plan>"`, `outcome = "no_plan"`, `planner` still populated.

### CLI flags

```python
@app.command("play")
def play(
    character: str = typer.Argument(...),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    dry_run: bool = typer.Option(False, "--dry-run"),
    trace: bool = typer.Option(False, "--trace", help="Write per-cycle JSONL to --trace-file"),
    trace_file: str | None = typer.Option(None, "--trace-file",
                                          help="Path for JSONL trace (default: play-trace-{character}-{timestamp}.jsonl)"),
) -> None: ...
```

Tracer is opened at startup, closed on exit (including KeyboardInterrupt via `try/finally` around the main loop).

## Phase E — Code quality cleanup

### Mypy: 67 errors → 0

| Class | Count | Fix pattern |
|---|---|---|
| Untyped generic containers (`dict`, `list`, `tuple`) | ~17 | Add type parameters — mechanical |
| API-response Union types (`.data` on `T \| ErrorResponseSchema \| None`) | ~40 | Apply `Action._raise_for_error(result, context)` consistently across every `execute()`; the helper already exists in `actions/base.py` |
| List variance in `gathering.py`, `farm_items.py` | 3 | Annotate the local as `list[Action]` from declaration |
| `WorldState \| None` dereferences in `player.py` | 4 | Tighten loop invariant: `assert self.state is not None` after `_full_refresh` |
| `PendingItemSchema.code` doesn't exist | 1 | **Real runtime bug** — read schema, use correct field |
| `ItemStats \| None` in `combat.py` | 1 | Add guard |

### Coverage: 94% → 98%

Targets the runtime-only paths the test suite doesn't currently exercise:

| File | Lines | What to test |
|---|---|---|
| `player.py:154, 161–167, 228–232, 275–281, 348–356, 360–364, 380–382` | HTTP 496 bank-block branch, achievement-resolution, dynamic delete-action construction, bank-retry resumption | Inject controlled `RuntimeError("HTTP 496:...")` into mocked `action.execute`; assert player state transitions |
| `delete.py:23, 26–30, 55, 58–61, 69` | `is_applicable`, cost weighting, repr | Unit tests parallel to other action tests |
| `unlock_bank.py:22, 25, 28, 31–38` | `relevant_actions` filter | Unit test for bank-locked + unlock-monster-known state |
| `consumable.py:80–86` | `execute` HTTP path | Mock use_item endpoint, assert transitions |
| `task.py:62–67, 119–124, 181–186` | Task state checks, reward logic | Direct unit tests per branch |

### Scope discipline

Cleanup respects file boundaries. No refactoring "while we're in there." The `_raise_for_error` helper exists; the cleanup just applies it consistently.

## Testing strategy

Five test layers, following TDD per project guidelines (`uv run pytest`).

**Layer 1 — Action unit tests** (`test_actions_npc_sell.py`, `test_actions_bank_expansion.py`, `test_actions_transition.py`, `test_actions_task_trade.py`, `test_actions_bank_gold.py`): per-action `is_applicable` truth-table, `apply` correctness, `cost` formula, `execute` against mocked endpoint with each error code.

**Layer 2 — Goal unit tests** (`test_goals_sell_inventory.py`, `test_goals_expand_bank.py`): `value` formula, `is_satisfied` boundary conditions, `relevant_actions` filter.

**Layer 3 — Detector unit tests** (`test_recovery.py`): feed synthetic `CycleRecord` sequences; assert returned `StuckSignal`. ~12 tests covering each rule + acknowledge behavior. Pure logic, no mocking.

**Layer 4 — Player-loop integration** (`test_player_recovery.py`): use the existing `fixtures.py` mocked client. Scenarios:
- Bank locked + full inventory + sellable items → bot reaches `NpcSellAction` not `DeleteItemAction`.
- 5 consecutive no-plan cycles → `NO_PROGRESS` → forced refresh → recovery.
- Two goals oscillating → both suppressed → third goal selected.
- Periodic refresh fires at action 20 and resets counter.

**Layer 5 — Tracer** (`test_tracer.py`): JSONL validity, all required fields present per cycle, `NullTracer` is a no-op.

### What's not tested
- No live-API integration tests (per v1 design — `--dry-run` is the live tool).
- No "run for 1 hour" tests — manual validation step in rollout, not part of suite.

## Build order

Six phases. Each phase is independently shippable; later phases build on earlier ones but don't gate them. Phase F is named here but **out of scope for this spec**.

| Phase | Scope | Estimate |
|---|---|---|
| A | NPC Sell foundation: `NpcSellAction`, `SellInventoryGoal`, GameData sell-prices, Delete cost re-weighting | ½ day |
| B | Remaining API actions: BankExpansion, MapTransition, TaskTrade, DepositGold/WithdrawGold, ExpandBankGoal | 1 day |
| C | Stuck-state detector + recovery ladder; player-loop integration | 1 day |
| D | Action-counted refresh policy; `Tracer` + `FileTracer` + CLI flags; delete `_refresh_if_stale` | ½ day |
| E | Mypy → 0; coverage → 98%; fix `PendingItemSchema.code` bug | 1 day |
| F | **Future**: autoregressive planning (offline trace analysis tools, learned costs, learned effects) | out of scope |

**Total Phase A–E**: ~4 days focused work.

**Validation gates** (each phase ends with):
- `uv run pytest` — green
- `uv run mypy src/artifactsmmo_cli/ai/` — clean within phase scope
- One manual `--dry-run` validation against a known scenario (e.g., Phase A: full inventory + bank locked → bot picks Sell)

## Forward-looking: autoregressive planning (Phase F)

Named here so the spec is explicit about the long-term direction. **Not implemented in this cycle.**

Current GOAP is memoryless — each cycle's plan ignores prior cycles. Costs are static estimates; effects are deterministic stubs. Real play diverges from both. The endgame is observation-conditioned planning that learns from past traces:

1. **Learned action costs**: empirical per-class median elapsed time replaces static `cost()` estimates.
2. **Learned effects / outcomes**: separate `expected_effect(state, history)` adjusts goal heuristics; `apply()` stays pure for A*.
3. **Pattern recognition**: offline analysis over JSONL traces first, online learning later.

**What this spec lays the groundwork for**:
- JSONL trace captures `(state, goal_set, selected_goal, action, next_state, outcome, planner_stats)` per cycle — that's the training signal.
- `StuckDetector` history buffer is the in-process version of the same data.
- `Action.cost(state, game_data)` / `Goal.value(state, game_data)` signatures already accept `state` + `game_data` — adding an optional `history: ActionHistory` parameter later is non-breaking.

**What this spec does NOT commit to**: no statistics accumulation in `WorldState`/`GameData`, no online learning, no model training, no deviation from forward A*. The trace exists; using it is Phase F.

## Open design decisions (revisit during implementation)

1. **Detector state_key bucketing granularity** — `task_progress // 10` may be too coarse for short tasks or too fine for long ones. Validate against first real trace, adjust if false positives observed.
2. **NpcSell vs Recycle preference** — both can clear inventory. Cost weighting handles the typical case (sell wins for high-`sell_price` items, recycle wins for craft-chain ingredients). For ambiguous items (low `sell_price` AND ingredient), the planner will pick lower-cost — needs verification on real inventory snapshots.
3. **Bank-expansion gold threshold** — `ExpandBankGoal` value triggers at 95% bank fill. Should it also factor in the rate at which gold can be earned, or just current gold? Defer to implementation.
4. **Wildcard goal list for `NO_PROGRESS` Level 2** — currently `RestoreHPGoal` + safest `FarmMonsterGoal`. May need to add `DepositInventoryGoal` if bank accessible. Tune from traces.

These are flagged for inline review during the implementation cycle, not blockers for the spec.
