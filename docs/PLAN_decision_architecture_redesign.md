# PLAN: decision architecture redesign (removing the epicycles)

Status: Phase 0 + 0b landed; 21 h mechanism baseline recorded (2026-09-27). Phase 1 design pending review.

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

### Phase 0b — mechanism baseline (21 h, 2026-09-26 03:50Z .. 09-27 00:50Z)

This session ran on build 8413a8f4: fleet rate governor, account cache,
wall-clock fix, decision events. The "per cycle" columns are events divided by
cycles.

| char | cycles/h | ok | char XP/h | skill XP/h | replan | cache hit | promotion | aged_pick | doomed_skip | search | grind_search | commitment_change | grind budget exhausted |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| C3P0 | 170 | 100.0% | 0 | 644 | 0.98 | 0.02 | 0.98 | 0.98 | 0.82 | 1.81 | 0.83 | 0.28 | 0 |
| HAL | 59 | 100.0% | 729 | 0 | 1.00 | 0 | 0.90 | 0.99 | 1.46 | 1.01 | 0 | 0.99 | 0 |
| Lor | 148 | 99.9% | 0 | 501 | 0.99 | 0.01 | 0.99 | 0.99 | 0.79 | 1.79 | 0.80 | 0.37 | 0 |
| R2D2 | 141 | 99.9% | 0 | 526 | 1.00 | 0.00 | 1.00 | 1.00 | 0.93 | 1.94 | 0.94 | 0.13 | 0 |
| Robby | 139 | 95.9% | 0 | 1188 | 0.97 | 0.03 | 0.97 | 0.97 | 5.00 | 1.96 | 0.88 | 0.24 | 120 |

**Skill levels gained in 21 h** (character levels unchanged except HAL
27 -> 28):
- C3P0: gear 16->17, jewelry 16->17.
- Lor: fishing 15->16, weapon 14->15.
- R2D2: cooking 23->24, gear 16->17, jewelry 16->17.
- Robby: jewelry 20->21.

The four crafters rotate among three `ReachSkill` goals (the
`commitment_change` column), so no one skill gets sustained effort.

**Targets for later phases** (from the table):
- `servable_promotion`, `aged_pick` and `doomed_skip` are about 1 per cycle.
  Phase 3 must drive them to ~0.
- `grind_search` is about 0.85 per cycle, with 120 of Robby's searches
  exhausting their budget (Robby RSS ~900 MB). Phase 2 must drive both to 0.
- `replan` is about 1 per cycle, with a cache hit rate of 0-3%. Phase 4 must
  replace the cache with a persisted intention.

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

### Progress

**Step 1a landed (2026-09-27):**
- Package `ai/obtain_model/`: `Gate`/`GateKind`, `Route`, `Policy` (+ `LEGACY`), and `ObtainModel.routes` / `ready`.
- `audit/obtain_model_census.legacy_differences`.
- Result: `ready(item, LEGACY) == obtain_sources(item)` for every item in all 44 scenario worlds, with the bank open and with it locked (46,024 comparisons, 0 differences). The same holds for every item of all five live characters (525 each, 0 differences).
- Mutation check: 7 hand mutants (licensed, bank, winnable, primary, permanent, recycle yield, SELL dedupe) are each caught.
- No consumers yet.

**Live preview of the first D-x flips** (routes gained or lost against LEGACY):
- D-A (gather-skill gate): C3P0 loses 17 gather routes and Robby 14. These are routes the character cannot gather today, e.g. C3P0 on birch_wood, which needs woodcutting 20 against his 17.
- D-B (every dropping resource): +40 alternative gather routes.
- D-F (event vendors): no change while no event is live.

**Remaining:**
- 1b (landed with the Lean pin for `ready`):
  - `ObtainModel.ready` delegates to the pure `ready_core.ready_routes`, mirrored by `formal/Formal/ObtainModelReady.lean::readyRoutes`.
  - Proved for all policies and route lists: soundness, order (sublist), completeness for non-SELL routes, SELL uniqueness + first-buyer, and the three policy switches (every other gate is always enforced).
  - Differential: 400 random examples, an exhaustive 2,816-case single-gate sweep, and a SELL witness.
  - 9 mutants over `ready_core.py` and `policy.py`, all killed. Two vendor-switch mutants survived the random harness alone, which is why the exhaustive sweep exists.
  - The Lean pin for `feasible` comes with 1c.
- 1c (landed with the Lean pin for `feasible`):
  - `ObtainModel.feasible(item, policy)` answers "can I get at least one unit?" as a least fixpoint over the input closure of ready routes (`feasible_core.feasible_items`). Held = bag, worn, or pocket gold; banked copies arrive as WITHDRAW routes.
  - It returns `Feasibility(ok, blocking_gates, missing_inputs)`: the unmet enforced gates on the item's own routes, and the infeasible inputs of its ready routes.
  - Mirrored by `formal/Formal/ObtainModelFeasible.lean`, with soundness, completeness, a termination bound (n+1 rounds) and monotonicity in holdings.
  - Differential: 500 random graphs + a cycle and a long-chain witness. 4 fixpoint mutants, all killed.
  - Live (C3P0, Robby): 280 / 292 of 525 items feasible under LEGACY. Under all three D-x flips, 16 / 14 of those flip to infeasible, e.g. bass, birch_wood, dead_wood.
  - Top blockers: craft skill, winnable, spawn_live.
  - Finding for Phase 3: `backpack`, `skull_staff` and `lich_race_trophy`, the roots promoted away every cycle, are all unit-feasible. So that churn comes from step-goal mapping / plannability, not obtainability.
  - `cost` and `demand` attach at step 4 as views over the existing pricer and the Lean-pinned `demand_set`; adding them before any consumer would only be unused surface.
- Step 3 (landed): `obtain_sources` is now a view, `ObtainModel.ready(item, LEGACY)` converted to `Source`s; the legacy rules module is gone.
  - The equality census was at zero differences immediately before the switch, and was then retired, because it would only have compared the model with itself.
  - Each eligibility rule's rationale moved onto the matching `ObtainModel._<kind>` method.
  - Speed: first measured at 1.31x slower per call. After making the rested-state copy lazy and removing a duplicate drop-table scan, it is 0.85x (faster than legacy).
  - The model's gate mutants moved to a mutation group killed by `test_obtain_sources.py`, which now runs through the model.
  - Behaviour: unchanged. Every consumer still asks LEGACY.
- Step 4, first consumer: `drop_obtainability` (M8) (landed).
  - Drop gates live in one function, `obtain_model/drop_routes.py`, used by the model and the oracle, with new gates `SPAWN_KNOWN` and `XP_POSITIVE`.
  - Two new policy switches: `drop_spawn_known` (D-D) and `allow_grey`.
  - `fightable_droppers` is now the policy `LEGACY + drop_spawn_known + allow_grey=<caller>` applied to those routes. It matched the old body exactly: 46,024 comparisons, 0 differences, with grey both ways.
  - The Lean policy gains the two switches (`enforces_drop_spawn`, `enforces_spawn_other`, `enforces_xp_positive`). The exhaustive sweep grows to 32 policies.
  - Found: forcing `SPAWN_KNOWN` true was never caught by `test_drop_obtainability.py`; only the new model test catches it.
- Step 4, second consumer: `skill_grind_target` obtainability (landed).
  - The recursive `_obtainable` walk is gone. `is_obtainable(rung, model)` asks the model under `GRIND_POLICY`, through the rung's own ready CRAFT route (a held copy of the rung does not serve a grind): every input must be RENEWABLE or ON HAND in the recipe's quantity.
  - New model views: `renewable(item, policy)` is the same proved fixpoint over unbounded routes with nothing held; `on_hand(item, policy)` is bag + ready WITHDRAW + RECYCLE capacity.
  - 🔥 Unit feasibility was NOT enough. The first cut used `feasible` and, live, admitted `steel_ring` (needs 2 `hard_leather`), `mushmush_jacket` (3) and `hard_leather_armor` (6) off the bank's ONE `hard_leather`, which nothing makes: rungs that could never be crafted. Caught by explaining every changed live target before merging.
  - `GRIND_POLICY` matches what the grind's descent can serve: every gatherer, routable spawns, grey allowed, and neither skill gate enforced (a skill gate on the chain is grindable, and `gather_demand` surfaces it). A vendor never makes a rung obtainable: BUY is renewable only if gold is, and gold is not. A `market_routes` switch was built for this and removed when a surviving mutant showed the quantity rule made it inert.
  - New policy switch: `craft_skill_gate` (LEGACY True). `drop_spawn_known` became `spawn_known` and now covers GATHER routes too, which carry a `SPAWN_KNOWN` gate from the new `GameData.resource_spawn_known` (reachable layered tiles count, as the action factory builds gathers for them).
  - Found: the obtain model's gather liveness was overworld-only, so underground `gold_rocks`, `mithril_rocks` and `adamantite_rocks` read as unspawned for every consumer. They are now spawned under `spawn_known`; LEGACY is unchanged.
  - Grind target census, 308 (scenario, skill) pairs: 7 targets change. 5 because a material is held or banked in full, 1 because gold ore comes from reachable underground rocks (`strangold_bar` becomes `gold_bar`), and 1 because the rung's material has no resource tile on any layer (`white_knight_helmet` <- `diamond_stone` <- `strange_rocks`). The old walk called that doomed rung obtainable.
  - Live, 5 chars x 7 skills: 1 of 35 targets changes (HAL gearcrafting `skeleton_armor` -> `tromatising_mask`, a tie on steps and level now that the 2 banked `cloth` it needs count).
  - Open-rung census: walled 6 -> 10. The four new walls are gearcrafting 42 in the l48 scenarios (the same `white_knight_helmet`). With combat stats off, 77 -> 63 closed cells because held and banked materials count; with holdings emptied it is 77 again.
  - `has_grind_target` over 308 calls: 0.06s before, 0.09s after.
  - Lean: the policy has 6 switches (`enforces_spawn_switch`, `enforces_craft_skill`, `admits_other`), and the exhaustive sweep covers 64 policies. The new mutants (policy, spawn predicate, quantity views, grind policy) are all killed.
