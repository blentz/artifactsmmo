# Plan-cache + macro-chain learning — design

**Date:** 2026-06-23
**Branch (proposed):** `feat/plan-cache-macro-learning`
**Status:** approved design, pre-implementation

## Problem

During productive play the bot burns CPU re-running a full GOAP search **every
cycle**. It computes an N-step plan, executes only `plan[0]`, discards steps
`2..N`, then re-searches from scratch on the next action. For an N-step recipe
chain this is O(N) redundant searches (memory: copper_ring ~52K-node re-search
churn, feather_coat 237K nodes/cycle). The cooldown `time.sleep` and the
no-plan 5s sleep are real sleeps — the CPU cost is the **search itself**, which
can consume seconds under the 90s planner budget.

## Goal

Stop re-searching a known multi-step plan. Plan once, execute the plan
step-by-step, re-plan only when an invalidation trigger fires. Then learn
recurring plan chains across sessions so the planner replays a cached chain
instead of re-deriving its interior, searching only the surrounding edges.

Two phases, shipped and gated independently:

- **Phase 1 — Plan-cache.** In-session commitment to a computed plan; skip
  `decide`+`select` on cache hits. Persist the live commitment + every plan body
  to the learning DB (the latter feeds Phase 2).
- **Phase 2 — Macro-chain learning.** Promote plan-body action-sequences seen
  more than 3 times to persisted *macros*; on re-plan, replay a matching macro
  from cache (skip the interior search) and let the existing loop compute the
  finish edge.

Phase 2 is the larger, higher-risk piece (new planning machinery touching the
formally-gated decision path). **Recommendation: implement Phase 2 only after
Phase 1 lands with `formal/gate.sh` green.**

---

## Phase 1 — Plan-cache

### Loop restructure (`ai/player.py::run`)

The cycle splits into three bands; only the middle becomes conditional.

| Band | Today (lines) | New cadence |
|------|---------------|-------------|
| **Bookkeeping** — periodic refresh, `_build_actions`, `_wait_for_cooldown`, `_maybe_retry_bank`, `gear_latch.update`, `_prev_level`, `arbiter.set_cycle` | 367–385 | **every cycle** |
| **Decision** — combat target, selection ctx, `_strategy.decide`, `crafting_target`, `_arbiter.select`, `_update_sticky_anchor` | 388–453 | **only on re-plan** |
| **Execute + record** — run chosen action, learning/trace/stuck records | 514–612 | **every cycle** |

On a cache hit the Decision band is skipped; the action comes from the cache.
The bookkeeping band MUST stay unconditional — `gear_latch.update` (line 383)
and the previous outcome both drive invalidation triggers.

### New component — `PlanCache`

`src/artifactsmmo_cli/ai/plan_cache.py` — one behavioral class (repo: one
behavioral class per file).

Live commitment fields:
- `selected_goal: Goal`
- `plan: list[Action]`
- `cursor: int`
- `crafting_target: str | None` — re-applied to `state.crafting_target` on every
  hit so the bank keep-set stays correct (today: player.py:429)
- `latch_active: bool` — `gear_latch.active` value at plan time
- `goal_repr: str` — canonical goal key (used by Phase 2)
- `cycles_since_replan: int`

Methods: `current() -> Action | None` (`plan[cursor]` or None), `advance()`
(`cursor += 1`), `exhausted() -> bool` (`cursor >= len(plan)`).

`PlanCache` is a passive holder; the *decision* to reuse it lives in the pure
predicate below.

### Invalidation — pure predicate `should_replan(...)`

`src/artifactsmmo_cli/ai/should_replan.py` — pure function, separately testable
and gate-able.

```
should_replan(
    cache: PlanCache | None,
    last_outcome: str | None,
    latch_active: bool,
    goal_satisfied: bool,
    step_applicable: bool,
    replan_interval: int,
) -> bool
```

Returns `True` (re-decide from scratch) when **any** hold:

