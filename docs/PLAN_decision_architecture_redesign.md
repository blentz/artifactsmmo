# PLAN: decision architecture redesign (removing the epicycles)

Status: Phase 0 + 0b landed (2026-09-25). Phase 1 design pending review; collect ≥24 h of decision events before Phase 1 code lands so it has a mechanism baseline.

## Why this exists

Live 2026-09-25: Robby's first three cycles after a restart were `error:other`,
each `LevelSkill(...) grind sub-plan EXHAUSTED the 15.0s planning budget` (29
such errors in 12 h). Offline replay: A* created 233,739 nodes for
`GatherMaterials(skull_staff)`, a goal whose right answer is three actions
(`Withdraw(steel_bar×5), Withdraw(hardwood_plank×4), Craft(skull_staff)`). The
deterministic recipe descent (`craft_plan_gen`) finds that answer in 8 ms, but
the grind path never asks it.

Patching that one call site would be one more epicycle. A read-only audit of
the whole decision pipeline (three parallel surveys, 2026-09-25) found about 35
mechanisms that exist only to compensate for the decision/planning layer
choosing badly, failing, looping or thrashing. They trace back to three
structural faults.

## Diagnosis: three structural faults

### F1. There is no single model of "how do I obtain X"

Seventeen models answer some version of "can I get X, how, and at what cost"
(`obtain_sources`, `RequirementGraph` + projections + memo, `recipe_closure`,
the `craft_plan_gen` descent, `shopping_list`, `drop_obtainability`, objective
attainability, `_producible` / `actionable_step` / `prerequisites`, skill-grind
`_obtainable`, the route pricer, `cheapest_path_to_level`, the obtain-item
decision graph, and the A* planner's implicit model).

Each one checks a different subset of the real gates: gather skill, craft
skill, bank access, event vendors, grey monsters, spawn liveness, winnability,
yields, and gold location. So they disagree. Eighteen concrete disagreements
are documented (D-A..D-R in the audit), for example:

- `obtain_sources` names GATHER without checking the gather skill; A* requires it.
- GE_FILL is named by the source model, has no pool action, and the descent
  maps it onto a FightAction.
- Five different answers to "is the craft-skill gate a blocker".
- Craft yield is honoured by `demand_set` and `CraftAction.apply` but ignored by
  the descent, `shopping_list`, the factory ladders and `prerequisites`.
- Event vendors excluded in some models and not others; gold counted pocket-only
  in some, pocket+bank in others, always-affordable in others.

Every disagreement surfaces as "component A chose X, component B cannot
do X". It is then patched locally: servable promotion, the grind-failure doom,
the rejected-action memo, parity audits, etc. The parity audits cover six
shallow, skill-10 cells, so most disagreements are unpinned.

### F2. Search does two jobs it is bad at

1. **Feasibility test.** The only way the arbiter learns "can this goal be
   served?" is to run A* and see whether a plan comes back (`select_pure`'s
   first-that-plans rule, `_record_attempt`, supply servability,
   `objective_unplannable`). A timeout is indistinguishable from a dead end, so
   failures must be remembered and aged: DoomedMemo with a 20→160-cycle window,
   `memo_exempt`, `memo_bypass`, `_mark_grind_failure_doomed`, the `is_plannable`
   gate (live-dead on real data), `_step_servable` / `_servable_promotion`, the
   budget floor. Since "always plannable" beats "often fails", ordering needed
   the worth gate, the COLLECT-band hoists and `lower_band_precedes`.
2. **Full-horizon sequencing, re-run on every replan.** h≈0 Dijkstra over
   about 1,900 statically built actions whose quantities are baked in as ladders
   (×full-chain / ×per-craft / ×1). This drove the budgets and node caps, the
   `craft_plan_gen` fast path, per-goal `relevant_actions` whitelists (which then
   needed the region-edge re-add), `max_depth` per goal, `gather_step_target`
   and `next_grind_goal` descents, `grind_probe_state`, one-leg truncation,
   execution-time craft rebatching, the ~1 GB transient search peaks, and the
   repr/quantity fragmentation that breaks every memo keyed on `repr(action)`.

