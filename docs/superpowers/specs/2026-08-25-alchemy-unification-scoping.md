# Alchemy unification — scoping the product side into the remaining waves

**Status:** scoping document. No production code. Written 2026-08-25 on branch
`waves-3-6`, against `main` @ `47780bf2`.

**Framing (the user's, verbatim):** *"scope the real gap into the remaining
waves. healing potions are the case that is covered better than other potions.
we can now fully complete and unify the rest of alchemy into the AI's
awareness."*

**Why "now".** `c7c3de9f` fixed alchemy's SKILL side: `_gear_nameable_skills`
restated `_gear_candidates_by_type`'s rule instead of asking it, and had drifted,
so `_orphan_skill_roots` declined alchemy a root on a nameability claim no code
path could honour. Alchemy had an open XP-positive rung in 42/42 scenarios and no
root. O1 routed moved 194 → 236 of 336, 7 of 8 skills → 8 of 8. **The skill is
reachable. This document scopes the PRODUCT side.**

---

## 0. Headline conclusions

1. **The catalogue is 20 craftable `utility` potions, all `alchemy`** — verified
   against the committed bundle: **7** `hp_restore`, **5** `dmg_elements`, **4**
   `resistance`, **3** `antipoison`, **1** `hp_bonus`. (MEASURED, §1.1.)

2. **The fleet has never reached alchemy 20.** Max ever observed, per character,
   over 86,016 cycles: Robby 17, C3P0 15, HAL 15, R2D2 7, Lor 4. Fifteen of the
   twenty potions require `crafting_level` 20–50. **Only 5 potions have ever been
   craftable by anyone**: `small_health_potion` (5) and the four elemental boosts
   (10). (MEASURED, §1.2.) **This is the single most important constraint in the
   document and it invalidates most of the obvious proposals** — see §5.

3. **The brief's headline ("heals have three routes, non-heals have one narrow
   one") is right in shape and wrong in emphasis.** Non-heals are provisioned,
   equipped, bought and recycled at volume: 357 of the 893 `Equip → utility_slot`
   actions are boost potions, 88 of the 241 potion `CraftAction`s are boosts, and
   **all 289 GE potion buys are boosts and zero are heals**. Post-restart the
   guard's crafting work is *entirely* the boost arm. (MEASURED, §1.3.)

4. **The real gap is narrower and sharper than "non-heals lack a stock notion":
   the stock notion EXISTS, is tested, and is unreachable.**
   `CraftPotionsGoal._active_craft` has a boost-stock branch
   (`craft_potions.py:186-207`) that fires when the heal deficit is met and a
   beneficial boost is below `potion_baseline_pure`. The guard predicate
   `craft_potions_fires` has **no such arm**, and `CraftPotionsGoal.value()`
   prices that branch at **0.0**. The branch is doubly dead. Its only tests call
   the private `_active_craft` directly. (MEASURED by code-read, §2.1.)

5. **That dead arm is the alchemy bug's exact shape, one module over.**
   `craft_potions_fires` RESTATES the goal's fire condition instead of ASKING it,
   and has drifted from it — precisely what `_gear_nameable_skills` did to
   `_gear_candidates_by_type`. Fixing it is a ~5-line change with no new node, no
   band change, no new comparison.

6. **`potion_type_weight` must not be revived, and the reason is stronger than
   "it is a fifth multiplier"** (though it is that): its key domain
   `{hp_restore, boost, resist, antipoison}` has **no classifier anywhere in
   `src/`**, so reviving it means writing a new item→family producer — a second
   producer of a classification `ItemStats` already carries; `health_boost_potion`
   (`hp_bonus`) is absent from the table and would silently weigh 0; and
   `armor_score_pure` **already** prices `dmg_elements`, `resistance`,
   `hp_bonus`, `combat_buff` and `hp_restore` on one commensurable ruler. §5.2.

7. **`utility_potion_targets` must not be restored to the gear sheet**, and one
   reason is new: even if the `type_ == "utility"` skip were lifted,
   `_gear_candidates_by_type` also filters `stats.level > level_cap`, and utility
   potion `level`s are 5–50 — importing exactly the ruler the design calls
   level-exempt. It also produces **heals only** (`bootstrap_potion_target`'s
   `effect` defaults to `hp_restore` at every call site), so it does nothing for
   the user's stated gap. §5.1.

8. **One measured live pathology neither wave names: boost potions are being
   RECYCLED.** 69 `RecycleAction` rows destroy boost potions (48 `water`, 20
   `air`, 1 `fire×2`), **all after 2026-08-23**, against **0** for heals. Heals
   carry `CONSUMABLE_KEEP = 999` via `hp_restore > 0`; non-heal utility potions
   do not, and fall back to `equippable_cap`. I could not isolate the cause. This
   is churn against the very route wave 6 §5.3 wants to widen. §4, piece C.

---

## 1. The gap, stated precisely and measured

### 1.1 The catalogue (MEASURED — committed bundle
`tests/test_ai/scenarios/fixtures/gamedata_bundle.json`)

20 items with `type_ == "utility"` and a crafting recipe; `crafting_skill` is
`alchemy` for **all 20**.

| family (by `ItemStats` field) | n | codes / `crafting_level` |
|---|---|---|
| `hp_restore` | 7 | small_health 5, minor_health 20, health 30, health_splash 30, greater_health 40, enhanced_health 45, enhanced_health_splash 50 |
| `dmg_elements` | 5 | air/earth/fire/water_boost 10, enhanced_boost 40 |
| `resistance` | 4 | air/earth/fire/water_res 40 |
| `antipoison` | 3 | small_antidote 20, antidote 30, enhanced_antidote 45 |
| `hp_bonus` | 1 | health_boost 40 |

`combat_buff` is not an independent family: `game_data.py:1979-1985` sums
`antipoison` into it, and the four elemental boosts carry `combat_buff` 12 (80
for `enhanced_boost`) alongside their `dmg_elements`. `boost_res_*` and
`boost_hp` are routed into `resistance` / `hp_bonus` and deliberately **not**
into `combat_buff`, so no stat is double-counted.

### 1.2 The skill ceiling (MEASURED — `~/.cache/artifactsmmo/learning.db`,
86,016 cycles, 2026-08-02T15:18 → 2026-08-26T01:03)

Max `alchemy` ever observed: **Robby 17, C3P0 15, HAL 15, R2D2 7, Lor 4.**
Unchanged in the post-restart window.

Therefore **`resistance` (4), `antipoison` (3) and `hp_bonus` (1) — 8 of 20
potions — have never been craftable by any character**, and the corresponding
measurement is exactly what you would expect: **zero rows in 86,016 cycles name
any of the eight**. That zero is NOT evidence the machinery for them is broken.
It is evidence the set is empty.

### 1.3 Family × capability (MEASURED, with the code path for each cell)

"Provisioned" = a guard/goal acquires it. "Equipped" = it reaches a utility slot.
"Stock" = pursued to a standing quantity target. "Upgrade" = proposed as a better
item than the one worn. "Unlock" = pursued because it flips a fight.

| family | craftable by fleet | provisioned | equipped | stock target | upgrade target | unlock-a-fight |
|---|---|---|---|---|---|---|
| `hp_restore` | 1 of 7 (`small_health`, alch 5) | **YES** — `craft_potions_fires` heal arm; 144 `CraftPotionsGoal` craft rows | **YES** — 536 `Equip→utility` rows | **YES** — `potion_stock_target_pure`, combat-projected, ramp-capped | **NO** — `utility_potion_targets` orphaned (Addendum 2) | **NO** — `_is_craftable_boost` excludes `hp_restore > 0` |
| `dmg_elements` | 4 of 5 (alch 10) | **YES, but only via the unlock arm** — 81 `CraftPotionsGoal` craft rows + 289 GE buys | **YES** — 357 `Equip→utility` rows | **BUILT AND DEAD** — `_active_craft:186-207`, unreachable (§2.1) | **NO** | **YES** — `unlock_boost_target`, and only when *no* in-band monster is bare-winnable |
| `resistance` | **0 of 4** (alch 40) | — (0 rows) | — (0 rows) | dead arm | **NO** | reachable in principle (`_is_craftable_boost` admits it) |
| `antipoison` | **0 of 3** (alch 20/30/45) | — (0 rows) | — (0 rows) | dead arm | **NO** | reachable in principle; `predict_win` reads `antipoison` (`combat.py:128`) |
| `hp_bonus` | **0 of 1** (alch 40) | — (0 rows) | — (0 rows) | dead arm | **NO** | reachable in principle |

**Supporting live counts (MEASURED, whole window unless stated):**

