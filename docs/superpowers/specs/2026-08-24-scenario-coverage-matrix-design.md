# The scenario set as a COVERAGE MATRIX, not a pile of incidents

Date: 2026-08-24
Status: DESIGN. No production code, no fixture, no scenario was changed.
Worktree read: `/home/blentz/git/artifactsmmo/.worktrees/waves-3-6` at `15b95d1c`
Prompted by: "Sounds like the fixture needs expanding to cover a matrix of
common cases."

Every number in this document is either MEASURED (the command that produced it
is given inline) or LIVE (a query against
`~/.cache/artifactsmmo/learning.db`, 80,194 cycles, 5 characters,
`2026-08-02T15:18` → `2026-08-24T21:23`). §8 separates measured claims from
reasoned ones. No claim rests on a `play-trace-*.jsonl` file.

---

## 0. Headline conclusions

1. **The scenario set is not a sample of production. It is close to its
   complement.** Measured, offline, by driving `GamePlayer.plan_from_state()`
   over all 30 scenarios and comparing the selected goal class against
   `cycles.selected_goal`:

   | goal class | LIVE share | offline |
   |---|---|---|
   | `UpgradeEquipment` | **26.0 %** (20,843 cycles) | **0/30 selected** (tried 25×, never wins) |
   | `GrindCharacterXP` | 25.7 % | 2/30 |
   | `RestoreHP` | 24.1 % | 1/30 |
   | `GatherMaterials` | 12.0 % | **14/30** |
   | `ReachSkill` | 1.2 % | **7/30** |
   | `CraftPotions` | 3.0 % | 1/30 |
   | `SupplyBank(*)` | ~1.5 % | 0/30 |
   | `CancelOrders` | 0.2 % | 0/30 |

   The single largest live goal class is never selected offline, and the two
   classes the fixture selects 70 % of the time are 13 % of live cycles.

2. **The most valuable single number in this document: the whole scenario set
   never produces a planner search larger than 41 nodes.** `MAX_SEARCH_NODES`
   in `tests/test_ai/scenarios/search_bounds.py` is `200_000` — four orders of
   magnitude above anything the fixture can reach. Live, **15.2 % of cycles
   (12,181) plan a search bigger than 41 nodes**, the maximum is **129,322**,
   and 313 cycles timed out. The bound is decorative: it cannot fail.

3. **The GE gap is not a missing scenario and not even a missing bundle key —
   it is a missing key that a test actively PINS SHUT.**
   `tests/test_ai/scenarios/test_gamedata_bundle.py:test_bundle_ge_orders_empty`
   asserts `gd.ge_best_buy_order("copper_ore") is None`. Twelve call sites
   across ten production modules read the order book; all twelve are provably
   dead in every offline test. That is decorative-test mechanism 3 promoted to
   a *pinned invariant of the harness*.

4. **The dimension that gates the most other dimensions is `derive_combat_stats`,
   and its effect is not the 14/30 the brief carried.** Measured: **11/30
   scenarios have zero total attack** (10 by the declared flag, plus `l1_fresh`,
   which sets the flag but wears nothing). `obtain_sources` emits a `DROP`
   source in exactly **19/30** scenarios — the same 19 with non-zero attack. At
   zero attack the entire monster-drop half of the acquisition model is
   unreachable, which is why forcing the flag on swung the O1 census 47 → 19 → 5.

5. **Eight of the thirteen guards fire in 0/30 scenarios**, including
   `REST_FOR_COMBAT` and `GEAR_REVIEW`. `HP_CRITICAL` fires in 1/30 while
   `RestoreHP` is 24.1 % of live cycles.

6. **The matrix must not be a cross-product, and this document does not propose
   one.** Two dimension pairs INTERACT (measured, §5.1) and the rest are
   independent of each other but MASKED by the guard ladder, which is a third,
   distinct relationship that forbids parallel packing. The construction in
   §5.3 yields **12 new scenarios (30 → 42)**, costing a measured **≈3.6 s**
   against a ~100 s suite (+3.6 %) and a ~5 min gate (+1.2 %).

7. **A coverage census IS feasible and IS the right shape**, but the honest
   version has a residual it cannot close (§7.4): it can prove every DECLARED
   dimension has both sides populated; it cannot prove the declaration is
   complete. A second, mechanical check over the 17 `WorldState` fields the
   decision and guard layers actually read closes most of that, and §7.5 says
   exactly what it still misses.

---

## 1. Method

Everything below was produced with read-only probes. The full test suite and
all coverage commands were deliberately NOT run (a concurrent task shares
`.coverage`).

| what | how |
|---|---|
| scenario field census | `uv run python -c` over `ai.scenario.SCENARIOS` + `scenario_state` |
| decision-graph arm coverage | drive `decisions.root.resolve_root` and `decisions.obtain_item.obtain_item_decision` node-by-node over the 30 scenarios, recording the class of each visited node |
| guard coverage | `tiers.guards.active_guards(state, gd, None, NO_PROFILE_CONTEXT)` per scenario |
| acquisition-source coverage | `obtain_sources(code, state, gd, NO_PROFILE_CONTEXT)` for all 522 catalogue codes × 30 scenarios |
| goal-class coverage | `GamePlayer.seed_offline(...)` + `plan_from_state()` per scenario |
| O1 re-measurement | `audit.open_rung_completeness.run_census(gd)` called directly (NOT via `scripts/gen_open_rung.py`, which writes the matrix doc and would dirty the worktree) |
| runtime | `time.monotonic()` around each of the above |
| live distributions | `sqlite3 ~/.cache/artifactsmmo/learning.db` |

The bundle under test is `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`,
`fetched_at 2026-07-06T23:46:18Z`, loaded with
`GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))`.

---

## 2. The dimensions, derived from what branches the decision

I read the branch sites rather than brainstorming. The decision surface is three
layers, and each contributes dimensions:

* **the root walk** — `ai/decisions/root.py`, five `Decision` classes;
* **the step walk** — `ai/decisions/obtain_item.py`, six `Decision` classes;
* **the guard ladder** — `ai/tiers/guards.py`, `GUARD_ORDER`, thirteen kinds.

Underneath all three sits `ai/obtain_sources.py`, whose `SourceKind` set is
what the prerequisite descent leafs on
(`ai/tiers/prerequisite_graph.py:_source_leafs`).

