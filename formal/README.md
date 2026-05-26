# Formal verification of core algorithms (TLA+ / PlusPy)

Executable TLA+ reference models that demonstrate the correctness of four pure
functions in the AI player. Each spec defines the answer twice — once as the
algorithm, once as an independent oracle (hand-computed values or an operational
simulation) — and PlusPy asserts they agree across an exhaustively enumerated,
**bounded** input domain.

## Scope and honesty

- **Not a proof for all inputs.** PlusPy is a TLA+ *interpreter*, not a theorem
  prover (TLAPS) or a model checker (TLC). Correctness is demonstrated only over
  the bounded domains encoded in each spec (small grids / stat ranges / recipe
  graphs). It is exhaustive over *that* domain, not unbounded.
- **No `.cfg`/`INVARIANT`.** Each spec enumerates its input set in `Next` and
  asserts the property per input via `TLC!Assert`. `pluspy -cN <Module>` drives
  all N inputs; an assertion failure halts PlusPy.
- **PlusPy subset.** PlusPy has no `RECURSIVE` operator keyword; recursion is
  expressed as recursive functions (`f[k \in S] == ...`), and declared function
  domains must cover every enumerated input (PlusPy will not catch an
  under-declared bound — TLC would).

## Setup and run

```bash
./formal/setup.sh            # clone pinned PlusPy into formal/vendor/ (gitignored)
uv run python formal/run.py  # run every spec; PASS/FAIL table, non-zero on any fail
```
(Use `python3 formal/run.py` in environments where `uv` cannot sync the project,
e.g. a git worktree. The runner is pure stdlib.)

## Property -> code map

