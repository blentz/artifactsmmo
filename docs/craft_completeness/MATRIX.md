# Craft-Planning Completeness — Matrix

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 2418 cells; PASS 642 (27%); recipes PASS 133/321; nominal-at-skill PASS 122/321; gaps: event_gated 660, combat_blocked 894, material_unreachable 187, skill_unreachable 0, grey_farm_suppressed 1, purchase_recursion 0, crossing_unaffordable 34, planner_bug 0

Legend: EG=event_gated, CB=combat_blocked, MU=material_unreachable, SU=skill_unreachable, GF=grey_farm_suppressed, PR=purchase_recursion, XU=crossing_unaffordable, PB=planner_bug; +ev = the cell with the recipe's sourcing events active.

## alchemy — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_boost_potion | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| earth_boost_potion | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| fire_boost_potion | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| recall_potion | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| small_health_potion | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| water_boost_potion | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |

## alchemy — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| forest_bank_potion | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| minor_health_potion | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| small_antidote | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |

## alchemy — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| antidote | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev PASS · 28/30+ev PASS · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| health_potion | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| health_splash_potion | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |

## alchemy — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| earth_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| enchanted_potion | 40 | 38/35 XU · 38/40 XU · 40/35 XU · 40/40 XU · 42/35 XU · 42/40 XU |
| enhanced_boost_potion | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev XU · 42/35+ev CB · 42/40+ev XU |
| fire_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| greater_health_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| health_boost_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| water_res_potion | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## alchemy — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| enhanced_antidote | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev XU · 50/40+ev CB · 50/45+ev XU |
| enhanced_health_potion | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev XU · 48/45+ev XU · 50/40+ev XU · 50/45+ev XU |
| enhanced_health_splash_potion | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev XU · 48/50+ev XU · 50/45+ev XU · 50/50+ev XU |
| lava_underground_potion | 50 | 48/45 XU · 48/50 XU · 50/45 XU · 50/50 XU |
| sandwhisper_potion | 50 | 48/45 XU · 48/50 XU · 50/45 XU · 50/50 XU |

## cooking — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cheese | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| cooked_beef | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 PASS · 12/5 PASS |
| cooked_chicken | 1 | 1/1 PASS · 8/1 PASS · 12/1 GF |
| cooked_gudgeon | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| cooked_shrimp | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| cookie | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| fried_eggs | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |

## cooking — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| apple_pie | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| cooked_porkchop | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| cooked_trout | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| cooked_wolf_meat | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| mushroom_soup | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |

## cooking — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_bass | 30 | 28/25 PASS · 28/30 PASS · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| cooked_rat_meat | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |

## cooking — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_hellhound_meat | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| cooked_salmon | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| fish_soup | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| maple_syrup | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## cooking — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| cooked_desert_scorpion_meat | 50 | 48/45 CB · 48/50 CB · 50/45 CB · 50/50 CB |
| cooked_swordfish | 50 | 48/45 PASS · 48/50 XU · 50/45 PASS · 50/50 XU |

## gearcrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adventurer_helmet | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| adventurer_vest | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| copper_armor | 5 | 1/1 CB · 1/5 CB · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| copper_boots | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_helmet | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_legs_armor | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| feather_coat | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| iron_armor | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_boots | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_helm | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_legs_armor | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_shield | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_armor | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_boots | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_hat | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_legs_armor | 10 | 8/5 CB · 8/10 CB · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| satchel | 5 | 1/1 CB · 1/5 CB · 8/1 CB · 8/5 CB · 12/1 MU · 12/5 MU |
| wooden_shield | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |

## gearcrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adventurer_boots | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| adventurer_pants | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| hard_leather_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hard_leather_boots | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| hard_leather_helmet | 20 | 18/15 MU · 18/20 MU · 20/15 MU · 20/20 MU · 22/15 MU · 22/20 MU |
| hard_leather_pants | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| lucky_wizard_hat | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| magic_wizard_hat | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| mushmush_jacket | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| mushmush_wizard_hat | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| skeleton_armor | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| skeleton_helmet | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| skeleton_pants | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| slime_shield | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| snakeskin_boots | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_boots | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_helm | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_legs_armor | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| tromatising_mask | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |

## gearcrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| conjurer_cloak | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| conjurer_skirt | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| flying_boots | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| gold_boots | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev MU · 30/30+ev MU · 32/25+ev MU · 32/30+ev MU |
| gold_helm | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| gold_mask | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| gold_platebody | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev PASS · 32/30+ev PASS |
| gold_platelegs | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| gold_shield | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| lizard_boots | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev MU · 30/30+ev MU · 32/25+ev MU · 32/30+ev MU |
| lizard_skin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |
| lizard_skin_legs_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |
| obsidian_armor | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| obsidian_helmet | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| obsidian_legs_armor | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| piggy_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |
| piggy_helmet | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev PASS · 30/25+ev PASS · 32/20+ev PASS · 32/25+ev PASS |
| piggy_pants | 25 | 28/20 MU · 28/25 MU · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| royal_skeleton_armor | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| royal_skeleton_helmet | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| royal_skeleton_pants | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| snakeskin_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |
| snakeskin_legs_armor | 25 | 28/20 PASS · 28/25 PASS · 30/20 PASS · 30/25 PASS · 32/20 PASS · 32/25 PASS |
| stormforged_armor | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |
| stormforged_pants | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |

## gearcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| ancient_jean | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| batwing_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| cultist_boots | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| cultist_cloak | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| cultist_hat | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| cultist_pants | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| cursed_hat | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| diamond_armor | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| diamond_skirt | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| dreadful_armor | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| dreadful_shield | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| earth_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| enchanter_boots | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| enchanter_pants | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| fire_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| hork_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| jester_hat | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| malefic_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| mithril_boots | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| mithril_helm | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| mithril_platebody | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| mithril_platelegs | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev PASS · 38/40+ev PASS · 40/35+ev PASS · 40/40+ev PASS · 42/35+ev PASS · 42/40+ev PASS |
| mithril_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| strangold_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| strangold_helmet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev MU · 38/35+ev MU · 40/30+ev MU · 40/35+ev MU · 42/30+ev MU · 42/35+ev MU |
| strangold_legs_armor | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| water_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| white_knight_armor | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_helmet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| white_knight_pants | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| white_knight_shield | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| wratharmor | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| wrathelmet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| wrathpants | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |

## gearcrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_mask | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_platebody | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_platelegs | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| dark_horned_helmet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| darkforged_boots | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| darkforged_helmet | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| darkforged_plate | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| darkforged_shield | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| demoniac_shield | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| duskarmor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| duskpants | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| dust_helmet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| hell_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| hell_helmet | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| hell_legs_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| magic_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| medic_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| medic_skirt | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| mesh_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| mesh_legs_armor | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| red_dragon_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| red_dragon_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| red_dragon_legs_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| red_dragon_shield | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| sand_snakeskin_armor | 45 | 48/40 CB · 48/45 CB · 50/40 CB · 50/45 CB |
| sand_snakeskin_bandana | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| sand_snakeskin_boots | 45 | 48/40 CB · 48/45 CB · 50/40 CB · 50/45 CB |
| sand_snakeskin_pants | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| skullforged_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| skullforged_pants | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| vital_armor | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| vital_boots | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |

## jewelrycrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_and_water_amulet | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| copper_ring | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| fire_and_earth_amulet | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_ring | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| life_amulet | 5 | 1/1 CB · 1/5 CB · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |

## jewelrycrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| air_ring | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| dreadful_amulet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| dreadful_ring | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| earth_ring | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| fire_ring | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| life_ring | 15 | 18/10 PASS · 18/15 PASS · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| ring_of_chance | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_amulet | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_ring | 20 | 18/15 CB · 18/20 CB · 20/15 MU · 20/20 MU · 22/15 MU · 22/20 MU |
| steel_ring | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| water_ring | 15 | 18/10 CB · 18/15 CB · 20/10 PASS · 20/15 PASS · 22/10 PASS · 22/15 PASS |
| wisdom_amulet | 15 | 18/10 CB · 18/15 CB · 20/10 MU · 20/15 MU · 22/10 MU · 22/15 MU |

## jewelrycrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| emerald_amulet | 25 | 28/20 MU · 28/25 MU · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| emerald_ring | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| gold_ring | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| greater_dreadful_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| lost_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| prospecting_amulet | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| royal_skeleton_ring | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |
| ruby_amulet | 25 | 28/20 MU · 28/25 MU · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| ruby_ring | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| sapphire_amulet | 25 | 28/20 MU · 28/25 MU · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| sapphire_ring | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| topaz_amulet | 25 | 28/20 MU · 28/25 MU · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| topaz_ring | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |

## jewelrycrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| ancestral_talisman | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| celest_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| corrupted_stone_amulet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| diamond_amulet | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| divinity_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| eternity_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| greater_emerald_amulet | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| greater_ruby_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| greater_sapphire_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| greater_topaz_amulet | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| malefic_ring | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev MU · 40/35+ev MU · 42/30+ev MU · 42/35+ev MU |
| masterful_necklace | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| mithril_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |
| sacred_ring | 40 | 38/35 EG · 38/40 EG · 40/35 EG · 40/40 EG · 42/35 EG · 42/40 EG · 38/35+ev CB · 38/40+ev CB · 40/35+ev CB · 40/40+ev CB · 42/35+ev CB · 42/40+ev CB |

## jewelrycrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| dust_amulet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| eternal_red_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| heart_amulet | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| hell_ring | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| skullforged_ring | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |

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
| obsidian_bar | 30 | 28/25 CB · 28/30 CB · 30/25 PASS · 30/30 PASS · 32/25 PASS · 32/30 PASS |

## mining — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| diamond | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev PASS · 38/35+ev PASS · 40/30+ev PASS · 40/35+ev PASS · 42/30+ev PASS · 42/35+ev PASS |
| mithril_bar | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| strangold_bar | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev PASS · 38/35+ev PASS · 40/30+ev PASS · 40/35+ev PASS · 42/30+ev PASS · 42/35+ev PASS |

## mining — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_bar | 50 | 48/45 PASS · 48/50 XU · 50/45 PASS · 50/50 XU |
| alexandrite | 50 | 48/45 PASS · 48/50 XU · 50/45 PASS · 50/50 XU |

## weaponcrafting — tier 1

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| apprentice_gloves | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_axe | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_dagger | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| copper_pickaxe | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| fire_bow | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| fire_staff | 5 | 1/1 CB · 1/5 CB · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| fishing_net | 1 | 1/1 PASS · 8/1 PASS · 12/1 PASS |
| greater_wooden_staff | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_axe | 10 | 8/5 MU · 8/10 MU · 10/5 MU · 10/10 MU · 12/5 MU · 12/10 MU |
| iron_dagger | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| iron_pickaxe | 10 | 8/5 MU · 8/10 MU · 10/5 MU · 10/10 MU · 12/5 MU · 12/10 MU |
| iron_sword | 10 | 8/5 PASS · 8/10 PASS · 10/5 PASS · 10/10 PASS · 12/5 PASS · 12/10 PASS |
| leather_gloves | 10 | 8/5 CB · 8/10 CB · 10/5 MU · 10/10 MU · 12/5 MU · 12/10 MU |
| spruce_fishing_rod | 10 | 8/5 MU · 8/10 MU · 10/5 MU · 10/10 MU · 12/5 MU · 12/10 MU |
| sticky_dagger | 5 | 1/1 CB · 1/5 CB · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| sticky_sword | 5 | 1/1 PASS · 1/5 PASS · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| water_bow | 5 | 1/1 CB · 1/5 CB · 8/1 PASS · 8/5 PASS · 12/1 PASS · 12/5 PASS |
| wooden_staff | 1 | 1/1 MU · 8/1 MU · 12/1 MU |

## weaponcrafting — tier 2

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| battlestaff | 20 | 18/15 PASS · 18/20 PASS · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| forest_whip | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| hunting_bow | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| king_slime_sword | 15 | 18/10 CB · 18/15 CB · 20/10 CB · 20/15 CB · 22/10 CB · 22/15 CB |
| mushmush_bow | 15 | 18/10 MU · 18/15 MU · 20/10 MU · 20/15 MU · 22/10 MU · 22/15 MU |
| mushstaff | 15 | 18/10 MU · 18/15 MU · 20/10 MU · 20/15 MU · 22/10 MU · 22/15 MU |
| shuriken | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| skull_staff | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| steel_axe | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_battleaxe | 20 | 18/15 CB · 18/20 CB · 20/15 PASS · 20/20 PASS · 22/15 PASS · 22/20 PASS |
| steel_fishing_rod | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |
| steel_gloves | 20 | 18/15 CB · 18/20 CB · 20/15 MU · 20/20 MU · 22/15 MU · 22/20 MU |
| steel_pickaxe | 20 | 18/15 CB · 18/20 CB · 20/15 CB · 20/20 CB · 22/15 CB · 22/20 CB |

