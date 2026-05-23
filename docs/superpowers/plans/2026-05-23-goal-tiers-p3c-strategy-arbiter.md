# Goal Tiers — P3c: Strategy as Sole Arbiter — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Tier-3 strategy the single decision point: a guard ladder + two-band means + the objective step, composed by a driver that maps to the top *plannable* goal; retire `priorities.py`, `_select_goal`, the goals' `priority()` methods, and dead committed-target/FarmMonster/FarmItems plumbing.

**Architecture:** Two new pure modules `tiers/guards.py` (state-pressure interrupts + prerequisite gates, ordered ladder + predicates) and `tiers/means.py` (collect-reward + discretionary bands). Predicates take an explicit `SelectionContext` (player runtime flags) so `tiers/` stays free of `goals/` imports and the pure `StrategyEngine` stays objective-only. `strategy_driver.py` gains `select(...)` — the arbiter that walks guards → collect-reward → objective step → discretionary, returns the first goal that **plans**, and owns sticky commitment. `player.py` calls `decide()`+`select()` once per cycle; `_select_goal`/`priorities.py` go.

**Tech Stack:** Python 3.13, `uv run` (pytest, ruff line-length 120, mypy --strict), dataclasses/enum. Spec: `docs/superpowers/specs/2026-05-23-goal-tiers-p3c-strategy-arbiter-design.md`.

**Refinement vs spec:** The spec described `decide()` emitting guards/means inside `StrategyDecision`. Because guard/means predicates need player runtime context (bank flags, unlock level/monster, task-coin threshold) that the pure engine can't see, the **driver** composes guards/means (from the new pure modules) with `decide()`'s objective step instead. End behavior is identical; layering is cleaner (`tiers/` imports no `goals/`).

---

## File Structure

- `src/artifactsmmo_cli/ai/tiers/guards.py` — CREATE: `GuardKind` enum, `GUARD_ORDER`, threshold constants, `SelectionContext` frozen dataclass, `active_guards(state, game_data, history, ctx) -> list[GuardKind]`.
- `src/artifactsmmo_cli/ai/tiers/means.py` — CREATE: `MeansKind` enum, `COLLECT_REWARD_ORDER`/`DISCRETIONARY_ORDER`, `active_means(state, game_data, history, ctx) -> tuple[list[MeansKind], list[MeansKind]]`.
- `src/artifactsmmo_cli/ai/strategy_driver.py` — MODIFY: add `map_guard`, `map_means`, `select(...)` arbiter + sticky commitment; drop `MetaGoalAdapter.priority_band`/`STRATEGY_BAND`/`FALLBACK_BAND`.
- `src/artifactsmmo_cli/ai/player.py` — MODIFY: rewire cycle to `decide()`+`select()`; delete `_select_goal`, committed-target probe; re-source `crafting_target` from `chosen_step`; delete `_gating_skill_targets`.
- `src/artifactsmmo_cli/ai/goals/*.py` — MODIFY: remove `priority()` overrides (keep `value`/`is_satisfied`/`desired_state`/`relevant_actions`/`max_depth`/`preemptive`).
- DELETE: `src/artifactsmmo_cli/ai/priorities.py`, `src/artifactsmmo_cli/ai/goals/farm_items.py`; remove `FarmMonsterGoal` from `goals/combat.py`.
- Tests: new `tests/test_ai/test_tiers_guards.py`, `test_tiers_means.py`; extend `test_strategy_driver.py`, `test_player.py`; delete `test_priorities.py`, FarmMonster/FarmItems tests, `_select_goal` tests.

`SelectionContext` (defined in `guards.py`, imported by `means.py` + driver):
```python
@dataclass(frozen=True)
class SelectionContext:
    bank_accessible: bool
    bank_required_level: int
    bank_unlock_monster: str | None
    initial_xp: int               # UnlockBank trigger: xp hasn't advanced since
    task_exchange_min_coins: int
    combat_monster: str | None    # winnable farm target for a ReachCharLevel step
```

Trigger thresholds (from the audited goals): HP `< 0.25`; deposit `used_fraction >= 0.80` (was ramp-start 0.5 / ceiling 0.80 — collapses to the ceiling threshold); discard high `>= 0.85`, critical `>= 0.95`; bank-expand `>= 0.95`; sell pressure reuses `>= 0.85`.

---

### Task 1: Guard ladder — `tiers/guards.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/guards.py`
- Test: `tests/test_ai/test_tiers_guards.py`

Helpers reused from existing modules: `overstocked_items(state, game_data)` (in `goals/discard_overstock.py` — import the module-level function), `select_bank_deposits(state, game_data)` (in `ai/bank_selection.py`). Verify their exact import paths before writing (grep `def overstocked_items`, `def select_bank_deposits`). Both are pure.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_tiers_guards.py`:

```python
"""Tests for the guard ladder (state-pressure interrupts + prerequisite gates)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import (
    GUARD_ORDER,
    GuardKind,
    SelectionContext,
    active_guards,
)
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def test_hp_critical_fires_below_quarter_and_outranks_all():
    state = make_state(hp=10, max_hp=100)            # 10% < 0.25
    guards = active_guards(state, GameData(), None, _ctx())
    assert guards[0] is GuardKind.HP_CRITICAL


def test_no_guards_when_calm():
    state = make_state(hp=100, max_hp=100, inventory={}, inventory_max=20)
    assert active_guards(state, GameData(), None, _ctx(bank_accessible=True)) == []


def test_deposit_full_fires_at_eighty_percent():
    # 16/20 = 0.80; needs a sellable/depositable item present.
    gd = GameData()
    gd._item_stats = {}
    state = make_state(hp=100, max_hp=100, inventory={"copper_ore": 16}, inventory_max=20,
                       bank_items={})
    guards = active_guards(state, gd, None, _ctx(bank_accessible=True))
    assert GuardKind.DEPOSIT_FULL in guards


def test_guard_order_is_ladder_order():
    # When several fire, they come back in GUARD_ORDER sequence.
    state = make_state(hp=10, max_hp=100, inventory={"x": 20}, inventory_max=20, bank_items={})
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=True))
    assert guards == [g for g in GUARD_ORDER if g in guards]
```

(Adjust the deposit test once `select_bank_deposits`' real signature is confirmed; if it needs item stats to return a deposit, give the inventory item an `ItemStats` entry so the deposit set is non-empty.)

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_tiers_guards.py -v`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.tiers.guards`.

- [ ] **Step 3: Implement `guards.py`**

```python
"""Guard tier: state-pressure interrupts + prerequisite gates that preempt every
instrumental means. The only surviving priority ladder, scoped to guards.

