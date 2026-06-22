# C3 — ReachCurrency Funding Subgoal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Add a plannable `ReachCurrencyGoal(currency, target)` that drives the accept→progress→complete task loop (C2 made completion mint coins) until `currency ≥ target`, with a kernel-proved guarantee that the loop TERMINATES and the goal's planning depth is SUFFICIENT (so the GOAP search never times out the way the original 641K-node burn did).

**Architecture:** A new goal mirroring `ReachUnlockLevelGoal`. A pure core `funding_cycles_pure(on_hand, target, floor)` (ceil-div cycle bound) that is LIVE in the goal's `max_depth` (× actions-per-cycle), so the search is bounded correctly. Lean `Formal/Liveness/CurrencyFunding.lean` proves SUFFICIENCY (those cycles, each adding ≥floor≥1 coins, reach target) and DESCENT (the remaining-coins measure strictly drops each cycle → termination).

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (Liveness namespace — mathlib ALLOWED here, per memory `project_liveness_axiom_split`), Hypothesis differential, `mutate.py`, pytest.

## Global Constraints

- `~/.local/bin/uv run` for Python; `lake` at `~/.elan/bin/lake` (NOT `~/.local/bin/lake`) — `export PATH="$HOME/.elan/bin:$PATH"`. Package/oracle already built; builds INCREMENTAL; do NOT clean `.lake`.
- Imports at top; no inline imports; no `if TYPE_CHECKING`; absolute imports. NEVER catch `Exception`. Use API data or fail.
- ONE behavioral class per file. Tests in `tests/`. Touched modules → 100% coverage.
- Builds on C1+C2 (same branch). `GameData.task_coin_reward`/`min_task_coin_reward` (≥1, enforced) exist from C2; `CompleteTaskAction.apply` mints coins.
- DEPLOY GATE: C1–C4 deploy together. C3 makes the goal EXIST + plannable + proven; the arbiter DEMAND ROUTING (when to select it) is C4. C3 does NOT wire the arbiter.
- `mutate.py` only with the bot stopped (it is). `git diff src` clean after.

## Design constants
- `ACTIONS_PER_CYCLE = 3` — one funding cycle ≈ AcceptTask + one progress action (Fight/Craft) + CompleteTask. `max_depth = max(<floor>, funding_cycles * ACTIONS_PER_CYCLE)`.
- The per-task floor for projection = `game_data.min_task_coin_reward()` (≥1, enforced at load in C2).

---

### Task 1: Currency-total helper + the funding-cycles pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/funding_core.py`
- Test: `tests/test_ai/test_funding_core.py`

**Interfaces:**
- Produces: `funding_cycles_pure(on_hand: int, target: int, per_task_floor: int) -> int` — `0` if `on_hand >= target`, else `ceil((target - on_hand) / per_task_floor)`. Precondition `per_task_floor >= 1` (caller passes `min_task_coin_reward()` which is ≥1).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_ai/test_funding_core.py
"""Pure core: cycles needed to fund a currency target, given a per-task floor."""
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure


def test_already_funded_zero_cycles():
    assert funding_cycles_pure(8, 8, 2) == 0
    assert funding_cycles_pure(10, 8, 2) == 0


def test_exact_multiple():
    assert funding_cycles_pure(0, 8, 2) == 4


def test_ceil_rounds_up():
    assert funding_cycles_pure(0, 9, 2) == 5   # ceil(9/2)
    assert funding_cycles_pure(3, 8, 2) == 3    # ceil(5/2)


def test_floor_one():
    assert funding_cycles_pure(0, 8, 1) == 8
```

- [ ] **Step 2: Run, verify failure** — `~/.local/bin/uv run pytest tests/test_ai/test_funding_core.py -v` → FAIL (module not found).

- [ ] **Step 3: Write the pure core**

```python
# src/artifactsmmo_cli/ai/goals/funding_core.py
"""Pure core: how many accept→complete task cycles fund a currency target.

Extracted so the formal differential test (`formal/diff/test_currency_funding_diff.py`)
can exercise it against the kernel-proved Lean
`Formal.Liveness.CurrencyFunding.fundingCycles`, whose `fundingCycles_sufficient`
theorem proves these many cycles (each adding ≥ the floor ≥ 1 coin) REACH the
target — so `ReachCurrencyGoal.max_depth` (∝ this count) admits a complete plan and
the GOAP search does not time out. `funding_remaining_descends` proves termination
(the remaining-coins measure strictly drops each cycle).
"""


