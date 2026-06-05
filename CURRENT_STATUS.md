# Current Status — ArtifactsMMO CLI

## Project Goal

Build a GOAP (Goal-Oriented Action Planning) AI player that plays
ArtifactsMMO autonomously, with kernel-checked formal proofs that the
pure decision logic is correct. The CLI tooling is for diagnostic and
development support.

Design specs live under `docs/superpowers/specs/` (initial GOAP design,
robustness layer, autoregressive planning, strategic reasoning,
max-level objective). Formal verification under `formal/`.

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
- **2596 passed, 0 skipped, 0 failed** (production tests)
- **407 differential tests** (Python↔Lean parity over Hypothesis-
  generated inputs)
- **6055 Lean kernel jobs build**, axiom budget `LIV-001` only
  (`xpToNextLevel` + `xpToNextLevel_pos`)
- mypy strict: 163 source files, 0 errors
- ruff bug-finder: 0 errors on `src/artifactsmmo_cli/ai/`

### CI Gates (all green)
- **type-gate** — mypy strict over `src/`
- **lint-gate** — ruff bug-finder ruleset on `src/artifactsmmo_cli/ai/`
- **formal-gate** — per-section steps (build, orphan-modules,
  no-sorry, axiom hygiene, role manifest, differential, mutation);
  mutation step is `continue-on-error` with a 40-min cap so a slow
  mutation run can't false-fail the verdict of the prior gates
- **mutation-gate** — `formal/diff/mutate.py` perturbs Python and
  fails on surviving mutants
- **snapshot-refresh** — refreshes `formal/sim/game_data_snapshot.json`
  from the live API

Pre-commit hook (`scripts/pre_commit.sh`) runs mypy + ruff + pytest
before every commit; no project-level bypass flag.

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
| `account` | details, logs |
| `play` | autonomous GOAP AI player (`--verbose`, `--dry-run`, `--learn`, `--trace`, `--tui`) |
| `stats` | sessions, summary — read session metrics from `learning.db` |

---

## GOAP AI Player

### Architecture
```
src/artifactsmmo_cli/ai/
├── world_state.py          # Frozen WorldState — single source of truth
├── game_data.py            # Static cache: monster/resource locations, recipes, item stats
├── planner.py              # Forward A* (Dijkstra under h=0; 90s budget)
├── player.py               # Main loop: sense → arbiter → plan → act → snapshot → learn
├── combat.py               # predict_win (rounds_to_kill vs rounds_to_die)
├── arbiter_select.py       # Pure-core select_pure (sticky-then-walk)
├── strategy_driver.py      # StrategyArbiter (guards → collect → step → discretionary)
├── craft_relief.py         # CRAFT_RELIEF circuit-breaker candidate scoring
├── inventory_caps.py       # useful_quantity_cap + overstocked_items
├── bank_selection.py       # select_bank_deposits with keep-set
├── recipe_closure.py       # walk crafting_recipe transitively
├── trace_stats.py          # SQLite-backed session analyzer
│
├── actions/                # ~25 Action subclasses (is_applicable / apply / cost / execute)
├── goals/                  # ~20 Goal subclasses (value / is_satisfied / desired_state / relevant_actions)
├── tiers/                  # Tier-0/1/2/3 decision layers
│   ├── objective.py        # CharacterObjective (target gear / tools / skill levels / char level)
│   ├── meta_goal.py        # ObtainItem / ReachCharLevel / ReachSkillLevel
│   ├── prerequisite_graph.py # Recursive recipe + skill prereq edges + objective_roots
│   ├── strategy.py         # decide() — ranks roots, picks chosen_step (with sticky-commit)
│   ├── means.py            # MeansKind + active_means (collect-reward + discretionary)
│   └── guards.py           # GuardKind + active_guards (interrupt ladder)
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
   `GatherMaterialsGoal`, `ReachSkillLevel` → `LevelSkillGoal`,
   `ReachCharLevel` → `GrindCharacterXPGoal`. Suppressed when an active
   items-task PursueTask would gather the same redundant material.

4. **Tier-3 — discretionary means** (`tiers/means.py`): pursue task,
   accept task, task exchange, sell idle, bank expand, wait.

The `StrategyArbiter` builds the ordered candidate list and walks via
`select_pure` (`arbiter_select.py`). Selection is sticky: a committed
goal that still fires + still plans wins re-selection without
preemption from a peer; only a guard can break commitment.

### Planner

Forward A* with `h ≡ 0` (Dijkstra). 90s wall-clock budget (covers a
game cooldown on cold runs). Per-goal `relevant_actions` filter bounds
branching to the goal's recipe closure. `max_depth` ranges from 15
(default) to 100 (PursueTask, LevelSkill, GatherMaterials).

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

---

## Formal verification

Lean 4 + Mathlib v4.30.0. `formal/Formal/` modules pin pure decision
logic; `formal/diff/test_*.py` differential tests assert
Python ↔ Lean parity over Hypothesis-generated inputs; `formal/diff/mutate.py`
perturbs Python and fails on surviving mutants.

**Coverage**: 38+ proven AI components (kernel-checked ∀ inputs,
sorry-free, axiom budget = `LIV-001` only). See `formal/README.md` for
the running coverage list + phase-by-phase findings (real bugs caught
during formalization + NOT-A-BUG verdicts).

---

## Known limitations / next up

- **Multi-character coordination** not in scope yet.
- **Combat XP from tasks only**: task-driven runs accumulate combat
  XP slowly when most tasks are mining/woodcutting items. Bot
  eventually levels via task rewards + occasional grinds; not a bug,
  just slow when the meta-objective is `ReachCharLevel(50)`.
- **Planner I/O bottleneck**: with the LearningStore enabled, every
  node hits SQLite for cost/yield lookups. Deep recipe chains can
  burn the 90s budget on I/O alone. `search_cache()` context manager
  amortises within a single `plan()` call but the budget is firm.
- **Live API snapshot drift**: the `formal/sim/game_data_snapshot.json`
  used by some diff tests can drift when the live game updates its
  catalog. `snapshot-refresh` workflow refreshes it; the affected
  diff test is in the ignore list of the formal gate's bulk pytest
  invocation so drift doesn't false-fail the gate.
