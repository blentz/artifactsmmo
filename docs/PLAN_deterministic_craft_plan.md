# Deterministic Craft-Plan — Implementation Plan (proof-first)

> **For agentic workers:** REQUIRED SUB-SKILLS: `formal-development` (orchestrator), `lean4:formalize`/`lean4:prove` (proofs), `superpowers:subagent-driven-development` or `executing-plans` (task execution), `superpowers:test-driven-development` (Python). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Craftable obtain-goals plan deterministically from the static recipe closure + inventory+bank netting, emitting `Withdraw` for banked intermediates so they never fall to the 50K-node A* over a bank gate. Attacks the measured 97%-of-search-cost (copper_ring 1.78M / copper_helmet 570K / copper_pickaxe 255K A* nodes).

**Spec:** `docs/superpowers/specs/2026-06-23-deterministic-craft-plan-design.md`

**Architecture:** Extend the *already-proven* `NextCraftAction` core (`formal/Formal/NextCraftAction.lean` ↔ `src/artifactsmmo_cli/ai/next_craft_core.py`) with a `withdraw` action kind and a bank input, in lockstep across Lean def + theorems + Contracts pin + differential + mutation. Add a per-item static recipe-cost memo over the existing `closure_demand`. A* remains the unchanged fallback for genuinely non-deterministic leaves (skill-gated / monster-drop / NPC).

**Tech Stack:** Python 3.13, `uv`, Lean 4 + Mathlib (`formal/`), Hypothesis differential harness, pytest.

## Global Constraints

- Run all Python via `uv run`; never run `formal/gate.sh` (or `mutate.py`) concurrently with anything importing `src` (poisons predicates — see project history). `git diff src` after every gate run must be empty.
- Imports at top; no inline / `if TYPE_CHECKING` / `...` imports. Never catch `Exception`.
- One behavioral class per file; pure cores extracted into `*_core.py` so the differential test calls them without I/O.
- **Proof discipline (formal-development):** prove a computable Lean `def` that mirrors the algorithm ∀ inputs (no bounds); no `sorry`/`admit`/`native_decide`/custom axioms; axiom lint must show only `{propext, Classical.choice, Quot.sound}`. Differential test calls the LIVE function (never inlines the formula). Mutation must kill every perturbation — a surviving mutant fails the gate.
- Tests: 0 errors, 0 warnings, 0 skipped, 100% coverage (`--cov-fail-under=100`).
- `formal/gate.sh` green at the end of every phase. Update `formal/Formal/Manifest.lean` + `formal/Formal/Contracts.lean` + `formal/README.md` roster in the same commit as any theorem change.
- A* fallback retained throughout — any state the generator still refuses degrades to today's behavior, never to "no plan".
- Branch `feat/deterministic-craft-plan` off `main` before Task 1.

**Existing artifacts to extend (verbatim):**
- `formal/Formal/NextCraftAction.lean`: `inductive Kind | gather | craft`; `structure NextAction (item, kind, qty)`; `def nextHelper`; `def nextCraftTarget`; theorems `nextCraftTarget_none_iff`, `nextHelper_craft_inputs_satisfied` (ORDERING), `nextHelper_qty_pos`, `nextCraftTarget_qty_pos`.
- `src/artifactsmmo_cli/ai/next_craft_core.py`: `next_craft_target_pure(recipes, owned, target, qty)`, `_next`, `NextAction`.
- `src/artifactsmmo_cli/ai/craft_plan_gen.py`: `generate_next_craft_action` (bank-gate refusal at `:134-144`).
- `src/artifactsmmo_cli/ai/recipe_closure.py`: `closure_demand`/`_closure_demand` (`:71,133`).
- `formal/diff/test_next_craft_diff.py`; `formal/diff/oracle/` client; `formal/diff/mutate.py`.

## Proof boundary (theorem roles)

| Component | Lean module | Roles to prove |
|---|---|---|
| **NextCraftAction (extended)** | `NextCraftAction.lean` | `none-iff` (unchanged, re-established over widened input), `ordering` (craft ⇒ all inputs on hand), `qty-positive` (all kinds), **NEW `withdraw-validity`** (withdraw returned ⇒ item is a craftable intermediate, short in inventory, present in bank), **NEW `withdraw-qty`** (withdraw qty = min(bank, deficit) ≥ 1) |
| **RecipeCostMemo (Phase A)** | none (pure cache of proven `closure_demand`) | differential-equivalence to uncached `closure_demand` only — no new theorem |
| **CraftPlanDriver (Phase B2, gated)** | `CraftPlanDriver.lean` | `termination` (iteration fuel-bounded by closure × qty; strict measure decrease), `correctness` (applying emitted plan in order from owned-state ⇒ `owned[target] ≥ qty`) |

