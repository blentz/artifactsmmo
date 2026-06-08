# Design: Macro/Micro Planning + Bank-Aware Acquisition

Date: 2026-06-07
Status: CLOSED (2026-06-08) — all four pieces (A/B/C/D) landed; see Status summary at end.
Trigger: user direction + observed planner search explosion on deep recipe chains.

## Problem

Deep crafting chains explode GOAP search. The **micro plan** (full unit expansion:
1000 copper_rocks → 100 copper_ore → 10 copper_bar → 1 copper_dagger ≈ 6000
node-steps) blows up search time; the live bot showed `UpgradeEquipment` timing out
at ~19.7k nodes (plan_len 0) and `GatherMaterials(wooden_shield)` building 43-step
plans / 21.7k nodes. The **macro plan** (copper_rocks → ore → bar → dagger, 4
*kinds* of step) is tractable. The planner needs a way to reason at the macro level
for structure/feasibility while only descending to micro quantities where needed.

This also caused two concrete live bugs:
- **Re-gather over withdraw** (FIXED, 21ef7b1, via `_BANKED_REGATHER_PENALTY` — a
  heuristic down-payment on behavior #2 below; this spec is the principled version).
- **Goal-mismatch** (OPEN): the #1-ranked objective `ReachCharLevel(5)` (fight
  green_slime to level) is never translated into a plannable GOAP combat goal — only
  `UpgradeEquipment` (timed out) + `GatherMaterials` were offered, so the bot falls
  through to gathering instead of fighting. The macro view (feasibility of a goal
  before committing the planner) is the lever to fix this.

## The two behaviors (user-specified)

### 1. Prefer a bank equippable over crafting a new one (MACRO view)
If an equippable item the objective wants is **already in the bank**, withdraw it
(1-step) rather than craft a new one (multi-step chain). Avoid redundant crafting.
- **Exception:** `TaskGoals` that require *multiples* of the item (the task needs N,
  the bank's 1 doesn't satisfy it).
- **Why macro:** the decision "1-step bank-withdraw dominates the 4-step craft chain"
  is visible only at the recipe-tree (macro) level, not from per-unit micro steps.

### 2. Bank-aware recipe shopping list (MICRO view)
When the goal is upgrade-equipment or crafting, **recurse the recipe chain to base
materials**, compiling a **shopping list** that records EVERY level's items
(intermediate + base). For each item in the list, **use what the bank already holds
(at any level) before gathering/crafting new**. E.g. if the bank has copper_bar
(intermediate), withdraw it instead of gathering copper_rocks → ore → bar.
- **Why micro:** correctly crediting bank stock at every recipe level requires the
  full per-level expansion (the shopping list), not just the macro shape.

## Proposed approach (to be refined in design discussion)

The unifying idea: a **macro feasibility/abstraction pass** that (a) prunes the
search and (b) pre-credits bank stock, feeding the existing micro GOAP planner a
much smaller problem.

