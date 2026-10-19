# Drop-Wall Census — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_drop_wall.py`.
>
> Every candidate root the tier walk offers — the argmax AND its alternatives — that prices at `UNOBTAINABLE_PER_UNIT` is either not this census's subject (`not_drop_walled`) or falls into a named unwinnable-dropper wall. The residual is a candidate that crosses on the collective grant with no single item owning the gap.
>
> ALTERNATIVES, not just the winner: an infinite price is a veto, so a drop-walled candidate never becomes the argmax and a census that prices only the resolved root cannot see this wall at all.
>
> The crossing is a differential on production's own pricer — the candidate priced as it stands, then again with the walled items granted. No closure is re-derived here; obligation O6 forbids a second cost model and this census must not be one.

257 candidate cells over 45 scenarios; gate opens 0 of 15 walls (store-less); obtainable 120; not_drop_walled 122; walled 15 (15 on ALTERNATIVES); closes 6; out_of_reach 9; drop_wall_unattributed 0; root_unresolved 0

argmax blindness: 0 of 15 walls sit on a RESOLVED root. A census that prices only the argmax sees those 0 and misses 15 — an infinite price is a veto, so a walled candidate never becomes the argmax.

| Scenario | Candidate | Root? | Verdict | base | granted | gated | item | droppers | live tiles | closes | chain |
|---|---|---|---|---|---|---|---|---|---|---|---|
| l1_fresh | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | 93 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_ring', quantity=1, slot='ring1_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 96 | 96 | 96 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 133 | 133 | 133 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 97 | 97 | 97 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 301 | 301 | 301 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 133 | 133 | 133 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 166 | 166 | 166 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 100 | 100 | 100 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l10_weapon_upgrade | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l3_low_hp | ObtainItem(code='copper_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | 93 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_ring', quantity=1, slot='ring1_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | 71 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='weaponcrafting', level=2) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 0 | 4000000 | mushroom | 1 | 1 | 0 | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_taskgated_bag | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_taskgated_bag | ReachSkillLevel(skill='mining', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ObtainItem(code='highwayman_dagger', quantity=1, slot='weapon_slot') | argmax | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='jewelrycrafting', level=7) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='gearcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 94 | 94 | 94 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 103 | 103 | 103 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='skull_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 218 | 218 | 218 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 311 | 311 | 311 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 88 | 88 | 88 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 93 | 93 | 93 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_armor', quantity=1, slot='body_armor_slot') | argmax | PASS | 426 | 426 | 426 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='jewelrycrafting', level=26) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 668 | 668 | 668 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 306 | 306 | 306 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 410 | 410 | 410 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 2345 | 2345 | 2345 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 2004 | 2004 | 2004 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1846 | 1846 | 1846 | - | - | - | - | - |
| l48_band_adequate | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_band_adequate | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 1846 | 1846 | 1846 | - | - | - | - | - |
| l48_raid_active | ReachSkillLevel(skill='jewelrycrafting', level=36) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l48_raid_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='goblin_guard_shield', quantity=1, slot='shield_slot') | argmax | PASS | 2020 | 2020 | 2020 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 2004 | 2004 | 2004 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 74 | 74 | 74 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 849 | 849 | 849 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 849 | 849 | 849 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 74 | 74 | 74 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 836 | 836 | 836 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 836 | 836 | 836 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 2603 | 2603 | 2603 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 317 | 317 | 317 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 494 | 494 | 494 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 2003 | 2003 | 2003 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 269 | 269 | 269 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='royal_skeleton_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 413 | 413 | 413 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='death_knight_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 2003 | 2003 | 2003 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 3 | 3 | 3 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 277 | 277 | 277 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='slime_shield', quantity=1, slot='shield_slot') | alt | PASS | 312 | 312 | 312 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='gearcrafting', level=26) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='weaponcrafting', level=16) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='weaponcrafting', level=16) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_staff', quantity=1, slot='weapon_slot') | argmax | PASS | 848 | 848 | 848 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='iron_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 130 | 130 | 130 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 251 | 251 | 251 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 130 | 130 | 130 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 848 | 848 | 848 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 848 | 848 | 848 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 105 | 105 | 105 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot') | alt | PASS | 45 | 45 | 45 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 1 | water_boost_potion, leather_hat, iron_boots |
| l10_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 1 | water_boost_potion, leather_hat, iron_boots |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='weaponcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachTaskOutcome(task_code='cow') | alt | PASS | 22 | 22 | 22 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='jewelrycrafting', level=2) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l21_grey_material_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 43 | 43 | 43 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 62 | 62 | 62 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 94 | 94 | 94 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='weaponcrafting', level=11) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 103 | 103 | 103 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | alt | PASS | 208 | 208 | 208 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 208 | 208 | 208 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='jewelrycrafting', level=3) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='gearcrafting', level=9) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l12_deep_chain_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1 | 1000001 | forest_ring | 1 | 1 | 0 | - |
| l19_band_edge | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 43 | 43 | 43 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 37 | 37 | 37 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='jewelrycrafting', level=15) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 29 | 29 | 29 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 66 | 66 | 66 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 37 | 37 | 37 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | alt | PASS | 46 | 46 | 46 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 216 | 216 | 216 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 604 | 604 | 604 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 604 | 604 | 604 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_items_task | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_workable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachTaskOutcome(task_code='wolf') | alt | PASS | 20 | 20 | 20 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_closable | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot') | alt | PASS | 29 | 29 | 29 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='wooden_club', quantity=1, slot='weapon_slot') | alt | PASS | 1000001 | 1 | 1000001 | wooden_club | 1 | 1 | 1 | perfect_bow, steel_boots |
| l32_held_task_open | ReachSkillLevel(skill='jewelrycrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='jewelrycrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 11 | 11 | 11 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring1_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='forest_ring', quantity=1, slot='ring2_slot') | alt | PASS | 869 | 869 | 869 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 219 | 219 | 219 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 73 | 73 | 73 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 106 | 106 | 106 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 106 | 106 | 106 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 205 | 205 | 205 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 10 | 10 | 10 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 2464 | 2464 | 2464 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 157 | 157 | 157 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 157 | 157 | 157 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 520 | 520 | 520 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 82 | 82 | 82 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='weaponcrafting', level=16) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 64 | 64 | 64 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 364 | 364 | 364 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring1_slot') | alt | PASS | 160 | 160 | 160 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='water_ring', quantity=1, slot='ring2_slot') | alt | PASS | 160 | 160 | 160 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachTaskOutcome(task_code='flying_snake') | alt | PASS | 78 | 78 | 78 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='weaponcrafting', level=21) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='dreadful_ring', quantity=1, slot='ring1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='dreadful_ring', quantity=1, slot='ring2_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='steel_boots', quantity=1, slot='boots_slot') | alt | PASS | 345 | 345 | 345 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='steel_armor', quantity=1, slot='body_armor_slot') | alt | PASS | 317 | 317 | 317 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='jewelrycrafting', level=21) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='hard_leather_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='steel_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 273 | 273 | 273 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='weaponcrafting', level=6) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l24_fisher_cooking_rung | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='earth_ring', quantity=1, slot='ring1_slot') | argmax | PASS | 171 | 171 | 171 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='earth_ring', quantity=1, slot='ring2_slot') | alt | PASS | 171 | 171 | 171 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 520 | 520 | 520 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='fire_and_earth_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 82 | 82 | 82 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='weaponcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | 1000001 | - | - | - | - | - |
| l14_wears_its_target | ReachCharLevel(level=15) | argmax | PASS | 1000000 | 1000000 | 1000000 | - | - | - | - | - |

