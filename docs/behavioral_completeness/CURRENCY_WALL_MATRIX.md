# O7 Currency-Wall Census — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_currency_wall.py`.
>
> Obligation O7 (wave-6 routes design §7): every currency the price walk charged at `UNOBTAINABLE_PER_UNIT` while pricing a root the walk offers (the resolved root or an alternative) is either task-earnable (FUNDED) or falls into a named wall. The residual is a charged currency with a BEATABLE dropper on a live tile — a route the model can see that the price did not take.
>
> `charged` is a differential on production's own pricer: the root is priced as the character stands and again with the currency granted, and a fall in price is the charge. No closure is re-derived here — obligation O6 forbids a second cost model, and this census must not be one.
>
> Every field `classify_gap` reads is a column: `droppers`, `live tiles` and `winnable` are the two conjuncts `ObtainModel._drop` gates on, and `event` separates a dormant event from a permanent monster with no tile.

1491 cells over 7 currencies; charged 25; FUNDED 3; walled 22; not_demanded 1466; root_unresolved 0; o7_silent_currency_stall 0; o7_multi_currency_wall 0; o7_unexplained 0; currency_catalogue_empty 0

residual scope: 25 of 1491 cells are CHARGED (2 distinct currencies) — gold 22, tasks_coin 3. An uncharged currency can only be not_demanded.

| Scenario | Candidate | root? | Currency | Verdict | charged | base | granted | earnable | droppers | live tiles | winnable | event |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l1_fresh | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l8_overstocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_copper_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='blue_slimeball', quantity=2)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='gearcrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_weapon_upgrade | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l3_low_hp | `ObtainItem(code='copper_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='weaponcrafting', level=2)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='mushroom', quantity=4)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_taskgated_bag | `ReachSkillLevel(skill='mining', level=10)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l15_midband | `ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='gearcrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l15_midband | `ReachSkillLevel(skill='jewelrycrafting', level=7)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l40_band_entry | `ReachSkillLevel(skill='jewelrycrafting', level=26)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_capstone_approach | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_band_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_raid_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_raid_active | `ReachSkillLevel(skill='jewelrycrafting', level=36)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l48_event_active | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_bag_pursuit | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_artifact_fill | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='steel_boots', quantity=1, slot='boots_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l35_boots_drop_farm | `ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ObtainItem(code='slime_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='gearcrafting', level=26)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l30_rune_fill | `ReachSkillLevel(skill='jewelrycrafting', level=19)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_dual_utility_one_stocked | `ReachSkillLevel(skill='jewelrycrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l13_drop_recipe_grind | `ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_gearcrafting_gap | `ReachTaskOutcome(task_code='cow')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='jewelrycrafting', level=2)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l10_gearcrafting_gap_combat_blocked | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l21_grey_material_grind | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='weaponcrafting', level=11)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_grey_rung_grind | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='weaponcrafting', level=6)` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='jewelrycrafting', level=3)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ReachSkillLevel(skill='gearcrafting', level=9)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_deep_chain_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l19_band_edge | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l19_band_edge | `ReachSkillLevel(skill='jewelrycrafting', level=15)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='leather_boots', quantity=1, slot='boots_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l11_band_floor | `ObtainItem(code='iron_shield', quantity=1, slot='shield_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_items_task | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_items_task | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_workable | `ReachTaskOutcome(task_code='wolf')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_closable | `ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l32_held_task_open | `ReachSkillLevel(skill='jewelrycrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='gearcrafting', level=10)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_quiet_book_grind | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ObtainItem(code='satchel', quantity=1, slot='bag_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l12_ge_book_adequate | `ReachSkillLevel(skill='jewelrycrafting', level=10)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l47_depth3_amulet | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_relief_full_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_bag_critical_empty_bank | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='water_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l22_rest_for_combat | `ReachTaskOutcome(task_code='flying_snake')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='gearcrafting', level=21)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='jewelrycrafting', level=21)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | tasks_coin | PASS | yes | 1000001 | 250 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | tasks_coin | PASS | yes | 1000001 | 162 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | tasks_coin | PASS | yes | 1000001 | 162 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l25_currency_leaf_unfunded | `ReachSkillLevel(skill='weaponcrafting', level=21)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | root | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='weaponcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='gearcrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l24_fisher_cooking_rung | `ReachSkillLevel(skill='jewelrycrafting', level=6)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot')` | root | gold | PASS | - | - | - | - | - | - | - | - |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot')` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot')` | alt | gold | **wall_gold** | - | - | - | - | - | - | - | - |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='weaponcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l20_boost_stock | `ReachSkillLevel(skill='gearcrafting', level=16)` | alt | gold | PASS | - | - | - | - | - | - | - | - |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | corrupted_gem | PASS | - | 0 | 0 | - | 3 | 0 | 0 | 3 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | enchanted_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | event_ticket | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | sandwhisper_coin | PASS | - | 0 | 0 | - | 3 | 1 | 0 | 1 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | sonnengott_coin | PASS | - | 0 | 0 | - | 0 | 0 | 0 | 0 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | tasks_coin | PASS | - | 0 | 0 | yes | 0 | 0 | 0 | 0 |
| l14_wears_its_target | `ReachCharLevel(level=15)` | root | gold | PASS | - | - | - | - | - | - | - | - |

