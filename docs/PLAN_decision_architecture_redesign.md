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