The decision + guard layer reads exactly **17 `WorldState` fields** and
**12 `SelectionContext` fields**:

```
grep -rhoE "state\.[a-z_]+" src/artifactsmmo_cli/ai/decisions/*.py \
    src/artifactsmmo_cli/ai/tiers/guards.py \
    src/artifactsmmo_cli/ai/combat_deficit.py \
    src/artifactsmmo_cli/ai/gear_latch.py | sort -u
```
→ `bank_items equipment hp hp_percent inventory inventory_max
inventory_slots_max inventory_slots_used inventory_used level max_hp skills
task_code task_progress task_total task_type xp`

That list is the ceiling on how many state dimensions can exist, and it is the
reference set §7 builds the anti-rot check from.

### 2.1 The dimensions

| # | dimension | the branch site that makes it a dimension | values |
|---|---|---|---|
| **D1** | **combat stats present** | `IsThereACombatTarget` reads `ctx.combat_monster`, fed by `band_target.band_combat_target` → `combat.is_winnable` → `predict_win`, which reads `state.attack`. `obtain_sources._drop_sources` is gated the same way. | zero attack / derived attack |
| **D2** | **held task** | `combat_deficit._blocked_task_monster` reads `task_code`/`task_type`/`task_progress`/`task_total`; `gear_latch.py:79` arms on `has_combat_deficit`; `strategy_driver.py:381` targets `deficit_upgrade_target` | none / workable / unwinnable-with-a-closing-chain / unwinnable-with-none |
| **D3** | **GE order book** | `obtain_sources._ge_sources` (`obtain_sources.py:353`) emits `GE_FILL` iff `ge_best_sell_order` is non-None and the GE tile is known; `_source_leafs` puts `GE_FILL` in `CRAFT_SUBSTITUTE_KINDS`; 12 further call sites price against it | empty / a standing order on the item being descended |
| **D4** | **craft-rung shape** | `DoesTheRecipeNeedAMonsterDrop` branches on `_recipe_has_combat_drop_input(root)`; `DoesTheChainFitTheDepthBudget` branches on whether `gather_step_target` returns the root itself | (closure depth 0–3) × (gather-fed / drop-fed) |
| **D5** | **gear-target blocker class** | `IsThisTargetBlocked` — four typed arms, emitted by `objective._classify_target` | skill-gated / attainable / own-blocker / material-gated |
| **D6** | **inventory pressure** | `DISCARD_CRITICAL`, `CRAFT_RELIEF`, `RECYCLE_RELIEF`, `SELL_RELIEF`, `DEPOSIT_FULL`, `DISCARD_HIGH` all read `inventory_used`/`inventory_slots_used` against their caps | empty / mid / ≥75 % / ≥90 % |
| **D7** | **bank contents** | `DoesTheRecipeNeedAMonsterDrop` merges `state.bank_items` into `owned` before `gather_step_target`; the relief guards read bank capacity; the grind's WITHDRAW leaf lives here | empty / stocked with a needed material / unknown (`None`) |
| **D8** | **character level vs the ladder** | `tier_ladder.tier_of_level` over a derived ladder `(1,5,10,15,20,25,30,35,40,45,50)`; `_next_rung_above`; `milestone_pure` (BAND 10) | on a rung / mid-band |
| **D9** | **gold / currency** | `CanIAffordTheCurrencyLeaf` → `analyze_currency_leaves(...).funding_target`; `objective.is_attainable_now` reads POCKET gold only while `analyze_currency_leaves` reads pocket + known bank gold | 0 / small / ≥ a vendor price / ≥ the progression reserve |
| **D10** | **HP fraction** | `HP_CRITICAL` (`hp_percent < CRITICAL_HP_FRACTION`) and `REST_FOR_COMBAT` — both PREEMPT the whole objective | full / 50–99 % / < 50 % |
| **D11** | **skill level vs the rung's `crafting_level`** | `CanICraftCurrentTier` — the only link from a skill-gated gear target to `ReachSkillGoal` | adequate / one short / many short |

Two candidates the brief named that the code does **not** support as separate
dimensions, and one it missed:

* **"cooking"** is not a dimension. `grep` finds no cooking root, guard, means
  or goal — the skill appears only in `skill_classes._CONSUMABLE_KITCHEN`, in
  `role_catalog`'s `fisher` role, and in the O1 census's own note. Cooking
  enters the decision *only* through D4/D11 (a cooking rung is a craft rung) and
  through `RestoreHP`'s planner discovering cook-and-eat. It is a VALUE of
  D11/D4, not an axis.
* **"bank unknown"** (`bank_items is None`) is dead as a live dimension:
  `SELECT bank_accessible, count(*) FROM cycles GROUP BY 1` → `1|80194`. Never
  inaccessible in 80,194 cycles. Keep it out of the matrix.
* **MISSED by the brief: `pending_items`.** It is `None` in 30/30 scenarios,
  has production readers in `actions/claim.py` and six state-carrying actions,
  and is slot 11 (`pendingItemsFlag`) of the Lean `ExtMeasure`. It is a real,
  uncovered dimension — but see §5.4 for why it does not earn a cell.

---

## 3. MEASURED current coverage over those dimensions

### 3.1 The scenario-level table

| dim | values, as they land on the 30 committed scenarios | verdict |
|---|---|---|
| **D1** combat stats | zero attack **11/30**, derived attack **19/30** (`derive_combat_stats=True` is declared on 20/30; `l1_fresh` sets it but wears nothing) | covered both sides |
| **D2** held task | **none 30/30** — `ScenarioCharacter.task` is `None` for every scenario | **STRUCTURAL BLIND SPOT** |
| **D3** GE book | **empty 30/30**, and there is no bundle key that could express otherwise | **STRUCTURAL BLIND SPOT (schema)** |
| **D4** rung shape *(shape of the root `resolve_root` returns)* | depth-0 11/30, depth-2 gather-fed 7/30, **depth-2 drop-fed 4/30**, depth-3 **0/30**, non-`ObtainItem` roots 6/30 | badly skewed, see §3.3 |
| **D5** blocker class | over all 151 gear targets in all 30: own-blocker 61, attainable 50, skill-gated 21, material-gated 19 | all four reached |
| **D6** inventory | empty **26/30**, 0–50 % 2/30, 50–75 % 1/30, ≥90 % 1/30, ≥75 % **1/30** | near-blind, see §3.4 |
| **D7** bank | known 30/30 (0 codes in 6, 1–14 in 24), unknown **0/30** | one side only — but see §2.1, the missing side is dead live |
| **D8** level | on a rung 15/30, mid-band 15/30 | covered both sides |
| **D9** gold | 0 in 11/30, 1–99 in 1, 100–999 in 15, 1k–10k in 2, ≥10k in 1 | ≥1000 in **3/30** |
| **D10** HP | full 29/30, < 50 % **1/30**, 50–99 % **0/30** | near-blind |
| **D11** skill gate | `ReachSkillLevel` is the resolved root in 4/30 and routed (root or alternative) in **13/30**, over 3 of 8 skills only: jewelrycrafting 11, gearcrafting 6, weaponcrafting 2 | 5 of 8 skills never routed |

