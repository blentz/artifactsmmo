# Inventory Keep/Disposal Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_inventory_completeness.py`.
>
> Census drives the REAL `StrategyArbiter.select` seam over the committed bundle. The cell grid is DERIVED from the `KeepReason` registry (`inventory_grid`) — nothing here is hand-picked.


66 cells; PASS 62 (94%); gaps: keep_all_sentinel 0, venue_unreachable 0, bank_full 0, no_route_available 1, inventory_bug 3

Legend: KA=keep_all_sentinel, VU=venue_unreachable, BF=bank_full, NR=no_route_available, IB=inventory_bug.

| Reason | Kind | Code | Cells (cap/pressure → verdict) |
|---|---|---|---|
| active_task | liveness | golden_egg | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full IB |
| active_task | safety | golden_egg | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | liveness | copper_dagger | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| combat_weapon | safety | copper_dagger | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| committed_recipe | liveness | copper_bar | in_bag/qty_full PASS · in_bag/slot_full PASS |
| committed_recipe | safety | copper_bar | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS |
| currency | safety | tasks_coin | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| equipped | liveness | copper_dagger | owned/qty_full PASS · owned/slot_full PASS |
| equipped | safety | copper_dagger | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | liveness | copper_boots | owned/qty_full PASS · owned/slot_full PASS |
| gear_demand | safety | copper_boots | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| goal_materials | liveness | ash_wood | in_bag/qty_full IB · in_bag/slot_full IB |
| goal_materials | safety | ash_wood | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS |
| healing_consumable | liveness | cooked_chicken | in_bag/qty_full PASS · in_bag/slot_full PASS |
| healing_consumable | safety | cooked_chicken | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS |
| recipe_demand | liveness | copper_bar | owned/qty_full PASS · owned/slot_full NR |
| recipe_demand | safety | copper_bar | owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | liveness | copper_axe | in_bag/qty_full PASS · in_bag/slot_full PASS · owned/qty_full PASS · owned/slot_full PASS |
| working_kit | safety | copper_axe | in_bag/below_threshold PASS · in_bag/qty_full PASS · in_bag/slot_full PASS · owned/below_threshold PASS · owned/qty_full PASS · owned/slot_full PASS |

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
| goal_materials | FAIL |
| equipped | PASS |
| gear_demand | PASS |
| recipe_demand | PASS |

