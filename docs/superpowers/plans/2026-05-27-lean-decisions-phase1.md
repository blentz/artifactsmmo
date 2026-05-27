# Lean AI Decision-Logic Phase 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Prove independent *intent* properties of four suspected-buggy AI decision-logic functions in Lean 4; where a proof can't close because the property is false, fix the Python (smallest correct change) and re-prove green — each landing through the existing `formal/gate.sh`.

**Architecture:** For each target: minimally refactor the Python into a *pure core* (lift store/clock/game_data reads to parameters), mirror it in a computable Lean `def`, state the intent theorem(s), fix the bug the unprovable theorem reveals, prove green, and add a Hypothesis differential test (real Python core vs Lean oracle) + ≥3 killed mutations. Gate enforces kernel build, axiom lint, manifest roles, statement contracts, differential fidelity, mutation kills.

**Tech Stack:** Lean 4 (v4.30.0, core only, no mathlib), `lake`; Python 3.13 with `uv run`; Hypothesis (deterministic "formal" profile); existing `formal/diff/` harness + `mutate.py`.

**Worktree:** `.claude/worktrees/lean-decisions` (branch `formal-lean-decisions`). All paths below are repo-relative to that worktree.

**Reference patterns:** copy the shape of an existing simple component end-to-end before starting — `formal/Formal/InventoryCaps.lean` (def + theorems), `formal/diff/test_inventory_caps_diff.py` (oracle differential), `formal/diff/mutate.py` (mutation catalogue entries), `formal/Formal/Manifest.lean` / `Contracts.lean` / `Audit.lean` (role wiring). The Lean oracle dispatch lives in `formal/oracle/` (one JSON case per component).

**Cross-task discipline (every task):**
- Run `./formal/gate.sh` before committing; it must be green.
- `#print axioms <thm>` for each new theorem ⊆ {`propext`, `Classical.choice`, `Quot.sound`}. No `sorry`/`admit`/custom axiom/`native_decide`.
- Existing Python test suite stays green after any refactor/fix: `uv run pytest` (0 errors, 0 warnings, 0 skipped, 100% coverage).
- A behavioral/tuning change (a threshold or constant that alters intended strategy, not a clear correctness defect) is **STOP-and-flag to the user**, not a unilateral edit. The cap *value* in Task 1 is such a flag point.
- Differential test ≥200 examples; mutation entries ≥3 per target, each must be killed.

---

### Task 1: `dynamic_priority.learned_priority_bonus` — survival-floor safety (STRONGLY suspected bug)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/dynamic_priority.py`
- Create: `formal/Formal/DynamicPriority.lean`
- Modify: `formal/Formal.lean` (add `import Formal.DynamicPriority`), `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`, `formal/Formal/Audit.lean`, `formal/oracle/` dispatch
- Create: `formal/diff/test_dynamic_priority_diff.py`
- Modify: `formal/diff/mutate.py`

- [ ] **Step 1: Read the target and confirm the pure core boundary**

Read `src/artifactsmmo_cli/ai/learning/dynamic_priority.py`. Identify the pure arithmetic: `bonus = scalar_yield * weight * confidence`, `confidence = min(1.0, sample_count / CONFIDENCE_CAP_SAMPLES)`, and the early-returns (history None / 0 samples / scalar ≤ 0 → 0.0). Note where `store`/history is read (the impure boundary) vs the arithmetic (the pure core).

- [ ] **Step 2: Extract the pure core (behavior-preserving refactor)**

Introduce a module-level pure function taking the already-fetched scalars, and have the existing method call it. No behavior change yet:

```python
def bonus_from_observed(
    observed_scalar: float,
    sample_count: int,
    weight: float,
    confidence_cap_samples: int,
) -> float:
    """Pure core of learned_priority_bonus: no store/IO reads."""
    if sample_count <= 0 or observed_scalar <= 0.0:
        return 0.0
    confidence = min(1.0, sample_count / confidence_cap_samples)
    return observed_scalar * weight * confidence
```

