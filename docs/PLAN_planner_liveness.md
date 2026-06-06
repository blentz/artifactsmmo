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

- [ ] **FIX BROKEN MODULE: `formal/Formal/RecycleProtection.lean`.** Clean `lake
      build` (gate part a) is RED at HEAD — `linter.unusedSimpArgs` fires on
      load-bearing `simp [h] at hNot2` / `simp [hF1]` contradiction patterns
      (lines 113, 122). Cache-masked at commit 842f4a5 (the committer had stale
      `.olean`s, so the lint never ran). The hypotheses ARE used (they supply the
      `decide`-reducing rewrite), so this is a linter false-positive at toolchain
      v4.30.0 — the right fix is `set_option linter.unusedSimpArgs false` scoped to
      those proofs (or restructure to `exact`). Blocks the full formal gate; my
      `PlannerDepthBound` module itself builds + is axiom-clean independently.

- [ ] **CLOSE PRE-EXISTING COVERAGE GAPS.** `uv run pytest` is at 98.80% (126
      lines, `--cov-fail-under=100` RED) at HEAD — independent of this work (my
      changes are coverage-neutral: +34 statements, all covered, 126 missing
      before AND after). Pre-existing gaps include `commands/stats.py` 75%
      (66-72, 103, 112-130, 148-158, 174-183, 230-231, 266-271), `ai/craft_relief.py`
      89% (42,47,71,91), `ai/goals/craft_relief.py` (40,49), `ai/tiers/means.py`
      90% (126-134), `ai/equipment/scoring.py` 93%, `ai/goals/level_skill.py`
      (the pre-existing `if not recipe: continue`), `ai/strategy_driver.py`
      (65,73,92,107,113,190-193 + the select fall-through), `ai/player.py`,
      `ai/inventory_caps.py`, `ai/learning/store.py`, `ai/trace_stats.py`, etc.
      Likely env-gated (network/TOKEN) command tests not running here. Audit
      whether these are genuinely uncovered or just not exercised in this
      environment, then add tests (or justified carve-outs) to restore the 100%
      gate.

## Open questions / risks

- LevelSkill(weaponcrafting) has `max_depth=100` and plan ~67 (<100) but still
  times out from **search WIDTH**, not depth. The depth gate will NOT catch it.
  Width is a separate problem (tiered planning budget) — out of scope for this
  plan; flag remaining cost after the depth gate lands.
- `TaskExchange` timeout cause not yet root-caused; verify post-gate.
- Decide whether GatherMaterialsGoal (which already scales max_depth) needs the
  same gate (likely not — it sets `max_depth = max(100, units*100)`).
