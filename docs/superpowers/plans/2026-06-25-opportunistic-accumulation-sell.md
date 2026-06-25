# Opportunistic Accumulation-Sell Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sell down accumulated multiples of an item without waiting for bag pressure, with priority rising geometrically with the held/cap ratio.

**Architecture:** A pure ratio core (`accumulation_sell.py`) computes geometric severity and sell-down-to-cap excess over the existing `useful_quantity_cap`. The moderate regime extends `SellInventoryGoal` (value + is_satisfied + relevant_actions) — pure Python, outside the formal ladder model. The severe regime extends the `SELL_PRESSURED` ladder firing via a new opaque `severeAccumulation` State bool, mirroring the proven `DRAIN_BANK_JUNK` State-field lockstep landed 2026-06-24.

**Tech Stack:** Python 3.13 (`uv run`), Lean 4 (formal/), Hypothesis differential + mutation gate.

## Global Constraints

- `uv run` prefix on every Python command (`uv` at `~/.local/bin/uv`).
- No inline imports; imports at top of file. One behavioral class per file. Never catch `Exception`. Use only API data or fail.
- `ACCUM_MULT = 5`, `SEVERE_STEPS = 5`, `accumulation_steps = floor(log2(held/eff_cap))` with `eff_cap = max(cap, 1)`. Integer-exact, no float.
- `ACCUM_BASE = 18`, `ACCUM_STEP = 3`, `DISCRETIONARY_CEIL = 48` (moderate value, strictly < progression 50 / survival 70).
- Sell-only: never delete. Currencies/consumables (cap 999) never fire.
- Formal safety axioms ⊆ {propext, Classical.choice, Quot.sound}; liveness modules may use Mathlib. 100% test coverage (`--cov-fail-under=100`).
- The `DRAIN_BANK_JUNK` commits (`git log --grep "drain-bank-junk"`) are the working template for every Lean/oracle/sim/diff/mutation site touched in Tasks 5-8.

---

### Task 1: Pure ratio core — `accumulation_sell.py`

**Files:**
- Create: `src/artifactsmmo_cli/ai/accumulation_sell.py`
- Test: `tests/test_ai/test_accumulation_sell.py`

**Interfaces:**
- Produces: `accumulation_steps(held: int, cap: int) -> int`, `accumulation_excess(held: int, cap: int) -> int`, `ACCUM_MULT: int = 5`, `SEVERE_STEPS: int = 5`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_accumulation_sell.py
from artifactsmmo_cli.ai.accumulation_sell import (
    ACCUM_MULT, SEVERE_STEPS, accumulation_excess, accumulation_steps,
)


def test_steps_is_floor_log2_ratio():
    assert accumulation_steps(14, 1) == 3   # 2^3=8<=14<16
    assert accumulation_steps(11, 2) == 2   # 11/2=5.5 -> 2^2=4*2=8<=11<16
    assert accumulation_steps(32, 1) == 5   # exactly SEVERE
    assert accumulation_steps(1000, 1) == 9


def test_steps_zero_below_eff_cap_and_cap_zero_uses_one():
    assert accumulation_steps(0, 5) == 0
    assert accumulation_steps(3, 0) == 1    # eff_cap 1: 2^1=2<=3<4


def test_excess_sells_down_to_true_cap_past_gate():
    assert accumulation_excess(14, 1) == 13   # keep 1
    assert accumulation_excess(14, 0) == 14   # dominated -> sell all
    assert accumulation_excess(11, 2) == 9    # keep 2


def test_excess_zero_below_ratio_gate():
    assert accumulation_excess(4, 1) == 0     # 4 < 5*1
    assert accumulation_excess(9, 2) == 0     # 9 < 5*2=10
    assert accumulation_excess(10, 2) == 8    # 10 >= 10 -> keep 2


def test_constants():
    assert ACCUM_MULT == 5
    assert SEVERE_STEPS == 5
```

- [ ] **Step 2: Run to verify failure**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_accumulation_sell.py -q --no-cov`
Expected: FAIL (ModuleNotFoundError: accumulation_sell).

