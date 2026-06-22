# C4 — Wiring + Affordability Fast-Fail + Demand Routing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development / executing-plans. Checkbox (`- [ ]`) steps.

**Goal:** Tie C1–C3 together so `satchel` becomes genuinely craftable: emit the deep-leaf `NpcBuy(jasper_crystal)` in GatherMaterials, fast-fail the craft when the currency-buy leaf is unaffordable (killing the original 641K-node burn for real), and route demand to `ReachCurrencyGoal` (C3) to fund the coins — then the craft plans end-to-end.

**Architecture:** Three live-planner integrations + one proved core. (1) `GatherMaterials.relevant_actions` emits `NpcBuyAction` for currency-buy CLOSURE leaves (mirroring the monster-drop fight-loop over `chain`). (2) A proved `currency_afford_plannable_pure` core (mirrors `SkillGateFastFail`) extends `GatherMaterials.is_plannable` to prune when a currency-buy leaf is unaffordable AND the goal cannot earn the currency (it can't — relevant_actions has no task-earning actions). (3) The arbiter injects `ReachCurrencyGoal(currency, price×qty)` when an ObtainItem step is blocked on an unaffordable currency-buy leaf. End-to-end: unaffordable → fund (no burn); affordable → buy+craft.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (core), Hypothesis differential, `mutate.py`, pytest.

## Global Constraints
- `~/.local/bin/uv run`; `lake` at `~/.elan/bin/lake` (`export PATH="$HOME/.elan/bin:$PATH"`). Incremental builds; don't clean `.lake`.
- Imports at top; no inline; absolute. NEVER catch `Exception`. API data or fail. ONE class/file. Tests in `tests/`; 100% coverage on touched modules.
- Builds on C1+C2+C3 (same branch). `ReachCurrencyGoal(currency, target)` exists at `src/artifactsmmo_cli/ai/goals/reach_currency.py`. `is_attainable`/`_producible` recognize task-currency leaves (C1). `CompleteTask` mints coins (C2). Funding goal proven-terminating (C3).
- **SOUNDNESS INVARIANT (load-bearing for the fast-fail):** `GatherMaterialsGoal.relevant_actions` must NOT include `AcceptTaskAction`/`CompleteTaskAction` (it filters to gather/craft/fight/withdraw/npcbuy). So `tasks_coin` cannot rise within a GatherMaterials A* search → an unaffordable currency-buy leaf stays unaffordable for the whole plan → pruning is sound. C4 must NOT add task actions to GatherMaterials' set (funding lives in the SEPARATE ReachCurrencyGoal).
- DEPLOY GATE LIFTS AFTER C4: once C4 lands + the full gate is green, the branch may merge and the bot restart. `mutate.py`/`gate.sh` only with the bot stopped.

---

### Task 1: Emit deep-leaf currency-buy NpcBuy in GatherMaterials.relevant_actions

**Files:**
- Modify: `src/artifactsmmo_cli/ai/goals/gathering.py` (`relevant_actions`, the closure region ~246-294)
- Test: `tests/test_ai/test_goals.py` (or the existing GatherMaterials relevant_actions test file — `grep -rl "GatherMaterialsGoal" tests/`)

**Interfaces:** none new; emits more `NpcBuyAction`s.

- [ ] **Step 1: Write a failing test** — construct a `GatherMaterialsGoal(satchel, {satchel:1})` with a GameData seeded so: satchel craftable (recipe {jasper_crystal:1,...}); jasper_crystal non-craftable, no drop, `npc_purchases('jasper_crystal') = [('tasks_trader', 8, 'tasks_coin')]`, `npc_location('tasks_trader')` set, not an event NPC. Assert `relevant_actions([...], state, gd)` includes an `NpcBuyAction(item_code='jasper_crystal', npc_code='tasks_trader', ...)`. (Reuse the existing GatherMaterials test fixtures; grep the test file for how it seeds recipes/npcs.)

- [ ] **Step 2: Run, verify FAIL** (jasper buy not emitted — only top-level `self._needed` gets buys today).

- [ ] **Step 3: Implement** — in `relevant_actions`, after the monster-drop fight loop (`for item in chain:` ~246-271) and before/within the top-level buy loop (~278), add emission for CLOSURE LEAVES that are currency-buyable. A leaf `item` in `chain` (the closure demand dict) is a currency-buy leaf when: `game_data.crafting_recipe(item) is None` AND `item not in game_data.resource_drops.values()` AND `not game_data.monsters_dropping(item)` AND `game_data.npc_purchases(item)`. For each such leaf emit, for every permanent vendor (exclude event NPCs, mirror `_permanent_vendor_purchases`):
  ```python
  for item, qty in chain.items():
      if item in self._needed:
          continue  # top-level handled by the existing loop below
      if (game_data.crafting_recipe(item) is None
              and item not in game_data.resource_drops.values()
              and not game_data.monsters_dropping(item)):
          for npc_code, _price, _currency in game_data.npc_purchases(item):
              if game_data.is_event_npc(npc_code) or game_data.npc_location(npc_code) is None:
                  continue
              result.append(NpcBuyAction(npc_code=npc_code, item_code=item,
                                         npc_location=game_data.npc_location(npc_code),
                                         quantity=qty))
  ```
  Place this where `chain` is in scope (after it's built ~135 and after the fight loop). Match the existing `NpcBuyAction(...)` constructor call shape (gathering.py:292-294).

- [ ] **Step 4: Run, verify PASS + no GatherMaterials regression** (`~/.local/bin/uv run pytest <gather test file> -q`). Commit: `feat(goals): emit NpcBuy for currency-buy recipe-closure leaves (C4)`

---

### Task 2: Affordability fast-fail pure core

**Files:**
- Create: `src/artifactsmmo_cli/ai/goals/currency_afford_core.py`
- Test: `tests/test_ai/test_currency_afford_core.py`

**Interfaces:**
- `currency_afford_plannable_pure(target_in_closure: bool, affordable: bool, owned: int, needed: int) -> bool` — `!target_in_closure || affordable || owned >= needed`. (Mirrors `gather_plannable_pure`'s shape.)

- [ ] **Step 1: Failing test**
```python
# tests/test_ai/test_currency_afford_core.py
"""Pure core: a currency-buy closure leaf is plannable iff affordable or owned."""
from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure


def test_unaffordable_unowned_not_plannable():
    assert currency_afford_plannable_pure(True, False, 0, 1) is False


def test_affordable_is_plannable():
    assert currency_afford_plannable_pure(True, True, 0, 1) is True


def test_already_owned_is_plannable():
    assert currency_afford_plannable_pure(True, False, 1, 1) is True


def test_not_a_currency_leaf_stays_plannable():
    assert currency_afford_plannable_pure(False, False, 0, 1) is True
```

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement**
```python
# src/artifactsmmo_cli/ai/goals/currency_afford_core.py
"""Pure core of GatherMaterials' currency-affordability fast-fail.

Extracted for the differential test (`formal/diff/test_currency_afford_diff.py`)
against the kernel-proved `Formal.CurrencyAffordFastFail.isPlannable`, whose
`fastfail_sound` theorem proves: when this returns False, NO plan in the goal's
action set raises the leaf's owned count to `needed` — because the only
acquisition is an NpcBuy that is inapplicable while unaffordable, and the goal's
actions cannot earn the currency (no task-completion in GatherMaterials'
relevant_actions). So pruning discards no satisfiable plan and the GOAP search is
spared the budget-exhausting node burn.
"""


def currency_afford_plannable_pure(target_in_closure: bool, affordable: bool,
                                   owned: int, needed: int) -> bool:
    """True ⇒ worth planning; False ⇒ fast-fail. Mirrors
    `Formal.CurrencyAffordFastFail.isPlannable`:
    `!targetInClosure || affordable || needed ≤ owned`."""
    return (not target_in_closure) or affordable or owned >= needed
```

- [ ] **Step 4: Run PASS. Commit:** `feat(goals): currency_afford_plannable_pure fast-fail core (C4)`

---

### Task 3: Lean model + roles (`Formal/CurrencyAffordFastFail.lean`)

Mirror `Formal/SkillGateFastFail.lean` structure (Step inductive, applyStep, runPlan, isPlannable, fastfail_sound).

- [ ] **Step 1: Write the model**
```lean
-- formal/Formal/CurrencyAffordFastFail.lean
-- @concept: core, planner @property: safety, totality
/-
Affordability fast-fail for a currency-buy recipe-closure leaf in
`GatherMaterialsGoal.is_plannable` (src/.../goals/currency_afford_core.py).

A closure leaf (e.g. jasper_crystal) acquired ONLY by NpcBuy for a currency
(tasks_coin) cannot have its owned count raised while UNAFFORDABLE: the buy is
inapplicable (currency_on_hand < price·qty) and GatherMaterials' action set has NO
task-earning action, so the currency cannot rise mid-search. Affordability is
therefore CONSTANT across the plan — the same invariant SkillGateFastFail relies
on for the crafting skill. Pruning loses no satisfiable plan.

Lean core only — no mathlib.
-/
namespace Formal.CurrencyAffordFastFail

inductive Step where
  | buy
  | other
deriving DecidableEq

/-- `buy` raises owned by one ONLY when affordable (NpcBuy applicable); `other`
never touches the leaf. -/
def applyStep (affordable : Bool) (owned : Nat) : Step → Nat
  | .buy => if affordable then owned + 1 else owned
  | .other => owned

def runPlan (affordable : Bool) (owned : Nat) : List Step → Nat
  | [] => owned
  | s :: rest => runPlan affordable (applyStep affordable owned s) rest

def isPlannable (targetInClosure affordable : Bool) (owned needed : Nat) : Bool :=
  !targetInClosure || affordable || decide (needed ≤ owned)

theorem applyStep_unaffordable (owned : Nat) (s : Step) :
    applyStep false owned s = owned := by cases s <;> simp [applyStep]

theorem runPlan_unaffordable (owned : Nat) (plan : List Step) :
    runPlan false owned plan = owned := by
  induction plan generalizing owned with
  | nil => rfl
  | cons s rest ih => rw [runPlan, applyStep_unaffordable, ih]

/-- **SOUNDNESS.** Fast-fail fires (`isPlannable = false`) ⇒ the leaf is in the
closure, UNAFFORDABLE, and `owned < needed`; then NO plan raises owned to needed. -/
theorem fastfail_sound (targetInClosure affordable : Bool) (owned needed : Nat)
    (h : isPlannable targetInClosure affordable owned needed = false) :
    ∀ plan, runPlan affordable owned plan < needed := by
  simp only [isPlannable, Bool.or_eq_false_iff, Bool.not_eq_false',
    decide_eq_false_iff_not, Nat.not_le] at h
  obtain ⟨⟨_, haff⟩, hown⟩ := h
  intro plan
  rw [haff, runPlan_unaffordable]
  exact hown

-- Non-vacuity.
example : isPlannable true false 0 1 = false := by decide
example : isPlannable true true 0 1 = true := by decide
example : isPlannable true false 1 1 = true := by decide
example : isPlannable false false 0 1 = true := by decide
example : runPlan true 0 [Step.buy, Step.buy] = 2 := by decide
example : runPlan false 0 [Step.buy, Step.buy] = 0 := by decide

end Formal.CurrencyAffordFastFail
```
NOTE: the `obtain` pattern after `simp` may need adjustment to the actual decomposed shape (isPlannable is `!targetInClosure || affordable || decide(needed≤owned)`; false forces all three false: targetInClosure=true, affordable=false, ¬(needed≤owned)). Inspect the goal and adapt the `obtain`/destructuring; the proof structure mirrors `SkillGateFastFail.fastfail_sound` — consult that file.

- [ ] **Step 2: Imports + Manifest + Contracts** (after the C3 CurrencyFunding entries): `#check` the 2 dynamics theorems + `fastfail_sound`; pin `runPlan_unaffordable` and `fastfail_sound` exact statements (mirror the SkillGateFastFail pins in Contracts.lean:2818-2828).

- [ ] **Step 3: Build + axiom check + commit** (`feat(formal): CurrencyAffordFastFail model + soundness + pins (C4)`).

---

### Task 4: Oracle handler + differential

- [ ] Add `runCurrencyAfford` to Oracle.lean (args `[targetInClosure(0/1), affordable(0/1), owned, needed]` → `{"plannable": bool}`) + route `"currency_afford"`. Mirror `runGatherPlannable`.
- [ ] `formal/diff/test_currency_afford_diff.py`: Hypothesis property over booleans × small nats, asserting `currency_afford_plannable_pure` == oracle; plus the unaffordable-unowned fast-fail case both sides False.
- [ ] Rebuild oracle, run, commit (`feat(formal): currency_afford oracle handler + differential (C4)`).

---

### Task 5: Wire the affordability fast-fail into GatherMaterials.is_plannable

**Files:** Modify `src/artifactsmmo_cli/ai/goals/gathering.py` (`is_plannable` ~363-383); test in the GatherMaterials test file.

- [ ] **Step 1: Failing test** — `GatherMaterialsGoal(satchel, {satchel:1})`, gd seeded as Task 1, state with `tasks_coin` = 0 (unaffordable for jasper @8): `is_plannable(state, gd, None)` is `False`. With `tasks_coin` ≥ 8 in inventory: `is_plannable` is `True` (not pruned). Keep the existing skill-gate fast-fail behavior intact (feather_coat case still False).

- [ ] **Step 2: Run, verify FAIL.**

- [ ] **Step 3: Implement** — in `is_plannable`, after the existing skill-gate logic, compute the recipe closure (reuse `recipe_closure`/`closure_demand`), find any currency-buy leaf (same predicate as Task 1), and for each compute `affordable = currency_on_hand >= price*qty` where `currency_on_hand = inv+bank` of that leaf's currency and `price,qty` from `npc_purchases`/closure. Call `currency_afford_plannable_pure(target_in_closure=True, affordable, owned=inv+bank of the leaf, needed=closure qty)`. If ANY currency-buy leaf returns False → return False (prune). Otherwise fall through to the existing return. KEEP the existing skill-gate fast-fail (don't replace it; AND the two — plannable only if BOTH gates pass).
  - The currency for a leaf comes from `npc_purchases(leaf)` (the `(npc, price, currency)` tuples). Use the cheapest affordable-if-any; if none affordable, that leaf prunes. Document the choice.

- [ ] **Step 4: Run PASS (new fast-fail + existing skill-gate untouched). Confirm core live:** `grep currency_afford_plannable_pure src/`. Commit (`feat(goals): affordability fast-fail in GatherMaterials.is_plannable (C4)`).

---

### Task 6: Arbiter demand routing — inject ReachCurrencyGoal

**Files:** Modify `src/artifactsmmo_cli/ai/strategy_driver.py` (`objective_step_goal` ~620-648 and/or `_resolve_step_goal` ~863-910); test `tests/test_ai/test_strategy_driver*.py`.

- [ ] **Step 1: GROUND FIRST** — read `objective_step_goal`/`_resolve_step_goal` to see exactly how an ObtainItem step becomes a Goal and how fallbacks are walked. The injection: when the chosen ObtainItem step's recipe closure has a currency-buy leaf that is UNAFFORDABLE now (the same check as Task 5), the arbiter selects `ReachCurrencyGoal(currency, price*qty)` for that leaf as the active step (so the bot funds coins) INSTEAD of the un-plannable GatherMaterials. Funding target = `price * needed_qty` for the leaf.
- [ ] **Step 2: Failing test** — an objective whose chosen step is `ObtainItem(satchel)`, state with 0 tasks_coin: the arbiter's selected goal is `ReachCurrencyGoal('tasks_coin', 8)` (not GatherMaterials(satchel), which is_plannable=False). With tasks_coin≥8: selected goal is GatherMaterials(satchel) (buy+craft plannable).
- [ ] **Step 3: Implement** the routing at the grounded insertion point. Extract the "unaffordable currency-buy leaf + its (currency, price*qty)" detection into a small helper (reuse Task 5's closure/affordability logic — DRY; consider a shared function in a new module both is_plannable and the arbiter call). Keep it minimal; do not disturb other step routing.
- [ ] **Step 4: Run PASS. Commit** (`feat(arbiter): route to ReachCurrencyGoal when objective blocked on unaffordable currency leaf (C4)`).

---

### Task 7: Mutation + end-to-end satchel test + full gate

- [ ] **Step 1: Mutation** — add `CURRENCY_AFFORD_CORE_SRC` + `CURRENCY_AFFORD_MUTATIONS` (drop affordable disjunct; drop owned-fallback; collapse-True) + `run_group(..., "formal/diff/test_currency_afford_diff.py", survivors)` to mutate.py. Bot stopped → `~/.local/bin/uv run python diff/mutate.py --only currency_afford` → 0 survivors. `git diff src` clean.
- [ ] **Step 2: End-to-end satchel test** (`tests/test_ai/`): with a satchel objective + a full GameData (recipe + cow/chicken droppers winnable + tasks_trader jasper vendor):
  - tasks_coin = 0 → arbiter selects ReachCurrencyGoal; GatherMaterials(satchel).is_plannable is False (NO 641K-node burn — assert is_plannable False, the regression guard for the original bug).
  - tasks_coin ≥ 8 → GatherMaterials(satchel) plannable; relevant_actions includes NpcBuy(jasper_crystal); a plan exists (buy jasper + craft satchel). Assert a non-empty plan / plan_len > 0.
- [ ] **Step 3: FULL GATE** — bot stopped: `cd formal && export PATH="$HOME/.elan/bin:$PATH" && ./gate.sh` (or the documented full gate). MUST be green (build + no-sorry + axiom-lint + manifest + contracts + differential + mutation). Fix any reds.
- [ ] **Step 4: Commit** (`test(formal): currency_afford mutation + end-to-end satchel plan (C4)`).

---

## Self-Review
- Deep-leaf buy emitted: Task 1. ✓
- Affordability fast-fail proved + LIVE in is_plannable: Tasks 2,3,5 (grep core live). ✓
- Soundness invariant (no task actions in GatherMaterials set) documented + relied on: Global Constraints + Task 3 model. ✓
- Demand routing to ReachCurrencyGoal: Task 6. ✓
- End-to-end satchel + node-burn regression guard: Task 7. ✓
- Full gate green before merge / deploy-gate lift: Task 7. ✓
- RISK: Task 3 `obtain` destructuring after simp may need adjustment (mirror SkillGateFastFail.fastfail_sound). Task 6 arbiter routing is the fuzziest — GROUND `objective_step_goal`/`_resolve_step_goal` before implementing; keep DRY with Task 5's affordability helper.

## After C4
- Deploy gate LIFTS: merge the branch, restart the bot (verify the satchel goal funds coins then crafts, and the memory peg is gone).
- Deferred Minors (C1–C3 final reviews): game_data import order, strategy private import, tighten zero-reward test, copper_ring ~52K-node churn (separate). Fold into a cleanup pass or follow-up.
