# Formal Verification of AI Pure-Logic Components (TLA+ / PlusPy)

**Date:** 2026-05-25
**Status:** Approved roadmap; Phase 1 ready for planning.

## Goal

Extend the existing `formal/` TLA+ / PlusPy harness to demonstrate the
correctness of the **pure, deterministic** logic components of the AI player.
Each component is modeled as a TLA+ state machine that enumerates a bounded
input domain and asserts its correctness property per input via `TLC!Assert`
against an **independent oracle** (hand-computed table, fixpoint, argmax
recomputation, or operational simulation).

This is the same technique and harness used for the four already-verified
functions (`calculate_path`, `recipe_closure`/`raw_material_units`,
`prerequisites`/`combat_capable`, `predict_win`). Correctness is demonstrated
**over a bounded input domain** that PlusPy interprets concretely — these are
executable reference-model checks, not unbounded TLAPS proofs. The README states
this scope plainly.

## What is NOT modelable (explicitly out of scope)

Most of `ai/` cannot be expressed in PlusPy because it is I/O-bound,
learning-coupled, or pure orchestration. These have no pure contract to check
and are deliberately excluded:

- **Orchestration / search:** `player.py`, `strategy_driver.py`, `planner.py`
  (the GOAP search loop).
- **API-fed data:** `game_data.py`, `world_state.py` (snapshots of live API
  data), all `actions/*.execute` (each issues an API call), all `goals/*`
  (planner glue + history reads).
- **Persistence / learning:** `learning/store.py`, `learning/projections.py`,
  `learning/scalarizer.py`, `learning/dynamic_priority.py` (SQLite / SQLModel).
- **Clock / history-coupled:** `task_decision.py`, `event_availability.py`,
  `tiers/guards._fires`, `tiers/means._fires`, `tiers/strategy.decide`
  (these read `LearningStore` / `datetime`; only their pure sub-parts qualify).
- **Trivial wrappers:** DTOs, enums, exception classes, formatters, validators.

The learning-coupled modules have *pure decision-ordering cores* (e.g.
`GUARD_ORDER` first-match, `strategy.actionable_step`) that COULD be modeled with
history abstracted as an input. Those are out of scope for the chosen
"all pure components" cut but are noted as a possible future extension.

## Mechanics (reuse the existing `formal/` harness)

- One `.tla` per component under `formal/specs/`.
- The module `EXTENDS` the needed stdlib modules and bakes a bounded input
  domain into a CONSTANT-free definition; `Next` walks a cursor over that domain
  and asserts the property per input with `TLC!Assert(cond, msg)`.
- PlusPy has **no `RECURSIVE` operator keyword** — recursion is expressed as
  recursive *functions* `f[k \in S] == ...` (bounded), per the established
  pattern.
- Run: `python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs:formal/vendor/PlusPy/modules/lib <Module>`;
  clean run prints `MAIN DONE` exit 0, a failed assert prints
  `Evaluating Assert ... failed`.
- Each spec is registered in `formal/run.py` `MODULES` with its domain size and
  mapped to its Python line(s) in `formal/README.md`.
- Each spec ships a **non-vacuous "break-it" check**: a deliberate mutation that
  must make PlusPy halt, proving the assertion bites.

## Roadmap (4 phases, each its own spec → plan → build cycle)

| Phase | Components | Rationale |
|---|---|---|
| **1 — Inventory/economy** (this cycle) | `bank_selection` (keep-set + deposits), `inventory_caps` (cap + overstock), `task_batch` (size) | Highest bug-cost — the documented PursueTask-freeze class; interrelated keep/cap/batch logic |
| 2 — Combat/equipment | `equipment/scoring.pick_loadout` (+ `weapon_score`/`armor_score`), `equipment/projection.project_loadout_stats` | Feed `predict_win`'s best-on-hand-loadout verdict |
| 3 — Strategy/feasibility | `tiers/objective.gap` + `is_attainable`, `task_feasibility.task_requirement`, `tiers/strategy` pure core (`actionable_step`, `unmet_closure_size`, `root_cost`, `is_reachable`) | Strategic descent target + pivot/feasibility decisions |
| 4 — Learning/recovery | `learning/skill_xp_curve.SkillXpCurve`, `recovery.StuckDetector` | Pure curve math + pure stuck-detection state machine |

Trivial pure helpers (`equip_value`, `personality.weighted_remaining`,
`meta_goal.owned_count`, `player_helpers.delete_cost`/`format_plan`) are covered
incidentally where they compose into the above, or added as cheap bonus asserts;
they are not standalone work items.