- [ ] **Step 3: Implement the core**

```python
# src/artifactsmmo_cli/ai/accumulation_sell.py
# accumulation_sell

"""Ratio-driven, space-pressure-independent sell-down of accumulated multiples.

Pure integer-exact core (no float, so it mirrors the Lean `AccumulationSell`
def byte-for-byte under the differential gate). An item is over-accumulated when
its held quantity is a large multiple of its keep-cap (`useful_quantity_cap`);
the bot sheds the surplus down to the cap by selling, with urgency rising
geometrically (one step per doubling of the ratio).
"""


ACCUM_MULT = 5
"""Fire the accumulation sell when `held >= ACCUM_MULT * max(cap, 1)`."""

SEVERE_STEPS = 5
"""`accumulation_steps >= SEVERE_STEPS` (held >= cap*32) escalates the sell above
the progression band (see `tiers/means.py` SELL_PRESSURED)."""


def accumulation_steps(held: int, cap: int) -> int:
    """Geometric severity: the largest `k >= 0` with `eff_cap * 2**k <= held`
    (= floor(log2(held / eff_cap))), `eff_cap = max(cap, 1)`. 0 when held is
    below `eff_cap`. Integer-exact doubling — no float."""
    eff_cap = cap if cap > 1 else 1
    if held < eff_cap:
        return 0
    k = 0
    bound = eff_cap
    while bound * 2 <= held:
        bound = bound * 2
        k = k + 1
    return k


def accumulation_excess(held: int, cap: int) -> int:
    """`held - max(cap, 0)` when `held >= ACCUM_MULT * max(cap, 1)`, else 0.
    The RATIO gate uses `eff_cap = max(cap, 1)`; the amount kept is the TRUE cap,
    so a dominated item (cap 0) past the gate sells down to 0, a kept item
    (cap 1) sells down to 1."""
    eff_cap = cap if cap > 1 else 1
    if held < ACCUM_MULT * eff_cap:
        return 0
    keep = cap if cap > 0 else 0
    return held - keep
```

- [ ] **Step 4: Run to verify pass**

Run: `~/.local/bin/uv run pytest tests/test_ai/test_accumulation_sell.py -q --no-cov`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/accumulation_sell.py tests/test_ai/test_accumulation_sell.py
git commit -m "feat(accumulation-sell): pure ratio core (steps + excess)"
```

---

### Task 2: Shell — sellable accumulation over GameData/WorldState

**Files:**
- Modify: `src/artifactsmmo_cli/ai/accumulation_sell.py` (append shell fns)
- Modify: `tests/test_ai/test_accumulation_sell.py`

**Interfaces:**
- Consumes: `accumulation_excess`, `accumulation_steps` (Task 1); `useful_quantity_cap` (`ai/inventory_caps.py`); `_has_sellable` is NOT reused (it is an any-item predicate) — instead use `game_data.npcs_buying_item(code)` + `tradeable` per-item, matching `_has_sellable`'s per-item rule (`tiers/guards.py:99-122`).
- Produces: `sellable_accumulation(state, game_data) -> dict[str, int]` (code → excess qty), `worst_accumulation_steps(state, game_data) -> int`.

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_ai/test_accumulation_sell.py
from artifactsmmo_cli.ai.accumulation_sell import (
    sellable_accumulation, worst_accumulation_steps,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_buyer() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "gold_coin": ItemStats(code="gold_coin", level=1, type_="currency"),
    }
    gd._crafting_recipes = {}
    # vendor buys wooden_shield (reachable, tradeable); nothing buys gold_coin.
    gd._npc_items = {"vendor": {"wooden_shield": 2}}
    gd._npc_locations = {"vendor": (1, 1)}
    return gd


def test_sellable_accumulation_targets_over_ratio_sellable_gear():
    gd = _gd_with_buyer()
    # 14 shields, cap 1 (equippable keep, not dominated) -> r=14 -> excess 13.
    state = make_state(level=1, inventory={"wooden_shield": 14})
    assert sellable_accumulation(state, gd) == {"wooden_shield": 13}


def test_sellable_accumulation_skips_unsellable_and_below_gate():
    gd = _gd_with_buyer()
    # gold_coin has no buyer -> skipped even if accumulated.
    state = make_state(level=1, inventory={"wooden_shield": 4, "gold_coin": 999})
    assert sellable_accumulation(state, gd) == {}  # 4 < 5*1; coin not sellable


def test_worst_accumulation_steps_is_max_over_items():
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 40})  # steps 5
    assert worst_accumulation_steps(state, gd) == 5
    assert worst_accumulation_steps(make_state(level=1), gd) == 0
```

