# Wave 6 — potions, cooking, tasks and GE as ROUTE OPTIONS

Date: 2026-08-23
Status: DESIGN, not authorised for implementation
Author task: `docs/PLAN_goal_decision_graph_waves_3_6.md` task 6.1
Parent spec: `docs/superpowers/specs/2026-08-22-goal-decision-graph-design.md` §"Wave 6"
Predecessors: `…2026-08-23-wave3-resolution-design.md` (merged as 3a),
`…2026-08-23-wave4-guards-design.md` (design, unimplemented)
Worktree read: `/home/blentz/git/artifactsmmo/.worktrees/waves-3-6` at `501d1936`

Live figures read from `~/.cache/artifactsmmo/learning.db`: **78,552 cycles,
2026-08-02T15:18Z → 2026-08-23T14:17Z. The fleet runs `origin/main`, which does
NOT carry wave 3a. Every live number in this document is PRE-FLIP.** Offline
figures are from `ai/scenario.SCENARIOS` (30) against
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, driven through the real
`GamePlayer.plan_from_state` on THIS branch (post-flip).

---

## 0. Headline conclusions

1. **There is no "cheapest route" question to invent — there are three answerers
   already, and they are already correctly separated.** `obtain_sources`
   answers EXISTENCE ("what routes can the executor serve right now"),
   `acquisition_cost.acquisition_actions` answers PRICE in planner actions, and
   the GOAP A\* answers CHOICE (it plans over the licensed action pool and takes
   whichever route is cheapest under the real edge costs). The route-option
   contract wave 6 owes is a **narrowing that names which of the three a
   `Decision` may consult, and forbids a fourth** — §2. It adds no cost model
   and no scoring surface.

2. **Cooking is the existing proof that the contract works, and nothing in the
   decision layer knows it exists.** Measured live: 33,840 cooking XP, of which
   **33,713 (99.6%) was earned by `Craft(cooked_beef×1)` and friends inside a
   `RestoreHP` plan** — the goal whose `relevant_actions` admits the `"craft"`
   tag (`goals/restore_hp.py:54`). No root, no guard, no means, no node ever
   names cooking; the planner discovered "cook and eat" as the cheapest way to
   satisfy `hp = max_hp`. Wave 6's cooking deliverable is to **state this,
   protect it, and delete the one rung that competes with it** —
   `MeansKind.MAINTAIN_CONSUMABLES`, which fired and won **3 times in 78,552
   cycles**. §1.2, §5.2.

3. **Wave 3a's ACCEPTED LOSS is bigger than wave 3a or wave 4 knew, and it took
   the bot's Grand Exchange with it.** Utility potions left the decision surface
   because `_gear_candidates_by_type` skips `stats.type_ == "utility"`
   (`tiers/objective.py:102`) and `_utility_candidates` is now unreachable from
   `decide_tree`. Pre-flip those roots won **1,183 cycles** — and **289 of the
   fleet's 314 `GeFillSellOrderAction`s (92.0%) ran under a utility-potion
   `UpgradeEquipment` goal**. The GE buy route's dominant live use was buying
   potions. Wave 4's `WhichSlotClosesTheFight` restores potions only when a
   fight is *blocked*; it does not restore the provisioning root. §1.1, §1.4,
   §5.1.

4. **Task synergy is measurably inert, and the fix is one argument.**
   `choose_taskmaster` (`tiers/taskmaster_choice.py:63`) scores task pools
   against `ctx.target_gear` — the **endgame BiS sheet**
   (`player.py:3712`), not the active link. Measured over all 30 scenarios:
   `CHAR_XP` is in the gear demand in **30/30**, so the monsters pool scores
   exactly `1.0` in **30/30** and wins **30/30**; the items pool scores in
   `[0.9814, 1.0]`, and in 2 scenarios both score exactly 1.0 and the *distance
   tiebreak* decides. That is precisely the pinning the module's own docstring
   says excluding the trunk avoids (`taskmaster_choice.py:11-17`). Re-pointing
   B at `objective_needs(resolution.root, …)` — already computed once per cycle
   at `strategy_driver.py:1470` — is the whole change. §1.3, §2.4.

5. **`GE_BID` is genuinely not a route (a posted bid fills asynchronously) and
   must stay a rung — but its gate is a SECOND-denominated second cost model
   with exactly one production caller, and it collapses to an integer.**
   `bid_vs_craft.estimate_craft_seconds` prices self-production in seconds with
   its own per-action table (`_FIGHT_SECONDS = 10.0`, `_GATHER_SECONDS = 6.0`,
   `_CRAFT_SECONDS = 5.0`), while `acquisition_cost` prices the same question in
   actions. `acquisition_cost.py:11-13` names this as the divergence the epic
   exists to remove. Because `BID_FILL_HORIZON_SECONDS = TTL_CYCLES *
   AVG_CYCLE_SECONDS`, replacing the seconds walk with
   `acquisition_actions × AVG_CYCLE_SECONDS` makes `AVG_CYCLE_SECONDS` **cancel
   on both sides**, leaving `acquisition_actions(item, qty, …) > TTL_CYCLES` —
   an integer comparison in actions against 20. §3 makes that the unit proof.

6. **Wave 6 adds ZERO new `Decision` nodes and zero new comparisons.** Every
   change is a deletion, a demotion, or re-pointing an existing question at the
   active link. That is the strongest available answer to the brief's warning
   about a fifth multiplier: there is nothing new to weight. §4.

7. **Scenario coverage is thin for three of the four mechanisms and
   STRUCTURALLY ZERO for GE.** 0/30 scenarios carry a task (wave 4's figure,
   re-measured and confirmed); 3/30 fire `craft_potions_fires`; 0/30 hold cooked
   food and cooking is never routed by the O1 census
   (`audit/open_rung_completeness.py:77`); and **GE cannot be exercised offline
   at all** — the bundle has no `ge_orders` key and the order book is loaded
   only by a live API call (`game_data.py:2099`), which
   `scenario.load_bundle_game_data` never makes. Any scenario-driven GE gate is
   vacuous by construction. §6.

---

## 1. How each mechanism enters the decision TODAY

Every row below was grep'd on this branch at `501d1936` and each reference
classified. The classification matters: this epic has repeatedly found "N
references" collapsing to zero production callers.

### 1.1 Potion crafting

| entry point | file:line | kind | verdict |
|---|---|---|---|
| `GuardKind.CRAFT_POTIONS` enum | `tiers/guards.py:87` | production | **A GUARD, at `BAND_GUARD` (0)** |
| `GUARD_ORDER` last slot | `tiers/guards.py:110` | production | lowest-priority guard, still above the objective step |
| firing predicate | `tiers/guards.py:262-263` → `potion_supply.craft_potions_fires` (`potion_supply.py:167`) | production | 9 helper reads, incl. TWO independent combat-target opinions (`primary_combat_target:29`, `unlock_boost_target`) that the root graph does not share |
| goal mapping | `strategy_driver.py:408-413` → `CraftPotionsGoal` | production | **the ONLY construction site of `CraftPotionsGoal` in `src/`**, so `selected_goal='CraftPotionsGoal'` in `learning.db` is an EXACT firing count |
| `decide_key._GUARD_REPR[CRAFT_POTIONS]` | `tiers/decide_key.py:52` | production | oracle index 11 — **`[AMENDED by the w4/w6 reconciliation]` becomes 10 after wave 4's increment 4.4**, which removes `GEAR_REVIEW` at index 8 and shifts everything above it down one (wave 4 §7, §11 C14). R5 of this document recommends wave 4 first, so an implementer reading "11" here would edit the wrong dispatch arm |
| `MeansKind.MAINTAIN_CONSUMABLES` | `tiers/means.py:121`, `:197` (`DISCRETIONARY_ORDER`), `:376` (`_fires`), `strategy_driver.py:506` | production | **a DISCRETIONARY MEANS** at `BAND_DISCRETIONARY` (5) |
| `objective.utility_potion_targets` | `tiers/objective.py:473` | production **but not a decision** | sole caller is `progression_tree._utility_candidates:131`, whose sole caller is `objective_candidates:165`, whose sole caller is **`commands/objective.py:261` — a read-only CLI diagnostic**. `decide_tree` no longer calls it (post-flip body: `progression_tree.py:507`) |
| utility exclusion from the gear sheet | `tiers/objective.py:102` (`stats.type_ == "utility"` in `_gear_candidates_by_type`) | production | why the root graph cannot see a potion |
| `EquipOwnedGoal` filling a utility slot | `BAND_COLLECT` | production | equips owned potions; never acquires |

**So: potion crafting is a GUARD (`CRAFT_POTIONS`) plus a discretionary means
(`MAINTAIN_CONSUMABLES`), and — pre-flip only — a set of ranked roots that the
flip deleted.** The third path is the interesting one and it is worth stating
precisely, because it is the "N references, zero production callers" trap
inverted: `utility_potion_targets` still HAS a production caller, but that
caller is a diagnostic command, not the decision. A grep alone reports it live.

**Live (PRE-FLIP), 78,552 cycles:**

| goal | cycles | share |
|---|---|---|
| `CraftPotionsGoal` (guard) | 2,245 | 2.86 % |
| `UpgradeEquipment(*→utility*_slot)` (the deleted roots) | **1,183** | 1.51 % |
| `EquipOwnedGear(…utility…)` | 144 | 0.18 % |
| `MaintainConsumables` | **3** | 0.004 % |

