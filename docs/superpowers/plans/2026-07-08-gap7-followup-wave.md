# GAP-7 + Follow-up Fix Wave

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining pinned gap (GAP-7) and the concrete follow-up items from the slot-gap wave: recipe-closure drop blindness, duplicate-slot best-fill, gold-reserve discipline on vendor buys, joint gold-affordability, and the drop-vs-craft route-preference pin. EXCLUDED by design (need the user's call, documented in wrap): equip_value utility-stat weighting (deliberate per the utility-gear-value decision) and one-fight drop optimism (deliberate abstraction, same family as FightAction xp+=10).

**Tech Stack:** Python 3.13 (`uv`), pytest. Anchored files throughout — static anchor sweep after every task. Bot may be LIVE: no gate.sh/mutate.py; full gate owed at next downtime.

## Global Constraints

- Tripwire discipline: pinned tests flip to positive with derivation comments; every ripple re-derived honestly; scenario net (`tests/test_ai/scenarios/`) is the acceptance harness.
- Repo rules: API-data only, no defaulting; never catch Exception; no inline imports; exact arithmetic; 100% coverage; mypy strict; TDD.
- Watch import cycles (tiers package init — the means.py lesson): if a needed import cycles, thread values through existing context objects instead.

---

### Task 1: GAP-7 — recipe_closure reads the full drop set

**Files:** `src/artifactsmmo_cli/ai/recipe_closure.py` (~:146-156 `needed_resources` from primary `resource_drops`); tripwire in test_slot_coverage.py (l35 `GatherMaterials(small_pearls)` 1-node pin) flips; unit tests beside existing recipe_closure tests.

Mirror GAP-2 exactly at the goal layer: the closure's gatherability check switches to `game_data.gatherable_drop_items()` (superset — verify same accessor). Expected flip: l35's `GatherMaterials(small_pearls)` PLANS (gather at a fishing spot needs the fishing skill + tool — the scenario may need fishing skill to make the plan executable; derive the actual plan honestly: if skill-gated, the honest outcome may be a skill-prereq step, not a 1-action gather — pin what the mapper produces). WATCH the argmax story: perfect_pearl's step becomes servable → l35's demotion to old_boots may UNWIND (pearl chosen outright) — re-derive the GAP-6 test so BOTH acquisitions stay covered (pearl route as primary, boots route via a pearl-stocked variant if needed — do not lose GAP-6's coverage).

- [ ] Flip pin (red) → implement → net green → sweep → commit `fix(closure): full gather-drop set feeds recipe_closure`

### Task 2: Duplicate-slot best-fill

**Files:** `src/artifactsmmo_cli/ai/tiers/objective.py` `_slot_assignments` (~:32): index-1 duplicate slot currently gets the 2nd-ranked DISTINCT item even when duplicating the best is strictly higher value (dup-allowed types: ring, artifact — actions/equip.py:32). Fix: for dup-allowed slot types, slot N gets the best item not yet CONSUMED-past-ownership — duplicate the top item when a second copy is permitted AND (ownership/attainability supports it — check how ownership caps duplicates today: the dual-ring carve-out memory says "capped at ownership"; near-term TARGETS are aspirational, so verify what the perfect-sheet vs now-sheet semantics should be — mirror whatever `near_term_gear` does for rings today: grep the dual-ring handling and make artifacts consistent with rings' proven behavior rather than inventing new semantics).

- [ ] Failing unit test (artifact2 gets pearl-duplicate when rings-precedent says so) → implement → ripple re-derive (EVENT_ONLY_CANDIDATES may shift again) → sweep → commit `fix(objective): duplicate-allowed slots fill with the best duplicate (rings-precedent)`

### Task 3: Gold-reserve discipline on vendor buys

**Files:** `src/artifactsmmo_cli/ai/goals/currency_demand.py` (gold arm from GAP-3): affordable becomes `pocket + bank_gold − reserve ≥ price` where reserve = the same progression-reserve floor the BANK_EXPAND gate uses (`progression_reserve.reserve_floor` — check import layering from goals/; if cyclic, compute at the caller that has ctx and thread it in like SelectionContext.gold_reserve). Unaffordable-because-of-reserve = honest defer (same as plain unaffordable). Unit tests: buy allowed at reserve boundary, blocked just below, None-bank unchanged. NOTE the WithdrawGold deficit sizing must NOT drain the reserve either (withdraw up to bank_gold − what keeps pocket+bank ≥ reserve... derive the exact invariant: post-buy total gold ≥ reserve).

- [ ] Failing tests → implement → l30 pin re-derive (25000 gold vs reserve at L30 — verify the buy still plans; if reserve blocks it, the scenario gains gold honestly) → sweep → commit `fix(currency): vendor gold buys respect the progression reserve floor`

### Task 4: Joint gold affordability + route-preference pin

**Files:** currency_demand.py (joint check: multiple unowned gold leaves must be affordable TOGETHER, not each-alone — the deficit sum already exists; align the affordability verdict with it); new test in test_slot_coverage.py or unit file pinning drop-vs-craft route preference: a craftable target with banked mats AND a winnable dropper — pin which route the planner picks (cost-model verdict; derive, comment, no judgment — this is the pin GAP-6's review asked for).

- [ ] Failing tests → implement joint check → pin route preference (derive actual) → sweep → commit `fix(currency): joint gold affordability; test: drop-vs-craft route pinned`

### Task 5: Wrap

- [ ] Full scenario net + suite; spec addendum ("GAP-7 + follow-up wave SHIPPED", excluded-by-design items named with rationale + the open design questions for the user: equip_value combat-vs-utility weighting, drop-rate cost modeling); ledger; memory; note gate owed.