- [ ] **Step 2: Run to verify failure** — `~/.local/bin/uv run pytest tests/test_ai/test_accumulation_sell.py -q --no-cov` → FAIL (ImportError).

- [ ] **Step 3: Implement the shell** (append to `accumulation_sell.py`; add imports at TOP of file)

```python
# top-of-file imports (add):
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.world_state import WorldState


def _is_sellable(code: str, game_data: GameData) -> bool:
    """An item with a reachable NPC buyer that is tradeable — the per-item rule
    behind `tiers/guards._has_sellable`."""
    stats = game_data.item_stats(code)
    if stats is not None and not stats.tradeable:
        return False
    return bool(game_data.npcs_buying_item(code))


def sellable_accumulation(state: WorldState, game_data: GameData) -> dict[str, int]:
    """Map each SELLABLE over-ratio inventory code to its sell-down-to-cap excess."""
    out: dict[str, int] = {}
    for code, held in state.inventory.items():
        if held <= 0 or not _is_sellable(code, game_data):
            continue
        cap = useful_quantity_cap(code, state, game_data)
        excess = accumulation_excess(held, cap)
        if excess > 0:
            out[code] = excess
    return out


def worst_accumulation_steps(state: WorldState, game_data: GameData) -> int:
    """Max `accumulation_steps` over sellable over-ratio items (0 if none) —
    the severity signal driving the SELL_PRESSURED escalation."""
    worst = 0
    for code, held in state.inventory.items():
        if held <= 0 or not _is_sellable(code, game_data):
            continue
        cap = useful_quantity_cap(code, state, game_data)
        if accumulation_excess(held, cap) > 0:
            steps = accumulation_steps(held, cap)
            if steps > worst:
                worst = steps
    return worst
```

- [ ] **Step 4: Run to verify pass** — `~/.local/bin/uv run pytest tests/test_ai/test_accumulation_sell.py -q --no-cov` → PASS.

- [ ] **Step 5: Commit**

```bash
git add src/artifactsmmo_cli/ai/accumulation_sell.py tests/test_ai/test_accumulation_sell.py
git commit -m "feat(accumulation-sell): sellable shell + severity signal"
```

> NOTE: confirm `game_data._npc_items` / `_npc_locations` / `npcs_buying_item` field names against `ai/game_data.py` when implementing; mirror the fixture shape used in `tests/test_ai/test_recycle_surplus.py` / `_has_sellable` tests if they differ.

---

### Task 3: SellInventoryGoal — moderate accumulation (value + satisfied + actions)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/sell_inventory.py`
- Test: `tests/test_ai/test_goals_sell_inventory.py` (or `test_sell_inventory_seize.py` — match existing)

**Interfaces:**
- Consumes: `sellable_accumulation`, `worst_accumulation_steps` (Task 2).
- Produces: extended `SellInventoryGoal.value` / `is_satisfied` / `relevant_actions`; constants `ACCUM_BASE=18`, `ACCUM_STEP=3`, `DISCRETIONARY_CEIL=48`.

- [ ] **Step 1: Write the failing tests**