### A. Recipe-closure shopping list with bank credit (serves #2)
A pure function `shopping_list(target, qty, state, game_data) -> {item: net_qty}`:
recurse the recipe tree; at each node subtract what the bank (and inventory) already
holds before expanding its sub-recipe. Bank stock at ANY level short-circuits that
subtree (withdraw it; don't expand below it). The net list is the *true* remaining
acquisition work — far smaller than the naive full expansion. The planner then only
plans for the net deficit, and withdraws are seeded for every credited bank item.
- This generalizes the just-landed `_BANKED_REGATHER_PENALTY` heuristic into a
  principled, proof-friendly pure core (dominance: a bank-credited plan is never
  longer than the gather-everything plan; correctness: the list + bank holdings
  reconstruct the recipe requirement).

### B. Macro equippable short-circuit (serves #1) — STATUS: ALREADY SATISFIED (2026-06-08)

Before expanding an `ObtainItem(equippable)` step into a craft chain, check: does the
bank hold the finished equippable? If yes (and the goal isn't a multiple-requiring
TaskGoal), the obtain step is satisfied by a single withdraw — emit that, skip the
chain entirely.

**Verified offline that this behavior is ALREADY produced by landed code — no new
`prefer_bank_equippable` predicate/module is needed (a redundant core would be inert
theater).** Evidence (repro, deleted after verification; pinned by
`tests/test_ai/test_prefer_bank_equippable.py`):

- SINGLE item, finished equippable in bank, slot empty: `UpgradeEquipmentGoal`
  surfaces the banked item via `_find_inventory_upgrade` (it scans `inventory | bank`),
  while `_find_craftable_upgrade_target` deliberately SKIPS bank-held items (so it is
  never re-crafted). `find_upgrade_target` returns the banked item, and the least-cost
  GOAP planner then chooses `Withdraw(item) -> Equip(item)` over the multi-step craft
  chain (the craft chain stays in the action set for admissibility; it is simply more
  expensive). This is the macro short-circuit, realized by ordinary least-cost search
  rather than a special predicate.

- MULTIPLES exception (task needs N, bank has < N): handled by the landed
  bank-aware `shopping_list` (Piece A). `shopping_list(item, N, recipes, owned)`
  credits the held copies at the TARGET node and expands the recipe for the REMAINDER
  `N - held`, so `fully_covered_materials` returns nothing for the target and the
  deficit's gather/craft actions survive — a single banked copy can never satisfy a
  multiples requirement. Independently, `PursueTaskGoal.is_satisfied` keys on
  server-tracked `task_progress >= task_total`, not on bank holdings, so a banked
  finished item never falsely completes a task.

Net: Piece B's single-item preference falls out of (a) `_find_inventory_upgrade`
reading the bank + (b) the craftable path skipping bank-held items + (c) least-cost
planning; its multiples exception falls out of Piece A's `shopping_list`. The honest
deliverable is the pinning test above (locks both halves so a regression fails the
build) plus this status note — NOT a new module.

### C. Macro feasibility gate for objective→GOAP translation — STATUS: LANDED (2026-06-08)
The strategy ranks roots (e.g. `ReachCharLevel(5)`); ensure EACH top root is
translated into a plannable GOAP goal (the char-level/combat root must yield a
combat/leveling goal, not be dropped so the bot falls through to gathering). A macro
feasibility check ("can this root reach a plannable goal within budget?") decides
whether to commit the micro planner or pick the next root — preventing both the
timeout-then-fallthrough and the deep-chain explosion.

**VERIFIED a real post-Piece-A gap (offline repro, deleted after verification;
pinned by `tests/test_ai/test_strategy_driver.py` +
`tests/test_ai/test_gather_step_target.py`):** the ReachCharLevel-with-no-winnable-monster
fall-through is CORRECT (the bot should gear up first — not a bug, not changed).
The genuine gap is the from-scratch DEEP equippable chain with NO bank stock
(steel_boots ← 6 steel_bar ← 8 iron_bar ← 10 iron_ore = 480 raw): Piece A credits
nothing (no bank), `UpgradeEquipmentGoal.is_plannable`'s sound
`min_gathers(480) > max_depth(15)` gate correctly defers the craft+equip, but the
arbiter's fallback then built `GatherMaterials(root, root's DIRECT recipe
{steel_bar: 6})` — whose plan must gather 480 units THROUGH the deep recipe. The
GOAP search EXPLODED: measured **1,011,121 nodes / 90s TIMEOUT / plan_len 0**, then
fall-through and the gear chain never progressed. The explosion cliff is recipe
DEPTH×count (a FLAT 480-ore gather plans in 1.7s; the 2-level 480 chain times out),
so no `min_gathers`/`max_depth` gate can distinguish them without a false-infeasible.

**Fix (sound):** route a depth-UNREACHABLE equippable root to the strategy's
DEEPEST actionable step (the raw base material) as a FLAT, budget-feasible gather
that makes incremental progress; the next recipe level becomes actionable as it
accumulates, and UpgradeEquipment fires when materials are in hand. Pure core
`src/.../ai/gather_step_target.py` (`gather_step_target`: root when
`min_gathers(root) ≤ equip_max_depth`, else the deepest step) mirrored + proven in
`formal/Formal/StepDispatch.lean` (`gatherTarget_*`): routes to the step ONLY when
the root strictly exceeds budget (a reachable root is never abandoned — the
honesty bar), and the step's flat cost never exceeds the declined root's
(PlannerAdmissibility preserved — the step is a genuine prerequisite ON the root's
path). Differential + 3 mutants. The reachable-root one-commit UpgradeEquipment
path (ash_plank/wooden_shield) is preserved. The timeout-then-fallthrough for the
deep chain is eliminated because the deep `GatherMaterials(root)` goal is never
built; the flat deepest-step gather plans within budget every cycle.

### D. Macro/micro bound on from-scratch deep chains — STATUS: LANDED (2026-06-08)
Expose the abstraction as a toggle/budget: plan at macro granularity (kinds of step,
bank-credited) first; descend to micro (unit quantities) only for the committed
plan's near-term steps. Keeps search bounded on deep chains.

**VERIFY-FIRST (offline repros, deleted after verification; pinned by new tests in
`tests/test_ai/test_strategy_driver.py`).** Measured GOAP `nodes_explored` on the
worst realistic from-scratch chain steel_boots ← 6 steel_bar ← 8 iron_bar ←
10 iron_ore (min_gathers = 480 raw, empty bank), faithfully mirroring the LIVE
action factory (`player._build_actions`: qty-1 gathers + qty-1 crafts + withdraw +
deposit):

| case | min_gathers | nodes | result |
|---|---|---|---|
| BANK-COVERED deep (Piece A credits the bars) | — | **1** | pruned, no gather |
| FLAT leaf gather `GatherMaterials(iron_ore, {iron_ore:N})` (Piece C target) | 60 / 120 / 240 / 480 | 1,960 / 4,300 / 8,980 / **18,340** | **LINEAR** (~38 nodes/unit), 0.8s @480, never times out |
| DEEP `GatherMaterials(root, DIRECT recipe)` | 24 / 60 / **480** | 2,724 / 31,513 / **655,052** | **SUPER-LINEAR**, 90s TIMEOUT @480, plan_len 0 |

So post-A/B/C the explosion is NOT subsumed: it persists wherever a depth-UNREACHABLE
equippable is routed to `GatherMaterials(root, root's DIRECT recipe)`, whose plan must
gather 480 units THROUGH the 3-level recipe (interleaving gather/craft/deposit at every
level — the cliff is recipe DEPTH×count). Piece A credits nothing (empty bank). Piece C
fixed exactly ONE such site (`objective_step_goal`, the intermediate-step path) but TWO
others survived and still built the explosive deep goal: the **GEAR_REVIEW guard**
(`map_guard`) and **`_equippable_goal`** (the objective-step equippable path). Both were
genuinely reachable (a from-scratch gear upgrade) and reproduced the live 1M-node /
timeout blowup.

**Fix (the macro/micro bound, reusing Piece C's already-proven core — NOT a new
toggle/module):** route those two sites through the SAME
`actionable_step` + `gather_step_target` machinery Piece C uses, via the shared helper
`strategy_driver._gather_goal_for_unreachable_equippable`. The deepest ACTIONABLE step
is the deepest recipe node whose DIRECT prerequisites are already satisfied — so its own
recipe is at most ONE level above raw, never the full chain. Gathering it is the micro
batch for the macro plan; the macro plan (gather leaf → craft up the chain → equip) is
reached by REPEATED cycle execution: as the leaf accumulates, the next level becomes the
actionable step (verified: with 10 banked iron_ore the routed step advances iron_ore →
iron_bar; the iron_bar sub-goal plans in 9,677 nodes / 0.6s — bounded, one level deep).
Post-fix both sites build `GatherMaterials(iron_ore)` and plan in **50 nodes / 0.01s**.

No new Lean proof is needed because no new decision logic was introduced — the bound is
the proved `gather_step_target` (`formal/Formal/StepDispatch.lean` `gatherTarget_*`:
routes only when the root strictly exceeds budget, and the step is never harder than the
declined root) composed with the proved `actionable_step`
(`formal/Formal/StrategyTraversal.lean` `actStep`). **PlannerAdmissibility is preserved**:
the routed step is a genuine prerequisite ON the root's recipe path, so a reachable goal
is never abandoned or falsely declared infeasible; progress accrues every cycle until
UpgradeEquipment fires the craft+equip. The reused cores' differentials
(`test_gather_step_target_diff` / `test_strategy_traversal_diff` / `test_shopping_list_diff`)
and the full gate stay green.

Net: D was a REAL gap post-A/B/C (not subsumed), closed by the minimal honest fix —
wiring the existing proven bound into the two unrouted sites plus pinning tests — rather
than a redundant macro/micro toggle module.

## Proof obligations (keep the gate honest)

- `shopping_list` dominance: the bank-credited net list ≤ the naive full requirement;
  reconstruction (net + bank/inv holdings = recipe requirement). Differential +
  mutation, mirroring `min_gathers`/`GatherSelection`.
- `prefer_bank_equippable` safety: never short-circuits a TaskGoal needing multiples
  (the exception is provably honored).
- Planner admissibility preserved: macro pruning must not drop a reachable plan
  (no false "infeasible"); the micro planner still finds least-cost within the pruned
  space. Do NOT hollow `PlannerAdmissibility`.

## Relationship to landed work

`_BANKED_REGATHER_PENALTY` (21ef7b1) is the interim heuristic for #2's gather case;
this spec's `shopping_list` core is the principled replacement (handles intermediates
at any level, proof-backed). The macro feasibility gate (C) also subsumes the
goal-mismatch fix. Implement incrementally: shopping-list core → equippable
short-circuit → feasibility gate → macro/micro toggle.

