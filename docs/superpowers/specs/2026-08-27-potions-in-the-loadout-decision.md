# Potions in the loadout decision — a future feature, scoped and measured

**Status:** NOT STARTED. Scoped 2026-08-27 while finishing wave 6; recorded so
the measurements do not have to be redone.

**Origin (USER, 2026-08-27):**

> `utility_potion_targets` needs new consumers — primarily the OptimizeLoadout
> path. When optimizing loadout, we should consider potion bonuses that help
> fight monsters with elemental weaknesses. Speed boost potions help reduce
> cooldown costs for long-chain gather/craft runs.

The request splits into two halves that are **not** equally buildable. The
elemental half is well-founded and mostly plumbed. The speed half's premise does
not survive the game data, and the blocker is an architectural invariant this
repo has already been burned by four times. Both measurements are below.

---

## 1. Why this is worth doing at all: `utility_potion_targets` is an ORPHAN

`tiers/objective.py:475` defines `utility_potion_targets`, which designates
slot 1 for the primary heal and slot 2 for the secondary. **It has ZERO
production callers.** Its only references are prose — comments in
`potion_supply.py:102,105`, `utility_slot.py:38` and `decisions/root.py:298` —
plus two tests.

It became an orphan in wave 3b, which deleted `progression_tree._utility_candidates`
and `objective_candidates` along with the `objective` CLI that reached them. The
wave-6 design (§5.3) anticipated exactly this and named the risk:

> Do not let a diagnostic-only path keep reading as the decision — that is how
> the next reader concludes potions are still ranked.

So the choice is: give it a real consumer (this feature), or retire it. Leaving
it is the one option the design rules out.

---

## 2. The elemental half — SUPPORTED, and the plumbing is most of the way there

**Measured against the committed bundle, 2026-08-27.** Of 21 utility items, the
effect distribution is:

| effect | items |
|---|---|
| `restore` | 5 |
| `antipoison` | 3 |
| `boost_dmg_{water,fire,air,earth}` | 2 each |
| `boost_res_{air,water,fire,earth}` | 2 each |
| `splash_restore` | 2 |
| `boost_hp` | 1 |

`water_boost_potion` for instance carries `boost_dmg_water` at **12%**, gated at
character level > 9, crafted from blue_slimeball + sunflower + algae.

**The purpose already carries the elemental data.** `pick_loadout`'s purpose is
`Combat(monster_attack, monster_resistance)` (`equipment/loadout_picker.py:121`),
so matching a boost to a monster's weakness needs no new input — the picker
simply stops before the potion slots by design:

> `_UTILITY_FILL_TYPES` … NOT `utility` (consumable/potion slots handled
> elsewhere) — `loadout_picker.py:21`

**Shape of the work.** Extend the Combat purpose's per-slot scoring to the two
utility slots, choosing a boost potion whose element matches the target's
weakness, with `utility_potion_targets` as the producer of "which slot". Nothing
in the actions/seconds boundary is touched, and no new game data is needed.

**What it must not do.** Potions are level-exempt by design
(`tiers/objective.py:474`) and `_tier_gap` is defined in ladder rungs
(`decisions/root.py:193-207`), so this must not put potions back on the tier
ladder — a potion's "gap" and an iron shield's are unrelated scales in one
column, the precise defect wave 3 deleted. Wave 4 §6.1(c) and wave 6 §5.3 both
state this and both are correct.

---

## 3. The speed half — BLOCKED, on two independent grounds

### 3.1 No potion carries haste

47 items in the catalogue carry the `haste` effect. **Every one is gear** —
boots and leg armor (`iron_boots` 3, `adventurer_boots` 4, `steel_legs_armor` 2,
…). Zero utility items carry it. "Speed boost potions" do not exist in this
game's data, so the feature as described has no item to equip.

### 3.2 Haste is a PERMANENT, DOCUMENTED exclusion from the cost model

`audit/stat_projection_completeness.UNPRICED["haste"]`:

> PERMANENT EXCLUSION — not a defect. Haste reduces action COOLDOWN, which is
> measured in SECONDS. `J` is denominated in ACTIONS. A hasted character
> performs the same number of actions, faster. Admitting haste would mix seconds
> into an action count, which is the exact confusion that has produced four
> separate bugs here (`mats_missing` as cost, `DEFAULT_FIGHT_CYCLES` as cycles,
> `cycles_to_fifty` as whole-loop cycles, `cheapest_path_to_level` in seconds).
> Wall-clock deserves its own objective with an explicit conversion, never a
> term smuggled into this one.

Restated at `acquisition_cost_core.py:18` and `equipment/projection.py:88-90`.

### 3.3 And haste is FIGHT-cooldown, not gather/craft

The effect's own description: *"Adds {value} Haste to its stats when equipped.
The haste reduces the cooldown of **a fight**."* So even with a hasted item
equipped, it would not serve "long-chain gather/craft runs" — the stated
motivation.

### 3.4 What the speed intent would actually require

The intent is sound; the route is different from the request:

1. Haste is a **gear** stat, so it belongs to `pick_loadout`'s combat purpose,
   not to a potion slot.
2. Pricing it at all means giving **wall-clock its own objective with an
   explicit seconds→actions conversion**, which is what the UNPRICED entry
   demands. That is a design act, not a wiring change.
3. `stat_projection_completeness` enforces NO STALE EXCLUSIONS — an entry that
   has since become priced FAILS the census. So the registry entry is deletable,
   but only as part of the increment that genuinely prices it.

**Recommendation if this is picked up:** build §2 alone first. It is additive,
uses data that exists, and is independent of §3. Treat wall-clock as its own
scoped question rather than a rider on this one.

---

## 4. Cited measurements, so they need not be redone

* 21 utility items; effect distribution in §2.
* 47 haste carriers, all gear; zero utility.
* `utility_potion_targets`: zero production callers (grep over `src/`,
  excluding comments).
* `pick_loadout` purpose already `Combat(monster_attack, monster_resistance)`.