```python
def test_value_positive_unpressured_when_accumulated():
    gd = _gd_with_buyer()  # reuse Task-2 fixture shape
    state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
    goal = SellInventoryGoal(bank_accessible=True)  # NOT bank-locked, bag has room
    # moderate: min(18 + steps(3)*3, 48) = 27
    assert goal.value(state, gd) == 27.0
    assert goal.is_satisfied(state) is False


def test_relevant_actions_sell_down_to_cap():
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=50)
    goal = SellInventoryGoal(bank_accessible=True)
    acts = goal.relevant_actions([], state, gd)
    sells = [a for a in acts if isinstance(a, NpcSellAction) and a.item_code == "wooden_shield"]
    assert len(sells) == 1 and sells[0].quantity == 13


def test_satisfied_when_no_accumulation_and_space_free():
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 1}, inventory_max=50)
    goal = SellInventoryGoal(bank_accessible=True)
    assert goal.is_satisfied(state) is True
    assert goal.value(state, gd) == 0.0
```

- [ ] **Step 2: Run to verify failure** — expect assertion failures (value 0.0, is_satisfied True).

- [ ] **Step 3: Implement** — add constants + accumulation term. `is_satisfied` stays the original free-slot rule (it has no `game_data`); `value()` computes `accum_value` BEFORE the satisfied early-return, so accumulation yields value even with free slots.

```python
# new module constants near SEIZE_WINDOW_VALUE:
ACCUM_BASE = 18.0
ACCUM_STEP = 3.0
DISCRETIONARY_CEIL = 48.0
"""Moderate (idle) accumulation-sell value: min(ACCUM_BASE + steps*ACCUM_STEP,
DISCRETIONARY_CEIL), strictly below progression (50) / survival (70). The SEVERE
regime (steps>=SEVERE_STEPS) is handled by the SELL_PRESSURED ladder disjunct,
not this value."""

# add import at top (NpcSellAction is already imported):
from artifactsmmo_cli.ai.accumulation_sell import (
    sellable_accumulation, worst_accumulation_steps,
)

    def value(self, state, game_data, history=None):
        if state.inventory_max == 0:
            return 0.0
        sellable = any(game_data.npcs_buying_item(code)
                       for code in state.inventory if state.inventory[code] > 0)
        if not sellable:
            return 0.0
        steps = worst_accumulation_steps(state, game_data)
        accum_value = min(ACCUM_BASE + steps * ACCUM_STEP, DISCRETIONARY_CEIL) if steps > 0 else 0.0
        if self.is_satisfied(state) and accum_value == 0.0:
            return 0.0
        used_fraction = state.inventory_used / state.inventory_max
        bank_locked_value = 0.0 if self._bank_accessible else used_fraction * 100.0
        window_value = SEIZE_WINDOW_VALUE if self._active_window_for_inventory(state, game_data) else 0.0
        return max(bank_locked_value, accum_value, window_value)
```

`is_satisfied` unchanged. `relevant_actions` constructs sized sells:

```python
    def relevant_actions(self, actions, state, game_data):
        result: list[Action] = []
        # Existing recovery / under-pressure prebuilt sells.
        for action in actions:
            if "recovery" in action.tags or (isinstance(action, NpcSellAction)
                                             and state.inventory.get(action.item_code, 0) > 0):
                result.append(action)
        # Accumulation sell-down-to-cap: one sized NpcSellAction per over-ratio code.
        for code, excess in sellable_accumulation(state, game_data).items():
            buyers = game_data.npcs_buying_item(code)
            if not buyers:
                continue
            npc_code = buyers[0][0]
            loc = game_data.npc_location_or_none(npc_code)
            if loc is None:
                continue
            act = NpcSellAction(npc_code=npc_code, item_code=code,
                                quantity=excess, npc_location=loc)
            if act.is_applicable(state, game_data):
                result.append(act)
        return result
```

> Confirm the npc-location accessor name (`npc_location_or_none` / `npc_location`) in `ai/game_data.py`; mirror how `factory.py` builds `NpcSellAction`.

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(accumulation-sell): moderate idle-sell in SellInventoryGoal"`

---