## Open questions for design discussion — RESOLVED (2026-06-08)

- ~~Toggle granularity~~ — No toggle was built. The macro/micro bound is AUTOMATIC and
  implicit: `gather_step_target` routes to the deepest actionable step ONLY when the root
  strictly exceeds the equip depth budget (`min_gathers(root) > equip_max_depth`); a
  depth-reachable root plans directly. No per-goal flag or global mode.
- ~~Where the macro pass lives~~ — In the arbiter (objective→goal translation), as the
  shared helper `strategy_driver._gather_goal_for_unreachable_equippable` called by all
  three equippable-routing sites (`objective_step_goal`, GEAR_REVIEW guard,
  `_equippable_goal`). Not in the planner.
- ~~materials_to_withdraw / min_gathers subsumption~~ — `min_gathers` is reused directly
  (it IS the depth-reachability gate inside `gather_step_target`); the shopping-list core
  handles the bank-credit/withdraw seeding orthogonally (Piece A).

## Status summary (2026-06-08)

All four pieces closed: **A** (shopping-list, landed 90a36f6/2e836af), **B** (prefer bank
equippable — subsumed by existing least-cost search, pinning test only), **C** (feasibility
gate / depth-unreachable routing in `objective_step_goal`, landed f58802c), **D** (the same
bound wired into the two remaining unrouted sites — GEAR_REVIEW guard + `_equippable_goal`).
The from-scratch deep-chain GOAP explosion (655k nodes / 90s timeout) is eliminated at every
equippable-routing site; flat-leaf gathers plan in tens of nodes and accrue progress every
cycle until UpgradeEquipment fires.
