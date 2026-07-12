# Craft-Planning Completeness

Census of the AI player's planner: of the game's craftable recipes, for how
many can the planner produce a *directional* plan toward making the item, from
a plausible under-progressed state? The analogue of
`docs/behavioral_completeness/` for crafting recipes — it validates the RUNNING
planner (not a proof), turning "gap discovered by chance" (GAP-8, GAP-9) into
"enumerated".

- [`MATRIX.md`](MATRIX.md) — every craftable recipe x its level/skill census
  cells → PASS or gap-class, grouped by craft skill × tier. Generated.
- [`BACKLOG.md`](BACKLOG.md) — the ranked `PLANNER_BUG` fix-queue (recipes the
  planner failed on despite every closure leaf being reachable). Generated.
- Spec: [`../superpowers/specs/2026-07-08-craft-planning-completeness-design.md`](../superpowers/specs/2026-07-08-craft-planning-completeness-design.md)
- Plan: [`../superpowers/plans/2026-07-09-craft-completeness-phase2-generator.md`](../superpowers/plans/2026-07-09-craft-completeness-phase2-generator.md)

## Gap classes

Every FAIL cell is classified by an ORDERED cascade (`classify_gap`), so
`PLANNER_BUG` means only an UNEXPLAINED failure — the actionable residual.

Game / policy limits (a FAIL here is expected, not a planner defect):

- `EVENT_GATED` — a closure leaf's only source is a timed event, absent from the
  event-free audit.
- `COMBAT_BLOCKED` — a leaf's only source is a permanently-spawning monster the
  cell's loadout can't beat yet.
- `MATERIAL_UNREACHABLE` — a leaf has no reachable source at all (includes a
  drop whose only resource is UNPLACED in the bundle, e.g. diamond_stone).
- `GREY_FARM_SUPPRESSED` — a monster-drop leaf's only dropper is grey (zero xp)
  and `grey_farm_allowed` declines the farm because a near next-tier same-family
  recipe is the better skill-grind. The intended grey-farm policy.

Census-aim / known-scope limits:

- `SKILL_UNREACHABLE` — the recipe's crafting skill is below its level AND cannot
  be bootstrapped from the cell at all (no in-band craftable/gatherable rung to
  grind on). A GRINDABLE under-skill cell is NOT a gap: the planner-native
  `LevelSkill` action (epic) plans `grind-skill → craft`, so the cell PASSES on
  a `LevelSkill` first leg (formerly the retired `SKILL_PREREQUISITE` class).
- `PURCHASE_RECURSION` — a leaf's only source is a permanent vendor selling it
  for a TASK-earned currency (e.g. jasper_crystal @ tasks_trader for
  tasks_coin). The recursive Task → earn-coin → NpcBuy edge is the tracked
  `npc_purchase_acquisition` Phase 2-4 feature, not yet planned.
- `PURCHASE_RECURSION` — a leaf's only source is a permanent vendor selling it
  for a TASK-earned currency (e.g. jasper_crystal @ tasks_trader for
  tasks_coin). The recursive Task → earn-coin → NpcBuy edge is the tracked
  `npc_purchase_acquisition` Phase 2-4 feature, not yet planned.

- `PLANNER_BUG` — the residual: every leaf reachable, the skill at level, yet no
  directional plan. **This count is an ongoing CI requirement: it must stay 0.**

## How to regenerate

```
uv run python scripts/gen_craft_completeness.py
```

Offline (loads the committed bundle, no API). Parallel across a process pool
(one GameData per worker) — ≈ 70 s on 32 cores over ~1758 cells (was ≈ an hour
serial); pass an optional worker count as the sole argument. A minority of cells
hit the planner's 10 s wall-clock budget and their verdict can vary between
regens — treat borderline cells as approximate, and regenerate on an idle
machine (the budget is wall-clock, so heavy concurrent CPU load inflates
timeouts). The SUMMARY line printed at the end is the completeness metric
tracked over time.
