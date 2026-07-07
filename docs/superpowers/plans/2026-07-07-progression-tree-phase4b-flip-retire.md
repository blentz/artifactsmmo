# Progression Tree — Phase 4b: Flip + Retire the Flat Ranking

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The tree becomes THE decision engine — `StrategyEngine.decide` delegates to `decide_tree`; the flat scalar ranking (priors, marginals, balancing, blend wiring, skill roots, urgency constants) is DELETED; formal artifacts rebound/retired; Phase-1 goldens promoted to tree semantics; TUI renders the descent. User approved the flip on live shadow data (865 dual cycles: churn measured at 50% of legacy replans; corrected adequacy → tree holds fire_bow steadily). Spec: `docs/superpowers/specs/2026-07-06-progression-tree-design.md` (Phase 4b REQUIRED checklist).

**Architecture:** One decision path end-to-end: player computes `band_adequate` and calls `decide(...)`, which is now a thin wrapper over `decide_tree` (+ servability demotion). The dual-shadow apparatus (flag, `record["tree"]`, `PlanReport.tree_decision`/`enacted_engine`, TUI `tree:` suffix, `plan --tree`) retires — `record["strategy"]` carries the enacted (tree) decision in the same `to_trace` shape, so trace consumers and the cycle lockstep keep working. The `stats` divergence section stays (reads historical dual traces; omits itself on new ones).

**Tech Stack:** Python 3.13 (`uv`), pytest, Lean 4 (retirements only — no new proofs), formal/diff mutation gate.

## Global Constraints (spec + repo rules)

- Zero-vacuousness: retired theorems/mutants/diff harnesses are DELETED, never weakened. Every retained proof must still be non-vacuous.
- Arbiter (`select_pure`, o54 SELECT differential, DecideKey ladder), guards/means, planner: UNTOUCHED. The tree replaces `decide()` internals only.
- Trace shape: `record["strategy"]` keeps its exact `StrategyDecision.to_trace()` shape (cycle lockstep depends on it). `record["gear"]`, `record["fires"]` untouched.
- Servability demotion MUST survive the cutover: an unservable chosen step falls through the tree's fallback list (in order) to the first servable step, exactly filling legacy `decide()`'s `step_servable` role — dropping it risks the plannability livelocks the flag exists to prevent.
- Sticky: decide-level sticky SCORING dies with the ranking (tree is deterministic — 326 consecutive identical picks in shadow). Arbiter-level commitment (`_update_sticky_anchor`, objective-committed arbitration, zombie release) survives untouched. `last_chosen_root` param may remain accepted-but-unused for interface stability ONLY if a caller still passes it; otherwise remove it.
- The bot is LIVE flag-off during implementation: no gate.sh/mutate.py. The FINAL task runs the full gate and REQUIRES the bot down — coordinate with the user (post-4b restart enacts the tree by default, so the stop is natural).
- TDD for behavior changes; deletions verified by grep-zero + suite green; 100% coverage (deletions SHRINK the denominator — dead-code coverage exemptions must all disappear); mypy strict; no inline imports; never catch Exception.

---

