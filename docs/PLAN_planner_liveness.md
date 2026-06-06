# PLAN: Planner depth-bound liveness + reachability gate

## Origin

User-reported "AI player stuck waiting for first cycle." Root-caused 2026-06-06.
The arbiter walks candidate goals, calling `GOAPPlanner.plan` once per goal, each
bounded by `_SEARCH_BUDGET_SECONDS = 90`. Several candidates per cycle are
**structurally unreachable** yet still consume the full 90s before returning
`no_plan`. Robby's first cycle: `UpgradeEquipment` + 8×`LevelSkill` + `TaskExchange`
each timing out ≈ 90s ⇒ ~12 min "stuck".

Two fixes already landed this session (separate, verified):
- **Command-nesting** (`play <name>` was `Missing command`): `main.py`/`play.py`.
- **LevelSkill closure regression** (`relevant_actions` now level-bounds the
  recipe closure): `level_skill.py`. Measured: jewelrycrafting/fishing 90s → 0.0s.

A curve-based `is_plannable` gate was attempted and **reverted as fake-green**
(the API seeds `SkillXpCurve` from `CharacterSchema.<skill>_max_xp`, so its
condition `required_xp(current)==0` never fires in production).

## The provable bug this plan targets

`planner.py`:
- L118 `if node.depth >= max_depth: continue` prunes beyond `max_depth`.
- Each expansion pushes `depth+1`, `plan=[*plan, action]` ⇒ `len(plan) == depth`.

**Theorem (load-bearing):** the planner never returns a plan longer than
`max_depth`. Formally `∀ inputs, (planner.plan ...).length ≤ goal.max_depth`.

**Corollary (reachability):** if every satisfying plan for a goal has length
`> max_depth`, the planner provably returns `[]`. Running such a search is pure
waste (up to 90s).

**The bug:** `UpgradeEquipmentGoal` inherits base `max_depth = 15`, but a
from-scratch craftable target needs far more steps. copper_boots recipe =
8×copper_bar, copper_bar = 10×copper_ore ⇒ ≥ 80 gather actions (gather mints **+1**
per action, proven in `gather_apply_core.gather_apply_pure`). 80 ≫ 15 ⇒ provably
unreachable, guaranteed `no_plan`, every cycle, ~90s burned.

**Sound lower bound on plan length** (yield-independent, since each gather = +1):
```
minGathers(target, state) =
  Σ over transitive RAW leaves L of  max(0, neededUnits(L) − inv(L) − bank(L))
```
Each raw unit requires ≥1 GatherAction (or 1 Withdraw, already subtracted via
bank), and crafts only ADD steps, so `minGathers ≤ minPlanLength`. Therefore
`minGathers > max_depth ⇒ unreachable`, and skipping is **sound** (never skips a
goal the planner could have solved).

## Proof boundary (Phase 0)

Core pure functions worth proving:
1. `depthBoundedSearch` — computable Lean model of the prune; theorem
   `plan_length_le_max_depth` (role: **safety-invariant**).
2. `minGathers` recipe-closure lower bound; theorem
   `minGathers_le_planLength` over a modeled valid plan (role: **lower-bound /
   soundness**), giving `gate_sound`: `minGathers > maxDepth → plannerReturns []`.

Lean core only (no mathlib), matching `PlannerAdmissibility.lean` precedent.

## Phases

- [x] Phase 0 — boundary + bug pinned (this doc).
- [ ] Phase 1 — `formal/Formal/PlannerDepthBound.lean`: model + the two theorems,
      kernel-checked, no sorry/native_decide/custom-axiom. Wire into
      `Manifest.lean` + `Contracts.lean`.
- [ ] Phase 2 — implement reachability gate honestly:
      - reintroduce `Goal.is_plannable(state, game_data, history) -> bool` (default True),
      - arbiter `_plans` skips when False (records skipped attempt),
      - `UpgradeEquipmentGoal.is_plannable`: False when `minGathers(target) > max_depth`
        and target not owned. Extract `minGathers` into a pure `*_core` module the
        differential test calls.
      - TDD throughout.