---

## Phase 1 — detailed properties (verified against independent oracles)

All three reuse the already-modeled `recipe_closure` / `raw_material_units`
logic, so the recipe data in these specs mirrors that of `RecipeClosure.tla`
(a diamond + a cyclic recipe) to keep the closure walk exercised.

### `bank_selection.select_bank_deposits` (`ai/bank_selection.py:68`)

Models `_keep_codes` + `_recipe_materials` + `_best_fighting_weapon` + the
deposit filter/sort.

- **Keep-set** = `{TASKS_COIN_CODE}` ∪ `{task_code}` (if set) ∪ `{HP-restore
  items in inventory}` ∪ `{best fighting weapon}` ∪ `recipe_materials({crafting_target}
  ∪ {task_code if task_type="items"})`, where `_recipe_materials` is the
  visited-guarded recipe-tree walk and `_best_fighting_weapon` is the
  max-attack non-tool weapon over inventory+equipped (ties: code asc).
- **Theorems** (∀ states in a bounded family, incl. one where a recipe material
  *is* the items-task item):
  - `deposits ∩ keep-set = ∅` — the bot never banks a protected item
    (the **PursueTask-freeze invariant**).
  - `deposits = { (code,qty) : code ∈ inventory, qty>0, code ∉ keep-set }` as a
    set — completeness + soundness of the filter.
  - `deposits` is sorted by `(−sell_value, code)` — a non-decreasing key
    sequence.
- **Oracle:** hand-specified keep-closure and expected deposit list per sample
  state; the keep-set is also checked equal to an independent fixpoint of the
  recipe-material relation (closed: no protected material's sub-material leaks).

### `inventory_caps.useful_quantity_cap` / `overstocked_items` (`ai/inventory_caps.py:30,82`)

- **`useful_quantity_cap(code)`** = `max(recipe_cap, task_cap, action_cap,
  equippable_cap)`, with `recipe_cap = max_recipe_demand·buffer` floored to
  `safety_floor` when `max_recipe_demand>0` (else 0), `task_cap = remaining`
  when `code` is the active items-task item (else 0), `action_cap =
  ACTION_CONSUMABLES_CAP.get(code,0)`, `equippable_cap = 1` when the item is
  equippable; and the result is floored to ≥1 when `code` is currently equipped.
- **Theorems** (∀ enumerated inventory/recipe/task/equip combos):
  - cap equals the independent max-of-four (+equipped floor) — exact.
  - `equipped(code) ⇒ cap ≥ 1`.
  - `overstocked_items = { code: qty−cap : code ∈ inventory, qty>0, qty>cap }` —
    exact, and every reported excess is `> 0`.
- **Oracle:** hand table of expected caps per `(item, state)`; `overstocked`
  recomputed independently from the cap.

### `task_batch.task_batch_size` (`ai/task_batch.py:19`)

- **Result** = `1` when not an items-task / no task_code / `task_total ≤ 0` /
  `remaining ≤ 0`; otherwise `max(1, min(remaining, fit, BATCH_CAP))` where
  `fit = ((inventory_free + held_recipe) − _MIN_FREE_SLOTS) // mats_per_unit`,
  `mats_per_unit = raw_material_units(task_code)`, and `held_recipe` sums held
  quantities of the resource-drop items of the task item's closure.
- **Theorems** (∀ enumerated task/inventory states):
  - `1 ≤ K` always (the floor).
  - When the task branch is taken and `fit ≥ 1`: `K ≤ remaining`,
    `K ≤ BATCH_CAP`, and `K·mats_per_unit ≤ (inventory_free + held_recipe) −
    _MIN_FREE_SLOTS` (the batch fits the available space).
  - `K` equals an independent recomputation of the clamp.
- **Oracle:** independent clamp recomputation + the bound invariants; reuses the
  `RecipeClosure.tla` recipe so `raw_material_units` is the shared, already-proven
  quantity.

## Phase 1 file structure

```
formal/specs/BankSelection.tla
formal/specs/InventoryCaps.tla
formal/specs/TaskBatch.tla
formal/run.py        # +3 MODULES entries with domain sizes
formal/README.md     # +3 property->code rows
```

## Out of scope for Phase 1

Phases 2–4 (combat/equipment, strategy/feasibility, learning/recovery) — each
gets its own spec → plan → build cycle after Phase 1 lands.
