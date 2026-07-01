# Potion Supply (CraftPotions) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A preemptive guard-tier `CraftPotionsGoal` that incrementally stocks the equipped utility-slot health-potion stack toward a level-scaled baseline — crafting from held ingredients, else buying the optimal ingredient mix, else gathering a 5-potion batch and replanning.

**Architecture:** Add equipped utility-slot quantities to `WorldState` (from `CharacterSchema`). Three float-free proven cores (fire decision, max-batch-from-held, optimal-buy-mix) with Lean mirrors + differential + mutation. A new `CraftPotionsGoal` wired into the GUARD tier (preemptive, like `RestoreHP`) so it can interrupt the grind to stock potions while its weight exceeds a fixed bar (70).

**Tech Stack:** Python 3.13, `uv`, pytest (100% coverage gate), Lean 4 + Lake (`formal/Oracle.lean` dispatcher, `formal/diff/` differential, `formal/diff/mutate.py` mutation), `fractions.Fraction` for exact rationals.

## Global Constraints

- Run every Python command via `uv run` (binary at `/home/blentz/.local/bin/uv` if `uv` isn't on PATH — the shell has a literal `~/.local/bin` that doesn't expand).
- Coverage gate: 0 errors, 0 warnings, 0 skipped, 100%. Use `--no-cov` for subset runs; the final task runs the full gate.
- ONE behavioral class per file. No inline imports. No `if TYPE_CHECKING`. Never catch `Exception`. Use only API data or fail.
- Proven cores are float-free (integer / `Fraction`): pure core + Lean mirror in `formal/Formal/<Name>.lean` + oracle branch in `formal/Oracle.lean` + differential test in `formal/diff/test_<name>_diff.py` + mutation anchors in `formal/diff/mutate.py`. Mirror the existing `marginal_potion_qty` end-to-end (`Oracle.lean` dispatch is an `if kind == "..."` chain ~line 2660; `intArg(args, i)` helper ~line 132; build with `cd formal && lake build <Module>` then `lake build oracle`).
- Commit messages end with: `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Spec: `docs/superpowers/specs/2026-06-30-potion-supply-design.md`. Branch: `feat/potion-supply`.
- Constants (add to `thresholds.py`): `POTION_LOW_LEVEL = 5`, `POTION_LOW_QTY = 5`, `POTION_HIGH_LEVEL = 45`, `POTION_HIGH_QTY = 100`, `POTION_GATHER_BATCH = 5`. The level→baseline curve is linear from `(5 → 5)` to `(45 → 100)`. `UTILITY_SLOT_MAX_STACK = 100` already exists (= `POTION_HIGH_QTY`).

---

## File Structure

| File | Responsibility |
|---|---|
| `src/artifactsmmo_cli/ai/world_state.py` | add `utility1_slot_quantity`/`utility2_slot_quantity`; populate from schema |
| `src/artifactsmmo_cli/ai/equipped_potion.py` | NEW: `equipped_potion_qty(state, code)` helper |
| `src/artifactsmmo_cli/ai/actions/equip.py` | `apply` updates utility-slot quantity (top-up semantics) |
| `src/artifactsmmo_cli/ai/potion_baseline.py` | NEW pure core: level→baseline curve |
| `src/artifactsmmo_cli/ai/max_batch_from_held.py` | NEW pure core: craftable batch from held |
| `src/artifactsmmo_cli/ai/optimal_buy_mix.py` | NEW pure core: max affordable batch |
| `formal/Formal/PotionBaseline.lean`, `MaxBatchFromHeld.lean`, `OptimalBuyMix.lean` | Lean mirrors |
| `formal/Oracle.lean`, `formal/diff/*`, `formal/diff/mutate.py` | oracle + differential + mutation |
| `src/artifactsmmo_cli/ai/goals/craft_potions.py` | NEW `CraftPotionsGoal` |
| `src/artifactsmmo_cli/ai/tiers/guards.py`, `strategy_driver.py` | GUARD wiring |
| `src/artifactsmmo_cli/ai/thresholds.py` | constants |

---

## Task 1: WorldState equipped utility-slot quantities

**Files:**
- Modify: `src/artifactsmmo_cli/ai/world_state.py` (dataclass fields + `from_character_schema`)
- Create: `src/artifactsmmo_cli/ai/equipped_potion.py`
- Test: `tests/test_ai/test_world_state.py` (find it: `grep -rl "from_character_schema" tests/`), `tests/test_ai/test_equipped_potion.py`

**Interfaces:**
- Produces: `WorldState.utility1_slot_quantity: int`, `WorldState.utility2_slot_quantity: int` (default 0). `equipped_potion.equipped_potion_qty(state: WorldState, code: str) -> int` — total quantity of `code` across utility slots.

- [ ] **Step 1: Read the current dataclass + builder.** Read `world_state.py` around the `@dataclass` field block and `from_character_schema`. Note the field style (frozen dataclass) and how `utility1_slot` is read (`_require(char, "utility1_slot")`). The schema also has `utility1_slot_quantity: int` / `utility2_slot_quantity: int` (verified in the client model).

- [ ] **Step 2: Write failing tests**

```python
def test_world_state_carries_utility_slot_quantities():
    char = make_character_schema(utility1_slot="small_health_potion", utility1_slot_quantity=40,
                                 utility2_slot="", utility2_slot_quantity=0)
    state = WorldState.from_character_schema(char, bank_items=None, bank_gold=0)
    assert state.utility1_slot_quantity == 40
    assert state.utility2_slot_quantity == 0

def test_equipped_potion_qty_sums_matching_slots():
    state = make_state(equipment={"utility1_slot": "small_health_potion", "utility2_slot": "small_health_potion"})
    state = dataclasses.replace(state, utility1_slot_quantity=40, utility2_slot_quantity=10)
    assert equipped_potion_qty(state, "small_health_potion") == 50
    assert equipped_potion_qty(state, "other") == 0
```

(Use the repo's real schema/fixture builders — `grep -rn "def make_character_schema\|CharacterSchema(" tests/`. `make_state` may need the two new kwargs; add them with default 0.)

- [ ] **Step 3: Run — expect FAIL.** `uv run pytest tests/test_ai/test_world_state.py tests/test_ai/test_equipped_potion.py -q --no-cov` → FAIL (fields/module missing).

- [ ] **Step 4: Add the fields + builder + helper.**

In `world_state.py` dataclass (after the equipment field, matching the frozen-dataclass style):
```python
    utility1_slot_quantity: int = 0
    utility2_slot_quantity: int = 0
```
In `from_character_schema`, after building `equipment`, read the quantities (use the same `_require`/`getattr` access the builder uses for ints):
```python
        utility1_slot_quantity=int(_require(char, "utility1_slot_quantity") or 0),
        utility2_slot_quantity=int(_require(char, "utility2_slot_quantity") or 0),
```
(Insert into the `WorldState(...)` constructor call in the order the dataclass declares.)

Create `src/artifactsmmo_cli/ai/equipped_potion.py`:
```python
"""Quantity of a consumable currently equipped across the utility slots."""

from artifactsmmo_cli.ai.world_state import WorldState

_UTILITY_SLOTS = ("utility1_slot", "utility2_slot")
_QTY_ATTR = {"utility1_slot": "utility1_slot_quantity",
             "utility2_slot": "utility2_slot_quantity"}


def equipped_potion_qty(state: WorldState, code: str) -> int:
    """Total quantity of `code` held across the utility slots (0 if not equipped)."""
    total = 0
    for slot in _UTILITY_SLOTS:
        if state.equipment.get(slot) == code:
            total += getattr(state, _QTY_ATTR[slot])
    return total
```

- [ ] **Step 5: Run — expect PASS.** Same command → PASS. Then full suite once (`uv run pytest --no-cov -q`) to catch any constructor/`make_state` call sites needing the new defaults; fix by relying on the defaults.

- [ ] **Step 6: Commit.**
```bash
git add src/artifactsmmo_cli/ai/world_state.py src/artifactsmmo_cli/ai/equipped_potion.py tests/test_ai/
git commit -m "$(cat <<'EOF'
feat(state): model equipped utility-slot quantities

WorldState now carries utility1/2_slot_quantity from CharacterSchema (the server
exposes them), with equipped_potion_qty(state, code) summing a code across utility
slots. Foundation for level-scaled potion stocking.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 2: EquipAction utility-slot quantity apply semantics

**Files:**
- Modify: `src/artifactsmmo_cli/ai/actions/equip.py` (`apply`)
- Test: `tests/test_ai/test_actions.py` (the EquipAction tests)

**Interfaces:**
- Consumes: `WorldState.utility{1,2}_slot_quantity` (Task 1).
- Produces: `EquipAction.apply` updates the target utility slot's modeled quantity.

- [ ] **Step 1: Resolve add-vs-set semantics.** This is the spec's flagged unknown. No live TOKEN here, so determine the model from evidence: read the openapi description for `EquipSchema.quantity` (`grep -n "Item quantity" openapi.json`), and check whether the server replaces or stacks. Default model (document the assumption in a code comment): **equipping `q` of a code into a utility slot that already holds the SAME code ADDS to the stack (`M + q`); into an empty/different slot it SETS the quantity to `q` (returning any displaced code to inventory).** Mark the comment `# ASSUMPTION (needs live verification): utility equip is additive for same-code.` so a later live probe can confirm.

- [ ] **Step 2: Write failing tests**

```python
def test_equip_utility_sets_quantity_on_empty_slot():
    state = make_state(inventory={"small_health_potion": 50}, level=1,
                       equipment={"utility1_slot": None})
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    out = EquipAction("small_health_potion", "utility1_slot", quantity=30).apply(state, gd)
    assert out.equipment["utility1_slot"] == "small_health_potion"
    assert out.utility1_slot_quantity == 30

def test_equip_utility_adds_to_existing_same_code_stack():
    state = make_state(inventory={"small_health_potion": 50}, level=1,
                       equipment={"utility1_slot": "small_health_potion"})
    state = dataclasses.replace(state, utility1_slot_quantity=20)
    gd = _gd_with_utility_heal("small_health_potion", hp_restore=60)
    out = EquipAction("small_health_potion", "utility1_slot", quantity=30).apply(state, gd)
    assert out.utility1_slot_quantity == 50  # 20 + 30
```

- [ ] **Step 3: Run — expect FAIL.** `uv run pytest tests/test_ai/test_actions.py -k "equip_utility" -q --no-cov` → FAIL.

- [ ] **Step 4: Implement.** In `EquipAction.apply`, after the existing inventory-decrement and `new_equipment[self.slot] = self.code`, when `self.slot` is a utility slot update the modeled quantity:
```python
        qty_attr = {"utility1_slot": "utility1_slot_quantity",
                    "utility2_slot": "utility2_slot_quantity"}.get(self.slot)
        replace_kwargs = {"inventory": new_inventory, "equipment": new_equipment,
                          "cooldown_expires": None}
        if qty_attr is not None:
            prior = getattr(state, qty_attr) if old_item == self.code else 0
            replace_kwargs[qty_attr] = prior + self.quantity
        return dataclasses.replace(state, **replace_kwargs)
```
(Keep the non-utility path identical to today. `old_item` is the code previously in the slot — when it equals `self.code` we add, else we set.)

- [ ] **Step 5: Run — expect PASS.** Same `-k equip_utility` command → PASS; then `uv run pytest tests/test_ai/ -k equip -q --no-cov` (existing equip tests still green).

- [ ] **Step 6: Commit.**
```bash
git add src/artifactsmmo_cli/ai/actions/equip.py tests/test_ai/test_actions.py
git commit -m "$(cat <<'EOF'
feat(equip): model utility-slot quantity on apply (additive for same code)

apply now updates utility{1,2}_slot_quantity: equipping more of the same code adds
to the stack; a new/different code sets it. ASSUMPTION flagged for live probe.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 3: Pure core `potion_baseline_pure` (+ Lean, differential, mutation)

The level→baseline curve: how many potions to maintain at a given level. Smooth linear ramp from `(low_level → low_qty)` to `(high_level → high_qty)`, clamped. Float-free integer. The fire decision (Tasks 6/7) is `equipped_qty < potion_baseline_pure(level, ...)`.

**Files:**
- Create: `src/artifactsmmo_cli/ai/potion_baseline.py`, `tests/test_ai/test_potion_baseline.py`
- Create: `formal/Formal/PotionBaseline.lean`, `formal/diff/test_potion_baseline_diff.py`
- Modify: `formal/Oracle.lean`, `formal/diff/mutate.py`

**Interfaces:**
- Produces: `potion_baseline_pure(level: int, low_level: int, low_qty: int, high_level: int, high_qty: int) -> int`.

- [ ] **Step 1: Write failing tests**

```python
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure

def _b(level):  # (5 -> 5) to (45 -> 100)
    return potion_baseline_pure(level, 5, 5, 45, 100)

def test_flat_low_through_low_level():
    assert _b(1) == 5
    assert _b(5) == 5

def test_full_at_and_above_high_level():
    assert _b(45) == 100
    assert _b(50) == 100

def test_linear_ramp_between():
    # 5 + floor(95*(level-5)/40)
    assert _b(6) == 7      # 5 + floor(95/40)=5+2
    assert _b(10) == 16    # 5 + floor(95*5/40)=5+11
    assert _b(20) == 40    # 5 + floor(95*15/40)=5+35
    assert _b(30) == 64    # 5 + floor(95*25/40)=5+59
    assert _b(40) == 88    # 5 + floor(95*35/40)=5+83

def test_monotone_non_decreasing():
    vals = [_b(l) for l in range(1, 51)]
    assert all(a <= b for a, b in zip(vals, vals[1:]))
```

- [ ] **Step 2: Run — expect FAIL.** `uv run pytest tests/test_ai/test_potion_baseline.py -q --no-cov` → FAIL (module missing).

- [ ] **Step 3: Implement the core**

```python
"""Level-scaled potion baseline: how many potions to keep on-hand at a given level.
Flat `low_qty` through `low_level`, full `high_qty` at/above `high_level`, linear ramp
(floor) between. Float-free; mirrored bit-for-bit by formal/Formal/PotionBaseline.lean."""


def potion_baseline_pure(
    level: int, low_level: int, low_qty: int, high_level: int, high_qty: int,
) -> int:
    if level <= low_level:
        return low_qty
    if level >= high_level:
        return high_qty
    # linear interpolation, floored: low_qty + (high_qty-low_qty)*(level-low_level)//(high_level-low_level)
    return low_qty + (high_qty - low_qty) * (level - low_level) // (high_level - low_level)
```

- [ ] **Step 4: Run — expect PASS.** Same command → PASS.

- [ ] **Step 5: Lean mirror.** Create `formal/Formal/PotionBaseline.lean`:
```lean
namespace Formal.PotionBaseline

def potionBaseline (level lowLevel lowQty highLevel highQty : Nat) : Nat :=
  if level ≤ lowLevel then lowQty
  else if highLevel ≤ level then highQty
  else lowQty + (highQty - lowQty) * (level - lowLevel) / (highLevel - lowLevel)

theorem baseline_flat_low (l ll lq hl hq : Nat) (h : l ≤ ll) :
    potionBaseline l ll lq hl hq = lq := by unfold potionBaseline; simp [h]

theorem baseline_full_high (l ll lq hl hq : Nat) (h : hl ≤ l) (h2 : ¬ l ≤ ll) :
    potionBaseline l ll lq hl hq = hq := by unfold potionBaseline; simp [h, h2]

end Formal.PotionBaseline
```
Discharge with the lean4 tools; `cd formal && lake build Formal.PotionBaseline` (no `sorry`, axioms ⊆ `{propext, Quot.sound}`). Python `//` (floor) matches Lean `Nat./` (floor) for non-negative operands — the inputs are all `Nat` and `high_level > low_level` on the ramp branch, so no truncated-subtraction divergence. Add a monotonicity theorem if the lean4 tools close it readily; otherwise the differential covers monotonicity empirically.

- [ ] **Step 6: Oracle branch.** In `formal/Oracle.lean`: `import Formal.PotionBaseline` at the top; add `runPotionBaseline (args : Array Json) : Json` near `runConsumableSelection` decoding 5 ints `[level, low_level, low_qty, high_level, high_qty]` with `intArg`, returning `Json.mkObj [("baseline", Json.num (Int.ofNat (Formal.PotionBaseline.potionBaseline ...)))]`; add `else if kind == "potion_baseline" then runPotionBaseline args` to the dispatch chain (~line 2660). Build: `cd formal && lake build oracle`.

- [ ] **Step 7: Differential test.** Create `formal/diff/test_potion_baseline_diff.py`:
```python
from hypothesis import given, settings, strategies as st
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from formal.diff.oracle_client import run_oracle

@settings(max_examples=500, deadline=None)
@given(level=st.integers(1, 60))
def test_potion_baseline_matches_lean(level):
    args = [level, 5, 5, 45, 100]
    py = potion_baseline_pure(level, 5, 5, 45, 100)
    lean = run_oracle("potion_baseline", [args])[0]
    assert lean["baseline"] == py
```
Run: `uv run pytest formal/diff/test_potion_baseline_diff.py -q --no-cov` → PASS.

- [ ] **Step 8: Mutation anchors.** Add `POTION_BASELINE_MUTATIONS` to `formal/diff/mutate.py` (mirror `MARGINAL_POTION_QTY_MUTATIONS`, register in the same aggregation):
```python
POTION_BASELINE_MUTATIONS = [
    ("potion_baseline: low-clamp compare flip (<= -> <)",
     "    if level <= low_level:",
     "    if level < low_level:"),
    ("potion_baseline: high-clamp compare flip (>= -> >)",
     "    if level >= high_level:",
     "    if level > high_level:"),
    ("potion_baseline: drop the low_qty offset",
     "    return low_qty + (high_qty - low_qty) * (level - low_level) // (high_level - low_level)",
     "    return (high_qty - low_qty) * (level - low_level) // (high_level - low_level)"),
    ("potion_baseline: span sign flip (level-low_level -> low_level-level)",
     "    return low_qty + (high_qty - low_qty) * (level - low_level) // (high_level - low_level)",
     "    return low_qty + (high_qty - low_qty) * (low_level - level) // (high_level - low_level)"),
]
```
Run `uv run python formal/diff/mutate.py --only potion_baseline` → all KILLED. (If a mutant is equivalent, retire it with a documented justification, as in the marginal_potion_qty precedent.)

- [ ] **Step 9: Commit.**
```bash
git add src/artifactsmmo_cli/ai/potion_baseline.py tests/test_ai/test_potion_baseline.py formal/Formal/PotionBaseline.lean formal/diff/test_potion_baseline_diff.py formal/Oracle.lean formal/diff/mutate.py
git commit -m "$(cat <<'EOF'
feat(potions): potion_baseline_pure level->baseline curve (proven)

Smooth ramp: ~5 potions through level 5, linear to a full 100 by level 45, full
thereafter. Float-free integer; Lean mirror + differential + mutation. The fire
decision is equipped < baseline(level).

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Task 4: Pure core `max_batch_from_held_pure` (+ Lean, differential, mutation)

Max potions craftable from held ingredients: `min_i(held_i // need_i) * yield_per_craft`.

**Files:** `src/artifactsmmo_cli/ai/max_batch_from_held.py`, `tests/test_ai/test_max_batch_from_held.py`, `formal/Formal/MaxBatchFromHeld.lean`, `formal/diff/test_max_batch_from_held_diff.py`, `Oracle.lean`, `mutate.py`.

**Interfaces:**
- Produces: `max_batch_from_held_pure(needs: list[int], held: list[int], yield_per_craft: int) -> int` — `needs[i]`/`held[i]` are the per-ingredient recipe quantity and held count (same index order); returns potions craftable now (0 if any need is 0-held-short or `needs` empty).

- [ ] **Step 1: Write failing tests**
```python
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure

def test_batch_is_min_floor_times_yield():
    # need [2,3], held [10,6], yield 1 -> min(10//2, 6//3)=min(5,2)=2 runs -> 2 potions
    assert max_batch_from_held_pure([2, 3], [10, 6], 1) == 2

def test_yield_multiplies_runs():
    assert max_batch_from_held_pure([2, 3], [10, 6], 5) == 10  # 2 runs * 5

def test_zero_when_any_ingredient_short():
    assert max_batch_from_held_pure([2, 3], [10, 0], 1) == 0

def test_empty_recipe_zero():
    assert max_batch_from_held_pure([], [], 1) == 0
```

- [ ] **Step 2: Run — FAIL.** `uv run pytest tests/test_ai/test_max_batch_from_held.py -q --no-cov`.

- [ ] **Step 3: Implement**
```python
"""Max potions craftable right now from held ingredients: the min over ingredients
of held//need, times the craft yield. Float-free; mirrored by
formal/Formal/MaxBatchFromHeld.lean."""


def max_batch_from_held_pure(needs: list[int], held: list[int], yield_per_craft: int) -> int:
    if not needs:
        return 0
    runs = min(held[i] // needs[i] for i in range(len(needs)))
    return runs * yield_per_craft
```

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5–8: Lean + oracle + differential + mutation.** `MaxBatchFromHeld.lean`:
```lean
namespace Formal.MaxBatchFromHeld

def runsFold : List (Nat × Nat) → Nat → Nat
  | [], acc => acc
  | (need, have_) :: rest, acc =>
      let r := if need == 0 then 0 else have_ / need
      runsFold rest (Nat.min acc r)

def maxBatchFromHeld (pairs : List (Nat × Nat)) (yieldPerCraft : Nat) : Nat :=
  match pairs with
  | [] => 0
  | (n0, h0) :: _ => (runsFold pairs (h0 / (if n0 == 0 then 1 else n0))) * yieldPerCraft

theorem batch_zero_on_empty (y : Nat) : maxBatchFromHeld [] y = 0 := by rfl

end Formal.MaxBatchFromHeld
```
(Discharge with lean4 tools; ensure the Lean fold matches the Python `min(...)` semantics exactly — Python `needs` are always `> 0` for real recipes, so the `need==0` guard is defensive; the differential samples `need ≥ 1`.) Oracle args: `[yield, n, need_0,held_0, ..., need_{n-1},held_{n-1}]` (length-prefixed list, mirror `runConsumableSelection`'s list decode at `Oracle.lean:1554`). Differential test samples `needs` in `[1,5]`, `held` in `[0,50]`, `yield` in `[1,5]`. Mutation anchors: floor-div→ceil, `min`→`max`, drop-yield-multiply. Commit `feat(potions): max_batch_from_held_pure (proven)`.

---

## Task 5: Pure core `optimal_buy_mix_pure` (+ Lean, differential, mutation)

Largest batch `B ≤ max_batch` affordable: `cost(B) = sum_i price_i * max(0, B*need_i - held_i) ≤ gold`. Cost is monotone non-decreasing in `B`, so the answer is the largest feasible `B`.

**Files:** `src/artifactsmmo_cli/ai/optimal_buy_mix.py`, tests, `formal/Formal/OptimalBuyMix.lean`, differential, `Oracle.lean`, `mutate.py`.

**Interfaces:**
- Produces: `optimal_buy_mix_pure(needs: list[int], held: list[int], prices: list[int], gold: int, max_batch: int) -> int` — the per-ingredient buy quantity for batch `B` is `max(0, B*needs[i] - held[i])` (derived in glue). Returns `B`.

- [ ] **Step 1: Write failing tests**
```python
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure

def test_buys_up_to_affordable_batch():
    # need [1,1], held [0,0], price [2,3] -> cost(B)=5B; gold=12 -> B=2 (cost 10<=12), B=3 cost15>12
    assert optimal_buy_mix_pure([1, 1], [0, 0], [2, 3], 12, 100) == 2

def test_held_reduces_cost():
    # held covers part: need[1], held[5], price[2]; cost(B)=2*max(0,B-5); gold=4 -> B up to 7 (cost 4)
    assert optimal_buy_mix_pure([1], [5], [2], 4, 100) == 7

def test_capped_at_max_batch():
    assert optimal_buy_mix_pure([1], [100], [2], 1000, 5) == 5  # held>=need*B for B<=5; capped

def test_zero_gold_only_what_is_covered():
    # gold 0 -> can only make batches fully covered by held: need[2] held[6] -> B=3
    assert optimal_buy_mix_pure([2], [6], [5], 0, 100) == 3
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement** (linear scan from `max_batch` down, or closed-form; use the simple monotone scan — `B` is small, ≤100):
```python
"""Largest craft batch affordable by buying the per-ingredient deficit. cost(B) is
monotone non-decreasing in B, so we return the largest feasible B <= max_batch.
Float-free; mirrored by formal/Formal/OptimalBuyMix.lean."""


def _cost(needs: list[int], held: list[int], prices: list[int], batch: int) -> int:
    total = 0
    for i in range(len(needs)):
        deficit = batch * needs[i] - held[i]
        if deficit > 0:
            total += prices[i] * deficit
    return total


def optimal_buy_mix_pure(needs: list[int], held: list[int], prices: list[int],
                         gold: int, max_batch: int) -> int:
    best = 0
    for batch in range(1, max_batch + 1):
        if _cost(needs, held, prices, batch) <= gold:
            best = batch
        else:
            break  # cost monotone non-decreasing -> no larger batch is affordable
    return best
```

- [ ] **Step 4: Run — PASS.**

- [ ] **Step 5: Lean mirror + proof.** `OptimalBuyMix.lean`: define `cost` and `optimalBuyMix` as a recursive scan; prove `cost` monotone in `batch` (`cost b ≤ cost (b+1)`) and that the returned `B` is feasible and `B+1` (if `≤ max_batch`) is not. This is the hardest proof — use the lean4 proving agents; if a monotonicity lemma is intractable, escalate BLOCKED with the goal state rather than weakening. Build clean (no `sorry`, allowed axioms only).

- [ ] **Step 6–8: Oracle + differential + mutation.** Oracle args: `[gold, max_batch, n, need_0,held_0,price_0, ...]`. Differential samples `n` in `[1,3]`, `needs` `[1,4]`, `held` `[0,20]`, `prices` `[1,10]`, `gold` `[0,200]`, `max_batch` `[1,20]`. Mutation anchors: `<=`→`<` in feasibility, drop the `break`, `deficit > 0`→`>= 0`, `batch*needs[i] - held[i]`→`held[i] - batch*needs[i]`. Run `--only optimal_buy_mix` → all KILLED. Commit `formal(potions): optimal_buy_mix_pure proven + differential & mutation`.

---

## Task 6: `CraftPotionsGoal`

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/craft_potions.py`, `tests/test_ai/test_craft_potions.py`
- Modify: `src/artifactsmmo_cli/ai/thresholds.py` (constants)

**Interfaces:**
- Consumes: `potion_baseline_pure`, `max_batch_from_held_pure`, `optimal_buy_mix_pure`, `equipped_potion_qty`, `EquipAction`(quantity), `CraftAction`(quantity), `NpcBuyAction`, `GatherAction`/`WithdrawItemAction`, `recipe_closure`/`closure_demand`.
- Produces: `CraftPotionsGoal(effect: str = "hp_restore")` with `preemptive = True`.

- [ ] **Step 1: Add constants.** In `thresholds.py`:
```python
# Level-scaled potion stocking (spec 2026-06-30-potion-supply). Baseline ramps
# linearly from (level 5 -> 5 potions) to (level 45 -> 100 potions).
POTION_LOW_LEVEL = 5
POTION_LOW_QTY = 5
POTION_HIGH_LEVEL = 45
POTION_HIGH_QTY = 100             # == UTILITY_SLOT_MAX_STACK
POTION_GATHER_BATCH = 5           # gather/craft this many when gathering is required
```

- [ ] **Step 2: Investigate target-potion selection + ladder helpers.** Read `consumable_supply.best_craftable_heal` (the alchemy/craftable-heal selection pattern) and `goals/maintain_consumables.py` (recipe-closure → actions). The target potion = the `type_="utility"`, `hp_restore>0`, `crafting_skill="alchemy"`, `crafting_level <= state.skills.get("alchemy",1)` item with the highest `hp_restore` (deterministic tie-break by code); `None` ⇒ goal satisfied. Note the exact accessor names.

- [ ] **Step 3: Write failing tests**
```python
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal

def test_satisfied_when_no_craftable_target():
    state = make_state(level=3)  # no alchemy / no craftable utility heal in gd
    gd = _gd_no_alchemy_heal()
    assert CraftPotionsGoal().is_satisfied(state) is True

def test_value_is_baseline_deficit_when_understocked():
    state, gd = _state_with_craftable_potion(level=1, equipped=0)
    v = CraftPotionsGoal().value(state, gd)
    assert v == 5.0  # baseline(1)=5, equipped 0 -> deficit 5

def test_craft_from_held_emits_craft_and_equip():
    # held ingredients allow a batch -> plan includes CraftAction + EquipAction(utility1)
    state, gd = _state_with_held_potion_ingredients(level=1, equipped=0)
    actions = CraftPotionsGoal().relevant_actions(_all_actions(state, gd), state, gd)
    assert any(isinstance(a, CraftAction) for a in actions)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in actions)

def test_gather_path_bounds_to_five_potion_batch():
    # no held ingredients, not buyable -> gather actions for a 5-potion batch
    state, gd = _state_must_gather(level=3, equipped=0)
    actions = CraftPotionsGoal().relevant_actions(_all_actions(state, gd), state, gd)
    craft = next(a for a in actions if isinstance(a, CraftAction))
    assert craft.quantity == 5  # POTION_GATHER_BATCH
```

- [ ] **Step 4: Run — FAIL.**

- [ ] **Step 5: Implement the goal** (skeleton — fill the ladder per the helpers found in Step 2):
```python
"""CraftPotionsGoal: preemptively stock the equipped utility-slot potion stack toward
a level-scaled baseline. Craft from held ingredients > buy optimal mix > gather a
5-potion batch and replan. Preemptive guard-tier goal (wired in tiers/guards.py)."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.equipped_potion import equipped_potion_qty
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from artifactsmmo_cli.ai.optimal_buy_mix import optimal_buy_mix_pure
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from artifactsmmo_cli.ai.thresholds import (
    POTION_GATHER_BATCH, POTION_HIGH_LEVEL, POTION_HIGH_QTY, POTION_LOW_LEVEL,
    POTION_LOW_QTY,
)
from artifactsmmo_cli.ai.world_state import WorldState

_TARGET_SLOT = "utility1_slot"


class CraftPotionsGoal(Goal):
    """Stock the utility-slot potion stack toward a level-scaled baseline."""

    preemptive = True

    def __init__(self, effect: str = "hp_restore") -> None:
        self._effect = effect

    def _target_potion(self, state: WorldState, game_data: GameData) -> str | None:
        # Highest-hp_restore, alchemy-craftable-now utility potion; deterministic by code.
        # (Implement using the accessors found in Step 2.)
        ...

    def _equipped(self, state: WorldState, game_data: GameData) -> int:
        code = self._target_potion(state, game_data)
        return equipped_potion_qty(state, code) if code else 0

    def _baseline(self, level: int) -> int:
        return potion_baseline_pure(level, POTION_LOW_LEVEL, POTION_LOW_QTY,
                                    POTION_HIGH_LEVEL, POTION_HIGH_QTY)

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        if self.is_satisfied(state):
            return 0.0
        deficit = self._baseline(state.level) - self._equipped(state, game_data)
        return float(max(0, deficit))

    def is_satisfied(self, state: WorldState) -> bool:
        # Goal.is_satisfied has no game_data, so the producibility/target half lives in the
        # guard `_fires` predicate (Task 7, which DOES have game_data). Here, the state-only
        # signal: some utility slot is stocked to this level's baseline.
        baseline = self._baseline(state.level)
        return (state.utility1_slot_quantity >= baseline
                or state.utility2_slot_quantity >= baseline)

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        # Ladder: craft-from-held > buy-mix > gather-5; then EquipAction to top up.
        # (Build per Step 2 helpers; bound the gather path to POTION_GATHER_BATCH.)
        ...
```
Resolve the `is_satisfied` / game_data tension explicitly: because `Goal.is_satisfied(state)` has no `game_data`, put the "no producible batch / no craftable target" satisfaction into the guard `_fires` predicate (Task 7, which has `game_data`), and keep `is_satisfied` to the state-only `equipped >= max_stack` check. The guard not firing == the goal effectively satisfied for the cycle. Document this split in the goal docstring.

- [ ] **Step 6: Run — PASS.** Then full suite once.

- [ ] **Step 7: Commit** `feat(potions): CraftPotionsGoal level-scaled stocking goal`.

---

## Task 7: Wire the CRAFT_POTIONS guard

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/guards.py` (`GuardKind`, `GUARD_ORDER`, `_fires`)
- Modify: `src/artifactsmmo_cli/ai/strategy_driver.py` (`map_guard`)
- Test: `tests/test_ai/test_tiers_guards.py`, `tests/test_ai/test_strategy_driver.py`

**Interfaces:**
- Consumes: `potion_baseline_pure`, `equipped_potion_qty`, `CraftPotionsGoal`, the target-potion + producibility helpers (Task 6).
- Produces: `GuardKind.CRAFT_POTIONS` firing when `equipped_of_target < baseline(level)` AND a batch is producible now (craft-from-held OR buyable OR gatherable); `map_guard` returns `CraftPotionsGoal()`.

- [ ] **Step 1: Write failing tests**
```python
def test_craft_potions_guard_fires_when_understocked_and_producible():
    state, gd, ctx = _understocked_producible(level=3, equipped=0)  # baseline(3)=5 > 0
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is True

def test_craft_potions_guard_quiet_when_not_producible():
    state, gd, ctx = _understocked_but_no_alchemy(level=3, equipped=0)
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is False

def test_craft_potions_guard_quiet_when_stocked_to_level_baseline():
    state, gd, ctx = _stocked_to_baseline(level=3, equipped=5)  # equipped == baseline(3)=5
    assert _fires(GuardKind.CRAFT_POTIONS, state, gd, None, ctx, None) is False

def test_map_guard_returns_craft_potions_goal():
    assert isinstance(map_guard(GuardKind.CRAFT_POTIONS, _gd(), _ctx()), CraftPotionsGoal)
```

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement.** In `guards.py`: add `CRAFT_POTIONS = "craft_potions"` to `GuardKind`; insert `GuardKind.CRAFT_POTIONS` into `GUARD_ORDER` as the LAST entry (lowest-priority guard — survival/bank/discard all precede it, but it still preempts the objective-step grind). Add to `_fires`:
```python
    if kind is GuardKind.CRAFT_POTIONS:
        return craft_potions_fires(state, game_data)
```
Add a `craft_potions_fires(state, game_data) -> bool` helper (new `potion_supply.py` module — one concern per file) that: finds the target potion (None → False), computes `equipped = equipped_potion_qty(state, target)` and `baseline = potion_baseline_pure(state.level, POTION_LOW_LEVEL, POTION_LOW_QTY, POTION_HIGH_LEVEL, POTION_HIGH_QTY)`, and returns `equipped < baseline` AND a batch is producible now (held OR buyable OR gatherable). In `strategy_driver.map_guard`: `if kind is GuardKind.CRAFT_POTIONS: return CraftPotionsGoal()`.

- [ ] **Step 4: Run — PASS.** Then full suite once.

- [ ] **Step 5: Commit** `feat(potions): wire CRAFT_POTIONS preemptive guard`.

---

## Task 8: Full gate + integration + offline sanity

**Files:** test additions only as needed for coverage.

- [ ] **Step 1: Types + lint.** `uv run mypy src/ && uv run ruff check src/ tests/` → clean.
- [ ] **Step 2: Full suite + coverage.** `uv run pytest` → 0 errors/warnings/skips, 100%. Cover any uncovered new branch (target-potion None, each ladder tier, baseline at L≤5 / mid-ramp / L≥45).
- [ ] **Step 3: Full formal gate.** `cd formal && ./gate.sh` (SERIALIZE — nothing importing `src` concurrently; see memory `feedback_serialize_gate_runs`). Expect kernel green, all three new differential tests pass, every new mutant killed, axiom lint clean.
- [ ] **Step 4: Integration sanity.** Add an integration test (or drive `objective_step_goal`/the arbiter): a level-3 character with `equipped=0`, alchemy able to craft a utility health potion, held ingredients for a batch → the CRAFT_POTIONS guard fires and `map_guard` yields a `CraftPotionsGoal` whose plan crafts+equips potions (NOT the grind). And: same char with no alchemy → guard quiet → grind proceeds. Assert both.
- [ ] **Step 5: Report branch state.** `git log --oneline main..HEAD`; do not merge/push unless asked.

---

## Self-Review Notes

- **Spec coverage:** level→baseline curve → Task 3 + Task 6 (value/is_satisfied); max-batch → Task 4; buy-mix → Task 5; craft+equip ladder + gather-5 → Task 6; equipped-quantity state → Task 1; equip top-up → Task 2; guard placement (preempt while equipped < baseline) → Task 7; incremental stocking + can't-craft-more satisfaction → Task 6/7; proofs for all three cores → Tasks 3-5; gate → Task 8. All spec sections mapped.
- **Open unknowns (flagged, not placeholders):** equip add-vs-set semantics (Task 2, documented assumption + live-probe flag); exact `from_character_schema` int accessor + fixture names (Task 1, grep step); target-potion accessor names + ladder helper wiring (Task 6, grep step). Each has a concrete resolution step.
- **Type consistency:** core signatures identical across their core/Lean/diff/goal tasks; `equipped_potion_qty`, `CraftPotionsGoal(effect)`, the three `*_pure` signatures, and the constants are used consistently in Tasks 6-7.
- **Behavior note:** the maintained baseline is a smooth linear ramp — ~5 potions through level 5, rising to a full 100 by level 45 (L10→16, L20→40, L30→64, L40→88), full thereafter.
