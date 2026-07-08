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
  inventory, bank, skills, task, gold) + GameData loaded offline from a
  committed copy of the disk-cache bundle (richer than the formal/sim
  snapshot: includes maps/NPCs/tasks/locations) — realistic catalog,
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

**GAP-7 + follow-up wave SHIPPED (2026-07-08, 9ebc927c..c50dd926):**
GAP-7: recipe_closure reads secondary drops via caller-side layer union
(proven core byte-identical, union proven exact) + gather_serves_closure
precision admission at 6 sites (flood self-caught by the bound net; net
6× faster). GAP-8 (live Robby stall): craft chains with monster-drop
ingredients plan via a Fight leg in the generator (GAP-6's proven wiring;
is_applicable-gated at the single chokepoint after review caught the
suicide-guard bypass); l13_drop_recipe_grind = live-API-mirror scenario +
6-recipe class sweep (set-equality pinned). Dup-allowed slots (rings AND
artifacts had the identical quirk) fill with the best duplicate. Vendor
gold buys respect the progression reserve (post-buy total ≥ reserve,
exact ints) and joint affordability holds over the admitted SET
(cheapest-first prefix, full-set invariant re-check per admission —
20K-trial fuzz, zero overspends). Drop-vs-craft route pinned: CRAFT
(9.0 < 10.0). DEBTS at next bot downtime: full gate + lake build +
effective_floor_multi Lean mirror (multi floor_plus_cost identity,
singleton reduction, oracle arm). OPEN DESIGN QUESTIONS (user call):
equip_value utility-stat weighting (deliberate, now dominates argmax at
scale — near_term_gear fixed points can be combat-weaker); drop-rate
cost modeling (1-fight-per-unit optimism now live in argmax).

**Slot-gap fix wave SHIPPED (2026-07-08, 563a5759..c9455a4f):** the five
real gaps pinned by the slot-coverage net are fixed, each tripwire flipped
to a positive test: ①held/banked stock credits is_attainable_now (incl.
currency recursion) ②full gather-drop set feeds _gatherable (rare drops →
vendor routes open; perfect_pearl now a fleet-wide artifact default)
⑤both utility slots fillable — per-slot stock check; slot 2 =
second-best craftable-now heal (same-code dual slots are server-illegal:
the old utility2 livelock) ③gold-priced vendor buys plannable — root was
gold read as an INVENTORY item in analyze_currency_leaves; proven
WithdrawGoldAction admitted+deficit-sized (zero new formal surface)
⑥equip targets acquire via targeted drops — gathering.py's proven
dropper wiring mirrored into UpgradeEquipmentGoal (grey-farm bypass for
the goal's own argmax-committed target; Lean dropFarm scope =
comments-only). GAP-4 (XP outranks empty utility) RETAINED as designed.
NEW GAP-7 pinned: recipe_closure still reads the primary drop map
(goal-layer analog of ②) — item-currency purchases (small_pearls →
perfect_pearl) die at 1 node. Follow-ups: GAP-7; gold-funding root;
gold-buy vs reserve floor; equip_value utility inflation; dup-slot
second-ranked quirk; craftable-target route-preference test. Full gate
owed at next bot downtime.

