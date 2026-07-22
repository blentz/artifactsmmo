# Craft-Planning Completeness — PLANNER_BUG Backlog

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 1758 cells; PASS 537 (31%); nominal-at-skill PASS 82/321; gaps: event_gated 709, combat_blocked 490, material_unreachable 3, skill_unreachable 0, grey_farm_suppressed 1, purchase_recursion 18, planner_bug 0

No PLANNER_BUG cells — every FAIL is an explained limit (event/combat/material/grey-farm policy, a skill prerequisite, or the tracked purchase-recursion gap). The planner produces a directional plan for every recipe cell it is aimed at with the skill in hand.
