# Craft-Planning Conditions

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_conditions.py`.
>
> Each recipe climbs the ladder of `audit/craft_conditions.py` (cell, every skill at the character level, gold, its events, then the character level in steps of 5); the first rung that plans is its condition. A fight's need is `bare` (the stats win), the potion loadout that wins it, or `loses`.

321 recipes; planned 321 (cell 108, events 21, gold 6, grey 6, L40 4, L6 5, skills 15, gear 13, achievements 111, L25 3, grey@L45 4, held:enchanted_fabric 9, grey@L50 1, L30 2, L45 2, keys 3, party 7, held:wooden_stick 1); unplanned 0 ()

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
| enhanced_health_potion | alchemy | 45 | grey | 50 | chicken: bare |
| enhanced_health_splash_potion | alchemy | 50 | L40 | 40 | - |
| lava_underground_potion | alchemy | 50 | L40 | 40 | - |
| sandwhisper_potion | alchemy | 50 | gold | 50 | - |
| cooked_chicken | cooking | 1 | cell | 1 | chicken: bare |
| cooked_gudgeon | cooking | 1 | cell | 1 | - |
| cooked_beef | cooking | 5 | L6 | 6 | cow: small_health_potion |
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
| cooked_desert_scorpion_meat | cooking | 50 | gear | 50 | solar_desert_scorpion: greater_health_potion |
| cooked_swordfish | cooking | 50 | gold | 50 | - |
| copper_boots | gearcrafting | 1 | cell | 1 | - |
| copper_helmet | gearcrafting | 1 | cell | 1 | - |
| wooden_shield | gearcrafting | 1 | cell | 1 | - |
| copper_armor | gearcrafting | 5 | L6 | 6 | sheep: bare |
| copper_legs_armor | gearcrafting | 5 | cell | 1 | chicken: bare |
| feather_coat | gearcrafting | 5 | cell | 1 | chicken: bare |
| satchel | gearcrafting | 5 | achievements | 1 | chicken: bare |
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
| hard_leather_helmet | gearcrafting | 20 | achievements | 20 | wolf: bare |
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
| lizard_skin_armor | gearcrafting | 25 | achievements | 30 | bandit_lizard: bare |
| lizard_skin_legs_armor | gearcrafting | 25 | achievements | 30 | bandit_lizard: bare |
| piggy_armor | gearcrafting | 25 | achievements | 30 | owlbear: bare |
| piggy_helmet | gearcrafting | 25 | L25 | 25 | pig: bare, cyclops: minor_health_potion, full_moon_vampire: bare |
| piggy_pants | gearcrafting | 25 | achievements | 30 | cyclops: bare |
| snakeskin_armor | gearcrafting | 25 | achievements | 30 | owlbear: bare |
| snakeskin_legs_armor | gearcrafting | 25 | cell | 30 | flying_snake: bare, cow: bare, wolf: bare |
| stormforged_armor | gearcrafting | 25 | achievements | 30 | bandit_lizard: bare |
| stormforged_pants | gearcrafting | 25 | achievements | 30 | bandit_lizard: bare |
| conjurer_cloak | gearcrafting | 30 | achievements | 30 | owlbear: bare |
| conjurer_skirt | gearcrafting | 30 | events | 30 | imp: bare, full_moon_vampire: bare, owlbear: bare, rat: bare |
| flying_boots | gearcrafting | 30 | achievements | 30 | cyclops: bare |
| gold_boots | gearcrafting | 30 | achievements | 30 | bandit_lizard: bare |
| gold_helm | gearcrafting | 30 | events | 30 | demon: minor_health_potion, imp: bare, vampire: bare, owlbear: bare |
| gold_mask | gearcrafting | 30 | L25 | 25 | - |
| gold_platebody | gearcrafting | 30 | events | 30 | full_moon_vampire: bare, death_knight: bare, imp: bare, demon: small_health_potion |
| gold_platelegs | gearcrafting | 30 | events | 30 | bandit_lizard: bare, rat: bare, vampire: bare, ogre: bare |
| gold_shield | gearcrafting | 30 | achievements | 30 | owlbear: bare |
| lizard_boots | gearcrafting | 30 | achievements | 30 | bandit_lizard: bare |
| obsidian_armor | gearcrafting | 30 | events | 30 | imp: bare, spider: bare, full_moon_vampire: bare |
| obsidian_helmet | gearcrafting | 30 | events | 30 | imp: bare, owlbear: bare, bandit_lizard: bare, vampire: bare |
| obsidian_legs_armor | gearcrafting | 30 | events | 30 | imp: bare, owlbear: bare, bandit_lizard: bare, death_knight: bare |
| royal_skeleton_armor | gearcrafting | 30 | cell | 30 | - |
| royal_skeleton_helmet | gearcrafting | 30 | cell | 30 | - |
| royal_skeleton_pants | gearcrafting | 30 | cell | 30 | - |
| ancient_jean | gearcrafting | 35 | achievements | 40 | orc: bare |
| cursed_hat | gearcrafting | 35 | achievements | 40 | goblin: bare |
| dreadful_armor | gearcrafting | 35 | achievements | 40 | goblin: bare |
| dreadful_shield | gearcrafting | 35 | achievements | 40 | goblin: bare |
| enchanter_boots | gearcrafting | 35 | achievements | 40 | orc: bare |
| enchanter_pants | gearcrafting | 35 | achievements | 40 | goblin_guard: bare |
| jester_hat | gearcrafting | 35 | achievements | 40 | goblin: bare |
| malefic_armor | gearcrafting | 35 | achievements | 40 | goblin: bare |
| strangold_armor | gearcrafting | 35 | achievements | 40 | demon: bare |
| strangold_helmet | gearcrafting | 35 | achievements | 40 | orc: bare |
| strangold_legs_armor | gearcrafting | 35 | achievements | 40 | goblin: bare |
| air_shield | gearcrafting | 40 | grey@L45 | 45 | green_slime: bare, goblin_wolfrider: bare, rosenblood: health_boost_potion+enhanced_health_potion |
| batwing_helmet | gearcrafting | 40 | achievements | 40 | goblin_guard: bare |
| cultist_boots | gearcrafting | 40 | held:enchanted_fabric | 60 | cultist_emperor: bare, hellhound: bare, orc: bare |
| cultist_cloak | gearcrafting | 40 | held:enchanted_fabric | 60 | cultist_emperor: bare, death_knight: bare, hellhound: bare |
| cultist_hat | gearcrafting | 40 | achievements | 40 | goblin: bare |
| cultist_pants | gearcrafting | 40 | achievements | 40 | goblin: bare |
| diamond_armor | gearcrafting | 40 | achievements | 40 | goblin_guard: bare |
| diamond_skirt | gearcrafting | 40 | held:enchanted_fabric | 60 | bat: bare, full_moon_vampire: bare, dryad: bare |
| earth_shield | gearcrafting | 40 | grey@L45 | 45 | yellow_slime: bare, bat: bare, rosenblood: health_boost_potion+enhanced_health_potion |
| fire_shield | gearcrafting | 40 | grey@L50 | 50 | red_slime: bare, orc: bare, rosenblood: fire_res_potion+enhanced_health_potion |
| hork_helmet | gearcrafting | 40 | events | 40 | orc: greater_health_potion, dryad: health_potion, bat: greater_health_potion, echoless_bat: greater_health_potion |
| mithril_boots | gearcrafting | 40 | achievements | 40 | goblin_guard: bare |
| mithril_helm | gearcrafting | 40 | achievements | 40 | goblin_guard: bare |
| mithril_platebody | gearcrafting | 40 | achievements | 40 | goblin_guard: bare |
| mithril_platelegs | gearcrafting | 40 | L30 | 30 | - |
| mithril_shield | gearcrafting | 40 | L30 | 30 | - |
| water_shield | gearcrafting | 40 | grey@L45 | 45 | blue_slime: bare, dryad: bare, rosenblood: health_boost_potion+enhanced_health_potion |
| white_knight_armor | gearcrafting | 40 | achievements | 40 | goblin: bare |
| white_knight_helmet | gearcrafting | 40 | events | 40 | hellhound: greater_health_potion, orc: greater_health_potion, owlbear: bare |
| white_knight_pants | gearcrafting | 40 | achievements | 40 | goblin: bare |
| white_knight_shield | gearcrafting | 40 | events | 40 | echoless_bat: greater_health_potion, goblin_wolfrider: health_potion, hellhound: greater_health_potion, goblin: health_potion |
| wratharmor | gearcrafting | 40 | achievements | 40 | goblin: bare |
| wrathelmet | gearcrafting | 40 | achievements | 40 | goblin: bare |
| wrathpants | gearcrafting | 40 | held:enchanted_fabric | 60 | goblin_priestess: enhanced_health_potion, goblin: bare, hellhound: bare |
| darkforged_boots | gearcrafting | 45 | achievements | 50 | goblin_wolfrider: health_potion |
| darkforged_helmet | gearcrafting | 45 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| darkforged_plate | gearcrafting | 45 | grey | 50 | cursed_tree: bare, echoless_bat: bare, rosenblood: enhanced_health_potion, grimlet: small_health_potion, sand_snake: bare |
| darkforged_shield | gearcrafting | 45 | held:enchanted_fabric | 60 | cursed_tree: bare, sea_marauder: bare, bat: bare |
| demoniac_shield | gearcrafting | 45 | L40 | 40 | cursed_tree: bare, grimlet: minor_health_potion, bat: bare, goblin: bare |
| hell_armor | gearcrafting | 45 | grey | 50 | cursed_tree: bare, efreet_sultan: bare, grimlet: small_health_potion, flameche: fire_res_potion+enhanced_health_potion, rosenblood: enhanced_health_potion, demon: bare |
| hell_helmet | gearcrafting | 45 | achievements | 50 | goblin_wolfrider: health_potion |
| hell_legs_armor | gearcrafting | 45 | gear | 50 | grimlet: small_health_potion, efreet_sultan: bare, cultist_emperor: bare, hellhound: bare |
| mesh_armor | gearcrafting | 45 | held:enchanted_fabric | 60 | efreet_sultan: bare, rosenblood: enhanced_health_potion, grimlet: bare, hellhound: bare |
| mesh_legs_armor | gearcrafting | 45 | held:enchanted_fabric | 60 | efreet_sultan: bare, orc: bare, cultist_alchemist: bare |
| sand_snakeskin_armor | gearcrafting | 45 | held:enchanted_fabric | 60 | sand_snake: bare, cultist_alchemist: bare, goblin_wolfrider: bare |
| sand_snakeskin_bandana | gearcrafting | 45 | held:enchanted_fabric | 60 | sand_snake: bare, grimlet: bare, sea_marauder: bare |
| sand_snakeskin_boots | gearcrafting | 45 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| sand_snakeskin_pants | gearcrafting | 45 | gear | 50 | sand_snake: bare, sea_marauder: bare, grimlet: small_health_potion, goblin_wolfrider: bare |
| adamantite_boots | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| adamantite_mask | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| adamantite_platebody | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| adamantite_platelegs | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| adamantite_shield | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| dark_horned_helmet | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| duskarmor | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| duskpants | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| dust_helmet | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| magic_shield | gearcrafting | 50 | L45 | 45 | - |
| medic_armor | gearcrafting | 50 | keys | 50 | solar_desert_scorpion: greater_health_potion, red_dragon: health_boost_potion+enhanced_health_potion, fennec: enhanced_health_potion, dryad: bare, flameche: fire_res_potion+enhanced_health_potion |
| medic_skirt | gearcrafting | 50 | keys | 50 | solar_desert_scorpion: greater_health_potion, baby_red_dragon: greater_health_potion, fennec: enhanced_health_potion, dryad: bare, flameche: fire_res_potion+enhanced_health_potion |
| red_dragon_armor | gearcrafting | 50 | gear | 50 | red_dragon: health_boost_potion+enhanced_health_potion, desert_scorpion: bare, fennec: enhanced_health_potion, baby_red_dragon: greater_health_potion, flameche: fire_res_potion+enhanced_health_potion |
| red_dragon_boots | gearcrafting | 50 | gear | 50 | red_dragon: health_boost_potion+enhanced_health_potion, baby_red_dragon: greater_health_potion, solar_desert_scorpion: greater_health_potion, flameche: fire_res_potion+enhanced_health_potion |
| red_dragon_legs_armor | gearcrafting | 50 | gear | 50 | red_dragon: health_boost_potion+enhanced_health_potion, sea_marauder: bare, fennec: enhanced_health_potion, baby_red_dragon: greater_health_potion |
| red_dragon_shield | gearcrafting | 50 | gear | 50 | red_dragon: health_boost_potion+enhanced_health_potion, baby_red_dragon: greater_health_potion, flameche: fire_res_potion+enhanced_health_potion, solar_desert_scorpion: greater_health_potion |
| skullforged_armor | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| skullforged_pants | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: minor_health_potion |
| vital_armor | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| vital_boots | gearcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| copper_ring | jewelrycrafting | 1 | cell | 1 | - |
| life_amulet | jewelrycrafting | 5 | L6 | 6 | chicken: bare, red_slime: bare |
| air_and_water_amulet | jewelrycrafting | 10 | cell | 10 | green_slime: bare, blue_slime: bare |
| fire_and_earth_amulet | jewelrycrafting | 10 | cell | 10 | red_slime: bare, yellow_slime: bare |
| iron_ring | jewelrycrafting | 10 | cell | 10 | sheep: bare |
| air_ring | jewelrycrafting | 15 | cell | 20 | green_slime: bare, flying_snake: bare |
| earth_ring | jewelrycrafting | 15 | cell | 20 | yellow_slime: bare, flying_snake: bare |
| fire_ring | jewelrycrafting | 15 | cell | 20 | red_slime: bare, flying_snake: bare |
| life_ring | jewelrycrafting | 15 | cell | 20 | sheep: bare, mushmush: bare |
| water_ring | jewelrycrafting | 15 | cell | 20 | blue_slime: bare, flying_snake: bare |
| wisdom_amulet | jewelrycrafting | 15 | achievements | 20 | wolf: bare |
| dreadful_amulet | jewelrycrafting | 20 | skills | 20 | ogre: minor_health_potion, cow: bare, king_slime: minor_health_potion |
| dreadful_ring | jewelrycrafting | 20 | achievements | 20 | wolf: bare |
| ring_of_chance | jewelrycrafting | 20 | achievements | 20 | wolf: bare |
| skull_amulet | jewelrycrafting | 20 | skills | 20 | skeleton: bare, king_slime: minor_health_potion, flying_snake: bare |
| skull_ring | jewelrycrafting | 20 | achievements | 20 | wolf: bare |
| steel_ring | jewelrycrafting | 20 | cell | 20 | skeleton: bare, cow: bare, flying_snake: bare |
| emerald_amulet | jewelrycrafting | 25 | achievements | 30 | cyclops: bare |
| ruby_amulet | jewelrycrafting | 25 | achievements | 30 | cyclops: bare |
| sapphire_amulet | jewelrycrafting | 25 | achievements | 30 | cyclops: bare |
| topaz_amulet | jewelrycrafting | 25 | achievements | 30 | cyclops: bare |
| emerald_ring | jewelrycrafting | 30 | achievements | 30 | cyclops: bare |
| gold_ring | jewelrycrafting | 30 | cell | 30 | - |
| greater_dreadful_amulet | jewelrycrafting | 30 | cell | 30 | - |
| lost_amulet | jewelrycrafting | 30 | cell | 30 | - |
| prospecting_amulet | jewelrycrafting | 30 | achievements | 30 | cyclops: bare |
| royal_skeleton_ring | jewelrycrafting | 30 | cell | 30 | - |
| ruby_ring | jewelrycrafting | 30 | achievements | 30 | cyclops: bare |
| sapphire_ring | jewelrycrafting | 30 | achievements | 30 | cyclops: bare |
| topaz_ring | jewelrycrafting | 30 | achievements | 30 | cyclops: bare |
| ancestral_talisman | jewelrycrafting | 35 | grey@L45 | 45 | cultist_acolyte: bare, goblin: bare, goblin_priestess: enhanced_health_potion |
| corrupted_stone_amulet | jewelrycrafting | 35 | achievements | 40 | goblin: bare |
| diamond_amulet | jewelrycrafting | 35 | achievements | 40 | goblin: bare |
| malefic_ring | jewelrycrafting | 35 | achievements | 40 | orc: bare |
| masterful_necklace | jewelrycrafting | 35 | achievements | 40 | goblin: bare |
| celest_ring | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| divinity_ring | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| eternity_ring | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| greater_emerald_amulet | jewelrycrafting | 40 | achievements | 40 | goblin_guard: bare |
| greater_ruby_amulet | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| greater_sapphire_amulet | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| greater_topaz_amulet | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| mithril_ring | jewelrycrafting | 40 | grey | 40 | bandit_lizard: bare, goblin_wolfrider: small_health_potion, cultist_alchemist: earth_boost_potion+health_potion, bat: bare |
| sacred_ring | jewelrycrafting | 40 | achievements | 40 | goblin: bare |
| hell_ring | jewelrycrafting | 45 | L40 | 40 | grimlet: minor_health_potion, efreet_sultan: greater_health_potion, bat: bare |
| adamantite_ring | jewelrycrafting | 50 | party | 50 | cultist_acolyte: bare, sand_snake: bare, duskworm: party3:water_res_potion+enhanced_health_potion, sandwarden: greater_health_potion, desert_scorpion: bare |
| dust_amulet | jewelrycrafting | 50 | party | 50 | cultist_alchemist: bare, duskworm: party3:water_res_potion+enhanced_health_potion, fennec: enhanced_health_potion, imp: bare, sandwarden: greater_health_potion |
| eternal_red_ring | jewelrycrafting | 50 | party | 50 | sand_snake: bare, duskworm: party3:water_res_potion+enhanced_health_potion, fennec: enhanced_health_potion, desert_scorpion: bare |
| heart_amulet | jewelrycrafting | 50 | party | 50 | cultist_acolyte: bare, grimlet: small_health_potion, duskworm: party3:water_res_potion+enhanced_health_potion, sandwarden: greater_health_potion, goblin: bare |
| skullforged_ring | jewelrycrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
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
| wooden_staff | weaponcrafting | 1 | held:wooden_stick | 60 | - |
| fire_staff | weaponcrafting | 5 | L6 | 6 | red_slime: bare |
| sticky_dagger | weaponcrafting | 5 | gear | 1 | green_slime: bare |
| sticky_sword | weaponcrafting | 5 | cell | 1 | yellow_slime: bare |
| water_bow | weaponcrafting | 5 | L6 | 6 | blue_slime: bare |
| fire_bow | weaponcrafting | 10 | cell | 10 | red_slime: bare |
| greater_wooden_staff | weaponcrafting | 10 | cell | 10 | blue_slime: bare |
| iron_axe | weaponcrafting | 10 | achievements | 10 | cow: bare |
| iron_dagger | weaponcrafting | 10 | cell | 10 | chicken: bare |
| iron_pickaxe | weaponcrafting | 10 | achievements | 10 | cow: bare |
| iron_sword | weaponcrafting | 10 | cell | 10 | chicken: bare |
| leather_gloves | weaponcrafting | 10 | achievements | 10 | cow: bare |
| spruce_fishing_rod | weaponcrafting | 10 | achievements | 10 | cow: bare |
| king_slime_sword | weaponcrafting | 15 | achievements | 20 | wolf: bare |
| mushmush_bow | weaponcrafting | 15 | achievements | 20 | wolf: bare |
| mushstaff | weaponcrafting | 15 | achievements | 20 | wolf: bare |
| battlestaff | weaponcrafting | 20 | cell | 20 | wolf: bare, blue_slime: bare |
| forest_whip | weaponcrafting | 20 | skills | 20 | king_slime: minor_health_potion, wolf: bare, ogre: minor_health_potion |
| hunting_bow | weaponcrafting | 20 | skills | 20 | highwayman: bare, ogre: minor_health_potion, pig: bare |
| shuriken | weaponcrafting | 20 | skills | 20 | wolf: bare, ogre: minor_health_potion, flying_snake: bare |
| skull_staff | weaponcrafting | 20 | cell | 20 | skeleton: bare |
| steel_axe | weaponcrafting | 20 | achievements | 20 | wolf: bare |
| steel_battleaxe | weaponcrafting | 20 | cell | 20 | skeleton: bare, wolf: bare |
| steel_fishing_rod | weaponcrafting | 20 | achievements | 20 | wolf: bare |
| steel_gloves | weaponcrafting | 20 | achievements | 20 | wolf: bare |
| steel_pickaxe | weaponcrafting | 20 | achievements | 20 | wolf: bare |
| dreadful_staff | weaponcrafting | 25 | achievements | 30 | cyclops: bare |
| skull_wand | weaponcrafting | 25 | achievements | 30 | cyclops: bare |
| vampire_bow | weaponcrafting | 25 | achievements | 30 | owlbear: bare |
| elderwood_staff | weaponcrafting | 30 | L25 | 25 | - |
| gold_axe | weaponcrafting | 30 | achievements | 30 | cyclops: bare |
| gold_fishing_rod | weaponcrafting | 30 | achievements | 30 | cyclops: bare |
| gold_pickaxe | weaponcrafting | 30 | achievements | 30 | owlbear: bare |
| gold_sword | weaponcrafting | 30 | events | 30 | imp: bare, death_knight: bare, demon: minor_health_potion |
| golden_gloves | weaponcrafting | 30 | achievements | 30 | cyclops: bare |
| greater_dreadful_staff | weaponcrafting | 30 | achievements | 30 | cyclops: bare |
| obsidian_battleaxe | weaponcrafting | 30 | events | 30 | imp: bare, bandit_lizard: bare, cyclops: bare |
| perfect_bow | weaponcrafting | 30 | events | 30 | spider: bare, demon: minor_health_potion, ogre: bare, death_knight: bare |
| cursed_sceptre | weaponcrafting | 35 | achievements | 40 | goblin: bare |
| diamond_sword | weaponcrafting | 35 | achievements | 40 | goblin: bare |
| dreadful_battleaxe | weaponcrafting | 35 | achievements | 40 | orc: bare |
| magic_bow | weaponcrafting | 35 | achievements | 40 | orc: bare |
| strangold_sword | weaponcrafting | 35 | achievements | 40 | goblin: bare |
| bloodblade | weaponcrafting | 40 | achievements | 40 | goblin: bare |
| lightning_sword | weaponcrafting | 40 | achievements | 40 | goblin: bare |
| mithril_axe | weaponcrafting | 40 | gear | 40 | owlbear: bare, goblin_wolfrider: small_health_potion, cultist_alchemist: earth_boost_potion+health_potion, vampire: bare |
| mithril_fishing_rod | weaponcrafting | 40 | gear | 40 | cursed_tree: bare, hellhound: minor_health_potion, cultist_alchemist: earth_boost_potion+health_potion, bat: bare |
| mithril_gloves | weaponcrafting | 40 | gear | 40 | cultist_acolyte: bare, hellhound: minor_health_potion, imp: bare, cultist_alchemist: earth_boost_potion+health_potion |
| mithril_pickaxe | weaponcrafting | 40 | gear | 40 | owlbear: bare, goblin_wolfrider: small_health_potion, cultist_alchemist: earth_boost_potion+health_potion, vampire: bare |
| mithril_sword | weaponcrafting | 40 | achievements | 40 | goblin: bare |
| wrathsword | weaponcrafting | 40 | achievements | 40 | goblin: bare |
| blade_of_hell | weaponcrafting | 45 | keys | 50 | efreet_sultan: bare, flameche: fire_res_potion+enhanced_health_potion, goblin_wolfrider: bare, orc: bare |
| bow_from_hell | weaponcrafting | 45 | grey | 50 | efreet_sultan: bare, demon: bare, flameche: fire_res_potion+enhanced_health_potion, imp: bare |
| demoniac_dagger | weaponcrafting | 45 | events | 50 | efreet_sultan: greater_health_potion, cultist_acolyte: bare |
| hell_reaper | weaponcrafting | 45 | gear | 50 | efreet_sultan: bare, goblin_wolfrider: bare, grimlet: small_health_potion |
| hell_staff | weaponcrafting | 45 | grey | 50 | cursed_tree: bare, efreet_sultan: bare, imp: bare |
| adamantite_axe | weaponcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| adamantite_fishing_rod | weaponcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| adamantite_gloves | weaponcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| adamantite_pickaxe | weaponcrafting | 50 | achievements | 50 | goblin_wolfrider: health_potion |
| adamantite_sword | weaponcrafting | 50 | party | 50 | duskworm: party3:water_res_potion+enhanced_health_potion, dusk_beetle: bare, bat: bare, sea_marauder: bare, goblin_wolfrider: bare |
| desert_whip | weaponcrafting | 50 | party | 50 | sand_snake: bare, efreet_sultan: bare, duskworm: party3:water_res_potion+enhanced_health_potion, desert_scorpion: bare, solar_desert_scorpion: greater_health_potion |
| dust_sword | weaponcrafting | 50 | party | 50 | sea_marauder: bare, duskworm: party3:water_res_potion+enhanced_health_potion, cultist_alchemist: bare, sandwarden: greater_health_potion, goblin_wolfrider: bare |
| moonlight_staff | weaponcrafting | 50 | L45 | 45 | - |
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
