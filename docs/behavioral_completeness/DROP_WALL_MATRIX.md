# Drop-Wall Census — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_drop_wall.py`.
>
> Every candidate root the tier walk offers — the argmax AND its alternatives — that prices at `UNOBTAINABLE_PER_UNIT` is either not this census's subject (`not_drop_walled`) or falls into a named unwinnable-dropper wall. The residual is a candidate that crosses on the collective grant with no single item owning the gap.
>
> ALTERNATIVES, not just the winner: an infinite price is a veto, so a drop-walled candidate never becomes the argmax and a census that prices only the resolved root cannot see this wall at all.
>
> The crossing is a differential on production's own pricer — the candidate priced as it stands, then again with the walled items granted. No closure is re-derived here; obligation O6 forbids a second cost model and this census must not be one.

438 candidate cells over 44 scenarios; obtainable 77; not_drop_walled 350; walled 9 (9 on ALTERNATIVES); closes 9; out_of_reach 0; drop_wall_unattributed 0; root_unresolved 2

argmax blindness: 0 of 9 walls sit on a RESOLVED root. A census that prices only the argmax sees those 0 and misses 9 — an infinite price is a veto, so a walled candidate never becomes the argmax.

| Scenario | Candidate | Root? | Verdict | base | granted | item | droppers | live tiles | closes | chain |
|---|---|---|---|---|---|---|---|---|---|---|
| l1_fresh | ObtainItem(code='wooden_stick', quantity=1) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_ring', quantity=1, slot='ring1_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l1_fresh | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l1_fresh | ReachCharLevel(level=10) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ReachSkillLevel(skill='mining', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l1_fresh | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l8_overstocked | ObtainItem(code='wooden_stick', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachCharLevel(level=10) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='mining', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l8_overstocked | ReachSkillLevel(skill='woodcutting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='jewelrycrafting', level=2) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='cowhide', quantity=5) | alt | PASS | 5000000 | 0 | cowhide | 1 | 1 | 1 | iron_sword |
| l10_copper_adequate | ObtainItem(code='water_bow', quantity=1, slot='weapon_slot') | alt | PASS | 143 | 143 | - | - | - | - | - |
| l10_copper_adequate | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l10_copper_adequate | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_copper_adequate | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='jewelrycrafting', level=2) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='gearcrafting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ObtainItem(code='blue_slimeball', quantity=2) | alt | PASS | 2000000 | 0 | blue_slimeball | 1 | 1 | 1 | iron_sword |
| l10_weapon_upgrade | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l10_weapon_upgrade | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_weapon_upgrade | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='wooden_stick', quantity=1) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_boots', quantity=1, slot='boots_slot') | alt | PASS | 93 | 93 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_ring', quantity=1, slot='ring1_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l3_low_hp | ReachCharLevel(level=10) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ReachSkillLevel(skill='mining', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l3_low_hp | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='jewelrycrafting', level=2) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='jasper_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='weaponcrafting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l12_taskgated_bag | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='mining', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_taskgated_bag | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l15_midband | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='alchemy', level=7) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='mining', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l15_midband | ReachSkillLevel(skill='woodcutting', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l20_band_entry | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l20_band_entry | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='cooking', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='fishing', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='mining', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_band_entry | ReachSkillLevel(skill='woodcutting', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l30_band_entry | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l30_band_entry | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='cooking', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='fishing', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='mining', level=29) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_band_entry | ReachSkillLevel(skill='woodcutting', level=29) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l40_band_entry | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l40_band_entry | ReachCharLevel(level=50) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='alchemy', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='cooking', level=36) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='fishing', level=36) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='mining', level=39) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l40_band_entry | ReachSkillLevel(skill='woodcutting', level=39) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l48_capstone_approach | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l48_capstone_approach | ReachCharLevel(level=50) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='alchemy', level=36) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='cooking', level=43) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='fishing', level=43) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='mining', level=47) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_capstone_approach | ReachSkillLevel(skill='woodcutting', level=47) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_band_adequate | - | argmax | PASS | 0 | 0 | - | - | - | - | - |
| l48_raid_active | - | argmax | PASS | 0 | 0 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='life_crystal', quantity=1, slot='artifact2_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='demon_horn', quantity=4) | alt | PASS | 4000000 | 4000000 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='corrupted_skull', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='novice_guide', quantity=1, slot='artifact3_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='lizard_skin', quantity=5) | alt | PASS | 5000000 | 5000000 | - | - | - | - | - |
| l48_event_active | ObtainItem(code='full_moon_vampire_cape', quantity=4) | alt | PASS | 4000000 | 4000000 | - | - | - | - | - |
| l48_event_active | ReachCharLevel(level=50) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ReachSkillLevel(skill='alchemy', level=36) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ReachSkillLevel(skill='cooking', level=43) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ReachSkillLevel(skill='fishing', level=43) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ReachSkillLevel(skill='mining', level=47) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l48_event_active | ReachSkillLevel(skill='woodcutting', level=47) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l10_bag_pursuit | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l10_bag_pursuit | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_bag_pursuit | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_bag_pursuit | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_bag_pursuit | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_bag_pursuit | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='lost_world_map', quantity=1, slot='artifact2_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='perfect_pearl', quantity=1, slot='artifact3_slot') | alt | PASS | 24 | 24 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='astralyte_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ObtainItem(code='king_slimeball', quantity=2) | alt | PASS | 2000000 | 0 | king_slimeball | 1 | 1 | 1 | cursed_sceptre |
| l35_artifact_fill | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='alchemy', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='cooking', level=31) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='fishing', level=31) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='mining', level=33) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_artifact_fill | ReachSkillLevel(skill='woodcutting', level=33) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='astralyte_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ObtainItem(code='king_slimeball', quantity=2) | alt | PASS | 2000000 | 0 | king_slimeball | 1 | 1 | 1 | cursed_sceptre |
| l35_boots_drop_farm | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l35_boots_drop_farm | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='alchemy', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='cooking', level=31) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='fishing', level=31) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='mining', level=33) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l35_boots_drop_farm | ReachSkillLevel(skill='woodcutting', level=33) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 3 | 3 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='king_slimeball', quantity=6) | alt | PASS | 6000000 | 0 | king_slimeball | 1 | 1 | 1 | death_knight_sword |
| l30_rune_fill | ObtainItem(code='astralyte_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='jewelrycrafting', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l30_rune_fill | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='alchemy', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='cooking', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='fishing', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='mining', level=29) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l30_rune_fill | ReachSkillLevel(skill='woodcutting', level=29) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='cooking', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='fishing', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='mining', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='woodcutting', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility | ReachSkillLevel(skill='alchemy', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='gearcrafting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='jewelrycrafting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='cooking', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='fishing', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='mining', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='woodcutting', level=19) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_dual_utility_one_stocked | ReachSkillLevel(skill='alchemy', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ObtainItem(code='sticky_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 45 | 45 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='fishing', level=4) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='cooking', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='mining', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l13_drop_recipe_grind | ReachSkillLevel(skill='alchemy', level=17) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l10_gearcrafting_gap | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_gearcrafting_gap | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='cooking', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_gearcrafting_gap | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | argmax | PASS | 71 | 71 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ObtainItem(code='wooden_stick', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='alchemy', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='cooking', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='woodcutting', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l10_gearcrafting_gap_combat_blocked | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 46 | 46 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_ring', quantity=1, slot='ring2_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 37 | 37 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='iron_ring', quantity=1, slot='ring1_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l21_grey_material_grind | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 66 | 66 | - | - | - | - | - |
| l21_grey_material_grind | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='cooking', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='woodcutting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='alchemy', level=17) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l21_grey_material_grind | ReachSkillLevel(skill='mining', level=22) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 97 | 97 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_ring', quantity=1, slot='ring2_slot') | alt | PASS | 96 | 96 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 88 | 88 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='iron_ring', quantity=1, slot='ring1_slot') | alt | PASS | 96 | 96 | - | - | - | - | - |
| l22_grey_rung_grind | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 107 | 107 | - | - | - | - | - |
| l22_grey_rung_grind | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='cooking', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='woodcutting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='alchemy', level=18) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_grey_rung_grind | ReachSkillLevel(skill='mining', level=22) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='jewelrycrafting', level=3) | argmax | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='cowhide', quantity=5) | alt | PASS | 5000000 | 0 | cowhide | 1 | 1 | 1 | iron_sword |
| l12_deep_chain_grind | ObtainItem(code='water_bow', quantity=1, slot='weapon_slot') | alt | PASS | 137 | 137 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='wooden_shield', quantity=1, slot='shield_slot') | alt | PASS | 71 | 71 | - | - | - | - | - |
| l12_deep_chain_grind | ObtainItem(code='copper_ring', quantity=1, slot='ring2_slot') | alt | PASS | 70 | 70 | - | - | - | - | - |
| l12_deep_chain_grind | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='fishing', level=2) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='alchemy', level=5) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='cooking', level=5) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='woodcutting', level=12) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_deep_chain_grind | ReachSkillLevel(skill='mining', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 46 | 46 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_ring', quantity=1, slot='ring2_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 37 | 37 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='iron_ring', quantity=1, slot='ring1_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l19_band_edge | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 66 | 66 | - | - | - | - | - |
| l19_band_edge | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='cooking', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='woodcutting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='alchemy', level=17) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l19_band_edge | ReachSkillLevel(skill='mining', level=22) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_shield', quantity=1, slot='shield_slot') | argmax | PASS | 46 | 46 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_ring', quantity=1, slot='ring2_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_boots', quantity=1, slot='boots_slot') | alt | PASS | 37 | 37 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='iron_ring', quantity=1, slot='ring1_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l11_band_floor | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 66 | 66 | - | - | - | - | - |
| l11_band_floor | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ReachSkillLevel(skill='cooking', level=13) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ReachSkillLevel(skill='woodcutting', level=16) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ReachSkillLevel(skill='alchemy', level=17) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l11_band_floor | ReachSkillLevel(skill='mining', level=22) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='jasper_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='lucky_wizard_hat', quantity=1, slot='helmet_slot') | alt | PASS | 621 | 621 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 387 | 387 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 255 | 255 | - | - | - | - | - |
| l32_items_task | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 64 | 64 | - | - | - | - | - |
| l32_items_task | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_items_task | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='jasper_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='lucky_wizard_hat', quantity=1, slot='helmet_slot') | alt | PASS | 621 | 621 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 387 | 387 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 255 | 255 | - | - | - | - | - |
| l32_held_task_workable | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 64 | 64 | - | - | - | - | - |
| l32_held_task_workable | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_workable | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ObtainItem(code='earth_boost_potion', quantity=1, slot='utility1_slot') | argmax | PASS | 20 | 20 | - | - | - | - | - |
| l32_held_task_closable | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_closable | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='jasper_crystal', quantity=1) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='lucky_wizard_hat', quantity=1, slot='helmet_slot') | alt | PASS | 621 | 621 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='mushmush_jacket', quantity=1, slot='body_armor_slot') | alt | PASS | 387 | 387 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='adventurer_pants', quantity=1, slot='leg_armor_slot') | alt | PASS | 255 | 255 | - | - | - | - | - |
| l32_held_task_open | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 64 | 64 | - | - | - | - | - |
| l32_held_task_open | ReachCharLevel(level=40) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l32_held_task_open | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_ge_book_grind | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='cooking', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_grind | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_quiet_book_grind | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='gearcrafting', level=10) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='cooking', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_quiet_book_grind | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='iron_legs_armor', quantity=1, slot='leg_armor_slot') | alt | PASS | 11 | 11 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 5 | 5 | - | - | - | - | - |
| l12_ge_book_adequate | ObtainItem(code='adventurer_vest', quantity=1, slot='body_armor_slot') | alt | PASS | 135 | 135 | - | - | - | - | - |
| l12_ge_book_adequate | ReachCharLevel(level=20) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='cooking', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='fishing', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='mining', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l12_ge_book_adequate | ReachSkillLevel(skill='woodcutting', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='greater_dreadful_amulet', quantity=1, slot='amulet_slot') | argmax | PASS | 73 | 73 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='life_crystal', quantity=1, slot='artifact2_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='corrupted_skull', quantity=1, slot='artifact1_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='lifesteal_rune', quantity=1, slot='rune_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='novice_guide', quantity=1, slot='artifact3_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l47_depth3_amulet | ObtainItem(code='demon_horn', quantity=4) | alt | PASS | 4000000 | 4000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachCharLevel(level=50) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachSkillLevel(skill='alchemy', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachSkillLevel(skill='cooking', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachSkillLevel(skill='fishing', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachSkillLevel(skill='mining', level=41) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l47_depth3_amulet | ReachSkillLevel(skill='woodcutting', level=41) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 12 | 12 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='adventurer_helmet', quantity=1, slot='helmet_slot') | alt | PASS | 8 | 8 | - | - | - | - | - |
| l20_relief_full_bank | ObtainItem(code='adventurer_vest', quantity=1, slot='body_armor_slot') | alt | PASS | 35 | 35 | - | - | - | - | - |
| l20_relief_full_bank | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_relief_full_bank | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 107 | 107 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 0 | mushroom | 1 | 1 | 1 | forest_whip |
| l20_bag_critical_empty_bank | ObtainItem(code='adventurer_vest', quantity=1, slot='body_armor_slot') | alt | PASS | 149 | 149 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_bag_critical_empty_bank | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 64 | 64 | - | - | - | - | - |
| l22_rest_for_combat | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 0 | mushroom | 1 | 1 | 1 | forest_whip |
| l22_rest_for_combat | ObtainItem(code='adventurer_vest', quantity=1, slot='body_armor_slot') | alt | PASS | 200 | 200 | - | - | - | - | - |
| l22_rest_for_combat | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l22_rest_for_combat | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ObtainItem(code='king_slime_sword', quantity=1, slot='weapon_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l25_currency_leaf_unfunded | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l24_fisher_cooking_rung | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='jewelrycrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='gearcrafting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='alchemy', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='mining', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='woodcutting', level=6) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='cooking', level=22) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l24_fisher_cooking_rung | ReachSkillLevel(skill='fishing', level=26) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='novice_guide', quantity=1, slot='artifact1_slot') | argmax | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='backpack', quantity=1, slot='bag_slot') | alt | PASS | 1000001 | 1000001 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='air_and_water_amulet', quantity=1, slot='amulet_slot') | alt | PASS | 107 | 107 | - | - | - | - | - |
| l20_boost_stock | ObtainItem(code='mushroom', quantity=4) | alt | PASS | 4000000 | 0 | mushroom | 1 | 1 | 1 | forest_whip |
| l20_boost_stock | ObtainItem(code='adventurer_vest', quantity=1, slot='body_armor_slot') | alt | PASS | 163 | 163 | - | - | - | - | - |
| l20_boost_stock | ReachCharLevel(level=30) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='alchemy', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='cooking', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='fishing', level=11) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='mining', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |
| l20_boost_stock | ReachSkillLevel(skill='woodcutting', level=21) | alt | PASS | 1000000 | 1000000 | - | - | - | - | - |

