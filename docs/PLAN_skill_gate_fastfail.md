# PLAN: Skill-gate fast-fail + cheap-pass no-plan memo

**Status:** in progress — proof expansion (DoomedMemo + is_plannable)
**Branch:** `feat/prove-fight-drops` (or a fresh branch off it)
**Trigger:** Robby pegged 99% CPU 2026-06-15. Diagnosis below.

---

## 0. CORRECTION (2026-06-15, after game-data + code verification)

Initial diagnosis blamed a missing skill-gate fast-fail. WRONG, corrected:

- `GatherMaterialsGoal.is_plannable` (gathering.py:316-335) **already implements**
  the terminal skill-gate fast-fail — added 2026-06-11 for this exact feather_coat
  case. It is currently **UNPROVEN** (no formal/ component).
- Recipe chain (game-data verified): feather_coat←gearcrafting 5 (feather×5 +
  ash_plank×2); feather←chicken drop; ash_plank←woodcutting **1**; ash_wood←gathered.
  **No intermediate is gated above the bot's skills.** So a closure-wide gate check
  would NOT have fired on 06-15 either.
- On 06-15 `is_plannable` returned True (237K nodes prove the gate was *passed*) ⇒
  gearcrafting was **≥5, gate OPEN**. feather_coat was doomed for a DEEPER reason
  (most likely inventory-cap interleaving: 25 raw mats vs 20 free slots → no
  simultaneously-satisfying state → 237K-node exhaustion, plan_len 0).
- **The actual CPU-peg cause is Fix B alone:** `try_plan_cheap` searches feather_coat
  (expensive, genuinely doomed) every cycle and NEVER `mark`s it (only `try_plan_full`
  marks, and it never runs because the cheap pass succeeds via iron_bar). The
  exponential-backoff `DoomedMemo` stays starved → re-explosion forever.

**Proof-expansion scope chosen (user, "Both"):** prove BOTH the DoomedMemo backoff
state machine (the real fix + the requested exponential backoff) AND the existing
terminal is_plannable skill-gate soundness. See §9.

---

## 9. FORMAL EXPANSION — theorem roles per component

Existing relevant proofs: `TieredSelection.lean` proves `memo_skip_sound` /
`wait_only_when_no_full` etc. but treats `skip` as an ABSTRACT predicate with the
no-plan contract as a hypothesis. `PlannerDepthBound.lean` proves length-based
unplannability (`reachable_not_satisfying_when_lb_exceeds_depth`). Neither models
the concrete backoff arithmetic nor the skill-gate predicate. Two NEW core-only
components (no Mathlib — safety/decision):

### Component: `DoomedMemo.lean` (mirrors doomed_memo.py + plannability_signature.py)
Computable defs: `ttl base maxR failures`, `marked` (failure-count update),
`isDoomed sig0 setAt failures sig cycle`. Theorem roles:
- **base** — `ttl b m 1 = min b m` (first failure = base window).
- **geometric** — `ttl b m (n+1)` uncapped doubles: `b <<< n = 2 * (b <<< (n-1))` for n≥1; window grows ×2 per consecutive failure until cap. (the requested "exponential backoff")
- **cap** — `ttl b m f ≤ m` (∀ f). Window never exceeds max_retry.
- **monotone** — `f1 ≤ f2 → ttl b m f1 ≤ ttl b m f2`.
- **sig-invalidates** — `sig ≠ sig0 → isDoomed … = false` (new plannability ⇒ re-probe; soundness).
- **window** — `sig = sig0 → (isDoomed = true ↔ cycle - setAt < ttl …)`.
- **eventually-retries (liveness)** — `cycle - setAt ≥ ttl … → isDoomed = false` (never a permanent skip).
- **escalates** — consecutive same-sig `mark` increments failures ⇒ ttl non-decreasing.

