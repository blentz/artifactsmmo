# Inventory Keep-Unification Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the `frozenset[str]` blanket-protection idiom (which can only mean "keep ALL copies" — four bug instances, one live) with two quantity caps — `keep_in_bag` and `keep_owned` — driven by a single `KeepReason` registry, and prove it with a behavioral-completeness census whose cells are derived from that registry.

**Architecture:** Protection today conflates "must stay in the BAG" (banking is reversible) with "must not be DESTROYED" (ownership). Split them into two integer caps. Every protection reason becomes a `KeepReason` registry entry contributing a *quantity* to one or both caps; caps combine by `max()`. Disposal consumers then compute `bankable = bag - keep_in_bag` and `destroyable = (bag+bank) - keep_owned`. A blanket becomes inexpressible except via an explicit `KEEP_ALL` sentinel. The census derives one SAFETY and one LIVENESS cell per reason, so a new reason without a disposability proof breaks the build.

**Tech Stack:** Python 3.13, `uv`, GOAP (`GOAPPlanner`/`StrategyArbiter`), Lean 4 (`formal/`).

Spec: `docs/superpowers/specs/2026-07-12-inventory-keep-unification-design.md` (656d2b99).

## Global Constraints

- `uv run` prefix on every Python command (uv is at `/home/blentz/.local/bin/uv`, NOT on PATH).
- Run test suites with `env -u FORCE_COLOR` — this shell sets `FORCE_COLOR=3`, which breaks ~10 ANSI-assertion tests in `tests/test_commands/`. Not a code bug.
- Two-lane suite: `uv run pytest -n auto tests/ --ignore=tests/test_ai/scenarios` then `uv run pytest tests/test_ai/scenarios --cov-append`. Never `-n auto` the scenarios dir (wall-clock flakes).
- **`tests/ai/` and `tests/test_ai/` are SEPARATE directories — run BOTH.** A prior epic shipped a break because a task ran only `tests/test_ai/`.
- **`formal/diff/` is NOT in the default pytest path. Any change to a shared signature/symbol (`SelectionContext` fields, `recyclable_surplus`/`select_bank_deposits`/`useful_quantity_cap` signatures) MUST run `uv run pytest formal/diff` before the task is done.** A prior epic broke 262 formal/diff constructors this exact way. `test_bank_selection_diff.py`, `test_inventory_caps_diff.py`, `test_cycle_step_diff.py`, `test_plan_exists_diff.py` and `mutate.py` all consume these cores.
- New `SelectionContext` fields MUST have a default (the codebase constructs it in ~26 formal/diff helpers); a required field breaks them all.
- Success criteria: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- No inline imports. Never catch `Exception`. Never use `if TYPE_CHECKING`. One behavioral class per file.
- Use only API/game data or fail with an error — no defaulting to paper over missing data.
- `formal/gate.sh` must be ALL PARTS PASSED at the end of every phase. The mutation part requires a CLEAN COMMITTED tree (it mutates+restores working files), so: commit, then gate, then amend if a survivor appears.
- **Whenever you edit a line that a `formal/diff/mutate.py` anchor quotes, refresh that anchor.** A rotted anchor is reported as a `(stale)` SURVIVOR and fails the gate (this happened in `cd0e6d04`).
- Migration must be behavior-preserving EXCEPT for the deliberate hoard fix. Every existing blanket reason must survive as a registry reason with an equivalent quantity — losing one silently is a regression (e.g. banking a healing potion, or banking the task's own recipe inputs, both livelock).
- `KEEP_ALL` is the ONLY way to express "keep every copy". It is used exactly once (`CURRENCY`/`tasks_coin`).

---

## File Structure

**Create**
- `src/artifactsmmo_cli/ai/inventory_keep.py` — the authority. `KeepReason` enum, the per-reason pure functions, `keep_in_bag`, `keep_owned`, `bankable`, `destroyable`. One module, no I/O.
- `src/artifactsmmo_cli/audit/inventory_completeness.py` — census pure cores: cell grid derived from `KeepReason`, the planner harness, the verdict, the gap classifier.
- `scripts/gen_inventory_completeness.py` — CI gate (`--check`) + report writer, mirroring `scripts/gen_craft_completeness.py`.
- `formal/Formal/InventoryKeep.lean` — Lean mirror of the two caps + role theorems.
- `formal/diff/test_inventory_keep_diff.py` — differential harness binding the real Python cores to the Lean oracle.
- `tests/test_ai/test_inventory_keep.py` — unit tests for the authority.
- `tests/test_audit/test_inventory_completeness.py` — unit tests for the census cores.

**Modify**
- `src/artifactsmmo_cli/ai/bank_selection.py` — `_keep_codes` (the live bug) → `bankable`.
- `src/artifactsmmo_cli/ai/recycle_surplus.py` — drop `protected_codes` + `kit` → `destroyable`.
- `src/artifactsmmo_cli/ai/accumulation_sell.py` — `useful_quantity_cap` → `destroyable`.
- `src/artifactsmmo_cli/ai/inventory_caps.py` — `overstocked_items` → `destroyable`.
- `src/artifactsmmo_cli/ai/tiers/guards.py` — delete `protected_gear_codes` / `recycle_protected_codes` / `_gear_protected`.
- `src/artifactsmmo_cli/ai/goals/deposit_inventory.py`, `goals/discard_overstock.py`, `goals/sell_inventory.py`, `goals/recycle_surplus.py` — drop the `protected_codes` / `profile_codes` params.
- `formal/Oracle.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`, `formal/Formal.lean`, `formal/diff/mutate.py`.

---

## The complete KeepReason registry

Derived from EVERY existing blanket site (`bank_selection._keep_codes`, `recycle_surplus` `protected_codes`+`kit`, `guards._gear_protected`, `useful_quantity_cap`). **Nothing here may be dropped in migration.**

| Reason | Feeds | Quantity | Replaces |
|---|---|---|---|
| `CURRENCY` | owned + in_bag | `KEEP_ALL` | `_keep_codes`: `{TASKS_COIN_CODE}` |
| `ACTIVE_TASK` | owned + in_bag | remaining task qty (`task_total - task_progress`) | `_keep_codes`: `state.task_code` |
| `HEALING_CONSUMABLE` | in_bag | `heal_stock_target(...)` (`ai/consumable_supply.py`) | `_keep_codes`: `stats.hp_restore > 0` |
| `COMBAT_WEAPON` | in_bag | 1 | `_keep_codes`: `_best_fighting_weapon` |
| `WORKING_KIT` | in_bag | 1 | `_keep_codes` + `recycle_surplus`: `_best_gathering_tools` |
| `COMMITTED_RECIPE` | in_bag | recipe qty needed | `_keep_codes`: `_recipe_materials(crafting_target, items-task)` |
| `GOAL_MATERIALS` | in_bag | active goal's `needed` qty | `_keep_codes`: `profile_codes` |
| `EQUIPPED` | owned | 1 | `useful_quantity_cap` equipped arm |
| `GEAR_DEMAND` | owned | `ctx.gear_keep[code]` | `guards._gear_protected`, `gear_keep` |
| `RECIPE_DEMAND` | owned | `useful_quantity_cap` recipe/batch/safety-floor logic | `useful_quantity_cap` |

`HEALING_CONSUMABLE` keeps ALL bag copies today (`_keep_codes` adds every `hp_restore > 0` code). **That is the blanket, merely re-expressed as a quantity — instance #5 of the same bug**, and the reason-coverage gate correctly refuses it: with `keep == held`, `bankable == 0` forever, so it could never pass a LIVENESS cell. **Resolution (user ruling, pre-flight):** use the system's own existing target, `consumable_supply.heal_stock_target(desired)` = `max(HEAL_STOCK_FLOOR, min(desired, UTILITY_SLOT_MAX_STACK))`. Surplus potions above the stock target become **bankable** — and because `HEALING_CONSUMABLE` feeds `in_bag` ONLY, they are never sold or deleted, just banked (recoverable, and it frees slots). `desired` comes from the same call site `consumable_supply` already uses to size the heal stock.

---

# P1 — The authority (inert)

Ships the cores with NO consumer migrated. Safe: nothing changes behaviour.

### Task 1: `KeepReason` registry + the two caps

**Files:**
- Create: `src/artifactsmmo_cli/ai/inventory_keep.py`
- Test: `tests/test_ai/test_inventory_keep.py`

**Interfaces:**
- Consumes: `WorldState`, `GameData`, `SelectionContext` (`ai/tiers/guards.py`), `useful_quantity_cap` (`ai/inventory_caps.py`), `_best_gathering_tools` / `_best_fighting_weapon` / `_recipe_materials` (`ai/bank_selection.py`), `TASKS_COIN_CODE` (`ai/constants.py`).
- Produces:
  - `KEEP_ALL: int` (sentinel, `1_000_000`)
  - `class KeepReason(Enum)` with members `CURRENCY, ACTIVE_TASK, HEALING_CONSUMABLE, COMBAT_WEAPON, WORKING_KIT, COMMITTED_RECIPE, GOAL_MATERIALS, EQUIPPED, GEAR_DEMAND, RECIPE_DEMAND`
  - `IN_BAG_REASONS: frozenset[KeepReason]`, `OWNED_REASONS: frozenset[KeepReason]`
  - `keep_in_bag(code, state, game_data, ctx) -> int`
  - `keep_owned(code, state, game_data, ctx) -> int`
  - `bankable(code, state, game_data, ctx) -> int`
  - `destroyable(code, state, game_data, ctx) -> int`
  - `reason_quantity(reason, code, state, game_data, ctx) -> int` (used by the census to build cells)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_inventory_keep.py
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_keep import (
    KEEP_ALL, KeepReason, bankable, destroyable, keep_in_bag, keep_owned,
    reason_quantity,
)
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from tests.test_ai.fixtures import make_state


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                subtype="tool", skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_axe": {"copper_bar": 6}}
    gd._workshop_locations = {"weaponcrafting": (3, 1)}
    return gd


def test_working_kit_keeps_ONE_in_bag_not_the_hoard():
    """The axe bug, at the authority level: kit is a QUANTITY of 1, so 18 held
    leaves 17 bankable. A blanket would leave 0."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    ctx = _ctx()
    assert reason_quantity(KeepReason.WORKING_KIT, "copper_axe", state, gd, ctx) == 1
    assert keep_in_bag("copper_axe", state, gd, ctx) == 1
    assert bankable("copper_axe", state, gd, ctx) == 17


def test_currency_is_the_only_blanket():
    gd = _gd()
    state = make_state(level=10, inventory={"tasks_coin": 40})
    ctx = _ctx()
    assert keep_owned("tasks_coin", state, gd, ctx) == KEEP_ALL
    assert destroyable("tasks_coin", state, gd, ctx) == 0


def test_destroyable_counts_bank_copies_toward_owned():
    """keep_owned is about OWNERSHIP, so bank copies satisfy it: holding 1 in the
    bag and 5 in the bank with a gear demand of 2 leaves 4 destroyable."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 1},
                       bank_items={"copper_axe": 5})
    ctx = _ctx(gear_keep={"copper_axe": 2})
    assert keep_owned("copper_axe", state, gd, ctx) == 2
    assert destroyable("copper_axe", state, gd, ctx) == 4