* `Equip → utility_slot`: **893** total — 536 `small_health_potion`, 357 boost, **0 other**.
* Potion `CraftAction`s: `small_health_potion` 153, `air_boost` 43, `water_boost` 33, `earth_boost` 7, `fire_boost` 5.
* `CraftPotionsGoal` craft rows: **heal 144, boost 81** — the guard's boost arm is 36 % of its crafting output.
* Goal selection: `CraftPotionsGoal` **2,819**; `MaintainConsumables` **3**; `ProvisionMarginalFight` **1**; `RestoreHP` **20,339**.
* Boost-potion actions by goal: `UpgradeEquipment` **510** (ends 2026-08-23 — the flip), `CraftPotions` 117, `EquipOwnedGear` 110, `RecycleSurplus` **68**, `GatherMaterials` 1.
* GE potion traffic: `GeBuy(fire_boost×1)` 163, `GeBuy(water_boost×1)` 86, `GeBuy(earth_boost×1)` 40 = **289, all boosts, zero heals**. This is the 289 wave 6 §5.3 cites; it is a **buy** route, not a sell fill.
* **Post-restart (2026-08-25T23:18 →, n = 487 cycles — SMALL SAMPLE):**
  `CraftPotionsGoal` 75, `MaintainConsumables` 0, `RestoreHP` 13; potion-naming
  actions: `Gather(gudgeon_spot→algae)` 67, `Gather(sunflower_field)` 5,
  `Craft(water_boost_potion×5)` 3 — **0 heal actions, 11 boost actions**. `algae`
  is in every boost recipe. **The guard's live work right now is the boost arm,
  not the heal arm.** This narrows the finding commit's wording (`47780bf2`
  attributed the 75 to provisioning generally).

### 1.4 The honest headline

Heals have **three** live routes (`CRAFT_POTIONS` heal arm → `EquipOwnedGear` →
`RestoreHP`/`MaintainConsumables` stock) and have lost a **fourth** (the gear
sheet, Addendum 2). Non-heals have **one** live route (`CRAFT_POTIONS` unlock
arm) plus incidental equipping, have lost a **second** (the pre-flip
`UpgradeEquipment` root, 510 rows + 289 GE buys, ending 2026-08-23), and have a
**third that exists in code and cannot run**. The user's "healing potions are
covered better" is correct; the mechanism is not "no one wrote the non-heal
code" — most of it is written.

---

## 2. What "unify" means concretely

### 2.1 The load-bearing finding: the guard restates the goal and has drifted

```
# ai/goals/craft_potions.py  _active_craft
pair = unlock_boost_target(...)          # arm 1: unlock
if pair is not None: return (boost, 1, cy)
...
deficit = self._baseline(...) - self._equipped(...)   # heal deficit
if deficit <= 0:                                       # arm 3: BOOST STOCK
    best_boost = best_boost_potion(state, game_data, primary_combat_target(...))
    if best_boost is not None and equipped_potion_qty(...) < potion_baseline_pure(...):
        return (best_boost, boost_runs, boost_equip_qty)
    return None
return (code, runs, equip_qty)                         # arm 2: heal stock
```

```
# ai/potion_supply.py  craft_potions_fires   -- the GUARD predicate
if unlock_boost_target(...) is not None and _recipe_producible(...): return True   # arm 1
target = target_potion_pure(...)                                                   # arm 2
if target is None: return False
... return equipped < combat_justified_target
#   *** no arm 3 ***
```

Arm 3's precondition is *exactly* the negation of arm 1 ∧ arm 2, so it can only
be reached in cycles where the guard returns `False` and the rung never fires.
And `CraftPotionsGoal.value()` short-circuits: `plan` is not `None`,
`unlock_boost_target` is `None`, so it returns `max(0, heal_deficit)` — and
`heal_deficit <= 0` is arm 3's own precondition, so **value is 0.0**.

`craft_potions_fires`' docstring claims to be *"the exclusive gating truth for
CraftPotionsGoal — the guard never fires when the goal would have no plannable
path."* The converse is what fails: **the goal has a plannable path the guard
cannot open.** The two tests that cover arm 3
(`test_goal_crafts_boost_after_heal_satisfied`,
`test_goal_prioritizes_heal_over_boost`) both call `goal._active_craft(...)`
directly — green, and blind to the unreachability.

**Second defect inside the dead arm, found while reading it:** arm 3 sizes to
`potion_baseline_pure` (the raw level ramp) while arm 2 sizes to
`potion_stock_target_pure` (combat-projected, ramp-capped). That is the ramp the
rest-time-value work replaced for heals. **Do not wire arm 3 without resolving
which target it should use** — wiring it as written re-introduces the bare-ramp
firing that `craft_potions_fires`' own comment records as a defect.

### 2.2 The second finding: the alchemy grind has no product

