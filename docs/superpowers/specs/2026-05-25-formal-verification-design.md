# Formal Verification of Core Algorithms (TLA+ / PlusPy)

**Date:** 2026-05-25
**Status:** Approved design — pending implementation plan

## Goal

Demonstrate the correctness of four pure-logic functions in the AI player by
modeling each as a TLA+ state machine, pairing it with an **independent
declarative specification** of what a correct answer is, and using PlusPy to
check that the two agree (refinement / equivalence) across a finite, enumerable
input domain.

**PlusPy execution model (important).** PlusPy is a TLA+ *interpreter*, not a
model checker (TLC). It does not read a `.cfg`, does not take an `INVARIANT`
declaration, and does not explore the state space exhaustively — it executes a
single behavior, applying the `Next` action `-c N` times. To obtain exhaustive
coverage over the bounded input domain, **each spec's state machine enumerates
the input set itself**: `Next` advances a cursor over the finite domain,
computes both the algorithm result and the declarative result for that input,
and asserts they agree via `TLC!Assert(cond, msg)` (the module `EXTENDS TLC`).
Running `./pluspy -c<domain-size> <Module>` then drives the machine through
every input; any `Assert` failure halts PlusPy with a message the runner
detects. This is genuinely exhaustive over the modeled domain.

These are **executable reference models + machine-checked invariant runs**, not
TLAPS theorem-prover proofs. Correctness is demonstrated *over a bounded input
domain* that PlusPy interprets concretely. The README states this scope plainly
so the artifacts are not mistaken for unbounded soundness proofs.

The core technique: define the answer **twice, independently** — once
constructively (the algorithm's steps) and once declaratively (least fixpoint /
quantified optimum / running simulation). A bug surfaces as the two definitions
disagreeing on some input. A single self-consistent invariant cannot catch a
wrong-but-internally-consistent algorithm; a refinement check can.

## Functions under verification

| Module | Python source | Core claim |
|---|---|---|
| `CalculatePath` | `utils/pathfinding.py:calculate_path` | Output path is legal AND length-optimal; reported cost = true game cost |
| `RecipeClosure` | `ai/recipe_closure.py:recipe_closure`, `raw_material_units` | Closure = least fixpoint of recipe/drop relation (sound + complete); quantity math exact |
| `PrerequisiteGraph` | `ai/tiers/prerequisite_graph.py:prerequisites`, `combat_capable` | Emitted edges = exact direct predecessors; expansion terminates; combat gate ⇔ runtime verdict |
| `PredictWin` | `ai/combat.py:predict_win` | Closed-form verdict = outcome of actually running the fight sim; monotone; MAX_TURNS cap sound |

## Directory layout

```
formal/
  README.md            # property -> Python-line map, scope statement, run instructions
  setup.sh             # git clone tlaplus/PlusPy -> formal/vendor/ (gitignored)
  run.py               # runner: invokes pluspy per module, asserts pass, prints table
  .gitignore           # vendor/
  vendor/              # gitignored PlusPy clone (created by setup.sh)
  specs/
    CalculatePath.tla
    RecipeClosure.tla
    PrerequisiteGraph.tla
    PredictWin.tla
```

No `.cfg` files — PlusPy does not use them. Each `.tla` `EXTENDS TLC`, bakes its
bounded input domain into a CONSTANT-free definition (or defaulted CONSTANT),
enumerates that domain in `Next`, and asserts the correctness property per input
with `TLC!Assert`.

## Correctness theorems per module

### CalculatePath — optimality, not just validity

Source algorithm: a `while` loop stepping one king-move per iteration toward
`dest`, moving diagonally when both axes differ.

- **Declarative spec.** `ValidPath(p)`: `p` starts adjacent to `start`, ends at
  `dest`, and every consecutive pair is king-move-adjacent (Δ ∈ {-1,0,1} on each
  axis, not both zero). `OptimalLen == Max(|dx|, |dy|)` — the Chebyshev lower
  bound; provably no king-walk from `start` to `dest` is shorter.
- **Theorems** (∀ `start`, `dest` in a bounded grid):
  - `ValidPath(output.steps)` — the produced walk is legal.
  - `Len(output.steps) = OptimalLen` — **no shorter legal path exists**
    (optimality), established by quantifying over candidate paths and showing
    none reaches `dest` in fewer moves.
  - `output.total_distance = |dx| + |dy|` (Manhattan) — the cost the function
    reports.
- **Use-case probe.** The function assumes 8-connected (diagonal) movement. The
  spec models **both** 4-connected and 8-connected grids; the README records
  which matches the artifactsmmo move API. If the game is 4-connected, Chebyshev
  optimality is the wrong contract and the dual model exposes it rather than
  silently blessing the code.

### RecipeClosure — soundness AND completeness vs least fixpoint

Source algorithm: `collect` recurses through `_crafting_recipes` with a
`visited` guard; `raw_material_units` multiplies ingredient quantities down the
tree, revisit → 1.

- **Declarative spec.** `Closure` = least fixpoint of the recipe/drop relation,
  computed independently in TLA+ by saturation:
  `Closure = roots ∪ { sub : sub ∈ DOMAIN recipe[m] ∧ m ∈ Closure }`.