def funding_cycles_pure(on_hand: int, target: int, per_task_floor: int) -> int:
    """Cycles to raise `on_hand` to `target`, each cycle yielding at least
    `per_task_floor` (≥1) coins: 0 if already funded, else ceil((target-on_hand)/floor).
    Caller guarantees `per_task_floor >= 1` (it is `min_task_coin_reward()`)."""
    if on_hand >= target:
        return 0
    deficit = target - on_hand
    return (deficit + per_task_floor - 1) // per_task_floor
```

- [ ] **Step 4: Run, verify pass.** Commit:
```bash
git add src/artifactsmmo_cli/ai/goals/funding_core.py tests/test_ai/test_funding_core.py
git commit -m "feat(goals): funding_cycles_pure — task cycles to fund a currency target (C3)"
```

---

### Task 2: Lean liveness model — sufficiency + descent

**Files:**
- Create: `formal/Formal/Liveness/CurrencyFunding.lean`
- Modify: `formal/Formal.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean` (imports + roster + pins)

**Interfaces:**
- Produces: `Formal.Liveness.CurrencyFunding.fundingCycles (onHand target floor : Nat) : Nat`
- Theorems: `fundingCycles_sufficient` (`1 ≤ floor → target ≤ onHand + fundingCycles onHand target floor * floor`); `funding_remaining_descends` (`coins < target → 1 ≤ floor → target - (coins + floor) < target - coins`).

- [ ] **Step 1: Write the Lean model**

```lean
-- formal/Formal/Liveness/CurrencyFunding.lean
-- @concept: liveness, tasks @property: termination, sufficiency
/-
Termination/sufficiency model for `ReachCurrencyGoal` funding
(`src/artifactsmmo_cli/ai/goals/funding_core.py::funding_cycles_pure`).

A funding plan repeats accept→progress→complete cycles; each completed task mints
≥ `floor` (≥1) `tasks_coin` (C2 `CompleteTaskIncome.applyComplete_monotone`). This
proves:
  * SUFFICIENCY: `fundingCycles` cycles, each adding ≥ floor, REACH the target —
    so `ReachCurrencyGoal.max_depth` (∝ fundingCycles) admits a complete plan and
    the GOAP search terminates with a plan rather than the budget timeout that
    caused the original 641K-node burn.
  * DESCENT: while under target, one cycle strictly drops the remaining-coins
    measure `target - coins` — the well-founded termination argument.

Liveness namespace — mathlib permitted (Nat.div lemmas).
-/
import Mathlib.Algebra.Order.Group.Nat
import Mathlib.Data.Nat.Defs

namespace Formal.Liveness.CurrencyFunding

/-- Cycles to fund: 0 if already at target, else ceil((target-onHand)/floor). -/
def fundingCycles (onHand target floor : Nat) : Nat :=
  if target ≤ onHand then 0 else (target - onHand + floor - 1) / floor

/-- **SUFFICIENCY.** With `floor ≥ 1`, completing `fundingCycles` cycles — each
adding at least `floor` coins — reaches `target`. The depth bound is enough. -/
theorem fundingCycles_sufficient (onHand target floor : Nat) (h : 1 ≤ floor) :
    target ≤ onHand + fundingCycles onHand target floor * floor := by
  unfold fundingCycles
  split
  · -- target ≤ onHand
    rename_i hle; omega
  · -- onHand < target: ceil-div property  deficit ≤ ⌈deficit/floor⌉ * floor
    rename_i hgt
    have hkey : (target - onHand) ≤ ((target - onHand + floor - 1) / floor) * floor :=
      Nat.le_div_mul_self_of_ceil ..  -- PLACEHOLDER: see Step 1b for the real lemma
    omega

/-- **DESCENT.** While under target, one cycle (adding ≥1) strictly reduces the
remaining-coins measure — the termination witness. -/
theorem funding_remaining_descends (coins target floor : Nat)
    (hlt : coins < target) (h : 1 ≤ floor) :
    target - (coins + floor) < target - coins := by omega

/-! ### Non-vacuity witnesses. -/
example : fundingCycles 0 8 2 = 4 := by decide
example : fundingCycles 0 9 2 = 5 := by decide
example : fundingCycles 8 8 2 = 0 := by decide
-- sufficiency is real, not vacuous: 0 + 4*2 = 8 ≥ 8.
example : (8 : Nat) ≤ 0 + fundingCycles 0 8 2 * 2 := by decide