`c7c3de9f` gave alchemy an orphan root — `LevelSkill(alchemy, N)`. Which recipe
that root grinds is chosen by `skill_grind_target`, whose ordering pivots on
`wanted`, set from `ctx.near_term_targets`. That set is built at
`player.py:3735` as `objective.near_term_gear(state).values() | target_tools`,
and `near_term_gear` is built from `_gear_candidates_by_type`, which **skips
`type_ == "utility"`**. Therefore **every alchemy rung has `wanted = False`**:
the grind levels alchemy on whatever ranks best by XP rate, with no connection to
the potion the guard is about to want.

The same `near_term_targets` feeds `_active_gear_keep` (`player.py:3737`), so
this is also a candidate explanation for §1.3's 69 recycles — **but I did not
confirm it** (see §6.2 U2).

### 2.3 So "unify" resolves to these pieces

| # | piece | what it is | capability gain or tidying? |
|---|---|---|---|
| **A** | **The guard asks the goal.** Replace `craft_potions_fires`' restated arms with a call that reflects `_active_craft`'s answer, resolving the arm-3 target question first. | **CAPABILITY.** Gives non-heals a standing STOCK notion — the thing the brief says does not exist. Machinery already written and tested. |
| **B** | **Wave 6 §5.3's `GeFillSellOrderAction` widening of `CraftPotionsGoal.relevant_actions`.** | **CAPABILITY.** Restores the buy route behind 289 measured GE buys, all non-heal. Already designed, already assigned. |
| **C** | **Why are boost potions recycled?** 69 rows, all post-flip, 0 for heals. | **INVESTIGATION, not a change.** A capability gain in B without this may buy more potions to destroy. |
| **D** | **Restore `utility_potion_targets` to the gear sheet.** | **DECLINED** — §5.1. Cheap tidying available instead (docstring/retire). |
| **E** | **Revive `potion_type_weight` as a family-weighted ranking.** | **DECLINED** — §5.2. |
| **F** | **Let the potion target enter `ctx.near_term_targets`** so the alchemy grind crafts the potion the guard wants. | **CAPABILITY, but coupled.** Cheap in code; touches the keep ladder, so MEASURE FIRST. |
| **G** | **Anything specific to `resistance` / `antipoison` / `hp_bonus`.** | **DECLINED** — §5.3. Empty set. |

---

## 3. Wave assignment, and where it touches a reconciled decision

The 2026-08-24 reconciliation (24 contact points, 6 silent conflicts) settled
five potion rulings. **Nothing here overturns any of them.** For the record:

* **C1** — `CRAFT_POTIONS` keeps its rung and its band. **Untouched.** Piece A
  changes the rung's *predicate*, not its band, and adds no comparison.
* **C2** — the potion route returns via wave 6's goal widening, not wave 4's
  `WhichSlotClosesTheFight`. **Untouched**; piece B *is* that ruling.
* **C4** — `MAINTAIN_CONSUMABLES` is kept. **Untouched** (and re-verified: 3 wins
  in 86,016).
* **C21** — the rung is unchanged, the goal gains a route. Piece A **narrows this
  wording once more**: the *predicate* changes too. That is a wording amendment,
  not a reversal, and §3.1 states why the existing measurements do not cover it.
* **C22** — `CraftPotionsGoal` freezes `_seed_target` at construction, so a buy
  route may leave `is_satisfied` unreachable. **Piece A inherits this risk**
  (arm 3 would seed a boost target), so A is gated on the same order-book fixture
  as B.

| piece | wave | justification |
|---|---|---|
| **A** — guard asks the goal | **wave 6**, as a sibling increment to §5.3 | Wave 6 owns the potion route and already opens `goals/craft_potions.py`. It is a route-inside-an-existing-rung change of exactly §5.3's shape: no band change, no new node, no `ObtainItem.is_satisfied` change, so wave 4 §6.1(b)/(c) do not bite. It must land **with or after B** so the widened action set exists before the widened predicate can call for it. |
| **B** — GE route widening | **wave 6 §5.3, unchanged** | Already assigned and measured. My measurement refines it: the 289 are `GeBuy` rows for boost potions, so what is restored is a BUY route for non-heals — which strengthens §5.3's own case and is worth writing into it. |
| **C** — recycle investigation | **NEW — wave 7 (gated investigation)**, in wave 3c's shape | It is not a design, it is a question with a measurement attached. Assigning it to wave 6 would make wave 6 depend on an unknown. It should be a **precondition on B shipping to the live fleet**, not a precondition on B being written. |
| **F** — potion target enters `near_term_targets` | **NEW — wave 7**, after wave 4 | It edits `SelectionContext` assembly, which wave 4 reads (`gear_review_active`, `gear_keep`) and wave 6 R5 already orders "wave 4 first". It also changes the keep ladder, which is piece C's subject — so F is downstream of C's answer. |
| **D, E, G** | **not assigned — declined** | §5. |