---

## Phase A — static recipe-cost memo

Pure caching of the already-proven `closure_demand`. No new decision logic; the only gate addition is a differential equality check (memo ≡ uncached).

### Task A1: `RecipeCostMemo`

**Files:**
- Create: `src/artifactsmmo_cli/ai/recipe_cost_memo.py`
- Test: `tests/test_ai/test_recipe_cost_memo.py`
- Modify: `src/artifactsmmo_cli/ai/game_data.py` (own the memo instance; invalidate on reload)

**Interfaces:**
- Produces: `RecipeCostMemo(recipes: dict[str, dict[str,int]])` with `full_cost(item: str) -> dict[str,int]` returning the memoized transitive demand (`closure_demand(item, 1)`); `clear()` on game-data reload.

- [ ] **Step 1: Failing test** — assert `full_cost("copper_ring")` equals a direct `closure_demand("copper_ring", 1, ...)` call, and that a second call returns the identical cached object (memoized), and `clear()` drops it.

```python
# tests/test_ai/test_recipe_cost_memo.py
from artifactsmmo_cli.ai.recipe_cost_memo import RecipeCostMemo
from artifactsmmo_cli.ai.recipe_closure import closure_demand
# build a small recipes dict {copper_ring:{copper_bar:6}, copper_bar:{copper_ore:10}}
# assert memo.full_cost("copper_ring") == expected net transitive demand
# assert memo.full_cost("copper_ring") is memo.full_cost("copper_ring")  # cached identity
# assert after clear(), recompute happens (new object)
```

(Implementer: read `recipe_closure.py:71,133` for the exact `closure_demand` signature/return shape and mirror it; the memo wraps it with a `dict[str, dict[str,int]]` cache keyed on item code.)