### Task 4: SELL_PRESSURED severe disjunct + production State plumbing

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/means.py` (`_fires` SELL_PRESSURED branch, import)
- Test: `tests/test_ai/test_tiers_means.py` (or `test_recycle_surplus.py` `_fires` pattern)

**Interfaces:**
- Consumes: `worst_accumulation_steps`, `SEVERE_STEPS` (Tasks 1-2).
- Produces: SELL_PRESSURED fires when `used_fraction >= 0.85 OR worst_accumulation_steps >= SEVERE_STEPS`, AND `_has_sellable`.

- [ ] **Step 1: Failing test**

```python
def test_sell_pressured_fires_on_severe_accumulation_unpressured():
    from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
    gd = _gd_with_buyer()
    # 40 shields, cap 1 -> steps 5 == SEVERE; bag NOT full (inventory_max 200).
    severe = make_state(level=1, inventory={"wooden_shield": 40}, inventory_max=200)
    assert _fires(MeansKind.SELL_PRESSURED, severe, gd, None, _ctx()) is True
    # 14 shields -> steps 3 < SEVERE, low pressure -> SELL_PRESSURED does NOT fire
    moderate = make_state(level=1, inventory={"wooden_shield": 14}, inventory_max=200)
    assert _fires(MeansKind.SELL_PRESSURED, moderate, gd, None, _ctx()) is False
```

- [ ] **Step 2: Run to verify failure.**

- [ ] **Step 3: Implement** — `means.py` import + branch:

```python
from artifactsmmo_cli.ai.accumulation_sell import SEVERE_STEPS, worst_accumulation_steps

    if kind is MeansKind.SELL_PRESSURED:
        if not _has_sellable(state, game_data):
            return False
        return (_used_fraction(state) >= SELL_PRESSURE_FRACTION
                or worst_accumulation_steps(state, game_data) >= SEVERE_STEPS)
```

- [ ] **Step 4: Run to verify pass.**
- [ ] **Step 5: Commit** — `git commit -m "feat(accumulation-sell): SELL_PRESSURED severe-hoard disjunct"`

> After this task run the FULL AI suite: `~/.local/bin/uv run pytest tests/test_ai/ -q --no-cov` (expect 0 regressions) — SELL_PRESSURED firing change can shift selection in existing tests.

---

### Task 5: Lean pure core — `Formal/AccumulationSell.lean`

**Files:**
- Create: `formal/Formal/AccumulationSell.lean`
- Modify: `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`

**Interfaces:**
- Produces: Lean `accumulationSteps`, `accumulationExcess` defs + theorems `excess_monotone`, `fires_implies_excess_positive`, `excess_sells_down_to_cap`, `steps_threshold`, `below_gate_quiet`.

- [ ] **Step 1: Write the computable defs + theorems** (mirror the integer doubling; `accumulationSteps` is fuel-bounded structural recursion seeded by `held`):

```lean
namespace Formal.AccumulationSell

def accMult : Nat := 5
def severeSteps : Nat := 5

/-- floor(log2(held / max(cap,1))). Fuel = held bounds the doubling loop. -/
def accumulationStepsFuel : Nat → Nat → Nat → Nat
  | 0, _, _ => 0
  | Nat.succ f, bound, held =>
      if bound * 2 ≤ held then 1 + accumulationStepsFuel f (bound * 2) held else 0

def accumulationSteps (held cap : Nat) : Nat :=
  let effCap := max cap 1
  if held < effCap then 0 else accumulationStepsFuel held effCap held

def accumulationExcess (held cap : Nat) : Nat :=
  let effCap := max cap 1
  if held < accMult * effCap then 0 else held - cap

theorem below_gate_quiet (held cap : Nat) (h : held < accMult * max cap 1) :
    accumulationExcess held cap = 0 := by simp [accumulationExcess, h]

theorem fires_implies_excess_positive (held cap : Nat)
    (hc : 0 < cap) (hf : accMult * max cap 1 ≤ held) :
    0 < accumulationExcess held cap := by
  -- accMult*cap ≤ held and 0<cap ⇒ cap < held ⇒ held - cap > 0
  sorry

theorem excess_sells_down_to_cap (held cap : Nat)
    (hf : accMult * max cap 1 ≤ held) :
    held - accumulationExcess held cap = cap := by
  sorry