### 3.1 Why piece A is not re-litigating a rejected proposal

Both potion proposals were measured and rejected once, and the brief is right to
demand a reason those measurements did not cover. Here it is, explicitly:

* Wave 4 §6.3's proposal was measured on **reach**: `has_combat_deficit` needs a
  workable `monsters` task, held in 15,240 of 78,552 cycles (19.4 %). Piece A is
  not gated on a task at all — it is gated on the heal deficit being met and a
  beneficial boost being understocked.
* Wave 6 §5.3's declined-demotion was measured on **band**:
  `MAINTAIN_CONSUMABLES` won 3 of 78,552 against `CraftPotionsGoal`'s 2,245.
  Piece A **changes no band**.
* **Neither design measured arm 3, and neither names it.** Both documents assume
  the only non-heal trigger is `unlock_boost_target`; wave 4 §6.1's four
  arguments and wave 6 §5.3's "`craft_potions_fires` already asks the right
  question" are both written as if the goal and the guard agree. They do not.
  That is the uncovered fact.

**What piece A costs that must be measured before it ships:** it makes
`CRAFT_POTIONS` fire in cycles where it currently does not, and `CRAFT_POTIONS`
is a `BAND_GUARD` rung that preempts the objective step. The predicate
self-quiets (it releases when `boost_equipped >= baseline`), so it is not the
freeze shape wave 4 §3.2 warns about — but "self-quieting" is a property of the
code, not a measured firing rate. **Acceptance gate: run the 42 committed
scenarios before and after and record the change in `CRAFT_POTIONS` firings; if
the added firings exceed the heal arm's own rate, the arm needs a narrower
predicate, not a wider one.**

---

## 4. Cost — what is cheap because it is already built

| piece | already built | still to build |
|---|---|---|
| **A** | `_active_craft` arm 3 (22 lines), `best_boost_potion` (its own module, 8 tests), `potion_baseline_pure`, `equipped_potion_qty`, `primary_combat_target`, `_recipe_producible`, two arm-3 unit tests | the predicate call (~5 lines), the arm-3 **target-unit decision** (`potion_baseline_pure` vs `potion_stock_target_pure` — §2.1), a `value()` arm, a scenario that reaches it through the real arbiter, the firing-rate measurement |
| **B** | `GeFillSellOrderAction`, and the identical widening on `GatherMaterialsGoal` (`gathering.py:607`) and `UpgradeEquipmentGoal` (`progression.py:507`) | wave 6's order-book fixture; the C22 `_seed_target` freeze |
| **C** | the measurement (this document) | nothing — it is a question |
| **F** | `target_potion_pure` / `unlock_boost_target` are already the single source of truth; `wanted` is an existing boolean pivot in an existing ordering | one line in `player.py`'s context assembly, plus whatever C's answer implies for `gear_keep` |
| **D** | `utility_potion_targets` (35 lines, 4 tests) | — declined; the cheap *tidy* is a docstring or a retirement, per wave 6 §5.3's cleanup bullet |
| **E** | `potion_type_weight`, `POTION_TYPE_WEIGHTS`, `potionWeight` + 2 Lean theorems, `gen_reachability_claims` pin | — declined; **and a new item→family classifier, which is the hidden cost** |

**The cheap ones are most of the value.** A and F together are on the order of
ten production lines plus their gates, and between them they give non-heal
potions a stock target and give the alchemy grind a product. B is already
scoped. That is the whole of "unify the rest of alchemy into the AI's
awareness" that is defensible today.

---

## 5. What I would NOT do, with the measurement

### 5.1 Do NOT restore `utility_potion_targets` to the gear sheet

Three reasons, in decreasing strength:

1. **It would not address the user's gap.** `utility_potion_targets` calls
   `bootstrap_potion_target(state, self._game_data)` and
   `target_potion_pure(state, self._game_data, exclude=primary)` — both with
   `effect` at its default `"hp_restore"`. **Every production call site of both
   selectors passes the default.** Restoring it puts *heals* back on the gear
   sheet. The family the user says is under-covered would gain nothing.
2. **The ruler objection stands, and there is a second one.** Wave 4 §6.1(c) and
   wave 6 §5.3 both refuse potions on the tier ladder because `_tier_gap` is
   defined in ladder rungs and potions are level-exempt. Reading
   `_gear_candidates_by_type` for this document found a second: it also filters
   `stats.level > level_cap`, and utility potion `level`s run 5→50. Entering that
   producer imports the level ruler the design calls exempt, at the same site.
3. **It has zero production callers and its restoration was already costed as a
   third option neither wave took** (Addendum 2). Nothing in this document's
   measurements changes that.

**Do instead (tidying, ~0 risk):** take wave 6 §5.3's cleanup bullet — either
docstring `utility_potion_targets` as diagnostic-only or retire it with
`commands/objective.py`'s `--candidates` view. Today it reads as decision code
and is not.

### 5.2 Do NOT revive `potion_type_weight` — and confronting it directly

The hard constraint says no fifth ranking multiplier. `potion_type_weight` *is* a
multiplier — `POTION_TYPE_WEIGHTS`' own docstring calls it "applied as a
multiplier on the candidate's value gain before the gear branch ranks it", and
wave 3 R2 warns that "the discipline that produced the four multipliers will
apply pressure to add a fifth". That alone refuses it. Three further findings,
each independently sufficient:

* **It would require a NEW producer of a classification the data already
  carries.** Its keys are `"hp_restore" | "boost" | "resist" | "antipoison"`.
  Grepping `src/` for those strings finds **no classifier**: nothing maps an item
  code to one of them. `ItemStats` carries `dmg_elements` / `resistance` /
  `antipoison` / `hp_bonus` as fields. Writing an item→family function is
  writing a second producer of "what kind of potion is this" — the alchemy bug's
  own shape, which this epic exists to stop making.
* **The table's universe is already wrong for the catalogue.** There is no
  `hp_bonus` key, and `potion_type_weight` returns `Fraction(0)` for an unknown
  family by design. `health_boost_potion` would weigh **0** — silently. The
  closed-universe contract that is the function's stated value is *already*
  violated by the live catalogue.
* **`armor_score_pure` already prices every one of these stats on ONE ruler**
  (`scoring.py:181-231`): `resistance` through the monster-relative defense term,
  `dmg_elements` through the offense term, and `hp_restore + hp_bonus +
  lifesteal + combat_buff` through the flat block — and `game_data.py:1979-1985`
  deliberately routes each boost effect into exactly one of them so nothing is
  double-counted. A family weight would be a **second scale over the same
  stats**, which is the defect wave 3 deleted.

**What I would do instead: leave the retention decision alone, and correct one
of its three stated grounds.** `potion_type_weight`'s docstring keeps it partly
because "waves 4 and 6 both put potions back on the decision surface". This
document narrows that: **neither wave puts potions back on a RANKED surface** —
wave 4 §6.3's conclusion was withdrawn and wave 6 §5.3 explicitly refuses the
ladder. The Lean mirror + two theorems remain a valid ground (deleting the Python
half would orphan a proof), and the closed-universe tuning record remains a valid
ground. The third should be rewritten so the next reader does not cite a reason
this document retired. That is a docstring edit, not a deletion, and the deletion
question stays the user's.

### 5.3 Do NOT build anything for `resistance` / `antipoison` / `hp_bonus`

**8 of 20 potions. 0 rows in 86,016 cycles. `crafting_level` 20–50 against a
fleet maximum of 17.** Wave 6 §5.5 records that this epic *"has now three times
shipped a mechanism into a set where it was unreachable"*. Every proposal above
is justified on the **5 potions the fleet can actually craft**
(`small_health_potion` + 4 elemental boosts); the other 15 ride free on the same
machinery when alchemy gets there, and none of them justifies a line of code
today. If a reviewer wants coverage for antipoison specifically, the honest
answer is to raise alchemy past 20 first and re-measure.

### 5.4 Do NOT widen `unlock_boost_target`

It is narrower than the brief states: it returns `None` **unless no in-band
monster is bare-winnable at all** (`unlock_boost.py:59-62`) — a total-stall
condition, not "a boost would help". Widening it to "a boost improves the
margin" would turn a stall-breaker into a standing preference and would
duplicate what piece A's arm 3 already does through `best_boost_potion`. **One
answer, one producer.** Piece A is the widening; `unlock_boost_target` stays as
the stall-breaker it is.

---

## 6. Risks, and what I could not determine

### 6.1 Risks