end Formal.Liveness.CurrencyFunding
```

- [ ] **Step 1b: Discharge the ceil-div lemma (the one non-trivial proof)**

The `hkey` line is a placeholder. The real obligation is `n ≤ ((n + floor - 1) / floor) * floor` for `floor ≥ 1` (with `n = target - onHand > 0`). Find the mathlib lemma via lean-lsp tooling (`lean_leansearch`/`lean_loogle` for "Nat ceil div mul le" / `Nat.lt_div_add_one_mul_self` / `Nat.div_mul_le_self` companions, or `Nat.le_div_iff_mul_le`). Candidate proof:
```lean
    have : target - onHand + floor - 1 = (target - onHand - 1) + floor := by omega
    -- ((m + floor)/floor)*floor ≥ m+1 > m  via Nat.div_mul_le_self / Nat.lt_succ_mul_div
    ...
```
**FALLBACK if the ceil-div lemma proves stubborn:** redefine `fundingCycles` by structural recursion so sufficiency is inductive (avoids ceil-div algebra), and make `funding_cycles_pure` match it:
```lean
def fundingCycles : Nat → Nat → Nat → Nat
  | onHand, target, floor =>
    if target ≤ onHand then 0
    else 1 + fundingCycles (onHand + floor) target floor
  termination_by onHand target _ => target - onHand
  decreasing_by simp_wf; omega   -- needs floor ≥ 1 in scope; pass floor ≥ 1 or use floor+1
```
with the Python core mirrored as a loop. If you take the fallback, update `funding_cycles_pure` AND the differential test to match the recursive count (same numeric result for floor ≥ 1). Prefer the ceil-div form if the lemma is found; the recursive form is the guaranteed-provable fallback. EITHER WAY: `fundingCycles_sufficient` and `funding_remaining_descends` must be real, non-vacuous theorems, and the Python core must compute the SAME number (differential-checked in Task 4).

- [ ] **Step 2: Imports + Manifest + Contracts**

`formal/Formal.lean`: `import Formal.Liveness.CurrencyFunding`
`formal/Formal/Manifest.lean`: import + roster (after the C2 CompleteTaskIncome block):
```lean
-- CurrencyFunding required roles (ReachCurrencyGoal funding termination;
-- src/artifactsmmo_cli/ai/goals/funding_core.py):
#check @Formal.Liveness.CurrencyFunding.fundingCycles_sufficient   -- depth bound reaches target
#check @Formal.Liveness.CurrencyFunding.funding_remaining_descends -- measure strictly drops
```
`formal/Formal/Contracts.lean`: import + pins (after C2 pins):
```lean
-- ─── CurrencyFunding (ReachCurrencyGoal funding) anti-weakening pins ───
example : ∀ (onHand target floor : Nat), 1 ≤ floor →
    target ≤ onHand + Formal.Liveness.CurrencyFunding.fundingCycles onHand target floor * floor :=
  @Formal.Liveness.CurrencyFunding.fundingCycles_sufficient
example : ∀ (coins target floor : Nat), coins < target → 1 ≤ floor →
    target - (coins + floor) < target - coins :=
  @Formal.Liveness.CurrencyFunding.funding_remaining_descends
```

- [ ] **Step 3: Build + axiom check + commit**

`cd formal && export PATH="$HOME/.elan/bin:$PATH" && lake build` — must succeed, no sorry. `#print axioms` for both theorems: mathlib axioms (propext/Classical.choice/Quot.sound) only; NO sorryAx/native_decide. Commit the 4 files.

---

### Task 3: Oracle handler + differential

**Files:** Modify `formal/Oracle.lean`; Create `formal/diff/test_currency_funding_diff.py`.

- [ ] **Step 1: Oracle handler + route**

After the C2 `runCompleteTaskIncome` in Oracle.lean:
```lean
-- CurrencyFunding: cycles to fund a currency target. args = [onHand, target, floor]
def runCurrencyFunding (args : Array Json) : Json :=
  let c := Formal.Liveness.CurrencyFunding.fundingCycles
    (intArg args 0).toNat (intArg args 1).toNat (intArg args 2).toNat
  Json.mkObj [("cycles", Json.num (Int.ofNat c))]
```
…and `else if kind == "currency_funding" then runCurrencyFunding args` in `runOne`.

- [ ] **Step 2: Differential test**