**Phase 4b SHIPPED — THE FLIP (2026-07-07):** commits 388f15c2 (decide()
delegates to decide_tree; servability demotion `_servable_promotion`
walks fallback pairs in order, all-unservable keeps choice for the
doomed-memo; goldens promoted — XFAIL_TODAY/CURRENT_TODAY/goldens_tree
deleted per their delete-at-flip mandates; shadow chrome removed),
ef67c1d6 (flat ranking DELETED: −1922 lines — all scoring constants, 11
pipeline methods, standalone skill roots, player-side sticky machinery;
arbiter-side commitment untouched), b2fc60d9 (formal retire: RankingComposition/
StickySelect/ObtainProgress/ZombieFreedom/GatedArming/PersonalityGrounding
+ 4 diff harnesses + 10 mutant groups; DecideKey DISPATCHER half KEPT —
shadows live map_guard/map_means; comparator half deleted; diff 721→703;
L50 capstone ai_reaches_fifty verified hypothesis-free and building),
8a3c5774 (descent rendering; chosen_step_alive/objective_roots/
near_term_skill_targets retired). Sticky decision RECORDED: decide-level
scoring retired (tree deterministic — 326 identical shadow picks);
arbiter-level commitment + zombie release survive. Remaining tuning
surface = POTION_TYPE_WEIGHTS. Post-flip backlog: tree-native
arming/anti-zombie re-proof; DecideKey repr-vs-dispatch mechanical
assert; per-band L20-50 scenarios. GATE: full run REQUIRED at next bot
downtime (red-by-construction risk window closed at b2fc60d9; static
anchor sweep 535 units 0 stale).

**Phase 4a SHIPPED (2026-07-07):** commits 3405472c (`--progression-tree`
flag on play+plan, default OFF; flip point at both decide sites with
object-identity flag-off guarantee; enacted decision feeds arbiter, sticky
anchor, crafting-target, servability, PlanReport.decision +
enacted_engine; record["enacted"] marker; record["strategy"]/["tree"] stay
engine-true — symmetric shadow), 532f7d95 (zero-gain utility filter —
Phase-2 latent flag closed), 3cf535f4 (flag-on tree goldens = the 4b
promotion set; guards proven engine-independent: RestoreHP /
DiscardOverstock identical under both engines).

**Phase 4b REQUIRED checklist (data-gated on corrected-shadow review):**
default flip → legacy-ranking deletion → STRATEGY_MUTATIONS rebind →
StickySelect scoring-theorem retirement → Phase-1 strict-xfail promotion +
CURRENT_TODAY deletion + legacy-golden retirement (test_goldens.py vs
test_goldens_tree.py reconciliation) → TUI descent rendering AND
strategy_ranking/plan_tree snapshot panes fed from the ENACTED engine
(final-review REQUIRED item — panes currently legacy-fed, misleading
during flag-on soak) → flag-on _decide_band live-loop integration test
(REQUIRED before extended soak) → POTION_TYPE_WEIGHTS tuning (empty
utility slot currently outranks xp/task-funding in l10_copper_adequate and
l12_taskgated_bag — deliberate argmax consequence, re-examine at flip) →
per-band L20-50 scenarios → `enacted:` line in plan output → gate.sh run
owed (bot was live throughout 4a) → derive enacted markers by identity
against the enacted object, not by re-deriving the flip condition
(player.py:563/:1263) → `enacted_engine` as Literal["legacy","tree"] →
flag-on soak caveat: sticky anchor feeds the TREE root into legacy
decide's last_chosen_root, biasing record["strategy"] toward agreement —
and (Phase-3 note) sticky under-counts flag-OFF agreement; read
divergent-pair CLASSES, never the headline %, in the data review.

**Phase 3 amendment (2026-07-07, live shadow review):** 6h/527 dual
cycles: legacy spent 263 cycles (50%) on the small_health_potion root (the
churn loop, measured); 264 cycles ReachCharLevel(14)!=(20) are
behavior-class agreement (repr-only). FINDING: tree picked gear 0×527 —
the adequacy signal's empty-armor-slot leg read a full COPPER set at L14
as adequate. FIX: adequacy leg replaced with tier-aware
`has_structural_upgrade` (positive-gain structural candidate reachable ⇒
NOT adequate; empty slot = gain-from-zero special case, subsumed).
Utility/potion targets still excluded from the break (churn stays dead);
when the gear branch fires with utility unstocked, the weighted potion can
outrank small structural gains — bounded by the provisioned-skip, tuned
via POTION_TYPE_WEIGHTS at Phase 4. Bot restart required for the corrected
live shadow.