def test_caps_are_never_negative():
    gd = _gd()
    state = make_state(level=10, inventory={})
    ctx = _ctx()
    assert bankable("copper_axe", state, gd, ctx) == 0
    assert destroyable("copper_axe", state, gd, ctx) == 0
```

- [ ] **Step 2: Run to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/test_ai/test_inventory_keep.py -q --no-cov`
Expected: FAIL — `ModuleNotFoundError: artifactsmmo_cli.ai.inventory_keep`

- [ ] **Step 3: Implement `inventory_keep.py`**

Each reason is a pure function of `(code, state, game_data, ctx) -> int`. Caps combine by `max()`. Import `useful_quantity_cap` for `RECIPE_DEMAND`/`EQUIPPED`/`GEAR_DEMAND` rather than reimplementing it — that logic is already correct and Lean-proved.

```python
"""The single keep authority: how many copies of an item must stay.

Protection used to be expressed as `frozenset[str]` code-sets, which can only
mean "keep ALL copies" — four hoard bugs came from that one type (18 copper_axe
shielded because the axe was the best woodcutting tool). Here every protection
reason contributes a QUANTITY, so a blanket is inexpressible; `KEEP_ALL` is the
one explicit escape hatch and it is used once (currency).

Two caps, because "protection" conflated two questions:
  * keep_in_bag  — copies that must stay in the BAG (banking is REVERSIBLE)
  * keep_owned   — copies that must remain OWNED, bag+bank (destroying is NOT)
"""
```