- **Theorems** (∀ recipe graphs in a bounded family, including one **cyclic**
  recipe and one **diamond / shared-subrecipe** graph):
  - `craftable_mats = { m ∈ Closure : recipe[m] ≠ <<>> }` — exactly. No omission
    (planner never drops a needed craft = **completeness**); no surplus (no
    wasted planner branching = **soundness**).
  - `needed_resources = { r : drop[r] ∈ Closure }` — exact.
  - `raw_material_units(item)` equals an independently defined recursive cost
    `Σ qty · units(sub)` with revisit → 1. Demonstrates the planner's quantity
    arithmetic is right and that cyclic recipes terminate at cost 1.

### PrerequisiteGraph — refinement of the planner's reachability

Source algorithm: `prerequisites(node, state, game_data)` returns a node's
direct prerequisites from game data; gather / unknown-source / already-satisfied
nodes are leaves.

- **Declarative spec.** The true dependency relation `DepEdges` defined directly
  from the modeled game data. A node is *satisfiable* iff repeated expansion
  reaches an all-leaves frontier.
- **Theorems:**
  - `prerequisites(n)` = exactly the direct predecessors of `n` under
    `DepEdges` — every emitted edge justified, none omitted.
  - Expansion from any objective root **terminates** (leaves have no
    successors), and the reachable leaf-set equals the materials the planner
    must actually obtain — search is **sound + complete + terminating**.
  - `combat_capable(s) ⇔ ∃ monster ∈ Monsters : predict_win(s, monster)` — the
    graph's combat gate is *equivalent* to the runtime verdict. This pins the
    exact bug class the combat-beatability-unification PLAN exists to eliminate
    (graph and runtime disagreeing on "beatable").

### PredictWin — closed-form ⇔ operational fight

Source algorithm: `predict_win` compares `rounds_to_kill = ceil(hp / hit)`
against `rounds_to_die`, with a `≤` vs `<` tiebreak on initiative
(`combat.py:79`).

- **Declarative spec.** A `Fight` state machine that **actually runs** the
  combat: alternating attacks (initiative decides who strikes first each round),
  HP decremented by `_expected_hit` per turn, until a combatant's HP ≤ 0 or
  `MAX_TURNS` is reached. `TrueOutcome` = who the simulator declares the winner.
- **Theorems** (∀ stat tuples in a bounded range):
  - `predict_win = TrueOutcome` — **refinement**: the closed-form shortcut equals
    the simulation it claims to summarize, including the initiative tiebreak.
  - **Monotonicity**: increasing player attack or decreasing monster HP never
    flips a win into a loss — guarantees the planner faces no perverse incentive.
  - **MAX_TURNS soundness**: a fight the simulator does not resolve by turn 100
    is correctly reported as a loss.

## Runner (`run.py`)

- Pure stdlib, invoked as `uv run python formal/run.py`.
- For each spec: `subprocess` runs PlusPy from the vendored clone
  (`python3 formal/vendor/PlusPy/pluspy.py -c<N> -P formal/specs <Module>`),
  with `<N>` = that module's input-domain size. A clean run prints no `Assert`
  failure and exits 0; a violated property halts PlusPy with the asserted
  message (non-zero exit / error text). The runner checks exit code and scans
  stdout+stderr for assertion-failure markers.
- Prints a per-module `PASS`/`FAIL` table; exits non-zero if any module fails or
  errors. Fails loud — no swallowed errors, consistent with the repo's
  no-silent-failure rule.
- If `formal/vendor/` is absent, the runner emits a clear instruction to run
  `formal/setup.sh` first (no auto-clone inside the runner).

## PlusPy provisioning

`formal/setup.sh` git-clones `tlaplus/PlusPy` into `formal/vendor/` (gitignored).
No third-party code vendored into the repo. The runner adds the clone to
`PYTHONPATH` / invokes its entry script. Pin a known-good PlusPy commit in the
script so runs are reproducible.

## Scope and honesty constraints

- **Bounded domains.** PlusPy interprets concrete states, so coordinates, stat
  ranges, and recipe-graph families are bounded to small enumerable sets.
  Correctness is demonstrated *over that domain*. The README says so explicitly.
- **Not TLAPS.** No unbounded machine-checked proof obligations. The artifacts
  are reference models + invariant runs.
- **Model fidelity.** Each `.tla` encodes the documented game rules
  (e.g. `_round_half_up`, the crit expected-value model, the initiative
  tiebreak) faithfully; the README maps every TLA+ operator to the Python line
  it mirrors so drift between model and code is reviewable.

## Out of scope

- I/O-bound functions (`get_character_position`, `find_nearest_*`,
  API wrappers) — no pure contract to model.
- `is_winnable` learned-loss veto (depends on `LearningStore` runtime history,
  not a pure function); the core `predict_win` it gates is covered.
- The live GOAP planner search loop (stateful, I/O-bound under `LearningStore`);
  only its pure substrate (`prerequisites`, `recipe_closure`) is modeled.