The public `learned_priority_bonus` fetches history from the store, then `return bonus_from_observed(...)`.

- [ ] **Step 3: Run the existing suite to confirm the refactor is behavior-preserving**

Run: `uv run pytest tests/ -q`
Expected: PASS, unchanged from baseline (0 errors/warnings/skips, 100% coverage).

- [ ] **Step 4: Write the faithful Lean model**

`formal/Formal/DynamicPriority.lean`. Use an order-preserving integer surrogate for the floats (scalar, weight in milli-units), exact `Nat`/`Int` arithmetic; disclose the surrogate in the header. Model `bonusFromObserved` and the effective discretionary priority `effPrio base bonus = base + bonus`.

```lean
namespace Formal.DynamicPriority
/-- scalar, weight scaled to integer milli-units; confidence as (num,den). -/
def bonusFromObserved (observed weightMilli sampleCount capSamples : Nat) : Nat :=
  if sampleCount = 0 ∨ observed = 0 then 0
  else
    let confNum := min sampleCount capSamples
    -- bonus = observed * weightMilli * confNum / (capSamples * 1000)
    (observed * weightMilli * confNum) / (capSamples * 1000)
end Formal.DynamicPriority
```

- [ ] **Step 5: State the intent theorem — and watch it fail to close**

The claim the docstring implies: a discretionary goal's effective priority stays strictly below the survival floor (70). Write it; attempt to prove. It will NOT close as written because `bonusFromObserved` is unbounded above (large `observed`).

```lean
/-- INTENT (expected unprovable as written): discretionary effective priority < floor. -/
theorem disc_below_floor
    (observed weightMilli sampleCount capSamples base : Nat)
    (hbase : base ≤ MAX_DISCRETIONARY_BASE) :
    effPrio base (bonusFromObserved observed weightMilli sampleCount capSamples) < SURVIVAL_FLOOR := by
  sorry -- cannot close: bonus unbounded
```

Document the counterexample (e.g. `observed` huge ⇒ bonus ≫ 70). This is the located bug. Do NOT leave the `sorry`.

- [ ] **Step 6: STOP — flag the fix shape and cap value to the user**

The correctness fix is "the bonus MUST be bounded so discretionary base+bonus < survival floor". The exact cap *value* / mechanism (clamp bonus to `SURVIVAL_FLOOR − MAX_DISCRETIONARY_BASE − 1`, vs excluding survival goals, vs clamping effective priority) is a behavioral/tuning decision. Present options + recommendation; get the user's choice before editing Python.

- [ ] **Step 7: Apply the approved fix to the pure core**

Add the agreed bound to `bonus_from_observed` (e.g. `return min(raw, BONUS_CAP)`), mirror in `bonusFromObserved`. Keep the constant named and sourced where the user approved.

- [ ] **Step 8: Re-prove the intent theorem green**

Replace the `sorry` with a real proof (the bound now makes `effPrio base bonus < SURVIVAL_FLOOR` provable by `omega`/`Nat.lt_of...`). Build.

Run: `lake build` (in `formal/`)
Expected: PASS, no `sorry`.

- [ ] **Step 9: Wire manifest / contract / audit + oracle dispatch**

Add to `Manifest.lean`: `#check @Formal.DynamicPriority.disc_below_floor` (role `survival-floor-safety`). Add to `Contracts.lean` the strong statement `example : <full disc_below_floor stmt> := @disc_below_floor`. Add an `Audit.lean` line. Add the JSON oracle case in `formal/oracle/`.

- [ ] **Step 10: Write the differential test**

`formal/diff/test_dynamic_priority_diff.py`: Hypothesis generates `(observed_scalar, sample_count, weight, cap)`; assert real `bonus_from_observed` (post-fix) equals the Lean oracle (within the surrogate's quantization) over ≥200 cases, AND assert the proven invariant on the Python side (`base + bonus < 70` for `base ≤ MAX_DISCRETIONARY_BASE`).

- [ ] **Step 11: Add mutations**

In `mutate.py`, add ≥3 mutants of `bonus_from_observed`: drop the cap (`min` removed), flip `<= 0` to `< 0`, change `min(1.0, …)` to `max`. Each must be killed by the differential/invariant test.

- [ ] **Step 12: Run the full gate, then commit**

Run: `./formal/gate.sh`
Expected: green (build, axioms, manifest, contracts, differential, mutations all pass).

```bash
git add -A
git commit -m "fix(ai): bound learned_priority_bonus below survival floor; prove in Lean"
```

---

### Task 2: `meta_goal.owned_count` — double-count under equipped items

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/meta_goal.py`
- Create: `formal/Formal/OwnedCount.lean`
- Modify: `formal/Formal.lean`, `Manifest.lean`, `Contracts.lean`, `Audit.lean`, `formal/oracle/`
- Create: `formal/diff/test_owned_count_diff.py`
- Modify: `formal/diff/mutate.py`

- [ ] **Step 1: Read target + locate the WorldState invariant**

Read `meta_goal.py` `owned_count`. Inspect the WorldState model and the API client to determine empirically: does an equipped item code ever also appear in `inventory`? Search `src/` and `artifactsmmo-api-client` for how `inventory` vs `equipment`/slots are populated. Record the finding.

- [ ] **Step 2: Extract the pure core**

```python
def owned_count_pure(
    inventory: Mapping[str, int],
    bank: Mapping[str, int] | None,
    equipped_codes: Collection[str],
    code: str,
) -> int:
    """Pure core: total owned across the three stores."""
    total = inventory.get(code, 0)
    if bank is not None:
        total += bank.get(code, 0)
    if code in equipped_codes:
        total += 1
    return total
```

`owned_count` builds `equipped_codes` from `equipment.values()` and calls this.

- [ ] **Step 3: Run suite** — Run: `uv run pytest tests/ -q`; Expected: PASS unchanged.

- [ ] **Step 4: Lean model + the disjointness invariant**

`formal/Formal/OwnedCount.lean`: model the three stores as `code → Nat` counts and an `equipped : code → Bool`. Define `ownedCount` mirroring the Python and `trueTotal inv bank equippedCount`.

```lean
def ownedCount (inv bank : String → Nat) (equipped : String → Bool) (code : String) : Nat :=
  inv code + bank code + (if equipped code then 1 else 0)
```

- [ ] **Step 5: State the intent theorem under the invariant**

```lean
/-- INTENT: ownedCount equals the true total IFF equipped items are not also
    counted in inventory (disjointness). -/
theorem ownedCount_correct
    (inv bank : String → Nat) (equipped : String → Bool) (code : String)
    (hdisjoint : equipped code = true → inv code = 0) :
    ownedCount inv bank equipped code
      = inv code + bank code + (if equipped code then 1 else 0) := rfl
-- and the contrapositive: WITHOUT hdisjoint, equipped∧inv>0 ⇒ overcount
theorem ownedCount_overcounts_when_equipped_in_inventory
    (inv bank : String → Nat) (equipped : String → Bool) (code : String)
    (heq : equipped code = true) (hinv : inv code > 0) :
    ownedCount inv bank equipped code > bank code + max (inv code) 1 := by
  simp [ownedCount, heq]; omega
```

(Make `ownedCount_correct` non-vacuous: the contract is the overcount theorem, which has teeth.)

- [ ] **Step 6: Resolve with the differential finding**

- If Step 1 found equipped codes NEVER appear in inventory: the invariant holds → document it as an enforced invariant (assert/comment in `owned_count`), prove `ownedCount_correct`, ship. No behavioral change.
- If equipped CAN appear in inventory: this is a **double-count bug** → STOP-and-flag the fix (count equipment separately / `1 if equipped and code not in inventory`), get user choice, fix, prove the post-fix `ownedCount = trueTotal` unconditionally.

- [ ] **Step 7: Manifest/Contracts/Audit/oracle wiring** (as Task 1 Step 9).

- [ ] **Step 8: Differential test**

`test_owned_count_diff.py`: Hypothesis generates inventory/bank/equipped dicts; assert Python `owned_count_pure` == Lean oracle ≥200 cases. Include a strategy that draws real-WorldState-shaped inputs to exercise the invariant.

- [ ] **Step 9: Mutations** — ≥3: drop the bank branch, change `+1` to `+2`, drop the `code in equipped` guard. Each killed.

- [ ] **Step 10: Gate + commit**

Run: `./formal/gate.sh` (green). Then:
```bash
git add -A
git commit -m "formal(ai): prove owned_count total under equipped-disjointness invariant"
```
(commit subject becomes `fix(ai): …` if Step 6 took the bug branch.)

---

### Task 3: `progression` upgrade selection — ranking total-order + commitment idempotence (the tangle)

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/progression.py`
- Create: `formal/Formal/UpgradeSelection.lean`
- Modify: `formal/Formal.lean`, `Manifest.lean`, `Contracts.lean`, `Audit.lean`, `formal/oracle/`
- Create: `formal/diff/test_upgrade_selection_diff.py`
- Modify: `formal/diff/mutate.py`

- [ ] **Step 1: Read + map the selection logic**

Read `progression.py`: `_best_by_value(inv, craft)`, `_find_craftable_upgrade_target` key `(relevant_tool, fills_empty, value, -craft_level, item_code)`, `_find_inventory_upgrade` key `(relevant, value, level, item_code)`, `_committed_upgrade_if_ready`, `_is_upgrade_over_impl`. Note the documented wooden_stick (`_best_by_value` returns strictly-worse) and fishing_net (commitment substituted) bug classes.

- [ ] **Step 2: Extract pure cores**

Lift to module-level pure functions over candidate value-objects (a small frozen dataclass of the fields the keys use), no store reads:

```python
@dataclass(frozen=True)
class UpgradeCandidate:
    item_code: str
    value: int
    level: int
    craft_level: int
    relevant_tool: bool
    fills_empty: bool

def best_by_value(inv: UpgradeCandidate | None, craft: UpgradeCandidate | None) -> UpgradeCandidate | None: ...
def craftable_key(c: UpgradeCandidate) -> tuple: ...   # (relevant_tool, fills_empty, value, -craft_level, item_code)
def inventory_key(c: UpgradeCandidate) -> tuple: ...    # (relevant, value, level, item_code)
def select_committed(committed_code: str | None, candidates: list[UpgradeCandidate]) -> UpgradeCandidate | None: ...
```

Existing methods build candidates from game_data then delegate.

- [ ] **Step 3: Run suite** — Run: `uv run pytest tests/ -q`; Expected: PASS unchanged. (If extraction can't preserve behavior, that itself is a finding — STOP and report.)

- [ ] **Step 4: Lean model**

`formal/Formal/UpgradeSelection.lean`: model `Candidate` as a structure, `craftableKey`/`inventoryKey` as lexicographic comparators returning `Ordering`, `bestByValue`, and `selectCommitted`.

- [ ] **Step 5: Intent theorems (expect ≥1 to fail → bug)**

```lean
/-- _best_by_value never returns the strictly-worse item (wooden_stick regression). -/
theorem best_by_value_not_worse (inv craft : Candidate) :
    (bestByValue (some inv) (some craft)).value ≥ max inv.value craft.value := by sorry
/-- craftable key is a strict total order ⇒ deterministic argmax. -/
theorem craftableKey_total (a b : Candidate) :
    craftableCmp a b = .lt ∨ craftableCmp a b = .eq ∨ craftableCmp a b = .gt := by decide_or_omega
theorem craftableKey_antisymm (a b : Candidate) :
    craftableCmp a b = .lt → craftableCmp b a = .gt := by sorry
theorem craftableKey_trans (a b c : Candidate) :
    craftableCmp a b = .lt → craftableCmp b c = .lt → craftableCmp a c = .lt := by sorry
/-- commitment idempotence: a set commitment is returned exactly, never substituted. -/
theorem select_committed_exact (code : String) (cs : List Candidate)
    (hmem : ∃ c ∈ cs, c.item_code = code) :
    (selectCommitted (some code) cs).map (·.item_code) = some code := by sorry
```

For each that won't close: produce the concrete counterexample (the failing field/key), confirm via differential, that's the bug.

- [ ] **Step 6: Fix the located bugs (smallest correct change), flag tuning**

Correctness defects (strictly-worse return; non-total key from a non-comparable field; commitment substitution) → fix in the pure core in place. Any change that alters intended *preference ordering* (e.g. reordering key fields by design) → STOP-and-flag. Re-prove each theorem green; remove all `sorry`.

- [ ] **Step 7: Manifest/Contracts/Audit/oracle wiring** (roles: `no-downgrade`, `key-total-order`, `commitment-idempotence`).

- [ ] **Step 8: Differential test**

`test_upgrade_selection_diff.py`: Hypothesis generates candidate lists; assert Python `best_by_value` / sorted-by-key / `select_committed` match the Lean oracle ≥200 cases; assert no strictly-worse selection.

- [ ] **Step 9: Mutations** — ≥3: flip `>=` to `>` in tie handling, swap two key fields, drop the commitment short-circuit. Each killed.

- [ ] **Step 10: Gate + commit**

Run: `./formal/gate.sh` (green). Then:
```bash
git add -A
git commit -m "fix(ai): correct progression upgrade selection ordering; prove total-order + commitment in Lean"
```

---

### Task 4: `scalarizer.scalar_yield` — monotonicity, weight dominance, coin-inversion

**Files:**
- Modify: `src/artifactsmmo_cli/ai/learning/scalarizer.py`
- Create: `formal/Formal/Scalarizer.lean`
- Modify: `formal/Formal.lean`, `Manifest.lean`, `Contracts.lean`, `Audit.lean`, `formal/oracle/`
- Create: `formal/diff/test_scalarizer_diff.py`
- Modify: `formal/diff/mutate.py`

- [ ] **Step 1: Read target**

Read `scalarizer.py`: `scalar_yield = char_xp*1.0*(level+1) + Σ(skill_xp*weight[2.0 relevant|0.2 baseline]) + gold/100 + coins*coin_value/100`; and `expected_coin_value_with_prices` with `coins_spent = received − cycle.delta_inv_used`.

- [ ] **Step 2: Extract pure cores**

```python
def scalar_yield_pure(
    char_xp: int, level: int,
    skill_xp: Mapping[str, int], relevant_skills: Collection[str],
    gold: int, coins: int, coin_value_milli: int,
    relevant_weight_milli: int, baseline_weight_milli: int,
) -> int:  # returns milli-scaled score for exact comparison
    ...
def coins_spent_pure(received: int, delta_inv_used: int) -> int:
    return received - delta_inv_used
```

- [ ] **Step 3: Run suite** — Run: `uv run pytest tests/ -q`; Expected: PASS unchanged.

- [ ] **Step 4: Lean model** — `formal/Formal/Scalarizer.lean`: `scalarYield` over `Nat` milli-units; `coinsSpent (received delta : Int) : Int := received - delta`.

- [ ] **Step 5: Intent theorems**

```lean
/-- non-decreasing in char_xp (and analogously each component). -/
theorem scalarYield_mono_charxp (a b : Nat) (h : a ≤ b) (rest …) :
    scalarYield a … ≤ scalarYield b … := by …
/-- relevant-skill weight dominates baseline weight. -/
theorem relevant_weight_dominates : baselineWeightMilli ≤ relevantWeightMilli := by decide
/-- coin inversion: coins_spent solves recorded delta = received − coins_spent. -/
theorem coinsSpent_inverts (received delta : Int) :
    received - coinsSpent received delta = delta := by ring
```

Add monotonicity for each yield component (skill_xp, gold, coins) given non-negative weights/values. If any won't close (e.g. a sign error makes a component decrease the score), that's the bug.

- [ ] **Step 6: Fix any located bug** (sign error / non-monotone weight) smallest-change, re-prove. Pure-tuning weight *values* → flag.

- [ ] **Step 7: Manifest/Contracts/Audit/oracle wiring** (roles: `component-monotonicity`, `weight-dominance`, `coin-inversion`).

- [ ] **Step 8: Differential test** — `test_scalarizer_diff.py`: Hypothesis generates yield components + weights; assert Python `scalar_yield_pure` == Lean oracle ≥200 cases; assert monotonicity by comparing pairs where one component is bumped.

- [ ] **Step 9: Mutations** — ≥3: flip `received - delta` to `delta - received`, swap relevant/baseline weights, change `+ gold` to `- gold`. Each killed.

- [ ] **Step 10: Gate + commit**

Run: `./formal/gate.sh` (green). Then:
```bash
git add -A
git commit -m "formal(ai): prove scalar_yield monotonicity, weight dominance, coin-inversion"
```

---

### Task 5: Phase-1 wrap-up

- [ ] **Step 1: Full gate green from clean tree** — Run: `./formal/gate.sh`; Expected: all six parts pass.
- [ ] **Step 2: Full Python suite** — Run: `uv run pytest`; Expected: 0 errors, 0 warnings, 0 skipped, 100% coverage.
- [ ] **Step 3: Update `formal/README.md`** — coverage table 14 → 18 components; list the four decision-logic components and the bugs found/fixed.
- [ ] **Step 4: Commit the README + write a findings note** in the plan's tail or a short `docs/postmortems/` entry summarizing which intent theorems failed (= bugs) and the fixes.
- [ ] **Step 5: Merge** — FF-merge `formal-lean-decisions` into `main`, push (only on user say-so, per session policy).

---

## Self-Review

**Spec coverage:** Design §"Phase 1" lists exactly four suspects — Tasks 1–4 map 1:1 (dynamic_priority survival floor; meta_goal owned_count; progression best_by_value/keys/commitment; scalarizer monotonicity/coin-inversion). Design "bug policy" (fix-then-prove, flag tuning) is encoded as the STOP-and-flag steps (1.6, 2.6, 3.6, 4.6). Design "architecture" 6-step per-target loop is the task substructure. Design "out of scope" honored — only pure cores modeled; store/game_data reads lifted to params. Task 5 covers the design's README/coverage expectation.

**Placeholder scan:** Lean proof bodies use `sorry` deliberately and ONLY in Step-5 "expected-to-fail" theorem statements, each paired with an explicit Step-8/6 instruction to replace it with a real proof and a cross-task rule forbidding committed `sorry`. No "TBD"/"handle edge cases"/"similar to". Python extraction signatures are concrete.

**Type consistency:** `bonus_from_observed`/`bonusFromObserved`, `owned_count_pure`/`ownedCount`, `UpgradeCandidate`/`Candidate` + `craftable_key`/`craftableCmp`, `scalar_yield_pure`/`scalarYield` + `coins_spent_pure`/`coinsSpent` — names consistent within each task between Python and Lean. Manifest `#check @Formal.<NS>.<thm>` matches the namespaces declared in each Lean file.

**Note:** the `decide_or_omega` token in Task 3 Step 5 is shorthand — use whichever of `decide`/`omega`/`cases` closes the goal; total-order over a finite tuple of `Nat`/`Bool`/`String` fields is decidable.