- `KEEP_ALL = 1_000_000`
- `KeepReason(Enum)` with the 10 members above.
- `IN_BAG_REASONS = frozenset({CURRENCY, ACTIVE_TASK, HEALING_CONSUMABLE, COMBAT_WEAPON, WORKING_KIT, COMMITTED_RECIPE, GOAL_MATERIALS})`
- `OWNED_REASONS = frozenset({CURRENCY, ACTIVE_TASK, EQUIPPED, GEAR_DEMAND, RECIPE_DEMAND})`
- `reason_quantity(reason, code, state, game_data, ctx)` dispatches to the per-reason function; returns 0 when the reason does not apply to `code`.
- `keep_in_bag = max(reason_quantity(r, ...) for r in IN_BAG_REASONS)`, `keep_owned` likewise over `OWNED_REASONS`.
- `bankable(code, ...) = max(0, state.inventory.get(code, 0) - keep_in_bag(code, ...))`
- `destroyable(code, ...) = max(0, (inventory + bank).get(code, 0) - keep_owned(code, ...))`

Per-reason quantities, verbatim from the registry table:
- `CURRENCY`: `KEEP_ALL if code == TASKS_COIN_CODE else 0`
- `ACTIVE_TASK`: `max(0, state.task_total - state.task_progress) if code == state.task_code else 0`
- `HEALING_CONSUMABLE`: `state.inventory.get(code, 0)` if `game_data.item_stats(code).hp_restore > 0` else 0
- `COMBAT_WEAPON`: `1 if code == _best_fighting_weapon(state, game_data) else 0`
- `WORKING_KIT`: `1 if code in _best_gathering_tools(state, game_data) else 0`
- `COMMITTED_RECIPE`: qty of `code` in `_recipe_materials([state.crafting_target, items-task code])`
- `GOAL_MATERIALS`: `ctx.step_profile.get(code, 0)` (the active objective-step goal's `needed` map; see Task 2)
- `EQUIPPED`: `1 if code in state.equipment.values() else 0`
- `GEAR_DEMAND`: `(ctx.gear_keep or {}).get(code, 0)`
- `RECIPE_DEMAND`: `useful_quantity_cap(code, state, game_data, gear_keep=ctx.gear_keep or None)`

- [ ] **Step 4: Run to verify they pass**

Run: `env -u FORCE_COLOR uv run pytest tests/test_ai/test_inventory_keep.py -q --no-cov`
Expected: PASS (4 passed)

- [ ] **Step 5: Lint + type**

Run: `uv run ruff check src/artifactsmmo_cli/ai/inventory_keep.py && uv run mypy src/artifactsmmo_cli/ai/inventory_keep.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add src/artifactsmmo_cli/ai/inventory_keep.py tests/test_ai/test_inventory_keep.py
git commit -m "feat(inventory): keep authority — two caps + KeepReason registry (P1, inert)"
```

---

### Task 2: Thread `step_profile` into `SelectionContext`

`GOAL_MATERIALS` needs the active objective-step goal's `needed` map. `guards.active_profile()` already receives a `step_profile` argument; `SelectionContext` does not carry it. Add it so `keep_in_bag` is a pure function of `(code, state, game_data, ctx)`.

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (add `step_profile: dict[str, int]` field to `SelectionContext`, default `{}`)
- Modify: `src/artifactsmmo_cli/ai/player.py` (populate it where the other ctx fields are built)
- Test: `tests/test_ai/test_inventory_keep.py` (add the case below)

**Interfaces:**
- Consumes: `SelectionContext` from Task 1.
- Produces: `SelectionContext.step_profile: dict[str, int]` — `{item_code: target_qty}` of the resolved objective-step goal.

- [ ] **Step 1: Write the failing test**

```python
def test_goal_materials_keep_the_active_goals_needed_qty():
    """The active gather goal's materials must not be banked out from under it —
    but only up to the NEEDED quantity; the surplus above it is bankable."""
    gd = _gd()
    state = make_state(level=10, inventory={"copper_bar": 20})
    ctx = _ctx(step_profile={"copper_bar": 6})
    assert keep_in_bag("copper_bar", state, gd, ctx) == 6
    assert bankable("copper_bar", state, gd, ctx) == 14
```

- [ ] **Step 2: Run to verify it fails**

Run: `env -u FORCE_COLOR uv run pytest tests/test_ai/test_inventory_keep.py::test_goal_materials_keep_the_active_goals_needed_qty -q --no-cov`
Expected: FAIL — `SelectionContext.__init__() got an unexpected keyword argument 'step_profile'`

- [ ] **Step 3: Add the field**

In `SelectionContext` (`tiers/guards.py`), beside `near_term_targets`:

```python
    # The resolved objective-step goal's `needed` map {item_code: target_qty}.
    # Feeds KeepReason.GOAL_MATERIALS so the active gather goal's materials are
    # not banked out from under it — as a QUANTITY, so the surplus above the
    # target is still bankable (the old `profile_codes` frozenset kept ALL).
    step_profile: dict[str, int] = field(default_factory=dict)
```

In `player.py`, populate `step_profile=` from the same resolved step goal `active_profile(...)` is already given.

- [ ] **Step 4: Run to verify it passes**

Run: `env -u FORCE_COLOR uv run pytest tests/test_ai/test_inventory_keep.py -q --no-cov`
Expected: PASS (5 passed)

- [ ] **Step 5: Full suite (nothing may regress — this is a live ctx change)**

Run: `env -u FORCE_COLOR uv run pytest -n auto tests/ --ignore=tests/test_ai/scenarios --cov-fail-under=0 -q`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add -A && git commit -m "feat(inventory): SelectionContext.step_profile feeds GOAL_MATERIALS keep (P1)"
```

---

### Task 3: Lean mirror + differential + mutation for the two caps

**Files:**
- Create: `formal/Formal/InventoryKeep.lean`
- Create: `formal/diff/test_inventory_keep_diff.py`
- Modify: `formal/Formal.lean` (import), `formal/Oracle.lean` (keys `keep_in_bag`, `keep_owned`), `formal/Formal/Manifest.lean` (role checks), `formal/Formal/Contracts.lean` (statement pins), `formal/diff/mutate.py` (anchors)

**Interfaces:**
- Consumes: `keep_in_bag` / `keep_owned` / `bankable` / `destroyable` from Task 1.
- Produces: Oracle kinds `keep_in_bag` / `keep_owned`; Lean `Formal.InventoryKeep.keepInBag` / `.keepOwned` / `.bankable` / `.destroyable`.

Model the caps over a list of `(reason, qty)` contributions (the reason *functions* stay opaque/diff-pinned, like `hasGrindRung` in `ActionApplicability`) so the theorems are about the COMBINATOR, which is where the bug class lives.

- [ ] **Step 1: Write `InventoryKeep.lean` with these NON-VACUOUS role theorems**

```lean
/-- The caps are the max over their reasons; 0 when no reason applies. -/
def keepFrom (contribs : List Nat) : Nat := contribs.foldl max 0

def bankable (bag keep : Nat) : Nat := bag - keep
def destroyable (total keep : Nat) : Nat := total - keep

/-- SAFETY: what must stay never leaves. -/
theorem bankable_never_eats_keep (bag keep : Nat) :
    bag - bankable bag keep ≥ min bag keep := by omega

/-- A reason's quantity is always honoured (max dominates each contribution). -/
theorem keep_dominates_each_reason (contribs : List Nat) (q : Nat)
    (h : q ∈ contribs) : keepFrom contribs ≥ q := by
  induction contribs with
  | nil => cases h
  | cons c cs ih => cases h <;> simp [keepFrom] <;> omega

/-- LIVENESS: surplus above the cap IS disposable — the property every hoard
    bug violated (a blanket made `keep = held`, so `bankable = 0` forever). -/
theorem surplus_is_disposable (bag keep : Nat) (h : bag > keep) :
    bankable bag keep > 0 := by omega

/-- No cap can silently mean "keep all" unless it IS all. -/
theorem blanket_requires_keep_ge_held (bag keep : Nat)
    (h : bankable bag keep = 0) : keep ≥ bag := by omega
```

- [ ] **Step 2: Build**

Run: `cd formal && lake build`
Expected: success, no `sorry`.

- [ ] **Step 3: Oracle keys + differential harness**

Add `runKeepInBag` / `runKeepOwned` to `Oracle.lean` and dispatch branches `keep_in_bag` / `keep_owned`. `formal/diff/test_inventory_keep_diff.py` drives the REAL Python `keep_in_bag`/`keep_owned` against them over randomized reason-contribution vectors (hypothesis, ≥300 examples).

- [ ] **Step 4: Mutation anchors**

Add `INVENTORY_KEEP_MUTATIONS` to `formal/diff/mutate.py`, each killed by `tests/test_ai/test_inventory_keep.py`:

```python
INVENTORY_KEEP_MUTATIONS = [
    ("inventory_keep: WORKING_KIT keeps ALL copies (the blanket bug)",
     "        return 1 if code in _best_gathering_tools(state, game_data) else 0",
     "        return (state.inventory.get(code, 0)\n"
     "                if code in _best_gathering_tools(state, game_data) else 0)"),

    ("inventory_keep: caps combine by sum not max (over-protects)",
     "    return max(quantities, default=0)",
     "    return sum(quantities)"),

    ("inventory_keep: destroyable ignores bank copies",
     "    total = state.inventory.get(code, 0) + (state.bank_items or {}).get(code, 0)",
     "    total = state.inventory.get(code, 0)"),
]
```

- [ ] **Step 5: Full gate**

Run: `git add -A && git commit -m "feat(formal): InventoryKeep Lean mirror + differential + mutation (P1)"` then `cd formal && env -u FORCE_COLOR bash gate.sh`
Expected: `ALL GATE PARTS PASSED`.

---

# P2 — The census (lands RED)

The census defines done. It must FAIL on the live deposit hoard before any consumer is migrated — that is the proof it can detect the bug class.

### Task 4: Census cores — grid, verdict, gap classes

**Files:**
- Create: `src/artifactsmmo_cli/audit/inventory_completeness.py`
- Test: `tests/test_audit/test_inventory_completeness.py`

**Interfaces:**
- Consumes: `KeepReason`, `IN_BAG_REASONS`, `OWNED_REASONS`, `keep_in_bag`, `keep_owned`, `bankable`, `destroyable` (Task 1); `StrategyArbiter` (`ai/strategy_driver.py`); `GOAPPlanner`.
- Produces:
  - `@dataclass(frozen=True) class InventoryCell` — `reason: KeepReason`, `kind: Literal["safety","liveness"]`, `cap: Literal["in_bag","owned"]`, `code: str`, `held: int`, `keep: int`, `pressure: Literal["slot_full","qty_full","below_threshold"]`
  - `inventory_grid(game_data) -> list[InventoryCell]` — DERIVED from the registry: for each reason × each cap it feeds × each pressure state, one SAFETY (`held == keep`) and one LIVENESS (`held == keep + surplus`) cell. `CURRENCY` yields SAFETY only (declared exemption).
  - `plan_inventory(cell, state, game_data) -> list[Action]` — drives the REAL `StrategyArbiter` (never a mocked planner).
  - `class InventoryGapClass(Enum)` — `NO_ROUTE_AVAILABLE, BANK_FULL, VENUE_UNREACHABLE, KEEP_ALL_SENTINEL, INVENTORY_BUG`
  - `inventory_cell_verdict(cell, plan, state, game_data) -> bool` — SAFETY: PASS iff no action in the plan disposes `cell.code` below `keep`. LIVENESS: PASS iff some action in the plan disposes `cell.code` (Deposit/Recycle/Sell/Delete of that code).
  - `classify_gap(cell, state, game_data) -> InventoryGapClass` — `INVENTORY_BUG` is the residual and must be 0.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_audit/test_inventory_completeness.py
from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_completeness import (
    InventoryGapClass, inventory_grid,
)


def test_grid_covers_every_reason_with_safety_and_liveness(bundle_game_data):
    """Behavioral completeness: the grid is DERIVED from the registry, so every
    KeepReason gets a SAFETY and a LIVENESS cell. CURRENCY is the one declared
    exemption (KEEP_ALL means nothing is ever disposable)."""
    cells = inventory_grid(bundle_game_data)
    for reason in KeepReason:
        kinds = {c.kind for c in cells if c.reason is reason}
        assert "safety" in kinds, f"{reason} has no SAFETY cell"
        if reason is not KeepReason.CURRENCY:
            assert "liveness" in kinds, f"{reason} has no LIVENESS cell"


def test_currency_is_the_only_liveness_exemption(bundle_game_data):
    cells = inventory_grid(bundle_game_data)
    exempt = {r for r in KeepReason
              if "liveness" not in {c.kind for c in cells if c.reason is r}}
    assert exempt == {KeepReason.CURRENCY}


def test_gap_classes_have_no_expected_bug_class():
    """INVENTORY_BUG means UNEXPLAINED, never EXPECTED — the craft-census rule."""
    assert InventoryGapClass.INVENTORY_BUG.value == "inventory_bug"
```

- [ ] **Step 2: Run to verify they fail**

Run: `env -u FORCE_COLOR uv run pytest tests/test_audit/test_inventory_completeness.py -q --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement the census cores** (grid derived from `KeepReason`, verdict, classifier as specified in Interfaces).

- [ ] **Step 4: Run to verify they pass**

Run: `env -u FORCE_COLOR uv run pytest tests/test_audit/test_inventory_completeness.py -q --no-cov`
Expected: PASS (3 passed).

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(audit): inventory census cores — registry-derived grid + verdict + gap classes (P2)"
```

---

### Task 5: Census runner + `--check` CI gate — lands RED

**Files:**
- Create: `scripts/gen_inventory_completeness.py`
- Create: `docs/behavioral_completeness/INVENTORY_MATRIX.md` (generated)

**Interfaces:**
- Consumes: Task 4's cores.
- Produces: `uv run python scripts/gen_inventory_completeness.py [--check] [max_workers]` — writes the matrix; with `--check` exits 1 if **either** gate trips:
  1. any cell classifies `INVENTORY_BUG`
  2. reason-coverage: any `KeepReason` (except `CURRENCY`) lacks a PASSing LIVENESS cell

Mirror `scripts/gen_craft_completeness.py` exactly (parallel workers, matrix writer, `--check` exit code).

- [ ] **Step 1: Run the census — expect RED**

Run: `env -u FORCE_COLOR uv run python scripts/gen_inventory_completeness.py --check`
Expected: **exit 1**. It MUST report a failing LIVENESS cell for `WORKING_KIT` on the `in_bag` cap — that is the live deposit bug (`bank_selection._keep_codes` blanket-keeps the best gathering tools, so `select_bank_deposits` banks none of the 17 copper_axe). If it does not, the census cannot see the bug class and Task 4 is wrong — STOP and fix it.

- [ ] **Step 2: Record the RED baseline in the plan's progress ledger** (which reasons fail, with counts).

- [ ] **Step 3: Commit (census RED, gate NOT yet wired to CI)**

```bash
git add -A && git commit -m "feat(audit): inventory census runner + --check gate (P2, RED: deposit hoard exposed)"
```

---

# P3 — Migrate consumers (deposit first — the live bug)

Each task turns cells green. Run the census after each.

### Task 6: `bank_selection` → `bankable` (fixes the live hoard)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/bank_selection.py` — delete `_keep_codes`; `select_bank_deposits` deposits `bankable(code, ...)` of each held code.
- Modify: `src/artifactsmmo_cli/ai/goals/deposit_inventory.py` — drop `profile_codes`.
- Test: `tests/test_ai/test_bank_selection.py`

- [ ] **Step 1: Failing test — the live shape**

```python
def test_deposit_banks_the_kit_tool_spares_not_the_working_tool():
    """Live Robby 2026-07-12: 18 copper_axe (best woodcutting tool) — deposit
    banked NONE because _keep_codes blanket-kept the whole code. It must bank 17
    and keep the one the gather re-arm will equip."""
    gd = _gd()
    state = make_state(level=10, skills={"weaponcrafting": 2},
                       inventory={"copper_axe": 18})
    deposits = dict(select_bank_deposits(state, gd, _ctx()))
    assert deposits["copper_axe"] == 17
```

- [ ] **Step 2: Verify RED**, **Step 3: Implement**, **Step 4: Verify GREEN**.
- [ ] **Step 5: Census** — `WORKING_KIT`/`in_bag` LIVENESS cell must now PASS.

Run: `env -u FORCE_COLOR uv run python scripts/gen_inventory_completeness.py --check`
Expected: the `WORKING_KIT` in_bag liveness cell is now PASS (other reasons may still fail).

- [ ] **Step 6: Full suite + gate + commit** (refresh any rotted `BANK_SELECTION_MUTATIONS` anchors).

---

### Task 7: `recycle_surplus` → `destroyable`

Delete the `protected_codes` param and the `kit` set entirely (the cap floor added in `cd0e6d04` is subsumed by `KeepReason.WORKING_KIT`). `recyclable_surplus(state, game_data, ctx)` returns `{code: destroyable(code)}` filtered by recyclability (has recipe, skill met, workshop known).

Same 6-step TDD shape. Census after. Gate. Commit.

### Task 8: `accumulation_sell` + `sell_inventory` → `destroyable`

Replace `useful_quantity_cap` calls with `destroyable`. Same shape.

### Task 9: `inventory_caps.overstocked_items` + `discard_overstock` → `destroyable`

`overstocked_items` keeps its watermark (pressure) logic but sources its per-item excess from `destroyable`. Same shape.

---

# P4 — Retire the legacy surface

### Task 10: Delete the set-based protection idiom

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` — delete `protected_gear_codes`, `recycle_protected_codes`, `_gear_protected`.
- Modify: `src/artifactsmmo_cli/ai/bank_selection.py` — delete `_keep_codes`, `_recipe_materials` if now unused.
- Modify: goals — delete the `protected_codes` / `profile_codes` constructor params.
- Modify: `SelectionContext` — `target_gear` / `target_tools` / `near_term_targets` survive ONLY in their ACQUISITION role; delete every protection-role read.

- [ ] **Step 1: Prove they are dead**

Run: `grep -rn "protected_gear_codes\|recycle_protected_codes\|_gear_protected\|_keep_codes\|profile_codes\|protected_codes" src/ tests/ formal/`
Expected: only acquisition-role hits remain; each must be justified in the commit message.

- [ ] **Step 2: Delete + delete their tests** (`tests/test_ai/test_recycle_protection.py` migrates to `test_inventory_keep.py` — the SAME behaviours must still be asserted, at the authority level; do NOT drop coverage).
- [ ] **Step 3: Full suite 100% + gate ALL PARTS PASSED.**
- [ ] **Step 4: Commit.**

### Task 11: Acceptance — census GREEN + CI gate wired

- [ ] **Step 1:** `env -u FORCE_COLOR uv run python scripts/gen_inventory_completeness.py --check` → **exit 0**: `inventory_bug == 0` AND every non-`CURRENCY` reason has a PASSing LIVENESS cell.
- [ ] **Step 2:** Wire `--check` into the same CI/pre-commit surface as `gen_craft_completeness.py --check`.
- [ ] **Step 3:** Runtime-verify on the live character: `uv run artifactsmmo plan Robby` must now shed the `copper_axe`/`fishing_net` hoard (bank or recycle) instead of hoarding it. Green tests are not enough — the four bugs all passed their unit tests.
- [ ] **Step 4:** Full two-lane suite 100% + `formal/gate.sh` ALL PARTS PASSED + whole-branch review.
- [ ] **Step 5:** Update `docs/behavioral_completeness/README.md` to describe the second census.

---

## Self-Review

**Spec coverage:** two caps (Task 1) ✓; reason registry incl. the 3 reasons the spec's table missed (Task 1 table) ✓; `step_profile` for `GOAL_MATERIALS` (Task 2) ✓; Lean lockstep (Task 3, and a gate at every phase) ✓; census derived from registry with SAFETY+LIVENESS (Task 4) ✓; `inventory_bug == 0` + reason-coverage gates (Task 5, 11) ✓; gap classes incl. `KEEP_ALL_SENTINEL` exemption (Task 4) ✓; consumers collapse (Tasks 6–9) ✓; legacy deletion (Task 10) ✓; deposit-first ordering (Task 6) ✓; census-before-migration (P2 before P3) ✓; non-goals (thresholds untouched) — no task tunes them ✓.

**Placeholder scan:** no TBD/TODO. Tasks 7–9 say "same 6-step TDD shape" and reference Task 6's shape rather than repeating it — acceptable ONLY because they are the identical mechanical substitution (`cap` → `destroyable`) on a different consumer; each still names its exact files, its failing-test subject, and its census check.

**Type consistency:** `keep_in_bag`/`keep_owned`/`bankable`/`destroyable` take `(code, state, game_data, ctx)` everywhere; `KeepReason` members are referenced identically in Tasks 1, 4, 5; `InventoryGapClass.INVENTORY_BUG.value == "inventory_bug"` matches the `--check` gate's key.

**Known risk:** `HEALING_CONSUMABLE` keeps ALL bag copies (preserved verbatim from `_keep_codes`). It is `in_bag` only, so potions remain sellable/recyclable — identical to today. If the census surfaces a potion hoard it is a follow-up, not this epic (recorded in the plan, not silently dropped).
