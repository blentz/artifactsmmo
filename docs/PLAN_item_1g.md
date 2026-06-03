# Item 1g — Reassessment after probe

## Conclusion: both fat axioms are GAME-SPEC, not structural residuals

After examining the axiom shapes against the existing model:

### `accept_cancel_loop_bound` (LIV-003c-A2)
Claims: starting from ANY state, within `(taskPoolFinite+1) * (lowYieldSampleThreshold+1)` cycleStep iterations, phase reaches `.complete`.

This is FALSE in the pure structural model:
- An initial state with no feasible task code may never accept.
- The model has no field tracking "distinct task codes already cancelled" — cancellation rotation is invisible to State.
- The axiom comment explicitly references `Formal.StuckDetector`'s SAFETY-side proof and `game_data.task_codes` as the spec backing.

Discharging structurally requires extending `State` with:
1. `taskCodesSeen : List String` — track cancelled codes.
2. `taskPool : List String` — model the API's task-code pool.
3. `acceptTask` semantics that picks from `taskPool \ taskCodesSeen`.
4. `taskCancel` semantics that adds current code to `taskCodesSeen`.
5. Pigeonhole on `taskCodesSeen.length ≤ taskPool.length`.

That's a **major model extension** (~600 LOC, multi-session), and it adds state fields that production tracks implicitly via the server's task assignment. The work is real, but it's modeling, not pure proof composition.

### `lifecycle_progress_from_bounds` (LIV-003-bridge)
Claims: under trajectory hypotheses + `level < 50`, ∃ k, level advances.

Structurally tractable PROVIDED `accept_cancel_loop_bound` is available — that's the strategy in Item 1f's docstring. The bridge IS a composition residual: 1f's `bounded_plan_grants_level_when_threshold` + accept_cancel_loop_bound + arithmetic induction on xp accumulation. But its discharge depends on 1g-A.

## Honest options

### Option A: accept both axioms permanently, document them
Update axiom docstrings to make explicit: these are game-spec claims approved via the user-signoff mechanism (already on per-axiom signoff list 2026-06-01). Update PLAN_perimeter.md Item 1 to "DONE through 1f; remaining axioms are game-spec, deliberately preserved with citations."

### Option B: model extension (Item 1g-extended)
- 1g-A1: extend State + applyActionKind for task pool tracking (~300 LOC).
- 1g-A2: prove accept_cancel_loop_bound_proven via pigeonhole (~200 LOC).
- 1g-B: prove lifecycle_progress_from_bounds_proven via 1g-A2 + 1f machinery + xp induction (~300 LOC).
- 1g-C: switch consumer + delete axioms + drop allow-list (~50 LOC).
- 4-5 focused sessions, real risk of model-extension bugs that hallucinate progress.

### Option C: extension limited to lifecycle_progress_from_bounds only
- Keep accept_cancel_loop_bound as game-spec axiom (narrow, well-cited).
- Prove lifecycle_progress_from_bounds_proven assuming accept_cancel_loop_bound.
- Drop ONE of the two axioms.
- 1 focused session.

## Recommendation
**Option C**. The bridge axiom IS structurally tractable given the narrower axiom — that's what Item 1f's docstring promised. accept_cancel_loop_bound is the genuine game-spec claim (not a composition residual) and deserves permanent axiom status with citation.

## Action
Pause for user decision on A/B/C before proceeding.