### 3.2 Decision-graph ARM coverage — the sharper measurement

Driving `resolve_root` over all 30:

```
root class:  ObtainItem 24/30 | ReachSkillLevel 4/30 | None (a WALL) 2/30
             ReachCharLevel  0/30
```

`ReachCharLevel` — the trunk, the outcome of BOTH `IsThereACombatTarget`'s
positive arm and `CanIClearMyTier`'s positive arm — is the resolved root in
**0/30** scenarios.

Driving `obtain_item_decision` on the 16 scenarios that produce an `ObtainItem`
step:

```
7×  CanIAffordTheCurrencyLeaf → IsTheStepTheEquippableItself → IsThisAnIntermediateOnAChain
      → CanICraftCurrentTier → DoesTheRecipeNeedAMonsterDrop → DoesTheChainFitTheDepthBudget
5×  CanIAffordTheCurrencyLeaf → IsTheStepTheEquippableItself
4×  CanIAffordTheCurrencyLeaf → IsTheStepTheEquippableItself → IsThisAnIntermediateOnAChain
      → CanICraftCurrentTier → DoesTheRecipeNeedAMonsterDrop
resulting goal:  GatherMaterialsGoal 16/16
```

Three of the step graph's six nodes have a positive arm that **never fires**:

| node | positive arm | fires |
|---|---|---|
| `CanIAffordTheCurrencyLeaf` | `ReachCurrencyGoal` (tasks_coin funding) | **0/30** |
| `CanICraftCurrentTier` | `ReachSkillGoal` — "the ONLY link from a skill-gated gear target to the skill it needs" | **0/30** |
| `DoesTheChainFitTheDepthBudget` | `UpgradeEquipmentGoal` (the root chain fits) | **0/30** |

`CanICraftCurrentTier`'s comment records that the defect it fixed cost "11,434
`LevelSkill(weaponcrafting→N)` actions … dead on four characters since
2026-08-16". The fix has zero offline coverage on the arm it added.

### 3.3 Acquisition-source coverage — where the GE hole shows up as a number

`obtain_sources` over all 522 catalogue codes × 30 scenarios:

| `SourceKind` | scenarios emitting it ≥ once | total emissions |
|---|---|---|
| `CRAFT` | 30/30 | 2,627 |
| `BUY` | 30/30 | 960 |
| `GATHER` | 30/30 | 840 |
| `DROP` | **19/30** | 479 |
| `WITHDRAW` | 24/30 | 56 |
| `RECYCLE` | **1/30** | 6 |
| `SELL` | 0/30 | 0 *(fires only for the code `gold`; not a gap)* |
| `GE_FILL` | **0/30** | **0** |

`DROP`'s 19 is exactly D1's 19. `RECYCLE`'s 1/30 is its own finding: the
recycle-as-acquisition epic has one offline witness.

### 3.4 Craft-rung shape — the fixture over-samples the catalogue's rarest shape

Closure depth × whether any leaf is a monster drop, over `crafting_recipes`
(321 recipes), over the roots the 30 scenarios resolve, and over the
`UpgradeEquipment` targets live characters actually pursued (weighted by cycles):

| shape | catalogue | LIVE `UpgradeEquipment` cycles | scenarios |
|---|---|---|---|
| depth-2 **drop-fed** | 227 (70.7 %) | **18,185 (87.2 %)** | **4/30** |
| depth-1 drop-fed | 33 | 2,030 (9.7 %) | — |
| depth-1 gather-fed | 38 | 578 (2.8 %) | — |
| depth-2 **gather-fed** | **14 (4.4 %)** | 31 (**0.1 %**) | **7/30** |
| depth-3 (all drop-fed) | 9 | 0 | **0/30** |

The fixture spends 23 % of its scenarios on a shape that is 4.4 % of the
catalogue and 0.1 % of live work, and 13 % on the shape that is 71 % of the
catalogue and 87 % of live work. Robby's stall was a depth-2 drop-fed rung
(`iron_legs_armor = {iron_bar:5, cowhide:3}`; `iron_bar ← iron_ore`,
`cowhide ← cow`), which is the majority shape.

`tests/test_ai/scenarios/test_craft_drop_chains.py` does sweep a drop-leaf
class, but it is **6 recipes** (`copper_armor fire_staff iron_helm iron_shield
sticky_dagger water_bow`, pinned by set equality) driven from ONE bare state.
That is a recipe sweep, not a character-shape dimension: it cannot exercise a
character *standing on* such a rung with a partial bag and a skill gate.

### 3.5 Guard coverage

`active_guards(state, gd, None, NO_PROFILE_CONTEXT)` per scenario:

| guard | fires | live goal share of its consequence |
|---|---|---|
| `HP_CRITICAL` | 1/30 | `RestoreHP` 24.1 % |
| `REST_FOR_COMBAT` | **0/30** | (same class) |
| `BANK_UNLOCK` | 0/30 | — |
| `REACH_UNLOCK_LEVEL` | 0/30 | — |
| `GE_CANCEL` | **0/30** | `CancelOrders` 0.2 % — unreachable without D3 |
| `DISCARD_CRITICAL` | 1/30 | `DiscardOverstock` 1.4 % |
| `CRAFT_RELIEF` | **0/30** | `CraftRelief(copper_bar)` 0.6 % |
| `RECYCLE_RELIEF` | **0/30** | — |
| `SELL_RELIEF` | **0/30** | — |
| `DEPOSIT_FULL` | 1/30 | `DepositInventory` 0.2 % |
| `DISCARD_HIGH` | 1/30 | — |
| `GEAR_REVIEW` | **0/30** | unreachable without D2 |
| `CRAFT_POTIONS` | 3/30 | `CraftPotions` 3.0 % |

