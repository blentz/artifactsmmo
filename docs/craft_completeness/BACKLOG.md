# Craft-Planning Completeness — PLANNER_BUG Backlog

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 1758 cells; PASS 106 (6%); nominal-at-skill PASS 35/321; gaps: event_gated 518, combat_blocked 878, material_unreachable 3, skill_unreachable 0, planner_bug 253

| Rank | Recipe | Skill | Craft lvl | # bug cells | Cells | Reason |
|---|---|---|---|---|---|---|
| 1 | copper_legs_armor | gearcrafting | 5 | 6 | 1/1, 1/5, 8/1, 8/5, 12/1, 12/5 | empty |
| 2 | feather_coat | gearcrafting | 5 | 6 | 1/1, 1/5, 8/1, 8/5, 12/1, 12/5 | empty |
| 3 | sticky_sword | weaponcrafting | 5 | 6 | 1/1, 1/5, 8/1, 8/5, 12/1, 12/5 | empty |
| 4 | cooked_shrimp | cooking | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 5 | iron_axe | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 6 | iron_boots | gearcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 7 | iron_dagger | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 8 | iron_pickaxe | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 9 | iron_sword | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 10 | spruce_fishing_rod | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 11 | cooked_trout | cooking | 20 | 6 | 18/15, 18/20, 20/15, 20/20, 22/15, 22/20 | empty |
| 12 | forest_bank_potion | alchemy | 20 | 6 | 18/15, 18/20, 20/15, 20/20, 22/15, 22/20 | empty |
| 13 | antidote | alchemy | 30 | 6 | 28/25, 28/30, 30/25, 30/30, 32/25, 32/30 | empty |
| 14 | cooked_bass | cooking | 30 | 6 | 28/25, 28/30, 30/25, 30/30, 32/25, 32/30 | empty |
| 15 | gold_bar | mining | 30 | 6 | 28/25, 28/30, 30/25, 30/30, 32/25, 32/30 | empty |
| 16 | diamond | mining | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 17 | magic_sap | woodcutting | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 18 | magical_plank | woodcutting | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 19 | strangold_bar | mining | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 20 | air_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 21 | cooked_salmon | cooking | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 22 | earth_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 23 | enchanted_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 24 | fire_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 25 | maple_syrup | cooking | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 26 | mithril_bar | mining | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 27 | water_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 28 | enhanced_health_potion | alchemy | 45 | 4 | 48/40, 48/45, 50/40, 50/45 | empty |
| 29 | adamantite_bar | mining | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 30 | alexandrite | mining | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 31 | cooked_swordfish | cooking | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 32 | enhanced_health_splash_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 33 | lava_underground_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 34 | sandwhisper_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 35 | fried_eggs | cooking | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 36 | recall_potion | alchemy | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 37 | small_health_potion | alchemy | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 38 | earth_boost_potion | alchemy | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 39 | iron_bar | mining | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 40 | spruce_plank | woodcutting | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 41 | apple_pie | cooking | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 42 | emerald | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 43 | hardwood_plank | woodcutting | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 44 | minor_health_potion | alchemy | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 45 | ruby | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 46 | sapphire | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 47 | steel_bar | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 48 | topaz | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 49 | dead_wood_plank | woodcutting | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 50 | health_potion | alchemy | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 51 | health_splash_potion | alchemy | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 52 | greater_health_potion | alchemy | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 53 | maple_plank | woodcutting | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 54 | maple_sap | woodcutting | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 55 | palm_plank | woodcutting | 50 | 2 | 48/45, 50/45 | empty |
| 56 | cooked_chicken | cooking | 1 | 1 | 12/1 | empty |