Pure: predicates read state/game_data/history + an explicit SelectionContext
(player runtime flags). No goals/ imports — the driver maps GuardKind to goals."""

from dataclasses import dataclass
from enum import Enum

from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.discard_overstock import overstocked_items
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

CRITICAL_HP_FRACTION = 0.25
DEPOSIT_FULL_FRACTION = 0.80
DISCARD_HIGH_FRACTION = 0.85
DISCARD_CRITICAL_FRACTION = 0.95
MAX_ACHIEVABLE_GAP = 5


@dataclass(frozen=True)
class SelectionContext:
    bank_accessible: bool
    bank_required_level: int
    bank_unlock_monster: str | None
    initial_xp: int
    task_exchange_min_coins: int
    combat_monster: str | None


class GuardKind(Enum):
    HP_CRITICAL = "hp_critical"
    BANK_UNLOCK = "bank_unlock"
    REACH_UNLOCK_LEVEL = "reach_unlock_level"
    DISCARD_CRITICAL = "discard_critical"
    DEPOSIT_FULL = "deposit_full"
    DISCARD_HIGH = "discard_high"


GUARD_ORDER: tuple[GuardKind, ...] = (
    GuardKind.HP_CRITICAL,
    GuardKind.BANK_UNLOCK,
    GuardKind.REACH_UNLOCK_LEVEL,
    GuardKind.DISCARD_CRITICAL,
    GuardKind.DEPOSIT_FULL,
    GuardKind.DISCARD_HIGH,
)


def _used_fraction(state: WorldState) -> float:
    if state.inventory_max <= 0:
        return 0.0
    return state.inventory_used / state.inventory_max


def _fires(kind: GuardKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is GuardKind.HP_CRITICAL:
        return state.hp_percent < CRITICAL_HP_FRACTION
    if kind is GuardKind.BANK_UNLOCK:
        if not (ctx.bank_unlock_monster is not None and not ctx.bank_accessible):
            return False
        if state.xp > ctx.initial_xp:                       # unlock fight already done
            return False
        target_level = game_data.monster_level(ctx.bank_unlock_monster)
        return target_level == 0 or state.level >= target_level - 1   # attemptable
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return (ctx.bank_required_level > 0
                and state.level < ctx.bank_required_level
                and ctx.bank_required_level - state.level <= MAX_ACHIEVABLE_GAP)
    if kind is GuardKind.DISCARD_CRITICAL:
        return bool(overstocked_items(state, game_data)) and _used_fraction(state) >= DISCARD_CRITICAL_FRACTION
    if kind is GuardKind.DEPOSIT_FULL:
        return (ctx.bank_accessible and _used_fraction(state) >= DEPOSIT_FULL_FRACTION
                and bool(select_bank_deposits(state, game_data)))
    if kind is GuardKind.DISCARD_HIGH:
        return bool(overstocked_items(state, game_data)) and _used_fraction(state) >= DISCARD_HIGH_FRACTION
    return False


def active_guards(state: WorldState, game_data: GameData,
                  history: LearningStore | None, ctx: SelectionContext) -> list[GuardKind]:
    """Triggered guards in ladder (preemption) order."""
    return [k for k in GUARD_ORDER if _fires(k, state, game_data, history, ctx)]
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_guards.py -v`
Expected: PASS. Then `uv run ruff check src/artifactsmmo_cli/ai/tiers/guards.py && uv run mypy src/artifactsmmo_cli/ai/tiers/guards.py` — clean. Confirm `tiers/guards.py` imports no `goals/` symbol except the pure `overstocked_items` (acceptable — it is a pure helper, not a Goal). If importing from `goals/discard_overstock` is judged a layering violation, copy the small `overstocked_items` predicate into `guards.py` instead; decide during implementation and note it.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/guards.py tests/test_ai/test_tiers_guards.py
git commit -m "feat(ai): guard ladder for the strategy arbiter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: Means bands — `tiers/means.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/tiers/means.py`
- Test: `tests/test_ai/test_tiers_means.py`

Means trigger conditions (from the audited goals): `CLAIM_PENDING` = `state.pending_items` truthy; `COMPLETE_TASK` = task held and `task_progress >= task_total > 0`; `SELL_PRESSURED` = `used_fraction >= 0.85` and a held item has `game_data.npcs_buying_item(code)`; `LOW_YIELD_CANCEL`/`TASK_CANCEL` = delegate to the existing pure predicates (`project_task_completion`/`task_decision` — reuse, do not reimplement); `ACCEPT_TASK` = no `task_code`; `TASK_EXCHANGE` = total `tasks_coin >= ctx.task_exchange_min_coins`; `SELL_IDLE` = sellable stock present and `used_fraction < 0.85`; `BANK_EXPAND` = `bank_accessible` and bank-fill `>= 0.95` and `gold >= next_expansion_cost`.

For the cancel predicates, import and call the same functions the goals use (`task_decision` from `ai/task_decision.py`, `project_task_completion` from `learning/projections.py`) so behavior matches exactly. Confirm their signatures by grep before writing.

- [ ] **Step 1: Write the failing test**

Create `tests/test_ai/test_tiers_means.py`:

```python
"""Tests for the means bands (collect-reward + discretionary)."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import (
    COLLECT_REWARD_ORDER,
    DISCRETIONARY_ORDER,
    MeansKind,
    active_means,
)
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def test_complete_task_in_collect_reward_when_task_done():
    state = make_state(task_code="cyclops", task_type="monsters", task_total=5, task_progress=5)
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.COMPLETE_TASK in collect