### 3.6 The live distributions the matrix should be sampled against

```
sqlite3 ~/.cache/artifactsmmo/learning.db   -- 80,194 cycles, 5 characters
```

| dimension | live | fixture |
|---|---|---|
| holds a task | **21.1 %** (16,882; `task_type` is `monsters` in **100 %** of them, `items` in 0) | 0/30 |
| inventory ≥ 75 % of cap | **39.6 %**; ≥ 50 % → **83.8 %**; **empty → 0 of 80,194** (`min(inventory_used)=1`) | ≥75 % in 1/30; **empty in 26/30** |
| gold ≥ 1,000 | **82.3 %** | 3/30 |
| level on a ladder rung | 24.2 % | 15/30 (50 %) |
| HP full | 44.4 %; 50–99 % 44.2 %; **< 50 % 11.4 %** | full 29/30 |
| planner nodes > 41 | **15.2 %**, max **129,322**, 313 timeouts | 0/30 (fixture max = **41**) |

**The empty-bag row is the cleanest single indictment.** 26 of 30 scenarios
model a state that has never once occurred in 80,194 live cycles.

---

## 4. The STRUCTURAL blind spots

A blind spot is structural when no scenario *can* express the other side. Three
qualify, and they are three different kinds of problem.

### 4.1 D3 (GE order book) — a missing bundle KEY, pinned shut by a test

`GameData.from_cache_bundle` (`game_data.py:1526`) says so in its own docstring:
"The Grand-Exchange order book is left EMPTY — orders are live-only by design."
`_hydrate_bundle` has ten keys and none of them is orders. Worse, the *disk
cache format itself* excludes them — `GameData.load`'s docstring: "GE orders are
ALWAYS fetched live (the market order book changes constantly)", and
`data._load_ge_orders(client)` runs *after* `_build_from_objs`, outside anything
`cache.write` sees. **Verified:** the bot's own live cache
`~/.cache/artifactsmmo/gamedata-api.artifactsmmo.com.json` (fetched today) has
exactly the same twelve keys as the committed fixture and no order data.

So "re-capture from the live API" through the existing writer **cannot** produce
this key. It needs a new capture path.

And `test_bundle_ge_orders_empty` asserts the emptiness, so the blind spot is
currently a maintained invariant.

Blast radius, measured: 12 call sites in 10 production modules
(`acquisition_cost`, `progression_reserve`, `ge_bid`, `liquidation_venue`,
`obtain_sources`, `goals/progression`, `goals/discard_overstock`,
`goals/gathering`, `actions/ge_fill`, `actions/ge_fill_sell`) are dead in every
offline test.

### 4.2 D2 (held task) — a field nobody sets

`ScenarioCharacter.task` exists (`scenario.py:84`) and defaults `None`. Nothing
sets it. This is NOT structural in the schema sense — the field is there and
`scenario_state` wires it through to `task_code`/`task_type`/`task_progress`/
`task_total`/`task_lifecycle_phase`. It is a pure content gap, and cheapest to
close. Wave 4 already declared it a prerequisite deliverable.

### 4.3 Depth-3 rungs and the > 41-node search — structural in a subtler way

Nine catalogue recipes have closure depth 3. None is reachable from any
scenario's resolved root. This is structural not because the fixture cannot
express it but because **no committed scenario has a level/skill/holdings
combination that puts a depth-3 rung on its gear sheet**, and the harness gives
no way to declare "the root I want tested" — the root is derived. Reaching a
depth-3 cell means constructing a character, not adding a field.

The 41-node ceiling is the same fact seen from the planner side.

---

## 5. Choosing the matrix

### 5.1 Which dimensions INTERACT (measured)

**I1 — D1 × D2 interact, and getting it wrong makes a new scenario vacuous.**
Adding a synthetic `monsters` task to every scenario at both settings of
`derive_combat_stats`, and asking `has_combat_deficit`:

| task monster | deficit=True with stats ON | with stats OFF |
|---|---|---|
| `chicken` | 2/30 | **29/30** |
| `cow` | 9/30 | **30/30** |
| `wolf` | 14/30 | **30/30** |
| `ogre` | 24/30 | **30/30** |

At zero attack every monster is unwinnable, so the deficit arm fires for
reasons that have nothing to do with the gear chain. Wave 4 §named this trap;
this is the measurement. **A D2 cell is only meaningful on the D1=derived side.**
That kills the cross-product term (D1=zero × D2=blocked) outright — it is not
"expensive", it is *wrong*.

**I2 — D1 × D4 interact.** `DROP` sources are emitted in exactly the 19
scenarios with non-zero attack (§3.3). A drop-fed rung — 71 % of the catalogue,
87 % of live gear work — has no reachable material set at zero attack. Every D4
drop-fed cell must sit on D1=derived.

**I3 — D3 × D4 × D11 interact.** The GE leaf rule
(`_source_leafs`, `CRAFT_SUBSTITUTE_KINDS = {BUY, GE_FILL}`) only *differs* when
a standing order exists **on the item the descent is currently walking**, and
that only matters when the walk is a `grind_descent` — i.e. a skill grind
(D11 = one short) on a craft rung (D4). Measured on a throwaway Robby-shaped
probe state (level 30, gearcrafting 15, partial bag), injecting a single order
into a loaded `GameData`:

```
GE book EMPTY      sources(iron_legs_armor) = [craft]
                   actionable_step(grind) -> ObtainItem('cowhide', 3)   0.004s
GE book POPULATED  sources(iron_legs_armor) = [craft, ge_fill]
                   actionable_step(grind) -> ObtainItem('cowhide', 3)   0.003s
```

Both descend correctly *because the fix at `dd946539` is in this worktree*.
Revert it and only the populated row changes. **The cell discriminates only if
the order exists**, which is the whole argument for §6.