```python
# formal/diff/test_currency_funding_diff.py
"""Differential: funding_cycles_pure must equal the kernel-proved
Formal.Liveness.CurrencyFunding.fundingCycles over all valid inputs (floor ≥ 1)."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from formal.diff.oracle_client import run_oracle

_n = st.integers(min_value=0, max_value=300)
_floor = st.integers(min_value=1, max_value=20)


@given(on_hand=_n, target=_n, floor=_floor)
def test_funding_cycles_matches_oracle(on_hand, target, floor):
    py = funding_cycles_pure(on_hand, target, floor)
    lean = run_oracle("currency_funding", [[on_hand, target, floor]])[0]["cycles"]
    assert py == lean, (f"divergence at (on_hand={on_hand}, target={target}, "
                        f"floor={floor}): py={py} lean={lean}")


def test_sufficiency_spotcheck_both_sides():
    """The cycle count is enough: on_hand + cycles*floor >= target."""
    on_hand, target, floor = 0, 8, 2
    cycles = funding_cycles_pure(on_hand, target, floor)
    assert run_oracle("currency_funding", [[on_hand, target, floor]])[0]["cycles"] == cycles
    assert on_hand + cycles * floor >= target
```

- [ ] **Step 3: Rebuild oracle, run differential (worktree root), commit.**
`cd formal && export PATH="$HOME/.elan/bin:$PATH" && lake build oracle`; `~/.local/bin/uv run pytest formal/diff/test_currency_funding_diff.py -v`. If the Task-2 FALLBACK (recursive def) was taken, ensure `funding_cycles_pure` matches it numerically — any divergence is a Python/Lean mismatch to fix in the CORE/handler, never by weakening the test.

---

