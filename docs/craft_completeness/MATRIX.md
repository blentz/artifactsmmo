# Craft-Planning Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 1758 cells; PASS 494 (28%); nominal-at-skill PASS 75/321; gaps: event_gated 732, combat_blocked 508, material_unreachable 5, skill_unreachable 0, grey_farm_suppressed 1, purchase_recursion 18, planner_bug 0

Legend: EG=event_gated, CB=combat_blocked, MU=material_unreachable, SU=skill_unreachable, GF=grey_farm_suppressed, PR=purchase_recursion, PB=planner_bug.

## alchemy — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_boost_potion | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| earth_boost_potion | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| fire_boost_potion | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| recall_potion | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| small_health_potion | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| water_boost_potion | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |

## alchemy — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| forest_bank_potion | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| minor_health_potion | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| small_antidote | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |

## alchemy — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| antidote | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| health_potion | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| health_splash_potion | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |

## alchemy — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| earth_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| enchanted_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| enhanced_boost_potion | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| fire_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| greater_health_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| health_boost_potion | 40 | 38/35 PASS · 38/40 CB · 40/35 PASS · 40/40 CB · 42/35 PASS · 42/40 CB |
| water_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## alchemy — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| enhanced_antidote | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| enhanced_health_potion | 45 | 48/40 PASS · 48/45 PASS · 50/40 PASS · 50/45 PASS |
| enhanced_health_splash_potion | 50 | 48/45 PASS · 48/50 EG · 50/45 PASS · 50/50 EG |
| lava_underground_potion | 50 | 48/45 PASS · 48/50 MU · 50/45 PASS · 50/50 MU |
| sandwhisper_potion | 50 | 48/45 PASS · 48/50 PASS · 50/45 PASS · 50/50 PASS |

## cooking — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cheese | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| cooked_beef | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| cooked_chicken | 1 | 1/1 PASS · 8/1 PASS · 12/1 GF |
| cooked_gudgeon | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| cooked_shrimp | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| cookie | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| fried_eggs | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |

## cooking — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| apple_pie | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| cooked_porkchop | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| cooked_trout | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| cooked_wolf_meat | 15 | 18/10 PASS · 18/15 CB · 20/10 PASS · 20/15 CB · 22/10 PASS · 22/15 CB |
| mushroom_soup | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |

## cooking — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_bass | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| cooked_rat_meat | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |

## cooking — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_hellhound_meat | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| cooked_salmon | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| fish_soup | 40 | 38/35 PASS · 38/40 CB · 40/35 PASS · 40/40 CB · 42/35 PASS · 42/40 CB |
| maple_syrup | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## cooking — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_desert_scorpion_meat | 50 | 48/45 PASS · 48/50 CB · 50/45 PASS · 50/50 CB |
| cooked_swordfish | 50 | 48/45 PASS · 48/50 PASS · 50/45 PASS · 50/50 PASS |

## gearcrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adventurer_helmet | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| adventurer_vest | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| copper_armor | 5 | 1/1 PASS · 1/5 CB · 8/1 PASS · 8/5 CB · 12/1 PASS · 12/5 CB |
| copper_boots | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_helmet | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_legs_armor | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| feather_coat | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| iron_armor | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| iron_boots | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_helm | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| iron_legs_armor | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| iron_shield | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| leather_armor | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| leather_boots | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| leather_hat | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
| leather_legs_armor | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
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
| mushmush_wizard_hat | 15 | 18/10 PASS · 18/15 CB · 20/10 PASS · 20/15 CB · 22/10 PASS · 22/15 CB |
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
| gold_helm | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| gold_mask | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| gold_platebody | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| gold_platelegs | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_shield | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| lizard_boots | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| lizard_skin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| lizard_skin_legs_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| obsidian_armor | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| obsidian_helmet | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| obsidian_legs_armor | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| piggy_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| piggy_helmet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| piggy_pants | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| royal_skeleton_armor | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| royal_skeleton_helmet | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| royal_skeleton_pants | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| snakeskin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| snakeskin_legs_armor | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| stormforged_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| stormforged_pants | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |

## gearcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_shield | 40 | 38/35 PASS · 38/40 EG · 40/35 PASS · 40/40 EG · 42/35 PASS · 42/40 EG |
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
| dreadful_shield | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| earth_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| enchanter_boots | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| enchanter_pants | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| fire_shield | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| hork_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| jester_hat | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| malefic_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| mithril_boots | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_helm | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_platebody | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_platelegs | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_shield | 40 | 38/35 PASS · 38/40 EG · 40/35 PASS · 40/40 EG · 42/35 PASS · 42/40 EG |
| strangold_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| strangold_helmet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| strangold_legs_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| water_shield | 40 | 38/35 PASS · 38/40 EG · 40/35 PASS · 40/40 EG · 42/35 PASS · 42/40 EG |
| white_knight_armor | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| white_knight_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| white_knight_pants | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| white_knight_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| wratharmor | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| wrathelmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| wrathpants | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |

## gearcrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
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
| iron_ring | 10 | 8/5 PASS · 8/10 CB · 10/5 PASS · 10/10 CB · 12/5 PASS · 12/10 CB |
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
| emerald_amulet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| emerald_ring | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_ring | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| greater_dreadful_amulet | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| lost_amulet | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| prospecting_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| royal_skeleton_ring | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| ruby_amulet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| ruby_ring | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| sapphire_amulet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| sapphire_ring | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| topaz_amulet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |
| topaz_ring | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |

## jewelrycrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| ancestral_talisman | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| celest_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| corrupted_stone_amulet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| diamond_amulet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| divinity_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| eternity_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| greater_emerald_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| greater_ruby_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| greater_sapphire_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| greater_topaz_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| malefic_ring | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| masterful_necklace | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| mithril_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| sacred_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |

## jewelrycrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| dust_amulet | 50 | 48/45 PASS · 48/50 EG · 50/45 PASS · 50/50 EG |
| eternal_red_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| heart_amulet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |
| hell_ring | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG |
| skullforged_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG |

## mining — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| copper_bar | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| iron_bar | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |

## mining — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| emerald | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| ruby | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| sapphire | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| steel_bar | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| topaz | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |

## mining — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| gold_bar | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| obsidian_bar | 30 | 28/25 PASS · 28/30 CB · 30/25 PASS · 30/30 CB · 32/25 PASS · 32/30 CB |

## mining — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| diamond | 35 | 38/30 PASS · 38/35 EG · 40/30 PASS · 40/35 EG · 42/30 PASS · 42/35 EG |
| mithril_bar | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| strangold_bar | 35 | 38/30 PASS · 38/35 EG · 40/30 PASS · 40/35 EG · 42/30 PASS · 42/35 EG |

## mining — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_bar | 50 | 48/45 PASS · 48/50 PASS · 50/45 PASS · 50/50 PASS |
| alexandrite | 50 | 48/45 PASS · 48/50 EG · 50/45 PASS · 50/50 EG |

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
| iron_axe | 10 | 8/5 PR · 8/10 PR · 10/5 PR · 10/10 PR · 12/5 PR · 12/10 PR |
| iron_dagger | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_pickaxe | 10 | 8/5 PR · 8/10 PR · 10/5 PR · 10/10 PR · 12/5 PR · 12/10 PR |
| iron_sword | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_gloves | 10 | 8/5 CB · 8/10 CB · 10/5 CB · 10/10 CB · 12/5 CB · 12/10 CB |
| spruce_fishing_rod | 10 | 8/5 PR · 8/10 PR · 10/5 PR · 10/10 PR · 12/5 PR · 12/10 PR |
| sticky_dagger | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| sticky_sword | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| water_bow | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 CB · 12/5 CB |
| wooden_staff | 1 | 1/1 MU · 8/1 MU · 12/1 MU |

## weaponcrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| battlestaff | 20 | 18/15 PASS · 18/20 CB · 20/15 PASS · 20/20 CB · 22/15 PASS · 22/20 CB |
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
| elderwood_staff | 30 | 28/25 PASS · 28/30 EG · 30/25 PASS · 30/30 EG · 32/25 PASS · 32/30 EG |
| gold_axe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_fishing_rod | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_pickaxe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| gold_sword | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| golden_gloves | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG |
| greater_dreadful_staff | 30 | 28/25 CB · 28/30 CB · 30/25 CB · 30/30 CB · 32/25 CB · 32/30 CB |
| obsidian_battleaxe | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| perfect_bow | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| skull_wand | 25 | 28/20 CB · 28/25 CB · 30/20 CB · 30/25 CB · 32/20 CB · 32/25 CB |
| vampire_bow | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG |

## weaponcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| bloodblade | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| cursed_sceptre | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| diamond_sword | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| dreadful_battleaxe | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| lightning_sword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| magic_bow | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| mithril_axe | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_fishing_rod | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| mithril_gloves | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_pickaxe | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| mithril_sword | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |
| strangold_sword | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG |
| wrathsword | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG |

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
| spruce_plank | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |

## woodcutting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| hardwood_plank | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |

## woodcutting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| dead_wood_plank | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| sap | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |

## woodcutting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cursed_plank | 35 | 38/30 PASS · 38/35 CB · 40/30 PASS · 40/35 CB · 42/30 PASS · 42/35 CB |
| magic_sap | 35 | 38/30 PASS · 38/35 EG · 40/30 PASS · 40/35 EG · 42/30 PASS · 42/35 EG |
| magical_plank | 35 | 38/30 PASS · 38/35 EG · 40/30 PASS · 40/35 EG · 42/30 PASS · 42/35 EG |
| maple_plank | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| maple_sap | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## woodcutting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| palm_plank | 50 | 48/45 PASS · 48/50 PASS · 50/45 PASS · 50/50 PASS |