**I4 — D6 × D7 interact (REASONED, not measured).** `DoesTheRecipeNeedAMonsterDrop`
merges `bank_items` into `owned` before calling `gather_step_target`, and the
four relief guards (`CRAFT_RELIEF`, `RECYCLE_RELIEF`, `SELL_RELIEF`,
`DEPOSIT_FULL`) each read a bag measure and a bank measure. I did not measure a
joint firing table because 0/30 scenarios fire any of the three relief guards,
so there is nothing offline to measure. Live, the joint distribution of bag
fullness and task is essentially independent (task rate 21.9 % at bag < 75 %,
19.7 % at ≥ 75 %) — that is a different pair, and it is the evidence that D2 and
D6 do NOT interact.

### 5.2 Which dimensions MASK (a third relationship, and the reason packing has limits)

D10 (HP) is not independent of the others — it **preempts** them. `HP_CRITICAL`
and `REST_FOR_COMBAT` sit at the top of `GUARD_ORDER`, so a scenario with
`hp < CRITICAL_HP_FRACTION` selects `RestoreHP` and every other dimension in
that cell is untested. The same is true of `DISCARD_CRITICAL` and `DEPOSIT_FULL`
for D6's ≥ 90 % value.

This is precisely the gear-latch failure recorded in project memory ("armed on
the bare deficit FACT, so GEAR_REVIEW preempted the objective step for 981
cycles"). **A preempting dimension value must get its own thin cell and must not
be packed onto a cell that is testing something else.** Conversely, a
non-preempting independent dimension (D8 level, D9 gold, D5 blocker class) can
be varied freely across the cells that exist for other reasons — that is what
makes the matrix sublinear in the number of dimensions.

### 5.3 The proposed matrix: 12 cells, 30 → 42 scenarios

Construction rule, stated once so a later plan can argue with it rather than
with a list:

> A cell exists for (a) each value of an interacting pair that is not
> measurement-vacuous, (b) each preempting value that currently has no cell,
> and (c) each structurally-unreachable shape. Every non-preempting independent
> dimension is assigned a value on an existing cell, never a cell of its own.

| # | cell (the interacting pair being covered) | packs (independent dims) | closes |
|---|---|---|---|
| 1 | D1 derived × D2 **workable** monsters task | D8 mid-band, D9 ≥10k | `deficit_upgrade_target` negative arm; `PursueTask` path |
| 2 | D1 derived × D2 **unwinnable, closing chain exists** | D6 ≥75 %, D5 material-gated | `has_combat_deficit`, `GearLatch`, `GEAR_REVIEW` |
| 3 | D1 derived × D2 **unwinnable, NO closing chain** | D8 on-rung, D9 0 | the fall-through wave 4 §1268 names |
| 4 | D3 **populated** × D4 depth-2 drop-fed × D11 one short | D7 stocked | `_source_leafs` GE arm; the Robby stall |
| 5 | D3 **populated** × D4 depth-2 drop-fed × D11 **adequate** (non-grind descent) | D9 ≥ a GE price | the *other* `_source_leafs` arm — GE_FILL still leafs outside a grind |
| 6 | D4 **depth-3** rung | D1 derived, D8 mid-band | 9 catalogue recipes, 0/30 today |
| 7 | D4 depth-2 drop-fed × D11 one short, GE **empty** | — | the control for cells 4–5; without it 4–5 prove nothing |
| 8 | D6 **≥75 %** × D7 **stocked** | D2 none, D9 mid | `CRAFT_RELIEF` / `RECYCLE_RELIEF` / `SELL_RELIEF` |
| 9 | D6 **≥90 %** (preempting) × D7 **empty** | — | `DISCARD_CRITICAL`, `DEPOSIT_FULL` under bank pressure |
| 10 | D10 **50–99 %** with a fight in the chain (preempting) | D1 derived | `REST_FOR_COMBAT`, 0/30 today, 44.2 % live |
| 11 | D9 **currency leaf unaffordable** (0 tasks_coin, a jasper-gated target) | D1 derived | `CanIAffordTheCurrencyLeaf` positive arm → `ReachCurrencyGoal` |
| 12 | D11 **cooking** rung on a fisher-role character | D4 depth-1 gather-fed | the O1 census's 5 never-routed skills; the 33,840 live cooking XP no node models |

Cells 4, 5 and 7 are the same character three ways; cells 1–3 are the same
character three ways. That is deliberate — holding everything else fixed is what
makes the pair the thing under test.

### 5.4 What this deliberately does NOT cover, and why

| not covered | why |
|---|---|
| **`items`-type tasks** | `SELECT task_type, count(*) FROM cycles GROUP BY 1` → `monsters 16882`, `items **0**`. Zero occurrences in 80,194 cycles. Building a cell for it is a combinatorial fantasy. |
| **`bank_items is None`** (bank unknown) | `bank_accessible = 1` in 80,194/80,194 cycles. |
| **`pending_items` non-empty** | Real dimension (§2.1), real Lean slot, 0/30 — but `ClaimPending` is a linear drain with no branch that reads anything else, so it is a *unit-test* shape, not a scenario cell. Named here so a later reader does not think it was overlooked. |
| **D1=zero × D2=anything** | Measurement-vacuous (§5.1 I1): the deficit fires 30/30 for reasons unrelated to gear. |
| **D5 all four blocker classes as their own cells** | All four already reached across the 151 targets in the existing 30 (§3.1). Pack, don't add. |
| **The full D8 × D9 grid** | Both are read by affordability/tier arithmetic with no joint site; pack them across cells 1–12. |
| **Raids / events beyond the existing pair** | 1/30 each already, and both are window-only live content. |
| **A cell per skill (8×)** | The O1 census already sweeps 30 × 8 = 240 cells for rung openness at 0.021 s per scenario. Adding scenarios widens that grid for free; adding *skill cells* would duplicate it. |

### 5.5 Runtime, measured

| sweep | measured cost |
|---|---|
| `GameData.from_cache_bundle` | 0.02 s (once per module) |
| `plan_from_state` per scenario | 0.026 – 0.104 s (30 scenarios end-to-end: **2.95 s**) |
| O1 census, per scenario (1 `routed_skills` + 8 cells) | **0.021 s** |
| whole O1 census | 0.64 s for 240 cells |

Which sweeps actually scale with `len(SCENARIOS)`? Only three:
`tests/test_ai/scenarios/test_scenario_builder.py` (two validation loops),
`tests/test_ai/test_drop_obtainability.py` (two `parametrize(sorted(SCENARIOS))`
sweeps), and `audit/open_rung_completeness.run_census`. **Every other scenario
test names its scenarios explicitly** (`BAND_NAMES`, `NEW_SCENARIOS`,
`SCENARIO_NAMES`, `EXPECTATIONS`), so a new scenario costs nothing there unless
it is added to a list.

Marginal cost of one scenario ≈ 0.021 s (O1) + ~0.05 s (2 drop-obtainability
cells) + 2 × ~0.1 s if it joins `test_goldens` ≈ **0.3 s**.

**12 scenarios ≈ 3.6 s.** Against a ~100 s suite: **+3.6 %**. Against a ~5 min
gate: **+1.2 %**.

**The honest caveat, and it is the real risk.** Those figures are the cost of
cells that plan *fast*. The cells worth adding are the ones that reach the
region where live incidents live — Robby's stall was 45,260 nodes and 15.3 s.
A cell that reproduces that shape *before* its fix is a 15 s test; after the fix
it is 0.004 s (measured, §5.1 I3). So the budget holds **only while the code is
correct**, which is exactly when a regression test is cheap and exactly the
property a regression test should have. What must not happen is a cell landing
in the tail *by accident*. §7.2 makes that a gate condition rather than a hope.

---

## 6. The bundle: what has to change, and the authenticity tension

### 6.1 The three options, and why two of them fail

| option | verdict |
|---|---|
| **Re-capture from the live API through the existing writer** | **Impossible.** `GameDataCache.write` receives `raw_pages` built in `GameData._load_once` from the ten `_fetch_*` calls; `_load_ge_orders` runs afterwards against the live client and its results never enter `raw`. Verified against the bot's own cache written today: same twelve keys, no orders. |
| **Synthetic overlay in the test harness** (`gd._ge_sell_orders[code] = (...)`) | **Works mechanically** — measured in §5.1 I3, two lines, no schema change, and it is exactly what the Robby investigation had to do by hand. But it makes the order book a hand-authored fiction, and the *shape* of a real order book (how many items carry one, what fraction of rungs, what quantities) is precisely the thing that made the live bug surprising. An overlay can reproduce a *known* bug; it could not have *found* one. |
| **A new capture path + a new bundle key** | **The right answer**, with a cost. |

### 6.2 The proposed change

1. **A new `CACHE_VERSION`-independent bundle key**, `ge_orders`, shaped as the
   two dicts `_load_ge_orders` builds:
   `{"buy": {code: [order_id, price, quantity]}, "sell": {...}}`.
   `_hydrate_bundle` gains one `raw.get("ge_orders", {"buy": {}, "sell": {}})`
   entry — `.get`, with the same "absent means the fail-closed direction"
   comment the `achievements` key already carries, so old bundles keep working.
   `from_cache_bundle` populates `_ge_buy_orders` / `_ge_sell_orders` from it.
2. **The key is written by a NEW script, not by `GameDataCache.write`.** The
   disk cache must keep excluding orders — its whole TTL contract is that the
   pages it stores are static, and an order book is not. A separate
   `scripts/snapshot_scenario_bundle.py` (the shape `formal/sim/snapshot_game_data.py`
   already has: `GameData.load(mgr.client)` then dump) writes the committed
   fixture *including* the live order book. `GameData.load` already calls
   `_load_ge_orders`, so the data is in hand at that point.
3. **`test_bundle_ge_orders_empty` is deleted and replaced by its dual**: an
   assertion that the book is NON-empty and that at least one craftable rung
   carries a standing sell order — i.e. an assertion that the fixture can still
   express the Robby shape. A pinned emptiness must not survive this work.

### 6.3 The authenticity tension, stated rather than waved at

The bundle's value is that it is a real API response. Two facts make the tension
concrete and one of them is already a problem:

* **The committed fixture is 49 days stale.** `fetched_at 2026-07-06T23:46:18Z`
  against a live cache written today. Measured drift: **items 522 vs 524, NPCs
  104 vs 107**; maps, monsters, tasks, events, effects, achievements identical.
  So the fixture is *already* not what the API returns, and nothing tests that.
* **An order book is volatile in a way a catalogue is not.** A captured book is
  authentic *as of an instant*. Re-capturing it daily (the way
  `snapshot-refresh.yml` already re-captures `formal/sim/`) would churn the
  fixture and every golden pinned against it; never re-capturing it means a
  frozen market that drifts from reality faster than the catalogue does.

The resolution I propose, and a later plan should argue with it:

> **Capture the book once, deliberately, and treat it as a fixed WITNESS rather
> than as live data.** The order book key is captured at one instant, committed,
> and dated in the same `fetched_at` the rest of the bundle carries. It is
> refreshed only when someone re-captures the whole bundle. What the fixture
> then asserts is not "this is today's market" but "this is a market that
> existed, and here is how the planner behaves in it" — which is exactly the
> epistemic status the rest of the bundle already has, and the only status a
> committed snapshot can honestly claim.

That also fixes the staleness problem in the same motion, because a re-capture
script that nobody has is why the bundle is 49 days old. The daily
`snapshot-refresh.yml` workflow already holds `ARTIFACTSMMO_TOKEN` and already
opens an auto-PR on drift; extending it to the scenario bundle is a workflow
edit, not new infrastructure. **But that is a separate decision** — a daily
auto-refresh of the scenario bundle would re-derive every golden, and this
document does not recommend enabling it without a golden-stability argument
nobody has made yet.

---

## 7. Catching the next gap instead of discovering it live

### 7.1 The census, in the shape this repo already uses eight times

`src/artifactsmmo_cli/audit/scenario_coverage.py` +
`scripts/gen_scenario_coverage.py --check`, added to `census-gate.yml` as a
tenth step, rendering `docs/behavioral_completeness/SCENARIO_COVERAGE_MATRIX.md`.

**The grid.** One cell per `(dimension, value)`. A DIMENSION REGISTRY declares
each dimension as a name plus a *total function* from `(WorldState, GameData)`
to one of its declared values — a partition, not a predicate list. Every
scenario is classified into exactly one value of every dimension.

**The residuals (must be zero):**

| residual | meaning |
|---|---|
| `DIMENSION_VALUE_UNCOVERED` | a declared value with **0** scenarios. This is the obligation itself — it is what would have failed on `D2 = held task` and `D3 = GE populated` from the day each dimension was declared. |
| `SCENARIO_UNCLASSIFIED` | a scenario a dimension's function cannot place in any declared value — the partition is not total, so the coverage counts mean nothing. |
| `DIMENSION_CITATION_DEAD` | a dimension whose declared branch-site citation (`module:symbol`) no longer resolves in `src/`. Stops the registry describing a decision layer that has been refactored away. |
| `UNREGISTERED_STATE_READER` | see §7.3. |

**Explained, non-failing classes**, in the shape O1's four `WALL_*` classes use:
`VALUE_DEAD_LIVE` — a declared value with 0 scenarios *and* a cited live
measurement showing 0 occurrences in `learning.db` (this is how
`task_type = items` and `bank_items is None` stay out of the failing set without
being silently deleted from the registry).

### 7.2 A second obligation the same census should carry, for free

Because it already classifies every scenario, the census can also assert the
**search-size distribution**: every scenario declares an expected node band, and
the census fails when a scenario's actual `max(goals_tried[].nodes)` leaves its
band. Today's `MAX_SEARCH_NODES = 200_000` against a measured fixture maximum of
**41** is a bound that cannot fail; a per-cell declared band is a bound that can.
This is what stops §5.5's runtime caveat from being a hope.

### 7.3 What would make this census VACUOUS — the part that matters

This repo has shipped a census that "reported total success over an EMPTY
reference set" (`gen_open_rung.py`'s own `MIN_CELLS` comment, and project memory
under *record every gate run*). The analogous failures here, and the mechanism
against each:

| vacuity | mechanism |
|---|---|
| **Empty registry.** Zero dimensions → zero uncovered values → `GATE CLEAN`. | `MIN_DIMENSIONS` floor, checked in the script *before* the residual test, read from the SAME module constant the suite asserts — the exact `MIN_CELLS` pattern, for the same reason (`scripts/*` is coverage-omitted and `census-gate.yml` runs no pytest). |
| **Trivial partition.** A dimension whose only declared value is "any" is covered 30/30 forever. | Every dimension must declare **≥ 2** values, and the census fails a dimension where one value holds for all 30 — that is `DIMENSION_VALUE_UNCOVERED` on the other value, which is the intended failure. |
| **Shrinking registry.** Deleting the dimension that is failing makes the gate green. | The registry size floor above, plus the citation requirement: a dimension can only be removed by removing the branch site it cites, and `DIMENSION_CITATION_DEAD` proves the citation is live *today*, not that removal was justified. This is a speed bump, not a proof. |
| **Blind sweep.** A `SCENARIOS` that collapsed to two entries. | A `MIN_SCENARIOS` floor, same pattern. |
| **A registry that simply omits a dimension.** | **Not detectable by this census.** See §7.4. |

### 7.4 The residual this census cannot close, named honestly

A coverage census proves that everything DECLARED is covered. It cannot prove
the declaration is complete — the reference set is hand-written, and that is the
same class of hole as an empty reference set, only harder to see. **Saying
otherwise would be the false-proof pattern this repo has found fourteen
instances of.**