theorem excess_monotone (h1 h2 cap : Nat) (h : h1 ≤ h2) :
    accumulationExcess h1 cap ≤ accumulationExcess h2 cap := by
  sorry

theorem steps_threshold (held cap : Nat)
    (h : severeSteps ≤ accumulationSteps held cap) :
    max cap 1 * 32 ≤ held := by
  sorry

end Formal.AccumulationSell
```

- [ ] **Step 2: Discharge the `sorry`s** using `lean4:prove` per theorem; `omega`/`Nat` lemmas for the arithmetic ones; the `steps_threshold` proof unfolds 5 doublings of the fuel def. Run `cd formal && ~/.elan/bin/lake build` — expect green, no `sorry`.

- [ ] **Step 3: Pin in Manifest + Contracts** — add `#check @Formal.AccumulationSell.<thm>` lines to `Manifest.lean` and exact-statement `example := @...` pins to `Contracts.lean` for all 5 theorems (mirror an existing block, e.g. the `InventoryCaps` pins).

- [ ] **Step 4: Verify** — `cd formal && ~/.elan/bin/lake build && bash gate/check_axioms.sh` (axioms ⊆ allowed; safety module → core-only set).

- [ ] **Step 5: Commit** — `git commit -m "feat(formal): AccumulationSell core + role theorems"`

---

### Task 6: Lean ladder State field + SELL_PRESSURED disjunct (mirror DRAIN_BANK_JUNK)

**Files (exact sites — mirror the `bankJunkNonempty` field added 2026-06-24):**
- `formal/Formal/Liveness/Measure.lean`: add `severeAccumulation : Bool` field (next to `bankJunkNonempty`).
- `formal/Formal/Liveness/ProductionLadder.lean`: `sellPressuredFires` gains `|| s.severeAccumulation` disjunct (find `def sellPressuredFires`).
- `formal/Formal/Liveness/LadderEval.lean` + `formal/Formal/Liveness/GameDataFixture.lean`: add `severeAccumulation := false` to the two full `State` literals.
- `formal/Oracle.lean`: State decoder — add `severeAccumulation := b 32` (arg index 32, after `bankJunkNonempty := b 31`); update the layout doc comment.
- `formal/sim/cycle_step.py`: `_sell_pressured_fires` mirror gains the disjunct (CycleState gets a `severe_accumulation` field; default False).

**Interfaces:**
- Produces: `Measure.State.severeAccumulation : Bool`; `sellPressuredFires s = (... used gate ...) && s.sellableInventoryNonempty || (s.severeAccumulation && s.sellableInventoryNonempty)` — match the production `_fires` shape exactly.

- [ ] **Step 1: Edit all sites above** (see DRAIN_BANK_JUNK commit for the identical pattern at each file).
- [ ] **Step 2: Build** — `cd formal && ~/.elan/bin/lake build` → green (fix any exhaustive-literal breakage by adding the field).
- [ ] **Step 3: Commit** — `git commit -m "feat(formal): severeAccumulation State field + SELL_PRESSURED disjunct"`

> The MeansKind enum is UNCHANGED (SELL_PRESSURED already exists) — only the firing predicate + State field change. No `allInLadderOrder`/count edits, unlike DRAIN_BANK_JUNK.

---

### Task 7: Differentials

**Files:**
- Create: `formal/diff/test_accumulation_sell_diff.py` (core vs `accumulation_sell` oracle).
- Modify: `formal/Oracle.lean` (add an `accumulation_sell` oracle command returning `{steps, excess}` from the Lean defs).
- Modify: `formal/diff/test_ladder_fires_diff.py` (drive arg[32] `severeAccumulation` from the real `worst_accumulation_steps(...) >= SEVERE_STEPS`; add the `_oracle_args` Scenario builder entry; add a drive-true / near-miss test).

- [ ] **Step 1: Oracle command** — in `Oracle.lean` add a `runAccumulationSell` that reads `[held, cap]` and emits `{"steps": accumulationSteps, "excess": accumulationExcess}`; register it in the command dispatch. `cd formal && ~/.elan/bin/lake build oracle`.

