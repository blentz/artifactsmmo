# Craft-Planning Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 1758 cells; PASS 108 (6%); nominal-at-skill PASS 37/321; gaps: event_gated 518, combat_blocked 878, material_unreachable 3, skill_unreachable 0, planner_bug 251

Legend: EG=event_gated, CB=combat_blocked, MU=material_unreachable, SU=skill_unreachable, PB=planner_bug.

## alchemy — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_boost_potion | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| earth_boost_potion | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| fire_boost_potion | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| recall_potion | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |
| small_health_potion | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |
| water_boost_potion | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |

## alchemy — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| forest_bank_potion | 20 | 18/15 PB · 18/20 PB · 20/15 PB · 20/20 PB · 22/15 PB · 22/20 PB |
| minor_health_potion | 20 | 18/15 PB · 18/20 PB · 20/15 PB · 20/20 PB · 22/15 PB · 22/20 PB |
| small_antidote | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |

## alchemy — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| antidote | 30 | 28/25 PB · 28/30 PB · 30/25 PB · 30/30 PB · 32/25 PB · 32/30 PB |
| health_potion | 30 | 28/25 PB · 28/30 PASS · 30/25 PB · 30/30 PASS · 32/25 PB · 32/30 PASS |
| health_splash_potion | 30 | 28/25 PB · 28/30 PB · 30/25 PB · 30/30 PB · 32/25 PB · 32/30 PB |

## alchemy — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_res_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| earth_res_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| enchanted_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| enhanced_boost_potion | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| fire_res_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| greater_health_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| health_boost_potion | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| water_res_potion | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |

## alchemy — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| enhanced_antidote | 45 | 48/40 CB · 48/45 CB · 50/40 CB · 50/45 CB |
| enhanced_health_potion | 45 | 48/40 PB · 48/45 PB · 50/40 PB · 50/45 PB |
| enhanced_health_splash_potion | 50 | 48/45 PB · 48/50 PB · 50/45 PB · 50/50 PB |
| lava_underground_potion | 50 | 48/45 PB · 48/50 PB · 50/45 PB · 50/50 PB |
| sandwhisper_potion | 50 | 48/45 PB · 48/50 PB · 50/45 PB · 50/50 PB |

## cooking — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cheese | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| cooked_beef | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| cooked_chicken | 1 | 1/1 PASS · 8/1 PASS · 12/1 PB |
| cooked_gudgeon | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| cooked_shrimp | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| cookie | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| fried_eggs | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |

## cooking — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| apple_pie | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |
| cooked_porkchop | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| cooked_trout | 20 | 18/15 PB · 18/20 PB · 20/15 PB · 20/20 PB · 22/15 PB · 22/20 PB |
| cooked_wolf_meat | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| mushroom_soup | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |

## cooking — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_bass | 30 | 28/25 PB · 28/30 PB · 30/25 PB · 30/30 PB · 32/25 PB · 32/30 PB |
| cooked_rat_meat | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |

## cooking — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_hellhound_meat | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| cooked_salmon | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |
| fish_soup | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| maple_syrup | 40 | 38/35 PB · 38/40 PB · 40/35 PB · 40/40 PB · 42/35 PB · 42/40 PB |

## cooking — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_desert_scorpion_meat | 50 | 48/45 CB · 48/50 CB · 50/45 CB · 50/50 CB |
| cooked_swordfish | 50 | 48/45 PB · 48/50 PB · 50/45 PB · 50/50 PB |

## gearcrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adventurer_helmet | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| adventurer_vest | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| copper_armor | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| copper_boots | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_helmet | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_legs_armor | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |
| feather_coat | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |
| iron_armor | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| iron_boots | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| iron_helm | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| iron_legs_armor | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| iron_shield | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| leather_armor | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| leather_boots | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| leather_hat | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| leather_legs_armor | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| satchel | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| wooden_shield | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |

## gearcrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adventurer_boots | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| adventurer_pants | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| hard_leather_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hard_leather_boots | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hard_leather_helmet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hard_leather_pants | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| lucky_wizard_hat | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| magic_wizard_hat | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| mushmush_jacket | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| mushmush_wizard_hat | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| skeleton_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skeleton_helmet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skeleton_pants | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| slime_shield | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| snakeskin_boots | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_boots | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_helm | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_legs_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| tromatising_mask | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |

## gearcrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| conjurer_cloak | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| conjurer_skirt | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| flying_boots | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| gold_boots | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_helm | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_mask | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_platebody | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_platelegs | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_shield | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| lizard_boots | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| lizard_skin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| lizard_skin_legs_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| obsidian_armor | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| obsidian_helmet | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| obsidian_legs_armor | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| piggy_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| piggy_helmet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| piggy_pants | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| royal_skeleton_armor | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| royal_skeleton_helmet | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| royal_skeleton_pants | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| snakeskin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| snakeskin_legs_armor | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| stormforged_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| stormforged_pants | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |

## gearcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_shield | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| ancient_jean | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| batwing_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cultist_boots | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cultist_cloak | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cultist_hat | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cultist_pants | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cursed_hat | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| diamond_armor | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| diamond_skirt | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| dreadful_armor | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| dreadful_shield | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| earth_shield | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| enchanter_boots | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| enchanter_pants | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| fire_shield | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| hork_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| jester_hat | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| malefic_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| mithril_boots | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_helm | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_platebody | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_platelegs | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| strangold_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| strangold_helmet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| strangold_legs_armor | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| water_shield | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_armor | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_helmet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_pants | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| wratharmor | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| wrathelmet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| wrathpants | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |

## gearcrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_boots | 50 | 48/45 CB · 48/50 CB · 50/45 CB · 50/50 CB |
| adamantite_mask | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_platebody | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_platelegs | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| dark_horned_helmet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| darkforged_boots | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| darkforged_helmet | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| darkforged_plate | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| darkforged_shield | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| demoniac_shield | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| duskarmor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| duskpants | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| dust_helmet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| hell_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| hell_helmet | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| hell_legs_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| magic_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| medic_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| medic_skirt | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| mesh_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| mesh_legs_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| red_dragon_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| red_dragon_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| red_dragon_legs_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| red_dragon_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| sand_snakeskin_armor | 45 | 48/40 CB · 48/45 CB · 50/40 CB · 50/45 CB |
| sand_snakeskin_bandana | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| sand_snakeskin_boots | 45 | 48/40 CB · 48/45 CB · 50/40 CB · 50/45 CB |
| sand_snakeskin_pants | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| skullforged_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| skullforged_pants | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| vital_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| vital_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |

## jewelrycrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_and_water_amulet | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| copper_ring | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| fire_and_earth_amulet | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| iron_ring | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| life_amulet | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |

## jewelrycrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_ring | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| dreadful_amulet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| dreadful_ring | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| earth_ring | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| fire_ring | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| life_ring | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| ring_of_chance | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_amulet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_ring | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_ring | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| water_ring | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| wisdom_amulet | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |

## jewelrycrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| emerald_amulet | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| emerald_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| gold_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| greater_dreadful_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| lost_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| prospecting_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| royal_skeleton_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| ruby_amulet | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| ruby_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| sapphire_amulet | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| sapphire_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| topaz_amulet | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| topaz_ring | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |

## jewelrycrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| ancestral_talisman | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| celest_ring | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| corrupted_stone_amulet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| diamond_amulet | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| divinity_ring | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| eternity_ring | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| greater_emerald_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| greater_ruby_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| greater_sapphire_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| greater_topaz_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| malefic_ring | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| masterful_necklace | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| mithril_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| sacred_ring | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |

## jewelrycrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| dust_amulet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| eternal_red_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| heart_amulet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| hell_ring | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| skullforged_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |

## mining — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| copper_bar | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| iron_bar | 10 | 8/5 PB · 8/10 PASS · 10/5 PB · 10/10 PASS · 12/5 PB · 12/10 PASS |

## mining — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| emerald | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |
| ruby | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |
| sapphire | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |
| steel_bar | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |
| topaz | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |

## mining — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| gold_bar | 30 | 28/25 PB · 28/30 PASS · 30/25 PB · 30/30 PASS · 32/25 PB · 32/30 PASS |
| obsidian_bar | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |

## mining — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| diamond | 35 | 38/30 PB · 38/35 PB · 40/30 PB · 40/35 PB · 42/30 PB · 42/35 PB |
| mithril_bar | 40 | 38/35 PB · 38/40 PASS · 40/35 PB · 40/40 PASS · 42/35 PB · 42/40 PASS |
| strangold_bar | 35 | 38/30 PB · 38/35 PB · 40/30 PB · 40/35 PB · 42/30 PB · 42/35 PB |

## mining — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_bar | 50 | 48/45 PB · 48/50 PASS · 50/45 PB · 50/50 PASS |
| alexandrite | 50 | 48/45 PB · 48/50 PB · 50/45 PB · 50/50 PB |

## weaponcrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| apprentice_gloves | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_axe | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_dagger | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_pickaxe | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| fire_bow | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| fire_staff | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| fishing_net | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| greater_wooden_staff | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| iron_axe | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| iron_dagger | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| iron_pickaxe | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| iron_sword | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| leather_gloves | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| spruce_fishing_rod | 10 | 8/5 PB · 8/10 PB · 10/5 PB · 10/10 PB · 12/5 PB · 12/10 PB |
| sticky_dagger | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| sticky_sword | 5 | 1/1 PB · 1/5 PASS · 8/1 PB · 8/5 PASS · 12/1 PB · 12/5 PASS |
| water_bow | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| wooden_staff | 1 | 1/1 MU · 8/1 MU · 12/1 MU |

## weaponcrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| battlestaff | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| forest_whip | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hunting_bow | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| king_slime_sword | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| mushmush_bow | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| mushstaff | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| shuriken | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_staff | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_axe | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_battleaxe | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_fishing_rod | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_gloves | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_pickaxe | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |

## weaponcrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| dreadful_staff | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| elderwood_staff | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_axe | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| gold_fishing_rod | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| gold_pickaxe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_sword | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| golden_gloves | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| greater_dreadful_staff | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| obsidian_battleaxe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| perfect_bow | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| skull_wand | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| vampire_bow | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |

## weaponcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| bloodblade | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| cursed_sceptre | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| diamond_sword | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| dreadful_battleaxe | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| lightning_sword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| magic_bow | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| mithril_axe | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_fishing_rod | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_gloves | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_pickaxe | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_sword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| strangold_sword | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| wrathsword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |

## weaponcrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_axe | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_fishing_rod | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_gloves | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_pickaxe | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| adamantite_sword | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| blade_of_hell | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| bow_from_hell | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| demoniac_dagger | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| desert_whip | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| dust_sword | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| hell_reaper | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| hell_staff | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| moonlight_staff | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |

## woodcutting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| ash_plank | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| spruce_plank | 10 | 8/5 PB · 8/10 PASS · 10/5 PB · 10/10 PASS · 12/5 PB · 12/10 PASS |

## woodcutting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| hardwood_plank | 20 | 18/15 PB · 18/20 PASS · 20/15 PB · 20/20 PASS · 22/15 PB · 22/20 PASS |

## woodcutting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| dead_wood_plank | 30 | 28/25 PB · 28/30 PASS · 30/25 PB · 30/30 PASS · 32/25 PB · 32/30 PASS |
| sap | 30 | 28/25 PB · 28/30 PASS · 30/25 PB · 30/30 PASS · 32/25 PB · 32/30 PASS |

## woodcutting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cursed_plank | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| magic_sap | 35 | 38/30 PB · 38/35 PB · 40/30 PB · 40/35 PB · 42/30 PB · 42/35 PB |
| magical_plank | 35 | 38/30 PB · 38/35 PB · 40/30 PB · 40/35 PB · 42/30 PB · 42/35 PB |
| maple_plank | 40 | 38/35 PB · 38/40 PASS · 40/35 PB · 40/40 PASS · 42/35 PB · 42/40 PASS |
| maple_sap | 40 | 38/35 PB · 38/40 PASS · 40/35 PB · 40/40 PASS · 42/35 PB · 42/40 PASS |

## woodcutting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| palm_plank | 50 | 48/45 PB · 48/50 PASS · 50/45 PB · 50/50 PASS |