| Spec | Pins (Python) | Demonstrated property |
|---|---|---|
| `CalculatePath.tla` | `utils/pathfinding.py:44-93` | Output is a legal king-walk, length = Chebyshev optimum (no shorter path), `total_distance` = Manhattan cost; never worse than 4-connected, strictly better off-axis. |
| `RecipeClosure.tla` | `ai/recipe_closure.py:15-54` | `craftable_mats`/`needed_resources` = least-fixpoint closure (sound + complete), both pinned to a hand-computed `ExpectedClosure`; `raw_material_units` matches a hand table; cyclic recipes terminate (ring=2, loop=2, a=1, b=1). |
| `PrerequisiteGraph.tla` | `ai/tiers/prerequisite_graph.py:20-65` | `prerequisites` emits exactly the data-derived direct edges; expansion terminates at leaves; `combat_capable <=> exists monster. predict_win`. |
| `PredictWin.tla` | `ai/combat.py:57-79` | Closed-form `ceil(hp/hit)` verdict (incl. the `<=`/`<` initiative tiebreak) = outcome of an independent turn-by-turn fight simulation; monotone in player hit / monster HP; MAX_TURNS cap is a sound loss (exercised by high-HP and zero-damage cap cases that drive both the closed-form and the sim's own truncation path). |
| `TaskBatch.tla` | `ai/task_batch.py:19` | `task_batch_size` clamps to `max(1, min(remaining, fit, BATCH_CAP))`: always >=1, never exceeds the task remainder or the depth cap, and a >=1 batch always fits the available inventory space (`K*mats <= free+held-MIN_FREE`). |
| `InventoryCaps.tla` | `ai/inventory_caps.py:30,82` | `useful_quantity_cap` = max(recipe_demand*buffer floored at safety, task_remaining, action_cap, equip_keep) with equipped => >=1; `overstocked_items` = `{code: qty-cap : qty>cap}` exactly. |
| `BankSelection.tla` | `ai/bank_selection.py:68` | `select_bank_deposits` deposits exactly the non-kept positive-qty inventory; the keep-set is closed under the recipe-material walk of {crafting_target, items-task item} plus task-coin/HP/best-weapon, so deposits never intersect the keep-set (the PursueTask-freeze invariant); sort key is the total order (-sell_value, code). |
| `EquipmentScoring.tla` | `ai/equipment/scoring.py:9,23,55` | `pick_loadout` picks, per slot independently, a score-optimal feasible owned item and never downgrades (swap only on strict score improvement; ties keep the current item; below-level items excluded). Scores use an integer surrogate order-equivalent to `weapon_score`/`armor_score`. |
| `LoadoutProjection.tla` | `ai/equipment/projection.py:30` | `project_loadout_stats` = current totals + Σ over changed slots of (new − old) per stat; equals the unconditional all-slot new−old sum (the changed-slot guard is sound), and the identity loadout reproduces current stats exactly. |

## Modeling notes

- `PredictWin.tla` works in per-turn integer damage; the element/crit expansion
  (`_element_damage`, `_expected_hit`, `_round_half_up`) is pure arithmetic
  verified by inspection, not re-derived in TLA+.
- `PrerequisiteGraph.tla` abstracts the skill-level prerequisites and uses an
  abstracted `Beatable` verdict for the combat-gate equivalence; the operational
  `predict_win` refinement lives in `PredictWin.tla`.
- `RecipeClosure.tla` defines the algorithm-DFS closure and the fixpoint closure
  with separate operators (intentionally) and pins both to `ExpectedClosure`.
- The inventory/economy specs (`TaskBatch`, `InventoryCaps`, `BankSelection`)
  abstract item attributes (recipe demand, sell value, equippability, HP-restore)
  as small in-spec tables and reuse the recipe-material closure already proven in
  `RecipeClosure.tla`. `TaskBatch` abstracts `raw_material_units`/`recipe_closure`
  (proven separately) as the enumerated `mats_per_unit`/`held_recipe` inputs and
  verifies only the clamp it adds.
- The combat/equipment specs (`EquipmentScoring`, `LoadoutProjection`) keep all
  arithmetic integer. `EquipmentScoring` replaces the float `weapon_score`/`armor_score`
  (`atk*(1-res/100)`) with the order-preserving integer surrogate `atk*max(0,100-res)`
  — `pick_loadout` only compares scores, so the surrogate proves the exact ordering it
  relies on. `LoadoutProjection` models the integer stat fields (attack/resistance
  elements, max_hp, initiative); the remaining scalar fields (dmg, dmg_elements,
  critical_strike) follow the identical additive pattern.
- `LoadoutProjection` models the pre-`_drop_zeros` accumulator values (plain integers
  per stat), not `project_loadout_stats`' final dict-shape transform that strips
  zero-valued entries; `_drop_zeros` is a trivial output filter verified by inspection.

## Move-API connectivity finding

**The server moves a character directly to an arbitrary target tile in a single
`action/move` action; `calculate_path` is therefore a client-side cost/preview
estimate, not a required step decomposition.** The relevant distinction the spec
verifies is Chebyshev (king-walk) vs Manhattan *cost*, not connectivity.

Evidence:

- The endpoint takes a single `DestinationSchema(x, y)` (or a `map_id`) and the
  server routes to it: openapi.json `/my/{name}/action/move` description —
  *"Moves a character on the map using either the map's ID or X and Y position.
  Provide either 'map_id' or both 'x' and 'y' coordinates."* (openapi.json:468).
  The server, not the client, owns routing: failure code **595 "No path
  available to the destination map"** and **596 "The map is blocked"** are
  server-side path/accessibility verdicts (openapi.json move responses), which
  only make sense if the server resolves the route from current position to the
  arbitrary target. There is no per-tile step parameter in the schema.
- The plain `move` command sends one request to the final coordinate and is
  done — no loop (`commands/action.py:198-199`:
  `destination = DestinationSchema(x=x, y=y); response = api.action_move(...)`).
- `calculate_path` does **not** call the API at all; it is pure arithmetic over
  start/end coordinates producing a `PathResult` of king-steps plus a Manhattan
  `total_distance` and a 5s/step time estimate (`utils/pathfinding.py:44-93`).
- The only place that walks the steps, the interactive `navigate` command,
  *chooses* to issue one `action_move` per `PathStep`
  (`commands/action.py:515-622`) for a progress-bar UX with per-move cooldown
  waits — but each step is an adjacent **diagonal/king** move (both axes change
  by 1 per step, `pathfinding.py:69-81`), confirming diagonal moves are
  reachable. Because the server accepts the arbitrary final target directly, the
  per-step decomposition is a UX/cost-preview choice, not an API constraint; a
  single move to `(end_x, end_y)` is equally valid.

Consequence for the spec: `calculate_path`'s contract is correctly modeled as a
**cost/preview** aid. The load-bearing guarantees are that the step count equals
the Chebyshev optimum (the number of king-moves the `navigate` UX will animate)
and that `total_distance` is the Manhattan figure — exactly the king-walk vs
4-connected distinction `CalculatePath.tla` pins. Chebyshev-optimal step
decomposition is a *sound, minimal* king-walk to the target, but it is not an
API requirement: the move endpoint would also accept the target in one shot.