### Task 4: ReachCurrencyGoal (the live goal)

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/reach_currency.py`
- Test: `tests/test_ai/test_reach_currency_goal.py`

**Interfaces:**
- `ReachCurrencyGoal(currency: str, target: int)` — `Goal` subclass. `max_depth` calls `funding_cycles_pure` (the LIVE consumer). `is_satisfied`: `currency_total ≥ target`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_ai/test_reach_currency_goal.py
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from tests.test_ai.fixtures import make_state


def test_satisfied_when_currency_at_target():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 8})) is True
    assert g.is_satisfied(make_state(inventory={TASKS_COIN_CODE: 5})) is False


def test_max_depth_is_property_sufficient_for_worst_case():
    # worst case on_hand=0, floor=1 -> 8 cycles * 3 actions = 24. `max_depth` is a
    # PROPERTY (no args), matching Goal.max_depth.
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    assert g.max_depth == 8 * 3


def test_relevant_actions_keeps_task_lifecycle_and_progress():
    g = ReachCurrencyGoal(TASKS_COIN_CODE, 8)
    acts = [AcceptTaskAction(taskmaster_location=(0, 0)),
            CompleteTaskAction(taskmaster_location=(0, 0)),
            FightAction(monster_code="chicken", ...)]
    kept = g.relevant_actions(acts, make_state(), <gd>)
    assert any(isinstance(a, AcceptTaskAction) for a in kept)
    assert any(isinstance(a, CompleteTaskAction) for a in kept)
```
(Fill the GameData/FightAction construction from the existing `tests/test_ai/test_actions.py::make_game_data` + the FightAction signature used there. Reuse, don't hand-roll.)

- [ ] **Step 2: Run, verify failure.**

- [ ] **Step 3: Write the goal** (mirror `ReachUnlockLevelGoal`)

```python
# src/artifactsmmo_cli/ai/goals/reach_currency.py
"""ReachCurrencyGoal: complete tasks until a currency (e.g. tasks_coin) reaches
a target, to fund a task-currency purchase (jasper_crystal @ tasks_trader).

max_depth is bounded by funding_cycles_pure (proved sufficient in
Formal.Liveness.CurrencyFunding.fundingCycles_sufficient), so the GOAP search has
enough depth to assemble the accept→progress→complete loop without the budget
timeout that pegged the planner before this capability existed."""
from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState

ACTIONS_PER_CYCLE = 3   # accept + one progress action + complete
PRIORITY_WHEN_NEEDED = 1.0  # placeholder ranking; demand routing is C4


class ReachCurrencyGoal(Goal):
    """Drive the task loop until `currency` count reaches `target`."""

    def __init__(self, currency: str, target: int) -> None:
        self._currency = currency
        self._target = target

    def _on_hand(self, state: WorldState) -> int:
        bank = state.bank_items or {}
        return state.inventory.get(self._currency, 0) + bank.get(self._currency, 0)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        return PRIORITY_WHEN_NEEDED

    def is_satisfied(self, state: WorldState) -> bool:
        return self._on_hand(state) >= self._target

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        return {"inventory": {self._currency: self._target}}

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        return [a for a in actions
                if isinstance(a, (AcceptTaskAction, CompleteTaskAction,
                                  FightAction, CraftAction))]

    @property
    def max_depth(self) -> int:
        # Conservative WORST CASE: on_hand=0 and the minimum possible floor=1 give
        # the MOST cycles (== target), so this depth is always enough for any
        # actual on_hand≥0 / floor≥1 (Formal...fundingCycles_sufficient). `max_depth`
        # is a PROPERTY (Goal.max_depth) — no state/gd available, hence the static
        # worst case. funding_cycles_pure is the LIVE proved-core caller.
        cycles = funding_cycles_pure(0, self._target, 1)
        return max(ACTIONS_PER_CYCLE, cycles * ACTIONS_PER_CYCLE)

    def __repr__(self) -> str:
        return f"ReachCurrency({self._currency}, {self._target})"
```
`max_depth` is a `@property` matching `Goal.max_depth` (base.py:59-62, default 15). It uses the worst-case `funding_cycles_pure(0, target, 1)` (= target) so no state/gd is needed and the depth is always sufficient. `min_task_coin_reward` is NOT used here (the worst-case floor=1 ≤ any real floor ⇒ real funding needs ≤ this many cycles). The goal therefore has no `gd` dependency in `max_depth`.

- [ ] **Step 4: Run tests, verify pass. Confirm live core:** `grep -rn funding_cycles_pure src/` shows the call in reach_currency.py. Commit.

---

### Task 5: Differential/live consistency + mutation coverage

**Files:** Modify `formal/diff/mutate.py`.

- [ ] **Step 1: Add the mutation group** (verify `old` strings against the actual `funding_core.py` text):
```python
FUNDING_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "funding_core.py"
```
(add to `_ALL_SRCS`)
```python
FUNDING_MUTATIONS = [
    ("funding_cycles: drop the ceil rounding (floor-div understates cycles)",
     "    return (deficit + per_task_floor - 1) // per_task_floor",
     "    return deficit // per_task_floor"),
    ("funding_cycles: ignore on_hand (always full target)",
     "    deficit = target - on_hand",
     "    deficit = target"),
    ("funding_cycles: drop already-funded short-circuit",
     "    if on_hand >= target:\n        return 0",
     "    if False:\n        return 0"),
]
```
`run_group(FUNDING_CORE_SRC, FUNDING_MUTATIONS, "formal/diff/test_currency_funding_diff.py", survivors)`

- [ ] **Step 2: Bot stopped → run `--only currency_funding`** → 0 survivors. `git diff --stat src` clean. Commit.

NOTE: the "drop already-funded short-circuit" mutant: with `on_hand >= target`, the unguarded ceil-div of a non-positive deficit (negative in Python int) would give a wrong count — the differential's `on_hand >= target` cases catch it (oracle returns 0, mutant returns ≤0 ≠ 0 for on_hand>target). If a mutant SURVIVES, the differential's input ranges may not cover the killing case — widen the strategy (don't pad with a fake assertion). Report any survivor.

---

## Self-Review
- New plannable funding goal: Task 4 (mirrors ReachUnlockLevelGoal). ✓
- Proved core LIVE: `funding_cycles_pure` in `max_depth` — Task 4 (verify grep). ✓
- Termination/sufficiency proof (non-vacuous, the C3 liveness obligation): Task 2. ✓
- Floor ≥1 sourced from C2's enforced `min_task_coin_reward`: Tasks 4. ✓
- Differential + mutation: Tasks 3, 5. ✓
- Demand routing deferred to C4 (no arbiter change here). ✓
- RISK: Task 2 ceil-div sufficiency lemma may need lean-lsp search; recursive-def fallback provided (keep sufficiency non-vacuous either way). The `max_depth` signature must match `goals/base.py` (Task 4 NOTE) — resolve before implementing.

## Out of scope (C4)
- Arbiter demand routing: select `ReachCurrencyGoal` when a chosen objective's currency-buy leaf is unaffordable.
- Deep-leaf buy emission (jasper_crystal NpcBuy in GatherMaterials) + affordability fast-fail + end-to-end satchel plan.
