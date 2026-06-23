# Next-Craft-Action Generator (copper_ring churn fix) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:subagent-driven-development. Checkbox (`- [ ]`) steps.

**Goal:** Kill the recurring craft-chain re-search (copper_ring ~52K nodes/cycle, 114×) by computing the NEXT action of a recipe-craft goal directly from the recipe closure in O(closure) instead of GOAP A*. Falls back to A* for goals the generator can't determine.

**Architecture:** The bot executes only `plan[0]` each cycle (player.py:522). So a craft goal needs only its NEXT action, which is DETERMINISTIC from the recipe DAG + current inventory: the deepest unmet item that is producible now (a raw to Gather, or a craftable whose inputs are on hand to Craft). A proved pure core decides that next item; `try_plan` returns `[next_action]` for craft-target GatherMaterials goals, bypassing A*; non-recipe / search-needed goals fall back to `self._planner.plan`.

**Tech Stack:** Python 3.13 (`uv`), Lean 4 (core), Hypothesis differential, `mutate.py`, pytest. uv at `~/.local/bin/uv`; lake at `~/.elan/bin/lake`.

## Why next-action, not full-plan
- The loop uses `plan[0]` only; a full 200-action plan is discarded after one step.
- Generation is O(closure) (~recipe size), no per-node SQLite — vs 52K A* nodes/cycle.
- No stale-cache / invalidation problem: recomputed cheaply each cycle from live state.
- Same number of executions as A* (still ~180 gathers for copper_ring×3), but each cycle's PLANNING is O(closure) not 52K nodes — that is the churn.

## Global Constraints
- `~/.local/bin/uv run`; `lake` at `~/.elan/bin/lake` (`export PATH="$HOME/.elan/bin:$PATH"`). Incremental Lean builds; don't clean `.lake`.
- Imports at top; no inline; absolute. NEVER catch Exception. API data or fail. ONE behavioral class/file. Tests in `tests/`; 100% coverage on touched modules.
- Builds on current main (C1–C4 + Minors). `closure_demand` (recipe_closure.py) gives cumulative demand. `GatherMaterialsGoal` is the craft-chain goal; its planning runs via `try_plan` → `self._planner.plan` (strategy_driver.py:783, GOAPPlanner.plan).
- Run `mutate.py`/`gate.sh` only with the bot stopped; `git diff src` clean after; COMMIT before mutation (the runner aborts on a dirty target).
- Deploy: this is a planner-efficiency change. Validate against a live trace (copper_ring search nodes → ~0, ring-making behavior unchanged) before relying on it.

## The decision (pure core)
`next_craft_target_pure(recipes, owned, target, qty) -> NextAction | None`:
- `NextAction = (item: str, kind: "gather" | "craft", count: int)` (count = how many still needed of `item`).
- None ⇒ `owned[target] >= qty` (goal satisfied; nothing to do — caller treats as satisfied, not a craft step).
- Else: DFS from `target`. For the current short item:
  - if it has a recipe AND every input is available in sufficient quantity (owned/produced) → return `(item, "craft", deficit)`.
  - if it has a recipe but an input is short → recurse into the FIRST short input (produce inputs first).
  - if it has NO recipe (raw) → return `(item, "gather", deficit)`.
