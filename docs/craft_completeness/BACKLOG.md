# Craft-Planning Completeness — PLANNER_BUG Backlog

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 2418 cells; PASS 565 (23%); recipes PASS 114/321; nominal-at-skill PASS 103/321; gaps: event_gated 660, combat_blocked 1078, material_unreachable 87, skill_unreachable 0, grey_farm_suppressed 1, purchase_recursion 0, crossing_unaffordable 27, planner_bug 0

No PLANNER_BUG cells — every FAIL is an explained limit (event/combat/material/grey-farm policy, a skill prerequisite, or the tracked purchase-recursion gap). The planner produces a directional plan for every recipe cell it is aimed at with the skill in hand.
