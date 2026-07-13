# Inventory Keep/Disposal Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_inventory_completeness.py`.
>
> Census drives the REAL `StrategyArbiter.select` seam over the committed bundle. The cell grid is DERIVED from the `KeepReason` registry (`inventory_grid`) — nothing here is hand-picked.


152 cells; PASS 144 (95%); gaps: keep_all_sentinel 0, venue_unreachable 2, bank_full 0, no_route_available 6, inventory_bug 0

by band: far 72/76 (inventory_bug 0); in_band 72/76 (inventory_bug 0)

Legend: KA=keep_all_sentinel, VU=venue_unreachable, BF=bank_full, NR=no_route_available, IB=inventory_bug.

| Reason | Kind | Band | Code | Cells (cap/pressure → verdict) |
|---|---|---|---|---|
| active_task | liveness | far | golden_egg | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full VU |
| active_task | liveness | in_band | golden_egg | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full VU |
| active_task | safety | far | golden_egg | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| active_task | safety | in_band | golden_egg | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | liveness | far | copper_dagger | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | liveness | in_band | copper_dagger | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | safety | far | copper_dagger | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | safety | in_band | copper_dagger | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| committed_recipe | liveness | far | copper_bar | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full NR |
| committed_recipe | liveness | in_band | copper_bar | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full NR |
| committed_recipe | safety | far | copper_bar | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| committed_recipe | safety | in_band | copper_bar | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| currency | safety | far | tasks_coin | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| currency | safety | in_band | tasks_coin | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| equipped | liveness | far | copper_dagger | owned/qty_full PASS · owned/slot_full PASS |
| equipped | liveness | in_band | copper_dagger | owned/qty_full PASS · owned/slot_full PASS |
| equipped | safety | far | copper_dagger | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| equipped | safety | in_band | copper_dagger | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | liveness | far | copper_boots | owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | liveness | in_band | copper_boots | owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | safety | far | copper_boots | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | safety | in_band | copper_boots | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| goal_materials | liveness | far | raw_beef | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full NR |
| goal_materials | liveness | in_band | raw_beef | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full NR |
| goal_materials | safety | far | raw_beef | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| goal_materials | safety | in_band | raw_beef | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| healing_consumable | liveness | far | cooked_chicken | in_bag/qty_full PASS · in_bag/slot_full PASS |
| healing_consumable | liveness | in_band | cooked_chicken | in_bag/qty_full PASS · in_bag/slot_full PASS |
| healing_consumable | safety | far | cooked_chicken | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS |
| healing_consumable | safety | in_band | cooked_chicken | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS |
| recipe_demand | liveness | far | copper_bar | owned/qty_full PASS · owned/slot_full NR |
| recipe_demand | liveness | in_band | copper_bar | owned/qty_full PASS · owned/slot_full NR |
| recipe_demand | safety | far | copper_bar | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| recipe_demand | safety | in_band | copper_bar | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | liveness | far | copper_axe | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | liveness | in_band | copper_axe | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | safety | far | copper_axe | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | safety | in_band | copper_axe | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |

## Reason coverage (Gate 2 — anti-rot)

Every `KeepReason` except `CURRENCY` must have at least one PASSing LIVENESS cell, or the reason's surplus has never been proven disposable.

| KeepReason | has passing LIVENESS cell |
|---|---|
| currency | PASS (KEEP_ALL exemption) |
| active_task | PASS |
| healing_consumable | PASS |
| combat_weapon | PASS |
| working_kit | PASS |
| committed_recipe | PASS |
| goal_materials | PASS |
| equipped | PASS |
| gear_demand | PASS |
| recipe_demand | PASS |