def test_accept_task_in_discretionary_when_no_task():
    state = make_state(task_code=None)
    _, discretionary = active_means(state, GameData(), None, _ctx())
    assert MeansKind.ACCEPT_TASK in discretionary


def test_claim_pending_fires_with_pending_items():
    state = make_state(pending_items=(("id1", "copper_ore"),))
    collect, _ = active_means(state, GameData(), None, _ctx())
    assert MeansKind.CLAIM_PENDING in collect


def test_sell_pressured_vs_idle_mutually_exclusive_on_bag():
    gd = GameData()
    gd._npc_sell_prices = {"merchant": {"copper_ore": 5}}
    pressured = make_state(inventory={"copper_ore": 18}, inventory_max=20)   # 0.90
    idle = make_state(inventory={"copper_ore": 2}, inventory_max=20)          # 0.10
    pc, _ = active_means(pressured, gd, None, _ctx())
    _, idd = active_means(idle, gd, None, _ctx())
    assert MeansKind.SELL_PRESSURED in pc
    assert MeansKind.SELL_IDLE in idd


def test_band_order_matches_declared_order():
    state = make_state(task_code=None, pending_items=(("id", "x"),))
    collect, discretionary = active_means(state, GameData(), None, _ctx())
    assert collect == [m for m in COLLECT_REWARD_ORDER if m in collect]
    assert discretionary == [m for m in DISCRETIONARY_ORDER if m in discretionary]
```

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_tiers_means.py -v`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.tiers.means`.

- [ ] **Step 3: Implement `means.py`**

```python
"""Means bands: instrumental/opportunistic actions ranked under the objective
step. Collect-reward sits just below guards; discretionary just below the
objective step. Pure predicates over state/game_data/history + SelectionContext."""

from enum import Enum

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import project_task_completion
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.task_decision import TaskDecision, task_decision
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

SELL_PRESSURE_FRACTION = 0.85
BANK_EXPAND_FILL = 0.95
LOW_YIELD_CONFIDENCE = 0.5
LOW_YIELD_MARGIN = 1.5


class MeansKind(Enum):
    CLAIM_PENDING = "claim_pending"
    COMPLETE_TASK = "complete_task"
    SELL_PRESSURED = "sell_pressured"
    LOW_YIELD_CANCEL = "low_yield_cancel"
    TASK_CANCEL = "task_cancel"
    ACCEPT_TASK = "accept_task"
    TASK_EXCHANGE = "task_exchange"
    SELL_IDLE = "sell_idle"
    BANK_EXPAND = "bank_expand"


COLLECT_REWARD_ORDER: tuple[MeansKind, ...] = (
    MeansKind.CLAIM_PENDING, MeansKind.COMPLETE_TASK, MeansKind.SELL_PRESSURED,
    MeansKind.LOW_YIELD_CANCEL, MeansKind.TASK_CANCEL,
)
DISCRETIONARY_ORDER: tuple[MeansKind, ...] = (
    MeansKind.ACCEPT_TASK, MeansKind.TASK_EXCHANGE, MeansKind.SELL_IDLE, MeansKind.BANK_EXPAND,
)


def _used_fraction(state: WorldState) -> float:
    return state.inventory_used / state.inventory_max if state.inventory_max > 0 else 0.0


def _has_sellable(state: WorldState, game_data: GameData) -> bool:
    return any(qty > 0 and game_data.npcs_buying_item(code)
               for code, qty in state.inventory.items())


def _tasks_coin_total(state: WorldState) -> int:
    inv = state.inventory.get("tasks_coin", 0)
    bank = (state.bank_items or {}).get("tasks_coin", 0)
    return inv + bank


def _low_yield_fires(state: WorldState, game_data: GameData, history: LearningStore | None) -> bool:
    # Mirror LowYieldCancelGoal: needs a held task + history; reuse project_task_completion.
    if not state.task_code or history is None:
        return False
    projection = project_task_completion(state, history)
    return projection.confidence >= LOW_YIELD_CONFIDENCE and projection.alternative_pays_more(LOW_YIELD_MARGIN)


def _fires(kind: MeansKind, state: WorldState, game_data: GameData,
           history: LearningStore | None, ctx: SelectionContext) -> bool:
    if kind is MeansKind.CLAIM_PENDING:
        return bool(state.pending_items)
    if kind is MeansKind.COMPLETE_TASK:
        return bool(state.task_code) and state.task_total > 0 and state.task_progress >= state.task_total
    if kind is MeansKind.SELL_PRESSURED:
        return _used_fraction(state) >= SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)
    if kind is MeansKind.LOW_YIELD_CANCEL:
        return _low_yield_fires(state, game_data, history)
    if kind is MeansKind.TASK_CANCEL:
        return (bool(state.task_code) and state.task_total > 0
                and task_decision(state, game_data, history) == TaskDecision.PIVOT)
    if kind is MeansKind.ACCEPT_TASK:
        return not state.task_code
    if kind is MeansKind.TASK_EXCHANGE:
        return _tasks_coin_total(state) >= ctx.task_exchange_min_coins
    if kind is MeansKind.SELL_IDLE:
        return _used_fraction(state) < SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)
    if kind is MeansKind.BANK_EXPAND:
        if not ctx.bank_accessible or game_data._bank_capacity <= 0:
            return False
        fill = len(state.bank_items or {}) / game_data._bank_capacity
        return fill >= BANK_EXPAND_FILL and state.gold >= game_data._next_expansion_cost
    return False


def active_means(state: WorldState, game_data: GameData, history: LearningStore | None,
                 ctx: SelectionContext) -> tuple[list[MeansKind], list[MeansKind]]:
    """(collect_reward, discretionary) — triggered means in declared band order."""
    collect = [k for k in COLLECT_REWARD_ORDER if _fires(k, state, game_data, history, ctx)]
    discretionary = [k for k in DISCRETIONARY_ORDER if _fires(k, state, game_data, history, ctx)]
    return collect, discretionary
```

**Before writing:** confirm the real signatures/return shapes of `task_decision`/`TaskDecision` (`ai/task_decision.py`) and `project_task_completion` (`learning/projections.py`). The snippet assumes `task_decision(state, game_data, history) -> TaskDecision` with a `PIVOT` member, and a projection object with `.confidence` plus a way to compare the alternative rate. If `project_task_completion`'s object lacks an `alternative_pays_more` helper, replicate `LowYieldCancelGoal`'s exact comparison inline (current/alternative `char_xp_per_cycle` with the `>= current*1.5` and zero-fast-path rules). Match the goal's logic precisely so the means predicate and the mapped goal agree.

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_tiers_means.py -v`
Expected: PASS. Then ruff + mypy on `means.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/tiers/means.py tests/test_ai/test_tiers_means.py
git commit -m "feat(ai): means bands for the strategy arbiter

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Driver arbiter — `select` + `map_guard`/`map_means` + sticky commitment

**Files:**
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py`
- Test: `tests/test_ai/test_strategy_driver.py`

The driver is the only layer that imports both `tiers/` and `goals/`. It maps `GuardKind`/`MeansKind` to goal instances (using `SelectionContext` for the runtime-flag constructors), composes the ordered candidate list, and returns the first that plans. Sticky commitment is held by the driver instance.

Goal constructors (from the audit): `RestoreHPGoal()`, `DiscardOverstockGoal(game_data=gd)`, `UnlockBankGoal(bank_locked=not ctx.bank_accessible, initial_xp=ctx.initial_xp, target_monster=ctx.bank_unlock_monster)`, `ReachUnlockLevelGoal(target_level=ctx.bank_required_level)`, `DepositInventoryGoal(bank_accessible=ctx.bank_accessible, game_data=gd)`, `ClaimPendingGoal()`, `CompleteTaskGoal()`, `SellInventoryGoal(bank_accessible=ctx.bank_accessible)`, `LowYieldCancelGoal()`, `TaskCancelGoal()`, `AcceptTaskGoal()`, `TaskExchangeGoal(min_coins=ctx.task_exchange_min_coins)`, `ExpandBankGoal(bank_accessible=ctx.bank_accessible, game_data=gd)`. The objective step maps via the existing `strategy_goal` inner-goal logic (gear→UpgradeEquipment, material→GatherMaterials, skill→LevelSkill, char-level→GrindCharacterXP(ctx.combat_monster)).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_strategy_driver.py` (create if absent). Use a real planner + small world so "plans" is real. Reuse fixtures; the driver needs `planner`, `actions`, `history`.

```python
from artifactsmmo_cli.ai.goals.survival import RestoreHPGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, map_guard, map_means
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind


def _ctx(**kw):
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw); return SelectionContext(**base)


def test_map_guard_hp_critical_returns_restore_hp():
    g = map_guard(GuardKind.HP_CRITICAL, GameData(), _ctx())
    assert isinstance(g, RestoreHPGoal)


def test_map_means_accept_task_returns_accept_goal():
    g = map_means(MeansKind.ACCEPT_TASK, GameData(), _ctx())
    assert repr(g) == "AcceptTask"


def test_select_guard_preempts_means(...):
    # Build a state where HP-critical fires AND a means is available; assert the
    # arbiter returns the RestoreHP goal (guard) over any means.
    ...


def test_select_falls_through_unplannable_to_next_candidate(...):
    # Top candidate cannot plan (no actions); arbiter returns the next plannable.
    ...


def test_select_sticky_keeps_committed_means_until_satisfied(...):
    # Two cycles: commit to a means; while it still fires and isn't satisfied and
    # no guard preempts, the same goal is returned.
    ...
```

Flesh out the `...` tests using the real `GOAPPlanner`, a `GameData` with a couple of monsters/resources, and a `make_state`. Model them on the existing P3b `test_player.py` build-goals tests (real planner, real goals). The arbiter under test is real; only inputs are constructed.

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -v`
Expected: FAIL — `ImportError: cannot import name 'StrategyArbiter'/'map_guard'/'map_means'`.

- [ ] **Step 3: Implement the driver**

Replace the `MetaGoalAdapter` band machinery. `map_guard`/`map_means` are module functions; `StrategyArbiter` is a small stateful class holding sticky commitment + the planner.