1. `cache is None` — cold start.
2. `last_outcome != "ok"` — T1: executed step failed (error / cooldown-miss /
   fight loss / network). Plan assumptions broke.
3. `goal_satisfied or cache.exhausted()` — T2: natural completion.
4. `latch_active != cache.latch_active` — T3: gear-review latch armed or cleared
   since plan time; a higher-priority root may now win.
5. `cache.cycles_since_replan >= replan_interval` — T4: bounded staleness
   (`REPLAN_INTERVAL = 20`, aligned with `BANK_REFRESH_INTERVAL`).
6. `not step_applicable` — safety: `cache.current().is_applicable(state,
   game_data)` is False, so the cached step is stale.

Else → **cache hit**: execute `cache.current()`, `cache.advance()`,
`cache.cycles_since_replan += 1`, re-apply `crafting_target`.

### Persistence (DB)

Extend `LearningStore` (`ai/learning/store.py`) + add SQLModel tables in
`ai/learning/models.py` (two-model `*Base` / `table=True` pattern).

- **Live commitment** — single row per character (upsert on every re-plan):
  `goal_repr`, `plan_json` (list of action reprs), `cursor`, `crafting_target`,
  `latch_active`, `replanned_ts`. Purpose: resume the commitment after a bot
  restart.
  - **Restart safety:** a persisted plan is *advisory*. On load it re-enters the
    normal cycle and is gated by `should_replan` exactly like an in-memory plan —
    trigger #6 (`step_applicable`) discards any step the changed world has
    invalidated. Action objects are reconstructed by matching stored reprs
    against the freshly built `actions` list; any repr with no match → discard
    the whole cached tail and re-plan cold.
- **Plan-body log** — append every computed plan body at re-plan time:
  `goal_repr`, `head_action_repr`, `body_json` (action-repr sequence), `ts`,
  `session_id`. This is the raw input Phase 2 counts. (Phase 1 writes it;
  Phase 1 does not read it.)

### Trace honesty

On a cache hit there is no search, so `planner.last_stats` is stale. Record
`nodes=0, depth=0`, add a `replanned: bool` field to `cycle_stats`, and tag the
cycle so traces never report phantom search cost (repo rule: traces/proofs must
not tell false stories). `_notify_planning(False)` on hits.

### Formal-gate impact (Phase 1)

The loop still emits **exactly one applicable action per cycle**, and every
cached action originally came from `select` — the emittable set is a subset of
what `select` would return. `decide_key`/arbiter internals are unchanged (called
less often, not differently), so differential/mutation gates should stay green.
Liveness (`cycleStepF` "fights eventually fire") is preserved *because* T4 bounds
the cached run to `REPLAN_INTERVAL` cycles before a forced fresh decision. Action
item: run `formal/gate.sh`; if the liveness obligation text assumes a fresh
decision every cycle, make the K-bound explicit in the obligation. No theorem is
expected to weaken.

### Testing (Phase 1)

- Unit: `PlanCache` cursor/advance/exhausted/current; `should_replan` truth
  table — all 6 trigger rows True + the all-false hit row.
- Integration (existing suite, real fixtures, no mocking the unit under test): a
  3-step plan (gather→gather→craft) executes 3 actions with `_arbiter.select`
  called **once** (assert via call-count spy on the arbiter), then each trigger
  forces exactly one re-plan.
- Persistence round-trip: write live commitment, reopen store, reload, assert
  validation-gated reuse; stale-repr load → cold re-plan.
- Repo gate: 0 errors, 0 warnings, 0 skipped, 100% coverage.

---

## Phase 2 — Macro-chain learning

### Concept

A **macro** is a recurring plan-body action-sequence observed more than 3 times.
Once promoted, the planner *replays* the macro's interior from cache instead of
re-searching it, and only plans the edges around it:

- **start edge** — how to reach a state where the macro head applies;
- **macro body** — replayed from cache, no search;
- **finish edge** — from the macro tail to the goal.

### Gate-safe realization (recommended, v1 = Phase 2a)

