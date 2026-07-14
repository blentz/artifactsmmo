# Recycle-as-a-Source Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_recycle_source_completeness.py`.
>
> Census drives the REAL `StrategyArbiter.select` seam over the committed bundle — the seam where `license_destructive_actions` runs, so the SAFETY cell sees the same LICENSED action pool production does.

5 cells; PASS 5; recycle_source_bug 0

| Cell | Source | Material | needed | recoverable | destroyable | Verdict | Goal | Plan |
|---|---|---|---|---|---|---|---|---|
| liveness | water_bow | ash_plank | 4 | 4 | 2 | PASS | `GatherMaterials(ash_plank, {ash_plank:4})` | `Recycle(water_bow×1) → Recycle(water_bow×1)` |
| safety | copper_axe | copper_bar | 6 | 0 | 0 | PASS | `GatherMaterials(copper_bar, {copper_bar:6})` | `Gather(copper_rocks) → Craft(copper_bar×6)` |
| banked | water_bow | ash_plank | 4 | 4 | 2 | PASS | `GatherMaterials(ash_plank, {ash_plank:4})` | `Withdraw(water_bow×1) → Withdraw(water_bow×1) → Recycle(water_bow×1) → Withdraw(water_bow×1) → Recycle(water_bow×1)` |
| partial | water_bow | ash_plank | 8 | 4 | 2 | PASS | `GatherMaterials(ash_plank, {ash_plank:8})` | `Recycle(water_bow×1) → Recycle(water_bow×1) → Gather(ash_tree) → Craft(ash_plank×4)` |
| partial_protection | copper_helmet | copper_bar | 6 | 3 | 1 | PASS | `GatherMaterials(copper_bar, {copper_bar:6})` | `Recycle(copper_helmet×1) → Gather(copper_rocks) → Craft(copper_bar×3)` |