**R1 — piece A makes a `BAND_GUARD` rung fire more often.** `CRAFT_POTIONS`
preempts the objective step, and wave 4 §6.1(a)'s measured argument for keeping
it at its band assumes its current firing rate. Arm 3's predicate self-quiets in
code; that is REASONED, not measured. *Mitigation: the §3.1 acceptance gate —
before/after firing counts on the 42 scenarios, with a stated ceiling.*

**R2 — piece A inherits C22.** `CraftPotionsGoal` freezes `_seed_target` at
construction and `relevant_actions` delegates to the frozen plan. Arm 3 seeds a
*boost* target; if piece B's buy route is in the admitted set, `is_satisfied`
may be unreachable for the same reason wave 6's R1/U2 flags. *Mitigation: A ships
behind the same order-book fixture as B, never before it.*

**R3 — arm 3's target unit is the ramp the heal arm abandoned.** Wiring it
as written re-introduces `potion_baseline_pure` as a firing driver. This is a
recurrence shape the memory index records twice (rest seconds, projection cycle
unit). *Mitigation: resolve the unit BEFORE wiring, not after; pin it by
identity against `potion_stock_target_pure` the way the heal arm is.*

**R4 — piece F changes the keep ladder as a side effect.** `near_term_targets`
feeds both `skill_grind_target`'s `wanted` pivot and `_active_gear_keep`. A
one-line change to the set is a two-consumer change. *Mitigation: F is
downstream of piece C's answer, and its test must assert both consumers.*

**R5 — the post-restart sample is 487 cycles.** Every "post-restart" number in
§1.3 rests on ~1h45m of fleet time and 5 characters. The inversion it shows (0
heal actions, 11 boost actions) is suggestive, not established. *Mitigation:
re-measure before citing it in an increment's acceptance criteria.*

**R6 — piece A adds no argmax, but it adds a REASON TO ADD ONE.** Once the
guard can pursue boosts as stock, the natural next request is "which boost, and
how does it rank against the heal?" `best_boost_potion` already answers the
first by combat-margin gain against a named monster, and arm 2 already answers
the second by strict precedence (heal deficit first). *Both answers exist. A
future increment that introduces a weight to blend them is the fifth multiplier
in disguise; this paragraph is the refusal.*

### 6.2 What I could not determine

**U1 — why 69 boost potions were recycled.** MEASURED: 69 `RecycleAction` rows
(48 `water_boost×1`, 20 `air_boost×1`, 1 `fire_boost×2`), all under
`RecycleSurplus`, all between 2026-08-23T04:22 and 2026-08-25T19:06, against 0
for heals. I established that `useful_quantity_cap_pure` grants
`CONSUMABLE_KEEP = 999` only on `hp_restore > 0`, so non-heal potions rely on
`equippable_cap` and `is_dominated`; and I checked that `may_displace` does
**not** make a heal dominate a boost (their stat vectors are incomparable —
`small_health` wins on `flat_utility`, the boost wins on `dmg_elements`). So the
dominance path is not the obvious explanation and I did not find the real one.
**This is piece C and it is a real open question, not a footnote.**

**U2 — whether piece F fixes U1.** `near_term_targets` feeds `gear_keep`, so
adding potions to it *might* be the missing keep reason. REASONED, untested.

**U3 — whether arm 3 would ever fire on the live fleet.** Its precondition needs
the heal deficit met AND `primary_combat_target` non-`None` AND a
strictly-positive-margin boost craftable. All three hold for a level-20 character
at alchemy 10+ on paper; I did not run the scenario harness to confirm, because
that requires the plan path and this document changes no code. **This is the
first thing an implementer should measure**, and if arm 3 turns out unreachable
for a *fourth* reason, piece A collapses to a deletion instead of a wiring — a
perfectly good outcome, and one the measurement decides.

**U4 — the pre-flip `UpgradeEquipment` boost rows.** 510 rows ending
2026-08-23T12:07, of which 289 are GE buys. I confirmed the timing matches the
flip and the codes are all elemental boosts, but I did not reconstruct which
root emitted them, so I cannot say whether piece A + B together recover that
work or only part of it. Wave 6 §5.3 claims B alone recovers the 289; my data is
consistent with that and does not prove it.

### 6.3 Which claims are MEASURED and which are REASONED

**MEASURED** (bundle or `learning.db`, reproducible from
`/tmp/.../scratchpad/q*.py` queries restated inline above): the 20-potion
catalogue and its family split; all 20 being `alchemy`; every `crafting_level`;
the per-character alchemy maxima; all goal-selection counts; all
`Equip→utility` / `CraftAction` / `GeBuy` / `RecycleAction` breakdowns; the
zero-row result for the eight `resistance`/`antipoison`/`hp_bonus` potions; the
post-restart window's composition.