Do **not** insert a composite macro-operator into the GOAP search — that changes
what `select`/the planner returns and is differentially/mutation gated (high
risk). Instead, realize macros as a **persistent, frequency-filtered seed for
`PlanCache`**:

1. **Detect.** From the Phase-1 plan-body log, count identical
   `(goal_repr, body_json)` chains. At count > 3, upsert a `Macro` row:
   `macro_id`, `goal_key`, `head_action_repr`, `body_json`, `hits`,
   `promoted_ts`.
2. **Replay.** On re-plan, *before* the expensive `decide`+`select`, consult the
   macro library keyed by `goal_key`. For each candidate macro whose
   `head_action_repr` resolves to an `is_applicable` action in the fresh
   `actions` list, seed `PlanCache` with the reconstructed body and skip the
   interior search. Any repr in the body that cannot be matched against the fresh
   `actions` list → macro miss → fall back to a full search this cycle.
3. **Finish edge** is computed by the *existing* loop for free: when the macro
   body exhausts (T2), the normal re-plan derives the continuation.
4. **Start edge** in v1 is trivial: a macro is only replayed when its head is
   already applicable from the current state. If the head is not applicable, the
   macro is skipped and the full planner runs (which may itself reach the macro
   start and get cached next time).

This keeps the proven planner **untouched** (gates stay green) while delivering
the CPU win — the recurring middle is never re-searched.

### Active edge-bridging (v2 = Phase 2b, deferred)

Actively searching a *start edge* to bridge from current state into a
non-applicable macro head (true macro-operator: aggregate precondition/effect as
one composite GOAP edge) is more powerful but inserts a synthetic operator into
the gated search. **Deferred** behind Phase 2a + a dedicated formal review; out
of scope for the first implementation.

### Open question — macro lookup key (resolve in writing-plans with real traces)

The dominant design risk. Candidates:
- `goal_repr` alone — coarse; may propose macros whose head never applies (cheap
  miss, just wasted lookup).
- `(goal_key, head_action_repr)` — proposes only macros whose entry matches the
  intended first step.
- `(goal_key, coarse_state_bucket)` — adds a level/skill band; tighter but
  repeats less often.

`goal_repr` carries volatile counts (e.g. batch K); the key must use a
**canonicalized** goal key that strips volatile fields, or macros will never
repeat. Nail this against real session traces during plan-writing, not now.

### Formal-gate impact (Phase 2a)

Same argument as Phase 1: replayed actions are real `Action`s, gated by
`is_applicable`, one per cycle, bounded by T4. The planner core is unchanged.
The macro layer only changes *which already-valid action* is committed — never
introduces an action `select` could not have produced. Run `formal/gate.sh`;
expect green. (Phase 2b would require new proof obligations — out of scope.)

### Testing (Phase 2a)

- Detector unit: 3 identical chains → no macro; 4th → promotion; near-miss chain
  → no merge.
- Replay: seeded macro with applicable head → `select` not called, 3 actions
  execute, then finish-edge re-plan fires once on exhaustion.
- Key canonicalization: two plans differing only in volatile goal counts map to
  the same macro key.
- Cross-session: promote in session A (DB), replay in session B.
- Repo gate: 0/0/0, 100% coverage.

---

## Out of scope

- Reducing the planner budget or changing GOAP search internals (rejected
  approach C — starves deep recipes).
- Memoizing the A* search by state-signature (rejected approach B — signature
  churns every action; memory cost).
- Active start-edge bridging / composite macro-operators in the planner
  (Phase 2b, deferred).

## Build order

1. Phase 1 PlanCache + `should_replan` + loop restructure (in-memory).
2. Phase 1 DB persistence (live commitment + plan-body log).
3. Run `formal/gate.sh`; resolve any liveness obligation text re T4. Merge.
4. Phase 2a detector + macro table + replay seed. Re-run gate. Merge.
5. (Deferred) Phase 2b active edge-bridging — separate spec + formal review.
