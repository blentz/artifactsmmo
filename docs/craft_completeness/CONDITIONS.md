# Craft-Planning Conditions

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_conditions.py`.
>
> Each recipe climbs the ladder of `audit/craft_conditions.py` (cell, every skill at the character level, gold, its events, then the character level in steps of 5); the first rung that plans is its condition. A fight's need is `bare` (the stats win), the potion loadout that wins it, or `loses`.

321 recipes; planned 155 (cell 108, events 20, gold 6, level+5 6, skills 15); unplanned 166 (combat_blocked 110, material_unreachable 50, grey_farm_suppressed 4, crossing_unaffordable 2)

| Recipe | Skill | Craft lvl | Plans at | Char lvl | Fights (what wins) |
|---|---|---|---|---|---|
| recall_potion | alchemy | 5 | cell | 1 | - |
| small_health_potion | alchemy | 5 | cell | 1 | - |
| air_boost_potion | alchemy | 10 | cell | 10 | green_slime: bare |
| earth_boost_potion | alchemy | 10 | cell | 10 | yellow_slime: bare |
| fire_boost_potion | alchemy | 10 | cell | 10 | red_slime: bare |
| water_boost_potion | alchemy | 10 | cell | 10 | blue_slime: bare |
| forest_bank_potion | alchemy | 20 | cell | 20 | - |
| minor_health_potion | alchemy | 20 | cell | 20 | - |
| small_antidote | alchemy | 20 | cell | 20 | cow: bare |
| antidote | alchemy | 30 | events | 30 | - |
| health_potion | alchemy | 30 | cell | 30 | chicken: bare |
| health_splash_potion | alchemy | 30 | cell | 30 | - |
| air_res_potion | alchemy | 40 | cell | 40 | green_slime: bare |
| earth_res_potion | alchemy | 40 | cell | 40 | yellow_slime: bare |
| enchanted_potion | alchemy | 40 | gold | 40 | - |
| enhanced_boost_potion | alchemy | 40 | events | 40 | bat: greater_health_potion |
| fire_res_potion | alchemy | 40 | cell | 40 | red_slime: bare |
| greater_health_potion | alchemy | 40 | cell | 40 | chicken: bare |
| health_boost_potion | alchemy | 40 | cell | 40 | cow: bare |
| water_res_potion | alchemy | 40 | cell | 40 | blue_slime: bare |
| enhanced_antidote | alchemy | 45 | events | 50 | - |
| enhanced_health_potion | alchemy | 45 | **none: grey_farm_suppressed** | 50 | - |
| enhanced_health_splash_potion | alchemy | 50 | **none: crossing_unaffordable** | 50 | - |
| lava_underground_potion | alchemy | 50 | **none: crossing_unaffordable** | 50 | - |
| sandwhisper_potion | alchemy | 50 | gold | 50 | - |
| cooked_chicken | cooking | 1 | cell | 1 | chicken: bare |
| cooked_gudgeon | cooking | 1 | cell | 1 | - |
| cooked_beef | cooking | 5 | level+5 | 6 | cow: small_health_potion |
| fried_eggs | cooking | 5 | cell | 1 | chicken: bare |
| cheese | cooking | 10 | cell | 10 | cow: bare |
| cooked_shrimp | cooking | 10 | cell | 10 | - |
| cookie | cooking | 10 | cell | 10 | cow: bare, chicken: bare |
| cooked_wolf_meat | cooking | 15 | cell | 20 | wolf: bare |
| mushroom_soup | cooking | 15 | cell | 20 | mushmush: bare |
| apple_pie | cooking | 20 | cell | 20 | chicken: bare |
| cooked_porkchop | cooking | 20 | cell | 20 | pig: bare |
| cooked_trout | cooking | 20 | cell | 20 | - |
| cooked_bass | cooking | 30 | cell | 30 | - |
| cooked_rat_meat | cooking | 30 | cell | 30 | rat: bare |
| cooked_hellhound_meat | cooking | 40 | skills | 40 | hellhound: greater_health_potion |
| cooked_salmon | cooking | 40 | cell | 40 | - |
| fish_soup | cooking | 40 | cell | 40 | cow: bare |
| maple_syrup | cooking | 40 | cell | 40 | - |
| cooked_desert_scorpion_meat | cooking | 50 | **none: combat_blocked** | 50 | - |
| cooked_swordfish | cooking | 50 | gold | 50 | - |
| copper_boots | gearcrafting | 1 | cell | 1 | - |
| copper_helmet | gearcrafting | 1 | cell | 1 | - |
| wooden_shield | gearcrafting | 1 | cell | 1 | - |
| copper_armor | gearcrafting | 5 | level+5 | 6 | sheep: bare |
| copper_legs_armor | gearcrafting | 5 | cell | 1 | chicken: bare |
| feather_coat | gearcrafting | 5 | cell | 1 | chicken: bare |
| satchel | gearcrafting | 5 | **none: material_unreachable** | 50 | - |
| adventurer_helmet | gearcrafting | 10 | cell | 10 | chicken: bare, cow: bare, mushmush: bare |
| adventurer_vest | gearcrafting | 10 | cell | 10 | sheep: bare, cow: bare, yellow_slime: bare |
| iron_armor | gearcrafting | 10 | cell | 10 | cow: bare |
| iron_boots | gearcrafting | 10 | cell | 10 | chicken: bare |
| iron_helm | gearcrafting | 10 | cell | 10 | sheep: bare |
| iron_legs_armor | gearcrafting | 10 | cell | 10 | cow: bare |
| iron_shield | gearcrafting | 10 | cell | 10 | sheep: bare |
| leather_armor | gearcrafting | 10 | cell | 10 | cow: bare |
| leather_boots | gearcrafting | 10 | cell | 10 | cow: bare |
| leather_hat | gearcrafting | 10 | cell | 10 | cow: bare, yellow_slime: bare |
| leather_legs_armor | gearcrafting | 10 | cell | 10 | cow: bare |
| adventurer_boots | gearcrafting | 15 | cell | 20 | wolf: bare, mushmush: bare |
| adventurer_pants | gearcrafting | 15 | cell | 20 | cow: bare, highwayman: bare, sheep: bare |
| lucky_wizard_hat | gearcrafting | 15 | cell | 20 | highwayman: bare, flying_snake: bare |
| mushmush_jacket | gearcrafting | 15 | cell | 20 | cow: bare, flying_snake: bare, mushmush: bare |
| mushmush_wizard_hat | gearcrafting | 15 | cell | 20 | cow: bare, wolf: bare, mushmush: bare |
| hard_leather_armor | gearcrafting | 20 | skills | 20 | cow: bare, spider: minor_health_potion, pig: bare |
| hard_leather_boots | gearcrafting | 20 | cell | 20 | highwayman: bare, cow: bare, pig: bare |
| hard_leather_helmet | gearcrafting | 20 | **none: material_unreachable** | 50 | - |
| hard_leather_pants | gearcrafting | 20 | cell | 20 | highwayman: bare, cow: bare, skeleton: bare |
| magic_wizard_hat | gearcrafting | 20 | skills | 20 | ogre: minor_health_potion, wolf: bare, blue_slime: bare, flying_snake: bare |
| skeleton_armor | gearcrafting | 20 | cell | 20 | skeleton: bare, wolf: bare, pig: bare |
| skeleton_helmet | gearcrafting | 20 | cell | 20 | skeleton: bare, wolf: bare |
| skeleton_pants | gearcrafting | 20 | cell | 20 | wolf: bare, skeleton: bare |
| slime_shield | gearcrafting | 20 | skills | 20 | king_slime: minor_health_potion, sheep: bare |
| snakeskin_boots | gearcrafting | 20 | skills | 20 | spider: minor_health_potion, flying_snake: bare, highwayman: bare |
| steel_armor | gearcrafting | 20 | skills | 20 | highwayman: bare, sheep: bare, spider: minor_health_potion |
| steel_boots | gearcrafting | 20 | skills | 20 | flying_snake: bare, ogre: minor_health_potion |
| steel_helm | gearcrafting | 20 | skills | 20 | ogre: minor_health_potion, wolf: bare, sheep: bare |
| steel_legs_armor | gearcrafting | 20 | skills | 20 | skeleton: bare, sheep: bare, king_slime: minor_health_potion |
| tromatising_mask | gearcrafting | 20 | cell | 20 | pig: bare, sheep: bare, skeleton: bare |
| lizard_skin_armor | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| lizard_skin_legs_armor | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| piggy_armor | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| piggy_helmet | gearcrafting | 25 | **none: grey_farm_suppressed** | 50 | - |
| piggy_pants | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| snakeskin_armor | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| snakeskin_legs_armor | gearcrafting | 25 | cell | 30 | flying_snake: bare, cow: bare, wolf: bare |
| stormforged_armor | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| stormforged_pants | gearcrafting | 25 | **none: material_unreachable** | 50 | - |
| conjurer_cloak | gearcrafting | 30 | **none: combat_blocked** | 50 | - |
| conjurer_skirt | gearcrafting | 30 | events | 30 | imp: bare, full_moon_vampire: bare, owlbear: bare, rat: bare |
| flying_boots | gearcrafting | 30 | **none: material_unreachable** | 50 | - |
| gold_boots | gearcrafting | 30 | **none: material_unreachable** | 50 | - |
| gold_helm | gearcrafting | 30 | events | 30 | demon: minor_health_potion, imp: bare, vampire: bare, owlbear: bare |
| gold_mask | gearcrafting | 30 | **none: combat_blocked** | 50 | - |
| gold_platebody | gearcrafting | 30 | events | 30 | full_moon_vampire: bare, death_knight: bare, imp: bare, demon: small_health_potion |
| gold_platelegs | gearcrafting | 30 | events | 30 | bandit_lizard: bare, rat: bare, vampire: bare, ogre: bare |
| gold_shield | gearcrafting | 30 | **none: combat_blocked** | 50 | - |
| lizard_boots | gearcrafting | 30 | **none: material_unreachable** | 50 | - |
| obsidian_armor | gearcrafting | 30 | events | 30 | imp: bare, spider: bare, full_moon_vampire: bare |
| obsidian_helmet | gearcrafting | 30 | events | 30 | imp: bare, owlbear: bare, bandit_lizard: bare, vampire: bare |
| obsidian_legs_armor | gearcrafting | 30 | events | 30 | imp: bare, owlbear: bare, bandit_lizard: bare, death_knight: bare |
| royal_skeleton_armor | gearcrafting | 30 | cell | 30 | - |
| royal_skeleton_helmet | gearcrafting | 30 | cell | 30 | - |
| royal_skeleton_pants | gearcrafting | 30 | cell | 30 | - |
| ancient_jean | gearcrafting | 35 | **none: material_unreachable** | 50 | - |
| cursed_hat | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| dreadful_armor | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| dreadful_shield | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| enchanter_boots | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| enchanter_pants | gearcrafting | 35 | **none: material_unreachable** | 50 | - |
| jester_hat | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| malefic_armor | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| strangold_armor | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| strangold_helmet | gearcrafting | 35 | **none: material_unreachable** | 50 | - |
| strangold_legs_armor | gearcrafting | 35 | **none: combat_blocked** | 50 | - |
| air_shield | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| batwing_helmet | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| cultist_boots | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| cultist_cloak | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| cultist_hat | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| cultist_pants | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| diamond_armor | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| diamond_skirt | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| earth_shield | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| fire_shield | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| hork_helmet | gearcrafting | 40 | events | 40 | orc: greater_health_potion, dryad: health_potion, bat: greater_health_potion, echoless_bat: greater_health_potion |
| mithril_boots | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_helm | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_platebody | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_platelegs | gearcrafting | 40 | **none: grey_farm_suppressed** | 50 | - |
| mithril_shield | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| water_shield | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| white_knight_armor | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| white_knight_helmet | gearcrafting | 40 | events | 40 | hellhound: greater_health_potion, orc: greater_health_potion, owlbear: bare |
| white_knight_pants | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| white_knight_shield | gearcrafting | 40 | events | 40 | echoless_bat: greater_health_potion, goblin_wolfrider: health_potion, hellhound: greater_health_potion, goblin: health_potion |
| wratharmor | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| wrathelmet | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| wrathpants | gearcrafting | 40 | **none: combat_blocked** | 50 | - |
| darkforged_boots | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| darkforged_helmet | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| darkforged_plate | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| darkforged_shield | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| demoniac_shield | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| hell_armor | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| hell_helmet | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| hell_legs_armor | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| mesh_armor | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| mesh_legs_armor | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| sand_snakeskin_armor | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| sand_snakeskin_bandana | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| sand_snakeskin_boots | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| sand_snakeskin_pants | gearcrafting | 45 | **none: combat_blocked** | 50 | - |
| adamantite_boots | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_mask | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_platebody | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_platelegs | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_shield | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| dark_horned_helmet | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| duskarmor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| duskpants | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| dust_helmet | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| magic_shield | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| medic_armor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| medic_skirt | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| red_dragon_armor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| red_dragon_boots | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| red_dragon_legs_armor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| red_dragon_shield | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| skullforged_armor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| skullforged_pants | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| vital_armor | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| vital_boots | gearcrafting | 50 | **none: combat_blocked** | 50 | - |
| copper_ring | jewelrycrafting | 1 | cell | 1 | - |
| life_amulet | jewelrycrafting | 5 | level+5 | 6 | chicken: bare, red_slime: bare |
| air_and_water_amulet | jewelrycrafting | 10 | cell | 10 | green_slime: bare, blue_slime: bare |
| fire_and_earth_amulet | jewelrycrafting | 10 | cell | 10 | red_slime: bare, yellow_slime: bare |
| iron_ring | jewelrycrafting | 10 | cell | 10 | sheep: bare |
| air_ring | jewelrycrafting | 15 | cell | 20 | green_slime: bare, flying_snake: bare |
| earth_ring | jewelrycrafting | 15 | cell | 20 | yellow_slime: bare, flying_snake: bare |
| fire_ring | jewelrycrafting | 15 | cell | 20 | red_slime: bare, flying_snake: bare |
| life_ring | jewelrycrafting | 15 | cell | 20 | sheep: bare, mushmush: bare |
| water_ring | jewelrycrafting | 15 | cell | 20 | blue_slime: bare, flying_snake: bare |
| wisdom_amulet | jewelrycrafting | 15 | **none: material_unreachable** | 50 | - |
| dreadful_amulet | jewelrycrafting | 20 | skills | 20 | ogre: minor_health_potion, cow: bare, king_slime: minor_health_potion |
| dreadful_ring | jewelrycrafting | 20 | **none: material_unreachable** | 50 | - |
| ring_of_chance | jewelrycrafting | 20 | **none: material_unreachable** | 50 | - |
| skull_amulet | jewelrycrafting | 20 | skills | 20 | skeleton: bare, king_slime: minor_health_potion, flying_snake: bare |
| skull_ring | jewelrycrafting | 20 | **none: material_unreachable** | 50 | - |
| steel_ring | jewelrycrafting | 20 | cell | 20 | skeleton: bare, cow: bare, flying_snake: bare |
| emerald_amulet | jewelrycrafting | 25 | **none: material_unreachable** | 50 | - |
| ruby_amulet | jewelrycrafting | 25 | **none: material_unreachable** | 50 | - |
| sapphire_amulet | jewelrycrafting | 25 | **none: material_unreachable** | 50 | - |
| topaz_amulet | jewelrycrafting | 25 | **none: material_unreachable** | 50 | - |
| emerald_ring | jewelrycrafting | 30 | **none: material_unreachable** | 50 | - |
| gold_ring | jewelrycrafting | 30 | cell | 30 | - |
| greater_dreadful_amulet | jewelrycrafting | 30 | cell | 30 | - |
| lost_amulet | jewelrycrafting | 30 | cell | 30 | - |
| prospecting_amulet | jewelrycrafting | 30 | **none: material_unreachable** | 50 | - |
| royal_skeleton_ring | jewelrycrafting | 30 | cell | 30 | - |
| ruby_ring | jewelrycrafting | 30 | **none: material_unreachable** | 50 | - |
| sapphire_ring | jewelrycrafting | 30 | **none: material_unreachable** | 50 | - |
| topaz_ring | jewelrycrafting | 30 | **none: material_unreachable** | 50 | - |
| ancestral_talisman | jewelrycrafting | 35 | **none: combat_blocked** | 50 | - |
| corrupted_stone_amulet | jewelrycrafting | 35 | **none: combat_blocked** | 50 | - |
| diamond_amulet | jewelrycrafting | 35 | **none: combat_blocked** | 50 | - |
| malefic_ring | jewelrycrafting | 35 | **none: material_unreachable** | 50 | - |
| masterful_necklace | jewelrycrafting | 35 | **none: combat_blocked** | 50 | - |
| celest_ring | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| divinity_ring | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| eternity_ring | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| greater_emerald_amulet | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| greater_ruby_amulet | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| greater_sapphire_amulet | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| greater_topaz_amulet | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_ring | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| sacred_ring | jewelrycrafting | 40 | **none: combat_blocked** | 50 | - |
| hell_ring | jewelrycrafting | 45 | **none: combat_blocked** | 50 | - |
| adamantite_ring | jewelrycrafting | 50 | **none: combat_blocked** | 50 | - |
| dust_amulet | jewelrycrafting | 50 | **none: combat_blocked** | 50 | - |
| eternal_red_ring | jewelrycrafting | 50 | **none: combat_blocked** | 50 | - |
| heart_amulet | jewelrycrafting | 50 | **none: combat_blocked** | 50 | - |
| skullforged_ring | jewelrycrafting | 50 | **none: combat_blocked** | 50 | - |
| copper_bar | mining | 1 | cell | 1 | - |
| iron_bar | mining | 10 | cell | 10 | - |
| emerald | mining | 20 | cell | 20 | - |
| ruby | mining | 20 | cell | 20 | - |
| sapphire | mining | 20 | cell | 20 | - |
| steel_bar | mining | 20 | cell | 20 | - |
| topaz | mining | 20 | cell | 20 | - |
| gold_bar | mining | 30 | cell | 30 | - |
| obsidian_bar | mining | 30 | cell | 30 | imp: bare |
| diamond | mining | 35 | events | 40 | - |
| strangold_bar | mining | 35 | events | 40 | - |
| mithril_bar | mining | 40 | cell | 40 | - |
| adamantite_bar | mining | 50 | gold | 50 | - |
| alexandrite | mining | 50 | gold | 50 | - |
| apprentice_gloves | weaponcrafting | 1 | cell | 1 | chicken: bare |
| copper_axe | weaponcrafting | 1 | cell | 1 | - |
| copper_dagger | weaponcrafting | 1 | cell | 1 | - |
| copper_pickaxe | weaponcrafting | 1 | cell | 1 | - |
| fishing_net | weaponcrafting | 1 | cell | 1 | - |
| wooden_staff | weaponcrafting | 1 | **none: material_unreachable** | 50 | - |
| fire_staff | weaponcrafting | 5 | level+5 | 6 | red_slime: bare |
| sticky_dagger | weaponcrafting | 5 | level+5 | 6 | green_slime: bare |
| sticky_sword | weaponcrafting | 5 | cell | 1 | yellow_slime: bare |
| water_bow | weaponcrafting | 5 | level+5 | 6 | blue_slime: bare |
| fire_bow | weaponcrafting | 10 | cell | 10 | red_slime: bare |
| greater_wooden_staff | weaponcrafting | 10 | cell | 10 | blue_slime: bare |
| iron_axe | weaponcrafting | 10 | **none: material_unreachable** | 50 | - |
| iron_dagger | weaponcrafting | 10 | cell | 10 | chicken: bare |
| iron_pickaxe | weaponcrafting | 10 | **none: material_unreachable** | 50 | - |
| iron_sword | weaponcrafting | 10 | cell | 10 | chicken: bare |
| leather_gloves | weaponcrafting | 10 | **none: material_unreachable** | 50 | - |
| spruce_fishing_rod | weaponcrafting | 10 | **none: material_unreachable** | 50 | - |
| king_slime_sword | weaponcrafting | 15 | **none: material_unreachable** | 50 | - |
| mushmush_bow | weaponcrafting | 15 | **none: material_unreachable** | 50 | - |
| mushstaff | weaponcrafting | 15 | **none: material_unreachable** | 50 | - |
| battlestaff | weaponcrafting | 20 | cell | 20 | wolf: bare, blue_slime: bare |
| forest_whip | weaponcrafting | 20 | skills | 20 | king_slime: minor_health_potion, wolf: bare, ogre: minor_health_potion |
| hunting_bow | weaponcrafting | 20 | skills | 20 | highwayman: bare, ogre: minor_health_potion, pig: bare |
| shuriken | weaponcrafting | 20 | skills | 20 | wolf: bare, ogre: minor_health_potion, flying_snake: bare |
| skull_staff | weaponcrafting | 20 | cell | 20 | skeleton: bare |
| steel_axe | weaponcrafting | 20 | **none: material_unreachable** | 50 | - |
| steel_battleaxe | weaponcrafting | 20 | cell | 20 | skeleton: bare, wolf: bare |
| steel_fishing_rod | weaponcrafting | 20 | **none: material_unreachable** | 50 | - |
| steel_gloves | weaponcrafting | 20 | **none: material_unreachable** | 50 | - |
| steel_pickaxe | weaponcrafting | 20 | **none: material_unreachable** | 50 | - |
| dreadful_staff | weaponcrafting | 25 | **none: material_unreachable** | 50 | - |
| skull_wand | weaponcrafting | 25 | **none: material_unreachable** | 50 | - |
| vampire_bow | weaponcrafting | 25 | **none: material_unreachable** | 50 | - |
| elderwood_staff | weaponcrafting | 30 | **none: grey_farm_suppressed** | 50 | - |
| gold_axe | weaponcrafting | 30 | **none: material_unreachable** | 50 | - |
| gold_fishing_rod | weaponcrafting | 30 | **none: material_unreachable** | 50 | - |
| gold_pickaxe | weaponcrafting | 30 | **none: combat_blocked** | 50 | - |
| gold_sword | weaponcrafting | 30 | events | 30 | imp: bare, death_knight: bare, demon: minor_health_potion |
| golden_gloves | weaponcrafting | 30 | **none: material_unreachable** | 50 | - |
| greater_dreadful_staff | weaponcrafting | 30 | **none: material_unreachable** | 50 | - |
| obsidian_battleaxe | weaponcrafting | 30 | events | 30 | imp: bare, bandit_lizard: bare, cyclops: bare |
| perfect_bow | weaponcrafting | 30 | events | 30 | spider: bare, demon: minor_health_potion, ogre: bare, death_knight: bare |
| cursed_sceptre | weaponcrafting | 35 | **none: combat_blocked** | 50 | - |
| diamond_sword | weaponcrafting | 35 | **none: combat_blocked** | 50 | - |
| dreadful_battleaxe | weaponcrafting | 35 | **none: material_unreachable** | 50 | - |
| magic_bow | weaponcrafting | 35 | **none: material_unreachable** | 50 | - |
| strangold_sword | weaponcrafting | 35 | **none: combat_blocked** | 50 | - |
| bloodblade | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| lightning_sword | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_axe | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_fishing_rod | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_gloves | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_pickaxe | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| mithril_sword | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| wrathsword | weaponcrafting | 40 | **none: combat_blocked** | 50 | - |
| blade_of_hell | weaponcrafting | 45 | **none: combat_blocked** | 50 | - |
| bow_from_hell | weaponcrafting | 45 | **none: combat_blocked** | 50 | - |
| demoniac_dagger | weaponcrafting | 45 | **none: combat_blocked** | 50 | - |
| hell_reaper | weaponcrafting | 45 | **none: combat_blocked** | 50 | - |
| hell_staff | weaponcrafting | 45 | **none: combat_blocked** | 50 | - |
| adamantite_axe | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_fishing_rod | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_gloves | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_pickaxe | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| adamantite_sword | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| desert_whip | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| dust_sword | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| moonlight_staff | weaponcrafting | 50 | **none: combat_blocked** | 50 | - |
| ash_plank | woodcutting | 1 | cell | 1 | - |
| spruce_plank | woodcutting | 10 | cell | 10 | - |
| hardwood_plank | woodcutting | 20 | cell | 20 | - |
| dead_wood_plank | woodcutting | 30 | cell | 30 | - |
| sap | woodcutting | 30 | cell | 30 | - |
| cursed_plank | woodcutting | 35 | skills | 40 | cursed_tree: minor_health_potion |
| magic_sap | woodcutting | 35 | events | 40 | - |
| magical_plank | woodcutting | 35 | events | 40 | - |
| maple_plank | woodcutting | 40 | cell | 40 | - |
| maple_sap | woodcutting | 40 | cell | 40 | - |
| palm_plank | woodcutting | 50 | gold | 50 | - |