- [ ] **Step 2:** run red. **Step 3:** implement memo (plain dict cache; `full_cost` computes via `closure_demand` on miss). **Step 4:** green.
- [ ] **Step 5: Differential equivalence** — add to `formal/diff/test_recipe_closure_diff.py` (or a new `test_recipe_cost_memo_diff.py`) a Hypothesis property: for random valid recipe DAGs + item, `memo.full_cost(item) == closure_demand(item, 1, ...)`. This pins the memo to the proven function (no new Lean theorem needed — `closure_demand` is already proved; we only prove the cache doesn't change the value).
- [ ] **Step 6:** wire `GameData` to own a `RecipeCostMemo`, `clear()` on reload; update hot consumers (`craft_plan_gen.py`, `gathering.py:relevant_actions`) to read `game_data.recipe_cost.full_cost(...)` instead of recomputing — ONLY where it's a drop-in for an existing `closure_demand`/closure recompute. Do not change behavior.
- [ ] **Step 7:** `uv run pytest` 100%; `bash formal/gate.sh` green; `git diff src` empty post-gate. Commit `feat(craft-plan): static per-item recipe-cost memo`.

---

## Phase B1 — `withdraw` action kind in the proven core

The load-bearing change. Extend the Lean def + Python core together so a banked craftable intermediate emits `withdraw` instead of dead-ending.

### Task B1-1: extend the Lean model + prove (driven by lean4:formalize/prove)

**Files:** `formal/Formal/NextCraftAction.lean`, `formal/Formal/Manifest.lean`, `formal/Formal/Contracts.lean`, `formal/README.md`

- [ ] **Step 1:** Add `| withdraw` to `inductive Kind`. Add a `bank : String → Nat` parameter to `nextHelper`/`nextCraftTarget` (inventory stays `owned`). New descent rule: when the deepest short input is a craftable (recipe present) AND `owned item < need` AND `bank item > 0` → emit `⟨item, .withdraw, min (bank item) (need - owned item)⟩`; else the existing gather/craft rules. Keep the fuel/totality guard.
- [ ] **Step 2:** State + prove the role theorems (∀ inputs, no bounds), using `lean4:formalize` / `lean4:prove`:
  - `nextHelper_withdraw_valid`: result.kind = withdraw ⇒ `recipes result.item ≠ none` ∧ `owned result.item < need` ∧ `bank result.item > 0`.
  - `nextHelper_withdraw_qty`: result.kind = withdraw ⇒ `result.qty = min (bank item) (need - owned item)` ∧ `result.qty ≥ 1`.
  - Re-establish `nextHelper_craft_inputs_satisfied` (ORDERING) and `nextCraftTarget_none_iff` over the widened signature (craft now requires inputs satisfied in inventory-or-after-withdraw per the chosen model — keep the model faithful to the Python).
  - Extend `nextCraftTarget_qty_pos` to the withdraw kind.
- [ ] **Step 3:** Add the new theorem names to `Manifest.lean`; pin EXACT statements in `Contracts.lean` (`example : <full statement> := @theoremName`) for the new roles AND any re-stated role. Update the `formal/README.md` roster row.
- [ ] **Step 4:** `lake build` green; `bash formal/check_axioms.sh` (or the gate's axiom-lint part) shows only `{propext, Classical.choice, Quot.sound}` for every NextCraftAction role. No `sorry`/`native_decide`. Commit `feat(formal): NextCraftAction withdraw branch + proofs`.

### Task B1-2: mirror in the Python core (TDD)

**Files:** `src/artifactsmmo_cli/ai/next_craft_core.py`, `tests/test_ai/test_next_craft_core.py`

**Interfaces:** `NextAction.kind` gains `"withdraw"`; `next_craft_target_pure(recipes, owned, bank, target, qty)` gains a `bank` arg (the Lean def's `bank` parameter). Document the exact arg order so the differential oracle matches.

- [ ] **Step 1:** Failing tests mirroring the Lean rules: a banked intermediate + short inventory ⇒ `NextAction(item, "withdraw", min(bank,deficit))`; raw still gathers; all-on-hand still crafts; withdraw qty ≥ 1.
- [ ] **Step 2:** run red. **Step 3:** implement the `withdraw` branch in `_next` exactly mirroring the Lean descent (inventory-then-bank). **Step 4:** green.
- [ ] **Step 5:** Commit `feat(craft-plan): next_craft_core withdraw branch (mirrors Lean)`.

### Task B1-3: differential + mutation (the teeth)

**Files:** `formal/diff/test_next_craft_diff.py`, `formal/diff/oracle/` (Lean oracle JSON I/O), `formal/diff/mutate.py` anchors

- [ ] **Step 1:** Extend the oracle to accept the new `bank` input + `withdraw` output kind (Lean `Oracle.lean` evaluating `nextCraftTarget` with bank). 
- [ ] **Step 2:** Extend the Hypothesis harness: generate random valid `(recipes, inventory, bank, target, qty)` — INCLUDING states with banked intermediates — feed BOTH `next_craft_target_pure` (live function, not inlined) and the oracle, assert agreement on item/kind/qty. Ensure the generator actually reaches the withdraw branch (assert coverage of `kind=="withdraw"` in the sample, else the differential is vacuous on the new path).
- [ ] **Step 3:** Run `formal/diff/mutate.py` over `next_craft_core.py`; confirm mutants on the withdraw branch (e.g. `min`→`max`, `<`→`<=`, drop bank check, withdraw→gather) are KILLED. Add anchors as needed. A surviving withdraw-branch mutant = gate fail.
- [ ] **Step 4:** `bash formal/gate.sh` full green; `git diff src` empty. Commit `test(formal): differential + mutation for withdraw branch`.

---

## Phase B3 — wire the generator (drop the bank-gate refusal)

### Task B3-1: `generate_next_craft_action` emits Withdraw

**Files:** `src/artifactsmmo_cli/ai/craft_plan_gen.py`, `tests/test_ai/test_craft_plan_gen.py`

- [ ] **Step 1:** Failing test: a `GatherMaterialsGoal(copper_ring, {copper_bar:6})` with `copper_bar` in BANK and short inventory ⇒ `generate_next_craft_action` returns a `WithdrawItemAction(copper_bar, ...)` (NOT None, NOT an A* fallback). Use real fixtures (the existing test module's GameData fixture).
- [ ] **Step 2:** run red (today it returns None → bank-gate refusal). 
- [ ] **Step 3:** Pass `bank` into `next_craft_target_pure` (merge `owned=inventory`, `bank=state.bank_items`); REMOVE the bank-gate refusal branch (`:134-144`); map the new `"withdraw"` `NextAction` to a concrete `WithdrawItemAction` from `goal.relevant_actions` (mirror how gather/craft are mapped at `:166`). Keep the OTHER refusals (skill gate `:114-115`, no workshop `:116-117`, monster-drop/NPC leaf `:118-121`) untouched.
- [ ] **Step 4:** green. Confirm the other refusals still return None (regression tests for skill-gated / monster-drop closures still fall to A*).
- [ ] **Step 5:** `uv run pytest` 100%; `bash formal/gate.sh` green (the differential now exercises the wired path through the core); `git diff src` empty. Commit `feat(craft-plan): emit Withdraw for banked intermediates (no A* bank-gate)`.

### Task B3-2: measurement gate for B2

- [ ] **Step 1:** Document how to re-measure: run the Phase-1 bot a stretch on a state with banked intermediates, then `artifactsmmo macro-research --out report.md` and inspect GatherMaterials total A* nodes for copper_ring/helmet/pickaxe.
- [ ] **Step 2:** **DECISION POINT** — if bank-gate items now show ~0 A* nodes, Phase B is COMPLETE (Phase-1 plan-cache + plan[0]-with-withdraw suffices); **do NOT build B2**. If they still show A* nodes, proceed to Phase B2. Record the decision in `docs/PLAN_deterministic_craft_plan.md`.

---

## Phase B2 — full-plan driver (BUILD ONLY IF B3-2 measurement says so)

A new proven component: iterate the next-action descent to completion, emitting the whole plan. The most expensive formal work (termination + correctness). Skip entirely if B1+B3 already zeroed the cost.

### Task B2-1: Lean model + termination/correctness proof

**Files:** `formal/Formal/CraftPlanDriver.lean`, `Manifest.lean`, `Contracts.lean`, `README.md`

- [ ] **Step 1:** `def craftPlan (recipes owned bank target qty fuel) : List NextAction` — iterate `nextCraftTarget`, applying each action's effect to a local `(owned, bank)` copy, accumulating actions until `owned target ≥ qty` or fuel exhausted. Fuel bound = `(closure size) * qty + 1`.
- [ ] **Step 2:** Prove (lean4:prove):
  - `craftPlan_terminates`: with `fuel ≥ (closure size)*qty+1`, the loop reaches `owned target ≥ qty` (a strict measure — total remaining deficit over the closure — decreases each step).
  - `craftPlan_correct`: folding the emitted actions' effects over the initial `(owned, bank)` yields `final_owned target ≥ qty`.
- [ ] **Step 3:** Manifest + Contracts pins + README roster. `lake build` + axiom lint green. Commit.

### Task B2-2: Python driver + differential + mutation

**Files:** `src/artifactsmmo_cli/ai/craft_plan_driver_core.py`, wire into `craft_plan_gen.py`, `formal/diff/test_craft_plan_driver_diff.py`, tests

- [ ] **Step 1–4:** TDD the Python driver mirroring `craftPlan`; differential harness (live function vs oracle) over random valid inputs reaching multi-step plans incl withdraw; mutation kills perturbations (e.g. off-by-one fuel, wrong effect application, dropped step). 100% coverage.
- [ ] **Step 5:** `bash formal/gate.sh` green; `git diff src` empty. Commit `feat(craft-plan): full-plan driver (proven termination + correctness)`.

---

## Phase C — final verification

- [ ] **Step 1:** Full `uv run pytest --cov=src/artifactsmmo_cli --cov-report=term-missing -q` — 0/0/0, 100%.
- [ ] **Step 2:** Full `bash formal/gate.sh` — all 7 parts green (kernel build, no-sorry/orphan, axiom lint, manifest, contracts, differential, mutation). `git diff --stat src/` empty.
- [ ] **Step 3: Adversarial proof review (formal-development Phase 4)** — read every NEW/CHANGED theorem statement against reachable program states: is the withdraw-validity theorem non-vacuous (satisfiability witness — a state that actually triggers withdraw)? Does the differential reach the withdraw branch (not silently skipped)? Is `min(bank,deficit)` actually modeled, not abstracted? Use `lean4:review` + a `superpowers:requesting-code-review` pass. Hunt the dishonest-proof patterns (vacuous hypotheses, rigged generators, surrogate domains).
- [ ] **Step 4:** Commit any review fixes; final gate green.

---

## Self-Review

**Spec coverage:**
- Static recipe-cost memo → Phase A. ✓
- Withdraw-banked-intermediate (the decisive bank-gate fix) → Phase B1 (core+proof) + B3 (wiring). ✓
- Full-plan driver, gated on measurement → Phase B2 (conditional). ✓
- A* fallback retained / other refusals unchanged → B3-1 Step 3-4 (explicit). ✓
- Formal extension in lockstep (Manifest/Contracts/differential/mutation) → B1-1/B1-3, B2-1/B2-2. ✓
- Adversarial review → Phase C Step 3. ✓

**Theorem-role consistency:** the `withdraw-validity` / `withdraw-qty` roles named in the proof-boundary table match Tasks B1-1; `termination`/`correctness` match B2-1. `next_craft_target_pure` gains a `bank` arg consistently across B1-2 (Python), B1-3 (oracle), B3-1 (caller).

**Known risk:** the Lean re-statement of `nextCraftTarget_none_iff` / ORDERING over the widened (bank-carrying) signature must stay faithful to the Python `_next` — the differential is the backstop, but the adversarial review (Phase C) must confirm the model didn't quietly weaken to ease the proof. The Contracts.lean pin guards against silent statement-weakening.

**Carve-out:** none — every new module carries provable decision logic except the `RecipeCostMemo` (pure cache, justified by the differential-equivalence check in A1 Step 5).
