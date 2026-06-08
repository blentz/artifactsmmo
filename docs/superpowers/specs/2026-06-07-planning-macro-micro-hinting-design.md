# Design: Macro/Micro Planning + Bank-Aware Acquisition

Date: 2026-06-07
Status: Drafting — pending design discussion (planner-architecture change)
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

### B. Macro equippable short-circuit (serves #1)
Before expanding an `ObtainItem(equippable)` step into a craft chain, check: does the
bank hold the finished equippable? If yes (and the goal isn't a multiple-requiring
TaskGoal), the obtain step is satisfied by a single withdraw — emit that, skip the
chain entirely. A pure predicate `prefer_bank_equippable(item, goal, state) -> bool`.

### C. Macro feasibility gate for objective→GOAP translation (fixes the open bug)
The strategy ranks roots (e.g. `ReachCharLevel(5)`); ensure EACH top root is
translated into a plannable GOAP goal (the char-level/combat root must yield a
combat/leveling goal, not be dropped so the bot falls through to gathering). A macro
feasibility check ("can this root reach a plannable goal within budget?") decides
whether to commit the micro planner or pick the next root — preventing both the
timeout-then-fallthrough and the deep-chain explosion.

### D. Macro/micro toggle
Expose the abstraction as a toggle/budget: plan at macro granularity (kinds of step,
bank-credited) first; descend to micro (unit quantities) only for the committed
plan's near-term steps. Keeps search bounded on deep chains.

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

## Open questions for design discussion

- Toggle granularity: per-goal flag, a global planner mode, or automatic (macro when
  estimated micro-node-count exceeds a budget)?
- Where the macro pass lives: in the arbiter (objective→goal translation) vs the
  planner (pre-expansion) vs a new layer between.
- How much of the existing `materials_to_withdraw` / `min_gathers` machinery the
  shopping-list core subsumes vs reuses.
