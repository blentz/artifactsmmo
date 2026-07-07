# Progression-Tree Selector — Design

Date: 2026-07-06
Status: approved (design); implementation via phased plan
Supersedes: the flat multiplicative root ranking in `ai/tiers/strategy.py`

## Problem

Root selection is a flat scalar competition: ~34 roots (gear, skills, char
level, capstone, potions) ranked by `prior × marginal × balancing ×
learned-blend`, governed by ~8 hand-tuned constant families. Every
misbehavior to date (grind overshadow, dampeners, urgency floors, capstone
gradients — see the retune history in project memory) is a rebalancing of
this surface, and each fix tilts another corner. Live symptom (2026-07-06,
L13 Robby): `small_health_potion` at 5/2 and `ReachCharLevel(14)` at 9/4
dominate; the real upgrades rank 6th (`fire_bow`, 1) and 8th
(`iron_shield`, 2/5); standalone skill roots (weaponcrafting 15 at 9/5)
outrank both. The bot alternates potion-crafting and blue-slime grinding;
gear stalls. Categories with an inherent order should not scalar-compete.

## Model (user-specified)

- **Trunk**: L50 through milestones — L10, L20, L30, L40, L50.
- **Two main branches** off the trunk:
  1. gear upgrades → gear crafting → resource gathering / targeted
     monster drops;
  2. fighting monsters for character XP toward `level + 1`.
- **Tertiary** supporting concerns: inventory/bank management,
  craft-vs-buy, bag upgrades, effect optimization, loadout-to-task
  optimization, events/boss fights, etc.

Decisions locked during brainstorm:
- Skills are **pure prerequisites**: a craft skill levels only when a
  concrete gear/consumable chain demands it. No standalone
  `ReachSkillLevel` roots. The L50 capstone stops competing and becomes
  the trunk. (Option A)
- Potions remain **strategically meaningful gear** (not tertiary), with a
  **per-type tunable weight table** — health maximized now; boost /
  resist / antipoison and future types dialed later. (Option B + weights)
- Branch arbitration is **adequacy-switched**: gear-first while the
  current band's loadout is below adequate; once band-adequate, xp-first
  to the next milestone; gear re-takes on adequacy break (new band or a
  strictly better reachable target). One boolean pivot, no scalar war.
  (Option A)
- Rollout: **shadow-first**, with a CLI/scenario testability workstream
  built BEFORE the new selector. (User directive)

## Architecture

New pure module `ai/tiers/progression_tree.py` (one behavioral unit; pure
cores extracted per repo convention):

```
trunk    : ReachCharLevel(min(50, (level // 10 + 1) * 10))
branch   : branch_pick_pure(band_adequate, gear_target_exists) -> GEAR | XP
  GEAR   : target = best per-slot upgrade (existing near_term_gear picker)
           ∪ utility slots scored via POTION_TYPE_WEIGHTS (per-type table)
           -> ObtainItem step -> existing actionable_step decomposition
              (skill prereqs, task funding, drop-farm, buy legs unchanged)
  XP     : GrindCharacterXP(best winnable in-band monster; existing picker)
tertiary : the proven guards > collect > discretionary means ladder,
           UNTOUCHED (inventory/bank/tasks/sell/recycle/expand/events)
```

- The tree replaces the *internals* of `StrategyEngine.decide` (what
  produces `chosen_root`/`chosen_step`). The **arbiter is not touched**:
  `select_pure` (o54 SELECT differential, 23 bound slots) and the
  DecideKey ladder consume the chosen step exactly as today.
- Sticky commitment survives, applied to the single branch target so
  chains do not flap mid-pursuit. `lower_band_precedes` and preemption
  semantics unchanged.
- Deleted at flip: `PRIOR_*`, `CHAR_GAP_PER_LEVEL(_GEARED)`,
  `SKILL_GAP_*`, `CHAR_CAPSTONE_SCALE`, balancing/learned-blend wiring in
  root scoring, standalone skill-root generation, and their mutants /
  StickySelect scoring theorems. STRATEGY_MUTATIONS / traversal diff
  rebind to the tree cores.

### Adequacy signal

Reuse the existing band gear-adequacy computation (geared-gate +
E-tower `adequate`/`gearGap` observables). `branch_pick_pure` consumes a
Bool + "reachable gear target exists" flag — both computed by existing
helpers (`near_term_gear` nonempty ∧ target plannable-now).

### Potion-type weights

