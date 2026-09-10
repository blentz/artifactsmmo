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

Add a third admission conjunct, applied uniformly to every gathering skill:

3. for a skill `S` that gates a gathered leaf, some offered root's requirement
   closure must contain an item whose gather gate for `S` exceeds the
   character's current level.

"A skill that gates a gathered leaf" is read from `_gather_skill_by_item`, not
from a hardcoded set. The rule does not name skills individually: one shape, one
conjunct, no per-skill arms.

Read off the live catalogue that set is {alchemy, fishing, mining, woodcutting}.
Alchemy is in it because it gathers herbs, and it takes the gate on exactly the
same terms — naming it an exception would be the per-skill carve-out this rule
exists to avoid.

Cooking is the one skill that gathers nothing, so it never enters the conjunct
and keeps its unconditional root. It is the anti-`Wait` floor: measured across
`ai/scenario.SCENARIOS`, cooking is admitted as an orphan in 44 of 44 scenarios
and the orphan group is empty in 0 of 44 after the gate.

An admitted demanded skill emits the **demanded** level, not `C+1`. HAL needs
fishing@10 and today is offered `fishing->9`, which completes and re-emits — the
same one-rung churn with no destination. Cooking, ungated, keeps `C+1`.

### The demand predicate

`tiers/objective_needs.py::_add_skill_gate` currently reads only
`stats.crafting_skill`, and only for closure items that are craftable. It must
also read the gather leg via `requirement_graph._gather_skill_by_item`, which
maps all 43 gatherable items to `(skill, level)` — woodcutting 13, mining 13,
fishing 12, alchemy 5.

This is load-bearing, not a tidy-up, and it is ONE rule covering every gathering
skill — not a fishing workaround. The gather gate tables are the same shape:

```
mining       copper_ore@1 topaz_stone@1 ... iron_ore@10 coal@20 gold_ore@30
             strange_ore@35 mithril_ore@40 adamantite_ore@50        (13 gates)
woodcutting  ash_wood@1 sap@1 apple@1 ... spruce_wood@10 birch_wood@20
             dead_wood@30 maple_wood@40 palm_wood@50                (13 gates)
fishing      gudgeon@1 algae@1 shell@1 shrimp@10 trout@20 bass@30
             salmon@40 swordfish@50                                 (12 gates)
```

and the predicate reads them identically. Measured: `iron_boots`' closure carries
`iron_ore -> mining@10`; `hard_leather_pants` carries `coal -> mining@20` and
`iron_ore -> mining@10`; `ash_plank` carries `ash_wood -> woodcutting@1`. With
mining forced to 1, `iron_boots` yields unmet demand `{'mining': 10}` — the same
answer the same code gives for `trout -> fishing@20`.

Without the gather leg the predicate names none of them from a gathered leaf.
`crafting_skill` covers mining and woodcutting only through their REFINING
recipes (ore->bar, wood->plank), which is a different leg answering a different
question, and it never covers fishing at all because no item is crafted with
`crafting_skill == "fishing"`.

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
alchemy      admitted_today=44  demanded= 0  would_drop=44
cooking      admitted_today=44  ungated (gathers nothing)
orphan HEAD changes:          2 of 44 scenarios
orphan group EMPTY after gate: 0 of 44 scenarios
```

### Reading the mining and woodcutting zeros

They are the same rule returning a different answer on different data, NOT
evidence that mining and woodcutting are a different case. Every character
measured is already past the gates that would fire: mining 15-21 against
`iron_ore@10` and `coal@20`, woodcutting 13-24 against `spruce_wood@10` and
`birch_wood@20`. Demand is zero because it is MET.

Held against a state where it is unmet, the same predicate names them. With
mining forced to 1, `iron_boots` yields `{'mining': 10}` — structurally the same
answer as `cooked_trout -> trout -> fishing@20` for fishing.

So every gathering skill takes the gate on the same terms, ships in the same
increment, and gets one rule in the code. There is no fishing-only increment and
no separate decision for mining and woodcutting: a per-skill carve-out here would
encode a difference that the catalogue does not have.

The zeros do mean the gate is near-inert for mining and woodcutting on TODAY's
fleet. That is the correct behaviour — nothing is asking for those levels right
now — and it is why the live evidence for the change comes from fishing.

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

- The demand predicate names the gating skill from a gathered leaf, PARAMETRISED
  over the gathering skills rather than written once for fishing: `trout` at
  fishing<20, `iron_ore` at mining<10, `ash_wood` at woodcutting<1. Each names
  its skill when short and does not when met. Fails today for every one of them:
  `_add_skill_gate` reads only `crafting_skill`.
- `_orphan_skill_roots` drops a gathering skill with no demand and keeps it with
  demand — same parametrised cases, so a per-skill regression cannot hide behind
  the fishing case. Each with a vacuity guard asserting the other two conjuncts
  are satisfied, so the assertion can only come from the new one.
- An admitted demanded skill emits the demanded level, not `C+1`.
- Cooking is admitted with no demand — the anti-`Wait` floor. Alchemy is NOT,
  because it gathers; the pair pins that the split follows the gather map rather
  than a hand-written list.
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