> The `EquipOwnedGear` figure is `selected_goal LIKE 'EquipOwnedGear%utility%'`.
> The wave-4 design reports 92 for the same phenomenon under a different
> pattern; both are counts of the same table over the same window and the
> difference is the pattern, not the data. Nothing in either design turns on
> which is used — the rung equips, it never acquires.

The 1,183 breaks down `small_health_potion→utility1` 576,
`fire_boost_potion→utility2` 198, `water_boost_potion→utility1` 189,
`air_boost_potion→utility1` 97, `earth_boost_potion→utility1` 84, and three
tails. **All 1,183 are unreachable post-flip.**

**Offline (POST-flip), 30 scenarios:** `craft_potions_fires` is True in **3**
(`l10_copper_adequate`, `l21_grey_material_grind`, `l22_grey_rung_grind`), and
`CraftPotionsGoal` is the goal actually selected in **1** —
`l10_copper_adequate`, where it **preempts the resolved root
`ReachSkillLevel(jewelrycrafting, 2)`**. That is a live-shaped demonstration,
reproducible offline today, of a `BAND_GUARD` rung beating the graph's answer.

### 1.2 Cooking

**Cooking does not enter the decision. There is no cooking root, guard, means,
node or goal.** The full production surface of the word:

| file:line | what it is |
|---|---|
| `tiers/skill_classes.py:43` | `_CONSUMABLE_KITCHEN = {"alchemy", "cooking"}` — a ranking-prior policy seed |
| `role_catalog.py:55` | `Role(name="fisher", gather="fishing", craft="cooking")` — a fleet role |
| `tui/widgets/map_pane.py:120`, `commands/craft.py:189`, `utils/formatters.py:329` | display / CLI |
| `audit/open_rung_completeness.py:77` | the O1 census recording that cooking is **never routed by any scenario** |

Everything else is a comment or a test. `consumable_supply.py` (the
`MAINTAIN_CONSUMABLES` core, `HEAL_STOCK_FLOOR = 5` at `:24`) is about *heal
stock*, not about cooking, and does not name the skill.

**And yet cooking is the fleet's second-largest skill-XP source.** Live
`delta_skill_xp_json` totals: woodcutting 56,173, **cooking 33,840**, alchemy
32,002, weaponcrafting 18,830, gearcrafting 12,551, fishing 5,497, mining 4,964,
jewelrycrafting 784. Attribution of the cooking XP by selected goal:

| goal | cooking XP |
|---|---|
| `RestoreHP` | **33,713 (99.6 %)** |
| `MaintainConsumables` | 127 |

and by action: `Craft(cooked_beef×1)` 14,673, `Craft(cooked_gudgeon×1)` 7,704,
`Craft(cheese×1)` 6,868, `Craft(cooked_chicken×1)` 3,102,
`Craft(fried_eggs×1)` 749, `Craft(cooked_wolf_meat×1)` 744.

`RestoreHPGoal` is the single most-selected goal in the fleet (19,079 cycles,
24.3 %). Its `relevant_actions` (`goals/restore_hp.py:40-54`) narrows the pool
to `{"recovery", "craft", "movement"}` — and that one admitted `"craft"` tag is
the entire cooking economy. **The planner found the route; no decision node
was involved.** This is the contract of §2 already working, and it is the
strongest existing evidence that a route option does not need a rung.

### 1.3 Task synergy

| entry point | file:line | kind | verdict |
|---|---|---|---|
| `choose_taskmaster(state, game_data, ctx.target_gear)` | `strategy_driver.py:483`, defined `tiers/taskmaster_choice.py:63` | production | **inside `map_means(ACCEPT_TASK)` only** — one call site |
| `ctx.target_gear` | written `player.py:3712` = `objective.target_gear.values()` (the **endgame BiS sheet**, `tiers/objective.py:349`) | production | the B the pools are scored against |
| `means_worth.means_serves` | `tiers/means_worth.py:68`, called `strategy_driver.py:1487` | production | **the worth gate** — suppresses `PURSUE_TASK` when the held task serves none of `objective_needs(chosen_root, …)` |
| `objective_needs` | `tiers/objective_needs.py:98`, called `strategy_driver.py:1470` | production | the ACTIVE LINK's `NeedSet`, computed once per cycle |
| `task_alignment.task_advances_progression` | `tiers/means.py:246` (`TASK_CANCEL` arm) | production | S-048 grey-task discard |
| `task_decision` (PURSUE/PIVOT) | `tiers/means.py:250`, `:258` | production | value-per-cycle pivot |
| `MeansKind.PURSUE_TASK` / `ACCEPT_TASK` / `TASK_EXCHANGE` / `TASK_CANCEL` / `COMPLETE_TASK` | `tiers/means.py:111-113`, `:106`, order at `:128-209` | production | rungs; `ACCEPT_TASK` was promoted to `COLLECT_REWARD_ORDER` (above the step) on 2026-08-19 |
| `synergy_core.synergy_pure` / `expected_pool_synergy` | `tiers/synergy_core.py`, consumed at `taskmaster_choice.py:26` and `means_worth.py:16` | production | the two NON-ranking consumers wave 3 §6.2 flagged; both survive the flip |
| `progression_tree._synergy_map` | `tiers/progression_tree.py:331` | **DEAD** | defined, **zero call sites in `src/`** post-flip. Wave 3b's deletion list already owns it |

**So: task synergy enters in TWO places, and only one of them is a
comparison.** `means_serves` is a *boolean* gate against the active link's
needs and is correct in shape. `choose_taskmaster` is the argmax, and its input
is wrong.

**Measured, all 30 scenarios, real `ctx.target_gear`:**

* `|ctx.target_gear| = 11` in 30/30 (the endgame sheet).
* `CHAR_XP ∈ _live_gear_demand(gd, ctx.target_gear)` in **30/30**.
* `expected_pool_synergy(monsters) = 1.0` exactly, in **30/30**.
* `expected_pool_synergy(items) ∈ [0.98148, 1.0]`, and `= 1.0` in 2 scenarios.
* `choose_taskmaster` returns `('monsters', (1, 2))` in **30/30**.

`_task_synergy` (`taskmaster_choice.py:42-54`) models a monsters task as
`{CHAR_XP: 1}`, so its synergy is 1 whenever `CHAR_XP` is anywhere in B. The
module's own docstring says the trunk was excluded from B *precisely* so this
would not happen — but the endgame gear sheet reaches `CHAR_XP` through its own
drop-routed materials, so the exclusion did not bite. **The lever is stuck.**

**Live (PRE-FLIP):** `AcceptTask` won 5 cycles in 78,552, so `choose_taskmaster`
has been consulted 5 times. `PursueTask` 0, `CompleteTask` 0, `TaskExchange` 0,
`TaskCancel` 0, `ReachCurrency` 0. 15,240 cycles (19.4 %) held a task, **all of
type `monsters`; zero `items` tasks in the whole window.**
`task_reward_observations` has **0 rows**, so
`task_decision.DEFAULT_TASK_REWARD_VALUE = 50.0` is what every task-value
comparison in the fleet has ever used.

### 1.4 Grand Exchange trading

| entry point | file:line | kind | verdict |
|---|---|---|---|
| `SourceKind.GE_FILL` | `source_kind.py:47`, emitted `obtain_sources.py:354`, priced `acquisition_cost.py:197` | production | **ALREADY A ROUTE OPTION** — route #6 in the declared priority order |
| `GeFillSellOrderAction` in a goal's pool | `goals/gathering.py:607`, `goals/progression.py:507` | production | the per-goal `relevant_actions` widening that makes the route executable |
| `GuardKind.GE_CANCEL` | `tiers/guards.py:88`, `:104` (`GUARD_ORDER`), `:264` (`_fires` → `cancel_targets`), `strategy_driver.py:414-419` → `CancelOrdersGoal` | production | **A GUARD** at `BAND_GUARD`, reads `ctx.step_profile` |
| `MeansKind.GE_BID` | `tiers/means.py:123`, `:204` (`DISCRETIONARY_ORDER`), `:326` (`_fires` → `ge_bid_candidates`), `strategy_driver.py:458` → `PostBuyBidGoal` | production | **A DISCRETIONARY MEANS** at `BAND_DISCRETIONARY` |
| `ge_bid.ge_bid_candidates` | `ge_bid.py:35`, callers `means.py:335` and `goals/post_buy_bid.py:50,66` | production | shared predicate — means and goal cannot disagree |
| `bid_vs_craft.should_bid` | `bid_vs_craft.py`, caller `ge_bid.py:54` | production | **exactly ONE production caller** |
| sell side (`GePostSellOrderAction`, `GeFillBuyOrderAction`) | `goals/discard_overstock.py:136`, `:153`; means `SELL_PRESSURED`/`SELL_IDLE` (`means.py:225`, `:303`) | production | disposal, not acquisition — out of wave-6 scope |

**Live (PRE-FLIP), by action class:**