**Phase 3 SHIPPED (2026-07-07):** commits cb62e5ba (adequacy parameter +
XP-arm gear-fallback retention + _ordered[0]==core-pick assert — all three
Phase-2 flags closed), 71aa2861 (shadow wiring: decide_tree computed every
cycle beside legacy, stashed, traced as record["tree"]; PlanReport.
tree_decision; legacy flow verified byte-identical), 31931812 (`plan
--tree` full descent block + always-on compact `tree: {root} {==|!=}`
line), 492ec91d (`stats summary --trace-file <jsonl>` divergence section —
dual cycles, agreement %, branch counts, top-5 divergent pairs; TraceStats
reads the learning DB, so divergence aggregates the trace JSONL via
analyze_tree_divergence), 6375ff9e (TUI: CycleSnapshot tree fields +
` tree:{==|!=}` log-line suffix — the TUI consumes the live observer
queue, not trace files). Adequacy signal live = winnable-band-target ∧
no-empty-armor-slot. LIVE-REVIEW CHECKLIST: run the bot with --trace,
then `artifactsmmo stats summary --trace-file play-trace-Robby.jsonl`
(divergence section) and `artifactsmmo plan Robby --tree`; review
agreement by scenario class before the Phase-4 flip.

**Phase 2 SHIPPED (2026-07-06):** commits b978bc88 (pure cores:
milestone/branch/argmax/potion-weights, exact Fractions), 35163ed5
(Formal/ProgressionTree.lean — 10 theorems core-only, zero sorry/axioms;
gearTargetPick_perm deferred with docstring rationale), eca0fed9
(decide_tree assembly, unwired; per-scenario pins: gear-first everywhere
below adequacy — l1_fresh → copper_dagger via copper_ore step), 249cf05c
(PROGRESSION_TREE_MUTATIONS, 5/5 unit-killed). Phase-2 interim decisions:
adequacy = candidate-set-empty (E-tower refinement in Phase 3); utility
candidates map to hp_restore family only; zero-gain utility trigger +
gd/objective same-snapshot contract flagged for Phase-3 wiring; ALSO
Phase-3 must revisit decide_tree's XP arm: under the crude adequacy
definition band_adequate implies zero candidates, so the XP arm carries no
gear fallbacks — when the E-tower adequacy signal replaces it, XP can fire
WITH candidates and the current arm would silently drop them (final-review
finding); and harden the display/fallback ordering with an assertion that
_ordered(candidates)[0] equals the proven core's pick.

**Phase 1 SHIPPED (2026-07-06):** commits b626ac4f (from_cache_bundle +
755KB fixture), 9657a3e9 (seed_offline + plan_from_state split), 4084a89c
(ScenarioCharacter + registry: l1_fresh, l8_overstocked,
l10_copper_adequate, l10_weapon_upgrade, l3_low_hp, l12_taskgated_bag),
8013d9e1 (goldens: 8 pass + 4 xfails = the tree's acceptance set —
l1_fresh/l10_copper_adequate potion-root defect, l10_weapon_upgrade
gear-underrank, l12_taskgated_bag bag-root loss), 8a728723
(`plan --scenario` CLI). Calibration findings: the empty-utility potion
root wins even at L1; l8_overstocked legitimately resolves to
DiscardOverstock at 96% pressure (pressure-ladder design, golden
corrected).

Deferred out of Phase 1 (not gaps — later phases are the right place):
per-band trunk scenarios (L20/L30/L40/L50) deferred to Phase 2/3, since
higher-band gear states are best authored alongside the tree's adequacy
signal rather than against the current flat ranking; the `--scenario
<file>` form (an ad-hoc scenario loaded from disk) deferred — Phase 1
ships names-only against the `SCENARIOS` registry, and `--bundle`
overrides the GameData catalog for a named scenario, not the scenario
itself; the potion-weight-table golden deferred to Phase 2, since the
table it would pin doesn't exist yet.

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