The best available partial closure is mechanical and cheap:
`UNREGISTERED_STATE_READER` — enumerate, by `ast` over `src/artifactsmmo_cli/ai/decisions/`,
`ai/tiers/guards.py`, `ai/combat_deficit.py` and `ai/gear_latch.py`, every
`state.<field>` and `ctx.<field>` attribute read, and fail when a field appears
there with no registry entry naming it. Measured today that set is **17
`WorldState` fields and 12 `SelectionContext` fields** (command in §2), all of
which map onto D1–D11 or onto a dimension §5.4 explicitly declines. So the check
would be GREEN on day one and would fire the first time a `Decision` or a guard
starts reading a state field the matrix does not model.

That converts "a new branch appeared and nobody noticed" from a live-incident
discovery into a CI failure for the *state-reading* case, which is the case the
five measured gaps all belong to. It does **not** catch a new dimension that is
a function of `GameData` alone (a new `SourceKind`, a new catalogue predicate) —
D3 itself is that shape. For that class the only honest answer is that the
`SourceKind` enum is small and closed and should be added to the registry's
citation set by hand, and that this document does not claim a mechanical guard
for it.

### 7.5 Anti-rot on the census itself

Record every run, not the good ones: `--check` writes the matrix even when it
fails (the `gen_open_rung.py` rule), and the summary line prints the covered and
uncovered counts unconditionally, so a run that finds a defect is as visible as
one that does not.

---

## 8. Risks, and what I could not determine

### 8.1 MEASURED

Every figure in §3 and §5.1/§5.5; the twelve GE call sites; the fixture's key
set versus the live cache's; the 49-day staleness and the 522-vs-524 /
104-vs-107 drift; the 41-node fixture ceiling; the guard table; the
`has_combat_deficit` 30/30-vs-9/30 vacuity table; the O1 re-measurement (240
cells, 235 `open_rung`, 5 `wall_rungs_unobtainable`, 0 residuals; 13/30
scenarios route a `ReachSkillLevel`, over 3 of 8 skills); all live distributions
in §3.6.

**Two figures in the brief that my measurement does not reproduce**, both
because the scenario set grew after they were taken:

* the brief's "**14/30** have zero attack" — I measure **11/30**;
* `open_rung_completeness.py`'s docstring says "**11 of the 30** opt the flag
  on" — **20 of 30** do today. The 47/19/5 spread that docstring pins is
  therefore describing a scenario set that no longer exists. Its pinning test
  (`test_the_zero_stat_harness_would_measure_the_fixture`) may still pass on the
  47 and the 5 (both are computed with the flag forced uniformly) while the
  middle number rots. **I did not run that test** (suite runs are off-limits
  this session), so this is a flag, not a finding.

### 8.2 REASONED, not measured

* **I4 (D6 × D7 interact).** Argued from the merge in
  `DoesTheRecipeNeedAMonsterDrop` and the four relief guards' predicates. Not
  measured, because 0/30 scenarios fire any relief guard — there is nothing
  offline to observe. If a later plan finds these are independent, cells 8 and 9
  collapse to one.
* **The 12-cell count.** The construction rule in §5.3 is principled; the
  mapping from rule to exactly twelve cells involves judgement about which
  independent dimension rides which cell. A defensible plan could land at ten or
  fifteen.