- Step 4: `feasible` becomes the plan's `feasible(item, qty, policy)` (landed).
  - One quantity-aware answer replaces both the unit fixpoint (`feasible_core`, `Formal/ObtainModelFeasible.lean`, retired) and the grind's `renewable`/`on_hand` pair: `supply_core.can_supply`, a path-guarded AND/OR walk. Yes when `qty` are on hand (bag + ready WITHDRAW/RECYCLE; pocket gold for GOLD), or when a ready producing route can deliver `qty` within its capacity and every input can be had in `ceil(qty / yield) * per_application`.
  - Why: the next consumer, `is_attainable_now`, compares a vendor price with pocket gold. Unit feasibility would call a 20,000-gold rune attainable with 1 gold.
  - Memo: each (item, qty) answer is stored with the items it visited and the path cuts it hit, and reused only where the path would not change it. Exact (the differential includes cut cases), and linear on shared subtrees (a 40-layer diamond: 2**40 naive, <= 160 expansions).
  - GE_FILL now carries its gold price as an input. Bank gold is still not counted (D-H).
  - Lean `Formal/ObtainModelSupply.lean`: sound (a yes has a finite supply tree), monotone in holdings, antitone in quantity, fuel bound (n+1 fuel equals the unbounded recursion). Differential: 500 random graphs with capacity cuts, cycles and shared subtrees.
  - The grind asks `feasible(input, recipe_qty, GRIND_POLICY)`. That makes affordable vendors count, so `market_routes` is a live switch again (GRIND keeps it off, because its descent buys only materials nothing else yields).
  - Grind census: 8 of 308 scenario targets change against the original walk. The new one is `greater_dreadful_amulet`, whose intermediate crafts from stock. Live: 2 of 35 (Robby, HAL: `snakeskin_boots` off the account bank's 2 `snakeskin`). ⚠️ Siblings share the bank, so two characters can pick a rung the bank can serve only once. The first craft consumes it and the other's rung drops out: a wasted cycle, not a livelock.
  - Open-rung all-off count 63 -> 62 (still 77 with holdings emptied).
- Step 4, third consumer: `objective.is_attainable_now` (landed).
  - D-N: `SourceKind.TASK_REWARD`. The task board is a route to what it pays (today only `tasks_coin`): one application is one task loop, no inputs, unbounded. A new `Policy.task_rewards` switch is off in LEGACY, so `obtain_sources` is unchanged.
  - `is_attainable_now(code)` = `feasible(code, 1, NEAR_TERM_POLICY)`. NEAR_TERM counts every gatherer, routable spawns, grey droppers, permanent vendors paid from the pocket, and the task board. It enforces no skill gate (the walk is materials-only; `classify_target` checks the crafting skill first).
  - 🔥 GE fills had to be split from vendors (`market_routes` became `vendor_routes` + `ge_routes`). With fills counted, the live comparison gave EVERY character 8-10 new near-term targets (`bandit_armor`, `lich_crown`, ...) that only a GE order supplied. Goal emission fills a GE order only as the cheaper venue for an item an NPC also sells (D-E, Phase 2), so each would have been a root nothing plans.
  - Behaviour: 439 of 22,968 scenario verdicts change, all old-yes -> new-no. The causes are resources with no tile anywhere (`strange_rocks`, `magic_tree` and `diamond_rocks` chains) and partial stock (1 of 5 `pig_skin`, 5 of 6 `cowhide`, ...: targets that could not be finished). 3 scenario gear-target changes. Live, 5 characters: `near_term_gear` and the blocker sheet are unchanged.
  - Cost: `near_term_gear` + `gear_targets_with_blockers` take 36 ms per scenario, up from 13 ms. They run once per cycle, not in the search.
  - The bank is still credited without a `SelectionContext` (NO_PROFILE_CONTEXT): D-I is deferred. Bank gold is not counted: D-H is deferred.
- Step 4, fourth consumer: `objective.is_suppliable` (landed).
  - New view `ObtainModel.mints(item)`: some CRAFT/GATHER/BUY/DROP/TASK_REWARD route exists, gates ignored. WITHDRAW, RECYCLE, GE_FILL and SELL only move existing stock (SELL exists only while a licensed surplus does).
  - `is_suppliable` = `mints` or a free copy in the bag/bank. It no longer reads `RequirementGraph` or `is_task_earnable` (the task board is a TASK_REWARD route now).
  - Equivalence: 23,012 scenario comparisons plus all 5 live characters (524 items each), 0 differences. A first cut counted SELL as a mint and differed only on gold, in the 3 states that held a sellable surplus.
  - Two fixtures had recipes with no crafting skill (never true of real data), so the model had no craft route for them.
- Step 4, fifth consumer: `strategy._producible`, the step graph's leaf test (landed). The user chose "model fight gold" over a gold-is-free flag or deferring to Phase 2.
  - `SourceKind.GOLD_DROP`: one route to GOLD per monster whose win pays gold (API `min_gold`/`max_gold`), yielding the expected `(min + max) // 2`, with the same fight gates as an item drop. `drop_routes` now evaluates fight gates once for both kinds. Gold is RENEWABLE for any character that can win a paying fight.
  - `Policy.fight_gold`: on for the step graph; off for LEGACY, the grind and near-term attainability (pocket gold only), so none of their answers change.
  - `_producible(code)` = craftable (the step graph's `prerequisites` owns the recipe's inputs) or `feasible(code, 1, STEP_POLICY)`. The flat one-level currency check is replaced by the recursive, quantity-aware walk.
  - Behaviour: 185 of 8,844 scenario verdicts change. 130 are spawnless chains (`magic_wood`, `diamond_stone`). 55 are vendor items in zero-attack states, where no fight is winnable, so gold is not renewable there (the old rule called gold always producible).
  - Live, 5 characters: 4 of 203 flip. `magic_wood`, `strange_ore` and `diamond_stone` go to no (spawnless). `lich_race_trophy` goes to YES: 10 `lich_race_medal`, each 100 `event_ticket`, a rare gather drop. The old flat rule refused it by accident. It is feasible but absurd in time, which is a COST question (the cost view is not built yet). Live `plan_once` chosen root, step and ranking are identical for all 5 characters.
  - `prerequisites._leafs` already asks the model (through `obtain_sources`, LEGACY). Its descent semantics are Phase 2's decomposition.
- Step 4, sixth consumer: `acquisition_cost.route_options`'s gated options (landed).
  - New view `ObtainModel.gated_by(item, policy, kind)`: the routes a policy offers that ONE kind of gate alone keeps from being ready.
  - The pricer's three deferred routes are now model routes priced by what opens their gate. They no longer re-derive existence (recipe, skill, workshop, live dropper) themselves:
    - `_gated_craft_option` / `_sibling_craft_option`: the CRAFT route gated by CRAFT_SKILL alone;
    - `_gated_drop_option`: the DROP routes gated by WINNABLE alone.
  - Equivalence: 45,936 `route_options` comparisons over every scenario item (geared states), store-less and with a copy of the live learning store (7,706 options carrying an unlock), 0 differences, same speed.
  - One intentional rule change, fixture-only: a sibling craft now needs a known workshop (a sibling crafts at one too). Three sibling-census fixtures had used "no workshop" to silence the grind route; they now declare it and rely on the missing grind rate.
  - This is the seam `cost` grows from: a gate is a price (grind cycles, gear chain), not a wall.
  - Next consumers: `shopping_list`, and a model `cost` view that folds `route_options` in.
- D-A flipped (landed): LEGACY, the executor's readiness behind `obtain_sources`, enforces the gathering skill. A resource the character cannot yet gather is no ready route: 660 gather routes are withdrawn across the scenario items.
  - The pricer offers such a gather as a route gated by the gathering skill ALONE, priced with the grind that opens it (`_gated_skill_option`, generalised from the gated craft; the census now allows gated craft, gather or drop).
  - 🔥 The first cut removed a live signal. The cooking grind RANKS rungs with the pricer, and a rung needing an uncatchable fish priced as unreachable, so the grind picked a rung it could do (`cooked_wolf_meat` over `cooked_trout`) and fishing lost its only demand. Lor's ranking dropped `ReachSkillLevel(fishing, 30)`. USER chose to keep the fish demand: the pricer now takes the caller's `policy` (default LEGACY), and the grind ranks under `GRIND_PRICING` (gather gate open), its stated stance.
  - Live A/B (5 characters, `plan_once`): chosen root, step and full ranking are identical.
- D-D flipped (landed): LEGACY counts a ROUTABLE spawn (a tile in a reachable region of any layer), not only a live overworld tile. 63 routes are added across the scenario items and none removed: underground `gold_rocks`/`mithril_rocks` gathers and layered `rat`/`bat`/`goblin_guard` drops.
  - Checked servable before flipping: the A* planner plans `Transition(->underground)` then `Gather(gold_rocks×3)` (with `LevelSkill(mining->40)` first for mithril).
  - Live A/B (5 characters, full ranking): identical. `drop_obtainability` no longer overrides the spawn switch (LEGACY is its policy now, plus the caller's grey rule).
- `shopping_list` (NOT migrated, measured first). It is a proved pure core over recipes and holdings; the D-I defect is in its callers (`GatherMaterialsGoal`, the progression goal), which credit bank stock even while the bank is locked. But D-I is dormant: 104 `HTTP_478` "missing item" cycles since 2026-08-03 out of 272,108, and ALL 104 had `bank_accessible=1`. They are shared-bank sibling races (64 `WithdrawItemAction`, 36 `LevelSkill`), not locked-bank credit. Threading bank access into ~15 goal-construction sites buys nothing live. It becomes part of Phase 2, where emission is built from model routes and reads `on_hand` directly.
- 1c: `feasible` / `cost` / `demand` views.
- Then steps 3-5 as above.

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

## Phase 2 — decomposition as the next-action producer (started 2026-09-27)

### Baseline (24 h to 2026-09-27 20:44Z, build d819eea1)

| char | cycles/h | LevelSkill share | search/cycle | grind_search/cycle | FAST_PATH | grind budget exhausted | char XP/h |
|---|---|---|---|---|---|---|---|
| C3P0 | 150 | 77.8% | 1.75 | 0.78 | 0 | 0 | 0 |
| R2D2 | 146 | 75.0% | 1.72 | 0.75 | 0 | 0 | 0 |
| Robby | 122 | 82.0% | 2.05 | 0.82 | 0 | 18 | 0 |
| Lor | 172 | 85.1% | 1.84 | 0.85 | 0 | 0 | 0 |
| HAL | 61 | 0% | 1.01 | 0 | 0 | 0 | 747 |

The route-driven producer (`craft_plan_gen`, the "fast path") produced ZERO plans in 24 h. It serves only a `GatherMaterialsGoal`, and live the arbiter's candidates are `ReachSkill`/`ObtainItem` goals whose A* plan is a `LevelSkill` macro. When the macro executes, `_execute_level_skill` expands it with a NESTED A* over the full pool (15 s budget, no fast path).

### Where next actions come from today (inventory, 2026-09-27)

- Arbiter: `_plans` tries the fast path (GatherMaterials only), then A* over the whole pool (budget = the cooldown, floor 15 s; `goal.max_depth`; 1M-node cap). Every other goal family is A*-only, over its `relevant_actions` whitelist.
- `LevelSkill`: an optimistic macro in the search (`apply` sets the skill). At execution: `next_grind_goal` then a nested A* (`GRIND_SEARCH`), first leg executed, failures marked on the OUTER goal (`GRIND_DOOM`) and raised.
- The pool: roughly 1,900 statically built actions per cycle, with withdraw quantity ladders (full-chain, per-craft, x1) re-sized by goals and overridden by the fast path.

### Increments

- **2a (landed): `LevelSkill` expands through decomposition first.** One shared producer, `craft_plan_gen.decompose(goal, state, game_data, actions, ctx)`, used by the arbiter and the grind. The nested A* runs only when decomposition returns None (instrumented: `FAST_PATH "grind ..."` vs `GRIND_SEARCH`).
  - Measured live over 40 grind goals (5 characters x 8 skills): decomposition answered in <= 10 ms whenever it served. The nested A* timed out at 15 s with NO plan on 4 of them (Robby's three `hardwood_plank` rungs and HAL's gearcrafting rung, 130-173k nodes); decomposition served all four. First legs agree on 20 of 40. Most differences are decomposition taking a recycle or withdraw leg where A* fights or gathers, and HAL's A* inserting a Rest/DepositAll first.
  - Decomposition does not yet serve: huge-quantity cooking rungs (`apple_pie` x173, `cooked_porkchop` x135) and a rung whose leaf is gather-skill-gated (Lor's `bass`, fishing 30). Those still search.
- **2b (landed): the decomposition gaps.** The 2a "quantity ceiling" was misread. Diagnosed branch by branch, decomposition declined for four named reasons:
  - a banked input (`raw_porkchop` x65) had no `Withdraw` action: the static pool builds withdraws only for equippable recipe chains. Decomposition now BUILDS the withdraw at the bank tile, with the real bank access (`generate_next_craft_action(..., bank_accessible=)`, passed from `ctx` by `decompose`).
  - a gather step (`ash_wood` for `hardwood_plank`) was pruned from the goal's A* whitelist. A gather or withdraw step decomposition decided on is now mapped from the whole pool.
  - a leaf gated by a GATHERING skill (Lor's `bass`, fishing 30) opened with an inapplicable gather. The plan now leads with the `LevelSkill` that opens it, as for a crafting gate.
  - a grind's source map offered recycling its own rung (`fire_bow` for `spruce_plank`), the null cycle the goal already excludes. Excluded recycles are dropped from the map.
  - Live, same 40 grind goals: decomposition serves 40 of 40, where 2a served 20 and declined the rest. None needs the nested search. Two 15 s A* timeouts that recurred (HAL's gearcrafting rung here, Robby's `hardwood_plank` before) are served in <= 10 ms.
  - The first legs that differ from A*'s follow the producer's route order: withdraw a banked copy first, recycle a licensed surplus before crafting, gather before crafting held ore.
  - Two producer tests that pinned "no withdraw action, so decline to A*" now pin the built withdraw (and a locked bank still declines).
- **Potion guard (landed, measured waste found while sizing 2c).** The arbiter's own searches are cheap per family (GrindCharacterXP ~3 nodes, ReachSkill ~8, RestoreHP ~441) except one. Robby's `CraftPotionsGoal` searched 836 times in 24 h, found no plan 821 times, and explored up to 98k nodes.
  - Cause: the guard used its own one-level, one-batch obtain walk (`_recipe_producible`) while the goal sized FIVE runs. `earth_boost_potion` x5 needed 5 `yellow_slimeball`; the bank held 1, and the only other source was a drop the potion ladder cannot fight for.
  - Fix: one decision, `potion_supply.potion_batch`, used by BOTH the guard (fires iff it names a batch) and the goal (`_active_craft`). The supply ladder's runs are cut to what the ladder can supply (`feasible_runs`: `ObtainModel.feasible` under `POTION_POLICY`: gathers with skill and spawn, permanent vendors from the pocket, holdings, crafts; NO drops, NO GE-only).
  - New `Policy.drop_routes` switch (on everywhere else; Lean `admits_drop`).
  - Live Robby after: the guard is quiet (nothing the ladder can supply), so `CraftPotionsGoal` no longer enters the arbiter.
- **Preliminary witness of 2a/2b + potion guard (2026-09-28, since the 22:57Z restart on b4a5a2da):** `grind_search` per cycle 0.75-0.85 to 0; Robby's grind budget exhaustions 18 to 0; planner nodes p95 2-6 (was 493-2,268); potion no-plan searches 758 to 0. Target-skill XP/h held (C3P0 458 to 465, R2D2 435 to 494, Lor 476 to 413). Total skill XP/h fell for C3P0, R2D2 and Lor; the loss is side-skill gather XP, with far fewer goal switches. Robby and HAL were down from 06:40Z (outage crash, below), so their numbers are partial.
- **Execution-time craft rebatching removed (landed @e360a3f1, 2026-09-28).** One of the F2 compensations this phase deletes, removed early because it was live damage. `_execute` raised every consumable/utility craft to the whole held pile (`consumable_craft_quantity`, 0dc7f4b6): a second authority over a quantity the goal had sized and the planner had priced.
  - Live: Robby's RestoreHP plan `Craft(cooked_gudgeon×1)` + eat, chosen over Rest as 8 s against 26 s, ran as ×102: a 510 s cooldown for 178 missing hp. There were 12 such crafts in two days (shrimp ×55 = 275 s), and Lor and R2D2 did the same. It also inflated potion crafts past the `potion_batch` sized above.
  - Now the executor only clamps DOWN to what the held inputs cover (`effective_quantity`). MaintainConsumables sizes its craft to the stock deficit; grind crafts take the goal's quantity through `decompose`.
  - Diagnostic: the TUI shows the PLANNED action and `cycles.action_repr` the EXECUTED one. A mismatch between them is an executor rewrite.
- **Unrelated fix landed in the same deploy (@2c31ef46):** an API outage now exits `server_unavailable` and the supervisor restarts it (uncapped; the budget resets after 10 healthy minutes). Robby and HAL had been down about 6 h. It changes nothing in decision-making, but the deploy restarts the witness window.
- **Queued after the witness: `UseConsumable.apply` full-heal fiction.** `apply` sets `hp = max_hp` from one item ("full-heal assumption"), so the planner believes one 50-hp gudgeon closes a 178-hp deficit: craft + eat (8 s) beats Rest (26 s), when it really takes four rounds (32 s, 8 requests) against one Rest. The rebatching hid this; with it gone, RestoreHP will loop craft ×1 + eat across cycles.
  - The fix is an honest `apply` (`hp + restore`, capped at `max_hp`). It is the same class of error as the `LevelSkill` macro (an optimistic `apply` in A*'s model), and it survives this redesign: RestoreHP is a guard that stays on A* until Phase 5.
  - Held back because it changes RestoreHP and combat plans (fights that plan to eat), which would confound the current witness. Ship it as its own change with its own before/after: RestoreHP action mix, Rest share, requests per hp restored.
- **Rest vs consume is honest (open; three defects in one local search).** Witnessed after @e360a3f1 (2026-09-28 19:51Z, 4.85 h): C3P0's gearcrafting grind fights cost 120 hp each; RestoreHP then runs `Craft(cheese×1)` (5 s) + `UseConsumable` (3 s, +150 hp) before the next fight. 186 crafts + 263 eats = 36% of C3P0's cycles, about 28 min of cooldown. Correct in seconds (8 s beats Rest's ~30 s) and gearcrafting XP/h rose (880 to 1,072), but it costs 3 requests per fight instead of 2. The rebatching used to hide it by cooking the whole pile in one request.
  - §3 already names "rest vs consume" as a local search that survives the redesign, and §5 moves RestoreHP from a competing goal to an interrupt (Phase 5). Neither says what that search must get right. Three defects, each shippable on its own with its own before/after:
    1. **Model:** `UseConsumable.apply` full-heal fiction (the queued item above).
    2. **Cost unit:** A* prices seconds only. The request budget is per IP and binds the fleet (~52 cycles/h/char at its tightest, measured when `play --all` landed), and obtain-model edges are already costed in expected CYCLES (§1), i.e. requests. Rest vs consume must price the request too, or two cheap requests keep beating one slightly longer one.
    3. **Stock:** nothing sizes a food batch for grind fights. `MaintainConsumables` fires only when combat is the active means (`ctx.combat_monster`), and a crafting `LevelSkill` whose leaves are fights never sets it. So RestoreHP buys food one unit at a time.
  - **Stock, decided 2026-09-28 (user): MaintainConsumables also fires when the grind's legs are fights.** Caveat found while sizing it: the rung sits in `DISCRETIONARY_ORDER`, BELOW the objective step, and has been selected 8 times in two months (the same unreachability SUPPLY_BANK, ACCEPT_TASK and BANK_EXPAND had before their promotions). Widening its fire condition alone would be inert. It needs either a promotion above the step (a descent slot in the Liveness measures, `formal/Formal/Liveness/*`) or to become part of the grind task itself: the fight leg's prerequisite, sized by the fights it plans. The second matches §3 (a leaf task constructs what it needs, sized to that need) and Phase 5 (no new band rung).
  - **Chosen and built (2026-09-28, user): the grind's fight leg preps.** `_execute_level_skill`: when the grind's next leg is a `FightAction` and the heal stock is under target, `grind_heal_prep.heal_prep_goal` names a `GatherMaterialsGoal` for the deficit, decomposed like every grind leg, and its legs run before the fight (event `FAST_PATH "grind heal prep"`). The fight goes ahead unchanged when the stock is met, when decomposition cannot serve the prep, or when the prep would open another skill grind: a heal stock saves requests and must never block the grind it serves. No new rung, no Liveness change.
    - The heal is the strongest craftable one whose batch `ObtainModel.feasible` finds suppliable under LEGACY (the readiness decomposition serves). On the scenario bundle with C3P0's skills, the strongest on skill alone is `apple_pie`, which cannot be supplied, while held milk makes `cheese`. A prep for the former would never have decomposed. `consumable_supply.craftable_heals` ranks the candidates; `best_craftable_heal` is its head.
    - Found on the way, a decomposition gap in the same family as 2b: `generate_next_craft_action` refused any closure with a leaf no route mints, even when that leaf was HELD (20 `milk_bucket`). A held leaf is now exempt from that pre-check; a leaf held short still declines at the mapping.
    - Offline probe (scenario bundle, C3P0's skills): milk in the bag gives `[Craft(cheese×5)]`, milk in the bank gives `[Withdraw(milk_bucket×5), Craft(cheese×5)]`, nothing held gives `[Gather(shrimp_spot×5), Craft(cooked_shrimp×5)]`.
    - Known residual: `cheese` yields 2 per craft, but the goal's craft is sized in units (×5 runs for 5 units), so a batch makes 10. This is the D-list "craft yield ignored by the sizing" defect, not new; harmless here (the stock caps below a utility stack).
    - Witness: C3P0's RestoreHP `CraftAction` count per fight should fall from about 1 to about 1/5 (one batch per stock), and requests per grind fight from 3 toward 2, with no drop in gearcrafting XP/h.
  - Food batching belongs to the fight leaf task in 2c/2d ("fight until N" sizes the food for N fights); the fix above is the interim, witnessed version.
- **Witness of 2a/2b: PASSED (recorded 2026-09-29).** About 31 h on 2a/2b code over three sessions (09-27 22:58Z, 09-28 13:10Z, 09-28 19:51Z; the last one, 17 h, also carries @e360a3f1 and @2c31ef46). Baseline: the 24 h ending 09-27 22:10Z, before 2a.
  - `grind_search` 2,337-3,565 per character-day to **0**; `grind_doom` and `grind budget exhausted` 18 to 0 (Robby); planner timeouts 0.6% to 0%; nodes p95 491-2,441 to 2-128; ok share 99.0-100% to 99.6-99.9%.
  - Fleet cycles/h 650 to 614 (-5.5%). Cooldown share rose (Lor 85% to 91%): more time in longer target crafts, not more planning overhead.
  - Skill XP/h 4,292 to 3,274, but TARGET-skill XP rose: C3P0 gearcrafting 233 to 345 and jewelrycrafting 66 to 247; Robby jewelrycrafting 45 to 282; Lor weaponcrafting 186 to 295; R2D2 gearcrafting 251 to 278 and jewelrycrafting 125 to 149. The loss is side XP:
    - cooking about 900/h to 0, all of it from RestoreHP cooking whole food piles through the rebatching @e360a3f1 removed (baseline day: Robby 8,688, C3P0 6,335, R2D2 5,940 cooking XP);
    - side gathering XP (Robby mining 409, Lor woodcutting 460 to 152), with goal switches 25-42% down to 5-24%.
  - HAL reached level 30 at 09-29 00:21Z and moved from the pig grind (char XP) to a weaponcrafting grind: an objective change, not a fault.
  - Residuals seen: one Robby `CraftPotionsGoal` search of 115k nodes (1 of 603, no timeout); C3P0's 227 RestoreHP crafts, which @2972d481 (grind fight-leg heal prep, deployed with the 09-29 restart) addresses under its own witness.
  - The `GRIND_SEARCH = 0` condition that gates 2d has held for the whole 31 h.
- **2c re-scoped by measurement (2026-09-29, user).** Arbiter searches outside the grind over the 17 h after the 09-28 19:51Z restart (`decision_events`):

  | goal family | searches | nodes created | timeouts |
  |---|---|---|---|
  | CraftPotionsGoal | 652 | 122 M | 320 |
  | RestoreHP | 816 | 248 k | 0 |
  | ReachSkill (plans the `LevelSkill` macro) | 8,420 | 68 k | 0 |
  | GrindCharacterXP | 7,160 | 20 k | 0 |

  The grind's own GatherMaterials already decomposes (8,420 fast paths, 19 searches). The only family that fails is Robby's CraftPotionsGoal: from 09-29 06Z, about 70 searches an hour, each timing out at ~200k nodes and depth 92 with no plan. `potion_batch` judges the batch suppliable, and the goal provisions `max_depth` to its own worst-case length (`runs * sum(recipe) + 2`), but a batch that long is beyond the search budget: F2 exactly (search as the feasibility test and as a full-horizon planner). Those searches are invisible to the per-cycle census because the goal is a candidate that never gets selected.
  - **2c-1: CraftPotionsGoal decomposes.** It is an obtain goal: `equip_qty` of the frozen target potion in the bag, then one `EquipAction`. `decompose` serves it through the same producer as the grind: a `GatherMaterialsGoal` for the potions the bag lacks, whose plan (withdraw, recycle, craft, gather, buy, in route order) is followed by the goal's own sized `EquipAction`; once the bag holds the batch, the plan is the equip alone. A* stays as the instrumented fallback. Witness: CraftPotionsGoal `search` events and timeouts to ~0, `fast_path` for it instead.
  - **2c-1 built (2026-09-29).** `craft_plan_gen._decompose_potions`, reached through `decompose` by both the arbiter and the grind. `CraftPotionsGoal.batch_equip` (the equip still owed, sized to what is unequipped) and `batch_obtain` (the potions the bag lacks, as a `GatherMaterialsGoal`). The equip joins the plan only when the legs land the whole batch: a craft leg is a bounded batch, so a plan can be a prefix, and the next cycle decomposes the rest. It declines (A* stays the fallback) when unseeded or satisfied, when the batch cannot be decomposed, or when the plan would fight or open a skill grind (the potion ladder serves neither: `POTION_POLICY`).
    - Offline, every committed scenario world where the potion guard fires (6), driven decompose → apply to satisfaction: 5 served in 4-23 ms each; the sixth (`l20_bag_critical_empty_bank`, 8 free slots against a 40-potion batch) declines honestly and A* can sequence the deposit.
    - **Craft yield in the descent (user, 2026-09-29), the D-list "craft yield ignored by the descent".** Robby's live potion (`earth_boost_potion`) and `small_health_potion` both yield 2. The descent sized inputs as `per * deficit` (units), asked for twice the ingredients, and reached for a fight, so 2c-1 would have declined exactly the live case. Now `next_craft_core._next` crafts `runs = ⌈deficit / yield⌉` and needs `per * runs`; a craft step's `qty` is RUNS; `craft_plan_driver_core._apply_state` credits `runs * yield`. `yields` defaults to empty (every yield 1: byte-identical for existing callers); `decompose` passes `GameData.craft_yields`.
      - Lean: `NextCraftAction.runsFor` (+ `runsFor_pos`) and a `yields` parameter through `nextHelper`/`nextCraftTarget` and `CraftPlanDriver.applyState`/`craftPlan`/`foldPlan`. Every role theorem re-proved with its statement unchanged apart from the new binder (ORDERING is literally the same, since `result.qty` is now runs). New `decide` witnesses: copper_bar yield 2 (20 ore, 2 runs, fold leaves 1 spare bar) and yield 0 read as 1. Contracts updated; oracle takes an optional 8th `yields` argument.
      - Differentials: random yields 0-3 on random DAGs and over the six-source scenarios, with a non-vacuity assertion that some answer depends on a yield. Mutants: units-not-runs, runs rounded down, fold credits runs not `runs * yield`: all killed.
      - Found with it: `size_intermediate_craft` passed `craft_batch_size_pure`'s UNITS through as RUNS, so a yield-2 craft made twice its batch (`Craft(earth_boost_potion×6)` for 6 potions). It now converts, rounding up when demand is the bound and down when space or the cap is (never below one run). The old unit test had pinned the mix-up (3 runs, i.e. 30 ore, against 15 usable slots).
    - Heal prep correction: `heal_prep_goal` asks for bank + bag + deficit, and now says why truly. Decomposition credits a banked copy of the TARGET without withdrawing it (the WITHDRAW source is dropped for the target; only banked INPUTS are withdrawn), so bag + deficit would leave the bag short by the bank's copies. A live bank-aware target withdraw is 2c-2's.
  - **2c-2 (was 2c): decomposition over the obtain model's routes directly** (drop the `Source` bridge), with gated routes as sub-tasks. No measured live payoff by itself; it is the prerequisite for 2d's deletion of the `LevelSkill` macro, since a skill gate must then be a sub-task rather than a macro leg.
- **2c-2 design (drafted 2026-09-29; user decisions: maximize sub-tasking; fix the banked-target discrepancy; refactor the formal core).**

  **The design principle: the next action is the first leaf of the feasibility witness.** Today two computations answer "can I get N of X" and "what do I do next": `ObtainModel.feasible` (`supply_core.can_supply`, proved in `ObtainModelSupply.lean`) and decomposition (`next_craft_core` + `craft_plan_driver_core`, proved in `NextCraftAction.lean` / `CraftPlanDriver.lean`, fed a lossy `Source` projection plus a separate `recipes` map). They disagree, and every disagreement surfaced this week as "the model says yes, decomposition declines, A* times out": craft yield (the descent ignored it), a secondary-drop gather (the mapping ignored it), a banked copy of the target (credited, never withdrawn). Each was patched where it bit. 2c-2 removes the class: ONE walk over the route graph returns a supply tree when one exists, and the next action is that tree's first leaf. By construction, and by theorem: feasible ⇒ a next action exists, and a decline ⇒ infeasible with named blockers.

  **Gates become sub-tasks wherever an action can open them (maximal sub-tasking).** A route blocked only by openable gates is a route whose first step is opening them, and the gate's sub-task is a goal the same decomposition serves:

  | Gate | Sub-task | Opens when | Notes |
  |---|---|---|---|
  | GATHER_SKILL(s, L) | ReachSkill(s, L), the grind's decomposition | skill s ≥ L | replaces `_unmet_gather_gate` and the craft-skill LevelSkill emission in `generate_next_craft_action` |
  | CRAFT_SKILL(s, L) | ReachSkill(s, L) | skill s ≥ L | same |
  | BANK_ACCESSIBLE | UnlockBank | the bank unlocks | the existing unlock goal, reached from the obtain walk instead of from a band |
  | WINNABLE(m) | BecomeWinnable(m): the gear (ObtainItem) or character level that makes `predict_win` true | the prediction flips | the combat-deficit machinery becomes a sub-task of the drop route that needs it; the C1 two-authority split (`has_combat_deficit` vs `task_decision`) closes because both read this one gate. Its own increment (largest) |
  | inputs: gold, currency | the input's own routes (GOLD_DROP, SELL, TASK_REWARD, ...) | held | already sub-tasking by construction: a price is an input like any other |
  | SPAWN_KNOWN in another region | movement (region transition) | reachable | already an action-level edge; no sub-task |
  | SPAWN_LIVE / VENDOR_TRADEABLE on event content | WaitForEvent when the start time is known (raids carry `next_start_at`) | the event starts | otherwise a time-gated BLOCKER that reopens on the fact (Phase 3), never a countdown |
  | VENDOR_LOCATED, GE_LOCATED, WORKSHOP_KNOWN, LICENSED | none | data or policy change | hard blockers, named |
  | XP_POSITIVE | none (a policy, not an obtain gate) | | stays a `Policy` switch |

  A sub-task's feasibility is its own model's (the grind's rung walk for ReachSkill, the combat model for WINNABLE). The core takes it as an input verdict per gate, `openable : Gate → Bool`, so the core stays pure and decidable while the recursion lives where each model already lives.

  **What the one walk does** (Lean-first, `Formal/Decompose.lean`, extending `ObtainModelSupply`):
  - Graph: items; per item, routes in priority order, each `{kind, via, yieldPer, capacity, inputs, gates}`. A CRAFT route's inputs ARE the recipe, so the separate `recipes` map disappears, and with it the "a CRAFT source defers to the recipe descent" special case. WITHDRAW is an ordinary route whose capacity is the bank's stock; `onHand` is the BAG only. That fixes the banked-target discrepancy by construction: a banked copy of the target is withdrawn like any banked input, and the heal-prep and potion quantities go back to plain bag + deficit.
  - `can` (existing, proved sound, monotone, antitone, fuel-bounded) is extended with sub-task nodes: a route whose unmet gates are all `openable` is usable, with the gates as prerequisite leaves.
  - `step`: the first leaf of the witness `can` builds, in route-priority order: `gather | craft(runs) | withdraw | recycle | buy | fill | fight | open(gate)`.
  - Theorems (roles): SOUND (a step is a leaf of a finite supply tree), COMPLETE (`can = true ↔ step ≠ none`: decomposition never declines a feasible goal), PROGRESS (executing a non-`open` step strictly decreases a well-founded deficit measure; `open` hands off to a sub-task whose success strictly shrinks the set of unmet gates), ORDERING (craft only with every input on hand), BANK/RECYCLE caps (withdraw ≤ bank, recycle ≤ remaining licence), YIELD (runs = ⌈deficit / yield⌉). `NextCraftAction` and `CraftPlanDriver` retire explicitly with their manifest, contract, audit and mutant entries (the formal-surface risk below).
  - Python `decompose_core.py` mirrors it; the differential drives random route graphs (six kinds, gates, capacities, yields, bag and bank) through both.

  **What it deletes** (the epicycles this removes, each a patch where a disagreement bit):
  - the `Source` bridge in decomposition (`obtain_source_map`; other consumers migrate separately);
  - in `generate_next_craft_action`: the craft-skill LevelSkill emission, `_unmet_gather_gate`, the WITHDRAW-source filter, the held-leaf exemption, the excluded-recycle filter (becomes an exclusion input to the walk), the "no source" pre-check;
  - `_map_next_action`'s pool matching (2c-2d below): actions are CONSTRUCTED from the step (§3: "actions are constructed by the task that needs them, sized to that need"), so a step can never lack an action (the 2b withdraw gap and today's secondary-drop gap);
  - `size_intermediate_craft` inside decomposition (the walk sizes runs itself; the unit/run conversion lives in one proved place);
  - the bank-inclusive quantity fudges in `grind_heal_prep` and `CraftPotionsGoal.batch_obtain`.

  **Kept deliberately:** one leg per cycle after a fight (drops are stochastic; the replan reads the real yield, the D-R expected-yield model is separate); the loadout re-arm before a gather or fight (a local problem, §3); `_finish`'s applicability check becomes a debug assertion once construction guarantees it.

  **Increments** (each shippable, each witnessed):
  - **2c-2.0 measure first:** a `DECOMPOSE_DECLINE` event naming the blocking gate(s) or missing input, for every decline, so each later increment has a before/after (live today, declines are invisible: the caller silently searches).
  - **2c-2a formal core:** `Formal/Decompose.lean` + `decompose_core.py` + differential + contracts + mutants; not yet wired.
    - **Built (2026-09-29).** One semantic decision it forced: the walk replaces BOTH `supply_core` (feasibility) and `next_craft_core` (the step), and they disagreed on holdings. `supply_core` was all-or-nothing (holding 3 of 5 does not make the other 2 cheaper); the descent served the deficit. The one walk serves the DEFICIT: `q` can be had when on hand, or when some route delivers `q - onHand` and every input can be had in the amount its `⌈deficit / yield⌉` runs consume. This makes `feasible` slightly more permissive when 2c-2b wires it; the parity check measures it.
    - Proved (all nine role theorems, axioms `propext`/`Quot.sound`, plus `Classical.choice` only in the fuel bounds): `step_complete` (feasible and unmet ⇒ a step), `step_sound`, `step_none_iff` (no step ⇔ satisfied or infeasible), `step_act_spec` (act only on a gate-free route whose capacity covers the deficit, `runs = ⌈need/yield⌉ ≥ 1`, every input on hand), `step_open_spec` (open the first gate of the route it blocks), `can_sound` (a finite supply tree), `can_mono` (more held or fewer wanted is never harder), `can_fuel_stable` and `step_fuel_stable` (`n + 1` fuel is the unbounded Python recursion, for a closed graph). Witnesses by `decide`: the copper-ring chain with bar yield 2 (gather 20, craft 2 runs), the deficit (1 ring held, 3 wanted ⇒ 1 bar run), a gate opened first, satisfied, infeasible, and a capacity cut handing over to the next route.
    - Python `decompose_core.py` (`can_obtain`, `next_step`; the `supply_core` memo carried over). Differential: 500 random graphs (cycles, self-loops, gates, yields 0-3, capacity cuts, holdings), feasibility AND step compared on every item at quantities 0-8, a seeded sweep asserting every answer shape occurs (satisfied, infeasible, act, descended act, open) and COMPLETE on the Python side, and the memo cut case. Eight mutants (round-down runs, all-or-nothing need, capacity off-by-one, yield ignored, gate ignored, descend into a held input, memo reused under any path, path guard dropped): all killed; the memo mutant survived the random sweep until the explicit cut case was added.
  - **2c-2b wire it:** `decompose` builds the route graph from `ObtainModel` (LEGACY readiness) and asks the core; delete the `generate_next_craft_action` patches listed above; retire the two old Lean modules. Parity check first, offline over every scenario world and grind goal: the new walk serves a superset of what the old one served, and every difference is named.
    - **Model revised twice while wiring (2026-09-29).** v1 chose ONE route per item node, so a capped route (a bank's 21 algae against 33 needed, a licensed recycle covering 3 of 6 bars) was skipped whole and the rest produced from scratch: the old descent's mixed plan was lost. v2 split held stock into bag and bank; v3, shipped, fills the deficit GREEDILY across routes in priority order, each taking `min(capacity, what is left)`. A bank is then just a WITHDRAW route capped at its stock (the bag/bank split went away), a licensed recycle covers its share and a gather the rest, and a banked copy of the goal itself is withdrawn. All role theorems re-proved over the greedy fill (plus a fill-monotonicity lemma for `can_mono`); the tree-soundness theorem was dropped (COMPLETE/SOUND/VALIDITY carry the step's contract).
    - **Adapter** (`ObtainModel.walk_graph`/`walk`): ready routes under `DECOMPOSE_POLICY` (LEGACY with every gather route offered, D-B, and no GE fill, D-E: a fill spends gold and the cost view does not exist yet); RECYCLE and SELL consume one copy of their source per application, capped at the copies held; `produce` (a grind's rung: its banked/recyclable copies are never counted, the XP is in the making: the held-rung livelock) and `keep` (the goal's own targets are never destroyed as a source: recycling a held copper_ring to craft a copper_ring was a null cycle the first cut reintroduced); gate-blocked routes whose unmet gates are all openable join after the ready ones (2c-2c: a skill gate with an applicable `LevelSkill` in the pool). Gather routes are ranked by the proved gather-source order (`gather_selection.rank_gather_sources`, same key as `select_gather_source`); which dropper to fight is `select_drop_fight`'s (proved expected-kills order, grey drop_farm).
    - **Parity**, offline, 337 goals over every scenario world (grind goals per skill, potion batches): 330 identical first legs; the 7 differences are all corrections (banked materials used before production: feathers, eggs, iron bars; a mining grind no longer recycles an `iron_helm` to "make" its rung). Feasibility identical except the 5 goals a skill-gate sub-task now makes feasible. Live, all 5 characters × 8 grinds + potions: no unmapped decline; corrections again (a grind rung makes exactly one more: withdraw 1 raw porkchop, not 65; HAL's jewelry grind withdraws banked hardwood planks instead of grinding woodcutting to 20; two cooking rungs the old descent declined are served).
    - Found by the live check: a GE_FILL step the old descent never used (its "ge_fill" NextAction fell through the mapping into a fight) — the reason for D-E above; and DROP steps naming the model's first dropper, which the pool did not fight — the reason the proved selection picks the monster.
    - **Retired:** `next_craft_core.py`, `craft_plan_driver_core.py`, `generate_next_craft_action` and its mapping/gate helpers, `obtain_source_map`, the Lean modules `NextCraftAction` and `CraftPlanDriver` with their oracle handlers, differentials, manifest/contract/audit entries and mutants. The 64 old-producer test calls moved to `decompose`: 70 unchanged, the rest updated where the walk corrects the old behaviour (a banked target is withdrawn; a locked bank means produce, not decline; a bank-only recycle source is withdrawn with a built withdraw) or where a fixture was never consistent with the model (resource tiles; recycle surpluses the keep authority protects). The obtain-parity witness that pinned the old descent gathering WITHOUT the model (via `gatherable_drop_items`) now shows both checks failing when the gather arm is deleted: the second authority is gone.
    - Follow-up: the obtain-parity census's WITHDRAW carve-out existed because the old descent did not use WITHDRAW sources; the walk does, so it can go, measured on its own.
  - **2c-2c skill and bank sub-tasks:** `open(GATHER_SKILL | CRAFT_SKILL)` emits the ReachSkill sub-task and `open(BANK_ACCESSIBLE)` the unlock. This is what lets 2d delete the `LevelSkill` macro: a skill gate is a sub-task, not a macro leg.
  - **2c-2d construct actions:** the step builds its action (gather at the nearest tile of the resource, craft at the workshop, withdraw at the bank, buy at the NPC, fill the GE order, fight the monster) from game data; the pool mapping goes.
  - **2c-2e WINNABLE sub-task:** BecomeWinnable(m) through the gear and level models, closing C1.
  - Event WaitForEvent is Phase 3's (blockers that reopen on facts); 2c-2 only names them.
  - **Witness:** `DECOMPOSE_DECLINE` by blocker (only hard or time blockers should remain), arbiter `search` share for obtain-shaped goals toward 0, A* timeouts 0, ok share, cycles/h, target-skill XP/h.

  **How this fits the original concept.** GOAP with A* and provable functional properties stays the architecture. The obtain decomposition becomes a proved hierarchical planner whose leaves are GOAP primitive actions: sound, complete relative to the model, terminating. A* keeps the local, bounded problems it is good at (rest vs consume, bag management, loadout), each with a small closed action set and an admissible heuristic.

- **2c-2 (original line):** decomposition over the obtain model's routes directly (drop the `obtain_source_map` / `Source` bridge), including gated routes as sub-tasks. Superseded by the design above.
- **2d:** the arbiter's `ReachSkill`/`ObtainItem` candidates decompose directly instead of A* planning a `LevelSkill` macro; the macro and its nested planner are deleted once `GRIND_SEARCH` stays at 0.
- **2d design (drafted 2026-09-29, after the 2c-2b deploy).**
  - **Measured.** Every live `LevelSkill` execution comes from a `ReachSkill` goal (12,465 cycles in the 26 h after 09-28 19:52Z; no other family ran it). The arbiter plans it with A* (the ReachSkill search, ~8,400 searches / 17 h), and the player then expands it: `next_grind_goal` picks the rung and `decompose` serves it (`GRIND_SEARCH` has been 0 since 2a/2b). So the macro is now a relay: A* plans one opaque step, and the real work happens in a second planner at execution.
  - **What depends on it** (47 source files): action production (`factory` builds one per needed (skill, level); `reach_skill`, `gathering`, `progression`, `supply_bank` admit it into A*); execution (`player._execute_level_skill`, `grind_expansion` for the TUI, `GRIND_SEARCH`/`GRIND_DOOM`); planning (the A* heuristic, region edges, plan cache/tree, macro segmentation); root and step decisions (`LevelSkill(S, C+1).is_applicable` is the "an open rung exists" predicate in `decisions/root.py` and the open-rung census); learned grind rates (`store.skill_grind_rate` keys on `action_repr` starting `LevelSkill(skill->`); and the formal side (the Liveness models treat a grind step as an action: `Plan`, `ProgressAction`, `Measure`, `GoalSystem`, `GatherProgress`, `WitnessAcquirable`, plus `test_level_skill_diff`).
  - **Increments.**
    - **2d-a: ReachSkill decomposes directly.** `decompose(ReachSkillGoal)` returns the grind's legs (the rung goal `next_grind_goal` picks, served by the one walk), so the arbiter plans the real actions and A* never sees ReachSkill; the walk's `OpenGate` sub-task expands the same way (recursively, with a cycle guard on the skill) instead of emitting a `LevelSkill` action. The macro stays in the pool for any A* goal that still names it (none live). Witness: ReachSkill `search` events to 0; `LevelSkill` cycles to 0; target-skill XP/h and cycles/h unchanged.
    - **2d-b: the macro leaves the pool.** No goal admits it; the A* heuristic's grind estimate and the region-edge re-add lose their LevelSkill arm.
    - **2d-c: delete it.** The action class, `_execute_level_skill`, the nested A* fallback and its `GRIND_SEARCH`/`GRIND_DOOM` mechanisms and memo marking; the "open rung" predicate becomes the function the macro's `is_applicable` already wraps (`best_gather_resource_drop` or `has_grind_target`); TUI and audits follow.
  - **Decisions for the user:**
    1. *Recording.* Today a grind leg is recorded under the outer `LevelSkill(...)` (by design, `_execute`'s docstring). After 2d-a the cycle's action is the real leg (Gather/Craft/Fight) with `ReachSkill(skill->L)` as its goal. Learned grind rates re-key on the goal (`selected_goal` starting `ReachSkill(skill->`), reading legacy `LevelSkill(skill->` rows too so the history carries over.
    2. *Formal.* The Liveness proofs model a grind step as one action. Either keep that abstraction in Lean (a "grind step" = one leg of the ReachSkill decomposition, its code anchor rebound from the macro to the decomposition) or re-model the grind as its legs. Keeping the abstraction is sound (each leg earns the skill XP the step models) and bounded in cost; re-modelling is a separate formal epic.
    3. *Order.* 2d-a first and witnessed on its own (it is the behaviour change), then 2d-b and 2d-c as deletions.
  - **Decided (user, 2026-09-29):** (1) re-key learned grind rates on the goal, reading legacy `LevelSkill` rows too; (2) RE-MODEL the grind as its legs in the Liveness proofs, a formal epic that must land before 2d-c deletes the macro; (3) 2d-a first, witnessed alone, then 2d-b/2d-c.
  - **2d-a built (2026-09-29).**
    - `decompose(ReachSkillGoal)` dispatches to `craft_plan_gen._decompose_grind`: it declines `satisfied` or `no_grind_rung:<skill>`, otherwise it walks the rung `next_grind_goal` picks.
    - A skill gate the walk meets is openable when `skill_is_grindable` holds (new `ai/skill_grindable.py`, the predicate `LevelSkill.is_applicable` now delegates to) and the skill is not already being ground further up (`grinding`). `OpenGate` expands into that grind's own legs, and the plan stops after them. A cyclic dependency (mining's rung needs mining-gated ore) is infeasible and named, never a loop.
    - The grind fight-leg heal prep moved from `player._with_heal_prep` into `_decompose_grind`, so the arbiter's ReachSkill candidate and the LevelSkill expansion both get it. The prep walks under `HEAL_PREP_POLICY` (no drop routes) and is dropped if its legs fight. Its declines are noted as `heal_prep:<reason>`. Residual: a grind that falls back to the nested A* runs without the prep; that path retires in 2d-c.
    - Learned grind rates read rows whose `selected_goal` starts `ReachSkill(skill->` as well as legacy `LevelSkill(skill->` actions (`store.grind_goal_prefix`).
    - The arbiter's fast-path comment names the grind. Plan shape changes in the goldens (l10 weapon upgrade now withdraws its copper ore first; l12 gathers copper) are the one walk's real legs replacing the opaque macro.
    - Mutants: the walk's gate openness and cycle guard, the prep (never prepped / may fight / decline not noted), `HEAL_PREP_POLICY`, and the three `LevelSkill` applicability mutants rebound to `skill_grindable.py`.
    - Craft census: the plan's first leg under a skill gate is now the grind's real leg, which the audit judged "unrelated" (47 PLANNER_BUG cells). `audit.craft_completeness.advances_a_closure_grind` accepts a leg that advances the rung closure of a skill the recipe's closure lacks, recursively through a gated rung (maple_syrup at cooking 35: cooking rung cooked_bass, bass needs fishing 30, leg = the fishing grind's gudgeon). Census after: PASS 301, PB 0, identical to 2c-2b.
    - **2c-2b census drop explained (found here).** The committed MATRIX said PASS 458; the 2c-2a gate measured 469 and the 2c-2b gate 301 (EG +85, CB +84, MU unchanged). The gate gates only on PLANNER_BUG, so nobody saw it. It is an honest correction: at 2c-2a the old descent emitted `LevelSkill` for an under-skill cell whether or not the recipe could be finished (antidote 30/30: `LevelSkill(mining->35)` toward event-only strange_ore; cheese 8/5: `LevelSkill(cooking->10)` with milk behind an unwinnable cow), and the audit passed any closure-skill grind. The one walk checks the whole tree before stepping and declines. Every lost cell is EG or CB, which `classify_gap` assigns without reading the plan, so each has an unreachable leaf. The regenerated MATRIX/BACKLOG are committed with 2d-a.
    - **Preliminary witness (restart 2026-09-30 00:58Z, 2h10m vs the 2h10m before, learning.db).** Cycles 1,389 → 1,380 (unchanged). ReachSkill `search` 1,175 → 0; all `search` 2,340 → 525. ReachSkill cycles now run real legs (Gather 752, Fight 402, Craft 39, Withdraw 30, Recycle 8); `LevelSkill` cycles 4, all in the first 90 s from plans cached before the restart. Skill XP 5,581 → 7,531 (+35%). Errors 6, all `HTTP_404` withdraws (the known sibling race); 0 decompose declines. The 24 h `decision-census` still to confirm.
- **2d-L design: the grind as legs in the proofs (drafted 2026-09-30; must land before 2d-c).**
  - **What the proofs model today** (map of formal/, spot-checked).
    - The liveness rung `.gather` raises `trackedSkillLevel` by 1 per step (`Liveness/Plan.lean:358-368`, `GatherProgress.lean:1-10`). Its docstring calls it "the single-level abstraction of the planner-native `LevelSkill` action grind". Production `GatherAction.apply` levels nothing, so this is a fiction the proofs rely on.
    - It discharges `SkillGapClosure.skill_prerequisite_reachable` / `skill_gap_then_complete_reachable`, `ProgressAction.step_decreases_measure` (measure slot 4, `skillXpDeficitProjected = target - tracked`), `RecipeChainClosure.recipe_then_complete_reachable`, and the `.gather` branch of `CycleStep.cycleStep_progress_or_waits`.
    - Macro-only models, with no Lean dependents: `ActionApplicability.levelSkill*` (six theorems, Oracle keys, `test_level_skill_diff.py`, the mutation groups) and the A* landmark `PlannerAdmissibility.skillGrind_*`. These retire with the macro in 2d-b/2d-c.
    - `Decompose.lean` (the one walk) is imported by no liveness file.
  - **Finding: the walk's feasibility is optimistic on a shared, capped material.**
    - `can` checks each input of a route against the whole bag, so sibling inputs that share a material both count the same stock.
    - Reproduced on `decompose_core`: X needs 2 A + 1 B, B needs 2 A, the bag holds 2 A, and A has no route. The walk says X is feasible and steps "craft B"; after that craft X is infeasible.
    - The Lean theorems are true of the definition (they never claim joint feasibility), but "feasible" over-promises, and a convergence theorem ("following the steps reaches the goal") would be false.
    - It bites only when a material with a capped route (the bag, a bank withdraw, a licensed recycle) is shared across a recipe's branches with no uncapped route behind it. Gathered and crafted leaves are uncapped.
  - **Proposed increments.**
    - **L1: the walk converges.** Model executing a step (`Act` moves `amount` into the bag, consumes `runs × per` of each input, and lowers the route's capacity by `amount`). Prove that iterating `nextStep` + execute reaches the goal from any feasible state within a bound. This needs one of:
      - (a) make feasibility JOINT: the walk threads the remaining bag and capacities through siblings (a fold instead of independent checks), so `can` means "can be had together". This changes `decompose_core`, its Lean mirror and the differential. It is the honest fix and closes the finding.
      - (b) keep the walk and prove convergence under a named hypothesis "no shared capped material", with a satisfiability witness and a census that counts where the hypothesis fails in the catalogue.
    - **L2: skill XP, not levels.** Replace the `+1 level per .gather` rung with skill XP. The XP-earning leg (the rung's gather or craft) adds positive XP (the `SkillXpPositive` gate), a level comes from XP against the per-level threshold, and preparatory legs (withdraw, recycle, material gathers and crafts) earn none but advance the walk's measure from L1. Measure slot 4 becomes the XP still owed to the target level. `SkillGapClosure` and `RecipeChainClosure` restate over legs.
    - **L3: rebind and retire.** Point the liveness grind at `craft_plan_gen._decompose_grind` (a new differential: its legs against the Lean walk-plus-execute). Delete the macro models together with the macro in 2d-b/2d-c.
  - **Decided (user, 2026-09-30):** (a) joint feasibility; order L1, L2, L3, then 2d-b/2d-c.
  - **L1 spec (joint walk).**
    - State threaded through the walk: the remaining bag and each route's remaining capacity. Asking for `qty` of an item takes what the bag holds first (reserving it), then fills the rest route by route; a route is usable when every input, asked in order, can be had from the state the previous input left. A failed route leaves the state as it was before it. Surplus yield (runs × yield above the amount taken) is ignored, which only under-promises.
    - The step is the first leaf of that joint witness: the first contributing route's gate, else its first input the threaded bag lacks, else the route itself. An emitted `Act` is executable in the real bag, since the threaded bag never holds more than the real one.
    - Proof roles kept: complete, sound, act/open spec, monotone in holdings, fuel. New: EXECUTE (applying an `Act` to the state) keeps the goal feasible, and a work measure (the runs of the joint witness) strictly drops, so iterating step + execute reaches the goal in at most that many steps.
    - Checks: the differential against the Lean mirror, a parity census of old vs joint answers on the live catalogue (every changed answer explained), and a performance bound on the live catalogue (the per-(item, qty) memo no longer applies as-is, and fan-out must not go exponential).
    - **Prototype measured (2026-09-30, live, 5 characters × every craftable, qty 1/5 and 10/25/60, gates shut and open):** 16,050 answers, 0 differences from the independent walk; joint worst case 0.2 ms. Behaviour-neutral on today's states: it closes a latent over-promise.
    - **Found while modelling: joint greedy is not monotone.** The root needs X and Y, Y needs M, X's first route needs M and Z, and its second is free. Without Z the walk gathers X and gives M to Y (yes). With Z, the first route becomes usable and spends the M (no). The greedy walk never backtracks across siblings; exact answers need a search that is exponential in fan-out.
    - **Decided (user, 2026-09-30):** sound greedy. `can_mono` retires. New role WITNESS (L1b): a yes means an executable leg sequence reaches the goal, and the step is its first leg. A census counts cells where the joint walk says no and the independent one yes, so false negatives stay visible. `ObtainModel.feasible` (`supply_core`, same independent over-promise) moves onto the joint walk in a follow-up increment ("one feasibility").
    - **L1a built (2026-09-30).** `Decompose.lean` threads a state (`St`: the bag left, the capacity spent per route) through `can`/`fill`/`feed`/`useRoute`/`step`/`descend`. Re-proved: COMPLETE, SOUND, VALIDITY, ORDERING (inputs on hand in the state the step started from), GATES, both fuel bounds; new `can_shrinks` (a yes only spends the bag). `can_mono` retired; `decide` witnesses show the shared bag (2 A for "2 A + a B of 2 A": no; 4 A: yes, first leaf the B), a shared bank (two asks of 2 from 3: no), and the non-monotone greedy case. `decompose_core` mirrors it (no memo; the live walks measure ≤ 0.2 ms). Differential green with two new cases; 13 core mutants, all killed (four new: capacity not threaded, siblings asked independently, a held input not reserved, the step not reserving). Census `scripts/gen_joint_walk.py` (report-only, in the gate): 642 cells, all agree; its classes are shown reachable by unit tests.
    - **L1b built (2026-09-30): WITNESS.** `formal/Formal/DecomposeWitness.lean`. `canP` runs the walk's own recursion and records its legs: for each route taken, its gates to open, its inputs' legs in order, then the route. `execStep` is the world's side: an `openGate` records the gate (opening it is a sub-task), and an `act` needs its gates opened, capacity left, `n ≥ ⌈c/yield⌉` and every input in the bag; it consumes them and credits exactly `c`, which under-counts real yield. Proved (axioms `propext`/`Quot.sound` only): `canP_state` (extraction answers exactly as `can`), `witness` (from any world covering the walk's state, the legs execute and cover what the walk promised), `feasible_witness` (from the real bag, a yes delivers `q`), `step_is_first_leg`. Invariant: execution dominates the walk with slack on the bag (`x`) and on spent capacity (`y`), and the walk never spends a route past its cap (`CapOk`). Caveat, stated in the module: gather and drop yields are averages, so a real leg can come up short; L1c settles the loop.
    - **Found: re-walking after every leg does not converge.** Random search over the real core with an executor mirroring `execStep`: 1 decline in ~155k loops. Shrunk: 2 of item 6 = one craft of (one 2 + one 4); 2 = craft of two 1; 1 has three routes (craft from one 4; a free source capped at 1; a free gather); 4 = a single banked unit. The first walk cannot craft two 1 from the single 4, so it takes the capped unit and the gather, keeping the 4 for the final craft. After the first leg the deficit is one, the craft route becomes usable for one unit, it spends the only 4, and the goal is declined, although the rest of the first plan still works. Production hits the same shape: `_walk_plan` re-walks in simulation after each leg, and `should_replan` re-decides every 20 cycles.
    - **Decided (user, 2026-09-30): commit to the plan.**
    - **L1c spec.**
      - (A) `decompose_core` extracts the legs (`canP`/`plan`, one implementation: the walker records legs as it answers). Differential: Python legs against the Lean `plan`.
      - (B) `_walk_plan` maps the whole extracted plan to actions (no simulated re-walk, no 8-leg cap, no stop after a fight), stopping only at the first gate (whose grind's legs follow, as today).
      - (C) A leg that comes up short repeats until it delivers: the cache's `step_target` (today batched gathers only) extends to fight legs for a drop, with the drop item and amount the leg was planned for.
      - (D) The periodic re-decide keeps a committed plan whose goal the arbiter re-selects and whose next leg is still applicable, instead of re-walking.
      - Formal: a Lean model of the committed loop (cursor advances when a leg's output reaches its target), proving termination from WITNESS under a fairness hypothesis (a repeated gather or fight eventually delivers), with a satisfiability witness.
    - **L1c built (2026-09-30).**
      - (A) `_Walker.can` records legs (`plan_legs`); the oracle emits the Lean `plan` and the differential compares it. Three new core mutants (gate legs dropped, the route's leg before its inputs, a route's legs dropped from the fill).
      - (B) `_walk_plan` maps `WalkAnswer.plan` whole; the simulated re-walk, `_MAX_LEGS` and the stop-after-fight are gone. The state is simulated only to size a gate's sub-grind.
      - (C) `FightAction.drop_target` (compare/repr off) is set by `_action_for` on a DROP leg. `PlanCache` arms a fight's drop and EVERY gather (a single secondary-drop gather can come up empty). The walk's gather and drop routes yield one per application, so the targets equal the leg amounts.
      - (D) `should_replan.refresh_only`: at the 20-cycle bound, a re-decide that picks the same goal keeps the committed plan and cursor (`COMMITMENT_KEPT`).
      - Formal: `formal/Formal/CommittedLoop.lean`. A stochastic leg (route with no inputs) runs as ticks until they add up to its amount. `committed_loop_delivers`: from the real bag, a yes means the committed loop delivers the goal under any fair tick schedule. `schedule_exists`: fairness is satisfiable. `execAll_dom`: execution is monotone in the world. Axioms `propext`/`Quot.sound`.
      - Live probe (scratch DB, 5 characters × 8 skills × 2 targets): 80/80 grinds served with whole plans (1-4 legs, e.g. Robby gearcrafting `Withdraw(iron_ring) → Recycle → Gather(iron_rocks×40) → Craft(iron_bar×4)`), 0 declines, ≤ 95 ms.
      - Residual: the walk's recycle yield (`recipe // 2`) and `RecycleAction.apply` disagree by one unit for an odd recipe (water_bow → ash_plank: the committed plan gathers 40 and crafts 4 where the re-walked forecast gathered 30 and crafted 3). The committed plan is the conservative one: it can make one extra unit. One recycle yield model is a follow-up.
- **Witness per increment:** `decision-census` over 24 h: `grind_search` and `search` per cycle down, `grind budget exhausted` to 0, and no drop in ok share, cycles/h or skill XP/h.
  - For the window that starts with the @e360a3f1 deploy, also check: cooking and alchemy XP/h, and crafts per request (grind crafts no longer get the whole held pile for free); consumable craft cooldowns never far above `predicted_cost`; and `action_repr` quantities that match the plan.

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
