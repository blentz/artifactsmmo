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

`PLANNER_BUG` (actionable — the planner should have planned), `COMBAT_BLOCKED`,
`EVENT_GATED`, `MATERIAL_UNREACHABLE`, `SKILL_UNREACHABLE` (game limits).

## How to regenerate

```
uv run python scripts/gen_craft_completeness.py
```

Offline (loads the committed bundle, no API). Serial ≈ 50 min over ~1758 cells;
~16% of cells hit the planner's 10 s wall-clock budget and their verdict can
vary between regens — treat borderline cells as approximate. The SUMMARY line
printed at the end is the completeness metric tracked over time.