| action | cycles | which goal ran it |
|---|---|---|
| `GeFillSellOrderAction` | **314** | 289 under `UpgradeEquipment(*→utility*_slot)`, 25 under gear roots |
| `GeCancelOrderAction` | 125 | all `CancelOrders` (the guard) |
| `GeFillBuyOrderAction` | 120 | all `DiscardOverstock` |
| `GePostSellOrderAction` | 84 | all `DiscardOverstock` |
| `GePostBuyOrderAction` | **0** | — |
| `NpcBuyAction` / `NpcSellAction` | 36 / 13 | — |

`PostBuyBidGoal` was **selected 0 times in 78,552 cycles**. So the only GE rung
on the ACQUISITION side has never won a cycle, while the GE *route* ran 314
times — **92.0 % of it (289) serving the very potion roots wave 3a deleted.**

`PostBuyBidGoal`'s own docstring (`goals/post_buy_bid.py:5-8`) states why the
bid is *not* an obtain-graph source: *"a posted bid fills asynchronously, so
this never claims to synchronously satisfy a material need"*. **That reasoning
is correct and wave 6 must not overturn it.** A bid cannot become a
`SourceKind`.

### 1.5 The grep trap, found inside this document's own subject area

The brief warns that a consumer may take a value as a **parameter** rather than
importing the class. There is a live instance here, and it is load-bearing:

```
combat_deficit.deficit_upgrade_target(state, game_data, cost_of=...)   # :164, :168
combat_deficit.<greedy walk>(..., cost_of: Callable[[str], float] | None)  # :220, :272
```

`grep acquisition_actions src/artifactsmmo_cli/ai/combat_deficit.py` returns
**only comments** (`:235`, `:242`) — yet `combat_deficit` is a production
consumer of `acquisition_cost.acquisition_actions`, injected at
`strategy_driver.py:378` and at `commands/combat_deficit_report.py:83`. A
deletion audit driven by grepping the function name would have reported
`combat_deficit` as price-blind and been wrong. **Every wave-6 audit of the
acquisition model must sweep `Callable` parameters named `cost_of` /
`price_of` / `store` in addition to the symbol itself.** The same shape holds
for `ctx.target_gear` (§1.3), `ctx.step_profile` and `ctx.combat_monster`:
all three are decisions passed as DATA.

---

## 2. The route-option contract

### 2.1 What already answers the question, and how the three are separated

This is the part the brief only gestures at, and the codebase has already
solved most of it. Three producers, three different questions:

| question | producer | shape | who consults it today |
|---|---|---|---|
| **EXISTENCE** — can the executor serve a route to this item *right now*? | `obtain_sources(item, state, game_data, ctx)` (`obtain_sources.py`) | `list[Source]` in a declared priority order | `prerequisite_graph.prerequisites._leafs` (`:138-150`, the `obtain_sources` call at `:148`), `acquisition_cost.route_options:427`, `combat_deficit._pool:106` |
| **PRICE** — what would it cost to obtain `qty` of it, over every route, including making a route ready? | `acquisition_cost.acquisition_actions(item, qty, state, game_data, ctx, equip, store)` (`:503`) | `int`, **planner actions** | `strategy_driver.py:378` (the GEAR_REVIEW deficit cost), `tiers/skill_grind_target.py:306`, `tiers/branch_objective.py:210` (dies with 3b), two CLI commands |
| **CHOICE** — which route does the plan actually take? | `GOAPPlanner` A\* over the licensed action pool | a plan | every goal, every cycle |

The separation is not accidental and is documented at both ends:
`acquisition_cost._gated_craft_option` (`:286-300`) states the seam —
*"`obtain_sources` answers READINESS … this module answers a different question
… That distinction is real, but it is also how a second route model creeps back
in"* — and pins it with a census
(`test_the_pricer_adds_nothing_but_gated_crafts`).

**The whole content of the wave-6 contract is: a `Decision` may consult (1) and
(2), must never consult (3), and must never add a (4).**

### 2.2 The contract

Add ONE module. It contains no behavioural class — it is a total dispatch over
`MetaGoal` kinds, in the same shape and with the same drift assertion as
`prerequisite_graph.prerequisites` (`:164-173`).

```python
# src/artifactsmmo_cli/ai/decisions/route.py  (new)
"""The ONE cost question a `Decision` may ask, and the ONE existence question.

A `Decision` selects a child. When two candidate children are genuinely
alternatives — not two arms of a branch — the node needs a comparison, and
this module is the only place it may get one. Two functions, both thin:
neither computes anything; each forwards to the single existing producer.

WHY A MODULE AND NOT A DIRECT CALL. Three reasons, all of them from this
epic's own scar tissue:

  * ONE SYMBOL TO GREP. `acquisition_actions` already has a production
    consumer invisible to its own name (`combat_deficit`, via a `cost_of`
    callback -- see the wave-6 design §1.5). A named funnel that every node
    imports keeps the consumer census answerable.
  * ONE UNIT. Every arm below returns PLANNER ACTIONS. The dispatch is total
    over `META_GOAL_KINDS` and asserts on drift, so a new root kind cannot
    silently return an unpriced 0 -- the failure mode `objective_needs`
    suffered when `ReachSkillLevel` became reachable at the flip
    (`tiers/objective_needs.py:103-114`).
  * ONE BUDGET. `route_price` is EXPENSIVE (see the call-budget rule below).
    A funnel is where a budget can be stated and a memo can live; scattered
    call sites are where 33.9s ranking walks came from.
"""

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.tiers.meta_goal import (
    META_GOAL_KINDS, MetaGoal, ObtainItem, ReachCharLevel, ReachSkillLevel)


def route_exists(code: str, state: WorldState, game_data: GameData,
                 ctx: SelectionContext) -> bool:
    """Can the executor serve ANY route to `code` this cycle?

    A pure forward to `obtain_sources`. It is the question
    `prerequisite_graph._leafs` already asks (`:148`), lifted so a root-graph
    node can ask it without importing the prerequisite walk. CHEAP: no cost
    walk, no closure, no learning store.

    A node facing "is this child reachable at all" asks THIS, never
    `route_price(...) < UNOBTAINABLE_PER_UNIT`. The two agree today, and the
    price form costs a full closure walk to learn a boolean.
    """
    return bool(obtain_sources(code, state, game_data, ctx))


def route_price(goal: MetaGoal, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None) -> int:
    """PLANNER ACTIONS to satisfy `goal` by the cheapest route the executor
    can currently serve, including the cost of making a route ready.

    THE UNIT IS PLANNER ACTIONS, on every arm, and that is load-bearing --
    see `acquisition_cost_core`'s "THE CURRENCY IS ACTIONS" contract and S-004.
    Nothing that is not an action count may enter: no gold price, no level
    gap, no wall-clock cooldown, no travel distance. A caller that needs
    seconds converts ONCE, at the call site, by the published
    `ge_order_config.AVG_CYCLE_SECONDS`, and says so.

    A LOWER BOUND, never an estimate. `acquisition_cost_core`'s soundness
    contract resolves every modelling choice downward because its consumers
    PRUNE with it. A caller that RANKS with it inherits the known bias:
    whatever is most under-priced wins. `_gated_craft_option`'s
    "AN UNPRICEABLE GRIND DECLINES THE ROUTE" note (`acquisition_cost.py:310`)
    is the live instance -- a free-looking grind captured R2D2 for 4.5 hours.

    NOT CACHEABLE ACROSS CYCLES. `UNOBTAINABLE_PER_UNIT` is charged for an
    item with no route THIS cycle; `acquisition_cost_core:60-83` states that a
    consumer which caches the bound across cycles breaks its own soundness
    argument.
    """
    if isinstance(goal, ObtainItem):
        return acquisition_actions(goal.code, goal.quantity, state, game_data,
                                   ctx, equip=goal.slot is not None,  # C11: the ONE equip rule
                                   store=history)
    if isinstance(goal, ReachSkillLevel):
        # Cycles ARE actions -- `skill_grind_cost_core`'s own headline. This
        # is the same term `acquisition_cost._gated_craft_option` charges as
        # `unlock_actions`, so a skill-gated ObtainItem and a bare
        # ReachSkillLevel price the same climb identically.
        ...
    if isinstance(goal, ReachCharLevel):
        # `PathPlan.total_cycles` is "CYCLES -- planner actions"
        # (`projections.py:263`) and counts the WHOLE combat loop.
        # `blocked` -> UNOBTAINABLE_PER_UNIT, never `inf`: the walk needs a
        # total order (see UNOBTAINABLE_PER_UNIT's "It is NOT infinity").
        ...
    assert not isinstance(goal, META_GOAL_KINDS), (
        f"{goal!r} is in META_GOAL_KINDS but route_price has no arm for it")
    raise AssertionError(f"unhandled MetaGoal kind: {goal!r}")
```

**THE CALL-BUDGET RULE, and it is part of the contract, not advice.**
`route_price` is expensive: `tiers/skill_grind_target.py:347` records a 15.1 s
planning budget *"essentially all `acquisition_actions`"*, and the `objective`
CLI measured a live ranking walk at 33.9 s against a documented 300 ms. So:

> A `Decision` may call `route_price` **at most once per candidate child, and
> only when the node has more than one child that is a genuine alternative**.
> **`[AMENDED by the w4/w6 reconciliation]` A call that INJECTS a pricing
> callback into a helper counts as one call per candidate the helper prices,
> not as one call.** Wave 4's `WhichSlotClosesTheFight` makes one textual call
> to `deficit_upgrade_target` which prices 22 candidates behind a `cost_of`
> closure (`strategy_driver.py:374-379`) — the §1.5 grep trap inverted into a
> budget-evasion. Without this sentence the rule does not bind the one node
> that most needs it (wave 4 §9.1 R1, §11 C24).
> It may never appear inside a `sorted(...)` key over a list of unbounded
> length, and never inside a loop over the gear sheet. A node that needs to
> rank a LIST ranks it on an integer with a meaning
> (`WhichSlotIsFurthestBehind`'s `_tier_gap`, `root.py:193`) and prices only
> the winner.

This rule is what stops the contract from re-creating the exponential fan-out
walk the unified-acquisition epic shipped and had to withdraw.

### 2.3 How the answer composes with the existing acquisition model

It does not compose — it *forwards*. Stated as invariants a reviewer can check:

* **`route_price` introduces no route.** Its `ObtainItem` arm is one call to
  `acquisition_actions`, whose routes come from `obtain_sources` plus exactly
  the two deferred options `route_options` (`:427-446`) already adds. The
  existing census `test_the_pricer_adds_nothing_but_gated_crafts` continues to
  be the pin; wave 6 adds nothing it must be extended for.
* **`route_exists` introduces no readiness rule.** It is `bool(obtain_sources(…))`
  with no filtering. If a node needs a *narrower* readiness question, that
  narrowing belongs in `obtain_sources` (one edit, every consumer gains it —
  `obtain_sources.py:17-20`), never in `decisions/route.py`.
* **No `Decision` may branch on `SourceKind`.** `RouteOption.kind` is
  documented as *"carried for diagnosis … Never decides anything here — the
  walk picks on cost alone, so adding a route kind cannot silently change an
  ordering"* (`acquisition_cost_core.py:93-96`). A node that branches on
  `kind is SourceKind.BUY` re-creates the venue policy the price walk owns.
  **This is the single rule most likely to be violated by a GE or potion
  feature request.** O8 (§5) is the census that catches it.
* **The planner still chooses.** Nothing in the contract narrows a goal's
  `relevant_actions`. `RestoreHP` cooking (§1.2) and `GeFillSellOrder` under a
  gear root (`goals/gathering.py:607`) are both A\* choices and both stay
  choices.

### 2.4 How a task becomes a FUNDING ROUTE for the active link

The mechanism already exists in three pieces, all live, none joined up:

1. **The active link is already published.** `strategy_driver.select` binds
   `ctx.step_profile = _step_protection_profile(step_goal, …)`
   (`:986`, `:995`) — the resolved step goal's material demand — and every
   consumer below that line sees it. `GE_BID` and `GE_CANCEL` already read it
   (`ge_bid.py:48`, `guards.py:264`).
2. **The active ROOT's unmet needs are already computed.**
   `objective_needs(chosen_root, state, game_data)` at
   `strategy_driver.py:1470`, once per cycle, producing
   `NeedSet(materials, skill_xp, buy_only, char_xp)`.
3. **A task is already gated on serving them.** `means_serves`
   (`tiers/means_worth.py:68`) suppresses `PURSUE_TASK` when the held task's
   four output kinds overlap the `NeedSet` in zero places.

**Wave 6's change is one argument and one deletion.**

```python
# strategy_driver.py:483 (map_means, ACCEPT_TASK arm) -- BEFORE
chosen = choose_taskmaster(state, game_data, ctx.target_gear)

# AFTER
chosen = choose_taskmaster(state, game_data, link_demand(needs))
```

where `needs` is the SAME `NeedSet` the worth gate computes this cycle (hoisted
above `_build_candidates` and threaded, not recomputed — one producer), and

```python
def link_demand(needs: NeedSet) -> frozenset[str]:
    """The ACTIVE LINK's unmet demand, as the codes a task pool is scored
    against. `materials | buy_only`; NEVER `char_xp`.

    `char_xp` is excluded for exactly the reason `taskmaster_choice`'s
    docstring already gives -- "the char-level trunk is deliberately excluded,
    because it always demands `char_xp` and would make every combat task score
    a perfect 1, pinning the choice to monsters". Measured 2026-08-23: the
    endgame sheet reaches CHAR_XP through its own drop-routed materials, so the
    exclusion did not bite and monsters won 30/30 scenarios at synergy exactly
    1.0. Excluding the TOKEN rather than the ROOT is what makes the exclusion
    hold.

    A `ReachCharLevel` root yields an EMPTY demand here, and that is correct:
    when the active link IS "level up", no items task serves it and
    `choose_taskmaster` should return None (fall back to the default master),
    not score every monsters task a perfect 1.
    """
    return needs.materials | needs.buy_only
```

**This is what "a funding route for the ACTIVE link rather than a rival
objective" means operationally**: the task's *distribution* is steered by what
the resolved root actually lacks, and the task's *selection* is already gated
by the same set. A task that funds the link is admitted; a task that does not
is suppressed by a gate that already exists. No new rung, no new score.

### 2.5 When the task's reward is a CURRENCY rather than the item

This is the case the brief singles out, and it is the one place the existing
machinery is genuinely incomplete rather than merely mis-pointed.

**What exists.** `CanIAffordTheCurrencyLeaf` (`decisions/obtain_item.py:50-80`)
is the FIRST node of the step graph. It calls
`analyze_currency_leaves({step.code: step.quantity}, state, game_data)` and, if
the closure is blocked on an *unaffordable currency-buy leaf*, returns
`ReachCurrencyGoal(currency, amount)` — a goal whose whole plan is the task loop
(`AcceptTask + one progress action + CompleteTask`, `goals/reach_currency.py:24`),
bounded by `funding_cycles_pure`. **That is already "a task as a funding route
for the active link", built, proved, and wired.**

**What is wrong with it, measured.**

* It has fired **0 times in 78,552 live cycles** (`ReachCurrency%` = 0), and it
  cannot fire offline either — 0/30 scenarios carry a task.
* Its trigger is *affordability of a purchase-only leaf*, not *cheapness of a
  route*. A material that is craftable but whose cheapest route is a
  currency-priced NPC buy never reaches it: `analyze_currency_leaves` requires
  the leaf to have **no recipe, no resource drop, no monster drop**
  (`goals/currency_demand.py:5-10`).
* Its funding arm mints **only `tasks_coin`**
  (`decisions/obtain_item.py:70-74`): a gold-priced or event-only leaf is
  classified `blocked` and pruned, but is **not routed** — so the bot can be
  blocked on 20,000 gold with no node saying so.

**The wave-6 rule, stated so an implementer can build it and a reviewer can
refuse an over-reach:**

> A task is a FUNDING ROUTE when the active link's cheapest priced route
> carries a currency `inputs` edge the character cannot currently pay, and the
> task loop mints that currency. It is a RIVAL OBJECTIVE in every other case,
> and stays governed by `means_serves`.
>
> The currency edge is **not re-derived**. `RouteOption.inputs` already carries
> it: *"purchase CURRENCIES alike — so a vendor item priced in `event_ticket`
> pulls in however the tickets themselves are obtained"*
> (`acquisition_cost.acquisition_options:449-460`), and `_owned_with_gold`
> (`:481`) already makes gold a payable input. So the funding question is
> answerable from the SAME price walk `route_price` runs, with no second
> closure:
>
> ```
> gap(currency) = the shortfall the price walk charged at UNOBTAINABLE_PER_UNIT
> ```
>
> A funding route exists iff `game_data.is_task_earnable(currency)` — the
> predicate `objective_needs._producible_by_self` (`:82`) already uses.

**Three consequences, each of which must be written down or an implementer will
guess:**

* **Gold is not task-earnable, so a gold gap is NOT a funding route.** It is
  earned by ordinary play and by the sell rungs. A gold-blocked link must
  report a **named wall**, not a `ReachCurrencyGoal(gold, N)` chasing a goal
  `AcceptTaskAction` cannot serve. This is the same shape as
  `obtain_item_routing.py:214-220`'s rule that a *passively accruing* currency
  (`event_ticket`, dropped by 56/58 monsters) must **not** get a dedicated
  grind, whose live diagnosis (2026-07-23) is recorded there: an over-boosted
  `event_ticket` grind out-ranked XP.
* **A funding route is a ROUTE, so it competes on PRICE, not on a rung.**
  `funding_cycles_pure` already prices the loop; `route_price` compares it
  against the alternatives for the same item. If gathering the material is
  cheaper in actions than funding the purchase, the price walk says so and no
  node has to.
* **`ReachCurrencyGoal` is `PRIORITY_WHEN_NEEDED = 1.0` — "placeholder ranking;
  demand routing is C4"** (`goals/reach_currency.py:32`). Wave 6 must not tune
  that number. It is reached from a `Decision`, not from a value comparison, so
  the placeholder is inert by construction; leave it and say so.

### 2.6 The graph after wave 6

**Unchanged.** Wave 3a's five nodes and wave 4's two, with no additions:

```
IsAFightBlockingMe          [wave 4]
  yes -> WhichSlotClosesTheFight   [wave 4]  -- may return a POTION (§5.1)
  no  -> IsMyGearBehindMyTier      [wave 3a, root.py:227]
           -> WhichSlotIsFurthestBehind / IsThereACombatTarget / …
```

Wave 6 changes what the *existing* nodes and rungs may consult, and deletes
three rungs. That is the design. §5 is the migration.

---

## 3. UNITS

This project shipped a cost in seconds read as cycles (~80x) and recorded that
**a structural diff CANNOT catch a unit error**. So:

**The contract's unit is PLANNER ACTIONS, as an `int`.** `route_price` returns
actions on every arm. It is comparable to:

* `acquisition_actions` (`acquisition_cost.py:503`) — by identity, it *is* that
  function on the `ObtainItem` arm;
* `skill_grind_cycles` (`skill_grind_cost_core.py:40`) — *"THE UNIT IS CYCLES,
  WHICH ARE ACTIONS … no seconds anywhere on the path. That is the whole reason
  this can be added to an acquisition cost at all (S-004)"*;
* `PathPlan.total_cycles` (`projections.py:263`) — *"denominated in CYCLES —
  planner actions"*;
* `funding_cycles_pure` (`goals/funding_core.py`), whose
  `ACTIONS_PER_CYCLE = 3` is stated as *exact for the planning `apply` model*
  (`goals/reach_currency.py:24-31`).

It is **not** comparable to, and must never be summed with:
`bid_vs_craft.estimate_craft_seconds` (seconds),
`BID_FILL_HORIZON_SECONDS` (seconds), `actual_cooldown_seconds` in
`learning.db` (seconds), `rest_cooldown_core` (seconds), or any gold price.

### 3.1 The one seconds boundary, and how a reader checks it BY IDENTITY

There is exactly one place in wave 6's scope where a genuine wall-clock quantity
appears: a posted GE bid fills in real time whether or not the bot acts, so
"would self-producing have been faster than waiting?" is genuinely
seconds-vs-seconds. Today that is answered by a **second cost model**:

```
bid_vs_craft.estimate_craft_seconds(item, qty, game_data)      # seconds
  _FIGHT_SECONDS = 10.0 ; _GATHER_SECONDS = 6.0 ; _CRAFT_SECONDS = 5.0
should_bid(...)  ==>  estimate_craft_seconds(...) > bid_fill_horizon_s
```

`acquisition_cost.py:11-13` already names this as a defect: *"`bid_vs_craft`
priced through its own seconds-denominated walk (which knows drop farms but not
vendors). Two models, disjoint coverage, incomparable units."* It has **one
production caller** (`ge_bid.py:54`).

**The wave-6 replacement, and the reason it is checkable by identity rather
than by inspection.** Substitute the one published conversion —
`ge_order_config.AVG_CYCLE_SECONDS`, which is defined in the same module as the
horizon:

```
BID_FILL_HORIZON_SECONDS  =  TTL_CYCLES * AVG_CYCLE_SECONDS        # :14
self_produce_seconds      =  route_price(ObtainItem(item, qty), …) * AVG_CYCLE_SECONDS

should_bid  <=>  route_price(...) * AVG_CYCLE_SECONDS  >  TTL_CYCLES * AVG_CYCLE_SECONDS
            <=>  route_price(...) > TTL_CYCLES                     # AVG_CYCLE_SECONDS CANCELS
```

**`AVG_CYCLE_SECONDS` appears on both sides and cancels.** The comparison
collapses to an integer comparison in ACTIONS against `TTL_CYCLES = 20`. A
future reader does not have to inspect any docstring to know the unit is right —
they run the identity test:

> `test_the_bid_gate_is_unit_free`: for every biddable item in the bundle and
> for `AVG_CYCLE_SECONDS ∈ {1.0, 30.0, 3600.0}`, `should_bid` returns the same
> verdict. A gate whose answer moves when the seconds constant moves has a
> seconds term left in it.

That is a check by identity, and it is exactly the check that would have caught
the `rest_cost_pure /10` and the `cheapest_path_to_level` seconds bugs. It also
kills the failure mode where someone "improves" the estimate by adding a travel
or cooldown term: any such term breaks the cancellation and fails the test.

`bid_vs_craft.estimate_craft_seconds`, `closure_leaf_kinds` and the three
`_*_SECONDS` constants become deletable (§5.4). **`should_bid` itself stays**,
as the named predicate, with an actions-denominated body.

### 3.2 The second unit hazard: `cost_of` is typed `float`

`combat_deficit`'s injection point is `cost_of: Callable[[str], float]`
(`:168`, `:220`) and `strategy_driver.py:378` wraps the integer in `float(...)`.
A `float` named "cost" with no unit in its type is where a seconds value gets
in. Wave 6 should retype it `Callable[[str], int]` in the same commit that
moves the call site (wave 4's `WhichSlotClosesTheFight`), or — if the ratio
arithmetic at `combat_deficit.py:272-279` genuinely needs a float — rename the
parameter `actions_of`. Naming the unit in the identifier is the cheapest
durable pin this codebase has.

---

## 4. Argmax discipline — what wave 6 adds, loudly

**Wave 6 introduces NO new argmax and NO fifth ranking multiplier.** The
inventory of comparisons after wave 6, with what forbids growth in each:

| comparison | key | forbids a multiplier |
|---|---|---|
| `WhichSlotIsFurthestBehind` (wave 3a) | `(-tier_gap, -target_rung, EQUIPMENT_SLOTS.index)` — `root.py:210-224` | its own docstring + wave 3 §8 R2; `EQUIPMENT_SLOTS` order, never alphabetical |
| `WhichSlotClosesTheFight` (wave 4) | margin gain per acquisition action, `max_chain=1` — `combat_deficit.py:267-279` | wave 4 §5.1: *"the two are in DIFFERENT ARMS of a branch, never summed"* |
| `choose_taskmaster` (**wave 6 re-points, does not re-key**) | `(expected_pool_synergy, -manhattan)` — `taskmaster_choice.py:84` | unchanged key; only the INPUT `B` moves from the endgame sheet to the active link |
| `should_bid` (**wave 6 re-denominates**) | `route_price(...) > TTL_CYCLES` | an integer comparison against a named constant; §3.1's identity test fails on any added term |
| `route_price` itself | a single `int` | §2.2's call-budget rule forbids it inside a sort key over a list |

**The one place pressure will come from, named in advance.** "The potion route
should be weighted against the tier gap" is the request that would turn
`route_price` into a scale. It must be refused for the wave-4 reason repeated
verbatim: the potion arm and the tier arm are **different arms of a branch**
(`IsAFightBlockingMe`), never summed, and that is exactly why neither needs a
scale. If someone can exhibit a state where both arms are live and must be
compared, that is a bug in the branch condition, not a missing multiplier.

**A note on `expected_pool_synergy`.** It survives wave 6 as a comparison, and
§1.3 measured it as having no discriminating power on its current input. After
re-pointing (§2.4) it may still not discriminate. **That is a measurement wave 6
owes (O9, §5), not an assumption**: if the re-pointed lever still returns the
same master in ≥28/30 scenarios, `choose_taskmaster` is a dead comparison and
should be DELETED rather than kept as decoration. A comparison that cannot
change an answer is the shape this epic exists to remove.

---

## 5. The design, increment by increment

Five increments. Each leaves `bash formal/gate.sh` green. Only 6.2 and 6.3 can
change what a live character does.

### 5.0 — Scenarios first (PREREQUISITE, not a nice-to-have)

§6 measures the coverage: 0/30 tasks, 3/30 potion firings, 0/30 GE (structural),
cooking never routed. **Every assertion in 6.1-6.4 is vacuous without new
fixtures.** Deliverables:

* **≥3 task-carrying scenarios** — this is wave 4's increment 4.0 and wave 6
  should NOT duplicate it. If waves 4 and 6 ship independently, whichever lands
  first owns the fixtures. Wave 6 additionally needs **one `items`-type task**
  (0 in 15,240 live task-cycles; the whole items-task economy is unobserved) and
  **one task whose reward is a currency an active link needs** (for §2.5).
* **A GE order book in the bundle.** `gamedata_bundle.json` has no `ge_orders`
  key (keys: `achievements, bank, effects, events, fetched_at, items, maps,
  monsters, npcs, resources, tasks, version`) and the book is loaded only by
  `GameData._load_ge_orders(client)` (`game_data.py:2099`). Without at least one
  standing buy order and one standing sell order in the fixture, `GE_FILL` can
  never be produced offline and `buy_post_price` always returns `None`. **This
  is a bundle-schema change and `test_gamedata_bundle.py` will need to admit
  the new key.** It is the single highest-value fixture in this plan: it turns
  the bot's most-used GE route (314 live actions) from untestable to testable.
* **One potion-closes-the-fight scenario**, which wave 4 §6.3 also asks for.
  Same ownership rule.

Assert against **today's** behaviour, before any of 6.1-6.4, so the later diffs
are against recorded numbers.

### 5.1 — `decisions/route.py`, and nothing calls it yet

`route_exists` + `route_price` as specified in §2.2, plus its total-dispatch
drift assertion and its own test module. **No production caller in this
increment.** This is the `acquisition_cost_core` "INERT ON ARRIVAL" discipline
(`:53-57`) applied deliberately: the model lands and is pinned before any
consumer switches.

Mutation anchors required in the same commit (each resolving to exactly one
site): the `ObtainItem` arm's `equip=` argument, the `ReachCharLevel` arm's
`blocked → UNOBTAINABLE_PER_UNIT` substitution, and `route_exists`' `bool(...)`.

### 5.2 — Cooking: delete the rival, protect the route

* **Delete `MeansKind.MAINTAIN_CONSUMABLES`** and its three sites
  (`tiers/means.py:121`, `:197`, `:376`; `strategy_driver.py:506`;
  `goals/maintain_consumables.py`; `consumable_supply.maintain_consumables_fires`
  at `:136`). 3 wins in 78,552 cycles. Its stated job — *"you cannot rest DURING
  a fight"* (`consumable_supply.py:14-15`) — is served by the utility-slot
  provisioning the `CRAFT_POTIONS` guard does and by `RestoreHP`'s own cook-then-
  eat route, and wave 4 §6.2 already corrects two documents that named it as a
  surviving safety net.
  **Check before deleting, and the counts are not uniform:** `heal_stock`
  (`consumable_supply.py:31`) has exactly one consumer,
  `goals/maintain_consumables.py:89`, and **dies with the rung**; but
  `HEAL_STOCK_FLOOR` and `heal_stock_target` (`:79`) are consumed by
  `inventory_keep.py:62,234` (the keep ladder's heal floor) and `best_held_heal`
  by `strategy_driver.py:586`. **The module does not die, the rung does** — and
  an implementer who deletes `consumable_supply.py` breaks the in-bag keep
  ladder. `decide_key`/`DecideKey.lean` carry a `MeansKind` index — retiring an
  enum member is an oracle renumber (§7 of the wave-4 design sizes the analogous
  cost for `GuardKind`); prefer leaving the enum member and removing it from
  `DISCRETIONARY_ORDER` if the renumber is not affordable in this increment, and
  say which was chosen.
* **Protect the route with a test, not a comment.**
  `test_restore_hp_may_cook`: a scenario whose cheapest path to `hp = max_hp`
  is a craft asserts that `RestoreHPGoal.relevant_actions` still admits the
  `"craft"` tag and that the resulting plan contains a `Craft`. Today nothing
  pins that tag; deleting it would silently remove 99.6 % of the fleet's cooking
  XP and nothing would fail.

### 5.3 — Potions: restore the provisioning route without restoring the rung

**The problem.** Post-flip, the only potion acquirer is the `CRAFT_POTIONS`
guard at `BAND_GUARD`, which preempts the objective step — demonstrated offline
today in `l10_copper_adequate`, where `CraftPotionsGoal` beats the resolved root
`ReachSkillLevel(jewelrycrafting, 2)`. Wave 4 recommends KEEPING that rung, with
four arguments (`wave4 §6.1`), the strongest measured: demoting it below the
step is deletion, because the sibling rung that already sits there fired 3 times
in 78,552 cycles.

**This design agrees with wave 4 and does not contradict it.** But wave 4's §6.3
restoration — potions return only through `WhichSlotClosesTheFight`, i.e. only
when a *held task's monster* cannot be beaten — is **insufficient for the 1,183
cycles and 289 GE fills wave 3a removed**, and here is why, measured:
`has_combat_deficit` requires `state.task_type == "monsters"` with a workable
task (`combat_deficit.py:137-143`). The fleet held such a task in 15,240 of
78,552 cycles (19.4 %). **The potion route is therefore reachable in at most
19.4 % of cycles under wave 4 alone**, and the 1,183 potion-root cycles were not
gated on holding a task at all.

**The wave-6 addition, and it is small.** `craft_potions_fires` already asks the
right question — *"is the equipped utility stack below the combat-justified
baseline"* — and already self-quiets. What is wrong is only its BAND. So:

* **Keep the rung and its predicate exactly as they are** (wave 4 §6.1 (a)-(d)
  all still hold).
* **Add a `WhichSlotClosesTheFight` sibling condition, not a new node**: wave 4's
  `IsAFightBlockingMe` fires on `ctx.combat_monster is None AND
  has_combat_deficit(...)`. Wave 6 proposes **no change to that condition** —
  widening it is exactly the freeze shape wave 4 §5.3 argues against.
* **Instead, make the GUARD's goal cheaper to satisfy by giving it the route it
  lost.** `CraftPotionsGoal.relevant_actions` should admit the same
  `GeFillSellOrderAction` widening `GatherMaterialsGoal` and
  `UpgradeEquipmentGoal` already carry (`goals/gathering.py:607`,
  `goals/progression.py:507`). **That single change is what recovers the 289 GE
  fills**: pre-flip those fills happened because the potion root was an
  `UpgradeEquipmentGoal`, which carries the widening; the guard's goal does not.
  It is a route restoration inside an existing rung — no band change, no new
  comparison, no `ObtainItem.is_satisfied` change (wave 4 §6.1 (b)'s
  quantity-blindness objection does not arise because no potion root is
  created).

**What this deliberately does NOT do**, and the reason must be recorded so it is
not re-litigated: it does not put potions back on the tier ladder.
`_tier_gap` is defined in ladder rungs (`root.py:193-207`) and utility potions
are level-exempt by design (`tiers/objective.py:474`), so a potion's "gap" and
an iron shield's would be two unrelated scales in one column — the precise
defect wave 3 deleted (`root.py:6-8`). Wave 4 §6.1 (c) states this and it is
correct.

**Cleanup in the same increment:** `objective.utility_potion_targets` (`:473`),
`progression_tree._utility_candidates` (`:131`) and
`progression_tree.objective_candidates` (`:165`) are reachable only from
`commands/objective.py:261`. Either keep them explicitly as a diagnostic (and
say so in their docstrings, because today they read as decision code) or retire
the `objective --candidates` view with them. **Do not let a diagnostic-only path
keep reading as the decision** — that is how the next reader concludes potions
are still ranked.

### 5.4 — GE: one cost model, and the rung keeps its band

* **`bid_vs_craft.should_bid` re-denominated** per §3.1: body becomes
  `route_price(ObtainItem(item, qty), …) > TTL_CYCLES`. Delete
  `estimate_craft_seconds`, `closure_leaf_kinds`, `_FIGHT_SECONDS`,
  `_GATHER_SECONDS`, `_CRAFT_SECONDS`. **Consumer count before deleting:**
  `should_bid` 1 (`ge_bid.py:54`); `estimate_craft_seconds` 0 outside its own
  module and tests; `closure_leaf_kinds` 0 outside its own module and tests.
  `ge_bid_candidates`' `bid_fill_horizon_s` parameter becomes
  `bid_horizon_actions: int = TTL_CYCLES`, and `BID_FILL_HORIZON_SECONDS` loses
  its last caller — **check `TTL_CYCLES`'s other consumer
  (`cancel_selection`'s TTL) before touching the constant.**
* **`MeansKind.GE_BID` keeps its rung and its band.** It has won 0 of 78,552
  cycles, which is a reason to ask whether it works, not a reason to delete it:
  its precondition needs a live order book, and §6 shows the fleet's book is
  reachable (314 fills) while its *post* path has never been exercised. Deleting
  an unfired rung whose gate was mis-denominated would delete the fix along with
  the feature. **Re-measure after the re-denomination and decide then** — that
  is O9's second half.
* **`GE_CANCEL` and the sell rungs are out of scope.** They are disposal and
  capital release, not acquisition; wave 6's subject is route options for an
  acquisition. Say so, so an implementer does not widen.
* **Do NOT make a posted bid a `SourceKind`.** `goals/post_buy_bid.py:5-8` gives
  the reason (asynchronous fill) and `source_kind.py:38-40` already encodes it:
  *"A GE order we might POST is speculative and may never fill, so it is not a
  route."* Any wave-6 proposal that adds `GE_POST` to `SourceKind` is refused by
  this paragraph.

### 5.5 — Tasks: the funding re-point

* `choose_taskmaster`'s third argument becomes `link_demand(needs)` (§2.4).
  `objective_needs(chosen_root, …)` is hoisted above `_build_candidates` and
  threaded to `map_means`; it must be computed **once** (it walks the
  requirement closure) — today `_worth_gate_suppressed` computes it at
  `:1470` and `map_means` does not see it.
* `link_demand` lives beside `NeedSet` in `tiers/objective_needs.py` (a pure
  projection of a value object, not a behavioural class — the CLAUDE.md
  one-class rule permits it).
* **The currency-funding widening of §2.5 is a SEPARATE increment and should be
  scoped out of wave 6 unless 5.0 delivers the items-task fixtures.** With 0
  items tasks in 78,552 live cycles and 0/30 scenarios, building it now is
  building against nothing. Record the design (§2.5) and the gate
  (O7) and defer the code. **This is the honest call, not a hedge**: this epic
  has now three times shipped a mechanism into a set where it was unreachable.

---

## 6. Scenario coverage — measured, and it changes what wave 6 can verify

Driven through the real `GamePlayer.seed_offline` + `plan_from_state` on this
branch, 30 scenarios, bundle as committed.

| mechanism | scenarios exercising it | note |
|---|---|---|
| **Tasks** | **0 / 30** | `ScenarioCharacter.task` (`scenario.py:84`) defaults `None` and is set by nobody. Confirms wave 4 §0.6 independently. Therefore `has_combat_deficit` is False 30/30 and `PURSUE_TASK`/`TASK_CANCEL`/`means_serves`' task arms are unreachable offline |
| **Potions** | **3 / 30** fire `craft_potions_fires`; **1 / 30** actually selects `CraftPotionsGoal` | firing: `l10_copper_adequate`, `l21_grey_material_grind`, `l22_grey_rung_grind`. Selecting: `l10_copper_adequate`, where the guard beats the resolved root. 9/30 have a utility slot equipped |
| **Cooking** | **0 / 30** hold a cooking-crafted item; cooking is **never routed** by the O1 census (`audit/open_rung_completeness.py:77`) | 20/30 have `cooking > 1` as a *level*, which exercises nothing. The `RestoreHP` cook path is untested offline |
| **GE** | **0 / 30, STRUCTURALLY** | the bundle has no `ge_orders` key; the order book is loaded only by `GameData._load_ge_orders(client)` (`game_data.py:2099`), a live API call `load_bundle_game_data` (`scenario.py:255`) never makes. So `ge_best_buy_order`/`ge_best_sell_order` return `None` for every item, `buy_post_price` returns `None`, `ge_bid_candidates` returns `[]` in 30/30 — measured both with the player's own ctx and with a step profile taken off the selected goal's `needed` map — and **`SourceKind.GE_FILL` can never be emitted offline** |
| **Task synergy** | 30 / 30 call `choose_taskmaster`, and **30 / 30 get the same answer** | `('monsters', (1,2))`; monsters synergy exactly 1.0 in 30/30, items in [0.98148, 1.0]; 2 scenarios tie at 1.0 and the distance tiebreak decides |

**What this means for a wave-6 plan, stated plainly.**

* Any acceptance criterion for **task** behaviour driven off `tests/test_ai/scenarios/`
  is vacuous today. New fixtures are a prerequisite deliverable.
* Any acceptance criterion for **GE** behaviour is vacuous today **and cannot be
  fixed by adding a scenario** — it needs a bundle-schema change. This is
  strictly worse than the task situation and is the reason 5.0 lists it first.
* **Cooking is the reverse case**: it has essentially zero offline coverage and
  enormous live coverage (33,713 XP). Its gate is therefore a *live* claim read
  from `learning.db`, not a scenario assertion. Say which kind of evidence each
  obligation rests on.
* The **potion** coverage (3/30, 1/30 selecting) is thin but non-zero and is
  enough to pin a band change. It is NOT enough to pin the GE-fill widening of
  5.3, which needs the order book.

---

## 7. Obligations wave 6 owes, and what makes each VACUOUS

Wave 3a shipped **O1** (`audit/open_rung_completeness.py`, wired into
`formal/gate.sh` phase c''' via `scripts/gen_open_rung.py --check`) and **O2**
(`tests/test_ai/test_decisions_dag.py`). Wave 4 proposes O3-O5. Wave 6 owes four
more. Each row states the residual that must be zero AND the condition under
which the census would report success over an empty set — because this project
shipped a census that reported total success over an EMPTY reference set, and
this epic produced ten decorative tests.

### O6 — ONE cost model: no `Decision` prices anything except through `route_price`

**Discharge:** a census in `src/artifactsmmo_cli/audit/`, wired into
`gate.sh`'s `--check` phase, that AST-sweeps every module under `ai/decisions/`
and asserts:

* no import of `acquisition_cost`, `acquisition_cost_core`, `min_plan_length`,
  `bid_vs_craft`, or `learning.projections` **except** in `decisions/route.py`;
* no `Callable` parameter on any `Decision.__init__` or `resolve` whose
  annotation returns a number (the `cost_of` injection shape of §1.5);
* every `Decision` subclass that compares two numbers does so on a value
  produced by `route_price` or by a named integer helper in the same module.

**Residual that must be zero:** `O6_SECOND_PRICER`.

**What would make it vacuous:** the sweep discovering zero `Decision` classes —
the exact failure `test_decisions_dag.py` guards against with `_MIN_CLASSES = 11`
/ `_MIN_EDGES = 9`. **This census must carry the same floors and the same named
pins**, and additionally a positive control: a test-local `Decision` that
imports `acquisition_cost` directly must be DETECTED by the same function, in
the shape of `test_a_cycle_is_detected`.

### O7 — every currency gap on an active link is FUNDED or NAMED

**Discharge:** extend the O1 census's grid, not a new one. For every
`(scenario, resolved root)` pair, price the root with `route_price`; for every
currency the price walk charged at `UNOBTAINABLE_PER_UNIT`, assert either
`game_data.is_task_earnable(currency)` (a funding route exists) or the currency
is classified into a named wall (`WALL_GOLD`, `WALL_EVENT_ONLY`,
`WALL_PASSIVE_ACCRUAL`).

**Residuals that must be zero:** `O7_SILENT_CURRENCY_STALL` (a gap that is
neither funded nor named) and `O7_UNEXPLAINED`.

**What would make it vacuous — and this is the important one.** With 0/30
scenarios carrying a task and 0 items tasks in 78,552 live cycles, **the funded
arm of this obligation is unreachable today**: every gap would classify as a
wall, the residual would be 0, and the gate would ship green while proving
nothing. O7 must therefore (a) print its routed-subset size the way O1's
`routing_breakdown` does — computed, not transcribed — and (b) **fail if the
funded arm is exercised zero times**, which is a `REFERENCE_SET_EMPTY` residual
in the shape of O1's `SKILL_CATALOGUE_EMPTY`. **Do not ship O7 before 5.0's
fixtures.**

### O8 — no `Decision` branches on a `SourceKind`

**Discharge:** an AST rule in the same census as O6 — no `SourceKind` member
appears in a comparison inside `ai/decisions/`. Cheap and total.

**Residual that must be zero:** `O8_ROUTE_KIND_BRANCH`.

**What would make it vacuous:** `SourceKind` being imported under an alias, or a
route kind compared by its `.value` string. The sweep must resolve both, and the
positive control is a test-local node that branches on
`SourceKind.BUY` and must be detected.

### O9 — the re-pointed levers actually discriminate

**Not a census — a measurement with a recorded threshold.** Two claims wave 6
makes that could each be false:

* **O9a — `choose_taskmaster` after the re-point.** Re-run the §1.3 measurement.
  If the chosen master is still identical in ≥28/30 scenarios AND the two pool
  scores are within 2 % in ≥28/30, `choose_taskmaster` is a comparison that
  cannot change an answer and **must be deleted, not kept**. Record the number
  either way.
* **O9b — `should_bid` after the re-denomination.** Count, across the (new,
  order-book-carrying) scenarios, how many step materials now clear
  `route_price > TTL_CYCLES`. Baseline: 0/30 today, and exactly one material in
  the whole set (`mithril_bar` in `l48_band_adequate`) clears the *seconds*
  gate. If the actions gate also admits ~1 material, `GE_BID` stays dormant for
  a reason unrelated to units and that should be said, not papered over.

**What would make O9 vacuous:** running it against the committed bundle (no
order book) or against the taskless scenarios. It is gated on 5.0.

### Inherited

**O2 (DAG)** is unaffected: wave 6 adds no node and no edge. `_MIN_CLASSES`/
`_MIN_EDGES` need no change unless wave 4 lands first (it adds two classes and
four edges). **O1** is unaffected in mechanism, but 5.0's new scenarios will
widen its routed subset — which is a *good* change that will make its
`O1_SILENT_STALL` residual reachable in more cells, and may turn currently-green
cells red. **Expect that and treat it as a finding, not a regression.**

---

## 8. Risks, and what I could not determine

### 8.1 Risks

**R1 — 5.3's GE-fill widening on `CraftPotionsGoal` is the only place wave 6
can plausibly break a live character, and it is untestable offline today.**
`CraftPotionsGoal.__init__` freezes its craft target against the seed state
(`goals/craft_potions.py:50-66`) precisely because a re-targeting goal left the
A\* with no reachable satisfying state — live 285/285 cycles with no plan. Adding
a *buy* route to the same goal widens the action set the frozen target was
computed against. Mitigation: the widening must be gated on the frozen
`_seed_target`'s code only, and 5.0's order-book fixture is a hard prerequisite.
**Do not ship 5.3 before 5.0.**

**R2 — deleting `MAINTAIN_CONSUMABLES` removes the fleet's only *inventory*
heal-stock rung.** `consumable_supply.py:1-15` distinguishes equipped-utility
provisioning (CRAFT_POTIONS) from inventory heals to drink mid-fight
(MAINTAIN_CONSUMABLES); wave 4 §6.2 explicitly corrects two documents that
conflated them. My argument for deletion is that `RestoreHP`'s cook-then-eat
route covers the *restoration* case with 19,079 cycles of evidence — but
`RestoreHP` cannot fire mid-fight either. **The honest statement: I am deleting
a rung that has fired 3 times, and I cannot prove from the data that the 3 were
worthless.** If a reviewer wants it kept, keeping it costs nothing; the rung is
inert. Prefer keeping it over an argument.

**R3 — re-pointing `choose_taskmaster` at the active link narrows B sharply, and
a narrow B is a coarse lever.** `objective_needs.materials` for a resolved
`ObtainItem` root is the *unmet closure*, and it is TINY. Measured over the 30
scenarios: **|materials| = 0 in 17, = 2 in 10, = 3 in 1**, and 2 scenarios
(`l48_band_adequate`, `l48_raid_active`) resolve to no root at all so there is no
`NeedSet`. `|buy_only| = 0` in all 30. With B that small, most tasks will score 0 and
`expected_pool_synergy` will be near-flat in the other direction. O9a is the
gate that catches this; the possible outcome is "delete the lever", and that
should be acceptable in advance.

**R4 — the `ReachCharLevel` arm of `route_price` calls
`cheapest_path_to_level`, which is slow.** `project_objective_cli_diagnostic`
recorded a live ranking walk at 33.9 s against a documented 300 ms, essentially
all of it this call plus `acquisition_actions`. The call-budget rule (§2.2) is
what keeps this safe, but the arm exists mostly for totality. **If no wave-6
caller prices a `ReachCharLevel`, consider making that arm raise instead of
compute** — an unpriceable-by-design kind is honest, and a slow arm nobody calls
is a trap for the next reader.

**R5 — wave 6 and wave 4 both want the same fixtures and both want to touch
`root.py`.** They are independent in code but not in test data. If they ship in
parallel, the task-carrying scenarios will be built twice or once badly.
**Recommendation: wave 4 first, wave 6 second**, and wave 6 inherits 4.0's
fixtures plus the GE order book.

**R6 — the enum renumber.** Retiring `MeansKind.MAINTAIN_CONSUMABLES` touches
`decide_key`, `DecideKey.lean`, `Oracle.lean` and the `test_decide_key_diff` /
`test_ladder_fires_diff` index tables, exactly as wave 4 §7 sizes for
`GuardKind`. `means.py:118-121` records that `MAINTAIN_CONSUMABLES` was
*appended last so the oracle's index dispatch stays stable* — removing it from
the middle of nothing is cheap, but removing it at all is an oracle edit.
Budget it or defer it.

### 8.2 What I could not determine

**U1 — whether the 289 GE fills under utility-potion roots were CHEAP or merely
AVAILABLE.** I measured that they happened and under which goal. I did not
measure what the alternative route would have cost, because `learning.db`'s
`predicted_cost` is per-cycle and not per-route. So my claim "the GE buy route's
dominant live use was buying potions" is measured; the claim "and that was the
right choice" is **not**, and 5.3 rests on restoring an option, not on proving it
was optimal.

**U2 — whether `CraftPotionsGoal`'s frozen-target invariant survives a buy
route.** I read `craft_potions.py:50-66` and understand the failure it prevents,
but I did not enumerate the goal's `relevant_actions` to check whether a
`GeFillSellOrderAction` for the seed target would leave `is_satisfied` reachable.
R1 is written on the assumption that it might not.

**U3 — the true live rate of `RestoreHP`-driven cooking per character.** I
aggregated `delta_skill_xp_json` fleet-wide. I did not split by character, so I
cannot say whether one fisher-role character carries all of it (which would make
the "cooking is a working route option" claim role-specific rather than general).
`skill_ledger` shows cooking levels of 12 (Robby), 5 (R2D2) — suggestive of
concentration, not conclusive.

**U4 — whether `MeansKind.GE_BID`'s 0/78,552 is caused by the seconds gate or by
the order book.** `should_bid` was False for every step material I could
measure offline, but offline the order book is empty, so `ge_bid_candidates`
short-circuits on `buy_post_price is None` before the venue choice. Live, I can
see 0 `GePostBuyOrderAction`s but the `cycles` table does not record *why* a
means did not fire. **The re-denomination of 5.4 is justified by unit hygiene
(§3.1), not by a claim that it will make the rung fire.** Anyone expecting the
latter should read O9b first.

**U5 — RESOLVED 2026-08-24 by the user; `ObtainItem.slot` IS the signal, and it
is the only one.** `acquisition_actions(..., equip=True)` adds exactly
`EQUIP_ACTIONS = 1` (`acquisition_cost.py:62`). `ObtainItem` carries
`slot: str | None`, and `IsThisTargetBlocked` constructs a slot-less
`ObtainItem` for a *material* blocker (`root.py:436`) and a slotted one for the
item itself (`:424`, `:430`).

The worry was that `strategy_driver.py:378` passes `equip=True` unconditionally
for a deficit code and might disagree. **It cannot.**
`combat_deficit.deficit_upgrade_target` is typed `-> tuple[str, str] | None`
and returns `(item_code, slot)` (`combat_deficit.py:164-169`), deriving the
slot from `ITEM_TYPE_TO_SLOTS` on the candidate's item type and REJECTING any
candidate with no slot. So every code it prices has a slot: `goal.slot is not
None` and the hand-written `equip=True` are the same value, and the second one
was duplication rather than a rival answer.

Consequently wave 4's node passes NO `equip=` argument (wave 4 §5.1, amended):
`cost_of` is widened to `(code, slot)` — the scan has already derived the slot —
and `route_price` reads `goal.slot`. One rule for the slot, one rule for equip,
no assertion beside a value that already knows.

This does NOT generalise: `goals/supply_bank.py:223` and
`tiers/skill_grind_target.py:308` pass `equip=False` for items that may be
equippable, because those callers bank or craft-for-XP rather than wear. There,
`equip` means "this character will put it on", which the item alone cannot
answer, and the parameter stays. The predicates coincide only where the value
in hand is a `(code, slot)` pair.

### 8.3 Which claims are MEASURED and which are REASONED

**Measured** (each re-derivable from a command in this document):

* all live counts in §1.1, §1.2, §1.3, §1.4 — `~/.cache/artifactsmmo/learning.db`,
  78,552 cycles, PRE-FLIP;
* the 99.6 % cooking attribution and its per-action breakdown;
* the 289/314 (92.0 %) GE-fill attribution;
* all scenario counts in §1 and §6, driven through `plan_from_state` on this
  branch;
* the taskmaster synergy values (monsters 1.0 in 30/30, items in [0.98148, 1.0])
  and `CHAR_XP ∈ B` in 30/30;
* the bundle's missing `ge_orders` key and the resulting structural GE vacuity;
* `_synergy_map` having zero call sites in `src/`;
* `should_bid` having exactly one production caller;
* `utility_potion_targets`' only reachable caller being `commands/objective.py`.

**Reasoned** (defensible, not measured):

* that the potion route restored by 5.3 will recover the GE fills (U1);
* that deleting `MAINTAIN_CONSUMABLES` is safe (R2 — explicitly flagged as the
  weakest claim in the document);
* that re-pointing B will make `choose_taskmaster` discriminate (R3, and O9a is
  the gate that decides it);
* that the `AVG_CYCLE_SECONDS` cancellation is the right unit discipline — the
  *algebra* is checkable, but that `TTL_CYCLES` actions is the right threshold
  is a judgement inherited from the existing constant;
* the whole of §2.5's funding rule, which has 0 live firings and 0 offline
  coverage to test against and is therefore DEFERRED in 5.5 rather than built.

---

## 10. `[MEASURED 2026-08-27]` O7 and O9b are NOT SHIPPED, and the numbers say why

Both obligations gate themselves on 5.0's fixtures. 5.0 delivered two of the
three things it promised — the GE order book and an items-type task cell — but
not populated step profiles or a currency-reward task. Measured against the
committed bundle with the order book HYDRATED (a quiet market makes both probes
vacuous by construction):

### O7 — not shipped. Its reference set is EMPTY.

| | |
|---|---|
| task-earnable currencies in the catalogue | 1 (`tasks_coin`) |
| resolved roots examined | 42 |
| roots with NON-EMPTY link demand | **12** — the probe is not vacuous |
| roots with a CURRENCY GAP | **0** |
| FUNDED-arm exercises | **0** |
| WALL-arm exercises | **0** |

O7's own text: *"fail if the funded arm is exercised zero times, which is a
`REFERENCE_SET_EMPTY` residual … **Do not ship O7 before 5.0's fixtures**."*
Both residuals would be trivially zero over an empty set, and the gate would go
green while proving nothing — the failure §7 calls "the important one".

**What would unblock it:** a scenario whose resolved root has a currency gap.
The catalogue supports it — `tasks_coin` is task-earnable and five other
currencies are not, so both arms exist in principle — but no committed cell
produces one. That is a FIXTURE gap, not a code gap, and it is the same
fixture gap 5.0 half-closed.

### O9b — not measurable. `ctx.step_profile` is empty in all 44 cells.

O9b counts step materials clearing `route_price > TTL_CYCLES`. Zero materials
were examined, because no committed scenario carries a step profile. The
baseline it wanted to compare against (0/30 today, one material clearing the
*seconds* gate) therefore cannot be re-taken.

The seconds gate itself is gone (increment 5.4), so the question O9b asks —
"does the actions gate admit about as few materials, meaning GE_BID stays dormant
for reasons unrelated to units?" — is still open and still worth asking. It needs
a scenario with a populated step profile.

### What this does NOT mean

Neither result is evidence that the mechanisms are wrong. O7's classification and
O9b's comparison are both unexercised, which is a statement about the FIXTURE
SET. Recording the numbers is what stops a later reader concluding either was
tried and found unnecessary.
