# Requirement-walk parity — characterization matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_requirement_parity.py`.

Wave 0 of the requirement-model unification epic. This records what the six requirement walks answer TODAY, **disagreements included**, so a later migration wave produces a binary signal: an intentional D-fix, or a regression. Rows are pins, not endorsements.

321 targets; D1 namespace-split 282; D2 drop-blind 282; D3 skill-shape 244; axis2 truncated 2

| target | closure res | closure craft | demand | drop-blind (D2) | prereqs (1-ply) | leafed | needs skills | worst gap | sources |
|---|---|---|---|---|---|---|---|---|---|
| recall_potion | 2 | 1 | 3 | · | 2 | · | · | alchemy:1->5 | craft |
| small_health_potion | 1 | 1 | 2 | · | 1 | · | · | alchemy:1->5 | craft |
| air_boost_potion | 6 | 1 | 4 | algae, green_slimeball | 3 | · | · | alchemy:1->10 | craft |
| earth_boost_potion | 6 | 1 | 4 | algae, yellow_slimeball | 3 | · | · | alchemy:1->10 | craft |
| fire_boost_potion | 6 | 1 | 4 | algae, red_slimeball | 3 | · | · | alchemy:1->10 | craft |
| water_boost_potion | 6 | 1 | 4 | algae, blue_slimeball | 3 | · | · | alchemy:1->10 | craft |
| forest_bank_potion | 2 | 1 | 3 | · | 2 | · | · | alchemy:1->20 | craft |
| minor_health_potion | 6 | 1 | 3 | algae | 2 | · | · | alchemy:1->20 | craft |
| small_antidote | 5 | 2 | 7 | milk_bucket | 3 | · | · | woodcutting:1->30 | craft |
| antidote | 4 | 3 | 7 | · | 3 | · | · | woodcutting:1->40 | craft |
| health_potion | 5 | 2 | 7 | egg | 3 | · | · | alchemy:1->30 | craft |
| health_splash_potion | 7 | 1 | 4 | algae | 3 | · | · | alchemy:1->30 | craft |
| air_res_potion | 2 | 2 | 5 | green_slimeball | 3 | · | · | alchemy:1->40 | craft |
| earth_res_potion | 2 | 2 | 5 | yellow_slimeball | 3 | · | · | alchemy:1->40 | craft |
| enchanted_potion | 2 | 1 | 3 | · | 2 | · | · | alchemy:1->40 | craft |
| enhanced_boost_potion | 3 | 2 | 6 | bat_wing | 4 | · | · | alchemy:1->40 | craft |
| fire_res_potion | 2 | 2 | 5 | red_slimeball | 3 | · | · | alchemy:1->40 | craft |
| greater_health_potion | 6 | 1 | 4 | algae, egg | 3 | · | · | alchemy:1->40 | craft |
| health_boost_potion | 5 | 2 | 7 | milk_bucket | 3 | · | · | alchemy:1->40 | craft |
| water_res_potion | 2 | 2 | 5 | blue_slimeball | 3 | · | · | alchemy:1->40 | craft |
| enhanced_antidote | 4 | 3 | 8 | sand_snake_poison | 4 | · | alchemy | alchemy:1->45 | · |
| enhanced_health_potion | 3 | 2 | 6 | egg | 4 | · | alchemy | alchemy:1->45 | · |
| enhanced_health_splash_potion | 4 | 2 | 6 | coconut | 4 | · | alchemy | alchemy:1->50 | · |
| lava_underground_potion | 2 | 1 | 3 | · | 2 | · | alchemy | alchemy:1->50 | · |
| sandwhisper_potion | 2 | 1 | 3 | · | 2 | · | alchemy | alchemy:1->50 | · |
| cooked_chicken | 0 | 1 | 2 | raw_chicken | 1 | · | · | · | craft |
| cooked_gudgeon | 1 | 1 | 2 | · | 1 | · | · | · | craft |
| cooked_beef | 0 | 1 | 2 | raw_beef | 1 | · | · | cooking:1->5 | craft |
| fried_eggs | 0 | 1 | 2 | egg | 1 | · | · | cooking:1->5 | craft |
| cheese | 0 | 1 | 2 | milk_bucket | 1 | · | · | cooking:1->10 | craft |
| cooked_shrimp | 1 | 1 | 2 | · | 1 | · | · | cooking:1->10 | craft |
| cookie | 0 | 1 | 3 | egg, milk_bucket | 2 | · | · | cooking:1->10 | craft |
| cooked_wolf_meat | 0 | 1 | 2 | raw_wolf_meat | 1 | · | · | cooking:1->15 | craft |
| mushroom_soup | 0 | 1 | 2 | mushroom | 1 | · | · | cooking:1->15 | craft |
| apple_pie | 1 | 1 | 3 | apple, egg | 2 | · | · | cooking:1->20 | craft |
| cooked_porkchop | 0 | 1 | 2 | raw_porkchop | 1 | · | · | cooking:1->20 | craft |
| cooked_trout | 1 | 1 | 2 | · | 1 | · | · | cooking:1->20 | craft |
| cooked_bass | 1 | 1 | 2 | · | 1 | · | · | cooking:1->30 | craft |
| cooked_rat_meat | 0 | 1 | 2 | raw_rat_meat | 1 | · | · | cooking:1->30 | craft |
| cooked_hellhound_meat | 0 | 1 | 2 | raw_hellhound_meat | 1 | · | · | cooking:1->40 | craft |
| cooked_salmon | 1 | 1 | 2 | · | 1 | · | · | cooking:1->40 | craft |
| fish_soup | 2 | 1 | 4 | milk_bucket | 3 | · | · | cooking:1->40 | craft |
| maple_syrup | 1 | 2 | 3 | · | 1 | · | · | cooking:1->40 | craft |
| cooked_desert_scorpion_meat | 0 | 1 | 2 | desert_scorpion_meat | 1 | · | cooking | cooking:1->50 | · |
| cooked_swordfish | 1 | 1 | 2 | · | 1 | · | cooking | cooking:1->50 | · |
| copper_boots | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| copper_helmet | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| wooden_shield | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| copper_armor | 1 | 2 | 4 | wool | 2 | · | · | gearcrafting:1->5 | craft |
| copper_legs_armor | 1 | 2 | 4 | feather | 2 | · | · | gearcrafting:1->5 | craft |
| feather_coat | 1 | 2 | 4 | feather | 2 | · | · | gearcrafting:1->5 | craft |
| satchel | 0 | 1 | 4 | cowhide, feather, jasper_crystal | 3 | · | · | gearcrafting:1->5 | craft |
| adventurer_helmet | 1 | 2 | 6 | cowhide, feather, mushroom | 4 | · | · | gearcrafting:1->10 | craft |
| adventurer_vest | 1 | 2 | 6 | cowhide, wool, yellow_slimeball | 4 | · | · | gearcrafting:1->10 | craft |
| iron_armor | 1 | 2 | 4 | cowhide | 2 | · | · | gearcrafting:1->10 | craft |
| iron_boots | 1 | 2 | 4 | feather | 2 | · | · | gearcrafting:1->10 | craft |
| iron_helm | 1 | 2 | 4 | wool | 2 | · | · | gearcrafting:1->10 | craft |
| iron_legs_armor | 1 | 2 | 4 | cowhide | 2 | · | · | gearcrafting:1->10 | craft |
| iron_shield | 1 | 2 | 4 | wool | 2 | · | · | gearcrafting:1->10 | craft |
| leather_armor | 1 | 2 | 4 | cowhide | 2 | · | · | gearcrafting:1->10 | craft |
| leather_boots | 1 | 2 | 4 | cowhide | 2 | · | · | gearcrafting:1->10 | craft |
| leather_hat | 0 | 1 | 3 | cowhide, yellow_slimeball | 2 | · | · | gearcrafting:1->10 | craft |
| leather_legs_armor | 1 | 2 | 4 | cowhide | 2 | · | · | gearcrafting:1->10 | craft |
| adventurer_boots | 1 | 2 | 5 | mushroom, wolf_hair | 3 | · | · | gearcrafting:1->15 | craft |
| adventurer_pants | 1 | 2 | 6 | cloth, green_cloth, hard_leather | 4 | · | · | gearcrafting:1->15 | craft |
| lucky_wizard_hat | 0 | 1 | 4 | flying_wing, green_cloth, snakeskin | 3 | · | · | gearcrafting:1->15 | craft |
| mushmush_jacket | 0 | 1 | 4 | flying_wing, hard_leather, mushroom | 3 | · | · | gearcrafting:1->15 | craft |
| mushmush_wizard_hat | 0 | 1 | 4 | cowhide, mushroom, wolf_hair | 3 | · | · | gearcrafting:1->15 | craft |
| hard_leather_armor | 2 | 2 | 7 | hard_leather, pig_skin, spider_leg | 4 | · | · | gearcrafting:1->20 | craft |
| hard_leather_boots | 2 | 2 | 7 | green_cloth, hard_leather, pig_skin | 4 | · | · | gearcrafting:1->20 | craft |
| hard_leather_helmet | 2 | 2 | 7 | astralyte_crystal, hard_leather, wolf_bone | 4 | · | · | gearcrafting:1->20 | craft |
| hard_leather_pants | 2 | 2 | 7 | green_cloth, hard_leather, skeleton_skull | 4 | · | · | gearcrafting:1->20 | craft |
| magic_wizard_hat | 2 | 2 | 8 | blue_slimeball, ogre_skin, snakeskin, wolf_hair | 5 | · | · | gearcrafting:1->20 | craft |
| skeleton_armor | 2 | 2 | 7 | pig_skin, skeleton_bone, wolf_bone | 4 | · | · | gearcrafting:1->20 | craft |
| skeleton_helmet | 1 | 2 | 6 | skeleton_bone, skeleton_skull, wolf_bone | 4 | · | · | gearcrafting:1->20 | craft |
| skeleton_pants | 1 | 2 | 6 | skeleton_bone, wolf_bone, wolf_hair | 4 | · | · | gearcrafting:1->20 | craft |
| slime_shield | 2 | 2 | 6 | cloth, king_slimeball | 3 | · | · | gearcrafting:1->20 | craft |
| snakeskin_boots | 2 | 2 | 7 | green_cloth, snakeskin, spider_leg | 4 | · | · | gearcrafting:1->20 | craft |
| steel_armor | 2 | 2 | 7 | cloth, green_cloth, spider_leg | 4 | · | · | gearcrafting:1->20 | craft |
| steel_boots | 4 | 3 | 9 | ogre_skin, snakeskin | 4 | · | · | gearcrafting:1->20 | craft |
| steel_helm | 2 | 2 | 7 | cloth, ogre_skin, wolf_bone | 4 | · | · | gearcrafting:1->20 | craft |
| steel_legs_armor | 2 | 2 | 7 | cloth, king_slimeball, skeleton_skull | 4 | · | · | gearcrafting:1->20 | craft |
| tromatising_mask | 2 | 2 | 7 | cloth, pig_skin, skeleton_bone | 4 | · | · | gearcrafting:1->20 | craft |
| lizard_skin_armor | 1 | 2 | 6 | jasper_crystal, lizard_skin, vampire_tooth | 4 | · | · | woodcutting:1->30 | craft |
| lizard_skin_legs_armor | 0 | 1 | 5 | jasper_crystal, lizard_skin, ogre_eye, vermin_leather | 4 | · | · | gearcrafting:1->25 | craft |
| piggy_armor | 1 | 2 | 6 | full_moon_vampire_cape, jasper_crystal, pig_skin | 4 | · | · | woodcutting:1->30 | craft |
| piggy_helmet | 2 | 2 | 7 | cyclops_eye, full_moon_vampire_cape, pig_skin | 4 | · | · | gearcrafting:1->25 | craft |
| piggy_pants | 2 | 2 | 7 | jasper_crystal, pig_skin, snakeskin | 4 | · | · | gearcrafting:1->25 | craft |
| snakeskin_armor | 0 | 1 | 5 | full_moon_vampire_cape, jasper_crystal, skeleton_bone, snakeskin | 4 | · | · | gearcrafting:1->25 | craft |
| snakeskin_legs_armor | 0 | 1 | 4 | hard_leather, snakeskin, wolf_bone | 3 | · | · | gearcrafting:1->25 | craft |
| stormforged_armor | 1 | 2 | 6 | jasper_crystal, lizard_skin, ogre_eye | 4 | · | · | woodcutting:1->30 | craft |
| stormforged_pants | 0 | 1 | 5 | jasper_crystal, lizard_eye, ogre_skin, vermin_leather | 4 | · | · | gearcrafting:1->25 | craft |
| conjurer_cloak | 0 | 2 | 7 | cyclops_eye, demon_horn, owlbear_hair, piece_of_obsidian, prime_fabric | 5 | · | · | gearcrafting:1->30 | craft |
| conjurer_skirt | 0 | 2 | 7 | full_moon_vampire_cape, owlbear_claw, piece_of_obsidian, vampire_tooth, vermin_leather | 5 | · | · | gearcrafting:1->30 | craft |
| flying_boots | 1 | 2 | 7 | demoniac_dust, hard_leather, magical_cure, owlbear_hair | 5 | · | · | gearcrafting:1->30 | craft |
| gold_boots | 1 | 2 | 7 | lizard_eye, magical_cure, owlbear_hair, vampire_blood | 5 | · | · | gearcrafting:1->30 | craft |
| gold_helm | 1 | 2 | 7 | demon_horn, imp_tail, owlbear_hair, vampire_tooth | 5 | · | · | gearcrafting:1->30 | craft |
| gold_mask | 1 | 2 | 7 | demon_horn, owlbear_claw, red_cloth, skeleton_skull | 5 | · | · | gearcrafting:1->30 | craft |
| gold_platebody | 1 | 2 | 7 | demon_horn, demoniac_dust, full_moon_vampire_cape, red_cloth | 5 | · | · | gearcrafting:1->30 | craft |
| gold_platelegs | 1 | 2 | 7 | lizard_eye, ogre_skin, vampire_tooth, vermin_leather | 5 | · | · | gearcrafting:1->30 | craft |
| gold_shield | 6 | 4 | 9 | demon_horn, magical_cure, sapphire_stone | 5 | · | · | gearcrafting:1->30 | craft |
| lizard_boots | 1 | 2 | 7 | imp_tail, lizard_skin, magical_cure, vermin_leather | 5 | · | · | gearcrafting:1->30 | craft |
| obsidian_armor | 5 | 3 | 8 | demoniac_dust, full_moon_vampire_cape, piece_of_obsidian, ruby_stone, spider_leg | 5 | · | · | gearcrafting:1->30 | craft |
| obsidian_helmet | 5 | 3 | 8 | emerald_stone, lizard_skin, owlbear_hair, piece_of_obsidian, vampire_tooth | 5 | · | · | gearcrafting:1->30 | craft |
| obsidian_legs_armor | 5 | 3 | 8 | lizard_eye, owlbear_claw, piece_of_obsidian, red_cloth, sapphire_stone | 5 | · | · | gearcrafting:1->30 | craft |
| royal_skeleton_armor | 3 | 4 | 12 | demoniac_dust, pig_skin, red_cloth, skeleton_bone, wolf_bone | 4 | · | · | gearcrafting:1->30 | craft |
| royal_skeleton_helmet | 2 | 4 | 11 | owlbear_claw, skeleton_bone, skeleton_skull, vermin_leather, wolf_bone | 4 | · | · | gearcrafting:1->30 | craft |
| royal_skeleton_pants | 2 | 4 | 11 | owlbear_hair, skeleton_bone, vampire_blood, wolf_bone, wolf_hair | 4 | · | · | gearcrafting:1->30 | craft |
| ancient_jean | 2 | 3 | 9 | goblin_guard_foot, lizard_skin, magical_cure, piece_of_obsidian | 5 | · | · | gearcrafting:1->35 | craft |
| cursed_hat | 1 | 3 | 9 | cursed_book, cursed_wood, diamond_stone, malefic_cloth, owlbear_hair, prime_fabric | 6 | · | · | gearcrafting:1->35 | craft |
| dreadful_armor | 0 | 2 | 7 | goblin_guard_foot, ogre_eye, piece_of_obsidian, priestess_orb, prime_fabric | 5 | · | · | gearcrafting:1->35 | craft |
| dreadful_shield | 5 | 3 | 8 | astralyte_crystal, cursed_book, imp_tail, piece_of_obsidian, ruby_stone | 5 | · | · | gearcrafting:1->35 | craft |
| enchanter_boots | 2 | 2 | 8 | lizard_eye, priestess_orb, prime_fabric, vermin_leather | 5 | · | · | gearcrafting:1->35 | craft |
| enchanter_pants | 2 | 2 | 9 | cursed_book, demon_horn, full_moon_vampire_cape, owlbear_claw, prime_fabric | 6 | · | · | gearcrafting:1->35 | craft |
| jester_hat | 0 | 2 | 8 | cursed_book, cursed_wood, goblin_guard_foot, owlbear_hair, prime_fabric, vampire_tooth | 6 | · | · | gearcrafting:1->35 | craft |
| malefic_armor | 2 | 2 | 8 | corrupted_stone, magical_cure, malefic_cloth, owlbear_hair | 5 | · | · | gearcrafting:1->35 | craft |
| strangold_armor | 2 | 2 | 8 | corrupted_stone, demon_horn, magical_cure, owlbear_hair | 5 | · | · | gearcrafting:1->35 | craft |
| strangold_helmet | 2 | 3 | 10 | corrupted_stone, demoniac_dust, diamond_stone, lizard_skin, magical_cure | 6 | · | · | gearcrafting:1->35 | craft |
| strangold_legs_armor | 2 | 2 | 8 | cursed_book, magical_cure, red_cloth, vermin_leather | 5 | · | · | gearcrafting:1->35 | craft |
| air_shield | 6 | 3 | 9 | emerald_stone, green_slimeball, rosenblood_elixir, wolfrider_ponytail | 5 | · | · | gearcrafting:1->40 | craft |
| batwing_helmet | 6 | 3 | 10 | bat_wing, echoless_bat_wing, prime_fabric, rosenblood_elixir, topaz_stone | 6 | · | · | gearcrafting:1->40 | craft |
| cultist_boots | 1 | 2 | 7 | enchanted_fabric, hellhound_hair, malefic_cloth, orc_bone | 5 | · | · | gearcrafting:1->40 | craft |
| cultist_cloak | 1 | 2 | 7 | enchanted_fabric, hellhound_collar, malefic_cloth, red_cloth | 5 | · | · | gearcrafting:1->40 | craft |
| cultist_hat | 1 | 2 | 7 | astralyte_crystal, bat_heart, malefic_cloth, orc_skin | 5 | · | · | gearcrafting:1->40 | craft |
| cultist_pants | 0 | 2 | 7 | cursed_wood, hellhound_hair, magical_cure, malefic_cloth, wolfrider_ponytail | 5 | · | · | gearcrafting:1->40 | craft |
| diamond_armor | 1 | 2 | 7 | diamond_stone, echoless_bat_wing, enchanted_fabric, prime_fabric, rosenblood_elixir | 5 | · | · | gearcrafting:1->40 | craft |
| diamond_skirt | 1 | 2 | 7 | bat_heart, diamond_stone, dryad_hair, enchanted_fabric, full_moon_vampire_cape | 5 | · | · | gearcrafting:1->40 | craft |
| earth_shield | 6 | 3 | 9 | bat_wing, rosenblood_elixir, topaz_stone, yellow_slimeball | 5 | · | · | gearcrafting:1->40 | craft |
| fire_shield | 6 | 3 | 9 | orc_skin, red_slimeball, rosenblood_elixir, ruby_stone | 5 | · | · | gearcrafting:1->40 | craft |
| hork_helmet | 2 | 2 | 8 | bat_wing, dryad_hair, echoless_bat_wing, orc_skin | 5 | · | · | gearcrafting:1->40 | craft |
| mithril_boots | 1 | 2 | 7 | echoless_bat_wing, goblin_eye, hellhound_hair, prime_fabric | 5 | · | · | gearcrafting:1->40 | craft |
| mithril_helm | 2 | 3 | 8 | diamond_stone, echoless_bat_wing, jasper_crystal, wolfrider_ponytail | 5 | · | · | gearcrafting:1->40 | craft |
| mithril_platebody | 1 | 2 | 7 | echoless_bat_wing, goblin_guard_foot, goblin_tooth, prime_fabric | 5 | · | · | gearcrafting:1->40 | craft |
| mithril_platelegs | 1 | 2 | 7 | demoniac_dust, lizard_eye, owlbear_hair, vampire_tooth | 5 | · | · | gearcrafting:1->40 | craft |
| mithril_shield | 1 | 2 | 7 | cyclops_eye, goblin_eye, hellhound_hair, lizard_skin | 5 | · | · | gearcrafting:1->40 | craft |
| water_shield | 6 | 3 | 9 | blue_slimeball, dryad_hair, rosenblood_elixir, sapphire_stone | 5 | · | · | gearcrafting:1->40 | craft |
| white_knight_armor | 1 | 2 | 7 | corrupted_stone, hellhound_hair, prime_fabric, wolfrider_ponytail | 5 | · | · | gearcrafting:1->40 | craft |
| white_knight_helmet | 2 | 3 | 8 | diamond_stone, hellhound_collar, orc_bone, owlbear_claw | 5 | · | · | gearcrafting:1->40 | craft |
| white_knight_pants | 1 | 2 | 7 | astralyte_crystal, goblin_tooth, hellhound_hair, wolfrider_hair | 5 | · | · | gearcrafting:1->40 | craft |
| white_knight_shield | 1 | 2 | 7 | echoless_bat_wing, goblin_eye, hellhound_hair, wolfrider_hair | 5 | · | · | gearcrafting:1->40 | craft |
| wratharmor | 1 | 2 | 7 | goblin_eye, hellhound_collar, prime_fabric, rosenblood_elixir | 5 | · | · | gearcrafting:1->40 | craft |
| wrathelmet | 1 | 2 | 7 | astralyte_crystal, cursed_book, rosenblood_elixir, wolfrider_hair | 5 | · | · | gearcrafting:1->40 | craft |
| wrathpants | 1 | 2 | 7 | enchanted_fabric, goblin_tooth, hellhound_collar, priestess_orb | 5 | · | · | gearcrafting:1->40 | craft |
| darkforged_boots | 1 | 2 | 7 | astralyte_crystal, bat_heart, dark_essence, lava_bucket | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| darkforged_helmet | 1 | 2 | 7 | dark_essence, grimlet_bone, marauder_hand, prime_fabric | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| darkforged_plate | 0 | 2 | 7 | cursed_wood, echoless_bat_wing, grimlet_bone, rosenblood_elixir, sand_snake_poison | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| darkforged_shield | 1 | 3 | 8 | bat_wing, cursed_wood, diamond_stone, enchanted_fabric, marauder_hand | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| demoniac_shield | 0 | 2 | 7 | bat_wing, book_from_hell, cursed_wood, goblin_tooth, grimlet_bone | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| hell_armor | 0 | 2 | 9 | book_from_hell, cursed_wood, demon_horn, efreet_cloth, fire_crystal, grimlet_bone, rosenblood_elixir | 7 | · | gearcrafting | gearcrafting:1->45 | · |
| hell_helmet | 1 | 2 | 7 | lava_bucket, orc_skin, prime_fabric, wolfrider_ponytail | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| hell_legs_armor | 1 | 2 | 7 | grimlet_bone, hellhound_collar, lava_bucket, malefic_cloth | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| mesh_armor | 1 | 2 | 8 | efreet_cloth, enchanted_fabric, grimlet_bone, hellhound_hair, rosenblood_elixir | 6 | · | gearcrafting | gearcrafting:1->45 | · |
| mesh_legs_armor | 1 | 2 | 7 | dark_essence, efreet_cloth, enchanted_fabric, orc_skin | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| sand_snakeskin_armor | 1 | 2 | 7 | cursed_flask, enchanted_fabric, sand_snakeskin, wolfrider_ponytail | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| sand_snakeskin_bandana | 1 | 2 | 7 | enchanted_fabric, grimlet_bone, marauder_hand, sand_snakeskin | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| sand_snakeskin_boots | 1 | 2 | 7 | astralyte_crystal, bat_wing, dark_essence, sand_snakeskin | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| sand_snakeskin_pants | 1 | 2 | 7 | grimlet_bone, marauder_hand, sand_snakeskin, wolfrider_hair | 5 | · | gearcrafting | gearcrafting:1->45 | · |
| adamantite_boots | 2 | 3 | 9 | diamond_stone, dusk_beetle_shell, golden_dust, prime_fabric, wolfrider_hair | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| adamantite_mask | 1 | 3 | 9 | alexandrite_stone, cursed_book, duskworm_skin, jasper_crystal, solar_desert_scorpion_tail | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| adamantite_platebody | 1 | 2 | 8 | adventurer_skull, desert_scorpion_carapace, golden_dust, malefic_cloth, prime_fabric | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| adamantite_platelegs | 1 | 2 | 8 | duskworm_skin, golden_dust, marauder_hand, prime_fabric, sand_snakeskin | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| adamantite_shield | 1 | 2 | 8 | adventurer_skull, bat_wing, dusk_beetle_shell, hellhound_collar, jasper_crystal | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| dark_horned_helmet | 6 | 3 | 10 | duskworm_skin, jasper_crystal, sand_snake_poison, sand_snakeskin, solar_desert_scorpion_tail, topaz_stone | 7 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| duskarmor | 6 | 3 | 10 | dusk_beetle_shell, duskworm_skin, enchanted_fabric, orc_skin, prime_fabric, sapphire_stone | 7 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| duskpants | 1 | 2 | 8 | dusk_beetle_shell, duskworm_skin, goblin_guard_foot, priestess_orb, prime_fabric | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| dust_helmet | 1 | 2 | 8 | adventurer_skull, astralyte_crystal, desert_scorpion_carapace, fire_crystal, golden_dust | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| magic_shield | 2 | 3 | 9 | alexandrite_stone, desert_scorpion_carapace, fennec_ear, grimlet_bone, marauder_hand | 6 | · | gearcrafting, mining, woodcutting | gearcrafting:1->50 | · |
| medic_armor | 1 | 2 | 8 | dryad_hair, fennec_tail, fire_crystal, red_dragon_scale, solar_desert_scorpion_tail | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| medic_skirt | 1 | 2 | 8 | baby_red_dragon_scale, dryad_hair, fennec_ear, fire_crystal, solar_desert_scorpion_tail | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| red_dragon_armor | 0 | 1 | 7 | baby_red_dragon_scale, desert_scorpion_carapace, dragon_bone, fennec_ear, fire_crystal, red_dragon_scale | 6 | · | gearcrafting | gearcrafting:1->50 | · |
| red_dragon_boots | 1 | 2 | 8 | alexandrite_stone, baby_red_dragon_scale, dragon_bone, fire_crystal, red_dragon_scale, solar_desert_scorpion_tail | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| red_dragon_legs_armor | 1 | 2 | 8 | alexandrite_stone, baby_red_dragon_scale, dragon_bone, fennec_tail, marauder_hand, red_dragon_scale | 6 | · | gearcrafting, mining | gearcrafting:1->50 | · |
| red_dragon_shield | 0 | 1 | 6 | baby_red_dragon_scale, dragon_bone, fire_crystal, red_dragon_scale, solar_desert_scorpion_tail | 5 | · | gearcrafting | gearcrafting:1->50 | · |
| skullforged_armor | 1 | 2 | 8 | adventurer_skull, astralyte_crystal, desert_scorpion_carapace, fennec_tail, lava_bucket | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| skullforged_pants | 1 | 2 | 9 | adventurer_skull, astralyte_crystal, demon_horn, desert_scorpion_carapace, dusk_beetle_shell, fennec_tail | 7 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| vital_armor | 6 | 3 | 10 | duskworm_skin, fennec_tail, lava_bucket, prime_fabric, ruby_stone, sand_snake_poison | 7 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| vital_boots | 1 | 2 | 8 | desert_scorpion_carapace, duskworm_skin, efreet_cloth, prime_fabric, sand_snake_poison | 6 | · | gearcrafting, woodcutting | gearcrafting:1->50 | · |
| copper_ring | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| life_amulet | 0 | 1 | 3 | feather, red_slimeball | 2 | · | · | jewelrycrafting:1->5 | craft |
| air_and_water_amulet | 1 | 2 | 5 | blue_slimeball, green_slimeball | 3 | · | · | jewelrycrafting:1->10 | craft |
| fire_and_earth_amulet | 1 | 2 | 5 | red_slimeball, yellow_slimeball | 3 | · | · | jewelrycrafting:1->10 | craft |
| iron_ring | 1 | 2 | 4 | wool | 2 | · | · | jewelrycrafting:1->10 | craft |
| air_ring | 1 | 2 | 5 | flying_wing, green_slimeball | 3 | · | · | jewelrycrafting:1->15 | craft |
| earth_ring | 1 | 2 | 5 | flying_wing, yellow_slimeball | 3 | · | · | jewelrycrafting:1->15 | craft |
| fire_ring | 1 | 2 | 5 | flying_wing, red_slimeball | 3 | · | · | jewelrycrafting:1->15 | craft |
| life_ring | 1 | 2 | 5 | cloth, mushroom | 3 | · | · | jewelrycrafting:1->15 | craft |
| water_ring | 1 | 2 | 5 | blue_slimeball, flying_wing | 3 | · | · | jewelrycrafting:1->15 | craft |
| wisdom_amulet | 1 | 2 | 6 | green_cloth, jasper_crystal, snake_hide | 4 | · | · | jewelrycrafting:1->15 | craft |
| dreadful_amulet | 2 | 2 | 7 | hard_leather, king_slimeball, ogre_eye | 4 | · | · | jewelrycrafting:1->20 | craft |
| dreadful_ring | 2 | 2 | 7 | cyclops_eye, jasper_crystal, ogre_eye | 4 | · | · | jewelrycrafting:1->20 | craft |
| ring_of_chance | 2 | 2 | 7 | jasper_crystal, king_slimeball, pig_skin | 4 | · | · | jewelrycrafting:1->20 | craft |
| skull_amulet | 2 | 2 | 7 | king_slimeball, skeleton_skull, snake_hide | 4 | · | · | jewelrycrafting:1->20 | craft |
| skull_ring | 2 | 2 | 7 | jasper_crystal, skeleton_skull, wolf_bone | 4 | · | · | jewelrycrafting:1->20 | craft |
| steel_ring | 2 | 2 | 7 | hard_leather, skeleton_bone, snake_hide | 4 | · | · | jewelrycrafting:1->20 | craft |
| emerald_amulet | 7 | 3 | 8 | emerald_stone, jasper_crystal, snake_hide | 4 | · | · | jewelrycrafting:1->25 | craft |
| ruby_amulet | 7 | 3 | 8 | jasper_crystal, ruby_stone, snake_hide | 4 | · | · | jewelrycrafting:1->25 | craft |
| sapphire_amulet | 7 | 3 | 8 | jasper_crystal, sapphire_stone, wolf_hair | 4 | · | · | jewelrycrafting:1->25 | craft |
| topaz_amulet | 7 | 3 | 8 | jasper_crystal, topaz_stone, wolf_hair | 4 | · | · | jewelrycrafting:1->25 | craft |
| emerald_ring | 5 | 4 | 9 | emerald_stone, magical_cure, piece_of_obsidian, vampire_blood | 5 | · | · | jewelrycrafting:1->30 | craft |
| gold_ring | 2 | 3 | 8 | skeleton_bone, vampire_blood, wolf_bone | 5 | · | · | jewelrycrafting:1->30 | craft |
| greater_dreadful_amulet | 3 | 4 | 12 | cyclops_eye, hard_leather, king_slimeball, ogre_eye, red_cloth | 5 | · | · | jewelrycrafting:1->30 | craft |
| lost_amulet | 1 | 3 | 8 | cyclops_eye, imp_tail, piece_of_obsidian, red_cloth | 5 | · | · | jewelrycrafting:1->30 | craft |
| prospecting_amulet | 1 | 2 | 7 | magical_cure, ogre_skin, owlbear_hair, spider_leg | 5 | · | · | jewelrycrafting:1->30 | craft |
| royal_skeleton_ring | 1 | 2 | 7 | ogre_skin, owlbear_claw, spider_leg, vampire_tooth | 5 | · | · | jewelrycrafting:1->30 | craft |
| ruby_ring | 5 | 4 | 9 | magical_cure, piece_of_obsidian, ruby_stone, vampire_blood | 5 | · | · | jewelrycrafting:1->30 | craft |
| sapphire_ring | 5 | 4 | 9 | magical_cure, piece_of_obsidian, sapphire_stone, vampire_blood | 5 | · | · | jewelrycrafting:1->30 | craft |
| topaz_ring | 5 | 4 | 9 | magical_cure, piece_of_obsidian, topaz_stone, vampire_blood | 5 | · | · | jewelrycrafting:1->30 | craft |
| ancestral_talisman | 3 | 3 | 9 | cursed_book, diamond_stone, goblin_tooth, priestess_orb | 5 | · | · | jewelrycrafting:1->35 | craft |
| corrupted_stone_amulet | 2 | 2 | 8 | corrupted_stone, magical_cure, malefic_cloth, orc_bone | 5 | · | · | jewelrycrafting:1->35 | craft |
| diamond_amulet | 3 | 4 | 10 | cursed_book, diamond_stone, magical_cure, piece_of_obsidian | 5 | · | · | jewelrycrafting:1->35 | craft |
| malefic_ring | 6 | 4 | 11 | astralyte_crystal, cursed_wood, lizard_eye, owlbear_claw, ruby_stone | 6 | · | · | jewelrycrafting:1->35 | craft |
| masterful_necklace | 2 | 2 | 8 | astralyte_crystal, corrupted_stone, goblin_tooth, priestess_orb | 5 | · | · | jewelrycrafting:1->35 | craft |
| celest_ring | 6 | 4 | 11 | astralyte_crystal, rosenblood_elixir, ruby_stone, sapphire_stone, wolfrider_hair | 6 | · | · | jewelrycrafting:1->40 | craft |
| divinity_ring | 6 | 4 | 11 | astralyte_crystal, hellhound_collar, rosenblood_elixir, sapphire_stone, topaz_stone | 6 | · | · | jewelrycrafting:1->40 | craft |
| eternity_ring | 6 | 4 | 11 | astralyte_crystal, emerald_stone, rosenblood_elixir, topaz_stone, wolfrider_ponytail | 6 | · | · | jewelrycrafting:1->40 | craft |
| greater_emerald_amulet | 8 | 5 | 13 | astralyte_crystal, echoless_bat_wing, emerald_stone, jasper_crystal, snake_hide | 5 | · | · | jewelrycrafting:1->40 | craft |
| greater_ruby_amulet | 8 | 5 | 13 | astralyte_crystal, hellhound_collar, jasper_crystal, ruby_stone, snake_hide | 5 | · | · | jewelrycrafting:1->40 | craft |
| greater_sapphire_amulet | 8 | 5 | 13 | astralyte_crystal, cursed_flask, jasper_crystal, sapphire_stone, wolf_hair | 5 | · | · | jewelrycrafting:1->40 | craft |
| greater_topaz_amulet | 8 | 5 | 13 | astralyte_crystal, hellhound_collar, jasper_crystal, topaz_stone, wolf_hair | 5 | · | · | jewelrycrafting:1->40 | craft |
| mithril_ring | 1 | 2 | 7 | bat_heart, dark_essence, lizard_eye, wolfrider_hair | 5 | · | · | jewelrycrafting:1->40 | craft |
| sacred_ring | 6 | 4 | 11 | astralyte_crystal, emerald_stone, hellhound_collar, rosenblood_elixir, ruby_stone | 6 | · | · | jewelrycrafting:1->40 | craft |
| hell_ring | 2 | 3 | 10 | bat_heart, book_from_hell, diamond_stone, efreet_cloth, grimlet_bone | 6 | · | jewelrycrafting | jewelrycrafting:1->45 | · |
| adamantite_ring | 1 | 2 | 8 | corrupted_stone, desert_scorpion_carapace, duskworm_skin, golden_dust, sand_snakeskin | 6 | · | jewelrycrafting, mining | jewelrycrafting:1->50 | · |
| dust_amulet | 1 | 3 | 10 | alexandrite_stone, dark_essence, demoniac_dust, duskworm_skin, fennec_ear, golden_dust | 7 | · | jewelrycrafting, mining | jewelrycrafting:1->50 | · |
| eternal_red_ring | 1 | 3 | 10 | alexandrite_stone, desert_scorpion_carapace, duskworm_skin, fennec_ear, fennec_tail, sand_snake_poison | 7 | · | jewelrycrafting, mining | jewelrycrafting:1->50 | · |
| heart_amulet | 1 | 2 | 8 | corrupted_stone, duskworm_skin, goblin_eye, golden_dust, grimlet_bone | 6 | · | jewelrycrafting, woodcutting | jewelrycrafting:1->50 | · |
| skullforged_ring | 1 | 3 | 9 | adventurer_skull, alexandrite_stone, dusk_beetle_shell, jasper_crystal, lava_bucket | 6 | · | jewelrycrafting, mining | jewelrycrafting:1->50 | · |
| copper_bar | 1 | 1 | 2 | · | 1 | · | · | · | craft |
| iron_bar | 1 | 1 | 2 | · | 1 | · | · | mining:1->10 | craft |
| emerald | 5 | 1 | 2 | emerald_stone | 1 | · | · | mining:1->20 | craft |
| ruby | 5 | 1 | 2 | ruby_stone | 1 | · | · | mining:1->20 | craft |
| sapphire | 5 | 1 | 2 | sapphire_stone | 1 | · | · | mining:1->20 | craft |
| steel_bar | 2 | 1 | 3 | · | 2 | · | · | mining:1->20 | craft |
| topaz | 5 | 1 | 2 | topaz_stone | 1 | · | · | mining:1->20 | craft |
| gold_bar | 1 | 1 | 2 | · | 1 | · | · | mining:1->30 | craft |
| obsidian_bar | 0 | 1 | 2 | piece_of_obsidian | 1 | · | · | mining:1->30 | craft |
| diamond | 1 | 1 | 2 | diamond_stone | 1 | · | · | mining:1->35 | craft |
| strangold_bar | 2 | 1 | 3 | · | 2 | · | · | mining:1->35 | craft |
| mithril_bar | 1 | 1 | 2 | · | 1 | · | · | mining:1->40 | craft |
| adamantite_bar | 1 | 1 | 2 | · | 1 | · | mining | mining:1->50 | · |
| alexandrite | 1 | 1 | 2 | alexandrite_stone | 1 | · | mining | mining:1->50 | · |
| apprentice_gloves | 0 | 1 | 2 | feather | 1 | · | · | · | craft |
| copper_axe | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| copper_dagger | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| copper_pickaxe | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| fishing_net | 1 | 2 | 3 | · | 1 | · | · | · | craft |
| wooden_staff | 1 | 1 | 3 | wooden_stick | 2 | · | · | · | craft |
| fire_staff | 1 | 2 | 4 | red_slimeball | 2 | · | · | weaponcrafting:1->5 | craft |
| sticky_dagger | 1 | 2 | 4 | green_slimeball | 2 | · | · | weaponcrafting:1->5 | craft |
| sticky_sword | 1 | 2 | 4 | yellow_slimeball | 2 | · | · | weaponcrafting:1->5 | craft |
| water_bow | 1 | 2 | 4 | blue_slimeball | 2 | · | · | weaponcrafting:1->5 | craft |
| fire_bow | 1 | 2 | 4 | red_slimeball | 2 | · | · | weaponcrafting:1->10 | craft |
| greater_wooden_staff | 1 | 2 | 4 | blue_slimeball | 2 | · | · | weaponcrafting:1->10 | craft |
| iron_axe | 2 | 3 | 6 | jasper_crystal | 3 | · | · | weaponcrafting:1->10 | craft |
| iron_dagger | 1 | 2 | 4 | feather | 2 | · | · | weaponcrafting:1->10 | craft |
| iron_pickaxe | 2 | 3 | 6 | jasper_crystal | 3 | · | · | weaponcrafting:1->10 | craft |
| iron_sword | 1 | 2 | 4 | feather | 2 | · | · | weaponcrafting:1->10 | craft |
| leather_gloves | 1 | 2 | 5 | cowhide, jasper_crystal | 3 | · | · | weaponcrafting:1->10 | craft |
| spruce_fishing_rod | 2 | 3 | 6 | jasper_crystal | 3 | · | · | weaponcrafting:1->10 | craft |
| king_slime_sword | 1 | 2 | 5 | jasper_crystal, king_slimeball | 3 | · | · | weaponcrafting:1->15 | craft |
| mushmush_bow | 1 | 2 | 6 | jasper_crystal, mushroom, wolf_hair | 4 | · | · | weaponcrafting:1->15 | craft |
| mushstaff | 1 | 2 | 6 | green_cloth, jasper_crystal, mushroom | 4 | · | · | weaponcrafting:1->15 | craft |
| battlestaff | 4 | 3 | 9 | blue_slimeball, wolf_bone | 4 | · | · | weaponcrafting:1->20 | craft |
| forest_whip | 2 | 2 | 7 | king_slimeball, ogre_eye, wolf_hair | 4 | · | · | weaponcrafting:1->20 | craft |
| hunting_bow | 2 | 2 | 7 | green_cloth, ogre_skin, pig_skin | 4 | · | · | weaponcrafting:1->20 | craft |
| shuriken | 2 | 2 | 7 | flying_wing, ogre_skin, wolf_bone | 4 | · | · | weaponcrafting:1->20 | craft |
| skull_staff | 4 | 3 | 9 | skeleton_bone, skeleton_skull | 4 | · | · | weaponcrafting:1->20 | craft |
| steel_axe | 2 | 2 | 7 | astralyte_crystal, flying_wing, ogre_eye | 4 | · | · | weaponcrafting:1->20 | craft |
| steel_battleaxe | 4 | 3 | 9 | skeleton_bone, wolf_hair | 4 | · | · | weaponcrafting:1->20 | craft |
| steel_fishing_rod | 2 | 2 | 7 | astralyte_crystal, green_cloth, ogre_skin | 4 | · | · | weaponcrafting:1->20 | craft |
| steel_gloves | 2 | 2 | 7 | astralyte_crystal, pig_skin, skeleton_bone | 4 | · | · | weaponcrafting:1->20 | craft |
| steel_pickaxe | 2 | 2 | 7 | astralyte_crystal, pig_skin, spider_leg | 4 | · | · | weaponcrafting:1->20 | craft |
| dreadful_staff | 2 | 2 | 7 | cyclops_eye, jasper_crystal, vampire_blood | 4 | · | · | weaponcrafting:1->25 | craft |
| skull_wand | 2 | 2 | 8 | jasper_crystal, skeleton_skull, spider_leg, vampire_tooth | 5 | · | · | weaponcrafting:1->25 | craft |
| vampire_bow | 2 | 2 | 8 | full_moon_vampire_cape, magical_cure, vampire_blood, vermin_leather | 5 | · | · | weaponcrafting:1->25 | craft |
| elderwood_staff | 1 | 2 | 7 | cyclops_eye, lizard_skin, red_cloth, skeleton_skull | 5 | · | · | weaponcrafting:1->30 | craft |
| gold_axe | 6 | 4 | 9 | magical_cure, red_cloth, ruby_stone | 5 | · | · | weaponcrafting:1->30 | craft |
| gold_fishing_rod | 6 | 4 | 9 | magical_cure, owlbear_claw, sapphire_stone | 5 | · | · | weaponcrafting:1->30 | craft |
| gold_pickaxe | 6 | 4 | 9 | demon_horn, magical_cure, topaz_stone | 5 | · | · | weaponcrafting:1->30 | craft |
| gold_sword | 2 | 3 | 8 | demon_horn, imp_tail, red_cloth | 5 | · | · | weaponcrafting:1->30 | craft |
| golden_gloves | 6 | 4 | 9 | demoniac_dust, emerald_stone, magical_cure, piece_of_obsidian | 5 | · | · | weaponcrafting:1->30 | craft |
| greater_dreadful_staff | 3 | 4 | 12 | cyclops_eye, jasper_crystal, ogre_eye, red_cloth, vampire_blood | 5 | · | · | weaponcrafting:1->30 | craft |
| obsidian_battleaxe | 1 | 3 | 8 | cyclops_eye, imp_tail, lizard_skin, piece_of_obsidian | 5 | · | · | weaponcrafting:1->30 | craft |
| perfect_bow | 1 | 2 | 7 | demon_horn, ogre_eye, red_cloth, spider_leg | 5 | · | · | weaponcrafting:1->30 | craft |
| cursed_sceptre | 3 | 3 | 10 | corrupted_stone, cursed_book, diamond_stone, magical_cure, malefic_cloth | 6 | · | · | weaponcrafting:1->35 | craft |
| diamond_sword | 3 | 3 | 10 | corrupted_stone, diamond_stone, goblin_eye, magical_cure, spider_leg | 6 | · | · | weaponcrafting:1->35 | craft |
| dreadful_battleaxe | 2 | 2 | 8 | goblin_eye, goblin_guard_foot, jasper_crystal, lizard_eye | 5 | · | · | weaponcrafting:1->35 | craft |
| magic_bow | 7 | 3 | 10 | corrupted_stone, lizard_skin, magical_cure, sapphire_stone, wolf_hair | 6 | · | · | weaponcrafting:1->35 | craft |
| strangold_sword | 2 | 2 | 8 | corrupted_stone, goblin_guard_foot, goblin_tooth, magical_cure | 5 | · | · | weaponcrafting:1->35 | craft |
| bloodblade | 1 | 2 | 7 | astralyte_crystal, bat_heart, broken_sword, goblin_tooth | 5 | · | · | weaponcrafting:1->40 | craft |
| lightning_sword | 1 | 2 | 7 | bat_heart, broken_sword, hellhound_hair, magical_cure | 5 | · | · | weaponcrafting:1->40 | craft |
| mithril_axe | 1 | 2 | 7 | dark_essence, owlbear_claw, vampire_tooth, wolfrider_ponytail | 5 | · | · | weaponcrafting:1->40 | craft |
| mithril_fishing_rod | 1 | 3 | 8 | bat_heart, cursed_flask, cursed_wood, hellhound_hair | 5 | · | · | weaponcrafting:1->40 | craft |
| mithril_gloves | 1 | 2 | 7 | cursed_book, cursed_flask, hellhound_collar, imp_tail | 5 | · | · | weaponcrafting:1->40 | craft |
| mithril_pickaxe | 1 | 2 | 7 | broken_sword, dark_essence, owlbear_claw, vampire_blood | 5 | · | · | weaponcrafting:1->40 | craft |
| mithril_sword | 1 | 2 | 8 | astralyte_crystal, broken_sword, corrupted_stone, goblin_guard_foot, wolfrider_hair | 6 | · | · | weaponcrafting:1->40 | craft |
| wrathsword | 1 | 2 | 7 | bat_wing, broken_sword, magical_cure, orc_bone | 5 | · | · | weaponcrafting:1->40 | craft |
| blade_of_hell | 2 | 2 | 9 | book_from_hell, broken_sword, fire_crystal, lava_bucket, orc_bone | 6 | · | weaponcrafting | weaponcrafting:1->45 | · |
| bow_from_hell | 2 | 2 | 9 | book_from_hell, demon_horn, efreet_cloth, fire_crystal, imp_tail | 6 | · | weaponcrafting | weaponcrafting:1->45 | · |
| demoniac_dagger | 2 | 3 | 9 | book_from_hell, cursed_book, efreet_cloth, piece_of_obsidian | 5 | · | weaponcrafting | weaponcrafting:1->45 | · |
| hell_reaper | 1 | 2 | 7 | book_from_hell, broken_sword, efreet_cloth, grimlet_bone | 5 | · | weaponcrafting | weaponcrafting:1->45 | · |
| hell_staff | 0 | 3 | 8 | book_from_hell, cursed_wood, efreet_cloth, imp_tail, piece_of_obsidian | 5 | · | weaponcrafting | weaponcrafting:1->45 | · |
| adamantite_axe | 1 | 2 | 8 | adventurer_skull, astralyte_crystal, cursed_flask, golden_dust, lava_bucket | 6 | · | mining, weaponcrafting | weaponcrafting:1->50 | · |
| adamantite_fishing_rod | 2 | 4 | 11 | astralyte_crystal, cursed_flask, cursed_wood, lava_bucket, solar_desert_scorpion_tail | 7 | · | mining, weaponcrafting, woodcutting | weaponcrafting:1->50 | · |
| adamantite_gloves | 1 | 2 | 8 | astralyte_crystal, desert_scorpion_carapace, efreet_cloth, goblin_guard_foot, rosenblood_elixir | 6 | · | mining, weaponcrafting | weaponcrafting:1->50 | · |
| adamantite_pickaxe | 1 | 2 | 8 | astralyte_crystal, broken_sword, dark_essence, efreet_cloth, sand_snake_poison | 6 | · | mining, weaponcrafting | weaponcrafting:1->50 | · |
| adamantite_sword | 1 | 2 | 8 | adventurer_skull, bat_wing, broken_sword, dusk_beetle_shell, marauder_hand | 6 | · | mining, weaponcrafting | weaponcrafting:1->50 | · |
| desert_whip | 1 | 2 | 8 | desert_scorpion_carapace, duskworm_skin, efreet_cloth, sand_snake_poison, solar_desert_scorpion_tail | 6 | · | weaponcrafting, woodcutting | weaponcrafting:1->50 | · |
| dust_sword | 1 | 2 | 8 | adventurer_skull, broken_sword, cursed_flask, golden_dust, marauder_hand | 6 | · | mining, weaponcrafting | weaponcrafting:1->50 | · |
| moonlight_staff | 2 | 3 | 9 | alexandrite_stone, dusk_beetle_shell, marauder_hand, orc_bone, priestess_orb | 6 | · | mining, weaponcrafting, woodcutting | weaponcrafting:1->50 | · |
| ash_plank | 1 | 1 | 2 | · | 1 | · | · | · | craft |
| spruce_plank | 1 | 1 | 2 | · | 1 | · | · | woodcutting:1->10 | craft |
| hardwood_plank | 2 | 1 | 3 | · | 2 | · | · | woodcutting:1->20 | craft |
| dead_wood_plank | 1 | 1 | 2 | · | 1 | · | · | woodcutting:1->30 | craft |
| sap | 4 | 1 | 4 | · | 0 | yes | · | woodcutting:1->30 | craft, gather |
| cursed_plank | 0 | 1 | 2 | cursed_wood | 1 | · | · | woodcutting:1->35 | craft |
| magic_sap | 1 | 1 | 2 | · | 1 | · | · | woodcutting:1->35 | craft |
| magical_plank | 2 | 1 | 3 | · | 2 | · | · | woodcutting:1->35 | craft |
| maple_plank | 1 | 1 | 2 | · | 1 | · | · | woodcutting:1->40 | craft |
| maple_sap | 1 | 1 | 2 | · | 0 | yes | · | woodcutting:1->40 | craft, gather |
| palm_plank | 1 | 1 | 2 | · | 1 | · | woodcutting | woodcutting:1->50 | · |
