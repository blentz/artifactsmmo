# Obtain-Model Parity Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_obtain_parity.py`.
>
> Census drives the REAL `StrategyArbiter.select` seam over the committed bundle, then compares the two plan producers (O(closure) descent and A*) and the shared obtain model. WITHDRAW is carved out of every comparison (the descent serves it via recipe-input withdraw, not a map leg); every other kind is compared in full.

6 cells; PASS 6; obtain_parity_bug 0

| Cell | Material | needed | model | pool(applicable) | descent | A* | P⊆M | M⊆P | parity | Verdict | Goal |
|---|---|---|---|---|---|---|---|---|---|---|---|
| gather | copper_ore | 5 | gather | gather | gather | gather | True | True | True | PASS | `GatherMaterials(copper_ore, {copper_ore:5})` |
| craft | copper_bar | 3 | craft | · | craft,gather | craft,gather | True | True | True | PASS | `GatherMaterials(copper_bar, {copper_bar:3})` |
| withdraw | copper_bar | 3 | craft | · | craft | craft | True | True | True | PASS | `GatherMaterials(copper_bar, {copper_bar:3})` |
| recycle | ash_plank | 4 | craft,recycle | recycle | recycle | recycle | True | True | True | PASS | `GatherMaterials(ash_plank, {ash_plank:4})` |
| buy | cloth | 2 | buy | buy | buy | buy | True | True | True | PASS | `GatherMaterials(cloth, {cloth:2})` |
| drop | feather | 2 | drop | drop | drop | drop | True | True | True | PASS | `GatherMaterials(feather, {feather:2})` |