`LevelSkill` is where both jobs collide. It is an optimistic macro action that
A* plans through, and at execution a SECOND A* (with no fast path, no budget,
no history, no memo) tries to expand it. Its failure is then written back into
the first layer's memo.

### F3. Decisions are stateless re-derivations with no notion of progress

Every replan recomputes root → step → goal → plan from scratch, with no memory
of what the character committed to or whether it is making progress. The
missing state was re-added piecemeal:

- **Stability:** sticky `_committed_repr`, focus aging + d'Hondt seats (four
  patch rounds), the RegearEdge latch (whose standing arm froze XP for 981
  cycles), role hold/idle/margin rules, the plan cache as an implicit stabiliser.
- **Recovery by countdown instead of by fact:** StuckDetector + recovery ladder
  + StuckExit, `_suppressed_goals`, `_failed_action_backoff`, error backoff, and
  the memo TTLs. Later code explicitly repudiates countdowns
  (`combat_deficit.py:6-13`, `winnable_cascade.py:21-33`). The ladder itself
  killed sessions (the `NEVER_SUPPRESSED` incident).
- Nearly all of this state is in memory only, so a restart re-runs every known
  failure once (today's Robby symptom).

## Target architecture

### 1. One obtain model (knowledge layer)

A single state-aware AND/OR graph over items, character level and skill levels.

- **Edges** are routes: WITHDRAW, RECYCLE, CRAFT (yield-aware), GATHER (per
  resource), BUY (vendor, currency, event window), GE_FILL, DROP (per monster),
  TASK_REWARD, and LEVEL (skill/char XP sources).
- **Each edge carries:**
  - its gates, as named predicates over the world state: skill ≥ L, level window,
    winnable with current or reachable gear, spawn live/reachable, bank
    accessible, vendor tradeable now, affordable (with one gold rule);
  - an expected cost in cycles, from learned rates where they exist;
  - quantity semantics (yield per action, capacity).
- **One implementation answers all three questions:**
  - Feasibility: a path exists whose gates are satisfied now, or are themselves
    feasible sub-goals.
  - Cost: expected cycles, with a lower bound where needed.
  - Decomposition: which unmet need is next, and which edge serves it.
- **Unmet gates carry a reason.** An infeasible answer names the gate that
  blocks it (e.g. `DROP skeleton_skull: unwinnable, needs weapon tier 3`). That
  replaces "A* found nothing".

Every current consumer (root walk, step routing, grind selection, pricing,
censuses, planner edges) reads this model. The 17 models collapse into it, and
the parity audits become identities. One Lean model plus one differential pins it.

### 2. Goal choice (question 1) never runs the planner

The root/step choice ranks feasible objectives by the obtain model's cost and
value. Infeasibility is a graph fact with a named blocking gate, so there is
nothing to "doom". A blocked goal becomes eligible again exactly when that gate's
fact changes (level-up, gear change, bank unlock, event start), not after N
cycles. This removes DoomedMemo, `memo_exempt` / `memo_bypass`, `is_plannable`,
servable promotion, the grind-failure doom, the worth gate, and first-that-plans
ordering.

### 3. Next action (question 2) is decomposition, not full-horizon search

- **Tasks.** The committed objective is refined through the obtain model into a
  stack of quantity-parameterised tasks, for example:
  - `ReachSkill(weaponcrafting, 21)`
  - → `Craft(skull_staff×1)`
  - → `Obtain(steel_bar, 5)`
  - → `Withdraw(steel_bar, 5)`
- **Primitive actions.** A leaf task emits the next primitive action with its
  real quantity: withdraw N, gather until N, fight until N drops, craft N.
  "Reach skill L" and "reach char level L" are ordinary tasks: pick the grind
  recipe/monster by modelled XP rate, then decompose it. The `LevelSkill` macro
  action and its nested planner disappear.
- **Search stays only for local, bounded problems:** pathing, loadout choice,
  rest vs consume, and short bag-management sequences. Each has a small, closed
  action set and a real heuristic.
- **The static action pool disappears as a planning input.** Actions are
  constructed by the task that needs them, sized to that need. So quantity
  ladders, residual ×1 withdraws and repr fragmentation go away.

### 4. Commitment is explicit, persisted state with a progress measure

- **The intention record.** An intention (objective + task stack + progress
  measure) is stored in the learning DB. Examples of a progress measure:
  holdings toward N, XP toward the level.
- **Re-plan / abandon triggers are facts:**
  - the task is satisfied;
  - a gate on its path turned false;
  - an attributed action failure (server code → model fact);
  - progress stalled across K attempts, with the reason recorded;
  - an interrupt (see 5).
- **Fairness between competing objectives is an explicit budget per intention**
  (e.g. at most N cycles before re-ranking alternatives), not aging applied to a
  stateless argmax. This replaces the sticky commitment, focus aging/d'Hondt,
  the RegearEdge latch, most of the stuck detector ladder, suppression
  countdowns, and the plan cache as a stabiliser.
- **It survives restarts.**

### 5. Guards are interrupts, not competing candidates

HP-critical, bag-full, bank-full and similar conditions are preconditions of
executing the current task. They are handled by a small interrupt layer that
pushes a short task (rest, deposit, discard) on top of the intention and then
resumes it. They are not goals walked in band order against the objective. This
removes band arithmetic, the COLLECT hoists, and sticky-vs-guard preemption
rules.

### 6. Server truth feeds the model, not a countdown

Categorical action refusals (473, 485, 478 …) become model facts:
- this item is not recyclable;
- this slot is occupied by X;
- the bank lacks Y (triggering a resync).

These close the corresponding edge or gate until the fact changes. This replaces
`_rejected_actions` TTLs and the error backoff.

## Migration (strangler, each phase shippable and witnessed live)

| Phase | Change | Removes |
|---|---|---|
| 0 | Baseline census from `cycles`: outcome mix, timeout rate, per-mechanism fire counts, cycles/hour | — (the yardstick) |
| 1 | Unified obtain model behind the existing call sites; fix D-A..D-R inside it; one Lean model + diff; parity audits become identities | 16 duplicate models, their audits |
| 2 | Decomposition becomes the primary next-action producer for every obtain/grind goal (quantity-parameterised leaf tasks); `LevelSkill` expands through it; A* kept only as an instrumented fallback until its fire rate is 0, then deleted for these goals | nested grind A*, grind doom, fast path as a special case, withdraw ladders, rebatching |
| 3 | Goal choice reads feasibility + named blockers from the model | DoomedMemo, memo_exempt/bypass, is_plannable, servable promotion, worth gate, objective_unplannable heuristics |
| 4 | Persistent intention + progress-based abandonment + per-intention budgets | sticky commitment, focus aging, RegearEdge, stuck ladder, suppressions, plan cache as stabiliser |
| 5 | Guards → interrupt layer; refusals → model facts | band walk, hoists, `_rejected_actions`, backoffs |

Phase 2 alone fixes today's symptom and most of the memory/CPU cost. Phases 1
and 2 are the foundation; phases 3-5 delete compensations that become
unnecessary once 1-2 hold.

## Phase 0 — baseline (started 2026-09-25)

**Tool.** `artifactsmmo decision-census <chars…> --hours H --until ISO` is
read-only. It computes the per-character metrics below from the durable
`cycles` / `sessions` tables (`audit/decision_census.py`,
`commands/decision_census_report.py`), and every phase is measured with it.

**Baseline** — 7 days, `2026-09-18T00:00Z .. 2026-09-25T00:00Z`. The window ends
before the GE-cancel fix (bd9b027b) and the fleet rate governor (64f678ef) went
live.

| char | cycles/h | ok | LevelSkill share | goal switches | timed out | nodes p95/max | char xp/h | skill xp/h | cooldown share | top errors |
|---|---|---|---|---|---|---|---|---|---|---|
| C3P0 | 48.9 | 99.6% | 83.0% | 24.8% | 0.1% | 371 / 22,013 | 0 | 225 | 21.2% | http_404 18, grind_budget_exhausted 10 |
| HAL | 36.9 | 99.8% | 10.7% | 77.6% | 0.0% | 823 / 39,760 | 387 | 24 | 42.1% | fight_lost 10 (1 crash) |
| Lor | 48.9 | 99.5% | 80.4% | 19.4% | 0.1% | 461 / 23,036 | 40 | 378 | 33.3% | http_404 17, fight_lost 13, grind 6 |
| R2D2 | 47.9 | 99.5% | 85.2% | 21.6% | 0.1% | 610 / 21,239 | 0 | 309 | 24.6% | http_404 26, grind 7 |
| Robby | 47.2 | 97.7% | 85.2% | 7.5% | 0.3% | 941 / 62,162 | 34 | 203 | 32.1% | http_404 100, http_434 49, grind 22 |

What the baseline says:
- **The fleet is not failing actions; it is mostly doing the wrong thing slowly.**
  - ok stays at 97.7–99.8%, but four of five characters spend 80–85% of cycles
    on `LevelSkill` legs.
  - C3P0 and R2D2 earned 0 character XP in a week.
  - Action cooldowns cover only 21–42% of wall-clock time; the rest is rate-limit
    waiting, planning and errors.
- **`planner_nodes` understates the search.** It records only the last search of
  the cycle (see memory). The 233,739-node grind searches show up as ~15k
  "explored".
- **HAL's 77.6% goal-switch rate** is the thrash that the stability mechanisms
  (sticky, focus aging) exist to damp.

**Correction.** No-plan cycles ARE recorded, as `cycles` rows with
`outcome="no_plan"` and `action_class="NoPlan"` (`player.py`, no-plan branch).
The baseline window simply contains none. An earlier draft of this section
claimed otherwise.

### Phase 0b — decision events (landed 2026-09-25)

**The table.** Every compensating mechanism now notes its firing into a
per-cycle `DecisionEventLog`, which the arbiter shares with the player. The
player writes the batch in the same transaction window as the `cycles` row,
keyed by `cycle_index`, into table
`decision_events(ts, session_id, character, cycle_index, mechanism, subject,
detail)`.

**Mechanisms recorded** (`ai/decision_mechanism.Mechanism`):

| Group | Mechanisms |
|---|---|
| Planning as a feasibility test | `doomed_skip`, `doomed_mark` (detail `timed_out`), `doomed_clear`, `not_plannable`, `grind_doom` |
| Which producer answered | `fast_path`, `search`, `grind_search`, each with `nodes_created / explored / depth / timed_out / node_capped / plan_len` (so the real search size is visible, not just `cycles.planner_nodes`' last-explored count) |
| Selection-order compensations | `worth_gate_bypass`, `wait_fallback`, `servable_promotion` |
| Stability | `commitment_change`, `guard_preempt`, `aged_pick`, `plan_cache_hit`, `replan` |
| Recovery by countdown | `stuck_signal` (level), `suppress` (goal or action, from the ladder's diff), `error_backoff`, `refusal_poison` |

**Not recorded.** `StuckExit` ends the process before the batch is written;
`sessions.exit_reason="stuck_exit"` already records it.

**Where to read it.** `decision-census` prints a `mechanisms:` line with the
per-mechanism counts over the window. Windows before 2026-09-25 show
"none recorded".

**Volume.** About one `replan` or `plan_cache_hit` per cycle, plus one event per
search, so roughly 3-5 rows per cycle and ~20k rows/day for the fleet. There is
no retention policy yet; revisit if the DB grows noticeably.

## Phase 1 — one obtain model (design)

### Goal

A single state-aware, gated, yield-aware model answers every "can I get X /
how / at what cost" question. Its public views keep today's call sites working
while each consumer migrates. The 18 documented disagreements (D-A..D-R in the
audit) are resolved INSIDE it, one explicit policy each, instead of per
consumer.

### Shape

The graph lives in package `ai/obtain_model/`, one behavioural class per file.

- **`Route`** (frozen data)
  - Fields: `kind` (WITHDRAW, RECYCLE, CRAFT, GATHER, BUY, GE_FILL, DROP,
    TASK_REWARD), `via` (resource / monster / npc / recipe / order),
    `yield_per`, `capacity`, `inputs` (item → qty per application, for CRAFT and
    for BUY's currency), and `gates: tuple[Gate, ...]`.
  - `yield_per` is always honoured: craft yield, recycle unit vs batch done
    explicitly, drop and gather expected yields.
- **`Gate`** (frozen data): a named predicate with its evaluated result for
  THIS state.
  - Gates: `SkillAtLeast(skill, L)`, `CharLevelWindow(lo, hi)`,
    `Winnable(monster)`, `SpawnLive(code)`, `BankAccessible`,
    `VendorTradeable(npc)`, `Affordable(currency, amount)`,
    `WorkshopKnown(skill)`, `XpPositive(monster)` (grey), `Licensed(item)`
    (recycle keep-authority).
  - A gate that is not met is a *blocker* the caller can name, price, or turn
    into a sub-goal.
- **`ObtainModel`** is built once per cycle from `(state, game_data, ctx,
  store | None)`, memoised per instance. Its views:
  - `routes(item) -> tuple[Route, ...]`: every route that exists at all, with
    gate status. This replaces `RequirementGraph.leaves` and `edges`.
  - `ready(item, *, policy) -> tuple[Route, ...]`: all gates met, in the
    declared priority order. This replaces `obtain_sources`.
  - `feasible(item, qty, *, policy) -> Feasibility(ok, blockers)`: a least
    fixpoint over AND (craft inputs) / OR (routes), cycle-safe. It replaces
    `_producible`, `is_attainable(_now)`, `drop_obtainable`, `_obtainable`,
    `is_suppliable`, `route_exists`, and `route_is_acquirable`.
  - `cost(item, qty, *, policy) -> float`: the lower bound in actions/cycles
    that `acquisition_cost` computes today. The gated-route pricing (skill grind,
    gear chain) moves here unchanged.
  - `demand(item, qty) -> dict[item, qty]`: yield-aware closure demand (today's
    `demand_set` / `_closure_demand`, unchanged semantics).
- **`Policy`** (frozen data) holds the few legitimate caller differences as
  explicit parameters instead of separate models:
  - `allow_grey` (attainability, grind) vs `drop_farm` (emission);
  - `include_event_vendors`;
  - `grind_descent` (BUY / GE_FILL do not stop a descent);
  - `withdraw_counts_as_owned`.

### One policy per disagreement

| Id | Decision |
|---|---|
| D-A | GATHER carries `SkillAtLeast(gather_skill, resource_level)` and `SpawnLive(resource)`. Every consumer sees the gate. |
| D-B | One GATHER route per resource that drops the item (not "most frequent" / "lowest level"); priority within GATHER by expected yield per action, then skill level. |
| D-C | A secondary-drop resource is an ordinary GATHER route with its own rate. The planner-side mapping is Phase 2. |
| D-D | DROP gates: `SpawnLive` using `monster_spawn_known` (layered/reachable included), `Winnable` (full-HP projection, learned veto through the store when given), `XpPositive` waived only by `Policy.allow_grey`. The level window is one constant shared with FightAction. |
| D-E | GE_FILL is a first-class route with order capacity. Its action construction is Phase 2 (the model names it; the planner must be able to serve it). |
| D-F | BUY routes exist for event vendors with a `VendorTradeable(npc)` gate; `Policy.include_event_vendors` decides whether an ungated-by-time answer is wanted. One "cheapest currency" rule: the min over (price in gold-equivalent via the pricer, then price). |
| D-H | One gold rule: `Affordable` counts pocket gold plus bank gold when `BankAccessible` (a WithdrawGold is one action). The pricer adds that action's cost. |
| D-I | `BankAccessible` gates every WITHDRAW route and every "owned" credit that relies on the bank. `shopping_list` credits the bank only through the model. |
| D-J | The model names exact withdraw quantities. Removing the factory ladders is Phase 2. |
| D-K | Craft yield honoured in `demand`, `feasible`, `cost`, and the (Phase 2) decomposition. |
| D-L | RECYCLE route carries the true unit yield; the batch-yield formula is used only where a batch action is emitted. |
| D-M | The craft-skill gate is a `SkillAtLeast` gate on every CRAFT route. `feasible` treats an unmet skill gate as a blocker, and it is feasible only if the grind itself is feasible (its sub-goal). `cost` prices it with the learned grind cost (today's `_gated_craft_option`). |
| D-N | TASK_REWARD becomes a route kind (today patched into `is_suppliable`). |
| D-O | All closure walks and "is this a drop leaf" classifiers go through `routes` / `demand`. |
| D-Q | A missing skill defaults to 1 (the API's starting level), in one place. |
| D-R | `cost` uses expected yields. A*'s deterministic-yield fiction is Phase 2's problem. |

### Migration order

Each step is one commit, gated by the full gate, and witnessed by
`decision-census` + a disagreement census.

1. **Build the model beside the old ones.** No consumer changes.
   - Unit tests.
   - A Lean spec `Formal/ObtainModel.lean`:
     - `feasible` is the least fixpoint;
     - soundness: `ready` ⊆ routes with all gates true;
     - the priority order.
   - An extracted core plus a diff harness.
2. **Disagreement census** (`audit/obtain_model_census.py`). For every item ×
   every live fleet character's state (plus the scenario fixtures), compare the
   model's views against each old model's answer. Every difference must be
   classified as one of the D-x decisions above; any unclassified difference
   fails. This replaces the six-cell parity audit with the full catalogue.
3. **`obtain_sources` becomes `ready()`**, with `Policy` defaults that reproduce
   today's intended behaviour. The D-A/D-B/D-D changes land here and show up in
   the census.
4. **Migrate consumers one per commit**, in order of blast radius (smallest
   first):
   `drop_obtainability` → `skill_grind_target._obtainable` →
   `objective.is_attainable(_now)` / `is_suppliable` → `strategy._producible` /
   `prerequisites._leafs` → `acquisition_cost.route_options` → `shopping_list` →
   the descent's source map.
5. **Delete** each replaced model, its duplicate closure walk and classifier, and
   the parity audits it made obsolete, with their Lean pins retired or re-pointed
   at `ObtainModel.lean` in the same commit.

### Out of scope for Phase 1

- The A* action pool: withdraw ladders, event vendors, GE_FILL actions, and
  secondary-drop mapping (D-C, D-E, D-F pool side, D-J).
- `LevelSkill` expansion.

All of these become moot or are rebuilt in Phase 2, when actions are
constructed from the model's routes instead of a static factory. Phase 1 must
not add pool patches for them.

### Witness

- **Model level:** the disagreement census goes to zero unclassified
  differences.
- **Behaviour:** `decision-census` over a 24–48 h window after each consumer
  migration shows:
  - no drop in ok share or cycles/hour;
  - char/skill XP per hour at least baseline;
  - no new error class.
- **Expected visible wins in Phase 1:** fewer steps routed to a gather the
  character cannot perform (D-A), and fewer `http_478` "missing items" from
  bank credit while the bank is locked (D-I).

## Risks and open questions

- **Formal surface:** many Lean models and diff harnesses pin components slated
  for deletion (liveness ladder, arbiter select, planner admissibility,
  next-craft). Each phase must retire or replace its pins explicitly, not let
  them rot.
- **Season 9:** launches 2026-10-31 with a full reset. Phases 1-2 are plausible
  before then; 3-5 likely are not. Decide whether season-9 readiness or this
  redesign takes priority.
- **What A* keeps:** the claim that only local problems need search must be
  checked against every goal family (tasks, currency, GE, events/raids, bank
  management). An inventory per goal family is part of Phase 2's design.
- **Stochastic yields:** decomposition must plan against expected yields and
  re-evaluate as drops land (gather/fight "until N"). This replaces A*'s
  deterministic-yield fiction and should be an improvement, but it needs its own
  model in the obtain graph.
- **Fleet coordination:** supply/role/claims are wired through the arbiter's
  goals. They must be re-expressed as obtain-model routes (sibling supply as a
  source) or as intention-level claims.
