# Drop-Wall Census — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_drop_wall.py`.
>
> Every candidate root the tier walk offers — the argmax AND its alternatives — that prices at `UNOBTAINABLE_PER_UNIT` is either not this census's subject (`not_drop_walled`) or falls into a named unwinnable-dropper wall. The residual is a candidate that crosses on the collective grant with no single item owning the gap.
>
> ALTERNATIVES, not just the winner: an infinite price is a veto, so a drop-walled candidate never becomes the argmax and a census that prices only the resolved root cannot see this wall at all.
>
> The crossing is a differential on production's own pricer — the candidate priced as it stands, then again with the walled items granted. No closure is re-derived here; obligation O6 forbids a second cost model and this census must not be one.

213 candidate cells over 45 scenarios; gate opens 1 of 17 walls (store-less); obtainable 91; not_drop_walled 105; walled 17 (16 on ALTERNATIVES); closes 7; out_of_reach 10; drop_wall_unattributed 0; root_unresolved 0

argmax blindness: 1 of 17 walls sit on a RESOLVED root. A census that prices only the argmax sees those 1 and misses 16 — an infinite price is a veto, so a walled candidate never becomes the argmax.

| Scenario | Candidate | Root? | Verdict | base | granted | gated | item | droppers | live tiles | closes | chain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_fresh | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 86 | 86 | 86 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 152 | 152 | 152 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 134 | 134 | 134 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | alt | PASS | 134 | 134 | 134 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 261 | 261 | 261 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 123 | 123 | 123 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 170 | 170 | 170 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 728 | 728 | 728 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 728 | 728 | 728 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='blue_slimeball', quantity=2) | argmax | PASS | 2000000 | 0 | 140 | blue_slimeball | 1 | 1 | 1 | iron_sword |
| l10_weapon_upgrade | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l3_low_hp | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 86 | 86 | 86 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 0 | 4000000 | mushroom | 1 | 1 | 0 | - |
| l12_taskgated_bag | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_taskgated_bag | ReachSkillLevel(skill='mining', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 867 | 867 | 867 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='gearcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='jewelrycrafting', level=7) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 72 | 72 | 72 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 76 | 76 | 76 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 195 | 195 | 195 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 268 | 268 | 268 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 58 | 58 | 58 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot') | argmax | PASS | 357 | 357 | 357 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 264 | 264 | 264 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 648 | 648 | 648 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 381 | 381 | 381 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=26) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 2458 | 2458 | 2458 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 2473 | 2473 | 2473 | - | - | - | - | - |
| l48_band_adequate | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 2473 | 2473 | 2473 | - | - | - | - | - |
| l48_raid_active | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 2223 | 2223 | 2223 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | argmax | PASS | 48 | 48 | 48 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 799 | 799 | 799 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 799 | 799 | 799 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 68 | 68 | 68 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 58 | 58 | 58 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 788 | 788 | 788 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 788 | 788 | 788 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot') | argmax | PASS | 125 | 125 | 125 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 272 | 272 | 272 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | alt | PASS | 2267 | 2267 | 2267 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot') | argmax | PASS | 111 | 111 | 111 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 260 | 260 | 260 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | alt | PASS | 2267 | 2267 | 2267 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 2165 | 2165 | 2165 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 308 | 308 | 308 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 6853 | 6853 | 6853 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='gearcrafting', level=26) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | argmax | PASS | 247 | 247 | 247 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 822 | 822 | 822 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 822 | 822 | 822 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 81 | 81 | 81 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot') | alt | PASS | 44 | 44 | 44 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 1 | water_boost_potion, leather_hat, iron_boots |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 1 | water_boost_potion, leather_hat, iron_boots |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 813 | 813 | 813 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 813 | 813 | 813 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachTaskOutcome(task_code='cow') | alt | PASS | 15 | 15 | 15 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l21_grey_material_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 31 | 31 | 31 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 25 | 25 | 25 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 175 | 175 | 175 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 175 | 175 | 175 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 76 | 76 | 76 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='jewelrycrafting', level=3) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='gearcrafting', level=9) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l19_band_edge | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 25 | 25 | 25 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 35 | 35 | 35 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 26 | 26 | 26 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | alt | PASS | 89 | 89 | 89 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_items_task | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_workable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachTaskOutcome(task_code='wolf') | alt | PASS | 15 | 15 | 15 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_closable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot') | alt | PASS | 23 | 23 | 23 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_open | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | argmax | PASS | 144 | 144 | 144 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 103 | 103 | 103 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='satchel', quantity=1, slot='bag_slot') | alt | PASS | 590 | 590 | 590 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 822 | 822 | 822 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 822 | 822 | 822 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | argmax | PASS | 21 | 21 | 21 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 103 | 103 | 103 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='satchel', quantity=1, slot='bag_slot') | alt | PASS | 590 | 590 | 590 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='jewelrycrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 69 | 69 | 69 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 38 | 38 | 38 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 260 | 260 | 260 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1988 | 1000001 | cursed_wood | 1 | 1 | 0 | - |
| l20_relief_full_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 65 | 65 | 65 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 484 | 484 | 484 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 34 | 34 | 34 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring1_slot') | alt | PASS | 140 | 140 | 140 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring2_slot') | alt | PASS | 140 | 140 | 140 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 308 | 308 | 308 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachTaskOutcome(task_code='flying_snake') | alt | PASS | 58 | 58 | 58 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot') | argmax | PASS | 368 | 368 | 368 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='gearcrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='skull_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='skull_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='weaponcrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 65 | 65 | 65 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 484 | 484 | 484 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l14_wears_its_target | ReachCharLevel(level=15) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |

