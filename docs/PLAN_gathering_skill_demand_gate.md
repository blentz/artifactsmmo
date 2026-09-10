# Gathering skills are not direct grind targets

Status: design, not yet implemented.
Date: 2026-09-10.

## The principle

Fishing, mining and woodcutting do not need to be direct grind targets. Recipes
require the grind indirectly: a cooking rung needs `cooked_trout`, which needs
`trout`, which needs fishing@20. The skill climb should be pulled by the thing
that needs it, not pursued for its own sake.

## What the code does today

`decisions/root.py::_orphan_skill_roots` offers a `ReachSkillLevel(S, C+1)` root
for every skill that satisfies two conjuncts:

1. no gear target can name it (`_gear_nameable_skills`, a property of the
   catalogue), and
2. it has an open, XP-positive rung (`LevelSkill(S, C+1).is_applicable`).

The group is appended last in `resolve_root` (root.py:852), behind the gear
siblings and behind the trunk, and is reached only when no gear step and no
trunk step can be served — "where the bot used to emit `Wait`". Within the group
the order is one integer, `skill_level - character_level`, most-neglected first,
tie-broken by `SKILL_NAMES`.

Conjunct 1 admits every gathering skill by construction. `crafting_skill` takes
exactly seven values in the live catalogue — gearcrafting 132, weaponcrafting 69,
jewelrycrafting 50, alchemy 25, cooking 20, mining 14, woodcutting 11 — and gear
is crafted by the first three. So fishing, mining, woodcutting, cooking and
alchemy all fall out as orphans.

The function's docstring says the rule admits exactly four skills (cooking,
fishing, mining, woodcutting). Live it admits five: alchemy is in too. The
docstring is stale and is corrected as part of this work.

## The measured problem

Over the 24h to 2026-09-10T11:22Z, R2D2 and Robby each spent ~617 cycles on
`ReachSkill(fishing->N)` for **0 character XP**. Both are grey-walled: no gear
step servable, and the trunk's `GrindCharacterXP` pays nothing because every
beatable monster is grey. So the walk falls through to the orphan group, where
fishing ranks first because it is the most neglected skill.

Neither character needs fishing. Measured against live state:

| char | cooking rung | needs | fishing gate | has | unmet demand |
|---|---|---|---|---|---|
| HAL | ->17 | `cooked_shrimp` -> `shrimp` | fishing@10 | 8 | fishing@10 |
| C3P0 | ->23 | `cooked_trout` -> `trout` | fishing@20 | 8 | fishing@20 |
| Lor | ->32 | `cooked_bass` -> `bass` | fishing@30 | 7 | fishing@30 |
| R2D2 | ->17 | `cooked_shrimp` -> `shrimp` | fishing@10 | 13 | none |
| Robby | ->17 | `cooked_wolf_meat` (monster drop) | — | 12 | none |

The three characters with real fishing demand are being pulled there by cooking,
which is the mechanism working correctly. The two characters grinding fishing
are the two with no demand at all.

## Two rejected designs, and why

Both were measured before being discarded. Neither is inert by argument; each
produces a byte-identical result on real inputs.

**Rejected: reorder the group demand-first.** R2D2 and Robby have an empty
demand vector, so every orphan ties, the fallback fires, and the order is
unchanged.

**Rejected: replace the order integer with "levels of demand unmet".** Produces
an identical order for all five live characters:

```
char    TODAY (neglect gap)                    NEW (demand shortfall)
R2D2    fishing alchemy mining cooking wood    fishing alchemy mining cooking wood
Robby   fishing cooking alchemy mining wood    fishing cooking alchemy mining wood
HAL     fishing wood alchemy cooking mining    fishing wood alchemy cooking mining
C3P0    fishing wood alchemy mining cooking    fishing wood alchemy mining cooking
Lor     fishing wood alchemy mining cooking    fishing wood alchemy mining cooking
```

The two integers are correlated: fishing is the most-neglected skill on every
character, and where it is demanded at all it is also the most-demanded. No
ordering change to this group can move R2D2 or Robby, because fishing ranks
first under every key available. The lever is admission, not order.

## The design

Add a third admission conjunct for the three gathering skills only:

3. for `S` in {fishing, mining, woodcutting}, some offered root's requirement
   closure must contain an item whose gather gate for `S` exceeds the
   character's current level.

Cooking and alchemy keep unconditional roots. Their recipes produce consumables
the bot actually spends, so the group is never empty and the anti-`Wait`
guarantee the seam exists for is preserved without a special case.

An admitted demanded skill emits the **demanded** level, not `C+1`. HAL needs
fishing@10 and today is offered `fishing->9`, which completes and re-emits — the
same one-rung churn with no destination. Undemanded skills (cooking, alchemy)
keep `C+1`.

### The demand predicate

`tiers/objective_needs.py::_add_skill_gate` currently reads only
`stats.crafting_skill`, and only for closure items that are craftable. It must
also read the gather leg via `requirement_graph._gather_skill_by_item`, which
maps all 43 gatherable items to `(skill, level)` — woodcutting 13, mining 13,
fishing 12, alchemy 5.

