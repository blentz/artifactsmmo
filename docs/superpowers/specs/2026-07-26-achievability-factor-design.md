# Achievability factor: down-weight gear by effort-to-reach

Status: design agreed 2026-07-26. Not implemented.

## Problem

The gear ranking is blind to how hard a candidate is to obtain. Live, Robby at
level 21:

| Candidate | gain | how it is actually obtained |
|---|---|---|
| `lich_race_trophy` | **25050** | buy for 10 × `lich_race_medal`, each 100 × `event_ticket` = **1000 tickets** |
| `life_ring` | 21020 | craft at jewelrycrafting 15 (have 10) from gatherable materials |
| `adventurer_pants` | 15019 | craft at gearcrafting 15 (have 10) from gatherable materials |
| `adventurer_boots` | 10041 | craft at gearcrafting 15 (have 10) |
| `mushmush_jacket` | 6990 | craft at gearcrafting 15 (have 10) |

`lich_race_trophy` wins on gain alone and the shorter chains queue behind it.
The selection weight is `gain * falloff(focus) * synergy` — magnitude,
staleness, alignment. Nothing expresses **effort to reach**.

Observed consequence: the tree picks `lich_race_trophy`, it is unservable, and
`_servable_promotion` walks the fallback list — where `ReachCharLevel(30)` sits
at index 0, ahead of every gear candidate. The bot levels instead of gearing.

### What this is NOT

An earlier attempt (ee9ea438, reverted in 3328a1eb) made currency passivity
transitive so `lich_race_trophy` stopped arming a dedicated currency grind. That
changed *servability*, not *ranking*: the trophy still sorted first at 25050
either way. Suppressing a grind does not reorder candidates. This spec addresses
the ranking.

## Design

### Where it plugs in

A `(slot, code) -> Fraction` map, built in `progression_tree.py` exactly as
`_synergy_map` is, and multiplied into `_scaled_weights`:

```
weight = gain * falloff(focus) * synergy * achievability
```

Same key, same bounded shape, same construction site. A fourth factor in an
established pattern.

### Where it sits in the factor hierarchy

The codebase already ranks its factors by range, deliberately:

| Factor | Range | Rationale (existing) |
|---|---|---|
| `falloff` (aging) | 9:1 (`FOCUS_FLOOR = 1/9`) | dominates everything — a stuck root always decays |
| `synergy` (alignment) | 3:1 (`S_MIN = 1/3`) | "strictly inside falloff's 9:1 so aging structurally dominates alignment" |
| **achievability** | **2:1 (`A_MIN = 1/2`)** | strictly inside synergy's 3:1 — effort informs, never dictates |

`A_MIN = Fraction(1, 2)`. This is the ONLY tuning surface, mirroring
`S_MIN`'s docstring discipline.

It satisfies the requirement it exists for: flipping `lich_race_trophy` (25050)
below `life_ring` (21020) needs an achievability ratio under 21020/25050 = 0.84,
and a 2:1 range reaches 0.5. It also bounds the blast radius — a maximally
unachievable candidate can only lose to a maximally achievable one when the gain
gap is under 2×, so a genuinely enormous upgrade still wins.

### Effort = UNMET demand

The naive magnitude of `requirement_multiset_for` ranks backwards:

```
lich_race_trophy   total=   11     <- the 1000-ticket item looks CHEAPEST
adventurer_pants   total=  805     (gold=700)
adventurer_boots   total= 1321     (gold=1250)
life_ring          total= 2106     (gold=2000)
```

Two reasons, both fixed by the definition below:

```
effort(c) = SUM over tokens of max(0, demand(token) - held(token))
```

* **Gold stops dominating.** `life_ring` demands 2000 gold; Robby holds 12382,
  so its contribution is 0. Total demand ranks by price tag; unmet demand ranks
  by difficulty.
* **Skill tokens count as the LEVEL DEFICIT.** `skill:jewelrycrafting` with
  recipe level 15 against skill 10 contributes 5. This is what makes a
  skill-gapped item cheaper than a currency-gated one rather than equally
  blocked — the distinction the whole feature turns on.

### The weight function is self-scaling

No absolute effort constant. Achievability is relative to the cheapest candidate
in the same decision:

```
r(c)            = (min_effort + 1) / (effort(c) + 1)      -> (0, 1]
achievability(c) = A_MIN + (1 - A_MIN) * r(c)             -> [A_MIN, 1]
```

The `+1` smoothing avoids a divide-by-zero when something is fully held, and
avoids a cliff where one zero-effort candidate slams every other to the floor.

MEASURED against Robby's live state and holdings (2026-07-26), with the
transitive expansion of §1 applied:

| Candidate | gain | effort | achievability | weight | order |
|---|---|---|---|---|---|
| `life_ring` | 21020 | 32 | 0.788 | **16561** | **1st** |
| `lich_race_trophy` | 25050 | **1000** | 0.509 | 12763 | 2nd |
| `adventurer_pants` | 15019 | 41 | 0.726 | 10907 | 3rd |
| `adventurer_boots` | 10041 | 18 | 1.000 | 10041 | 4th |
| `mushmush_jacket` | 6990 | 30 | 0.806 | 5637 | 5th |

**Note (2026-07-26 post-Task 3 correction):** The per-candidate figures above predate the per-skill gate lookup fix in Task 3, which corrected the code to apply the candidate's craft level only to its own recipes, not to every token in the closure. The ordering claim—that a craftable candidate outranks the currency-gated trophy—remains valid. However, at HEAD, the actual live result is:
- `chosen_root: ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')`
- `chosen_step: ObtainItem(code='ash_plank', quantity=7)`
- `lich_race_trophy` remains the raw-gain argmax at 25050 but is no longer picked.

The desired reordering, from the real catalog and real holdings. Note
`lich_race_trophy` lands 2nd, not last — down-weighted, not banished, which is
the stated intent.

### The prerequisite is load-bearing, and this was measured too

The same computation WITHOUT §1's transitive expansion:

| Candidate | gain | effort | achievability | weight | order |
|---|---|---|---|---|---|
| `lich_race_trophy` | 25050 | **11** | 1.000 | **25050** | **1st** |
| `life_ring` | 21020 | 107 | 0.556 | 11678 | 2nd |

Un-expanded, the trophy's effort is 11 (10 medals plus itself), it reads as the
CHEAPEST candidate in the list, and the factor makes the ordering *worse* than
today — it hands the most expensive item a perfect achievability score. §1 is
therefore a hard prerequisite, not an optimisation: shipping the factor without
it is a regression.

## Prerequisite corrections

Two existing defects must be fixed first, or the factor computes on bad input.

### 1. Currency expansion must be transitive

`requirement_graph_memo.py:134-140` enriches a BUY leaf with `price * quantity`
in its currency, but only for items IN the closure. `lich_race_medal` is not
itself a closure member, so its own 100-ticket price is never expanded:
`lich_race_trophy` scores `total=11` and reads as the cheapest candidate in the
list.

The recursion belongs here — in the requirement expansion that feeds ranking —
not in the passivity gate that feeds grind suppression, which is where the
reverted attempt put it. Needs cycle protection (currency A priced in B priced
in A) and a depth bound.

This also fixes synergy, which consumes the same multiset and is today blind to
the same 1000 tickets.

### 2. The reduction must be holdings-aware

`requirement_multiset_for` is a static per-item memo (`_multiset_cache`), and
must stay that way — synergy's caching depends on it. Effort is therefore a
SEPARATE state-aware reduction over the memo's output, not a change to the memo.

## The flat-window trap

`focus_aging_pick` short-circuits to the plain `gear_target_pick` argmax while
every candidate is inside `FOCUS_FLAT` **and** every synergy factor is 1. Its
docstring records why the synergy half of that condition is load-bearing:
without it, synergy was "silently inert for the first FOCUS_FLAT cycles of every
root — exactly the window where it matters most".

Achievability must extend the same clause or it inherits the identical bug —
and inherits it in precisely the window that matters, since a fresh gear
decision is exactly when effort should be consulted.

## Testing

**Falsifiability is the acceptance criterion**, not coverage. The factor must be
switchable by holdings:

1. With Robby's real state, `life_ring` outranks `lich_race_trophy` (measured:
   16561 vs 12763). `adventurer_pants` need NOT outrank it — at gain 15019 it
   lands 3rd, which is the correct outcome of a factor that informs rather than
   dictates, and pinning it above the trophy would be pinning a number the
   design does not claim.
1b. Ordering must be asserted on the ACHIEVABILITY-WEIGHTED order, not on the
   `RootScore` rows: `progression_tree.py:152` records that those rows are
   display-only ("no separate weighting exists in this display path"). A test
   reading them would pass while the real order was unchanged — the exact
   vacuousness this project guards against.
2. With a synthetic state holding 1000 `event_ticket`, `lich_race_trophy`
   returns to the top — its effort collapses to ~0. A factor that cannot be
   switched off by holdings is not measuring effort.
3. `A_MIN` pinned by a test AND a mutation anchor (it is a live decision knob;
   see `POTION_LEAD_FIGHTS` for the precedent).
4. Transitive expansion: `lich_race_trophy`'s multiset contains ~1000
   `event_ticket`, not 10 `lich_race_medal`.
5. Cycle protection: a currency priced in itself terminates.

## Risks

| Risk | Mitigation |
|---|---|
| `_gear_pref_key` "Mirrors Lean `Formal.ProgressionTree.better`", and `synergy` has `Synergy.lean` — a new weight factor likely carries a Lean obligation | Establish the Lean surface BEFORE implementing; if `better` moves, the proof moves in the same commit. This is the largest unknown in the plan and may dominate its cost. |
| Effort recomputed per candidate per cycle could be slow | The multiset is already memoized; only the unmet-demand reduction is per-cycle, over a small token map. Measure before optimising. |
| Down-weighting could starve a long-chain item forever | `A_MIN > 0` and `falloff`'s 9:1 still dominates, so d'Hondt awards it a seat eventually (`interleaveDue_reaches`, resting on `minWeight_pos`) — the same anti-starvation argument synergy relies on. |

## Out of scope

* The **trunk at fallback index 0**. Even correctly reordered, gear candidates
  sit behind `ReachCharLevel(30)` in `_servable_promotion`'s walk, so an
  unservable top pick still promotes levelling over gear. Separate defect,
  separate fix.
* **Nothing raises the crafting skills.** Every tier-3 candidate needs skill 15
  against Robby's 10, and character XP does not raise gearcrafting. Whether a
  candidate blocked only by a skill gap should be servable-via-`LevelSkill` is a
  separate design question — and is what would actually get tier-3 gear built.
* The reverted transitive-passivity change. It may hold on its own merits; it is
  a grind-suppression question, judged separately.