* **"Cooking is a value, not an axis."** From `grep` over the decision layer
  finding no cooking-specific branch. If wave 6 adds a cooking root, this
  becomes wrong and D11's registry entry must gain a value.
* **The proposed census's value.** No census exists yet; its cost is estimated
  from O1's 0.64 s for 240 cells, and a coverage grid is arithmetic over
  already-built states, so it should be cheaper. Not measured.

### 8.3 What I could not determine

1. **How many catalogue items would carry a standing GE sell order in a fresh
   capture.** The order book is not persisted anywhere on disk — not in the
   committed fixture, not in the bot's live cache (verified: identical twelve
   keys), not in `learning.db`. The only figure available is the Robby
   investigation's live reading: **21 of the 23 gearcrafting rungs at level ≤ 15**
   carried one on 2026-08-24. I could not verify that independently without a
   live API call, which this task's method does not authorise. **The whole size
   argument for cells 4/5/7 rests on that one borrowed number.**
2. **The real wall-clock of the current suite.** I did not run pytest. "~100 s"
   and "~5 min gate" come from the task brief and from
   `project_local_gate_runtime` in memory, not from my own measurement, so
   §5.5's "+3.6 %" is a ratio with a measured numerator and a reported
   denominator.
3. **Whether adding a task-carrying scenario changes any existing golden.**
   `EXPECTATIONS` in `test_goldens.py` names four scenarios; new scenarios do
   not join it automatically. But `test_drop_obtainability.py` and
   `test_scenario_builder.py` sweep `sorted(SCENARIOS)`, so a new scenario runs
   there immediately, and I could not check those pass without running them.
4. **Why the live task rate differs 2× by ladder position** (33.9 % on a rung vs
   16.9 % mid-band). I attribute it to per-character confounding — five
   characters, unevenly levelled — rather than to any decision-graph
   interaction, because no site reads both `level` and `task_code`. That is an
   inference, and if it is wrong then D2 × D8 interact and cells 1–3 need their
   ladder positions chosen more carefully than "pack them".
5. **Whether a GE-populated bundle breaks any existing test.** Twelve call sites
   go from returning `None` to returning a price. `acquisition_cost`,
   `progression_reserve` and `liquidation_venue` all *price* against it, so
   pinned costs elsewhere in the suite could move. I could not check this
   without running the suite, and a later plan must treat it as the main
   integration risk of §6.2 rather than as a formality.

---

## 9. What a plan derived from this must do first

In order, because each step makes the next one measurable rather than
speculative:

1. **The census before the scenarios.** Build §7's registry with D1–D11 declared
   and let it fail on D2 and D3. A coverage gate that is red on the known holes
   is the only proof it is not vacuous — and per project memory, that failing
   run must be RECORDED, not fixed-then-recorded.
2. **The bundle key (§6.2), with the emptiness pin deleted**, and the
   integration risk in §8.3(5) measured before anything is committed.
3. **Cells 1–3 and 7** — the two cheapest, highest-value blocks, both pure
   content, both closing a gap wave 4 already declared a prerequisite.
4. **Cells 4–5** — only after (2), and only with cell 7 as the control. Without
   the control they assert nothing.
5. **The rest**, in the order the census's uncovered count ranks them.

Nothing in this document authorises step 2 or later. It is a specification of
what is missing and what a cell has to earn, not a plan.

---

## Addendum — a production finding the D3 measurement surfaced (2026-08-24)

Measuring the GE pricing shift before populating the bundle (user's direction,
"measure the pricing shift first") turned up something that is NOT a fixture
property. Recording it here because it was found by this work, but it belongs to
the acquisition model, not to the scenario set.

### An affordable-but-unfunded route prices ABOVE the no-route sentinel

`acquisition_cost_core.UNOBTAINABLE_PER_UNIT = 10**6` is the sentinel for "no
route exists". A gold-priced route carries `inputs={"gold": price}`, and
`_owned_with_gold` credits only the character's POCKET. Any shortfall beyond
that is charged `UNOBTAINABLE_PER_UNIT` PER UNIT, so an unaffordable real route
prices at `price * 10^6 + 2` — **strictly worse than a route that does not exist
at all.** The comparison inverts: an impossible route outranks a merely
unaffordable one.

Measured while populating the GE book: emission went 0/30 -> 30/30 scenarios
(5,370 emissions) and `acquisition_actions` moved for 33-160 codes per scenario,
in that direction.

### It is reachable LIVE, not only in the fixture

My first reading was that empty fixture bags caused it — 26/30 scenarios carry an
empty bag against **0 of 80,194** live cycles, so a live character always has
something to sell. That reading was WRONG, and checking it is what corrected it.

Gold's own route is `SourceKind.SELL`, emitted by `obtain_sources._sell_sources`,
which iterates `accumulation_sell.sellable_surplus(state, ...)` AND requires
`event_npc_tradeable`. **Every item-buying NPC in this game is an event NPC** —
all five, 55 buyer rows, not one non-event (that function's own docstring states
it, and it matches the recorded `reference_every_buyer_is_an_event_npc` finding).

So gold has TWO gates: sellable surplus, and an OPEN BUYER EVENT. Live bags are
never empty, but buyer windows are intermittent. During any window with no buyer
event, gold is unobtainable and every unaffordable route prices above the
sentinel.

### Why this is the same family as the gold-holding wall

`19804b6a` fixed "gold lives in `state.gold`, not `inventory`, so every
gold-priced vendor route cost `price x 10^6`" — 46 walled pairs. `_owned_with_gold`
is that fix, and its docstring states its own limit honestly: pocket only, bank
not credited, "making banked gold a withdraw route of its own is a separate
increment". This addendum is the NEXT limit of the same wall: the fix credits
what is HELD, and says nothing about a shortfall.

### Not fixed here, deliberately

This is an acquisition-model change, not a fixture change, and the task that
found it was scoped to prerequisites. Options worth weighing, none chosen:
cap any priced route at `UNOBTAINABLE_PER_UNIT` so the sentinel is a true
ceiling; credit banked gold via the dormant `WithdrawGoldAction`; or price a
gold shortfall at the cost of ACQUIRING that gold rather than at the
no-route sentinel. The first is the smallest and makes the comparison sound
without claiming the route is cheap.
