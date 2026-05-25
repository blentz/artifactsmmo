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

## Modeling notes

- `PredictWin.tla` works in per-turn integer damage; the element/crit expansion
  (`_element_damage`, `_expected_hit`, `_round_half_up`) is pure arithmetic
  verified by inspection, not re-derived in TLA+.
- `PrerequisiteGraph.tla` abstracts the skill-level prerequisites and uses an
  abstracted `Beatable` verdict for the combat-gate equivalence; the operational
  `predict_win` refinement lives in `PredictWin.tla`.
- `RecipeClosure.tla` defines the algorithm-DFS closure and the fixpoint closure
  with separate operators (intentionally) and pins both to `ExpectedClosure`.

## Move-API connectivity finding

**The server moves a character directly to an arbitrary target tile in a single
`action/move` action; `calculate_path` is therefore a client-side cost/preview
estimate, not a required step decomposition.** The relevant distinction the spec
verifies is Chebyshev (king-walk) vs Manhattan *cost*, not connectivity.

Evidence:

- The endpoint takes a single `DestinationSchema(x, y)` (or a `map_id`) and the
  server routes to it: openapi.json `/my/{name}/action/move` description —
  *"Moves a character on the map using either the map's ID or X and Y position.
  Provide either 'map_id' or both 'x' and 'y' coordinates."* (openapi.json:467).
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