This is load-bearing, not a tidy-up. `crafting_skill` is never `fishing`, so
without the gather leg the predicate could never name fishing and the gate would
drop it unconditionally — the right answer for R2D2 by accident and the wrong
rule for HAL.

### Seeding demand from a skill root

A `ReachSkillLevel` root names no item, so its demand is invisible to a closure
walk over `.code`. This is the same blind spot already recorded for the supply
link. Seed it with `tiers/skill_grind_target.skill_grind_target(skill, state,
game_data)`, which returns the item the character would craft for that rung —
`ReachSkillLevel(cooking, 23)` seeds `cooked_trout`, whose closure carries
`trout -> fishing@20`.

Guard against recursion: seed only for non-gathering skill roots. A gathering
root seeding its own demand would be circular.

### Ordering

Unchanged. The group keeps its single integer, `skill_level -
character_level`, tie-broken by `SKILL_NAMES`. This design deliberately does not
touch it — the docstring's "if the order is wrong, change WHICH integer it is,
not how many" stands, and the measurement above shows the order was never the
defect.

## Projected effect

Live, from the same states measured above:

| char | fishing demand | admitted | orphan head becomes |
|---|---|---|---|
| R2D2 | none | dropped | `alchemy->16` |
| Robby | none | dropped | `cooking->17` |
| HAL | fishing@10 | kept | `fishing->10` (was `->9`) |
| C3P0 | fishing@20 | kept | `fishing->20` (was `->9`) |
| Lor | fishing@30 | kept | `fishing->30` (was `->8`) |

Across the 44-scenario census set (`ai/scenario.SCENARIOS`):

```
fishing      admitted_today=44  demanded= 4  would_drop=40
mining       admitted_today=44  demanded= 0  would_drop=44
woodcutting  admitted_today=44  demanded= 0  would_drop=44
orphan HEAD changes: 2 of 44 scenarios
```

## Flagged decision: mining and woodcutting

Their demand is zero in all 44 census scenarios and all 5 live characters. For
them the gate is not a gate — it is a deletion, and it removes the root
permanently rather than conditionally.

That is a stronger change than "stop grinding a skill nothing asks for", and it
is recorded here rather than buried because it may be wrong. Two readings:

- **Correct.** Mining and woodcutting feed refining recipes (ore->bar,
  wood->plank) whose `crafting_skill` IS mining/woodcutting, so those levels get
  pulled through conjunct 1's own path — `classify_target` already sets
  `blocking_skill` from `crafting_skill`, which is how `maple_plank` reports
  woodcutting@40. The orphan root is redundant for them.
- **Premature.** Zero demand across every state measured may mean the demand
  predicate does not see their demand rather than that none exists. The
  characters measured all sit at mining 15-21 and woodcutting 13-24 while
  chasing buy-only or drop-only gear, which is a narrow sample.

The implementation must resolve this before the gate ships for mining and
woodcutting. If the second reading holds, ship the gate for fishing only. The
increment is separable and the fishing case is the one with live evidence
behind it.

## Effect on the O1 census

`audit/open_rung_completeness.routed_skills` collects `goal.skill` for every
`ReachSkillLevel` in root plus alternatives. It reads `.skill` and never
`.level`, so changing the emitted target level cannot affect it.

The gate can only shrink the routed set, and `O1_SILENT_STALL` fires on
routed-AND-no-open-rung. The orphan seam's conjunct 2 already refuses a skill
with no open rung, so it contributes no such cell today; removing routes cannot
create one. Cells with an open rung classify `OPEN_RUNG` regardless of routing.

This reasoning predicts an unchanged verdict distribution. It is a prediction,
not a proof: the implementation runs the census before and after and pins the
diff. If any cell moves, the reasoning above is wrong and the design stops for
review rather than absorbing the change.

## Files

- `src/artifactsmmo_cli/ai/decisions/root.py` — third conjunct, demanded target
  level, stale docstring (four skills -> five).
- `src/artifactsmmo_cli/ai/tiers/objective_needs.py` — gather leg in
  `_add_skill_gate`.
- `src/artifactsmmo_cli/audit/open_rung_completeness.py` — before/after census
  diff; changes only if a cell moves.

## Testing

- The demand predicate names fishing for a state needing `trout` at fishing<20,
  and does not for fishing>=20. Fails today: `_add_skill_gate` cannot name
  fishing at all.
- `_orphan_skill_roots` drops fishing with no demand and keeps it with demand,
  each with a vacuity guard asserting the other conjuncts are satisfied, so the
  assertion can only come from the new one.
- An admitted demanded skill emits the demanded level, not `C+1`.
- Cooking and alchemy are admitted with no demand — the anti-`Wait` floor.
- The R2D2 and Robby states above, driven through the real `resolve_root`, no
  longer offer a fishing root; the HAL, C3P0 and Lor states still do. This is
  the runtime-activation check, and it runs through the real walk rather than
  the helper.

## Residual

The gate answers "does anything ask for this skill", not "is this skill the best
use of the next cycle". A grey-walled character with no demand and no servable
gear step still has nothing good to do; it will now climb cooking or alchemy
instead of fishing. That is a better filler, not an escape. The grey wall itself
is out of scope here.