**MEASURED BY CODE-READ** (verified in the worktree, not by execution): arm 3's
unreachability and the `value()` short-circuit; `craft_potions_fires` having no
arm 3; `utility_potion_targets` and `potion_type_weight` having zero production
callers; the absence of any `"boost"`/`"resist"` classifier; `hp_bonus`'s absence
from `POTION_TYPE_WEIGHTS`; `_gear_candidates_by_type`'s `level_cap` filter;
`near_term_targets`' composition; `useful_quantity_cap_pure`'s `hp_restore`
gate; `unlock_boost_target`'s no-monster-is-winnable precondition;
`may_displace`'s incomparability on heal-vs-boost.

**REASONED**: that arm 3 self-quiets at live rates (R1); that piece A recovers
part of the pre-flip work (U4); that F would fix U1 (U2); that the eight
never-craftable potions need no code today (an argument from an empty set, which
is strong but is an argument).

---

## 7. One-paragraph summary for whoever picks this up

Alchemy's skill side is fixed and its product side is *mostly written and partly
unreachable*. The single highest-value change is five lines: make the
`CRAFT_POTIONS` guard **ask** `CraftPotionsGoal` whether it has work instead of
restating the question, which switches on a boost-stock arm that already exists,
is already tested, and today cannot run — the same defect, one module over, that
`c7c3de9f` just fixed. Ship it behind wave 6 §5.3's order-book fixture, with a
firing-rate gate, after resolving whether that arm should size to the level ramp
or the combat-projected target. Do not put potions back on the gear sheet, do not
revive the family weight, and do not build anything for the eight potions the
fleet has never been able to craft.

---

## Correction — the guard DOES have a boost-stock arm (2026-08-26)

The section above states that `craft_potions_fires` has no non-heal stock arm,
and that arm 3's precondition is "exactly the negation of the guard's two arms —
reachable only when the guard returns False". **That is wrong, and it inverts the
recommendation.** Verified by reading `potion_supply.py`:

    :190  target = target_potion_pure(...)          # heal target
    :204  combat_monster = primary_combat_target(...)
    :207  baseline = potion_stock_target_pure(hp_need, ...)
    :210  if equipped >= baseline:                  # HEAL STOCK SATISFIED
    :211      monster = primary_combat_target(...)
    :213      boost = best_boost_potion(state, game_data, monster)
    :217      if boost is not None and equipped_potion_qty(state, boost) < boost_baseline:
    :219          if boost_recipe and _recipe_producible(...):
    :220              return True                    # <-- THE BOOST-STOCK ARM

The guard has THREE arms, not two: unlock-boost (`:184-189`), boost-stock
(`:210-220`), and heal-deficit (`:222-225`). The boost-stock arm's precondition —
heal stock satisfied — is exactly arm 3's `deficit <= 0`, not its negation. And
the guard's own comment records that the heal baseline was deliberately unified
with the goal's ("Same core the goal sizes from, so the two cannot diverge").

**So piece A is not a deletion.** Guard and goal are already paired on this arm.

### What IS true, measured

- **Offline: arm 3 never fires.** Across all 42 scenarios the guard fires in 5,
  and every one takes arm 2 (heal). Arm 3: **0**. So the arm is unexercised by
  the suite — a coverage gap, which is what the matrix exists to close.
- **Live: boost potions ARE crafted.** `CraftPotionsGoal` produced
  `water_boost_potion` (26) and `air_boost_potion` (25 + 18) crafts, the most
  recent at 2026-08-26T00:35Z. Boost crafting is live behaviour, not theory.
- **Live attribution is BLOCKED.** Whether those crafts came from arm 1
  (unlock-boost, `runs=1`) or arm 3 (boost-stock, `runs` from a deficit) cannot
  be recovered from `learning.db`: `cycles.action_repr` records the executed
  action, not which goal arm chose it. This is the same observability gap the
  2026-08-24 Robby investigation hit, where the executed grind leg had to be
  inferred from map tiles and cooldown durations.

### What this changes about the scoping

The actionable items are now: (a) a scenario that exercises the guard's
boost-stock arm, so arm 3 stops being suite-invisible; and (b) recording which
goal arm produced a craft, so live attribution stops requiring inference. (b) is
the general fix and would have paid for itself twice already.

`potion_type_weight` and `utility_potion_targets` are unaffected — both declines
above stand on their own measurements (`utility_potion_targets` emits heals only;
`potion_type_weight` is a fifth multiplier with no classifier in `src/`).