## weaponcrafting — tier 3

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| dreadful_staff | 25 | 28/20 CB · 28/25 CB · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| elderwood_staff | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| gold_axe | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| gold_fishing_rod | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| gold_pickaxe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| gold_sword | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| golden_gloves | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| greater_dreadful_staff | 30 | 28/25 CB · 28/30 CB · 30/25 MU · 30/30 MU · 32/25 MU · 32/30 MU |
| obsidian_battleaxe | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev PASS · 30/30+ev PASS · 32/25+ev PASS · 32/30+ev PASS |
| perfect_bow | 30 | 28/25 EG · 28/30 EG · 30/25 EG · 30/30 EG · 32/25 EG · 32/30 EG · 28/25+ev CB · 28/30+ev CB · 30/25+ev CB · 30/30+ev CB · 32/25+ev CB · 32/30+ev CB |
| skull_wand | 25 | 28/20 CB · 28/25 CB · 30/20 MU · 30/25 MU · 32/20 MU · 32/25 MU |
| vampire_bow | 25 | 28/20 EG · 28/25 EG · 30/20 EG · 30/25 EG · 32/20 EG · 32/25 EG · 28/20+ev CB · 28/25+ev CB · 30/20+ev MU · 30/25+ev MU · 32/20+ev MU · 32/25+ev MU |

## weaponcrafting — tier 4

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| bloodblade | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| cursed_sceptre | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| diamond_sword | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| dreadful_battleaxe | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| lightning_sword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| magic_bow | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev MU · 38/35+ev MU · 40/30+ev MU · 40/35+ev MU · 42/30+ev MU · 42/35+ev MU |
| mithril_axe | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_fishing_rod | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_gloves | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_pickaxe | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| mithril_sword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |
| strangold_sword | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev CB · 38/35+ev CB · 40/30+ev CB · 40/35+ev CB · 42/30+ev CB · 42/35+ev CB |
| wrathsword | 40 | 38/35 CB · 38/40 CB · 40/35 CB · 40/40 CB · 42/35 CB · 42/40 CB |

## weaponcrafting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| adamantite_axe | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_fishing_rod | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_gloves | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_pickaxe | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| adamantite_sword | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| blade_of_hell | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| bow_from_hell | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| demoniac_dagger | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| desert_whip | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| dust_sword | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |
| hell_reaper | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| hell_staff | 45 | 48/40 EG · 48/45 EG · 50/40 EG · 50/45 EG · 48/40+ev CB · 48/45+ev CB · 50/40+ev CB · 50/45+ev CB |
| moonlight_staff | 50 | 48/45 EG · 48/50 EG · 50/45 EG · 50/50 EG · 48/45+ev CB · 48/50+ev CB · 50/45+ev CB · 50/50+ev CB |

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
| cursed_plank | 35 | 38/30 CB · 38/35 CB · 40/30 CB · 40/35 CB · 42/30 CB · 42/35 CB |
| magic_sap | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev PASS · 38/35+ev PASS · 40/30+ev PASS · 40/35+ev PASS · 42/30+ev PASS · 42/35+ev PASS |
| magical_plank | 35 | 38/30 EG · 38/35 EG · 40/30 EG · 40/35 EG · 42/30 EG · 42/35 EG · 38/30+ev PASS · 38/35+ev PASS · 40/30+ev PASS · 40/35+ev PASS · 42/30+ev PASS · 42/35+ev PASS |
| maple_plank | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |
| maple_sap | 40 | 38/35 PASS · 38/40 PASS · 40/35 PASS · 40/40 PASS · 42/35 PASS · 42/40 PASS |

## woodcutting — tier 5

| Recipe | Craft lvl | Cells (char/skill → verdict) |
|---|---|---|
| palm_plank | 50 | 48/45 PASS · 48/50 XU · 50/45 PASS · 50/50 XU |