```python
from artifactsmmo_cli.ai.goals.claim_pending import ClaimPendingGoal
from artifactsmmo_cli.ai.goals.combat import AcceptTaskGoal, CompleteTaskGoal
from artifactsmmo_cli.ai.goals.discard_overstock import DiscardOverstockGoal
from artifactsmmo_cli.ai.goals.expand_bank import ExpandBankGoal
from artifactsmmo_cli.ai.goals.low_yield_cancel import LowYieldCancelGoal
from artifactsmmo_cli.ai.goals.reach_unlock_level import ReachUnlockLevelGoal
from artifactsmmo_cli.ai.goals.sell_inventory import SellInventoryGoal
from artifactsmmo_cli.ai.goals.survival import DepositInventoryGoal, RestoreHPGoal
from artifactsmmo_cli.ai.goals.task_cancel import TaskCancelGoal
from artifactsmmo_cli.ai.goals.task_exchange import TaskExchangeGoal
from artifactsmmo_cli.ai.goals.unlock_bank import UnlockBankGoal
from artifactsmmo_cli.ai.tiers.guards import GuardKind, SelectionContext, active_guards
from artifactsmmo_cli.ai.tiers.means import MeansKind, active_means
# (existing imports: Action, GameData, Goal, GatherMaterialsGoal, GrindCharacterXPGoal,
#  LevelSkillGoal, UpgradeEquipmentGoal, MetaGoal/ObtainItem/ReachCharLevel/ReachSkillLevel,
#  WorldState, ITEM_TYPE_TO_SLOTS, LearningStore, GOAPPlanner)


def map_guard(kind: GuardKind, game_data: GameData, ctx: SelectionContext) -> Goal:
    if kind is GuardKind.HP_CRITICAL:
        return RestoreHPGoal()
    if kind in (GuardKind.DISCARD_CRITICAL, GuardKind.DISCARD_HIGH):
        return DiscardOverstockGoal(game_data=game_data)
    if kind is GuardKind.BANK_UNLOCK:
        return UnlockBankGoal(bank_locked=not ctx.bank_accessible, initial_xp=ctx.initial_xp,
                              target_monster=ctx.bank_unlock_monster)
    if kind is GuardKind.REACH_UNLOCK_LEVEL:
        return ReachUnlockLevelGoal(target_level=ctx.bank_required_level)
    if kind is GuardKind.DEPOSIT_FULL:
        return DepositInventoryGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
    raise ValueError(f"unmapped guard {kind}")


def map_means(kind: MeansKind, game_data: GameData, ctx: SelectionContext) -> Goal:
    if kind is MeansKind.CLAIM_PENDING:
        return ClaimPendingGoal()
    if kind is MeansKind.COMPLETE_TASK:
        return CompleteTaskGoal()
    if kind in (MeansKind.SELL_PRESSURED, MeansKind.SELL_IDLE):
        return SellInventoryGoal(bank_accessible=ctx.bank_accessible)
    if kind is MeansKind.LOW_YIELD_CANCEL:
        return LowYieldCancelGoal()
    if kind is MeansKind.TASK_CANCEL:
        return TaskCancelGoal()
    if kind is MeansKind.ACCEPT_TASK:
        return AcceptTaskGoal()
    if kind is MeansKind.TASK_EXCHANGE:
        return TaskExchangeGoal(min_coins=ctx.task_exchange_min_coins)
    if kind is MeansKind.BANK_EXPAND:
        return ExpandBankGoal(bank_accessible=ctx.bank_accessible, game_data=game_data)
    raise ValueError(f"unmapped means {kind}")


def objective_step_goal(step: MetaGoal | None, state: WorldState, game_data: GameData,
                        ctx: SelectionContext) -> Goal | None:
    """Map the strategy's objective chosen_step to a planner goal (was strategy_goal)."""
    if isinstance(step, ObtainItem):
        stats = game_data.item_stats(step.code)
        slots = ITEM_TYPE_TO_SLOTS.get(stats.type_) if stats is not None else None
        if slots:
            return UpgradeEquipmentGoal(initial_equipment=state.equipment,
                                        committed_target=(step.code, slots[0]))
        return GatherMaterialsGoal(target_item=step.code, needed={step.code: step.quantity})
    if isinstance(step, ReachSkillLevel):
        return LevelSkillGoal(skill_name=step.skill, target_level=step.level)
    if isinstance(step, ReachCharLevel):
        if ctx.combat_monster is None:
            return None
        return GrindCharacterXPGoal(target_monster=ctx.combat_monster, initial_xp=state.xp)
    return None


class StrategyArbiter:
    """Composes guards + collect-reward + objective step + discretionary into one
    ordered candidate list and returns the first goal that PLANS, with sticky
    commitment on the chosen means (guards bypass stickiness)."""

    def __init__(self, planner: GOAPPlanner, history: LearningStore | None) -> None:
        self._planner = planner
        self._history = history
        self._committed_repr: str | None = None
        self.goals_tried: list[dict[str, object]] = []

    def _plans(self, goal: Goal, state, game_data, actions) -> list[Action]:
        plan = self._planner.plan(state, goal, actions, game_data, self._history)
        s = self._planner.last_stats
        self.goals_tried.append({"goal": repr(goal), "nodes": s.nodes_explored,
                                 "depth": s.max_depth_reached, "timed_out": s.timed_out,
                                 "plan_len": len(plan)})
        return plan

    def select(self, decision, state, game_data, actions, ctx):
        self.goals_tried = []
        guards = active_guards(state, game_data, self._history, ctx)
        collect, discretionary = active_means(state, game_data, self._history, ctx)

        # Ordered (goal, is_means) candidates.
        candidates: list[tuple[Goal, bool]] = []
        candidates += [(map_guard(g, game_data, ctx), False) for g in guards]
        candidates += [(map_means(m, game_data, ctx), True) for m in collect]
        step_goal = objective_step_goal(decision.chosen_step, state, game_data, ctx)
        if step_goal is not None:
            candidates.append((step_goal, True))
        candidates += [(map_means(m, game_data, ctx), True) for m in discretionary]

        # Sticky: if the committed means is still in the means candidates, not
        # satisfied, and no guard precedes it, keep it.
        if self._committed_repr is not None:
            preceding_guard = any(not is_means for goal, is_means in candidates
                                  if repr(goal) != self._committed_repr
                                  and _precedes(candidates, repr(goal), self._committed_repr))
            for goal, is_means in candidates:
                if is_means and repr(goal) == self._committed_repr and not goal.is_satisfied(state) \
                        and not preceding_guard:
                    plan = self._plans(goal, state, game_data, actions)
                    if plan:
                        return goal, plan, self.goals_tried

        for goal, is_means in candidates:
            plan = self._plans(goal, state, game_data, actions)
            if plan:
                self._committed_repr = repr(goal) if is_means else self._committed_repr
                return goal, plan, self.goals_tried
        return None, [], self.goals_tried
```

