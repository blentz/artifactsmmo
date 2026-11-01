# Drop-Wall Census — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_drop_wall.py`.
>
> Every candidate root the tier walk offers — the argmax AND its alternatives — that prices at `UNOBTAINABLE_PER_UNIT` is either not this census's subject (`not_drop_walled`) or falls into a named unwinnable-dropper wall. The residual is a candidate that crosses on the collective grant with no single item owning the gap.
>
> ALTERNATIVES, not just the winner: an infinite price is a veto, so a drop-walled candidate never becomes the argmax and a census that prices only the resolved root cannot see this wall at all.
>
> The crossing is a differential on production's own pricer — the candidate priced as it stands, then again with the walled items granted. No closure is re-derived here; obligation O6 forbids a second cost model and this census must not be one.

213 candidate cells over 45 scenarios; gate opens 0 of 5 walls (store-less); obtainable 92; not_drop_walled 116; walled 5 (5 on ALTERNATIVES); closes 4; out_of_reach 1; drop_wall_unattributed 0; root_unresolved 0

argmax blindness: 0 of 5 walls sit on a RESOLVED root. A census that prices only the argmax sees those 0 and misses 5 — an infinite price is a veto, so a walled candidate never becomes the argmax.

| Scenario | Candidate | Root? | Verdict | base | granted | gated | item | droppers | live tiles | closes | chain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_fresh | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | 93 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='greater_wooden_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 125 | 125 | 125 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 118 | 118 | 118 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | alt | PASS | 118 | 118 | 118 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 112 | 112 | 112 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 121 | 121 | 121 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 280 | 280 | 280 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 875 | 875 | 875 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 875 | 875 | 875 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='blue_slimeball', quantity=2) | argmax | PASS | 2000000 | 2000000 | 2000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | 93 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 4000000 | 4000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='mining', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 569 | 569 | 569 | - | - | - | - | - |
| l15_midband | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | alt | PASS | 102 | 102 | 102 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='gearcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 127 | 127 | 127 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 107 | 107 | 107 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 236 | 236 | 236 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 99 | 99 | 99 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 321 | 321 | 321 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 115 | 115 | 115 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot') | argmax | PASS | 501 | 501 | 501 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 481 | 481 | 481 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 693 | 693 | 693 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 323 | 323 | 323 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=26) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1897 | 1897 | 1897 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1871 | 1871 | 1871 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_band_adequate | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1871 | 1871 | 1871 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_raid_active | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1792 | 1792 | 1792 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | argmax | PASS | 54 | 54 | 54 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 647 | 647 | 647 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 647 | 647 | 647 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 74 | 74 | 74 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 638 | 638 | 638 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 638 | 638 | 638 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | argmax | PASS | 297 | 297 | 297 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | alt | PASS | 2316 | 2316 | 2316 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot') | alt | PASS | 195 | 195 | 195 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | argmax | PASS | 302 | 302 | 302 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='mushmush_wizard_hat', quantity=1, slot='helmet_slot') | alt | PASS | 190 | 190 | 190 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | alt | PASS | 2318 | 2318 | 2318 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | alt | PASS | 2676 | 2676 | 2676 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 330 | 330 | 330 | - | - | - | - | - |
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
| l13_drop_recipe_grind | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | argmax | PASS | 185 | 185 | 185 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='leather_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 42 | 42 | 42 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 615 | 615 | 615 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 615 | 615 | 615 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | alt | PASS | 100 | 100 | 100 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 99 | 99 | 99 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 636 | 636 | 636 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 636 | 636 | 636 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachTaskOutcome(task_code='cow') | alt | PASS | 15 | 15 | 15 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 85 | 85 | 85 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 55 | 55 | 55 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 191 | 191 | 191 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 191 | 191 | 191 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 106 | 106 | 106 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='jewelrycrafting', level=3) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='gearcrafting', level=9) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 56 | 56 | 56 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 87 | 87 | 87 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='leather_boots', quantity=1, slot='boots_slot') | argmax | PASS | 102 | 102 | 102 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 58 | 58 | 58 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1019 | 1000001 | death_knight_sword | 1 | 1 | 1 | obsidian_battleaxe, gold_helm, topaz_ring, topaz_ring, fire_and_earth_amulet, bandit_armor |
| l32_items_task | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1019 | 1000001 | death_knight_sword | 1 | 1 | 1 | obsidian_battleaxe, gold_helm, topaz_ring, topaz_ring, fire_and_earth_amulet, bandit_armor |
| l32_held_task_workable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachTaskOutcome(task_code='wolf') | alt | PASS | 15 | 15 | 15 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1019 | 1000001 | death_knight_sword | 1 | 1 | 1 | obsidian_battleaxe, gold_helm, topaz_ring, topaz_ring, fire_and_earth_amulet, bandit_armor |
| l32_held_task_closable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1019 | 1000001 | death_knight_sword | 1 | 1 | 1 | obsidian_battleaxe, gold_helm, topaz_ring, topaz_ring, fire_and_earth_amulet, bandit_armor |
| l32_held_task_open | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | argmax | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='satchel', quantity=1, slot='bag_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 615 | 615 | 615 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 615 | 615 | 615 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | argmax | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='satchel', quantity=1, slot='bag_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='jewelrycrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 73 | 73 | 73 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 52 | 52 | 52 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 199 | 199 | 199 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1238 | 1000001 | cursed_wood | 1 | 1 | 0 | - |
| l20_relief_full_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 94 | 94 | 94 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 398 | 398 | 398 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 85 | 85 | 85 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring1_slot') | alt | PASS | 169 | 169 | 169 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring2_slot') | alt | PASS | 169 | 169 | 169 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 353 | 353 | 353 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachTaskOutcome(task_code='flying_snake') | alt | PASS | 58 | 58 | 58 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='skeleton_armor', quantity=1, slot='body_armor_slot') | argmax | PASS | 289 | 289 | 289 | - | - | - | - | - |
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
| l20_boost_stock | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 94 | 94 | 94 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 398 | 398 | 398 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l14_wears_its_target | ReachCharLevel(level=15) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |

