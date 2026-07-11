# Craft-Planning Completeness — PLANNER_BUG Backlog

> GENERATED — do not hand-edit. Regenerate with `uv run python scripts/gen_craft_completeness.py`.
>
> Census drives the REAL planner over the committed bundle. Cells whose plan hits the 10 s wall-clock budget (~16% of cells) can vary between regens; treat their verdict as approximate.


321 recipes, 1758 cells; PASS 120 (7%); nominal-at-skill PASS 41/321; gaps: event_gated 518, combat_blocked 878, material_unreachable 3, skill_unreachable 0, planner_bug 239

| Rank | Recipe | Skill | Craft lvl | # bug cells | Cells | Reason |
|---|---|---|---|---|---|---|
| 1 | cooked_shrimp | cooking | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 2 | iron_axe | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 3 | iron_boots | gearcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 4 | iron_dagger | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 5 | iron_pickaxe | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 6 | iron_sword | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 7 | spruce_fishing_rod | weaponcrafting | 10 | 6 | 8/5, 8/10, 10/5, 10/10, 12/5, 12/10 | empty |
| 8 | cooked_trout | cooking | 20 | 6 | 18/15, 18/20, 20/15, 20/20, 22/15, 22/20 | empty |
| 9 | forest_bank_potion | alchemy | 20 | 6 | 18/15, 18/20, 20/15, 20/20, 22/15, 22/20 | empty |
| 10 | antidote | alchemy | 30 | 6 | 28/25, 28/30, 30/25, 30/30, 32/25, 32/30 | empty |
| 11 | cooked_bass | cooking | 30 | 6 | 28/25, 28/30, 30/25, 30/30, 32/25, 32/30 | empty |
| 12 | diamond | mining | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 13 | magic_sap | woodcutting | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 14 | magical_plank | woodcutting | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 15 | strangold_bar | mining | 35 | 6 | 38/30, 38/35, 40/30, 40/35, 42/30, 42/35 | empty |
| 16 | air_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 17 | cooked_salmon | cooking | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 18 | earth_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 19 | enchanted_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 20 | fire_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 21 | maple_syrup | cooking | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 22 | water_res_potion | alchemy | 40 | 6 | 38/35, 38/40, 40/35, 40/40, 42/35, 42/40 | empty |
| 23 | enhanced_health_potion | alchemy | 45 | 4 | 48/40, 48/45, 50/40, 50/45 | empty |
| 24 | alexandrite | mining | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 25 | cooked_swordfish | cooking | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 26 | enhanced_health_splash_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 27 | lava_underground_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 28 | sandwhisper_potion | alchemy | 50 | 4 | 48/45, 48/50, 50/45, 50/50 | empty |
| 29 | copper_legs_armor | gearcrafting | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 30 | feather_coat | gearcrafting | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 31 | fried_eggs | cooking | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 32 | recall_potion | alchemy | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 33 | small_health_potion | alchemy | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 34 | sticky_sword | weaponcrafting | 5 | 3 | 1/1, 8/1, 12/1 | empty |
| 35 | earth_boost_potion | alchemy | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 36 | iron_bar | mining | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 37 | spruce_plank | woodcutting | 10 | 3 | 8/5, 10/5, 12/5 | empty |
| 38 | apple_pie | cooking | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 39 | emerald | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 40 | hardwood_plank | woodcutting | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 41 | minor_health_potion | alchemy | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 42 | ruby | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 43 | sapphire | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 44 | steel_bar | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 45 | topaz | mining | 20 | 3 | 18/15, 20/15, 22/15 | empty |
| 46 | dead_wood_plank | woodcutting | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 47 | gold_bar | mining | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 48 | health_potion | alchemy | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 49 | health_splash_potion | alchemy | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 50 | sap | woodcutting | 30 | 3 | 28/25, 30/25, 32/25 | empty |
| 51 | greater_health_potion | alchemy | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 52 | maple_plank | woodcutting | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 53 | maple_sap | woodcutting | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 54 | mithril_bar | mining | 40 | 3 | 38/35, 40/35, 42/35 | empty |
| 55 | adamantite_bar | mining | 50 | 2 | 48/45, 50/45 | empty |
| 56 | palm_plank | woodcutting | 50 | 2 | 48/45, 50/45 | empty |
| 57 | cooked_chicken | cooking | 1 | 1 | 12/1 | empty |