Add a small `_precedes(candidates, a_repr, b_repr) -> bool` helper (index of `a_repr` < index of `b_repr` in `candidates`). Keep `strategy_goal`/`MetaGoalAdapter`/`STRATEGY_BAND`/`FALLBACK_BAND` **only** until Task 5 removes their last caller, then delete in Task 5. (If nothing else imports them after Task 5, delete them in Task 5's commit.)

Confirm `GOAPPlanner.plan` signature and `last_stats` fields against `ai/planner.py` before writing (the audit shows `plan(state, goal, actions, game_data, history)` and `last_stats.nodes_explored/max_depth_reached/timed_out`).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_strategy_driver.py -v` — PASS. ruff + mypy on `strategy_driver.py` — clean.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/strategy_driver.py tests/test_ai/test_strategy_driver.py
git commit -m "feat(ai): StrategyArbiter composes guards+means+step (top-plannable, sticky)

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Player cutover — call decide()+arbiter once; retire `_select_goal`; re-source crafting_target

**Files:**
- Modify: `src/artifactsmmo_cli/ai/player.py`
- Test: `tests/test_ai/test_player.py`

The cycle currently: `_build_goals()` → compute `goal_priorities` → sort → `_select_goal(...)`. Replace with: build `state`, build `actions`, build `SelectionContext`, `decision = self._strategy.decide(state, game_data)`, re-source `crafting_target` from `decision.chosen_step`, `goal, plan, goals_tried = self._arbiter.select(decision, state, game_data, actions, ctx)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_ai/test_player.py`:

```python
def test_cycle_uses_arbiter_not_select_goal():
    # The player exposes a StrategyArbiter and no _select_goal.
    player = GamePlayer(character="hero")
    assert not hasattr(player, "_select_goal")
    assert hasattr(player, "_arbiter")


def test_crafting_target_resourced_from_objective_step(self):
    # When the strategy's chosen_step is an ObtainItem(code), state.crafting_target
    # is set to that code; otherwise None.
    ...  # build a player+gd where decide() yields an ObtainItem step; assert
         # the post-decide state.crafting_target == that code.
```

Curate the existing build-goals tests: `TestBuildGoals` assertions that referenced `Strategy(...)` adapters, `FALLBACK_BAND`, `MetaGoalAdapter`, and grind-target lists must move to the arbiter's selection contract (the cycle now returns a single goal). Rewrite them to assert on the goal the arbiter selects given a constructed state (e.g. bag-full → DepositInventory; done-task → CompleteTask; healthy+gap → the objective step goal; idle → AcceptTask). Use the same real-stat approach as P3b.1 (no mocking the arbiter; stub only `_path_aligned_monster` if needed for the combat target).

- [ ] **Step 2: Run to verify fail**

Run: `uv run pytest tests/test_ai/test_player.py -k "arbiter or crafting_target" -v`
Expected: FAIL — arbiter attribute missing / `_select_goal` still present.

- [ ] **Step 3: Implement the cutover**

1. In `GamePlayer.__init__`, construct the arbiter once: `self._arbiter = StrategyArbiter(self.planner, history)` (after `self.planner`/`history` are set). Remove `self._committed_goal_name` and `self._committed_upgrade_target`.
2. Replace the cycle block (audit lines ~284–305) that built `goal_priorities` and called `_select_goal` with:

```python
        actions = self._build_actions()
        ctx = self._selection_context()
        decision = self._strategy.decide(state, game_data)
        # Re-source the committed craft target from the objective step so deposit
        # protection / yield scoring still know what we're gathering for.
        step = decision.chosen_step
        crafting_target = step.code if isinstance(step, ObtainItem) else None
        self.state = state = replace(state, crafting_target=crafting_target)
        selected_goal, plan, goals_tried = self._arbiter.select(
            decision, state, game_data, actions, ctx)
```

3. Add `_selection_context()` building `SelectionContext` from the player's runtime flags:

```python
    def _selection_context(self) -> SelectionContext:
        assert self.state is not None
        return SelectionContext(
            bank_accessible=self._bank_accessible,
            bank_required_level=self._bank_required_level,
            bank_unlock_monster=self._bank_unlock_monster,
            initial_xp=self.state.xp,
            task_exchange_min_coins=self._task_exchange_min_coins,
            combat_monster=self._winnable_farm_target(),
        )
```

4. Add `_winnable_farm_target()` wrapping the P3b.1 gate (path-aligned, gated by `_is_winnable`, else `_pick_winnable_monster`) — extract the existing `farm_target` computation from `_build_goals` into this method (it returns the gated monster or None).
5. Delete `_build_goals` entirely (its goal-list, committed-target probe, and strategy/fallback append are all superseded). Move any kept setup (e.g. the bank-retry `_blockers.clear("bank")` logic that lived in `_build_goals`) into the cycle before the decide() call.
6. Delete `_select_goal` (audit lines 1252–1329), `_upgrade_target_still_valid` (1161), `_gating_skill_targets` (1215).
7. Update `_emit_trace` to reuse the already-computed `decision` instead of calling `decide()` again (pass `decision` in or cache it on `self` for the trace), eliminating the double `decide()` call.
8. Imports: add `from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter`; `from artifactsmmo_cli.ai.tiers.guards import SelectionContext`; `from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem` (or via tiers export). Remove now-unused imports (`UpgradeEquipmentGoal` if only the probe used it, `GrindCharacterXPGoal`/`MetaGoalAdapter`/`STRATEGY_BAND`/`FALLBACK_BAND`/`strategy_goal` if no longer referenced).

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_ai/test_player.py -v` — PASS (curated). ruff + mypy on `player.py` — clean (mypy on `player.py` only; the repo has a pre-existing 131-error baseline in unrelated files — do not regress `player.py`).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/player.py tests/test_ai/test_player.py
git commit -m "feat(ai): player cycle uses StrategyArbiter; retire _select_goal + committed-target probe

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Delete `priorities.py`; remove `priority()` from goals; delete `MetaGoalAdapter`/band constants

**Files:**
- Delete: `src/artifactsmmo_cli/ai/priorities.py`
- Modify: every goal file that defined `priority()` or imported `priorities`; `strategy_driver.py` (drop `MetaGoalAdapter`/`strategy_goal`/`STRATEGY_BAND`/`FALLBACK_BAND` if unreferenced)
- Test: delete `tests/test_ai/test_priorities.py`; adjust any test asserting a goal's `priority()`

- [ ] **Step 1: Establish the failing/red state**

Run: `grep -rln "priorities" src/artifactsmmo_cli/` to list every importer (audit: discard_overstock, farm_items, gathering, grind_character_xp, level_skill, low_yield_cancel, progression, reach_unlock_level, survival, player). Run `uv run pytest tests/test_ai/test_priorities.py -q` to confirm it currently passes (it will be deleted).

- [ ] **Step 2: Remove `priority()` overrides + `priorities` imports**

For each goal class that defines `priority(self, ...)`, delete the method (the base `Goal.priority` default → `self.value(...)` remains; selection no longer reads it, but `value()` is still used as the planner heuristic). Remove the `from artifactsmmo_cli.ai import priorities` / `import priorities` line. Where a `priorities.X` constant was used inside `value()` (e.g. `RestoreHPGoal.CRITICAL_HP_VALUE = priorities.HP_CRITICAL`, `FarmItems` value math), inline the literal with a local module constant + a comment (these files: `survival.py`, `discard_overstock.py`, `reach_unlock_level.py`, `low_yield_cancel.py`, `gathering.py`, `grind_character_xp.py`, `level_skill.py`, `progression.py`). `farm_items.py` is deleted in Task 6 so skip it here.

For each edited goal, run its test file (`uv run pytest tests/test_ai/test_<goal>.py -q`) and fix any test that asserted `.priority(...)` — re-point to `.value(...)` or delete the assertion if it only verified the retired selection number.

- [ ] **Step 3: Delete priorities.py + its test**

```bash
git rm src/artifactsmmo_cli/ai/priorities.py tests/test_ai/test_priorities.py
```

- [ ] **Step 4: Drop dead driver band machinery**

In `strategy_driver.py`, if `grep -rn "MetaGoalAdapter\|strategy_goal\|STRATEGY_BAND\|FALLBACK_BAND" src tests` shows no remaining callers after Task 4, delete `MetaGoalAdapter`, `strategy_goal`, `STRATEGY_BAND`, `FALLBACK_BAND` and their tests.

- [ ] **Step 5: Verify**

Run: `grep -rn "import priorities\|from artifactsmmo_cli.ai.priorities\|from artifactsmmo_cli.ai import priorities" src tests` → no output. Run `uv run pytest -q` → all pass. ruff + mypy on changed goal files — clean.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "refactor(ai): retire priorities.py and goal priority() methods

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Delete dead goals — FarmItemsGoal, FarmMonsterGoal

**Files:**
- Delete: `src/artifactsmmo_cli/ai/goals/farm_items.py`
- Modify: `src/artifactsmmo_cli/ai/goals/combat.py` (remove `FarmMonsterGoal` class only — keep `AcceptTaskGoal`/`CompleteTaskGoal`)
- Test: delete the FarmItems/FarmMonster test files/cases

- [ ] **Step 1: Confirm no live importers**

Run: `grep -rn "FarmItemsGoal\|FarmMonsterGoal\|farm_items" src tests`. Expected live references only in: their own files, their tests, and (possibly) `learning/projections.py` which references `FarmMonster(*)`/`FarmItems` action reprs as *strings* for win-rate lookup — those are string literals, not class imports, and stay. Confirm no `from ...goals.farm_items import` / `from ...goals.combat import FarmMonsterGoal` in src outside tests.

- [ ] **Step 2: Delete FarmItemsGoal**

```bash
git rm src/artifactsmmo_cli/ai/goals/farm_items.py
```
Remove its test file (`tests/test_ai/test_farm_items*.py` — confirm exact name via `ls tests/test_ai | grep farm`).

- [ ] **Step 3: Remove FarmMonsterGoal from combat.py**

Delete the `class FarmMonsterGoal(...)` block (audit: `goals/combat.py:23`) and any now-unused imports it alone needed (e.g. `best_equipped_level`, `learned_priority_bonus`) — verify each is unused elsewhere in the file before removing. Remove FarmMonster test cases (`tests/test_ai/test_combat_goals*` / wherever `FarmMonsterGoal` is tested — grep).

- [ ] **Step 4: Verify**

Run: `grep -rn "FarmItemsGoal\|FarmMonsterGoal" src` → no output (string reprs in projections are `"FarmMonster("`/`"FarmItems"` literals, not the class — those are fine and may remain for historical win-rate keys). `uv run pytest -q` → all pass.

- [ ] **Step 5: Commit**

```bash
git add -A
git commit -m "refactor(ai): delete dormant FarmItems/FarmMonster goals

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Final verification + cleanup grep gates

**Files:** none (verification only)

- [ ] **Step 1: Full suite**

Run: `uv run pytest -q` → 0 failures, 0 errors, 0 skipped.

- [ ] **Step 2: Lint + type-check**

Run: `uv run ruff check src tests` → clean. `uv run mypy src/artifactsmmo_cli/ai/tiers/guards.py src/artifactsmmo_cli/ai/tiers/means.py src/artifactsmmo_cli/ai/strategy_driver.py src/artifactsmmo_cli/ai/player.py` → no issues (the four+two changed files; the 131-error repo baseline in unrelated files is pre-existing — confirm zero new errors in changed files).

- [ ] **Step 3: Retirement/cleanup grep gates**

Run and confirm empty output:
```bash
grep -rn "priorities" src/artifactsmmo_cli/ | grep -v "# " || true   # no priorities imports
grep -rn "_select_goal\|_committed_upgrade_target\|_upgrade_target_still_valid\|_gating_skill_targets" src tests
grep -rn "def priority(" src/artifactsmmo_cli/ai/goals/
```
The first two must be empty (the third may show nothing — base `Goal.priority` lives in `base.py` and is fine; assert no *override* in `goals/` subclasses).

- [ ] **Step 4: Coverage on changed code**

Run: `uv run pytest tests/test_ai/test_tiers_guards.py tests/test_ai/test_tiers_means.py tests/test_ai/test_strategy_driver.py tests/test_ai/test_player.py --cov=artifactsmmo_cli.ai.tiers.guards --cov=artifactsmmo_cli.ai.tiers.means --cov=artifactsmmo_cli.ai.strategy_driver --cov-report=term-missing -q`
Expected: 100% on `guards.py`/`means.py`; the changed driver/player lines covered. Add targeted tests for any uncovered new line.

- [ ] **Step 5: Commit (if Step 4 added tests)**

```bash
git add -A
git commit -m "test(ai): cover P3c arbiter edge cases

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review

**Spec coverage:**
- Total preemption order (guards > collect-reward > objective step > discretionary) → Task 3 `select`. ✓
- Guard ladder + thresholds + gate precedence → Task 1. ✓
- Means two bands + within-band order + cancels in collect-reward + Sell in both → Task 2. ✓
- Driver top-plannable + sticky commitment → Task 3. ✓
- `decide()`/`StrategyDecision` — kept objective-only; guards/means composed in driver (documented refinement) → Task 3 + plan header. ✓
- `_select_goal` retirement + cycle rewire → Task 4. ✓
- `crafting_target` re-sourced (not deleted) → Task 4 step 3. ✓
- `priorities.py` + goal `priority()` retirement → Task 5. ✓
- FarmMonster/FarmItems + `_gating_skill_targets` deletion → Tasks 6 + 4. ✓
- Testing (0/0/0, 100% changed, grep gates) → Task 7. ✓
- Error handling (`select` returns None → idle/recovery; unplannable guard falls through) → Task 3 `select` returns `(None, [], …)`. ✓

**Placeholder scan:** Task 3 and Task 4 tests carry `...` placeholders for the planner-integration cases — these are flagged as "flesh out using the real GOAPPlanner + make_state, modelled on the P3b build-goals tests"; the implementer must write concrete bodies (the surrounding concrete tests show the shape). All implementation steps carry full code. The means-predicate task explicitly says to confirm `task_decision`/`project_task_completion` signatures and replicate `LowYieldCancelGoal`'s exact comparison if the projection lacks an `alternative_pays_more` helper — verify before writing, no guessing.

**Type consistency:** `SelectionContext` fields identical across guards.py/means.py/driver/player. `active_guards(state, game_data, history, ctx)` and `active_means(...)→(collect, discretionary)` consistent Task 1↔2↔3. `map_guard(kind, game_data, ctx)`/`map_means(kind, game_data, ctx)`/`objective_step_goal(step, state, game_data, ctx)` consistent Task 3↔4. `StrategyArbiter(planner, history).select(decision, state, game_data, actions, ctx) -> (Goal|None, list[Action], list[dict])` consistent Task 3↔4.

**Known verification points the implementer MUST confirm before writing (not guesses):** exact import paths/signatures of `overstocked_items`, `select_bank_deposits`, `task_decision`/`TaskDecision.PIVOT`, `project_task_completion`, `GOAPPlanner.plan`/`last_stats`; the real name of the FarmItems/FarmMonster test files; whether `learning/projections.py` references band constants (audit says only a comment — confirm). Each task names its check.