- [ ] Phase 3 — differential (oracle on the `minGathers`/depth core) + mutation.
- [ ] Phase 4 — adversarial review: confirm the theorem talks about reachable
      program states; confirm the gate condition is the SAME function as the Lean
      `minGathers` (no inlined surrogate).
- [ ] Phase 5 — unit coverage for new code paths (repo enforces 100%).

## Follow-up TODOs

- [x] **DONE 2026-06-06 (branch `chore/followups-formal-gate-coverage`) — formal
      gate fully restored.** RecycleProtection's `linter.unusedSimpArgs` issue was
      not a mere false-positive: a clean rebuild surfaced real `unsolved goals`
      (the module was a Mathlib-importing ORPHAN, never compiled by the default
      build, so its errors were cache-masked). Fixed by restructuring those proofs
      to explicit `simp only`/contrapositive forms (commit 07a2a0c). The clean run
      then exposed a larger pre-existing issue: **19 `Formal/` safety modules
      imported Mathlib while living outside `Formal/Liveness/` (violating the
      core-only quarantine) and weren't imported into `Formal.lean` (orphan
      check)**. Per user decision, all 19 were converted to CORE-ONLY
      (`linarith`→`omega`, Mathlib List/min lemmas → core; statements
      byte-identical, adversarially verified; 54 theorems now axiom-free) and wired
      into `Formal.lean`. Final gate: `lake build` GREEN (6099 jobs); orphan check
      OK (113 modules); no-sorry OK; cross-namespace Mathlib-leak OK; safety +
      liveness axiom checks OK.
      - Minor residual follow-up: the 19 de-Mathlib'd modules are not yet listed in
        `Formal/Audit.lean`'s by-name axiom roster (the safety gate covers them via
        the build + leak check, and they were spot-`#print axioms`-verified clean,
        but registering them in Audit.lean would audit each by name).

- [x] **DONE 2026-06-06 — coverage restored to 100%.** `uv run pytest` now reports
      **100.00%** (0 missing), 2751 tests, via ~50 real behavior-asserting tests
      across the previously-uncovered files (stats, craft_relief, means, scoring,
      goals, inventory_caps, learning/store, trace_stats, strategy_driver, player,
      actions, arbiter, blockers). One justified `# pragma: no cover`
      (`equipment/scoring.py:182` — an unreachable `_claim(None)` guard). A
      hash-seed-flaky scoring test was made deterministic. None required live
      network/TOKEN.

## Open questions / risks

- **[LANDED 2026-06-06]** LevelSkill(weaponcrafting) has `max_depth=100` and
  plan ~67 (<100) but still times out from **search WIDTH**, not depth. The
  depth gate alone does NOT catch it. This was addressed by the **tiered-budget
  + gear-prioritization** feature on branch `fix/planner-depth-bound-stuck-cycle`
  (spec: `docs/superpowers/specs/2026-06-06-tiered-budget-gear-prioritization-design.md`,
  plan: `docs/superpowers/plans/2026-06-06-tiered-budget-gear-prioritization.md`).
  The feature adds: (a) a `DoomedMemo` that records width-unfindable goals after
  the first timeout so they are skipped on subsequent cycles until the
  plannability signature (char level + skill levels) changes; (b) a tiered
  `CHEAP_BUDGET_SECONDS=1.0` first pass so fast goals win immediately without
  burning 90s; (c) a `GearLatch` (GEAR_REVIEW guard) that triggers
  UpgradeEquipmentGoal when a better piece is craftable/available, with the
  commitment persisted across cycles. Width stall resolved; depth gate + memo
  together make first-cycle planning bounded.
- `TaskExchange` timeout cause not yet root-caused; verify post-gate.
- Decide whether GatherMaterialsGoal (which already scales max_depth) needs the
  same gate (likely not — it sets `max_depth = max(100, units*100)`).