### Task 1: `decide()` cutover — tree is the engine, servability survives

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/progression_tree.py` (`decide_tree` gains `step_servable`)
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (`decide` at :708 rewritten as thin delegate; body's ranking pipeline abandoned in place — deleted in Task 2)
- Modify: `src/artifactsmmo_cli/ai/player.py` (both decide sites: single decision; `_compute_tree_shadow`/`_tree_band_adequate` fold into the main path; flip conditional, `_last_tree_decision`, `_last_enacted_decision` collapse to `_last_decision`)
- Test: `tests/test_ai/test_progression_tree.py`, `tests/test_ai/scenarios/test_plan_from_state.py` (extend/adjust)

**Interfaces:**
- `decide_tree(state, game_data, objective, band_adequate=False, step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None)` — when the chosen (root, step) is unservable, walk `fallback_roots/steps` pairs in order to the first servable pair; demoted pairs stay in the fallback lists after the promoted one; all-unservable keeps the original choice (arbiter's doomed-memo handles it, as today).
- `StrategyEngine.decide(state, game_data, history=None, combat_monster=None, last_chosen_root=None, step_servable=None, band_adequate=False) -> StrategyDecision` — returns `decide_tree(state, game_data, self._objective... , band_adequate, step_servable)`. `history`/`combat_monster`/`last_chosen_root` accepted for callsite stability this task; Task 2 prunes what ends up unused after callers adjust.
- Player: `decision = self._strategy.decide(..., band_adequate=self._tree_band_adequate(), step_servable=...)` at both sites; enacted==decision; flag/`progression_tree` param and CLI flags REMOVED (play.py, plan.py); `PlanReport.tree_decision`/`enacted_engine` removed; `record["enacted"]`/`record["tree"]` removed; `_emit_trace`'s `record["strategy"]` = the (tree) decision — shape unchanged.

- [ ] Step 1: failing tests — servability demotion unit tests on `decide_tree` (servable fallback promoted; all-unservable keeps choice); plan_from_state returns tree decision as `report.decision` (no tree_decision attr).
- [ ] Step 2: implement; adjust existing flag-era tests (Task-1-4a tests for enacted_engine/record["enacted"] are DELETED with the feature, their intent now covered by the goldens).
- [ ] Step 3: full suite green (expect Phase-1 legacy goldens + strict xfails to FAIL/XPASS — mark the goldens module for Task 4 by temporarily asserting nothing? NO: sequence Task 4's golden rewrite FIRST if the suite can't stay green — the executor may reorder Task 4 before Task 1 commits if needed; otherwise land them in ONE commit). Pre-commit must pass — if goldens block, fold Task 4's golden changes into this commit and say so.
- [ ] Step 4: commit — `feat(flip)!: progression tree is the decision engine — flat ranking bypassed`

---

### Task 2: Delete the flat ranking

**Files:**
- Modify: `src/artifactsmmo_cli/ai/tiers/strategy.py` (~785 → expect roughly half)
- Modify/audit: `src/artifactsmmo_cli/ai/tiers/objective.py` (skill-root generation), `strategy_blend.py` usage, player.py dead params
- Test: `tests/test_ai/test_tiers_strategy.py` and siblings (delete tests of deleted code)

**Deletion list (verify each has no remaining callers before deleting; grep src/ AND formal/ AND tests/):**
- Constants: `PRIOR_*` (all 7), `SKILL_GAP_PER_LEVEL`, `SKILL_GAP_CAP`, `CHAR_GAP_PER_LEVEL`, `CHAR_GAP_PER_LEVEL_GEARED`, `CHAR_CAPSTONE_SCALE`, `PRIOR_RELEVANT_TOOL`, `EMPTY_SLOT_URGENCY`, `BAG_SLOT_URGENCY` (+ any sibling scoring constants in the :56-190 block).
- Methods: `_base_prior`, `_has_empty_armor_slot`, `_equip_gain`, `_marginal`, `_balancing`, `_relevant_tool_value`, `_value`, `_learned_blend`, `_gear_slot`, `_root_slot`, `_combat_gear_slots`, and the old `decide` body's ranking/candidate loop.
- `strategy_blend` imports in strategy.py (`blend_weight`, `learned_blend`) — if `strategy_blend.py` loses all callers, delete the module + its tests; if learning-store write paths still use it, keep the module and note it.
- Standalone skill-root generation: wherever `ReachSkillLevel` roots enter `objective_roots` (objective.py) — remove ONLY the standalone-root emission; `ReachSkillLevel` as a STEP/prereq (skill_target_curve, actionable_step decomposition) is load-bearing and stays.
- KEEP: `root_category`, `desired_state_of`, `actionable_step`, `unmet_closure_size`/`root_cost`/`is_reachable`/`_producible` IF still referenced (audit — mapper/goals use several); `RootScore`, `StrategyDecision`, `to_trace`.
- [ ] Verify: `grep -rn "EMPTY_SLOT_URGENCY\|_base_prior\|CHAR_GAP\|_learned_blend" src/ tests/ formal/` → zero hits (or documented keeps); full suite green; coverage 100% with a SMALLER total.
- [ ] Commit — `refactor(flip)!: delete the flat scalar ranking (constants, pipeline, skill roots)`

---

### Task 3: Formal retire + rebind

**Files:**
- Modify: `formal/diff/mutate.py` (delete groups anchored to deleted code — audit ALL 24 STRATEGY-related hits + BAG_SLOT/urgency/marginal groups; keep groups anchoring retained helpers)
- Audit/modify: `formal/Formal/StickySelect.lean` (retire SCORING theorems; commitment/`lower_band_precedes` proofs stay), any strategy-ranking traversal diff harnesses in `formal/diff/` (delete whole harness files whose subject died; adjust gate.sh --ignore ONLY with justification per the gate-diff-completeness rule)
- Run: `uv run python scripts/gen_proof_concept_index.py` (module deletions change the index)
- KEEP UNTOUCHED: o54 SELECT differential, DecideKey ladder, ProductionLadder, ProgressionTree.lean + PROGRESSION_TREE_MUTATIONS.
- [ ] Verify: `cd formal && lake build` green, zero sorry; every deleted mutant's anchor is genuinely gone from src (no orphaned "(stale)" risk); `grep -rn "sorry" formal/Formal/` clean.
- [ ] Commit — `chore(formal)!: retire flat-ranking proofs and mutants; index regen`

---

### Task 4: Goldens promotion + scenario reconciliation

**Files:**
- Rewrite: `tests/test_ai/scenarios/test_goldens.py` — tree expectations become THE goldens (content from `test_goldens_tree.py`, minus the flag plumbing); `XFAIL_TODAY`, `CURRENT_TODAY`, `test_scenario_current_behavior_pinned` DELETED (their delete-at-flip docstrings say exactly this).
- Delete: `tests/test_ai/scenarios/test_goldens_tree.py` (merged).
- Audit: `plan --scenario` output tests (compact tree line gone), any test asserting legacy ranking output in plan CLI.
- [ ] Verify: suite green with ZERO xfails remaining in scenarios (the acceptance set has been promoted); liveness tests intact.
- [ ] Commit — `test(flip)!: goldens promoted to tree semantics; legacy pins retired`

---

### Task 5: TUI descent + display cleanup

**Files:**
- Modify: `src/artifactsmmo_cli/tui/widgets/log_pane.py` (remove ` tree:{==|!=}` suffix — always `==` now), `src/artifactsmmo_cli/ai/cycle_snapshot.py` (remove `tree_active`/`tree_chosen_root`), player `_notify_observer` (single decision feeds `chosen_root`, `strategy_ranking`, `plan_tree` — panes automatically enacted-fed now), plan.py `_print_report` (drop compact tree line + `--tree` flag + `_print_tree_block`; the ranking block now naturally prints the descent rows: trunk first, then gear candidates).
- The descent IS the ranking rows (Phase-2 display parity design) — verify the plan output + TUI Tree/plan pane render sensibly with the tree's rows; adjust the plan screen's "root ranking (top 8)" header to "descent" if trivial, else leave.
- Test: adjust log_pane/plan-command/TUI tests for removed surfaces.
- [ ] Commit — `feat(tui)!: single-engine display — descent rendering, shadow chrome removed`

---

### Follow-ups promoted from Task-3 review (post-4b backlog, not this plan)

- Tree-native arming/anti-zombie liveness re-proof: GatedArming +
  no_infinite_zombie_below_fifty retired with the sticky machinery; the L50
  capstone is verified intact (ai_reaches_fifty hypothesis-free), but if the
  reach-50 narrative wants an arming story over the TREE's decide path, it
  needs a new proof over decide_tree/servable-promotion.
- DecideKey dispatcher half: add a mechanical repr-vs-dispatch assert
  (goal_repr_of_guard(k) vs map_guard(k) actual goal) to make the kept
  lockstep binding mechanical rather than conventional.
- chosen_step_alive (write-only post-flip) + objective_roots re-export:
  retire or re-consume in Task 5 or the backlog.

### Task 6: Wrap-up + THE GATE (bot must be down)

- [ ] Spec: "Phase 4b SHIPPED — THE FLIP" note (commits; what died; sticky decision recorded: decide-level scoring retired, arbiter commitment retained; weight table = the remaining tuning surface).
- [ ] Memory + MEMORY.md updates.
- [ ] Coordinate: user stops bot → `./formal/gate.sh` end-to-end (expect large mutant-count drop; PROOF_CONCEPT index fresh) → push → user restarts bot (now on the tree by default) → watch first cycles (`plan Robby` + trace tail).
