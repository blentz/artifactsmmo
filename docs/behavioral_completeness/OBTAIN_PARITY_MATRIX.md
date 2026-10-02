# Obtain-Model Parity Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_obtain_parity.py`.
>
> Census drives the REAL `StrategyArbiter.select` seam over the committed bundle, then compares the action pool with the shared obtain model and reports the walk's plan. WITHDRAW is carved out of every comparison; every other kind is compared in full.

6 cells; PASS 6; obtain_parity_bug 0

| Cell | Material | needed | model | pool(applicable) | walk | P⊆M | M⊆P | Verdict | Goal |
|---|---|---|---|---|---|---|---|---|---|
| gather | copper_ore | 5 | gather | gather | gather | True | True | PASS | `GatherMaterials(copper_ore, {copper_ore:5})` |
| craft | copper_bar | 3 | craft | · | craft,gather | True | True | PASS | `GatherMaterials(copper_bar, {copper_bar:3})` |
| withdraw | copper_bar | 3 | craft | · | craft | True | True | PASS | `GatherMaterials(copper_bar, {copper_bar:3})` |
| recycle | ash_plank | 2 | craft,recycle | recycle | recycle | True | True | PASS | `GatherMaterials(ash_plank, {ash_plank:2})` |
| buy | cloth | 2 | buy | buy | buy | True | True | PASS | `GatherMaterials(cloth, {cloth:2})` |
| drop | feather | 2 | drop | drop | drop | True | True | PASS | `GatherMaterials(feather, {feather:2})` |