- [ ] **Step 2: Core differential** (`test_accumulation_sell_diff.py`):

```python
from hypothesis import given, settings, strategies as st
from artifactsmmo_cli.ai.accumulation_sell import accumulation_excess, accumulation_steps
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(held=st.integers(0, 5000), cap=st.integers(0, 50))
def test_accumulation_core_matches_lean(held, cap):
    lean = run_oracle("accumulation_sell", [[held, cap]])[0]
    assert accumulation_steps(held, cap) == lean["steps"]
    assert accumulation_excess(held, cap) == lean["excess"]
```

- [ ] **Step 3: Ladder-fires arg[32]** — in `test_ladder_fires_diff.py` add `severeAccumulation` to `_ORACLE_KEY`-adjacent arg builders (both `_oracle_args` Scenario builder AND the rich `drive_and_contest` arg list), deriving it independently: Scenario mirror `1 if scn.severe_accumulation else 0`; rich harness `1 if worst_accumulation_steps(w, gd) >= SEVERE_STEPS else 0`. Add a deterministic `test_sell_pressured_severe_accumulation_*` drive-true + near-miss. (Mirror the `bankJunkNonempty` arg[31] additions verbatim.)

- [ ] **Step 4: Run** — `~/.local/bin/uv run pytest formal/diff/test_accumulation_sell_diff.py formal/diff/test_ladder_fires_diff.py -q --no-cov` → PASS.

- [ ] **Step 5: Commit** — `git commit -m "feat(formal): accumulation-sell differentials (core + ladder disjunct)"`

---

### Task 8: Mutation anchors + full gate

**Files:**
- Modify: `formal/diff/mutate.py` (anchors), `docs/PLAN_*`/spec status.

- [ ] **Step 1: Add mutation anchors** (verify each KILLED via the in-memory apply→test→restore loop, NOT `git checkout` — the Lean guardrail blocks destructive checkout):
  - `accumulation_sell: ACCUM_MULT 5 -> 3` (killed by core diff at held in [3*cap, 5*cap)).
  - `accumulation_sell: drop ratio gate` (`if held < ACCUM_MULT*eff_cap: return 0` → `if False:`) — killed by below-gate diff.
  - `accumulation_sell: steps off-by-one` (`k = k + 1` → `k = k + 2`) — killed by core diff.
  - `ladder/means: SELL_PRESSURED drop severe disjunct` (`or worst_accumulation_steps(...) >= SEVERE_STEPS` → `or False`) — killed by the ladder severe drive-true test.
  Wire each into the right `run_group` (core → `test_accumulation_sell_diff.py`; means → `test_ladder_fires_diff.py`).

- [ ] **Step 2: Run the FULL gate** (no bot / no other src-importing process running first — `pgrep -af artifactsmmo`):

Run: `cd formal && bash gate.sh`
Expected: `ALL GATE PARTS PASSED`, `mutation gate OK`.

- [ ] **Step 3: Update spec status to BUILT; commit** — `git commit -m "feat(formal): accumulation-sell mutation anchors; gate green"`

- [ ] **Step 4: Finish the branch** via `superpowers:finishing-a-development-branch` (merge to main, matching the session pattern).

---

## Notes for the implementer

- Tasks 1-4 are pure Python and independently testable via pytest — land them first; the feature is functionally live (moderate idle-sell + severe firing) after Task 4 even before the formal lockstep.
- Tasks 5-8 are the formal lockstep. The State-field ripple (Task 6) + oracle/sim/diff (Tasks 6-7) MUST land together — a half-applied State field reddens the build and the ladder-fires differential, exactly as documented for DRAIN_BANK_JUNK. Do not commit Task 6 with a red `lake build`.
- The DRAIN_BANK_JUNK merge commit (`git log --grep "drain-bank-junk\|DRAIN_BANK_JUNK"`) is the line-by-line template for every formal site in Tasks 6-7.
- Run `git diff src` after any `mutate.py` run to confirm sources are clean (the serialize-gate-runs lesson).