`POTION_TYPE_WEIGHTS: dict[effect-family, Fraction]` — a single tunable
table (health/restore maximized now; boost, resist, antipoison, future
families adjustable independently). Utility-slot targets are scored by
`weight(type) × effect-magnitude`; the table is the ONLY tuning surface
for consumables in the gear branch. Refill churn is bounded by the
existing provisioning quantities (win-rate provisioning guard unchanged).

## Testability workstream (Phase 1 — built first, on the CURRENT engine)

- Refactor `GamePlayer.plan_once` into a pure
  `plan_from_state(state, game_data, history) -> PlanReport` with no
  ClientManager dependency; the CLI `plan` command and tests share this
  single entry point.
- `tests/scenarios/`: `ScenarioCharacter` builder (level, gear,
  inventory, bank, skills, task, gold) + GameData loaded from the real
  snapshot (`formal/sim/game_data_snapshot.json`) — realistic catalog,
  deterministic, zero API.
- Golden scenario tests (expected selected-goal category + first action
  class + plan non-emptiness), e.g.: L1 fresh start → xp branch, fights a
  starter monster; L10 copper-set band-adequate → xp; L10 with a
  reachable weapon upgrade → gear chain step; L8 overstocked inventory →
  deposit guard preempts; empty utility slot → potion target per weight
  table; one scenario per level band for the trunk.
- CLI: `artifactsmmo plan --scenario <name|file>` runs the same fixtures
  interactively for debugging.
- Goldens are written against the CURRENT engine first (regression net
  during the rework), then forked to tree expectations at flip.
- L50 connection: band scenarios double as empirical evidence for the
  `ai_reaches_fifty` capstone; the milestone trunk aligns with the
  LevelingDescent measure (each milestone is a measure decrement).

## Shadow rollout (Phase 3)

- `decide()` computes both the legacy ranking decision and the tree
  decision; enacts legacy until the flip flag; both are traced per cycle
  (new `tree_decision` snapshot field).
- `plan --tree` prints the tree's would-be decision next to the legacy
  one; a divergence report (stats subcommand) summarizes agreement by
  scenario class over live traces.
- Flip via config once divergence is reviewed; legacy pipeline and its
  mutants/theorems are deleted in the following phase, gate-green.

## TUI impact

- The plan screen's prerequisite Tree and the log `why` line currently
  render the flat `goal_rank`; post-flip they render the descent
  (trunk milestone → branch → target → step), which is strictly more
  legible. During shadow, snapshots carry both decisions; the log line
  gains a compact `tree:` annotation. Trace/snapshot schema additions are
  versioned (CACHE_VERSION bump if any cached schema changes).

## Formal plan

- New tiny cores, proven + mutation-bound to scenario/unit tests:
  `branch_pick_pure` (total, deterministic switch),
  `gear_target_pick` (argmax with semantic tiebreak, no repr sorts),
  potion-type weight lookup (table total over families).
- Untouched: guards/means ladder (DecideKey, MeansFiring, ProductionLadder),
  planner admissibility, apply-baseline, o54 SELECT differential.
- Retired at flip: scalar-ranking constants + mutants + StickySelect
  scoring theorems (commitment semantics keep their proofs).
- Zero-vacuousness discipline: every retired theorem is deleted, not
  weakened; every new hypothesis gets a satisfiability witness.

## Phases

1. **Testability**: `plan_from_state` refactor + scenario harness +
   goldens on the current engine. Gate green.
2. **Tree module**: pure cores + Lean + unit/scenario tests (not wired).
   Gate green.
3. **Shadow**: dual-trace, divergence report, `--scenario`/`--tree` CLI,
   TUI shadow annotation. Gate green; run live for review.
4. **Flip + retire**: cutover, delete legacy ranking, rebind mutants,
   TUI descent rendering, full gate.

Each phase lands independently valuable and gate-green.

## Risks

- Adequacy oscillation at band edges → sticky commitment on branch
  target + adequacy hysteresis if observed in shadow.
- Hidden dependencies on ranking internals (worth-suppression,
  objective-committed arbitration read `chosen_root`) — Phase 2 keeps
  the `StrategyDecision` interface identical (root/step/desired_state/
  ranking fields), with the tree filling `ranking` with its descent for
  display compatibility.
- Scenario goldens on the current engine may encode today's BUGS as
  expectations — goldens assert category/step-class, not exact scores,
  and are forked at flip.