- "available quantity" accounts for owned inventory+bank net of what higher levels already consume (use closure_demand's net demand per item; an item is "short" when owned < closure demand).

**Theorem roles (Lean `Formal/NextCraftAction.lean`):**
- `ordering`: a returned `craft` item has all recipe inputs available (never craft before inputs) — `kind = craft ⇒ ∀ input, demand(input) ≤ owned/produced`.
- `progress`: producing the returned item strictly decreases a well-founded measure (e.g. total remaining raw-units across the closure), so repeated application reaches the target — termination.
- `validity`: `None ⇒ owned target ≥ qty` (only stops when satisfied); non-None ⇒ the item is genuinely short.
- differential (Python ≡ Lean) + mutation; ≥100% unit coverage.

This mirrors the C3 measure-descent pattern. Keep it core-only or Liveness-namespaced (progress is a termination property — Liveness, mathlib allowed).

---

### Task 1: `next_craft_target_pure` pure core + unit tests
**Files:** Create `src/artifactsmmo_cli/ai/next_craft_core.py` (NextAction NamedTuple + the function); `tests/test_ai/test_next_craft_core.py`.
- Inputs: `recipes: Mapping[str, dict[str,int]]` (item→inputs; absent ⇒ raw), `owned: Mapping[str,int]`, `target: str`, `qty: int`. (Pass `closure`/demand precomputed OR compute net inside — decide at build; keep the proved decision pure and total.)
- TDD: copper_ring chain (0 owned → ("copper_ore","gather",...)); with 180 ore → ("copper_bar","craft",...); with bars → ("copper_ring","craft",...); satisfied (owned≥qty) → None; partial owned reduces counts.
- Cycle-safety (recipe cycles can't exist in data, but the function must be total — bound recursion by closure size).

### Task 2: Lean model `Formal/NextCraftAction.lean` + Manifest/Contracts
- `def nextCraftTarget` mirroring the Python; theorems `ordering`, `progress` (measure descent), `validity`. Pins + manifest `#check`. Build green, axiom-clean.

### Task 3: Oracle handler + differential
- `runNextCraft` in Oracle.lean over a JSON recipe-DAG + owned encoding; `formal/diff/test_next_craft_diff.py` property test (random small DAGs) asserting Python core ≡ Lean. (Encoding a DAG as flat JSON is the nontrivial bit — define a compact schema, e.g. parallel arrays.)

### Task 4: Wire into `try_plan` (the integration + A* fallback)
**Files:** `strategy_driver.py` (the `try_plan`/`_PlanRunner.plan` path ~783), tests.
- For a `GatherMaterialsGoal` whose `target_item` is craft-assembled and whose closure leaves are all generator-handleable (raw-gather or craftable; NO monster-drop / multi-source-choice leaf — those fall back to A*), build the next action from `next_craft_target_pure`:
  - map `(item,"gather")` → the `GatherAction`/source for that item from `relevant_actions` (reuse the existing source selection — gather vs the proved monster-drop/buy decisions); `(item,"craft")` → the `CraftAction`.
  - return `[next_action]`.
- If the closure contains a leaf the generator can't source deterministically (winnable-monster-drop target choice, currency-buy needing affordability already handled by is_plannable, multi-source cost tradeoff) → return None and let the caller fall back to `self._planner.plan` (A*).
- Keep is_plannable's fast-fails (skill gate, affordability) as the pre-gate; the generator runs only for plannable craft goals.
- Tests: a copper_ring-style goal returns a single-action plan via the generator (assert no A* invoked — e.g. spy/observe node count ~0); a goal with a monster-drop leaf falls back to A*.

### Task 5: Mutation coverage
- `NEXT_CRAFT_CORE_SRC` + mutations (drop the inputs-available guard → craft-before-inputs; drop the deficit short-circuit; invert ordering) + run_group; 0 survivors. Commit before running.

### Task 6: Live-trace validation + full gate
- Bot stopped: run `artifactsmmo plan <char>` in a state where a craft chain (copper_ring or gear) is the chosen step; confirm `goals_tried` nodes for that goal → ~0 (generation) vs ~52K (A*), and the next action is correct (Gather/Craft toward the target).
- Run the FULL gate (`formal/gate.sh`) GREEN. Commit (tree clean before mutation).

## Risks (resolve at build)
1. **Source policy parity:** A* implicitly picked sources/paths. The generator's `(item,"gather")`→action mapping must reuse the EXISTING source decisions (relevant_actions / acquisition_method / proved monster-drop selection), not invent a new policy — otherwise behavior drifts from today. Where a real cost tradeoff exists, fall back to A*.
2. **Fallback boundary:** be conservative — only generate for the clearly-deterministic gather-craft case; fall back to A* otherwise. Measure fallback frequency on live traces.
3. **GatherAction batching:** if a GatherAction yields >1 per execution, the count/measure must reflect per-action yield (reuse the proved gather-yield model) so progress is honest.
4. **Interaction with DoomedMemo / two-pass budget:** a generator-served goal should not be memoized as doomed; ensure the cheap/full path treats a generated plan as a normal success.

## Out of scope
- Full-plan generation / pattern (macro) caching (design doc Option C) — only if generation is later shown hot.
- Plan-following for non-recipe goals (design Option B) — only if a measured non-recipe re-search cost remains.