### Component: `SkillGateFastFail.lean` (mirrors GatherMaterialsGoal.is_plannable)
Computable def `isPlannable targetInNeeded hasCraftGate curLevel craftLevel owned needed`.
Abstract acquisition model: target is craft-acquired; the only owned-increasing
action is the gated `craft` (requires `curLevel ≥ craftLevel`); skill constant
in-plan (the invariant `CraftAction.is_applicable` relies on — gates on base
`state.skills`, not projected xp; verified crafting.py:46-47). Theorem roles:
- **gate-blocks-craft** — `curLevel < craftLevel → craft not applicable` (∀ state on plan).
- **owned-invariant** — `curLevel < craftLevel ∧ owned0 < needed → ∀ action seq, ownedₙ < needed` (craft never fires ⇒ owned never rises).
- **soundness (headline)** — `isPlannable = false → no satisfying plan exists` (goal `owned ≥ needed` unreachable). i.e. the fast-fail NEVER prunes a reachable goal.
- **completeness-guard / non-vacuity** — witnesses: gate-open ⇒ isPlannable True; already-owned ⇒ True; materials-only (target∉needed) ⇒ True (regression: don't prune the feather raw-drop case).

### Gate wiring (both components)
- Extract pure cores: `doomed_memo.py` ttl/isDoomed already pure (call directly);
  add `is_plannable_core(target_in_needed, has_gate, cur, req, owned, needed)` pure
  fn in gathering.py (or a `*_core.py`) the diff test calls.
- `Oracle.lean`: add `runDoomedMemo` + `runSkillGateFastFail` dispatch arms.
- `formal/diff/`: `test_doomed_memo_diff.py`, `test_skill_gate_fastfail_diff.py`
  (Hypothesis over random failures/cycles/sigs and gate/owned/level tuples).
- `mutate.py`: `DOOMED_MEMO_MUTATIONS` (drop backoff, drop sig-check, ttl off-by-one),
  `IS_PLANNABLE_MUTATIONS` (drop gate, `<` vs `>` on level, drop owned-fallback).
- `Manifest.lean`: `#check @` each role theorem. `Contracts.lean`: exact-statement
  type-pins per role.
- `README.md`: two new roster rows.
- Code change (the actual fix): `try_plan_cheap` marks no-plan non-guard failures
  into `_memo` (TDD: tests/.../test_strategy_driver.py).

---

## 1. Problem (evidence)

`play Robby` burned 99% CPU continuously while limping forward one
`Gather(iron_rocks)` per ~66s cooldown. py-spy wall-clock profile (1598 samples)
landed 100% in `planner.plan` GOAP A* search. Trace
`play-trace-Robby-20260615-090149.jsonl`, every cycle 553-559:

```
goals_tried[0]: GatherMaterials(feather_coat, {feather_coat:1})
                nodes: ~236876   depth: 100   timed_out: false   plan_len: 0
goals_tried[last]: GatherMaterials(iron_bar, {iron_bar:4})  -> plan_len 19  (succeeds)
```

`feather_coat.craft` = gearcrafting **level 5**, feather×5 + ash_plank×2. `feather`
itself is plannable now (chicken drop, made plannable by commit c9c0231). But the
character's gearcrafting is below 5 (`strategy.chosen_root = ReachSkillLevel(gearcrafting, 10)`),
so terminal `Craft(feather_coat)` is inapplicable → goal unsatisfiable. Because the
feather-gather subspace branches richly (Fight/Gather/Move) and `GatherMaterials`
runs at `max_depth 100`, the unsatisfiable search exhausts ~237K WorldState
`_replace` clones (the 1MB-mmap flood) every cycle. Not a timeout — it fully
explores a huge dead space, returns `[]`, then the walk falls through to iron_bar
and gathers. ~1 useful action/min, CPU pegged in between.

## 2. Why the two EXISTING guards both miss it

The codebase already has both mechanisms this needs. Both have a wiring gap.

### Defect A — `GatherMaterialsGoal` lacks a skill-gate `is_plannable`
`strategy_driver._plans` line 662 already calls `goal.is_plannable(state, game_data, history)`
as a free pre-plan gate that returns `[]` at `nodes:0`.
`UpgradeEquipmentGoal.is_plannable` (`goals/progression.py:100-138`) already
implements the exact skill-gate predicate:

```python
stats = game_data.item_stats(item)
if stats is not None and stats.crafting_skill and \
   state.skills.get(stats.crafting_skill, 1) < stats.crafting_level:
    return False   # craft gated above current level => unplannable this cycle
```

`GatherMaterialsGoal` (`goals/gathering.py`) never overrides `is_plannable`, so the
base default (returns True) lets `feather_coat` through to the 237K-node search.

### Defect B — the cheap pass never feeds the doomed-memo
`strategy_driver._arbitrate` lines 975-988:

```python
def try_plan_cheap(goal):
    if _skip(goal): return []                 # checks is_doomed, but...
    return self._plans(goal, ..., cheap=True) # ...NEVER marks on failure

def try_plan_full(goal):
    if _skip(goal): return []
    plan = self._plans(goal, ..., cheap=False)
    if not plan and repr(goal) not in guard_reprs:
        self._memo.mark(repr(goal), state, self._cycle)   # only the FULL pass marks
    else:
        self._memo.clear(repr(goal))
    return plan
```

The cheap pass (line 994) runs first and **succeeds every cycle** (iron_bar plans),
so the full pass (line 999) is never reached. The expensive dead `feather_coat`
search happens in the cheap pass, which never `mark`s it → `DoomedMemo` stays empty
for it → no backoff ever engages. The exponential backoff the user wants
(`doomed_memo.py`: TTL 20→40→80→160 per consecutive failure, keyed by `repr(goal)`,
invalidated only when `plannability_signature = (char level, sorted skill levels)`
changes) is fully built and correct — it is simply starved of input on the hot path.

## 3. The fix (two surgical changes)

### Fix A (primary): `GatherMaterialsGoal.is_plannable` skill-gate
Add an `is_plannable` override to `goals/gathering.py` that returns `False` when any
item in the goal's recipe closure has `crafting_skill` whose required `crafting_level`
exceeds the current `state.skills` level. Reuse the `UpgradeEquipmentGoal` predicate;
iterate over `recipe_closure(...)` items (closure already computed for
`relevant_actions`, `recipe_closure.py:114`). Cuts `feather_coat` from 237K nodes to
`nodes:0` at the gate.

### Fix B (defense-in-depth): cheap pass marks no-plan failures
Make `try_plan_cheap` record failures into the memo, same as `try_plan_full`:

```python
def try_plan_cheap(goal):
    if _skip(goal): return []
    plan = self._plans(goal, ..., cheap=True)
    if not plan and repr(goal) not in guard_reprs:
        self._memo.mark(repr(goal), state, self._cycle)
    else:
        self._memo.clear(goal)   # repr(goal)
    return plan
```

This activates the existing exponential backoff for ANY width-unfindable goal the
fast-fail doesn't catch (not just skill-gated ones), which is precisely the
"retry failed goals only every N plans, N growing exponentially" behavior requested.
Fix A makes feather_coat cheap; Fix B ensures even a goal that is genuinely
expensive-and-unfindable (no static gate) is searched once then backed off.

## 4. Soundness

A craft gated above current skill level is genuinely unreachable **this cycle**: the
planner does NOT level skills mid-plan to unlock a craft. Confirmed:
`CraftAction.is_applicable` (`actions/crafting.py:46-47`) gates on `state.skills`
(base level), not on `projected_skill_xp_delta`. The existing
`UpgradeEquipmentGoal.is_plannable` already relies on this exact invariant, so Fix A
reuses an already-accepted, already-shipped soundness argument. When the skill levels
up, `plannability_signature` changes → memo invalidates → goal is re-probed. No goal
is permanently abandoned.

## 5. Formal / gate obligations (investigated)

**No Lean proof changes.** Both fixes live OUTSIDE the proven core:
- `ArbiterSelect.selectPure` treats `try_plan` / `is_satisfied` / `is_suppressed`
  as opaque closures — changing what `try_plan_cheap` does (mark on failure) does not
  touch its theorems (`select_pure_guard_wins`, `..._any_plannable_guard_wins`, etc.).
- `PlannerAdmissibility` is downstream of selection; pruning a doomed goal before
  search does not change which plan is returned for goals that ARE planned, so
  admissibility/optimality is untouched.
- `DecideKey` comparator (goal sort order) is unchanged.

**What the gate WILL require** (`formal/gate.sh` parts (d) differential + (c) mutation,
plus CLAUDE.md 100% coverage):
- New `is_plannable` branch and new `mark` branch are mutation targets. Need unit
  tests that KILL mutants of: the skill-gate comparison (`<` vs `<=`, skill lookup),
  and the cheap-pass mark/clear branch.
- Check `formal/diff/` for an existing selection diff test that exercises
  `try_plan_cheap`; if the cheap-pass mark changes any extraction-visible behavior,
  add/extend a diff test. (Investigator: selection closures are opaque to the oracle,
  so likely only Python-side unit + mutation coverage is needed — confirm by running
  `formal/gate.sh` after.)
- Run `formal/gate.sh` serialized (memory: never concurrent with anything importing
  `src`, incl. the bot). `git diff src` after mutate.py.

## 6. Test plan (TDD — write first)

1. `tests/.../test_gathering_goal.py`: `GatherMaterialsGoal(feather_coat)` with a
   fixture where gearcrafting < 5 → `is_plannable(...) is False`; with gearcrafting
   ≥ 5 → `True`. Also `feather` (a drop, no craft gate) → `True` (regression: don't
   over-prune the raw-material case that c9c0231 fixed).
2. Intermediate-gate case: a target whose INTERMEDIATE (not the final item) is
   skill-gated → `is_plannable False` (closure iteration, not just terminal).
3. `tests/.../test_strategy_driver.py`: cheap pass marks a no-plan non-guard goal;
   assert `_memo.is_doomed(repr, state, cycle+1)` True; assert a guard goal is NOT
   marked; assert a successful plan calls `clear`.
4. Mutation: run `formal/diff/mutate.py`; confirm new branches have no surviving
   mutants (refactor stale anchors if mutate.py reports drift — memo: run after ai/
   refactors).
5. Full `formal/gate.sh` green; 0 errors / 0 warnings / 0 skipped / 100% coverage.

## 7. Out of scope / open questions

- `max_depth 100` on GatherMaterials is the sprawl *enabler*; Fix A makes it moot for
  skill-gated goals, so leave max_depth alone unless a non-gated explosion appears.
- Should the arbiter de-rank not-yet-craftable gear upgrades so they don't sit at the
  head of the walk at all? Larger arbitration change; current fix makes their probe
  cheap, which is sufficient. Defer.
- Whether `feather_coat` SHOULD be pursued at all before gearcrafting 5 is a
  goal-ranking question, not a planner-cost question. Defer.

## 8. Risk

Low. Fix A mirrors shipped `UpgradeEquipmentGoal` logic; Fix B mirrors the existing
`try_plan_full` mark. Main risk is over-pruning a genuinely reachable goal — guarded
by regression test 1 (feather raw-drop stays plannable) and the soundness argument in
§4. Both changes are in the decision path → mandatory full gate before merge.
