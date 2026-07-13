# Current Status — ArtifactsMMO CLI

*Last updated: 2026-06-11.*

## Project Goal

Build a GOAP (Goal-Oriented Action Planning) AI player that plays
ArtifactsMMO autonomously, with kernel-checked formal proofs that the
pure decision logic is correct. The CLI tooling is for diagnostic and
development support.

Design specs live under `docs/superpowers/specs/` (initial GOAP design,
robustness layer, autoregressive planning, strategic reasoning,
max-level objective, objective-committed arbitration, LevelSkill
liveness, per-goal inventory profiles). Formal verification under
`formal/`; the mechanical-extraction program is documented in
`docs/PLAN_mechanical_extraction.md` (COMPLETE) and the 2026-06-09
trace-bug campaign in `docs/PLAN_trace_bug_fixes.md`.

---

## Infrastructure

### API Client
- Generated from the live OpenAPI spec via `generate_openapi_client.sh`
- Two patches applied at generation time:
  1. Fight endpoint request body: `allOf + $ref + default` → plain
     `$ref` (ModelProperty default bug)
  2. `nullable: true` + `$ref` → `anyOf: [{$ref}, {type: null}]` for
     null-safe `from_dict`
- Custom template `openapi_templates/types.py.jinja` produces
  `X | Y` (PEP 604) instead of `Union[X, Y]`

### Test Suite
- **3117 passed, 0 skipped, 0 failed** (production tests, 100% coverage)
- **484 differential tests** in the gate's run (Python↔Lean parity over
  Hypothesis-generated inputs; 489 collected under `formal/diff/` in
  total — the snapshot-fixture drift test is gate-excluded)
- **152 Lean modules** under `formal/Formal/` build sorry-free;
  safety axioms ⊆ {propext, Classical.choice, Quot.sound}; liveness
  axiom budget = `LIV-001` only (`xpToNextLevel` + `xpToNextLevel_pos`)
- **267 mutation anchors** (89 target groups) in `formal/diff/mutate.py`
- mypy strict: 201 source files, 0 errors
- ruff: full pyproject ruleset green over `src/` + `tests/`

### CI Gates (all green)
- **pytest** — full production suite (added 2026-06-09)
- **type-gate** — mypy strict over `src/`
- **lint-gate** — full ruff ruleset on `src/` + `tests/`
- **formal-gate** — per-section steps: Lean kernel build,
  orphan-modules, no-sorry, axiom hygiene, role manifest,
  **extraction drift** (regenerate `Formal/Extracted/`, diff must be
  empty), differential suite, mutation (55-min cap,
  `continue-on-error` so a slow run can't false-fail the prior
  verdicts), strict OpenAPI conformance
- **mutation-gate** — `formal/diff/mutate.py` perturbs Python and
  fails on surviving mutants. **First-ever green CI run 2026-06-10**:
  the two step-direction mutants made `calculate_path` diverge and
  OOM-kill the 16GB runners (exit 137 miscounted as a kill) — fixed by
  a liveness guard bounding the step loop (`96fdce5`); four green runs
  followed the same day
- **snapshot-refresh** — refreshes `formal/sim/game_data_snapshot.json`
  from the live API

`formal/gate.sh` part structure: (pre) Mathlib cache, (a) kernel
build, (a') orphan modules, (a'') no sorry/admit, (b) axiom lint,
(b') role manifest, (b'') proof-concept index, (b''') extraction
drift, (d) differential (globs `formal/diff/`, one snapshot-drift
ignore), (c) mutation. Never run gate.sh / mutate.py concurrently with
anything that reads `src/` — mutate.py live-writes mutants.

Pre-commit hook (`scripts/pre_commit.sh`) runs mypy + ruff bug-finder
+ the AI test suite before every commit; no project-level bypass flag.

### Mutate↔play interlock
`formal/diff/mutate.py` holds a repo-root lockfile
(`.mutation-run.lock`) for the whole run; `play` refuses to start
while the lock is active (`src/artifactsmmo_cli/utils/mutation_lock.py`),
so the bot can never run on mutated source.

### CLI Commands
| Command group | Status |
|---|---|
| `status` | API connectivity check |
| `character` | list, create, delete, info, inventory, status, cooldown |
| `action` | move, fight, gather, rest, equip, unequip, use, goto, path, batch |
| `bank` | list, details, deposit/withdraw gold/items, expand, deposit-all, exchange |
| `trade` | ge-buy, ge-sell, ge-orders, ge-cancel, prices, orders, history, analyze, trending, opportunities, spread |
| `craft` | craft, recycle, preview, recipes |
| `task` | new, complete, exchange, trade, cancel, status, list |
| `info` | items, monsters, monster, resources, achievements, leaderboard, events, map, npcs, npc, nearest |
| `account` | details, logs (flat real-schema rendering since 2026-06-09) |
| `play` | autonomous GOAP AI player (`--verbose`, `--dry-run`, `--learn`, `--trace`, `--tui`) |
| `stats` | sessions, summary — read session metrics from `learning.db` |

The 2026-06-09 commands cleanup deleted 24 dead `cooldown_remaining`
branches (the helper never set the field) and fixed account-logs
rendering against the real schema.

---

## GOAP AI Player

### Architecture
```
src/artifactsmmo_cli/ai/
├── world_state.py          # Frozen WorldState — single source of truth
├── game_data.py            # GameData FACADE — public accessors only
├── item_catalog.py         # ┐
├── monster_catalog.py      # │ domain catalogs behind the facade
├── recipe_catalog.py       # │ (no private GameData reads exist
├── location_catalog.py     # ┘  outside the facade + catalogs)
├── constants.py            # centralized magic numbers
├── planner.py              # Forward A* (Dijkstra under h=0; 10s cheap pass / 300s escalation)
├── player.py               # Main loop: sense → arbiter → plan → act → snapshot → learn
├── combat.py               # predict_win (rounds_to_kill vs rounds_to_die)
├── combat_picker.py        # window-preferred target pick + liveness fallback (pure core)
├── arbiter_select.py       # Pure-core select_pure (sticky-then-walk)
├── strategy_driver.py      # StrategyArbiter — select decomposed into tier-phase
│                           #   helpers (_plans/_resolve_step_goal/_suppress_step_for_task/
│                           #   _build_candidates/_worth_gate_suppressed/_arbitrate)
├── task_reservation.py     # items-task material reservation (step-tier suppression)
├── doomed_memo.py          # unplannable-goal memo, exponential-backoff TTL
├── shopping_list.py        # bank-aware acquisition (fueled, DAG-safe)
├── craft_relief.py         # CRAFT_RELIEF candidates — net-relief gate + batched crafts
├── inventory_caps.py / inventory_profile.py  # per-goal soft-target profiles
├── inventory_keep.py       # THE keep authority: keep_in_bag/keep_owned/bankable/
│                           #   destroyable — per-reason QUANTITIES (no code-sets)
├── bank_selection.py       # select_bank_deposits — banks bankable(code) per held code
├── kit_selection.py        # best fighting weapon / best gathering tool per skill
├── recipe_closure.py       # walk crafting_recipe transitively (fueled)
├── trace_stats.py          # SQLite-backed session analyzer
│
├── actions/                # ~30 Action subclasses + factory.py (all action
│                           #   construction extracted from GamePlayer)
├── goals/                  # ~20 Goal subclasses (value / is_satisfied / desired_state / relevant_actions)
├── tiers/                  # Tier-0/1/2/3 decision layers
│   ├── objective.py        # CharacterObjective (target gear / tools / skill levels / char level)
│   ├── objective_needs.py  # NeedSet derivation (worth gate input)
│   ├── meta_goal.py        # ObtainItem / ReachCharLevel / ReachSkillLevel
│   ├── prerequisite_graph.py # Recursive recipe + skill prereq edges + objective_roots
│   ├── strategy.py         # decide() — ranks roots, picks chosen_step (sticky-commit)
│   ├── means.py / means_worth.py # MeansKind + active_means + worth gate
│   ├── guards.py           # GuardKind + active_guards (interrupt ladder)
│   ├── equip_value.py      # equipment scoring — EXACT arithmetic (int/Fraction, float-free)
│   └── skill_gates.py / skill_grind_target.py # skill-gate deadlock-breaking
├── equipment/              # scoring, projection, realizable_loadout (exact arithmetic)
├── blockers/               # documented progression gates + registry
└── learning/
    ├── models.py           # Cycle / Session / Blocker / SkillXpObservation / TaskRewardObservation
    ├── store.py            # LearningStore (SQLite via SQLModel)
    └── projections.py      # cheapest_path_to_level + per-cycle yield projections
```

### Decision layers

1. **Tier-0 — guards** (`tiers/guards.py`): hard-interrupt ladder.
   In order: `HP_CRITICAL`, `BANK_UNLOCK`, `REACH_UNLOCK_LEVEL`,
   `DISCARD_CRITICAL`, `CRAFT_RELIEF`, `DEPOSIT_FULL`, `DISCARD_HIGH`.
   First firing guard wins.

2. **Tier-1 — collect-reward means** (`tiers/means.py`): claim pending,
   complete task, sell-pressured, low-yield cancel, task cancel.

3. **Tier-2 — objective step** (`tiers/strategy.py` →
   `objective_step_goal`): the ladder-derived single step toward the
   highest-ranked meta-objective root. Maps `ObtainItem(gear)` →
   `UpgradeEquipmentGoal`, `ObtainItem(resource)` →
   `GatherMaterialsGoal`, `ReachSkillLevel` → `LevelSkillGoal` (a
   narrow skill-gate deadlock-breaker, not a grind engine),
   `ReachCharLevel` → `GrindCharacterXPGoal`.

4. **Tier-3 — discretionary means** (`tiers/means.py`): pursue task,
   accept task, task exchange, sell idle, bank expand, wait.

**Objective-committed, need-gated arbitration** (merged 2026-06-09):
the arbiter commits to a `chosen_root` and worth-suppresses task means
that serve no objective need (`objective_needs` NeedSet → `means_serves`
gate); combat-readiness urgency can lift a weapon to chosen_root.
**Task-material reservation** (2026-06-09): while an items task is
active, the task item's closure demand × remaining need is reserved;
a step-tier goal that would consume reserved, non-surplus materials is
deferred for the cycle (`task_reservation.py`, proven in
`TaskReservation.lean`).

The `StrategyArbiter` builds the ordered candidate list and walks via
`select_pure` (`arbiter_select.py`). Selection is sticky: a committed
goal that still fires + still plans wins re-selection without
preemption from a peer; only a guard can break commitment. Goals that
failed to plan are memoized by plannability signature with an
exponential-backoff TTL (`doomed_memo.py`).

### Planner

Forward A* with `h ≡ 0` (Dijkstra). Two-pass budget: the arbiter's
cheap pass gives every candidate 10s (`CHEAP_BUDGET_SECONDS`); the
escalation pass allows up to 300s for a genuinely deep but reachable
goal. Per-goal `relevant_actions` filter bounds branching to the
goal's recipe closure; per-goal `max_depth` ranges from the default 15
up to 100 (PursueTask, LevelSkill, GatherMaterials). Action
construction lives in `actions/factory.py`, which emits residual
unit-quantity withdraws for every material (at most one extra action
per material) so bank coverage is always plan-expressible.

Proven optimal: `formal/Formal/PlannerAdmissibility.lean` shows
`firstSatisfied_least_cost_of_admissible` applied with h=0 gives
strict-cost-minimum plans for all non-negative-cost action sets.

### Learning store

SQLite-backed event log (`~/.cache/artifactsmmo/learning.db`). Per-cycle
records (state snapshot + selected goal + action + outcome + planner
stats + delta_inv/xp/hp + drops). Per-session rows. Per-skill XP
observations. Per-task reward observations. Per-blocker progression
gates (e.g. bank achievement requires defeating sea_marauder L45).

Read by the planner via `action_cost` / `success_rate` / `goal_avg_cycles`
for cost-shaping. Read by `cheapest_path_to_level` for objective
projection. Read by `stats` subcommand for session inspection.

### Behavioral fixes from the 2026-06-09 trace campaign

Analysis of 5 play traces (17.6h, 1,485 cycles, level 4 frozen,
0 combat XP) produced `docs/PLAN_trace_bug_fixes.md`; all confirmed
bugs are fixed, each pinned by Lean models + diff oracles + mutation
anchors where behavior is formal:

- **No-combat deadlock**: `winnable ∩ [L-1, L+2] = ∅` at low levels made
  the picker return None forever. Fixed with a window-preferred picker
  plus a liveness fallback to the highest-level winnable XP-positive
  monster (`combat_picker.py`); `FightAction`'s lower gate is now
  XP-gated (`xp_per_kill > 0`); `_sync_*` rebuilds use
  `dataclasses.replace` so combat stats survive bank refreshes.
- **Task-material theft**: gear-step goals consumed the active items
  task's crafted materials, restarting the task from zero forever —
  fixed by the reservation rule above.
- **TaskExchange timeout storm**: "drain ALL coins" satisfaction made
  the minimum plan exceed `max_depth` (guaranteed 300s timeout,
  re-armed at every memo expiry, 24-29% of wall clock). Now one-batch
  satisfaction + narrowed `relevant_actions` + doubling memo TTL.
- **Gather replan failure**: bank stock was unreachable by the
  factory's withdraw quanta; the residual unit-withdraw fix makes the
  documented plan-admissibility true.
- **CraftRelief flap**: 1:1 recipes relieve nothing; the guard now
  requires net relief per craft and batches crafts to the relief
  target.
- **Equip 485 loop**: the planner proposed equipping a code already
  worn in another slot; `EquipAction` now refuses, and HTTP 485 is
  survived in the run loop like other action-level failures.
- **Honest exits**: worker-thread death is supervised via
  `threading.excepthook`; a dead bot thread no longer ghosts the TUI
  for hours or records `exit_reason="normal"` on a crash.

Deferred from the campaign (perf, not correctness): BATCH_CAP=10
travel amortization and withdraw-dribble plan shapes; worth-gate
steady-state bypass re-check pending fresh post-fix traces.

---

## Formal verification

Lean 4 + Mathlib. `formal/Formal/` (152 modules) pins pure decision
logic; `formal/diff/test_*.py` (66 files, 484 gate-run tests) assert
Python ↔ Lean parity over Hypothesis-generated inputs;
`formal/diff/mutate.py` (267 anchored mutations) perturbs Python and
fails on surviving mutants.

**Coverage**: 38/38 proven AI components (kernel-checked ∀ inputs,
sorry-free; safety axioms ⊆ {propext, Classical.choice, Quot.sound},
liveness budget = `LIV-001`). See `formal/README.md` for the running
coverage list + phase-by-phase findings (real bugs caught during
formalization + NOT-A-BUG verdicts).

### Mechanical extraction (COMPLETE, 2026-06-10 → 2026-06-11)

Hand-written Lean models can lie about the code (the
CombatTargetExistence false-theorem class). The extraction program
closed that gap: **all 15 pure decision cores** now have Lean
definitions **mechanically generated from the Python source** by
`scripts/extract_lean.py` (AST-level transpiler for a restricted,
typed, pure Python subset), sha256-stamped and byte-deterministic.

- **Extracted cores (15)**: ArbiterSelect, CombatPicker,
  CyclesForProgress, EquipmentScoring, EquipValue, InventoryCaps,
  MinGathers, NearestTile, NpcBuyCore, PriorityBand, RecipeClosure,
  ScalarCore, ShoppingList, TaskBatch, TaskReservation →
  `formal/Formal/Extracted/`.
- **Bridges** (`Bridges.lean` … `Bridges7.lean`): kernel proofs
  connecting every extracted def to its hand model (or directly to the
  spec). Load-bearing hand theorems transfer onto the extracted defs
  (survival floor, sticky guard-wins, clamps/tiebreaks, batch ≥ 1,
  reservation surplus-safety, closure soundness + completeness iff).
- **Gate**: `formal/gate/check_extraction.sh` re-runs the extractor,
  requires regeneration to be a byte-level no-op, then `lake build`
  proves the bridges. Python drift ⇒ regenerated def changes ⇒ bridge
  breaks ⇒ gate red. Wired into gate.sh part (b''') and formal-gate CI.
- **Four hand-model divergences found by bridging** (Python was the
  spec; models corrected): NpcBuy Nat-truncation outside
  wellformedness; ShoppingList constant-credit vs consume on DAG
  recipes; CyclesForProgress keeping prevProgress through None
  readings; minGathers constant-credit (DAG witness 1 vs 0). Latent
  code findings: an order-dependent set-iteration early-return in the
  dominance walk, RecursionError on cyclic recipes (now fuel-bounded),
  and 92-in-200k float "strict" orderings that were rounding noise.
- **Exact decision arithmetic**: equipment scoring
  (`tiers/equip_value.py`, `equipment/scoring.py` and consumers) moved
  from float to exact int/Fraction arithmetic — exact is the spec
  going forward; near-tie rankings may legitimately differ from the
  old float behavior, and the diff oracles are re-pinned exactly
  (tolerances removed).
- **Standing policy**: every new pure core ships with an extracted
  model from day one.

---

## Known limitations / next up

- **What is NOT proven** (honest scope): cross-core *composition* is
  not bridged core-by-core (it is covered from the other side by the
  arbitration/liveness models); the environment/server is axiomatized,
  not modeled (server axioms are replayed against the live API, and
  new ones need per-axiom signoff + OpenAPI citation). Remaining
  trusted seams, documented and sampled but out of scope by design:
  the extractor itself (~480 oracle tests sample it), the single
  `float()` boundaries on the two learning wrappers (exact cores
  behind them), and the impure I/O shells around the pure cores.
- **Level-50 liveness** remains the long-term open goal: LevelSkill is
  proven as a skill-gate deadlock-breaker, not a grind engine; the
  full "planner never deadlocks / always reaches level 50" theorem is
  future work.
- **Deferred perf items** (from the trace campaign): BATCH_CAP=10
  travel amortization (38% of wall clock was travel) and
  withdraw-dribble plan shapes (×3 ten times; ×10↔trade ping-pong).
  Both are formally pinned behaviors; changing them is tuning, not a
  bug fix.
- **Worth-gate steady-state re-check pending**: pre-fix traces showed
  worth-gate bypass as steady state (55-69% of cycles), mostly a
  consequence of the no-combat bug. Needs fresh post-fix traces to
  confirm it subsided.
- **Multi-character coordination** not in scope yet.
- **Planner I/O bottleneck**: with the LearningStore enabled, every
  node hits SQLite for cost/yield lookups. The cheap-pass/escalation
  split (10s/300s) plus the doomed-goal memo keep this off the hot
  path, but deep recipe chains under `--learn` are still I/O-bound.
- **Live API snapshot drift**: the `formal/sim/game_data_snapshot.json`
  used by some diff tests can drift when the live game updates its
  catalog. `snapshot-refresh` refreshes it; the affected fixture diff
  test is excluded from the gate's bulk pytest invocation so drift
  doesn't false-fail the gate.
