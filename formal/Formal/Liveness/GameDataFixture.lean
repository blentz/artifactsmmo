import Formal.Liveness.CatalogTypes
import Formal.Liveness.RecipeChainClosure
import Formal.Liveness.SkillGapClosure
import Formal.Liveness.TaskCompleteReachable
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Mathlib.Tactic

/-! # GameDataFixture — Phase 24 LIVE SNAPSHOT

  Captured: 2026-07-04T22:06:10.738986+00:00
  API: https://api.artifactsmmo.com
  Counts: 58 monsters, 522 items, 321 recipes, 26 resources.

  Generated from formal/sim/game_data_snapshot.json by
  formal/sim/generate_lean_fixture.py. Regenerate after
  snapshot_game_data.py captures a new snapshot.

  Recipe `craftDepth` field computed by topological sort over
  ingredient DAG (production game-data guarantees acyclicity).
  Leaves (no crafting_recipes entry) get depth 0; crafts get
  max(ingredient depths) + 1.

  This fixture instantiates Phase 23d-8's universal
  recipe_then_complete_reachable theorem against LIVE data.
  NO new axioms; pure structural data + instantiation. -/

set_option maxRecDepth 8192

namespace Formal.Liveness.GameDataFixture

open Formal.Liveness
open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable
open Formal.Liveness.SkillGapClosure
open Formal.Liveness.RecipeChainClosure

/-- Snapshot timestamp (UTC ISO 8601). -/
def snapshotCapturedAt : String := "2026-07-04T22:06:10.738986+00:00"

/-- Snapshot API base URL. -/
def snapshotApiBaseUrl : String := "https://api.artifactsmmo.com"

/-! ## Live recipes (sorted by output code) -/

/-- Recipe for `adamantite_axe` (craftDepth 2). -/
def recipe_adamantite_axe : Recipe :=
  { output := "adamantite_axe"
    ingredients := [("adamantite_bar", 10), ("adventurer_skull", 3), ("astralyte_crystal", 2), ("cursed_flask", 3), ("golden_dust", 4), ("lava_bucket", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_bar` (craftDepth 1). -/
def recipe_adamantite_bar : Recipe :=
  { output := "adamantite_bar"
    ingredients := [("adamantite_ore", 10)]
    craftDepth := 1 }

/-- Recipe for `adamantite_boots` (craftDepth 2). -/
def recipe_adamantite_boots : Recipe :=
  { output := "adamantite_boots"
    ingredients := [("adamantite_bar", 12), ("diamond", 1), ("dusk_beetle_shell", 4), ("golden_dust", 3), ("prime_fabric", 2), ("wolfrider_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_fishing_rod` (craftDepth 2). -/
def recipe_adamantite_fishing_rod : Recipe :=
  { output := "adamantite_fishing_rod"
    ingredients := [("adamantite_bar", 5), ("astralyte_crystal", 2), ("cursed_flask", 3), ("cursed_plank", 3), ("lava_bucket", 4), ("palm_plank", 5), ("solar_desert_scorpion_tail", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_gloves` (craftDepth 2). -/
def recipe_adamantite_gloves : Recipe :=
  { output := "adamantite_gloves"
    ingredients := [("adamantite_bar", 10), ("astralyte_crystal", 3), ("desert_scorpion_carapace", 4), ("efreet_cloth", 4), ("goblin_guard_foot", 4), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `adamantite_mask` (craftDepth 2). -/
def recipe_adamantite_mask : Recipe :=
  { output := "adamantite_mask"
    ingredients := [("adamantite_bar", 12), ("alexandrite", 1), ("cursed_book", 5), ("duskworm_skin", 3), ("jasper_crystal", 2), ("solar_desert_scorpion_tail", 3)]
    craftDepth := 2 }

/-- Recipe for `adamantite_pickaxe` (craftDepth 2). -/
def recipe_adamantite_pickaxe : Recipe :=
  { output := "adamantite_pickaxe"
    ingredients := [("adamantite_bar", 10), ("astralyte_crystal", 2), ("broken_sword", 2), ("dark_essence", 4), ("efreet_cloth", 4), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_platebody` (craftDepth 2). -/
def recipe_adamantite_platebody : Recipe :=
  { output := "adamantite_platebody"
    ingredients := [("adamantite_bar", 12), ("adventurer_skull", 3), ("desert_scorpion_carapace", 3), ("golden_dust", 4), ("malefic_cloth", 3), ("prime_fabric", 2)]
    craftDepth := 2 }

/-- Recipe for `adamantite_platelegs` (craftDepth 2). -/
def recipe_adamantite_platelegs : Recipe :=
  { output := "adamantite_platelegs"
    ingredients := [("adamantite_bar", 12), ("duskworm_skin", 3), ("golden_dust", 3), ("marauder_hand", 3), ("prime_fabric", 2), ("sand_snakeskin", 3)]
    craftDepth := 2 }

/-- Recipe for `adamantite_ring` (craftDepth 2). -/
def recipe_adamantite_ring : Recipe :=
  { output := "adamantite_ring"
    ingredients := [("adamantite_bar", 12), ("corrupted_stone", 3), ("desert_scorpion_carapace", 2), ("duskworm_skin", 3), ("golden_dust", 3), ("sand_snakeskin", 3)]
    craftDepth := 2 }

/-- Recipe for `adamantite_shield` (craftDepth 2). -/
def recipe_adamantite_shield : Recipe :=
  { output := "adamantite_shield"
    ingredients := [("adamantite_bar", 12), ("adventurer_skull", 3), ("bat_wing", 3), ("dusk_beetle_shell", 3), ("hellhound_collar", 3), ("jasper_crystal", 2)]
    craftDepth := 2 }

/-- Recipe for `adamantite_sword` (craftDepth 2). -/
def recipe_adamantite_sword : Recipe :=
  { output := "adamantite_sword"
    ingredients := [("adamantite_bar", 12), ("adventurer_skull", 3), ("bat_wing", 3), ("broken_sword", 2), ("dusk_beetle_shell", 3), ("marauder_hand", 3)]
    craftDepth := 2 }

/-- Recipe for `adventurer_boots` (craftDepth 2). -/
def recipe_adventurer_boots : Recipe :=
  { output := "adventurer_boots"
    ingredients := [("mushroom", 5), ("spruce_plank", 5), ("wolf_hair", 5)]
    craftDepth := 2 }

/-- Recipe for `adventurer_helmet` (craftDepth 2). -/
def recipe_adventurer_helmet : Recipe :=
  { output := "adventurer_helmet"
    ingredients := [("cowhide", 3), ("feather", 4), ("mushroom", 4), ("spruce_plank", 3)]
    craftDepth := 2 }

/-- Recipe for `adventurer_pants` (craftDepth 2). -/
def recipe_adventurer_pants : Recipe :=
  { output := "adventurer_pants"
    ingredients := [("ash_plank", 7), ("cloth", 2), ("green_cloth", 3), ("hard_leather", 3)]
    craftDepth := 2 }

/-- Recipe for `adventurer_vest` (craftDepth 2). -/
def recipe_adventurer_vest : Recipe :=
  { output := "adventurer_vest"
    ingredients := [("cowhide", 6), ("spruce_plank", 4), ("wool", 2), ("yellow_slimeball", 4)]
    craftDepth := 2 }

/-- Recipe for `air_and_water_amulet` (craftDepth 2). -/
def recipe_air_and_water_amulet : Recipe :=
  { output := "air_and_water_amulet"
    ingredients := [("blue_slimeball", 2), ("green_slimeball", 2), ("iron_bar", 4)]
    craftDepth := 2 }

/-- Recipe for `air_boost_potion` (craftDepth 1). -/
def recipe_air_boost_potion : Recipe :=
  { output := "air_boost_potion"
    ingredients := [("algae", 1), ("green_slimeball", 1), ("sunflower", 1)]
    craftDepth := 1 }

/-- Recipe for `air_res_potion` (craftDepth 2). -/
def recipe_air_res_potion : Recipe :=
  { output := "air_res_potion"
    ingredients := [("glowstem_leaf", 1), ("green_slimeball", 2), ("maple_sap", 1)]
    craftDepth := 2 }

/-- Recipe for `air_ring` (craftDepth 2). -/
def recipe_air_ring : Recipe :=
  { output := "air_ring"
    ingredients := [("flying_wing", 3), ("green_slimeball", 4), ("iron_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `air_shield` (craftDepth 2). -/
def recipe_air_shield : Recipe :=
  { output := "air_shield"
    ingredients := [("emerald", 1), ("green_slimeball", 20), ("rosenblood_elixir", 1), ("strangold_bar", 6), ("wolfrider_ponytail", 5)]
    craftDepth := 2 }

/-- Recipe for `alexandrite` (craftDepth 1). -/
def recipe_alexandrite : Recipe :=
  { output := "alexandrite"
    ingredients := [("alexandrite_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `ancestral_talisman` (craftDepth 2). -/
def recipe_ancestral_talisman : Recipe :=
  { output := "ancestral_talisman"
    ingredients := [("cursed_book", 4), ("diamond", 1), ("goblin_tooth", 5), ("magical_plank", 8), ("priestess_orb", 2)]
    craftDepth := 2 }

/-- Recipe for `ancient_jean` (craftDepth 2). -/
def recipe_ancient_jean : Recipe :=
  { output := "ancient_jean"
    ingredients := [("goblin_guard_foot", 3), ("lizard_skin", 5), ("magical_cure", 2), ("magical_plank", 6), ("obsidian_bar", 4)]
    craftDepth := 2 }

/-- Recipe for `antidote` (craftDepth 2). -/
def recipe_antidote : Recipe :=
  { output := "antidote"
    ingredients := [("glowstem_leaf", 1), ("maple_sap", 1), ("strangold_bar", 2)]
    craftDepth := 2 }

/-- Recipe for `apple_pie` (craftDepth 1). -/
def recipe_apple_pie : Recipe :=
  { output := "apple_pie"
    ingredients := [("apple", 2), ("egg", 1)]
    craftDepth := 1 }

/-- Recipe for `apprentice_gloves` (craftDepth 1). -/
def recipe_apprentice_gloves : Recipe :=
  { output := "apprentice_gloves"
    ingredients := [("feather", 6)]
    craftDepth := 1 }

/-- Recipe for `ash_plank` (craftDepth 1). -/
def recipe_ash_plank : Recipe :=
  { output := "ash_plank"
    ingredients := [("ash_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `battlestaff` (craftDepth 2). -/
def recipe_battlestaff : Recipe :=
  { output := "battlestaff"
    ingredients := [("blue_slimeball", 5), ("hardwood_plank", 6), ("steel_bar", 4), ("wolf_bone", 3)]
    craftDepth := 2 }

/-- Recipe for `batwing_helmet` (craftDepth 2). -/
def recipe_batwing_helmet : Recipe :=
  { output := "batwing_helmet"
    ingredients := [("bat_wing", 5), ("echoless_bat_wing", 5), ("prime_fabric", 2), ("rosenblood_elixir", 1), ("strangold_bar", 6), ("topaz", 1)]
    craftDepth := 2 }

/-- Recipe for `blade_of_hell` (craftDepth 2). -/
def recipe_blade_of_hell : Recipe :=
  { output := "blade_of_hell"
    ingredients := [("book_from_hell", 1), ("broken_sword", 2), ("fire_crystal", 1), ("lava_bucket", 3), ("orc_bone", 6), ("strangold_bar", 11)]
    craftDepth := 2 }

/-- Recipe for `bloodblade` (craftDepth 2). -/
def recipe_bloodblade : Recipe :=
  { output := "bloodblade"
    ingredients := [("astralyte_crystal", 2), ("bat_heart", 4), ("broken_sword", 1), ("goblin_tooth", 5), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `bow_from_hell` (craftDepth 2). -/
def recipe_bow_from_hell : Recipe :=
  { output := "bow_from_hell"
    ingredients := [("book_from_hell", 1), ("demon_horn", 3), ("efreet_cloth", 3), ("fire_crystal", 1), ("imp_tail", 5), ("magical_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `celest_ring` (craftDepth 2). -/
def recipe_celest_ring : Recipe :=
  { output := "celest_ring"
    ingredients := [("astralyte_crystal", 2), ("rosenblood_elixir", 1), ("ruby", 2), ("sapphire", 2), ("strangold_bar", 9), ("wolfrider_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `cheese` (craftDepth 1). -/
def recipe_cheese : Recipe :=
  { output := "cheese"
    ingredients := [("milk_bucket", 1)]
    craftDepth := 1 }

/-- Recipe for `conjurer_cloak` (craftDepth 2). -/
def recipe_conjurer_cloak : Recipe :=
  { output := "conjurer_cloak"
    ingredients := [("cyclops_eye", 5), ("demon_horn", 4), ("obsidian_bar", 6), ("owlbear_hair", 4), ("prime_fabric", 1)]
    craftDepth := 2 }

/-- Recipe for `conjurer_skirt` (craftDepth 2). -/
def recipe_conjurer_skirt : Recipe :=
  { output := "conjurer_skirt"
    ingredients := [("full_moon_vampire_cape", 4), ("obsidian_bar", 6), ("owlbear_claw", 3), ("vampire_tooth", 4), ("vermin_leather", 3)]
    craftDepth := 2 }

/-- Recipe for `cooked_bass` (craftDepth 1). -/
def recipe_cooked_bass : Recipe :=
  { output := "cooked_bass"
    ingredients := [("bass", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_beef` (craftDepth 1). -/
def recipe_cooked_beef : Recipe :=
  { output := "cooked_beef"
    ingredients := [("raw_beef", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_chicken` (craftDepth 1). -/
def recipe_cooked_chicken : Recipe :=
  { output := "cooked_chicken"
    ingredients := [("raw_chicken", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_desert_scorpion_meat` (craftDepth 1). -/
def recipe_cooked_desert_scorpion_meat : Recipe :=
  { output := "cooked_desert_scorpion_meat"
    ingredients := [("desert_scorpion_meat", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_gudgeon` (craftDepth 1). -/
def recipe_cooked_gudgeon : Recipe :=
  { output := "cooked_gudgeon"
    ingredients := [("gudgeon", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_hellhound_meat` (craftDepth 1). -/
def recipe_cooked_hellhound_meat : Recipe :=
  { output := "cooked_hellhound_meat"
    ingredients := [("raw_hellhound_meat", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_porkchop` (craftDepth 1). -/
def recipe_cooked_porkchop : Recipe :=
  { output := "cooked_porkchop"
    ingredients := [("raw_porkchop", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_rat_meat` (craftDepth 1). -/
def recipe_cooked_rat_meat : Recipe :=
  { output := "cooked_rat_meat"
    ingredients := [("raw_rat_meat", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_salmon` (craftDepth 1). -/
def recipe_cooked_salmon : Recipe :=
  { output := "cooked_salmon"
    ingredients := [("salmon", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_shrimp` (craftDepth 1). -/
def recipe_cooked_shrimp : Recipe :=
  { output := "cooked_shrimp"
    ingredients := [("shrimp", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_swordfish` (craftDepth 1). -/
def recipe_cooked_swordfish : Recipe :=
  { output := "cooked_swordfish"
    ingredients := [("swordfish", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_trout` (craftDepth 1). -/
def recipe_cooked_trout : Recipe :=
  { output := "cooked_trout"
    ingredients := [("trout", 1)]
    craftDepth := 1 }

/-- Recipe for `cooked_wolf_meat` (craftDepth 1). -/
def recipe_cooked_wolf_meat : Recipe :=
  { output := "cooked_wolf_meat"
    ingredients := [("raw_wolf_meat", 1)]
    craftDepth := 1 }

/-- Recipe for `cookie` (craftDepth 1). -/
def recipe_cookie : Recipe :=
  { output := "cookie"
    ingredients := [("egg", 1), ("milk_bucket", 1)]
    craftDepth := 1 }

/-- Recipe for `copper_armor` (craftDepth 2). -/
def recipe_copper_armor : Recipe :=
  { output := "copper_armor"
    ingredients := [("copper_bar", 5), ("wool", 2)]
    craftDepth := 2 }

/-- Recipe for `copper_axe` (craftDepth 2). -/
def recipe_copper_axe : Recipe :=
  { output := "copper_axe"
    ingredients := [("copper_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `copper_bar` (craftDepth 1). -/
def recipe_copper_bar : Recipe :=
  { output := "copper_bar"
    ingredients := [("copper_ore", 10)]
    craftDepth := 1 }

/-- Recipe for `copper_boots` (craftDepth 2). -/
def recipe_copper_boots : Recipe :=
  { output := "copper_boots"
    ingredients := [("copper_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `copper_dagger` (craftDepth 2). -/
def recipe_copper_dagger : Recipe :=
  { output := "copper_dagger"
    ingredients := [("copper_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `copper_helmet` (craftDepth 2). -/
def recipe_copper_helmet : Recipe :=
  { output := "copper_helmet"
    ingredients := [("copper_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `copper_legs_armor` (craftDepth 2). -/
def recipe_copper_legs_armor : Recipe :=
  { output := "copper_legs_armor"
    ingredients := [("copper_bar", 5), ("feather", 2)]
    craftDepth := 2 }

/-- Recipe for `copper_pickaxe` (craftDepth 2). -/
def recipe_copper_pickaxe : Recipe :=
  { output := "copper_pickaxe"
    ingredients := [("copper_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `copper_ring` (craftDepth 2). -/
def recipe_copper_ring : Recipe :=
  { output := "copper_ring"
    ingredients := [("copper_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `corrupted_stone_amulet` (craftDepth 2). -/
def recipe_corrupted_stone_amulet : Recipe :=
  { output := "corrupted_stone_amulet"
    ingredients := [("corrupted_stone", 5), ("magical_cure", 2), ("malefic_cloth", 2), ("orc_bone", 5), ("strangold_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `cultist_boots` (craftDepth 2). -/
def recipe_cultist_boots : Recipe :=
  { output := "cultist_boots"
    ingredients := [("enchanted_fabric", 2), ("hellhound_hair", 4), ("malefic_cloth", 2), ("maple_plank", 7), ("orc_bone", 5)]
    craftDepth := 2 }

/-- Recipe for `cultist_cloak` (craftDepth 2). -/
def recipe_cultist_cloak : Recipe :=
  { output := "cultist_cloak"
    ingredients := [("enchanted_fabric", 2), ("hellhound_collar", 4), ("malefic_cloth", 2), ("maple_plank", 8), ("red_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `cultist_hat` (craftDepth 2). -/
def recipe_cultist_hat : Recipe :=
  { output := "cultist_hat"
    ingredients := [("astralyte_crystal", 2), ("bat_heart", 4), ("malefic_cloth", 1), ("maple_plank", 8), ("orc_skin", 5)]
    craftDepth := 2 }

/-- Recipe for `cultist_pants` (craftDepth 2). -/
def recipe_cultist_pants : Recipe :=
  { output := "cultist_pants"
    ingredients := [("cursed_plank", 8), ("hellhound_hair", 3), ("magical_cure", 4), ("malefic_cloth", 2), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `cursed_hat` (craftDepth 2). -/
def recipe_cursed_hat : Recipe :=
  { output := "cursed_hat"
    ingredients := [("cursed_book", 4), ("cursed_plank", 8), ("diamond", 1), ("malefic_cloth", 2), ("owlbear_hair", 4), ("prime_fabric", 1)]
    craftDepth := 2 }

/-- Recipe for `cursed_plank` (craftDepth 1). -/
def recipe_cursed_plank : Recipe :=
  { output := "cursed_plank"
    ingredients := [("cursed_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `cursed_sceptre` (craftDepth 2). -/
def recipe_cursed_sceptre : Recipe :=
  { output := "cursed_sceptre"
    ingredients := [("corrupted_stone", 3), ("cursed_book", 3), ("diamond", 1), ("magical_cure", 2), ("magical_plank", 8), ("malefic_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `dark_horned_helmet` (craftDepth 2). -/
def recipe_dark_horned_helmet : Recipe :=
  { output := "dark_horned_helmet"
    ingredients := [("duskworm_skin", 2), ("jasper_crystal", 3), ("palm_plank", 10), ("sand_snake_poison", 3), ("sand_snakeskin", 2), ("solar_desert_scorpion_tail", 4), ("topaz", 2)]
    craftDepth := 2 }

/-- Recipe for `darkforged_boots` (craftDepth 2). -/
def recipe_darkforged_boots : Recipe :=
  { output := "darkforged_boots"
    ingredients := [("astralyte_crystal", 3), ("bat_heart", 2), ("dark_essence", 5), ("lava_bucket", 4), ("maple_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `darkforged_helmet` (craftDepth 2). -/
def recipe_darkforged_helmet : Recipe :=
  { output := "darkforged_helmet"
    ingredients := [("dark_essence", 5), ("grimlet_bone", 4), ("marauder_hand", 2), ("mithril_bar", 10), ("prime_fabric", 3)]
    craftDepth := 2 }

/-- Recipe for `darkforged_plate` (craftDepth 2). -/
def recipe_darkforged_plate : Recipe :=
  { output := "darkforged_plate"
    ingredients := [("cursed_plank", 10), ("echoless_bat_wing", 5), ("grimlet_bone", 4), ("rosenblood_elixir", 1), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `darkforged_shield` (craftDepth 2). -/
def recipe_darkforged_shield : Recipe :=
  { output := "darkforged_shield"
    ingredients := [("bat_wing", 5), ("cursed_plank", 10), ("diamond", 1), ("enchanted_fabric", 3), ("marauder_hand", 5)]
    craftDepth := 2 }

/-- Recipe for `dead_wood_plank` (craftDepth 1). -/
def recipe_dead_wood_plank : Recipe :=
  { output := "dead_wood_plank"
    ingredients := [("dead_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `demoniac_dagger` (craftDepth 2). -/
def recipe_demoniac_dagger : Recipe :=
  { output := "demoniac_dagger"
    ingredients := [("book_from_hell", 1), ("cursed_book", 5), ("efreet_cloth", 3), ("obsidian_bar", 5), ("strangold_bar", 10)]
    craftDepth := 2 }

/-- Recipe for `demoniac_shield` (craftDepth 2). -/
def recipe_demoniac_shield : Recipe :=
  { output := "demoniac_shield"
    ingredients := [("bat_wing", 4), ("book_from_hell", 1), ("cursed_plank", 10), ("goblin_tooth", 6), ("grimlet_bone", 3)]
    craftDepth := 2 }

/-- Recipe for `desert_whip` (craftDepth 2). -/
def recipe_desert_whip : Recipe :=
  { output := "desert_whip"
    ingredients := [("desert_scorpion_carapace", 3), ("duskworm_skin", 3), ("efreet_cloth", 3), ("palm_plank", 12), ("sand_snake_poison", 3), ("solar_desert_scorpion_tail", 2)]
    craftDepth := 2 }

/-- Recipe for `diamond` (craftDepth 1). -/
def recipe_diamond : Recipe :=
  { output := "diamond"
    ingredients := [("diamond_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `diamond_amulet` (craftDepth 2). -/
def recipe_diamond_amulet : Recipe :=
  { output := "diamond_amulet"
    ingredients := [("cursed_book", 4), ("diamond", 1), ("magical_cure", 2), ("magical_plank", 8), ("obsidian_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `diamond_armor` (craftDepth 2). -/
def recipe_diamond_armor : Recipe :=
  { output := "diamond_armor"
    ingredients := [("diamond", 8), ("echoless_bat_wing", 4), ("enchanted_fabric", 5), ("prime_fabric", 2), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `diamond_skirt` (craftDepth 2). -/
def recipe_diamond_skirt : Recipe :=
  { output := "diamond_skirt"
    ingredients := [("bat_heart", 3), ("diamond", 8), ("dryad_hair", 4), ("enchanted_fabric", 4), ("full_moon_vampire_cape", 3)]
    craftDepth := 2 }

/-- Recipe for `diamond_sword` (craftDepth 2). -/
def recipe_diamond_sword : Recipe :=
  { output := "diamond_sword"
    ingredients := [("corrupted_stone", 3), ("diamond", 1), ("goblin_eye", 3), ("magical_cure", 2), ("magical_plank", 7), ("spider_leg", 3)]
    craftDepth := 2 }

/-- Recipe for `divinity_ring` (craftDepth 2). -/
def recipe_divinity_ring : Recipe :=
  { output := "divinity_ring"
    ingredients := [("astralyte_crystal", 2), ("hellhound_collar", 4), ("rosenblood_elixir", 1), ("sapphire", 2), ("strangold_bar", 9), ("topaz", 2)]
    craftDepth := 2 }

/-- Recipe for `dreadful_amulet` (craftDepth 2). -/
def recipe_dreadful_amulet : Recipe :=
  { output := "dreadful_amulet"
    ingredients := [("hard_leather", 2), ("hardwood_plank", 6), ("king_slimeball", 2), ("ogre_eye", 4)]
    craftDepth := 2 }

/-- Recipe for `dreadful_armor` (craftDepth 2). -/
def recipe_dreadful_armor : Recipe :=
  { output := "dreadful_armor"
    ingredients := [("goblin_guard_foot", 4), ("obsidian_bar", 8), ("ogre_eye", 5), ("priestess_orb", 2), ("prime_fabric", 1)]
    craftDepth := 2 }

/-- Recipe for `dreadful_battleaxe` (craftDepth 2). -/
def recipe_dreadful_battleaxe : Recipe :=
  { output := "dreadful_battleaxe"
    ingredients := [("goblin_eye", 3), ("goblin_guard_foot", 3), ("jasper_crystal", 3), ("lizard_eye", 4), ("magical_plank", 7)]
    craftDepth := 2 }

/-- Recipe for `dreadful_ring` (craftDepth 2). -/
def recipe_dreadful_ring : Recipe :=
  { output := "dreadful_ring"
    ingredients := [("cyclops_eye", 3), ("jasper_crystal", 1), ("ogre_eye", 4), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `dreadful_shield` (craftDepth 2). -/
def recipe_dreadful_shield : Recipe :=
  { output := "dreadful_shield"
    ingredients := [("astralyte_crystal", 1), ("cursed_book", 5), ("imp_tail", 5), ("obsidian_bar", 8), ("ruby", 1)]
    craftDepth := 2 }

/-- Recipe for `dreadful_staff` (craftDepth 2). -/
def recipe_dreadful_staff : Recipe :=
  { output := "dreadful_staff"
    ingredients := [("cyclops_eye", 4), ("hardwood_plank", 6), ("jasper_crystal", 1), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `duskarmor` (craftDepth 2). -/
def recipe_duskarmor : Recipe :=
  { output := "duskarmor"
    ingredients := [("adamantite_bar", 10), ("dusk_beetle_shell", 3), ("duskworm_skin", 3), ("enchanted_fabric", 1), ("orc_skin", 4), ("prime_fabric", 3), ("sapphire", 2)]
    craftDepth := 2 }

/-- Recipe for `duskpants` (craftDepth 2). -/
def recipe_duskpants : Recipe :=
  { output := "duskpants"
    ingredients := [("dusk_beetle_shell", 3), ("duskworm_skin", 4), ("goblin_guard_foot", 4), ("palm_plank", 10), ("priestess_orb", 2), ("prime_fabric", 3)]
    craftDepth := 2 }

/-- Recipe for `dust_amulet` (craftDepth 2). -/
def recipe_dust_amulet : Recipe :=
  { output := "dust_amulet"
    ingredients := [("adamantite_bar", 10), ("alexandrite", 1), ("dark_essence", 4), ("demoniac_dust", 3), ("duskworm_skin", 2), ("fennec_ear", 2), ("golden_dust", 4)]
    craftDepth := 2 }

/-- Recipe for `dust_helmet` (craftDepth 2). -/
def recipe_dust_helmet : Recipe :=
  { output := "dust_helmet"
    ingredients := [("adventurer_skull", 3), ("astralyte_crystal", 2), ("desert_scorpion_carapace", 4), ("fire_crystal", 1), ("golden_dust", 4), ("palm_plank", 12)]
    craftDepth := 2 }

/-- Recipe for `dust_sword` (craftDepth 2). -/
def recipe_dust_sword : Recipe :=
  { output := "dust_sword"
    ingredients := [("adamantite_bar", 10), ("adventurer_skull", 3), ("broken_sword", 2), ("cursed_flask", 3), ("golden_dust", 4), ("marauder_hand", 4)]
    craftDepth := 2 }

/-- Recipe for `earth_boost_potion` (craftDepth 1). -/
def recipe_earth_boost_potion : Recipe :=
  { output := "earth_boost_potion"
    ingredients := [("algae", 1), ("sunflower", 1), ("yellow_slimeball", 1)]
    craftDepth := 1 }

/-- Recipe for `earth_res_potion` (craftDepth 2). -/
def recipe_earth_res_potion : Recipe :=
  { output := "earth_res_potion"
    ingredients := [("glowstem_leaf", 1), ("maple_sap", 1), ("yellow_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `earth_ring` (craftDepth 2). -/
def recipe_earth_ring : Recipe :=
  { output := "earth_ring"
    ingredients := [("flying_wing", 3), ("iron_bar", 5), ("yellow_slimeball", 4)]
    craftDepth := 2 }

/-- Recipe for `earth_shield` (craftDepth 2). -/
def recipe_earth_shield : Recipe :=
  { output := "earth_shield"
    ingredients := [("bat_wing", 3), ("rosenblood_elixir", 1), ("strangold_bar", 6), ("topaz", 1), ("yellow_slimeball", 20)]
    craftDepth := 2 }

/-- Recipe for `elderwood_staff` (craftDepth 2). -/
def recipe_elderwood_staff : Recipe :=
  { output := "elderwood_staff"
    ingredients := [("cyclops_eye", 5), ("dead_wood_plank", 5), ("lizard_skin", 4), ("red_cloth", 3), ("skeleton_skull", 3)]
    craftDepth := 2 }

/-- Recipe for `emerald` (craftDepth 1). -/
def recipe_emerald : Recipe :=
  { output := "emerald"
    ingredients := [("emerald_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `emerald_amulet` (craftDepth 2). -/
def recipe_emerald_amulet : Recipe :=
  { output := "emerald_amulet"
    ingredients := [("emerald", 1), ("hardwood_plank", 8), ("jasper_crystal", 2), ("snake_hide", 5)]
    craftDepth := 2 }

/-- Recipe for `emerald_ring` (craftDepth 2). -/
def recipe_emerald_ring : Recipe :=
  { output := "emerald_ring"
    ingredients := [("emerald", 1), ("gold_bar", 8), ("magical_cure", 2), ("obsidian_bar", 4), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `enchanted_potion` (craftDepth 1). -/
def recipe_enchanted_potion : Recipe :=
  { output := "enchanted_potion"
    ingredients := [("enchanted_mushroom", 1), ("salmon", 1)]
    craftDepth := 1 }

/-- Recipe for `enchanter_boots` (craftDepth 2). -/
def recipe_enchanter_boots : Recipe :=
  { output := "enchanter_boots"
    ingredients := [("lizard_eye", 4), ("magical_plank", 8), ("priestess_orb", 2), ("prime_fabric", 1), ("vermin_leather", 5)]
    craftDepth := 2 }

/-- Recipe for `enchanter_pants` (craftDepth 2). -/
def recipe_enchanter_pants : Recipe :=
  { output := "enchanter_pants"
    ingredients := [("cursed_book", 3), ("demon_horn", 2), ("full_moon_vampire_cape", 2), ("magical_plank", 8), ("owlbear_claw", 4), ("prime_fabric", 1)]
    craftDepth := 2 }

/-- Recipe for `enhanced_antidote` (craftDepth 2). -/
def recipe_enhanced_antidote : Recipe :=
  { output := "enhanced_antidote"
    ingredients := [("magic_sap", 1), ("sand_snake_poison", 1), ("strangold_bar", 2), ("torch_cactus_flower", 1)]
    craftDepth := 2 }

/-- Recipe for `enhanced_boost_potion` (craftDepth 2). -/
def recipe_enhanced_boost_potion : Recipe :=
  { output := "enhanced_boost_potion"
    ingredients := [("bat_wing", 1), ("enchanted_mushroom", 1), ("glowstem_leaf", 2), ("magic_sap", 1)]
    craftDepth := 2 }

/-- Recipe for `enhanced_health_potion` (craftDepth 2). -/
def recipe_enhanced_health_potion : Recipe :=
  { output := "enhanced_health_potion"
    ingredients := [("egg", 1), ("enchanted_mushroom", 1), ("glowstem_leaf", 2), ("magic_sap", 1)]
    craftDepth := 2 }

/-- Recipe for `enhanced_health_splash_potion` (craftDepth 2). -/
def recipe_enhanced_health_splash_potion : Recipe :=
  { output := "enhanced_health_splash_potion"
    ingredients := [("coconut", 1), ("lava_fish", 1), ("magic_sap", 1), ("torch_cactus_flower", 1)]
    craftDepth := 2 }

/-- Recipe for `eternal_red_ring` (craftDepth 2). -/
def recipe_eternal_red_ring : Recipe :=
  { output := "eternal_red_ring"
    ingredients := [("adamantite_bar", 12), ("alexandrite", 1), ("desert_scorpion_carapace", 2), ("duskworm_skin", 3), ("fennec_ear", 4), ("fennec_tail", 1), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `eternity_ring` (craftDepth 2). -/
def recipe_eternity_ring : Recipe :=
  { output := "eternity_ring"
    ingredients := [("astralyte_crystal", 2), ("emerald", 2), ("rosenblood_elixir", 1), ("strangold_bar", 9), ("topaz", 2), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `feather_coat` (craftDepth 2). -/
def recipe_feather_coat : Recipe :=
  { output := "feather_coat"
    ingredients := [("ash_plank", 2), ("feather", 5)]
    craftDepth := 2 }

/-- Recipe for `fire_and_earth_amulet` (craftDepth 2). -/
def recipe_fire_and_earth_amulet : Recipe :=
  { output := "fire_and_earth_amulet"
    ingredients := [("iron_bar", 4), ("red_slimeball", 2), ("yellow_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `fire_boost_potion` (craftDepth 1). -/
def recipe_fire_boost_potion : Recipe :=
  { output := "fire_boost_potion"
    ingredients := [("algae", 1), ("red_slimeball", 1), ("sunflower", 1)]
    craftDepth := 1 }

/-- Recipe for `fire_bow` (craftDepth 2). -/
def recipe_fire_bow : Recipe :=
  { output := "fire_bow"
    ingredients := [("red_slimeball", 2), ("spruce_plank", 6)]
    craftDepth := 2 }

/-- Recipe for `fire_res_potion` (craftDepth 2). -/
def recipe_fire_res_potion : Recipe :=
  { output := "fire_res_potion"
    ingredients := [("glowstem_leaf", 1), ("maple_sap", 1), ("red_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `fire_ring` (craftDepth 2). -/
def recipe_fire_ring : Recipe :=
  { output := "fire_ring"
    ingredients := [("flying_wing", 3), ("iron_bar", 5), ("red_slimeball", 4)]
    craftDepth := 2 }

/-- Recipe for `fire_shield` (craftDepth 2). -/
def recipe_fire_shield : Recipe :=
  { output := "fire_shield"
    ingredients := [("orc_skin", 5), ("red_slimeball", 20), ("rosenblood_elixir", 1), ("ruby", 1), ("strangold_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `fire_staff` (craftDepth 2). -/
def recipe_fire_staff : Recipe :=
  { output := "fire_staff"
    ingredients := [("ash_plank", 5), ("red_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `fish_soup` (craftDepth 1). -/
def recipe_fish_soup : Recipe :=
  { output := "fish_soup"
    ingredients := [("milk_bucket", 1), ("salmon", 1), ("trout", 1)]
    craftDepth := 1 }

/-- Recipe for `fishing_net` (craftDepth 2). -/
def recipe_fishing_net : Recipe :=
  { output := "fishing_net"
    ingredients := [("ash_plank", 6)]
    craftDepth := 2 }

/-- Recipe for `flying_boots` (craftDepth 2). -/
def recipe_flying_boots : Recipe :=
  { output := "flying_boots"
    ingredients := [("dead_wood_plank", 8), ("demoniac_dust", 5), ("hard_leather", 3), ("magical_cure", 1), ("owlbear_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `forest_bank_potion` (craftDepth 1). -/
def recipe_forest_bank_potion : Recipe :=
  { output := "forest_bank_potion"
    ingredients := [("nettle_leaf", 1), ("trout", 1)]
    craftDepth := 1 }

/-- Recipe for `forest_whip` (craftDepth 2). -/
def recipe_forest_whip : Recipe :=
  { output := "forest_whip"
    ingredients := [("hardwood_plank", 4), ("king_slimeball", 2), ("ogre_eye", 4), ("wolf_hair", 5)]
    craftDepth := 2 }

/-- Recipe for `fried_eggs` (craftDepth 1). -/
def recipe_fried_eggs : Recipe :=
  { output := "fried_eggs"
    ingredients := [("egg", 2)]
    craftDepth := 1 }

/-- Recipe for `gold_axe` (craftDepth 2). -/
def recipe_gold_axe : Recipe :=
  { output := "gold_axe"
    ingredients := [("dead_wood_plank", 2), ("gold_bar", 7), ("magical_cure", 2), ("red_cloth", 3), ("ruby", 1)]
    craftDepth := 2 }

/-- Recipe for `gold_bar` (craftDepth 1). -/
def recipe_gold_bar : Recipe :=
  { output := "gold_bar"
    ingredients := [("gold_ore", 10)]
    craftDepth := 1 }

/-- Recipe for `gold_boots` (craftDepth 2). -/
def recipe_gold_boots : Recipe :=
  { output := "gold_boots"
    ingredients := [("gold_bar", 8), ("lizard_eye", 3), ("magical_cure", 1), ("owlbear_hair", 4), ("vampire_blood", 4)]
    craftDepth := 2 }

/-- Recipe for `gold_fishing_rod` (craftDepth 2). -/
def recipe_gold_fishing_rod : Recipe :=
  { output := "gold_fishing_rod"
    ingredients := [("dead_wood_plank", 2), ("gold_bar", 7), ("magical_cure", 2), ("owlbear_claw", 3), ("sapphire", 1)]
    craftDepth := 2 }

/-- Recipe for `gold_helm` (craftDepth 2). -/
def recipe_gold_helm : Recipe :=
  { output := "gold_helm"
    ingredients := [("demon_horn", 2), ("gold_bar", 8), ("imp_tail", 3), ("owlbear_hair", 4), ("vampire_tooth", 3)]
    craftDepth := 2 }

/-- Recipe for `gold_mask` (craftDepth 2). -/
def recipe_gold_mask : Recipe :=
  { output := "gold_mask"
    ingredients := [("demon_horn", 2), ("gold_bar", 8), ("owlbear_claw", 4), ("red_cloth", 2), ("skeleton_skull", 4)]
    craftDepth := 2 }

/-- Recipe for `gold_pickaxe` (craftDepth 2). -/
def recipe_gold_pickaxe : Recipe :=
  { output := "gold_pickaxe"
    ingredients := [("dead_wood_plank", 2), ("demon_horn", 2), ("gold_bar", 7), ("magical_cure", 2), ("topaz", 1)]
    craftDepth := 2 }

/-- Recipe for `gold_platebody` (craftDepth 2). -/
def recipe_gold_platebody : Recipe :=
  { output := "gold_platebody"
    ingredients := [("demon_horn", 2), ("demoniac_dust", 4), ("full_moon_vampire_cape", 3), ("gold_bar", 8), ("red_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `gold_platelegs` (craftDepth 2). -/
def recipe_gold_platelegs : Recipe :=
  { output := "gold_platelegs"
    ingredients := [("gold_bar", 8), ("lizard_eye", 3), ("ogre_skin", 2), ("vampire_tooth", 4), ("vermin_leather", 3)]
    craftDepth := 2 }

/-- Recipe for `gold_ring` (craftDepth 2). -/
def recipe_gold_ring : Recipe :=
  { output := "gold_ring"
    ingredients := [("dead_wood_plank", 3), ("gold_bar", 8), ("skeleton_bone", 3), ("vampire_blood", 3), ("wolf_bone", 3)]
    craftDepth := 2 }

/-- Recipe for `gold_shield` (craftDepth 2). -/
def recipe_gold_shield : Recipe :=
  { output := "gold_shield"
    ingredients := [("dead_wood_plank", 7), ("demon_horn", 4), ("gold_bar", 7), ("magical_cure", 1), ("sapphire", 1)]
    craftDepth := 2 }

/-- Recipe for `gold_sword` (craftDepth 2). -/
def recipe_gold_sword : Recipe :=
  { output := "gold_sword"
    ingredients := [("dead_wood_plank", 3), ("demon_horn", 2), ("gold_bar", 8), ("imp_tail", 4), ("red_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `golden_gloves` (craftDepth 2). -/
def recipe_golden_gloves : Recipe :=
  { output := "golden_gloves"
    ingredients := [("dead_wood_plank", 7), ("demoniac_dust", 3), ("emerald", 1), ("magical_cure", 2), ("obsidian_bar", 2)]
    craftDepth := 2 }

/-- Recipe for `greater_dreadful_amulet` (craftDepth 3). -/
def recipe_greater_dreadful_amulet : Recipe :=
  { output := "greater_dreadful_amulet"
    ingredients := [("cyclops_eye", 4), ("dreadful_amulet", 1), ("gold_bar", 8), ("ogre_eye", 4), ("red_cloth", 3)]
    craftDepth := 3 }

/-- Recipe for `greater_dreadful_staff` (craftDepth 3). -/
def recipe_greater_dreadful_staff : Recipe :=
  { output := "greater_dreadful_staff"
    ingredients := [("cyclops_eye", 5), ("dead_wood_plank", 5), ("dreadful_staff", 1), ("ogre_eye", 4), ("red_cloth", 3)]
    craftDepth := 3 }

/-- Recipe for `greater_emerald_amulet` (craftDepth 3). -/
def recipe_greater_emerald_amulet : Recipe :=
  { output := "greater_emerald_amulet"
    ingredients := [("astralyte_crystal", 2), ("echoless_bat_wing", 6), ("emerald", 2), ("emerald_amulet", 1), ("maple_plank", 8)]
    craftDepth := 3 }

/-- Recipe for `greater_health_potion` (craftDepth 1). -/
def recipe_greater_health_potion : Recipe :=
  { output := "greater_health_potion"
    ingredients := [("algae", 1), ("egg", 1), ("glowstem_leaf", 2)]
    craftDepth := 1 }

/-- Recipe for `greater_ruby_amulet` (craftDepth 3). -/
def recipe_greater_ruby_amulet : Recipe :=
  { output := "greater_ruby_amulet"
    ingredients := [("astralyte_crystal", 2), ("hellhound_collar", 6), ("maple_plank", 8), ("ruby", 2), ("ruby_amulet", 1)]
    craftDepth := 3 }

/-- Recipe for `greater_sapphire_amulet` (craftDepth 3). -/
def recipe_greater_sapphire_amulet : Recipe :=
  { output := "greater_sapphire_amulet"
    ingredients := [("astralyte_crystal", 2), ("cursed_flask", 6), ("maple_plank", 8), ("sapphire", 2), ("sapphire_amulet", 1)]
    craftDepth := 3 }

/-- Recipe for `greater_topaz_amulet` (craftDepth 3). -/
def recipe_greater_topaz_amulet : Recipe :=
  { output := "greater_topaz_amulet"
    ingredients := [("astralyte_crystal", 2), ("hellhound_collar", 6), ("maple_plank", 8), ("topaz", 2), ("topaz_amulet", 1)]
    craftDepth := 3 }

/-- Recipe for `greater_wooden_staff` (craftDepth 2). -/
def recipe_greater_wooden_staff : Recipe :=
  { output := "greater_wooden_staff"
    ingredients := [("blue_slimeball", 2), ("spruce_plank", 6)]
    craftDepth := 2 }

/-- Recipe for `hard_leather_armor` (craftDepth 2). -/
def recipe_hard_leather_armor : Recipe :=
  { output := "hard_leather_armor"
    ingredients := [("hard_leather", 6), ("pig_skin", 2), ("spider_leg", 3), ("steel_bar", 4)]
    craftDepth := 2 }

/-- Recipe for `hard_leather_boots` (craftDepth 2). -/
def recipe_hard_leather_boots : Recipe :=
  { output := "hard_leather_boots"
    ingredients := [("green_cloth", 2), ("hard_leather", 3), ("hardwood_plank", 5), ("pig_skin", 5)]
    craftDepth := 2 }

/-- Recipe for `hard_leather_helmet` (craftDepth 2). -/
def recipe_hard_leather_helmet : Recipe :=
  { output := "hard_leather_helmet"
    ingredients := [("astralyte_crystal", 1), ("hard_leather", 4), ("hardwood_plank", 7), ("wolf_bone", 2)]
    craftDepth := 2 }

/-- Recipe for `hard_leather_pants` (craftDepth 2). -/
def recipe_hard_leather_pants : Recipe :=
  { output := "hard_leather_pants"
    ingredients := [("green_cloth", 2), ("hard_leather", 5), ("skeleton_skull", 2), ("steel_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `hardwood_plank` (craftDepth 1). -/
def recipe_hardwood_plank : Recipe :=
  { output := "hardwood_plank"
    ingredients := [("ash_wood", 4), ("birch_wood", 6)]
    craftDepth := 1 }

/-- Recipe for `health_boost_potion` (craftDepth 2). -/
def recipe_health_boost_potion : Recipe :=
  { output := "health_boost_potion"
    ingredients := [("milk_bucket", 1), ("nettle_leaf", 2), ("sap", 1)]
    craftDepth := 2 }

/-- Recipe for `health_potion` (craftDepth 2). -/
def recipe_health_potion : Recipe :=
  { output := "health_potion"
    ingredients := [("egg", 1), ("nettle_leaf", 2), ("sap", 1)]
    craftDepth := 2 }

/-- Recipe for `health_splash_potion` (craftDepth 1). -/
def recipe_health_splash_potion : Recipe :=
  { output := "health_splash_potion"
    ingredients := [("algae", 1), ("nettle_leaf", 2), ("sunflower", 1)]
    craftDepth := 1 }

/-- Recipe for `heart_amulet` (craftDepth 2). -/
def recipe_heart_amulet : Recipe :=
  { output := "heart_amulet"
    ingredients := [("corrupted_stone", 3), ("duskworm_skin", 3), ("goblin_eye", 2), ("golden_dust", 3), ("grimlet_bone", 3), ("palm_plank", 12)]
    craftDepth := 2 }

/-- Recipe for `hell_armor` (craftDepth 2). -/
def recipe_hell_armor : Recipe :=
  { output := "hell_armor"
    ingredients := [("book_from_hell", 1), ("cursed_plank", 10), ("demon_horn", 5), ("efreet_cloth", 3), ("fire_crystal", 1), ("grimlet_bone", 3), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `hell_helmet` (craftDepth 2). -/
def recipe_hell_helmet : Recipe :=
  { output := "hell_helmet"
    ingredients := [("lava_bucket", 5), ("maple_plank", 10), ("orc_skin", 4), ("prime_fabric", 3), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `hell_legs_armor` (craftDepth 2). -/
def recipe_hell_legs_armor : Recipe :=
  { output := "hell_legs_armor"
    ingredients := [("grimlet_bone", 4), ("hellhound_collar", 4), ("lava_bucket", 4), ("malefic_cloth", 2), ("maple_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `hell_reaper` (craftDepth 2). -/
def recipe_hell_reaper : Recipe :=
  { output := "hell_reaper"
    ingredients := [("book_from_hell", 1), ("broken_sword", 3), ("efreet_cloth", 4), ("grimlet_bone", 5), ("mithril_bar", 11)]
    craftDepth := 2 }

/-- Recipe for `hell_ring` (craftDepth 2). -/
def recipe_hell_ring : Recipe :=
  { output := "hell_ring"
    ingredients := [("bat_heart", 5), ("book_from_hell", 1), ("diamond", 2), ("efreet_cloth", 2), ("grimlet_bone", 4), ("strangold_bar", 10)]
    craftDepth := 2 }

/-- Recipe for `hell_staff` (craftDepth 2). -/
def recipe_hell_staff : Recipe :=
  { output := "hell_staff"
    ingredients := [("book_from_hell", 1), ("cursed_plank", 10), ("efreet_cloth", 2), ("imp_tail", 5), ("obsidian_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `hork_helmet` (craftDepth 2). -/
def recipe_hork_helmet : Recipe :=
  { output := "hork_helmet"
    ingredients := [("bat_wing", 3), ("dryad_hair", 3), ("echoless_bat_wing", 3), ("orc_skin", 4), ("strangold_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `hunting_bow` (craftDepth 2). -/
def recipe_hunting_bow : Recipe :=
  { output := "hunting_bow"
    ingredients := [("green_cloth", 4), ("hardwood_plank", 5), ("ogre_skin", 3), ("pig_skin", 3)]
    craftDepth := 2 }

/-- Recipe for `iron_armor` (craftDepth 2). -/
def recipe_iron_armor : Recipe :=
  { output := "iron_armor"
    ingredients := [("cowhide", 3), ("iron_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `iron_axe` (craftDepth 2). -/
def recipe_iron_axe : Recipe :=
  { output := "iron_axe"
    ingredients := [("iron_bar", 8), ("jasper_crystal", 1), ("spruce_plank", 2)]
    craftDepth := 2 }

/-- Recipe for `iron_bar` (craftDepth 1). -/
def recipe_iron_bar : Recipe :=
  { output := "iron_bar"
    ingredients := [("iron_ore", 10)]
    craftDepth := 1 }

/-- Recipe for `iron_boots` (craftDepth 2). -/
def recipe_iron_boots : Recipe :=
  { output := "iron_boots"
    ingredients := [("feather", 3), ("iron_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `iron_dagger` (craftDepth 2). -/
def recipe_iron_dagger : Recipe :=
  { output := "iron_dagger"
    ingredients := [("feather", 2), ("iron_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `iron_helm` (craftDepth 2). -/
def recipe_iron_helm : Recipe :=
  { output := "iron_helm"
    ingredients := [("iron_bar", 5), ("wool", 3)]
    craftDepth := 2 }

/-- Recipe for `iron_legs_armor` (craftDepth 2). -/
def recipe_iron_legs_armor : Recipe :=
  { output := "iron_legs_armor"
    ingredients := [("cowhide", 3), ("iron_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `iron_pickaxe` (craftDepth 2). -/
def recipe_iron_pickaxe : Recipe :=
  { output := "iron_pickaxe"
    ingredients := [("iron_bar", 8), ("jasper_crystal", 1), ("spruce_plank", 2)]
    craftDepth := 2 }

/-- Recipe for `iron_ring` (craftDepth 2). -/
def recipe_iron_ring : Recipe :=
  { output := "iron_ring"
    ingredients := [("iron_bar", 6), ("wool", 2)]
    craftDepth := 2 }

/-- Recipe for `iron_shield` (craftDepth 2). -/
def recipe_iron_shield : Recipe :=
  { output := "iron_shield"
    ingredients := [("iron_bar", 5), ("wool", 3)]
    craftDepth := 2 }

/-- Recipe for `iron_sword` (craftDepth 2). -/
def recipe_iron_sword : Recipe :=
  { output := "iron_sword"
    ingredients := [("feather", 2), ("iron_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `jester_hat` (craftDepth 2). -/
def recipe_jester_hat : Recipe :=
  { output := "jester_hat"
    ingredients := [("cursed_book", 3), ("cursed_plank", 8), ("goblin_guard_foot", 3), ("owlbear_hair", 3), ("prime_fabric", 1), ("vampire_tooth", 2)]
    craftDepth := 2 }

/-- Recipe for `king_slime_sword` (craftDepth 2). -/
def recipe_king_slime_sword : Recipe :=
  { output := "king_slime_sword"
    ingredients := [("iron_bar", 8), ("jasper_crystal", 1), ("king_slimeball", 6)]
    craftDepth := 2 }

/-- Recipe for `lava_underground_potion` (craftDepth 1). -/
def recipe_lava_underground_potion : Recipe :=
  { output := "lava_underground_potion"
    ingredients := [("enchanted_mushroom", 1), ("lava_fish", 1)]
    craftDepth := 1 }

/-- Recipe for `leather_armor` (craftDepth 2). -/
def recipe_leather_armor : Recipe :=
  { output := "leather_armor"
    ingredients := [("cowhide", 4), ("spruce_plank", 4)]
    craftDepth := 2 }

/-- Recipe for `leather_boots` (craftDepth 2). -/
def recipe_leather_boots : Recipe :=
  { output := "leather_boots"
    ingredients := [("ash_plank", 4), ("cowhide", 4)]
    craftDepth := 2 }

/-- Recipe for `leather_gloves` (craftDepth 2). -/
def recipe_leather_gloves : Recipe :=
  { output := "leather_gloves"
    ingredients := [("ash_plank", 2), ("cowhide", 8), ("jasper_crystal", 1)]
    craftDepth := 2 }

/-- Recipe for `leather_hat` (craftDepth 1). -/
def recipe_leather_hat : Recipe :=
  { output := "leather_hat"
    ingredients := [("cowhide", 5), ("yellow_slimeball", 3)]
    craftDepth := 1 }

/-- Recipe for `leather_legs_armor` (craftDepth 2). -/
def recipe_leather_legs_armor : Recipe :=
  { output := "leather_legs_armor"
    ingredients := [("cowhide", 3), ("spruce_plank", 5)]
    craftDepth := 2 }

/-- Recipe for `life_amulet` (craftDepth 1). -/
def recipe_life_amulet : Recipe :=
  { output := "life_amulet"
    ingredients := [("feather", 4), ("red_slimeball", 2)]
    craftDepth := 1 }

/-- Recipe for `life_ring` (craftDepth 2). -/
def recipe_life_ring : Recipe :=
  { output := "life_ring"
    ingredients := [("cloth", 2), ("iron_bar", 8), ("mushroom", 5)]
    craftDepth := 2 }

/-- Recipe for `lightning_sword` (craftDepth 2). -/
def recipe_lightning_sword : Recipe :=
  { output := "lightning_sword"
    ingredients := [("bat_heart", 5), ("broken_sword", 1), ("hellhound_hair", 4), ("magical_cure", 3), ("maple_plank", 7)]
    craftDepth := 2 }

/-- Recipe for `lizard_boots` (craftDepth 2). -/
def recipe_lizard_boots : Recipe :=
  { output := "lizard_boots"
    ingredients := [("dead_wood_plank", 8), ("imp_tail", 4), ("lizard_skin", 4), ("magical_cure", 1), ("vermin_leather", 3)]
    craftDepth := 2 }

/-- Recipe for `lizard_skin_armor` (craftDepth 2). -/
def recipe_lizard_skin_armor : Recipe :=
  { output := "lizard_skin_armor"
    ingredients := [("dead_wood_plank", 5), ("jasper_crystal", 2), ("lizard_skin", 5), ("vampire_tooth", 4)]
    craftDepth := 2 }

/-- Recipe for `lizard_skin_legs_armor` (craftDepth 1). -/
def recipe_lizard_skin_legs_armor : Recipe :=
  { output := "lizard_skin_legs_armor"
    ingredients := [("jasper_crystal", 2), ("lizard_skin", 5), ("ogre_eye", 4), ("vermin_leather", 5)]
    craftDepth := 1 }

/-- Recipe for `lost_amulet` (craftDepth 2). -/
def recipe_lost_amulet : Recipe :=
  { output := "lost_amulet"
    ingredients := [("cyclops_eye", 4), ("gold_bar", 8), ("imp_tail", 3), ("obsidian_bar", 4), ("red_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `lucky_wizard_hat` (craftDepth 1). -/
def recipe_lucky_wizard_hat : Recipe :=
  { output := "lucky_wizard_hat"
    ingredients := [("flying_wing", 6), ("green_cloth", 6), ("snakeskin", 3)]
    craftDepth := 1 }

/-- Recipe for `magic_bow` (craftDepth 2). -/
def recipe_magic_bow : Recipe :=
  { output := "magic_bow"
    ingredients := [("corrupted_stone", 3), ("lizard_skin", 3), ("magical_cure", 2), ("magical_plank", 7), ("sapphire", 1), ("wolf_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `magic_sap` (craftDepth 1). -/
def recipe_magic_sap : Recipe :=
  { output := "magic_sap"
    ingredients := [("magic_wood", 15)]
    craftDepth := 1 }

/-- Recipe for `magic_shield` (craftDepth 2). -/
def recipe_magic_shield : Recipe :=
  { output := "magic_shield"
    ingredients := [("alexandrite", 1), ("desert_scorpion_carapace", 3), ("fennec_ear", 2), ("grimlet_bone", 4), ("marauder_hand", 4), ("palm_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `magic_wizard_hat` (craftDepth 2). -/
def recipe_magic_wizard_hat : Recipe :=
  { output := "magic_wizard_hat"
    ingredients := [("blue_slimeball", 6), ("hardwood_plank", 2), ("ogre_skin", 2), ("snakeskin", 4), ("wolf_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `magical_plank` (craftDepth 1). -/
def recipe_magical_plank : Recipe :=
  { output := "magical_plank"
    ingredients := [("dead_wood", 4), ("magic_wood", 6)]
    craftDepth := 1 }

/-- Recipe for `malefic_armor` (craftDepth 2). -/
def recipe_malefic_armor : Recipe :=
  { output := "malefic_armor"
    ingredients := [("corrupted_stone", 3), ("magical_cure", 2), ("magical_plank", 8), ("malefic_cloth", 2), ("owlbear_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `malefic_ring` (craftDepth 2). -/
def recipe_malefic_ring : Recipe :=
  { output := "malefic_ring"
    ingredients := [("astralyte_crystal", 2), ("cursed_plank", 4), ("lizard_eye", 2), ("owlbear_claw", 2), ("ruby", 2), ("strangold_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `maple_plank` (craftDepth 1). -/
def recipe_maple_plank : Recipe :=
  { output := "maple_plank"
    ingredients := [("maple_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `maple_sap` (craftDepth 1). -/
def recipe_maple_sap : Recipe :=
  { output := "maple_sap"
    ingredients := [("maple_wood", 15)]
    craftDepth := 1 }

/-- Recipe for `maple_syrup` (craftDepth 2). -/
def recipe_maple_syrup : Recipe :=
  { output := "maple_syrup"
    ingredients := [("maple_sap", 2)]
    craftDepth := 2 }

/-- Recipe for `masterful_necklace` (craftDepth 2). -/
def recipe_masterful_necklace : Recipe :=
  { output := "masterful_necklace"
    ingredients := [("astralyte_crystal", 2), ("corrupted_stone", 5), ("goblin_tooth", 5), ("priestess_orb", 2), ("strangold_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `medic_armor` (craftDepth 2). -/
def recipe_medic_armor : Recipe :=
  { output := "medic_armor"
    ingredients := [("dryad_hair", 4), ("fennec_tail", 3), ("fire_crystal", 2), ("palm_plank", 12), ("red_dragon_scale", 3), ("solar_desert_scorpion_tail", 3)]
    craftDepth := 2 }

/-- Recipe for `medic_skirt` (craftDepth 2). -/
def recipe_medic_skirt : Recipe :=
  { output := "medic_skirt"
    ingredients := [("baby_red_dragon_scale", 3), ("dryad_hair", 4), ("fennec_ear", 3), ("fire_crystal", 2), ("palm_plank", 12), ("solar_desert_scorpion_tail", 3)]
    craftDepth := 2 }

/-- Recipe for `mesh_armor` (craftDepth 2). -/
def recipe_mesh_armor : Recipe :=
  { output := "mesh_armor"
    ingredients := [("efreet_cloth", 3), ("enchanted_fabric", 2), ("grimlet_bone", 3), ("hellhound_hair", 5), ("mithril_bar", 10), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `mesh_legs_armor` (craftDepth 2). -/
def recipe_mesh_legs_armor : Recipe :=
  { output := "mesh_legs_armor"
    ingredients := [("dark_essence", 4), ("efreet_cloth", 3), ("enchanted_fabric", 3), ("mithril_bar", 10), ("orc_skin", 4)]
    craftDepth := 2 }

/-- Recipe for `minor_health_potion` (craftDepth 1). -/
def recipe_minor_health_potion : Recipe :=
  { output := "minor_health_potion"
    ingredients := [("algae", 1), ("nettle_leaf", 2)]
    craftDepth := 1 }

/-- Recipe for `mithril_axe` (craftDepth 2). -/
def recipe_mithril_axe : Recipe :=
  { output := "mithril_axe"
    ingredients := [("dark_essence", 3), ("mithril_bar", 8), ("owlbear_claw", 3), ("vampire_tooth", 3), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_bar` (craftDepth 1). -/
def recipe_mithril_bar : Recipe :=
  { output := "mithril_bar"
    ingredients := [("mithril_ore", 10)]
    craftDepth := 1 }

/-- Recipe for `mithril_boots` (craftDepth 2). -/
def recipe_mithril_boots : Recipe :=
  { output := "mithril_boots"
    ingredients := [("echoless_bat_wing", 3), ("goblin_eye", 4), ("hellhound_hair", 4), ("mithril_bar", 7), ("prime_fabric", 2)]
    craftDepth := 2 }

/-- Recipe for `mithril_fishing_rod` (craftDepth 2). -/
def recipe_mithril_fishing_rod : Recipe :=
  { output := "mithril_fishing_rod"
    ingredients := [("bat_heart", 3), ("cursed_flask", 3), ("cursed_plank", 3), ("hellhound_hair", 3), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `mithril_gloves` (craftDepth 2). -/
def recipe_mithril_gloves : Recipe :=
  { output := "mithril_gloves"
    ingredients := [("cursed_book", 3), ("cursed_flask", 3), ("hellhound_collar", 3), ("imp_tail", 3), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `mithril_helm` (craftDepth 2). -/
def recipe_mithril_helm : Recipe :=
  { output := "mithril_helm"
    ingredients := [("diamond", 1), ("echoless_bat_wing", 3), ("jasper_crystal", 5), ("mithril_bar", 8), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_pickaxe` (craftDepth 2). -/
def recipe_mithril_pickaxe : Recipe :=
  { output := "mithril_pickaxe"
    ingredients := [("broken_sword", 1), ("dark_essence", 3), ("mithril_bar", 8), ("owlbear_claw", 3), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `mithril_platebody` (craftDepth 2). -/
def recipe_mithril_platebody : Recipe :=
  { output := "mithril_platebody"
    ingredients := [("echoless_bat_wing", 3), ("goblin_guard_foot", 3), ("goblin_tooth", 4), ("mithril_bar", 8), ("prime_fabric", 2)]
    craftDepth := 2 }

/-- Recipe for `mithril_platelegs` (craftDepth 2). -/
def recipe_mithril_platelegs : Recipe :=
  { output := "mithril_platelegs"
    ingredients := [("demoniac_dust", 3), ("lizard_eye", 2), ("mithril_bar", 8), ("owlbear_hair", 4), ("vampire_tooth", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_ring` (craftDepth 2). -/
def recipe_mithril_ring : Recipe :=
  { output := "mithril_ring"
    ingredients := [("bat_heart", 4), ("dark_essence", 3), ("lizard_eye", 2), ("mithril_bar", 8), ("wolfrider_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_shield` (craftDepth 2). -/
def recipe_mithril_shield : Recipe :=
  { output := "mithril_shield"
    ingredients := [("cyclops_eye", 3), ("goblin_eye", 4), ("hellhound_hair", 3), ("lizard_skin", 3), ("mithril_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `mithril_sword` (craftDepth 2). -/
def recipe_mithril_sword : Recipe :=
  { output := "mithril_sword"
    ingredients := [("astralyte_crystal", 2), ("broken_sword", 1), ("corrupted_stone", 3), ("goblin_guard_foot", 4), ("mithril_bar", 7), ("wolfrider_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `moonlight_staff` (craftDepth 2). -/
def recipe_moonlight_staff : Recipe :=
  { output := "moonlight_staff"
    ingredients := [("alexandrite", 1), ("dusk_beetle_shell", 5), ("marauder_hand", 4), ("orc_bone", 4), ("palm_plank", 10), ("priestess_orb", 2)]
    craftDepth := 2 }

/-- Recipe for `mushmush_bow` (craftDepth 2). -/
def recipe_mushmush_bow : Recipe :=
  { output := "mushmush_bow"
    ingredients := [("jasper_crystal", 1), ("mushroom", 4), ("spruce_plank", 5), ("wolf_hair", 2)]
    craftDepth := 2 }

/-- Recipe for `mushmush_jacket` (craftDepth 1). -/
def recipe_mushmush_jacket : Recipe :=
  { output := "mushmush_jacket"
    ingredients := [("flying_wing", 6), ("hard_leather", 3), ("mushroom", 6)]
    craftDepth := 1 }

/-- Recipe for `mushmush_wizard_hat` (craftDepth 1). -/
def recipe_mushmush_wizard_hat : Recipe :=
  { output := "mushmush_wizard_hat"
    ingredients := [("cowhide", 4), ("mushroom", 6), ("wolf_hair", 4)]
    craftDepth := 1 }

/-- Recipe for `mushroom_soup` (craftDepth 1). -/
def recipe_mushroom_soup : Recipe :=
  { output := "mushroom_soup"
    ingredients := [("mushroom", 2)]
    craftDepth := 1 }

/-- Recipe for `mushstaff` (craftDepth 2). -/
def recipe_mushstaff : Recipe :=
  { output := "mushstaff"
    ingredients := [("green_cloth", 2), ("jasper_crystal", 1), ("mushroom", 4), ("spruce_plank", 5)]
    craftDepth := 2 }

/-- Recipe for `obsidian_armor` (craftDepth 2). -/
def recipe_obsidian_armor : Recipe :=
  { output := "obsidian_armor"
    ingredients := [("demoniac_dust", 4), ("full_moon_vampire_cape", 4), ("obsidian_bar", 6), ("ruby", 1), ("spider_leg", 5)]
    craftDepth := 2 }

/-- Recipe for `obsidian_bar` (craftDepth 1). -/
def recipe_obsidian_bar : Recipe :=
  { output := "obsidian_bar"
    ingredients := [("piece_of_obsidian", 4)]
    craftDepth := 1 }

/-- Recipe for `obsidian_battleaxe` (craftDepth 2). -/
def recipe_obsidian_battleaxe : Recipe :=
  { output := "obsidian_battleaxe"
    ingredients := [("cyclops_eye", 3), ("dead_wood_plank", 4), ("imp_tail", 3), ("lizard_skin", 3), ("obsidian_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `obsidian_helmet` (craftDepth 2). -/
def recipe_obsidian_helmet : Recipe :=
  { output := "obsidian_helmet"
    ingredients := [("emerald", 1), ("lizard_skin", 5), ("obsidian_bar", 6), ("owlbear_hair", 3), ("vampire_tooth", 5)]
    craftDepth := 2 }

/-- Recipe for `obsidian_legs_armor` (craftDepth 2). -/
def recipe_obsidian_legs_armor : Recipe :=
  { output := "obsidian_legs_armor"
    ingredients := [("lizard_eye", 5), ("obsidian_bar", 6), ("owlbear_claw", 3), ("red_cloth", 5), ("sapphire", 1)]
    craftDepth := 2 }

/-- Recipe for `palm_plank` (craftDepth 1). -/
def recipe_palm_plank : Recipe :=
  { output := "palm_plank"
    ingredients := [("palm_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `perfect_bow` (craftDepth 2). -/
def recipe_perfect_bow : Recipe :=
  { output := "perfect_bow"
    ingredients := [("demon_horn", 2), ("gold_bar", 8), ("ogre_eye", 4), ("red_cloth", 3), ("spider_leg", 3)]
    craftDepth := 2 }

/-- Recipe for `piggy_armor` (craftDepth 2). -/
def recipe_piggy_armor : Recipe :=
  { output := "piggy_armor"
    ingredients := [("dead_wood_plank", 5), ("full_moon_vampire_cape", 4), ("jasper_crystal", 2), ("pig_skin", 5)]
    craftDepth := 2 }

/-- Recipe for `piggy_helmet` (craftDepth 2). -/
def recipe_piggy_helmet : Recipe :=
  { output := "piggy_helmet"
    ingredients := [("cyclops_eye", 2), ("full_moon_vampire_cape", 2), ("pig_skin", 6), ("steel_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `piggy_pants` (craftDepth 2). -/
def recipe_piggy_pants : Recipe :=
  { output := "piggy_pants"
    ingredients := [("hardwood_plank", 5), ("jasper_crystal", 2), ("pig_skin", 5), ("snakeskin", 3)]
    craftDepth := 2 }

/-- Recipe for `prospecting_amulet` (craftDepth 2). -/
def recipe_prospecting_amulet : Recipe :=
  { output := "prospecting_amulet"
    ingredients := [("dead_wood_plank", 4), ("magical_cure", 1), ("ogre_skin", 6), ("owlbear_hair", 4), ("spider_leg", 3)]
    craftDepth := 2 }

/-- Recipe for `recall_potion` (craftDepth 1). -/
def recipe_recall_potion : Recipe :=
  { output := "recall_potion"
    ingredients := [("gudgeon", 1), ("sunflower", 1)]
    craftDepth := 1 }

/-- Recipe for `red_dragon_armor` (craftDepth 1). -/
def recipe_red_dragon_armor : Recipe :=
  { output := "red_dragon_armor"
    ingredients := [("baby_red_dragon_scale", 4), ("desert_scorpion_carapace", 3), ("dragon_bone", 12), ("fennec_ear", 3), ("fire_crystal", 2), ("red_dragon_scale", 3)]
    craftDepth := 1 }

/-- Recipe for `red_dragon_boots` (craftDepth 2). -/
def recipe_red_dragon_boots : Recipe :=
  { output := "red_dragon_boots"
    ingredients := [("alexandrite", 1), ("baby_red_dragon_scale", 4), ("dragon_bone", 12), ("fire_crystal", 2), ("red_dragon_scale", 4), ("solar_desert_scorpion_tail", 3)]
    craftDepth := 2 }

/-- Recipe for `red_dragon_legs_armor` (craftDepth 2). -/
def recipe_red_dragon_legs_armor : Recipe :=
  { output := "red_dragon_legs_armor"
    ingredients := [("alexandrite", 1), ("baby_red_dragon_scale", 3), ("dragon_bone", 12), ("fennec_tail", 3), ("marauder_hand", 3), ("red_dragon_scale", 3)]
    craftDepth := 2 }

/-- Recipe for `red_dragon_shield` (craftDepth 1). -/
def recipe_red_dragon_shield : Recipe :=
  { output := "red_dragon_shield"
    ingredients := [("baby_red_dragon_scale", 5), ("dragon_bone", 10), ("fire_crystal", 2), ("red_dragon_scale", 4), ("solar_desert_scorpion_tail", 4)]
    craftDepth := 1 }

/-- Recipe for `ring_of_chance` (craftDepth 2). -/
def recipe_ring_of_chance : Recipe :=
  { output := "ring_of_chance"
    ingredients := [("jasper_crystal", 1), ("king_slimeball", 4), ("pig_skin", 4), ("steel_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `royal_skeleton_armor` (craftDepth 3). -/
def recipe_royal_skeleton_armor : Recipe :=
  { output := "royal_skeleton_armor"
    ingredients := [("demoniac_dust", 3), ("gold_bar", 8), ("red_cloth", 3), ("skeleton_armor", 1)]
    craftDepth := 3 }

/-- Recipe for `royal_skeleton_helmet` (craftDepth 3). -/
def recipe_royal_skeleton_helmet : Recipe :=
  { output := "royal_skeleton_helmet"
    ingredients := [("gold_bar", 8), ("owlbear_claw", 4), ("skeleton_helmet", 1), ("vermin_leather", 4)]
    craftDepth := 3 }

/-- Recipe for `royal_skeleton_pants` (craftDepth 3). -/
def recipe_royal_skeleton_pants : Recipe :=
  { output := "royal_skeleton_pants"
    ingredients := [("gold_bar", 8), ("owlbear_hair", 3), ("skeleton_pants", 1), ("vampire_blood", 3)]
    craftDepth := 3 }

/-- Recipe for `royal_skeleton_ring` (craftDepth 2). -/
def recipe_royal_skeleton_ring : Recipe :=
  { output := "royal_skeleton_ring"
    ingredients := [("gold_bar", 8), ("ogre_skin", 4), ("owlbear_claw", 3), ("spider_leg", 2), ("vampire_tooth", 3)]
    craftDepth := 2 }

/-- Recipe for `ruby` (craftDepth 1). -/
def recipe_ruby : Recipe :=
  { output := "ruby"
    ingredients := [("ruby_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `ruby_amulet` (craftDepth 2). -/
def recipe_ruby_amulet : Recipe :=
  { output := "ruby_amulet"
    ingredients := [("hardwood_plank", 8), ("jasper_crystal", 2), ("ruby", 1), ("snake_hide", 5)]
    craftDepth := 2 }

/-- Recipe for `ruby_ring` (craftDepth 2). -/
def recipe_ruby_ring : Recipe :=
  { output := "ruby_ring"
    ingredients := [("gold_bar", 8), ("magical_cure", 2), ("obsidian_bar", 4), ("ruby", 1), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `sacred_ring` (craftDepth 2). -/
def recipe_sacred_ring : Recipe :=
  { output := "sacred_ring"
    ingredients := [("astralyte_crystal", 2), ("emerald", 2), ("hellhound_collar", 4), ("rosenblood_elixir", 1), ("ruby", 2), ("strangold_bar", 9)]
    craftDepth := 2 }

/-- Recipe for `sand_snakeskin_armor` (craftDepth 2). -/
def recipe_sand_snakeskin_armor : Recipe :=
  { output := "sand_snakeskin_armor"
    ingredients := [("cursed_flask", 3), ("enchanted_fabric", 2), ("maple_plank", 10), ("sand_snakeskin", 5), ("wolfrider_ponytail", 4)]
    craftDepth := 2 }

/-- Recipe for `sand_snakeskin_bandana` (craftDepth 2). -/
def recipe_sand_snakeskin_bandana : Recipe :=
  { output := "sand_snakeskin_bandana"
    ingredients := [("enchanted_fabric", 2), ("grimlet_bone", 3), ("maple_plank", 10), ("marauder_hand", 4), ("sand_snakeskin", 5)]
    craftDepth := 2 }

/-- Recipe for `sand_snakeskin_boots` (craftDepth 2). -/
def recipe_sand_snakeskin_boots : Recipe :=
  { output := "sand_snakeskin_boots"
    ingredients := [("astralyte_crystal", 3), ("bat_wing", 4), ("dark_essence", 2), ("maple_plank", 10), ("sand_snakeskin", 5)]
    craftDepth := 2 }

/-- Recipe for `sand_snakeskin_pants` (craftDepth 2). -/
def recipe_sand_snakeskin_pants : Recipe :=
  { output := "sand_snakeskin_pants"
    ingredients := [("grimlet_bone", 3), ("maple_plank", 10), ("marauder_hand", 2), ("sand_snakeskin", 5), ("wolfrider_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `sandwhisper_potion` (craftDepth 1). -/
def recipe_sandwhisper_potion : Recipe :=
  { output := "sandwhisper_potion"
    ingredients := [("swordfish", 1), ("torch_cactus_flower", 1)]
    craftDepth := 1 }

/-- Recipe for `sap` (craftDepth 1). -/
def recipe_sap : Recipe :=
  { output := "sap"
    ingredients := [("ash_wood", 5), ("dead_wood", 5), ("spruce_wood", 5)]
    craftDepth := 1 }

/-- Recipe for `sapphire` (craftDepth 1). -/
def recipe_sapphire : Recipe :=
  { output := "sapphire"
    ingredients := [("sapphire_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `sapphire_amulet` (craftDepth 2). -/
def recipe_sapphire_amulet : Recipe :=
  { output := "sapphire_amulet"
    ingredients := [("hardwood_plank", 8), ("jasper_crystal", 2), ("sapphire", 1), ("wolf_hair", 5)]
    craftDepth := 2 }

/-- Recipe for `sapphire_ring` (craftDepth 2). -/
def recipe_sapphire_ring : Recipe :=
  { output := "sapphire_ring"
    ingredients := [("gold_bar", 8), ("magical_cure", 2), ("obsidian_bar", 4), ("sapphire", 1), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `satchel` (craftDepth 1). -/
def recipe_satchel : Recipe :=
  { output := "satchel"
    ingredients := [("cowhide", 5), ("feather", 2), ("jasper_crystal", 1)]
    craftDepth := 1 }

/-- Recipe for `shuriken` (craftDepth 2). -/
def recipe_shuriken : Recipe :=
  { output := "shuriken"
    ingredients := [("flying_wing", 3), ("ogre_skin", 3), ("steel_bar", 5), ("wolf_bone", 4)]
    craftDepth := 2 }

/-- Recipe for `skeleton_armor` (craftDepth 2). -/
def recipe_skeleton_armor : Recipe :=
  { output := "skeleton_armor"
    ingredients := [("pig_skin", 2), ("skeleton_bone", 6), ("steel_bar", 4), ("wolf_bone", 3)]
    craftDepth := 2 }

/-- Recipe for `skeleton_helmet` (craftDepth 2). -/
def recipe_skeleton_helmet : Recipe :=
  { output := "skeleton_helmet"
    ingredients := [("iron_bar", 7), ("skeleton_bone", 3), ("skeleton_skull", 1), ("wolf_bone", 2)]
    craftDepth := 2 }

/-- Recipe for `skeleton_pants` (craftDepth 2). -/
def recipe_skeleton_pants : Recipe :=
  { output := "skeleton_pants"
    ingredients := [("ash_plank", 7), ("skeleton_bone", 3), ("wolf_bone", 3), ("wolf_hair", 2)]
    craftDepth := 2 }

/-- Recipe for `skull_amulet` (craftDepth 2). -/
def recipe_skull_amulet : Recipe :=
  { output := "skull_amulet"
    ingredients := [("hardwood_plank", 7), ("king_slimeball", 2), ("skeleton_skull", 3), ("snake_hide", 3)]
    craftDepth := 2 }

/-- Recipe for `skull_ring` (craftDepth 2). -/
def recipe_skull_ring : Recipe :=
  { output := "skull_ring"
    ingredients := [("jasper_crystal", 2), ("skeleton_skull", 1), ("steel_bar", 4), ("wolf_bone", 4)]
    craftDepth := 2 }

/-- Recipe for `skull_staff` (craftDepth 2). -/
def recipe_skull_staff : Recipe :=
  { output := "skull_staff"
    ingredients := [("hardwood_plank", 5), ("skeleton_bone", 4), ("skeleton_skull", 1), ("steel_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `skull_wand` (craftDepth 2). -/
def recipe_skull_wand : Recipe :=
  { output := "skull_wand"
    ingredients := [("hardwood_plank", 4), ("jasper_crystal", 1), ("skeleton_skull", 3), ("spider_leg", 3), ("vampire_tooth", 2)]
    craftDepth := 2 }

/-- Recipe for `skullforged_armor` (craftDepth 2). -/
def recipe_skullforged_armor : Recipe :=
  { output := "skullforged_armor"
    ingredients := [("adventurer_skull", 4), ("astralyte_crystal", 2), ("desert_scorpion_carapace", 4), ("fennec_tail", 3), ("lava_bucket", 3), ("palm_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `skullforged_pants` (craftDepth 2). -/
def recipe_skullforged_pants : Recipe :=
  { output := "skullforged_pants"
    ingredients := [("adventurer_skull", 3), ("astralyte_crystal", 2), ("demon_horn", 4), ("desert_scorpion_carapace", 2), ("dusk_beetle_shell", 3), ("fennec_tail", 2), ("palm_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `skullforged_ring` (craftDepth 2). -/
def recipe_skullforged_ring : Recipe :=
  { output := "skullforged_ring"
    ingredients := [("adamantite_bar", 10), ("adventurer_skull", 4), ("alexandrite", 1), ("dusk_beetle_shell", 3), ("jasper_crystal", 4), ("lava_bucket", 4)]
    craftDepth := 2 }

/-- Recipe for `slime_shield` (craftDepth 2). -/
def recipe_slime_shield : Recipe :=
  { output := "slime_shield"
    ingredients := [("cloth", 3), ("hardwood_plank", 6), ("king_slimeball", 6)]
    craftDepth := 2 }

/-- Recipe for `small_antidote` (craftDepth 2). -/
def recipe_small_antidote : Recipe :=
  { output := "small_antidote"
    ingredients := [("milk_bucket", 1), ("nettle_leaf", 1), ("sap", 1)]
    craftDepth := 2 }

/-- Recipe for `small_health_potion` (craftDepth 1). -/
def recipe_small_health_potion : Recipe :=
  { output := "small_health_potion"
    ingredients := [("sunflower", 3)]
    craftDepth := 1 }

/-- Recipe for `snakeskin_armor` (craftDepth 1). -/
def recipe_snakeskin_armor : Recipe :=
  { output := "snakeskin_armor"
    ingredients := [("full_moon_vampire_cape", 4), ("jasper_crystal", 1), ("skeleton_bone", 5), ("snakeskin", 2)]
    craftDepth := 1 }

/-- Recipe for `snakeskin_boots` (craftDepth 2). -/
def recipe_snakeskin_boots : Recipe :=
  { output := "snakeskin_boots"
    ingredients := [("green_cloth", 2), ("hardwood_plank", 5), ("snakeskin", 2), ("spider_leg", 2)]
    craftDepth := 2 }

/-- Recipe for `snakeskin_legs_armor` (craftDepth 1). -/
def recipe_snakeskin_legs_armor : Recipe :=
  { output := "snakeskin_legs_armor"
    ingredients := [("hard_leather", 3), ("snakeskin", 2), ("wolf_bone", 5)]
    craftDepth := 1 }

/-- Recipe for `spruce_fishing_rod` (craftDepth 2). -/
def recipe_spruce_fishing_rod : Recipe :=
  { output := "spruce_fishing_rod"
    ingredients := [("iron_bar", 2), ("jasper_crystal", 1), ("spruce_plank", 8)]
    craftDepth := 2 }

/-- Recipe for `spruce_plank` (craftDepth 1). -/
def recipe_spruce_plank : Recipe :=
  { output := "spruce_plank"
    ingredients := [("spruce_wood", 10)]
    craftDepth := 1 }

/-- Recipe for `steel_armor` (craftDepth 2). -/
def recipe_steel_armor : Recipe :=
  { output := "steel_armor"
    ingredients := [("cloth", 3), ("green_cloth", 2), ("spider_leg", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_axe` (craftDepth 2). -/
def recipe_steel_axe : Recipe :=
  { output := "steel_axe"
    ingredients := [("astralyte_crystal", 2), ("flying_wing", 2), ("ogre_eye", 4), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_bar` (craftDepth 1). -/
def recipe_steel_bar : Recipe :=
  { output := "steel_bar"
    ingredients := [("coal", 7), ("iron_ore", 3)]
    craftDepth := 1 }

/-- Recipe for `steel_battleaxe` (craftDepth 2). -/
def recipe_steel_battleaxe : Recipe :=
  { output := "steel_battleaxe"
    ingredients := [("hardwood_plank", 4), ("skeleton_bone", 4), ("steel_bar", 4), ("wolf_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `steel_boots` (craftDepth 2). -/
def recipe_steel_boots : Recipe :=
  { output := "steel_boots"
    ingredients := [("hardwood_plank", 5), ("ogre_skin", 3), ("snakeskin", 2), ("steel_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `steel_fishing_rod` (craftDepth 2). -/
def recipe_steel_fishing_rod : Recipe :=
  { output := "steel_fishing_rod"
    ingredients := [("astralyte_crystal", 2), ("green_cloth", 3), ("ogre_skin", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_gloves` (craftDepth 2). -/
def recipe_steel_gloves : Recipe :=
  { output := "steel_gloves"
    ingredients := [("astralyte_crystal", 2), ("pig_skin", 3), ("skeleton_bone", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_helm` (craftDepth 2). -/
def recipe_steel_helm : Recipe :=
  { output := "steel_helm"
    ingredients := [("cloth", 3), ("ogre_skin", 3), ("steel_bar", 8), ("wolf_bone", 2)]
    craftDepth := 2 }

/-- Recipe for `steel_legs_armor` (craftDepth 2). -/
def recipe_steel_legs_armor : Recipe :=
  { output := "steel_legs_armor"
    ingredients := [("cloth", 3), ("king_slimeball", 3), ("skeleton_skull", 2), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_pickaxe` (craftDepth 2). -/
def recipe_steel_pickaxe : Recipe :=
  { output := "steel_pickaxe"
    ingredients := [("astralyte_crystal", 2), ("pig_skin", 3), ("spider_leg", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `steel_ring` (craftDepth 2). -/
def recipe_steel_ring : Recipe :=
  { output := "steel_ring"
    ingredients := [("hard_leather", 2), ("skeleton_bone", 3), ("snake_hide", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `sticky_dagger` (craftDepth 2). -/
def recipe_sticky_dagger : Recipe :=
  { output := "sticky_dagger"
    ingredients := [("copper_bar", 5), ("green_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `sticky_sword` (craftDepth 2). -/
def recipe_sticky_sword : Recipe :=
  { output := "sticky_sword"
    ingredients := [("copper_bar", 5), ("yellow_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `stormforged_armor` (craftDepth 2). -/
def recipe_stormforged_armor : Recipe :=
  { output := "stormforged_armor"
    ingredients := [("dead_wood_plank", 5), ("jasper_crystal", 2), ("lizard_skin", 5), ("ogre_eye", 4)]
    craftDepth := 2 }

/-- Recipe for `stormforged_pants` (craftDepth 1). -/
def recipe_stormforged_pants : Recipe :=
  { output := "stormforged_pants"
    ingredients := [("jasper_crystal", 2), ("lizard_eye", 4), ("ogre_skin", 6), ("vermin_leather", 4)]
    craftDepth := 1 }

/-- Recipe for `strangold_armor` (craftDepth 2). -/
def recipe_strangold_armor : Recipe :=
  { output := "strangold_armor"
    ingredients := [("corrupted_stone", 3), ("demon_horn", 4), ("magical_cure", 2), ("owlbear_hair", 3), ("strangold_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `strangold_bar` (craftDepth 1). -/
def recipe_strangold_bar : Recipe :=
  { output := "strangold_bar"
    ingredients := [("gold_ore", 4), ("strange_ore", 6)]
    craftDepth := 1 }

/-- Recipe for `strangold_helmet` (craftDepth 2). -/
def recipe_strangold_helmet : Recipe :=
  { output := "strangold_helmet"
    ingredients := [("corrupted_stone", 3), ("demoniac_dust", 4), ("diamond", 1), ("lizard_skin", 4), ("magical_cure", 1), ("strangold_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `strangold_legs_armor` (craftDepth 2). -/
def recipe_strangold_legs_armor : Recipe :=
  { output := "strangold_legs_armor"
    ingredients := [("cursed_book", 3), ("magical_cure", 2), ("red_cloth", 3), ("strangold_bar", 8), ("vermin_leather", 4)]
    craftDepth := 2 }

/-- Recipe for `strangold_sword` (craftDepth 2). -/
def recipe_strangold_sword : Recipe :=
  { output := "strangold_sword"
    ingredients := [("corrupted_stone", 4), ("goblin_guard_foot", 3), ("goblin_tooth", 3), ("magical_cure", 2), ("strangold_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `topaz` (craftDepth 1). -/
def recipe_topaz : Recipe :=
  { output := "topaz"
    ingredients := [("topaz_stone", 24)]
    craftDepth := 1 }

/-- Recipe for `topaz_amulet` (craftDepth 2). -/
def recipe_topaz_amulet : Recipe :=
  { output := "topaz_amulet"
    ingredients := [("hardwood_plank", 8), ("jasper_crystal", 2), ("topaz", 1), ("wolf_hair", 5)]
    craftDepth := 2 }

/-- Recipe for `topaz_ring` (craftDepth 2). -/
def recipe_topaz_ring : Recipe :=
  { output := "topaz_ring"
    ingredients := [("gold_bar", 8), ("magical_cure", 2), ("obsidian_bar", 4), ("topaz", 1), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `tromatising_mask` (craftDepth 2). -/
def recipe_tromatising_mask : Recipe :=
  { output := "tromatising_mask"
    ingredients := [("cloth", 2), ("pig_skin", 3), ("skeleton_bone", 3), ("steel_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `vampire_bow` (craftDepth 2). -/
def recipe_vampire_bow : Recipe :=
  { output := "vampire_bow"
    ingredients := [("full_moon_vampire_cape", 4), ("magical_cure", 1), ("steel_bar", 4), ("vampire_blood", 4), ("vermin_leather", 2)]
    craftDepth := 2 }

/-- Recipe for `vital_armor` (craftDepth 2). -/
def recipe_vital_armor : Recipe :=
  { output := "vital_armor"
    ingredients := [("duskworm_skin", 4), ("fennec_tail", 2), ("lava_bucket", 2), ("palm_plank", 10), ("prime_fabric", 3), ("ruby", 2), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `vital_boots` (craftDepth 2). -/
def recipe_vital_boots : Recipe :=
  { output := "vital_boots"
    ingredients := [("desert_scorpion_carapace", 3), ("duskworm_skin", 3), ("efreet_cloth", 3), ("palm_plank", 12), ("prime_fabric", 2), ("sand_snake_poison", 3)]
    craftDepth := 2 }

/-- Recipe for `water_boost_potion` (craftDepth 1). -/
def recipe_water_boost_potion : Recipe :=
  { output := "water_boost_potion"
    ingredients := [("algae", 1), ("blue_slimeball", 1), ("sunflower", 1)]
    craftDepth := 1 }

/-- Recipe for `water_bow` (craftDepth 2). -/
def recipe_water_bow : Recipe :=
  { output := "water_bow"
    ingredients := [("ash_plank", 5), ("blue_slimeball", 2)]
    craftDepth := 2 }

/-- Recipe for `water_res_potion` (craftDepth 2). -/
def recipe_water_res_potion : Recipe :=
  { output := "water_res_potion"
    ingredients := [("blue_slimeball", 2), ("glowstem_leaf", 1), ("maple_sap", 1)]
    craftDepth := 2 }

/-- Recipe for `water_ring` (craftDepth 2). -/
def recipe_water_ring : Recipe :=
  { output := "water_ring"
    ingredients := [("blue_slimeball", 4), ("flying_wing", 3), ("iron_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `water_shield` (craftDepth 2). -/
def recipe_water_shield : Recipe :=
  { output := "water_shield"
    ingredients := [("blue_slimeball", 20), ("dryad_hair", 3), ("rosenblood_elixir", 1), ("sapphire", 1), ("strangold_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `white_knight_armor` (craftDepth 2). -/
def recipe_white_knight_armor : Recipe :=
  { output := "white_knight_armor"
    ingredients := [("corrupted_stone", 3), ("hellhound_hair", 3), ("mithril_bar", 8), ("prime_fabric", 2), ("wolfrider_ponytail", 4)]
    craftDepth := 2 }

/-- Recipe for `white_knight_helmet` (craftDepth 2). -/
def recipe_white_knight_helmet : Recipe :=
  { output := "white_knight_helmet"
    ingredients := [("diamond", 1), ("hellhound_collar", 4), ("mithril_bar", 8), ("orc_bone", 3), ("owlbear_claw", 4)]
    craftDepth := 2 }

/-- Recipe for `white_knight_pants` (craftDepth 2). -/
def recipe_white_knight_pants : Recipe :=
  { output := "white_knight_pants"
    ingredients := [("astralyte_crystal", 2), ("goblin_tooth", 4), ("hellhound_hair", 3), ("mithril_bar", 8), ("wolfrider_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `white_knight_shield` (craftDepth 2). -/
def recipe_white_knight_shield : Recipe :=
  { output := "white_knight_shield"
    ingredients := [("echoless_bat_wing", 3), ("goblin_eye", 4), ("hellhound_hair", 3), ("maple_plank", 7), ("wolfrider_hair", 3)]
    craftDepth := 2 }

/-- Recipe for `wisdom_amulet` (craftDepth 2). -/
def recipe_wisdom_amulet : Recipe :=
  { output := "wisdom_amulet"
    ingredients := [("green_cloth", 3), ("jasper_crystal", 1), ("snake_hide", 3), ("spruce_plank", 4)]
    craftDepth := 2 }

/-- Recipe for `wooden_shield` (craftDepth 2). -/
def recipe_wooden_shield : Recipe :=
  { output := "wooden_shield"
    ingredients := [("ash_plank", 6)]
    craftDepth := 2 }

/-- Recipe for `wooden_staff` (craftDepth 1). -/
def recipe_wooden_staff : Recipe :=
  { output := "wooden_staff"
    ingredients := [("ash_wood", 4), ("wooden_stick", 1)]
    craftDepth := 1 }

/-- Recipe for `wratharmor` (craftDepth 2). -/
def recipe_wratharmor : Recipe :=
  { output := "wratharmor"
    ingredients := [("goblin_eye", 4), ("hellhound_collar", 5), ("mithril_bar", 8), ("prime_fabric", 2), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `wrathelmet` (craftDepth 2). -/
def recipe_wrathelmet : Recipe :=
  { output := "wrathelmet"
    ingredients := [("astralyte_crystal", 2), ("cursed_book", 5), ("mithril_bar", 8), ("rosenblood_elixir", 1), ("wolfrider_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `wrathpants` (craftDepth 2). -/
def recipe_wrathpants : Recipe :=
  { output := "wrathpants"
    ingredients := [("enchanted_fabric", 2), ("goblin_tooth", 5), ("hellhound_collar", 3), ("mithril_bar", 8), ("priestess_orb", 2)]
    craftDepth := 2 }

/-- Recipe for `wrathsword` (craftDepth 2). -/
def recipe_wrathsword : Recipe :=
  { output := "wrathsword"
    ingredients := [("bat_wing", 4), ("broken_sword", 1), ("magical_cure", 3), ("mithril_bar", 7), ("orc_bone", 5)]
    craftDepth := 2 }

/-- All recipes in the live snapshot. -/
def allRecipes : List Recipe :=
  [
    recipe_adamantite_axe,
    recipe_adamantite_bar,
    recipe_adamantite_boots,
    recipe_adamantite_fishing_rod,
    recipe_adamantite_gloves,
    recipe_adamantite_mask,
    recipe_adamantite_pickaxe,
    recipe_adamantite_platebody,
    recipe_adamantite_platelegs,
    recipe_adamantite_ring,
    recipe_adamantite_shield,
    recipe_adamantite_sword,
    recipe_adventurer_boots,
    recipe_adventurer_helmet,
    recipe_adventurer_pants,
    recipe_adventurer_vest,
    recipe_air_and_water_amulet,
    recipe_air_boost_potion,
    recipe_air_res_potion,
    recipe_air_ring,
    recipe_air_shield,
    recipe_alexandrite,
    recipe_ancestral_talisman,
    recipe_ancient_jean,
    recipe_antidote,
    recipe_apple_pie,
    recipe_apprentice_gloves,
    recipe_ash_plank,
    recipe_battlestaff,
    recipe_batwing_helmet,
    recipe_blade_of_hell,
    recipe_bloodblade,
    recipe_bow_from_hell,
    recipe_celest_ring,
    recipe_cheese,
    recipe_conjurer_cloak,
    recipe_conjurer_skirt,
    recipe_cooked_bass,
    recipe_cooked_beef,
    recipe_cooked_chicken,
    recipe_cooked_desert_scorpion_meat,
    recipe_cooked_gudgeon,
    recipe_cooked_hellhound_meat,
    recipe_cooked_porkchop,
    recipe_cooked_rat_meat,
    recipe_cooked_salmon,
    recipe_cooked_shrimp,
    recipe_cooked_swordfish,
    recipe_cooked_trout,
    recipe_cooked_wolf_meat,
    recipe_cookie,
    recipe_copper_armor,
    recipe_copper_axe,
    recipe_copper_bar,
    recipe_copper_boots,
    recipe_copper_dagger,
    recipe_copper_helmet,
    recipe_copper_legs_armor,
    recipe_copper_pickaxe,
    recipe_copper_ring,
    recipe_corrupted_stone_amulet,
    recipe_cultist_boots,
    recipe_cultist_cloak,
    recipe_cultist_hat,
    recipe_cultist_pants,
    recipe_cursed_hat,
    recipe_cursed_plank,
    recipe_cursed_sceptre,
    recipe_dark_horned_helmet,
    recipe_darkforged_boots,
    recipe_darkforged_helmet,
    recipe_darkforged_plate,
    recipe_darkforged_shield,
    recipe_dead_wood_plank,
    recipe_demoniac_dagger,
    recipe_demoniac_shield,
    recipe_desert_whip,
    recipe_diamond,
    recipe_diamond_amulet,
    recipe_diamond_armor,
    recipe_diamond_skirt,
    recipe_diamond_sword,
    recipe_divinity_ring,
    recipe_dreadful_amulet,
    recipe_dreadful_armor,
    recipe_dreadful_battleaxe,
    recipe_dreadful_ring,
    recipe_dreadful_shield,
    recipe_dreadful_staff,
    recipe_duskarmor,
    recipe_duskpants,
    recipe_dust_amulet,
    recipe_dust_helmet,
    recipe_dust_sword,
    recipe_earth_boost_potion,
    recipe_earth_res_potion,
    recipe_earth_ring,
    recipe_earth_shield,
    recipe_elderwood_staff,
    recipe_emerald,
    recipe_emerald_amulet,
    recipe_emerald_ring,
    recipe_enchanted_potion,
    recipe_enchanter_boots,
    recipe_enchanter_pants,
    recipe_enhanced_antidote,
    recipe_enhanced_boost_potion,
    recipe_enhanced_health_potion,
    recipe_enhanced_health_splash_potion,
    recipe_eternal_red_ring,
    recipe_eternity_ring,
    recipe_feather_coat,
    recipe_fire_and_earth_amulet,
    recipe_fire_boost_potion,
    recipe_fire_bow,
    recipe_fire_res_potion,
    recipe_fire_ring,
    recipe_fire_shield,
    recipe_fire_staff,
    recipe_fish_soup,
    recipe_fishing_net,
    recipe_flying_boots,
    recipe_forest_bank_potion,
    recipe_forest_whip,
    recipe_fried_eggs,
    recipe_gold_axe,
    recipe_gold_bar,
    recipe_gold_boots,
    recipe_gold_fishing_rod,
    recipe_gold_helm,
    recipe_gold_mask,
    recipe_gold_pickaxe,
    recipe_gold_platebody,
    recipe_gold_platelegs,
    recipe_gold_ring,
    recipe_gold_shield,
    recipe_gold_sword,
    recipe_golden_gloves,
    recipe_greater_dreadful_amulet,
    recipe_greater_dreadful_staff,
    recipe_greater_emerald_amulet,
    recipe_greater_health_potion,
    recipe_greater_ruby_amulet,
    recipe_greater_sapphire_amulet,
    recipe_greater_topaz_amulet,
    recipe_greater_wooden_staff,
    recipe_hard_leather_armor,
    recipe_hard_leather_boots,
    recipe_hard_leather_helmet,
    recipe_hard_leather_pants,
    recipe_hardwood_plank,
    recipe_health_boost_potion,
    recipe_health_potion,
    recipe_health_splash_potion,
    recipe_heart_amulet,
    recipe_hell_armor,
    recipe_hell_helmet,
    recipe_hell_legs_armor,
    recipe_hell_reaper,
    recipe_hell_ring,
    recipe_hell_staff,
    recipe_hork_helmet,
    recipe_hunting_bow,
    recipe_iron_armor,
    recipe_iron_axe,
    recipe_iron_bar,
    recipe_iron_boots,
    recipe_iron_dagger,
    recipe_iron_helm,
    recipe_iron_legs_armor,
    recipe_iron_pickaxe,
    recipe_iron_ring,
    recipe_iron_shield,
    recipe_iron_sword,
    recipe_jester_hat,
    recipe_king_slime_sword,
    recipe_lava_underground_potion,
    recipe_leather_armor,
    recipe_leather_boots,
    recipe_leather_gloves,
    recipe_leather_hat,
    recipe_leather_legs_armor,
    recipe_life_amulet,
    recipe_life_ring,
    recipe_lightning_sword,
    recipe_lizard_boots,
    recipe_lizard_skin_armor,
    recipe_lizard_skin_legs_armor,
    recipe_lost_amulet,
    recipe_lucky_wizard_hat,
    recipe_magic_bow,
    recipe_magic_sap,
    recipe_magic_shield,
    recipe_magic_wizard_hat,
    recipe_magical_plank,
    recipe_malefic_armor,
    recipe_malefic_ring,
    recipe_maple_plank,
    recipe_maple_sap,
    recipe_maple_syrup,
    recipe_masterful_necklace,
    recipe_medic_armor,
    recipe_medic_skirt,
    recipe_mesh_armor,
    recipe_mesh_legs_armor,
    recipe_minor_health_potion,
    recipe_mithril_axe,
    recipe_mithril_bar,
    recipe_mithril_boots,
    recipe_mithril_fishing_rod,
    recipe_mithril_gloves,
    recipe_mithril_helm,
    recipe_mithril_pickaxe,
    recipe_mithril_platebody,
    recipe_mithril_platelegs,
    recipe_mithril_ring,
    recipe_mithril_shield,
    recipe_mithril_sword,
    recipe_moonlight_staff,
    recipe_mushmush_bow,
    recipe_mushmush_jacket,
    recipe_mushmush_wizard_hat,
    recipe_mushroom_soup,
    recipe_mushstaff,
    recipe_obsidian_armor,
    recipe_obsidian_bar,
    recipe_obsidian_battleaxe,
    recipe_obsidian_helmet,
    recipe_obsidian_legs_armor,
    recipe_palm_plank,
    recipe_perfect_bow,
    recipe_piggy_armor,
    recipe_piggy_helmet,
    recipe_piggy_pants,
    recipe_prospecting_amulet,
    recipe_recall_potion,
    recipe_red_dragon_armor,
    recipe_red_dragon_boots,
    recipe_red_dragon_legs_armor,
    recipe_red_dragon_shield,
    recipe_ring_of_chance,
    recipe_royal_skeleton_armor,
    recipe_royal_skeleton_helmet,
    recipe_royal_skeleton_pants,
    recipe_royal_skeleton_ring,
    recipe_ruby,
    recipe_ruby_amulet,
    recipe_ruby_ring,
    recipe_sacred_ring,
    recipe_sand_snakeskin_armor,
    recipe_sand_snakeskin_bandana,
    recipe_sand_snakeskin_boots,
    recipe_sand_snakeskin_pants,
    recipe_sandwhisper_potion,
    recipe_sap,
    recipe_sapphire,
    recipe_sapphire_amulet,
    recipe_sapphire_ring,
    recipe_satchel,
    recipe_shuriken,
    recipe_skeleton_armor,
    recipe_skeleton_helmet,
    recipe_skeleton_pants,
    recipe_skull_amulet,
    recipe_skull_ring,
    recipe_skull_staff,
    recipe_skull_wand,
    recipe_skullforged_armor,
    recipe_skullforged_pants,
    recipe_skullforged_ring,
    recipe_slime_shield,
    recipe_small_antidote,
    recipe_small_health_potion,
    recipe_snakeskin_armor,
    recipe_snakeskin_boots,
    recipe_snakeskin_legs_armor,
    recipe_spruce_fishing_rod,
    recipe_spruce_plank,
    recipe_steel_armor,
    recipe_steel_axe,
    recipe_steel_bar,
    recipe_steel_battleaxe,
    recipe_steel_boots,
    recipe_steel_fishing_rod,
    recipe_steel_gloves,
    recipe_steel_helm,
    recipe_steel_legs_armor,
    recipe_steel_pickaxe,
    recipe_steel_ring,
    recipe_sticky_dagger,
    recipe_sticky_sword,
    recipe_stormforged_armor,
    recipe_stormforged_pants,
    recipe_strangold_armor,
    recipe_strangold_bar,
    recipe_strangold_helmet,
    recipe_strangold_legs_armor,
    recipe_strangold_sword,
    recipe_topaz,
    recipe_topaz_amulet,
    recipe_topaz_ring,
    recipe_tromatising_mask,
    recipe_vampire_bow,
    recipe_vital_armor,
    recipe_vital_boots,
    recipe_water_boost_potion,
    recipe_water_bow,
    recipe_water_res_potion,
    recipe_water_ring,
    recipe_water_shield,
    recipe_white_knight_armor,
    recipe_white_knight_helmet,
    recipe_white_knight_pants,
    recipe_white_knight_shield,
    recipe_wisdom_amulet,
    recipe_wooden_shield,
    recipe_wooden_staff,
    recipe_wratharmor,
    recipe_wrathelmet,
    recipe_wrathpants,
    recipe_wrathsword
  ]

/-! ## Sanity theorems (live snapshot) -/

/-- The snapshot contains the expected number of recipes. -/
theorem snapshot_recipe_count : allRecipes.length = 321 := by
  rfl

/-! ## Fixture instantiation: prove a representative recipe is completable -/

/-- A fixture State with an items task whose target is the first recipe
    in `allRecipes` (lexicographic order). Demonstrates the Phase 23d-8
    universal applied to LIVE game-data shape. -/
noncomputable def fixtureFreshState : State where
  level := 1
  xp := 0
  taskProgress := 0
  taskTotal := 1
  inventoryUsed := 0
  inventoryMax := 30
  hp := 100
  maxHp := 100
  taskType := some "items"
  taskCode := some "adamantite_axe"
  projectedSkillXpDelta := 0
  targetSkillXp := 0
  gold := 0
  bankAccessible := true
  bankJunkNonempty := false
  bankUnlockMonsterPresent := false
  initialXp := 0
  unlockMonsterLevel := 0
  bankRequiredLevel := 0
  hasOverstockItems := false
  selectBankDepositsNonempty := false
  pendingItemsNonempty := false
  sellableInventoryNonempty := false
  recyclableSurplusNonempty := false
  taskCoinsTotal := 0
  taskExchangeMinCoins := 1
  lowYieldCancelFires := false
  taskCancelFires := false
  pursueTaskFires := false
  objectiveStepFires := false
  craftReliefFires := false
  restForCombatReady := false
  gearReviewFires := false
  bankItemsKnown := false
  bankItemsCount := 0
  bankCapacity := 0
  nextExpansionCost := 1
  taskLifecyclePhase := .accepted
  actionsAttempted := 0
  craftableSlots := 0
  taskFeasibleProjected := true
  -- Item 1g-A1: task pool tracking. Default empty for legacy fixtures
  -- (no pool-depletion reasoning); 1g-A2 populates from allRecipes.
  taskPool := []
  taskCodesSeen := []
  -- Item 4a: inventory composition + gather target. Legacy fixture
  -- defaults to empty + none.
  inventoryItems := []
  gatherTarget := none
  -- Item 4b: equipment composition. Legacy fixture: nothing equipped,
  -- no pending equip/unequip.
  equipment := []
  equipTarget := none
  unequipTarget := none
  -- Item 4c: position. Legacy fixture spawns at (0, 0); no pending move.
  posX := 0
  posY := 0
  moveTarget := none
  -- Item 4e: per-skill XP map + skill targets. Legacy fixture: empty
  -- map, no pending gather/craft skill.
  skillXpDelta := []
  gatherSkill := none
  craftSkill := none
  -- Item 8: state field gap closure. Legacy fixture defaults to empty
  -- maps + zero bank gold.
  skillLevels := []
  bankItemsCatalog := []
  bankGold := 0
  pendingItemCodes := []
  npcStock := []
  eventSpawns := []

/-- **Live-fixture items-task completable**.

    Instantiates Phase 23d-8 against the first live recipe.
    Witnesses an explicit K_gather + K_craft + K_taskTrade plan
    reaching `phase = .complete`. NO new axioms; pure
    instantiation of the universal theorem against LIVE data. -/
theorem live_first_recipe_completable :
    ∃ (K_gather K_craft K_taskTrade : Nat),
      (applyPlan
        ((List.replicate K_gather .gather)
          ++ (List.replicate K_craft .craft)
          ++ (List.replicate K_taskTrade .taskTrade))
        fixtureFreshState).taskLifecyclePhase = TaskLifecyclePhase.complete := by
  apply recipe_then_complete_reachable recipe_adamantite_axe fixtureFreshState
  · decide
  · decide
  · decide

/-! ## Live monster catalog (sorted by code) -/

def monster_baby_red_dragon : CatalogMonster :=
  { code := "baby_red_dragon", level := 50
    hp := 4500
    attackFire := 250, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 50, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def monster_bandit_lizard : CatalogMonster :=
  { code := "bandit_lizard", level := 25
    hp := 780
    attackFire := 40, attackEarth := 0, attackWater := 40, attackAir := 0
    resFire := -5, resEarth := 25, resWater := -5, resAir := 25
    crit := 5 }

def monster_bat : CatalogMonster :=
  { code := "bat", level := 38
    hp := 2000
    attackFire := 0, attackEarth := 0, attackWater := 80, attackAir := 80
    resFire := 5, resEarth := 5, resWater := 5, resAir := -20
    crit := 5 }

def monster_blue_slime : CatalogMonster :=
  { code := "blue_slime", level := 6
    hp := 120
    attackFire := 0, attackEarth := 0, attackWater := 15, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 25, resAir := 0
    crit := 0 }

def monster_chicken : CatalogMonster :=
  { code := "chicken", level := 1
    hp := 60
    attackFire := 0, attackEarth := 0, attackWater := 4, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def monster_corrupted_ogre : CatalogMonster :=
  { code := "corrupted_ogre", level := 20
    hp := 850
    attackFire := 0, attackEarth := 80, attackWater := 0, attackAir := 0
    resFire := 50, resEarth := 100, resWater := 70, resAir := 50
    crit := 5 }

def monster_corrupted_owlbear : CatalogMonster :=
  { code := "corrupted_owlbear", level := 30
    hp := 1500
    attackFire := 0, attackEarth := 0, attackWater := 115, attackAir := 0
    resFire := 70, resEarth := 50, resWater := 115, resAir := 70
    crit := 5 }

def monster_cow : CatalogMonster :=
  { code := "cow", level := 8
    hp := 280
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 21
    resFire := 0, resEarth := -30, resWater := 30, resAir := 0
    crit := 0 }

def monster_cultist_acolyte : CatalogMonster :=
  { code := "cultist_acolyte", level := 33
    hp := 1500
    attackFire := 0, attackEarth := 65, attackWater := 0, attackAir := 65
    resFire := -10, resEarth := 10, resWater := -10, resAir := 40
    crit := 5 }

def monster_cultist_alchemist : CatalogMonster :=
  { code := "cultist_alchemist", level := 40
    hp := 3000
    attackFire := 0, attackEarth := 0, attackWater := 50, attackAir := 100
    resFire := 5, resEarth := -10, resWater := 5, resAir := -30
    crit := 5 }

def monster_cultist_emperor : CatalogMonster :=
  { code := "cultist_emperor", level := 35
    hp := 1750
    attackFire := 0, attackEarth := 40, attackWater := 40, attackAir := 90
    resFire := 20, resEarth := 10, resWater := 0, resAir := -10
    crit := 5 }

def monster_cursed_tree : CatalogMonster :=
  { code := "cursed_tree", level := 34
    hp := 1550
    attackFire := 0, attackEarth := 0, attackWater := 130, attackAir := 0
    resFire := 5, resEarth := -5, resWater := -5, resAir := 5
    crit := 20 }

def monster_cyclops : CatalogMonster :=
  { code := "cyclops", level := 25
    hp := 850
    attackFire := 0, attackEarth := 105, attackWater := 0, attackAir := 25
    resFire := -20, resEarth := 20, resWater := 10, resAir := 0
    crit := 5 }

def monster_death_knight : CatalogMonster :=
  { code := "death_knight", level := 28
    hp := 820
    attackFire := 28, attackEarth := 28, attackWater := 28, attackAir := 28
    resFire := -5, resEarth := -5, resWater := -5, resAir := -5
    crit := 5 }

def monster_demon : CatalogMonster :=
  { code := "demon", level := 30
    hp := 1250
    attackFire := 110, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 20, resEarth := 0, resWater := -10, resAir := 0
    crit := 5 }

def monster_desert_scorpion : CatalogMonster :=
  { code := "desert_scorpion", level := 50
    hp := 4250
    attackFire := 0, attackEarth := 350, attackWater := 0, attackAir := 0
    resFire := -10, resEarth := 0, resWater := -10, resAir := 0
    crit := 50 }

def monster_dryad : CatalogMonster :=
  { code := "dryad", level := 40
    hp := 3000
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 140
    resFire := 10, resEarth := 10, resWater := 10, resAir := -10
    crit := 15 }

def monster_dusk_beetle : CatalogMonster :=
  { code := "dusk_beetle", level := 47
    hp := 3500
    attackFire := 120, attackEarth := 120, attackWater := 0, attackAir := 0
    resFire := 20, resEarth := -10, resWater := 20, resAir := -10
    crit := 5 }

def monster_duskworm : CatalogMonster :=
  { code := "duskworm", level := 48
    hp := 25000
    attackFire := 0, attackEarth := 0, attackWater := 550, attackAir := 0
    resFire := -80, resEarth := -80, resWater := -80, resAir := -80
    crit := 20 }

def monster_echoless_bat : CatalogMonster :=
  { code := "echoless_bat", level := 38
    hp := 2250
    attackFire := 80, attackEarth := 0, attackWater := 80, attackAir := 0
    resFire := -20, resEarth := 5, resWater := 5, resAir := 5
    crit := 5 }

def monster_efreet_sultan : CatalogMonster :=
  { code := "efreet_sultan", level := 42
    hp := 3600
    attackFire := 100, attackEarth := 0, attackWater := 0, attackAir := 100
    resFire := 50, resEarth := 0, resWater := 50, resAir := 0
    crit := 5 }

def monster_fennec : CatalogMonster :=
  { code := "fennec", level := 52
    hp := 5000
    attackFire := 0, attackEarth := 350, attackWater := 100, attackAir := 0
    resFire := -20, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def monster_flameche : CatalogMonster :=
  { code := "flameche", level := 52
    hp := 2000
    attackFire := 1250, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := -50, resAir := -50
    crit := 5 }

def monster_flying_snake : CatalogMonster :=
  { code := "flying_snake", level := 12
    hp := 360
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 34
    resFire := -20, resEarth := 0, resWater := -20, resAir := 40
    crit := 5 }

def monster_full_moon_vampire : CatalogMonster :=
  { code := "full_moon_vampire", level := 24
    hp := 760
    attackFire := 24, attackEarth := 0, attackWater := 40, attackAir := 0
    resFire := 0, resEarth := -15, resWater := -15, resAir := 30
    crit := 35 }

def monster_goblin : CatalogMonster :=
  { code := "goblin", level := 33
    hp := 1550
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 170
    resFire := 10, resEarth := 30, resWater := -20, resAir := -20
    crit := 5 }

def monster_goblin_guard : CatalogMonster :=
  { code := "goblin_guard", level := 35
    hp := 2300
    attackFire := 0, attackEarth := 140, attackWater := 0, attackAir := 0
    resFire := -20, resEarth := -20, resWater := 30, resAir := 20
    crit := 5 }

def monster_goblin_priestess : CatalogMonster :=
  { code := "goblin_priestess", level := 35
    hp := 6750
    attackFire := 75, attackEarth := 75, attackWater := 75, attackAir := 75
    resFire := 20, resEarth := 20, resWater := 20, resAir := 20
    crit := 20 }

def monster_goblin_wolfrider : CatalogMonster :=
  { code := "goblin_wolfrider", level := 40
    hp := 2650
    attackFire := 0, attackEarth := 145, attackWater := 0, attackAir := 0
    resFire := 10, resEarth := -5, resWater := 10, resAir := 10
    crit := 5 }

def monster_green_slime : CatalogMonster :=
  { code := "green_slime", level := 4
    hp := 80
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 12
    resFire := 0, resEarth := 0, resWater := 0, resAir := 25
    crit := 0 }

def monster_grimlet : CatalogMonster :=
  { code := "grimlet", level := 45
    hp := 7000
    attackFire := 0, attackEarth := 0, attackWater := 150, attackAir := 0
    resFire := 90, resEarth := 70, resWater := 90, resAir := 50
    crit := 5 }

def monster_hellhound : CatalogMonster :=
  { code := "hellhound", level := 40
    hp := 3250
    attackFire := 90, attackEarth := 50, attackWater := 0, attackAir := 0
    resFire := -20, resEarth := 10, resWater := -20, resAir := 10
    crit := 5 }

def monster_highwayman : CatalogMonster :=
  { code := "highwayman", level := 15
    hp := 380
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 25
    resFire := 10, resEarth := 10, resWater := -10, resAir := -10
    crit := 35 }

def monster_imp : CatalogMonster :=
  { code := "imp", level := 28
    hp := 1750
    attackFire := 0, attackEarth := 45, attackWater := 0, attackAir := 0
    resFire := 10, resEarth := 60, resWater := 10, resAir := 10
    crit := 5 }

def monster_king_slime : CatalogMonster :=
  { code := "king_slime", level := 15
    hp := 1000
    attackFire := 14, attackEarth := 14, attackWater := 14, attackAir := 14
    resFire := 20, resEarth := 20, resWater := 20, resAir := 20
    crit := 20 }

def monster_lich : CatalogMonster :=
  { code := "lich", level := 30
    hp := 6600
    attackFire := 140, attackEarth := 140, attackWater := 0, attackAir := 0
    resFire := 24, resEarth := 24, resWater := 18, resAir := 18
    crit := 5 }

def monster_mushmush : CatalogMonster :=
  { code := "mushmush", level := 10
    hp := 350
    attackFire := 16, attackEarth := 0, attackWater := 16, attackAir := 0
    resFire := 20, resEarth := 20, resWater := 0, resAir := -30
    crit := 5 }

def monster_ogre : CatalogMonster :=
  { code := "ogre", level := 20
    hp := 650
    attackFire := 0, attackEarth := 80, attackWater := 0, attackAir := 0
    resFire := -20, resEarth := 30, resWater := 0, resAir := 0
    crit := 5 }

def monster_orc : CatalogMonster :=
  { code := "orc", level := 38
    hp := 2100
    attackFire := 115, attackEarth := 0, attackWater := 0, attackAir := 115
    resFire := -20, resEarth := 20, resWater := -20, resAir := 20
    crit := 10 }

def monster_owlbear : CatalogMonster :=
  { code := "owlbear", level := 30
    hp := 1450
    attackFire := 0, attackEarth := 0, attackWater := 105, attackAir := 0
    resFire := 0, resEarth := -20, resWater := 45, resAir := 0
    crit := 5 }

def monster_pig : CatalogMonster :=
  { code := "pig", level := 19
    hp := 480
    attackFire := 0, attackEarth := 0, attackWater := 30, attackAir := 0
    resFire := 0, resEarth := -10, resWater := 40, resAir := 0
    crit := 30 }

def monster_pixie : CatalogMonster :=
  { code := "pixie", level := 40
    hp := 600000
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 675
    resFire := 10, resEarth := 5, resWater := 10, resAir := 5
    crit := 5 }

def monster_rat : CatalogMonster :=
  { code := "rat", level := 25
    hp := 800
    attackFire := 50, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 40, resEarth := -10, resWater := 5, resAir := 5
    crit := 50 }

def monster_red_dragon : CatalogMonster :=
  { code := "red_dragon", level := 51
    hp := 5000
    attackFire := 300, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 80, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def monster_red_slime : CatalogMonster :=
  { code := "red_slime", level := 7
    hp := 120
    attackFire := 18, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 25, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def monster_rosenblood : CatalogMonster :=
  { code := "rosenblood", level := 40
    hp := 8000
    attackFire := 400, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 10, resEarth := 10, resWater := 10, resAir := 10
    crit := 30 }

def monster_sand_snake : CatalogMonster :=
  { code := "sand_snake", level := 44
    hp := 3200
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 180
    resFire := 5, resEarth := 0, resWater := 5, resAir := 10
    crit := 5 }

def monster_sandwarden : CatalogMonster :=
  { code := "sandwarden", level := 50
    hp := 4500
    attackFire := 220, attackEarth := 0, attackWater := 0, attackAir := 220
    resFire := 0, resEarth := -20, resWater := 0, resAir := 0
    crit := 5 }

def monster_sandwhisper_empress : CatalogMonster :=
  { code := "sandwhisper_empress", level := 55
    hp := 13500
    attackFire := 400, attackEarth := 0, attackWater := 0, attackAir := 400
    resFire := 5, resEarth := 10, resWater := 10, resAir := 5
    crit := 5 }

def monster_sea_marauder : CatalogMonster :=
  { code := "sea_marauder", level := 45
    hp := 2900
    attackFire := 190, attackEarth := 0, attackWater := 0, attackAir := 190
    resFire := 10, resEarth := 10, resWater := 10, resAir := 10
    crit := 5 }

def monster_sheep : CatalogMonster :=
  { code := "sheep", level := 5
    hp := 120
    attackFire := 0, attackEarth := 14, attackWater := 0, attackAir := 0
    resFire := 10, resEarth := 10, resWater := 10, resAir := 10
    crit := 0 }

def monster_skeleton : CatalogMonster :=
  { code := "skeleton", level := 18
    hp := 480
    attackFire := 26, attackEarth := 18, attackWater := 0, attackAir := 0
    resFire := 30, resEarth := 0, resWater := -10, resAir := -10
    crit := 5 }

def monster_solar_desert_scorpion : CatalogMonster :=
  { code := "solar_desert_scorpion", level := 50
    hp := 4250
    attackFire := 400, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := -10, resWater := 0, resAir := -10
    crit := 75 }

def monster_sonnengott : CatalogMonster :=
  { code := "sonnengott", level := 55
    hp := 1500000
    attackFire := 1100, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := -20, resEarth := 10, resWater := -20, resAir := 5
    crit := 20 }

def monster_spider : CatalogMonster :=
  { code := "spider", level := 20
    hp := 550
    attackFire := 40, attackEarth := 0, attackWater := 40, attackAir := 0
    resFire := 0, resEarth := 5, resWater := -30, resAir := 5
    crit := 5 }

def monster_vampire : CatalogMonster :=
  { code := "vampire", level := 24
    hp := 680
    attackFire := 20, attackEarth := 0, attackWater := 0, attackAir := 50
    resFire := 0, resEarth := -15, resWater := -15, resAir := 30
    crit := 35 }

def monster_wolf : CatalogMonster :=
  { code := "wolf", level := 15
    hp := 400
    attackFire := 0, attackEarth := 0, attackWater := 12, attackAir := 12
    resFire := -10, resEarth := -10, resWater := 10, resAir := 10
    crit := 50 }

def monster_yellow_slime : CatalogMonster :=
  { code := "yellow_slime", level := 2
    hp := 70
    attackFire := 0, attackEarth := 8, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 25, resWater := 0, resAir := 0
    crit := 0 }

def monsterCatalog : List CatalogMonster :=
  [monster_baby_red_dragon, monster_bandit_lizard, monster_bat, monster_blue_slime, monster_chicken, monster_corrupted_ogre, monster_corrupted_owlbear, monster_cow, monster_cultist_acolyte, monster_cultist_alchemist, monster_cultist_emperor, monster_cursed_tree, monster_cyclops, monster_death_knight, monster_demon, monster_desert_scorpion, monster_dryad, monster_dusk_beetle, monster_duskworm, monster_echoless_bat, monster_efreet_sultan, monster_fennec, monster_flameche, monster_flying_snake, monster_full_moon_vampire, monster_goblin, monster_goblin_guard, monster_goblin_priestess, monster_goblin_wolfrider, monster_green_slime, monster_grimlet, monster_hellhound, monster_highwayman, monster_imp, monster_king_slime, monster_lich, monster_mushmush, monster_ogre, monster_orc, monster_owlbear, monster_pig, monster_pixie, monster_rat, monster_red_dragon, monster_red_slime, monster_rosenblood, monster_sand_snake, monster_sandwarden, monster_sandwhisper_empress, monster_sea_marauder, monster_sheep, monster_skeleton, monster_solar_desert_scorpion, monster_sonnengott, monster_spider, monster_vampire, monster_wolf, monster_yellow_slime]

/-! ## Character base stats by level (1..49) -/

def baseStats_1 : BaseStatsRow :=
  { level := 1, maxHp := 120
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_2 : BaseStatsRow :=
  { level := 2, maxHp := 125
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_3 : BaseStatsRow :=
  { level := 3, maxHp := 130
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_4 : BaseStatsRow :=
  { level := 4, maxHp := 135
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_5 : BaseStatsRow :=
  { level := 5, maxHp := 140
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_6 : BaseStatsRow :=
  { level := 6, maxHp := 145
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_7 : BaseStatsRow :=
  { level := 7, maxHp := 150
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_8 : BaseStatsRow :=
  { level := 8, maxHp := 155
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_9 : BaseStatsRow :=
  { level := 9, maxHp := 160
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_10 : BaseStatsRow :=
  { level := 10, maxHp := 165
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_11 : BaseStatsRow :=
  { level := 11, maxHp := 170
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_12 : BaseStatsRow :=
  { level := 12, maxHp := 175
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_13 : BaseStatsRow :=
  { level := 13, maxHp := 180
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_14 : BaseStatsRow :=
  { level := 14, maxHp := 185
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_15 : BaseStatsRow :=
  { level := 15, maxHp := 190
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_16 : BaseStatsRow :=
  { level := 16, maxHp := 195
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_17 : BaseStatsRow :=
  { level := 17, maxHp := 200
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_18 : BaseStatsRow :=
  { level := 18, maxHp := 205
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_19 : BaseStatsRow :=
  { level := 19, maxHp := 210
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_20 : BaseStatsRow :=
  { level := 20, maxHp := 215
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_21 : BaseStatsRow :=
  { level := 21, maxHp := 220
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_22 : BaseStatsRow :=
  { level := 22, maxHp := 225
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_23 : BaseStatsRow :=
  { level := 23, maxHp := 230
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_24 : BaseStatsRow :=
  { level := 24, maxHp := 235
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_25 : BaseStatsRow :=
  { level := 25, maxHp := 240
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_26 : BaseStatsRow :=
  { level := 26, maxHp := 245
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_27 : BaseStatsRow :=
  { level := 27, maxHp := 250
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_28 : BaseStatsRow :=
  { level := 28, maxHp := 255
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_29 : BaseStatsRow :=
  { level := 29, maxHp := 260
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_30 : BaseStatsRow :=
  { level := 30, maxHp := 265
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_31 : BaseStatsRow :=
  { level := 31, maxHp := 270
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_32 : BaseStatsRow :=
  { level := 32, maxHp := 275
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_33 : BaseStatsRow :=
  { level := 33, maxHp := 280
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_34 : BaseStatsRow :=
  { level := 34, maxHp := 285
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_35 : BaseStatsRow :=
  { level := 35, maxHp := 290
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_36 : BaseStatsRow :=
  { level := 36, maxHp := 295
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_37 : BaseStatsRow :=
  { level := 37, maxHp := 300
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_38 : BaseStatsRow :=
  { level := 38, maxHp := 305
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_39 : BaseStatsRow :=
  { level := 39, maxHp := 310
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_40 : BaseStatsRow :=
  { level := 40, maxHp := 315
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_41 : BaseStatsRow :=
  { level := 41, maxHp := 320
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_42 : BaseStatsRow :=
  { level := 42, maxHp := 325
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_43 : BaseStatsRow :=
  { level := 43, maxHp := 330
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_44 : BaseStatsRow :=
  { level := 44, maxHp := 335
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_45 : BaseStatsRow :=
  { level := 45, maxHp := 340
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_46 : BaseStatsRow :=
  { level := 46, maxHp := 345
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_47 : BaseStatsRow :=
  { level := 47, maxHp := 350
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_48 : BaseStatsRow :=
  { level := 48, maxHp := 355
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStats_49 : BaseStatsRow :=
  { level := 49, maxHp := 360
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0, initiative := 100 }

def baseStatsTable : List BaseStatsRow :=
  [baseStats_1, baseStats_2, baseStats_3, baseStats_4, baseStats_5, baseStats_6, baseStats_7, baseStats_8, baseStats_9, baseStats_10, baseStats_11, baseStats_12, baseStats_13, baseStats_14, baseStats_15, baseStats_16, baseStats_17, baseStats_18, baseStats_19, baseStats_20, baseStats_21, baseStats_22, baseStats_23, baseStats_24, baseStats_25, baseStats_26, baseStats_27, baseStats_28, baseStats_29, baseStats_30, baseStats_31, baseStats_32, baseStats_33, baseStats_34, baseStats_35, baseStats_36, baseStats_37, baseStats_38, baseStats_39, baseStats_40, baseStats_41, baseStats_42, baseStats_43, baseStats_44, baseStats_45, baseStats_46, baseStats_47, baseStats_48, baseStats_49]

/-! ## Equippable item catalog (sorted by code) -/

def item_adamantite_axe : CatalogItem :=
  { code := "adamantite_axe", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adamantite_boots : CatalogItem :=
  { code := "adamantite_boots", level := 50, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 8, resEarth := 0, resWater := 0, resAir := 8
    crit := 0 }

def item_adamantite_fishing_rod : CatalogItem :=
  { code := "adamantite_fishing_rod", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adamantite_gloves : CatalogItem :=
  { code := "adamantite_gloves", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 5
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adamantite_mask : CatalogItem :=
  { code := "adamantite_mask", level := 50, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 5, resWater := 0, resAir := 0
    crit := 5 }

def item_adamantite_pickaxe : CatalogItem :=
  { code := "adamantite_pickaxe", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adamantite_platebody : CatalogItem :=
  { code := "adamantite_platebody", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 5, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adamantite_platelegs : CatalogItem :=
  { code := "adamantite_platelegs", level := 50, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 5, resEarth := 7, resWater := 0, resAir := 0
    crit := 3 }

def item_adamantite_ring : CatalogItem :=
  { code := "adamantite_ring", level := 50, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 7 }

def item_adamantite_shield : CatalogItem :=
  { code := "adamantite_shield", level := 50, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 18, resEarth := 0, resWater := 0, resAir := 18
    crit := 0 }

def item_adamantite_sword : CatalogItem :=
  { code := "adamantite_sword", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 115
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_adventurer_boots : CatalogItem :=
  { code := "adventurer_boots", level := 15, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 60
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adventurer_helmet : CatalogItem :=
  { code := "adventurer_helmet", level := 10, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adventurer_pants : CatalogItem :=
  { code := "adventurer_pants", level := 15, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 60
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_adventurer_vest : CatalogItem :=
  { code := "adventurer_vest", level := 10, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 60
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_air_and_water_amulet : CatalogItem :=
  { code := "air_and_water_amulet", level := 10, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_air_boost_potion : CatalogItem :=
  { code := "air_boost_potion", level := 10, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_air_res_potion : CatalogItem :=
  { code := "air_res_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 10
    crit := 0 }

def item_air_ring : CatalogItem :=
  { code := "air_ring", level := 15, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_air_shield : CatalogItem :=
  { code := "air_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := -5, resEarth := 0, resWater := 0, resAir := 25
    crit := 0 }

def item_amulet_of_the_grand_master : CatalogItem :=
  { code := "amulet_of_the_grand_master", level := 50, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 175
    resFire := -5, resEarth := -5, resWater := -5, resAir := -5
    crit := 8 }

def item_ancestral_talisman : CatalogItem :=
  { code := "ancestral_talisman", level := 35, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_ancient_jean : CatalogItem :=
  { code := "ancient_jean", level := 35, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := -10, resEarth := 10, resWater := 0, resAir := 0
    crit := 6 }

def item_antidote : CatalogItem :=
  { code := "antidote", level := 30, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_apprentice_gloves : CatalogItem :=
  { code := "apprentice_gloves", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 5
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_backpack : CatalogItem :=
  { code := "backpack", level := 10, slotType := "bag"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_bandit_armor : CatalogItem :=
  { code := "bandit_armor", level := 25, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 6, resWater := 6, resAir := 0
    crit := 5 }

def item_battlestaff : CatalogItem :=
  { code := "battlestaff", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 40, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_batwing_helmet : CatalogItem :=
  { code := "batwing_helmet", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := -5, resEarth := -5, resWater := 0, resAir := 0
    crit := 8 }

def item_blade_of_hell : CatalogItem :=
  { code := "blade_of_hell", level := 45, slotType := "weapon"
    attackFire := 0, attackEarth := 115, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_bloodblade : CatalogItem :=
  { code := "bloodblade", level := 40, slotType := "weapon"
    attackFire := 70, attackEarth := 0, attackWater := 0, attackAir := 30
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_bow_from_hell : CatalogItem :=
  { code := "bow_from_hell", level := 45, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 106
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_burn_rune : CatalogItem :=
  { code := "burn_rune", level := 20, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_celest_ring : CatalogItem :=
  { code := "celest_ring", level := 40, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_conjurer_cloak : CatalogItem :=
  { code := "conjurer_cloak", level := 30, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_conjurer_skirt : CatalogItem :=
  { code := "conjurer_skirt", level := 30, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_copper_armor : CatalogItem :=
  { code := "copper_armor", level := 5, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 25
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_axe : CatalogItem :=
  { code := "copper_axe", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_boots : CatalogItem :=
  { code := "copper_boots", level := 1, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 10
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_dagger : CatalogItem :=
  { code := "copper_dagger", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 6
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_copper_helmet : CatalogItem :=
  { code := "copper_helmet", level := 1, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_legs_armor : CatalogItem :=
  { code := "copper_legs_armor", level := 5, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 25
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_pickaxe : CatalogItem :=
  { code := "copper_pickaxe", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_copper_ring : CatalogItem :=
  { code := "copper_ring", level := 1, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_corrupted_crown : CatalogItem :=
  { code := "corrupted_crown", level := 45, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 350
    resFire := 5, resEarth := 5, resWater := 5, resAir := 5
    crit := 0 }

def item_corrupted_skull : CatalogItem :=
  { code := "corrupted_skull", level := 25, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 8 }

def item_corrupted_stone_amulet : CatalogItem :=
  { code := "corrupted_stone_amulet", level := 35, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_cultist_boots : CatalogItem :=
  { code := "cultist_boots", level := 40, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 8, resAir := 8
    crit := 0 }

def item_cultist_cloak : CatalogItem :=
  { code := "cultist_cloak", level := 40, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 0, resEarth := 0, resWater := 7, resAir := 7
    crit := 0 }

def item_cultist_hat : CatalogItem :=
  { code := "cultist_hat", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_cultist_pants : CatalogItem :=
  { code := "cultist_pants", level := 40, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 7, resEarth := 0, resWater := 7, resAir := 0
    crit := 0 }

def item_cursed_hat : CatalogItem :=
  { code := "cursed_hat", level := 35, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_cursed_sceptre : CatalogItem :=
  { code := "cursed_sceptre", level := 35, slotType := "weapon"
    attackFire := 82, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_dark_horned_helmet : CatalogItem :=
  { code := "dark_horned_helmet", level := 50, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 5, resWater := 0, resAir := 0
    crit := 8 }

def item_darkforged_boots : CatalogItem :=
  { code := "darkforged_boots", level := 45, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 7 }

def item_darkforged_helmet : CatalogItem :=
  { code := "darkforged_helmet", level := 45, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_darkforged_plate : CatalogItem :=
  { code := "darkforged_plate", level := 45, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_darkforged_shield : CatalogItem :=
  { code := "darkforged_shield", level := 45, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 13, resEarth := 13, resWater := 13, resAir := 13
    crit := 0 }

def item_death_knight_sword : CatalogItem :=
  { code := "death_knight_sword", level := 30, slotType := "weapon"
    attackFire := 37, attackEarth := 37, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_demoniac_dagger : CatalogItem :=
  { code := "demoniac_dagger", level := 45, slotType := "weapon"
    attackFire := 85, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_demoniac_shield : CatalogItem :=
  { code := "demoniac_shield", level := 45, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 15, resEarth := 15, resWater := 15, resAir := 15
    crit := 0 }

def item_desert_whip : CatalogItem :=
  { code := "desert_whip", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 125, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_desert_wrap : CatalogItem :=
  { code := "desert_wrap", level := 50, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 7, resEarth := 0, resWater := 0, resAir := 7
    crit := 0 }

def item_diabolic_elixir : CatalogItem :=
  { code := "diabolic_elixir", level := 45, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 12, resEarth := 12, resWater := 12, resAir := 12
    crit := 0 }

def item_diamond_amulet : CatalogItem :=
  { code := "diamond_amulet", level := 35, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_diamond_armor : CatalogItem :=
  { code := "diamond_armor", level := 40, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_diamond_skirt : CatalogItem :=
  { code := "diamond_skirt", level := 40, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_diamond_sword : CatalogItem :=
  { code := "diamond_sword", level := 35, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 75, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_divinity_ring : CatalogItem :=
  { code := "divinity_ring", level := 40, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_dreadful_amulet : CatalogItem :=
  { code := "dreadful_amulet", level := 20, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_dreadful_armor : CatalogItem :=
  { code := "dreadful_armor", level := 35, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 0, resEarth := 0, resWater := 10, resAir := 0
    crit := 5 }

def item_dreadful_battleaxe : CatalogItem :=
  { code := "dreadful_battleaxe", level := 35, slotType := "weapon"
    attackFire := 0, attackEarth := 20, attackWater := 65, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_dreadful_ring : CatalogItem :=
  { code := "dreadful_ring", level := 20, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_dreadful_shield : CatalogItem :=
  { code := "dreadful_shield", level := 35, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := -5, resEarth := 15, resWater := 15, resAir := -5
    crit := 0 }

def item_dreadful_staff : CatalogItem :=
  { code := "dreadful_staff", level := 25, slotType := "weapon"
    attackFire := 0, attackEarth := 25, attackWater := 25, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_duskarmor : CatalogItem :=
  { code := "duskarmor", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 5, resWater := 0, resAir := 0
    crit := 0 }

def item_duskpants : CatalogItem :=
  { code := "duskpants", level := 50, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 5, resWater := 7, resAir := 0
    crit := 7 }

def item_dust_amulet : CatalogItem :=
  { code := "dust_amulet", level := 50, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_dust_helmet : CatalogItem :=
  { code := "dust_helmet", level := 50, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 7, resWater := 7, resAir := 0
    crit := 0 }

def item_dust_sword : CatalogItem :=
  { code := "dust_sword", level := 50, slotType := "weapon"
    attackFire := 115, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_earth_boost_potion : CatalogItem :=
  { code := "earth_boost_potion", level := 10, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_earth_res_potion : CatalogItem :=
  { code := "earth_res_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 10, resWater := 0, resAir := 0
    crit := 0 }

def item_earth_ring : CatalogItem :=
  { code := "earth_ring", level := 15, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_earth_shield : CatalogItem :=
  { code := "earth_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 25, resWater := -10, resAir := 0
    crit := 0 }

def item_elderwood_staff : CatalogItem :=
  { code := "elderwood_staff", level := 30, slotType := "weapon"
    attackFire := 40, attackEarth := 0, attackWater := 40, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_emerald_amulet : CatalogItem :=
  { code := "emerald_amulet", level := 25, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 70
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_emerald_book : CatalogItem :=
  { code := "emerald_book", level := 40, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_emerald_ring : CatalogItem :=
  { code := "emerald_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_enchanted_rune : CatalogItem :=
  { code := "enchanted_rune", level := 40, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enchanter_boots : CatalogItem :=
  { code := "enchanter_boots", level := 35, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 110
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enchanter_pants : CatalogItem :=
  { code := "enchanter_pants", level := 35, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 10, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enhanced_antidote : CatalogItem :=
  { code := "enhanced_antidote", level := 45, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enhanced_boost_potion : CatalogItem :=
  { code := "enhanced_boost_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enhanced_health_potion : CatalogItem :=
  { code := "enhanced_health_potion", level := 45, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_enhanced_health_splash_potion : CatalogItem :=
  { code := "enhanced_health_splash_potion", level := 50, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_eternal_red_ring : CatalogItem :=
  { code := "eternal_red_ring", level := 50, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_eternity_ring : CatalogItem :=
  { code := "eternity_ring", level := 40, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_feather_coat : CatalogItem :=
  { code := "feather_coat", level := 5, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 25
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_fire_and_earth_amulet : CatalogItem :=
  { code := "fire_and_earth_amulet", level := 10, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_fire_boost_potion : CatalogItem :=
  { code := "fire_boost_potion", level := 10, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_fire_bow : CatalogItem :=
  { code := "fire_bow", level := 10, slotType := "weapon"
    attackFire := 17, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_fire_res_potion : CatalogItem :=
  { code := "fire_res_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 10, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_fire_ring : CatalogItem :=
  { code := "fire_ring", level := 15, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_fire_shield : CatalogItem :=
  { code := "fire_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 25, resEarth := 0, resWater := 0, resAir := -5
    crit := 0 }

def item_fire_staff : CatalogItem :=
  { code := "fire_staff", level := 5, slotType := "weapon"
    attackFire := 16, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_fishing_net : CatalogItem :=
  { code := "fishing_net", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_flying_boots : CatalogItem :=
  { code := "flying_boots", level := 30, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_forest_ring : CatalogItem :=
  { code := "forest_ring", level := 10, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_forest_staff : CatalogItem :=
  { code := "forest_staff", level := 10, slotType := "weapon"
    attackFire := 12, attackEarth := 12, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_forest_whip : CatalogItem :=
  { code := "forest_whip", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 40
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_goblin_guard_shield : CatalogItem :=
  { code := "goblin_guard_shield", level := 35, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 15, resEarth := -5, resWater := -5, resAir := 15
    crit := 0 }

def item_gold_axe : CatalogItem :=
  { code := "gold_axe", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_boots : CatalogItem :=
  { code := "gold_boots", level := 30, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 110
    resFire := 0, resEarth := 8, resWater := 0, resAir := 8
    crit := 0 }

def item_gold_fishing_rod : CatalogItem :=
  { code := "gold_fishing_rod", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_helm : CatalogItem :=
  { code := "gold_helm", level := 30, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_mask : CatalogItem :=
  { code := "gold_mask", level := 30, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_pickaxe : CatalogItem :=
  { code := "gold_pickaxe", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_platebody : CatalogItem :=
  { code := "gold_platebody", level := 30, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 6, resWater := 6, resAir := 0
    crit := 0 }

def item_gold_platelegs : CatalogItem :=
  { code := "gold_platelegs", level := 30, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 7, resWater := 0, resAir := 7
    crit := 0 }

def item_gold_ring : CatalogItem :=
  { code := "gold_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_gold_shield : CatalogItem :=
  { code := "gold_shield", level := 30, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 10, resEarth := 10, resWater := 10, resAir := 10
    crit := 0 }

def item_gold_sword : CatalogItem :=
  { code := "gold_sword", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 60, attackWater := 0, attackAir := 20
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_golden_gloves : CatalogItem :=
  { code := "golden_gloves", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_dreadful_amulet : CatalogItem :=
  { code := "greater_dreadful_amulet", level := 30, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_dreadful_staff : CatalogItem :=
  { code := "greater_dreadful_staff", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 20, attackWater := 60, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_greater_emerald_amulet : CatalogItem :=
  { code := "greater_emerald_amulet", level := 40, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 130
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_greater_healing_rune : CatalogItem :=
  { code := "greater_healing_rune", level := 40, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_health_potion : CatalogItem :=
  { code := "greater_health_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_lifesteal_rune : CatalogItem :=
  { code := "greater_lifesteal_rune", level := 40, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_protection_rune : CatalogItem :=
  { code := "greater_protection_rune", level := 40, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_greater_ruby_amulet : CatalogItem :=
  { code := "greater_ruby_amulet", level := 40, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 130
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_greater_sapphire_amulet : CatalogItem :=
  { code := "greater_sapphire_amulet", level := 40, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 130
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_greater_topaz_amulet : CatalogItem :=
  { code := "greater_topaz_amulet", level := 40, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 130
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_greater_wooden_staff : CatalogItem :=
  { code := "greater_wooden_staff", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 24, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_hard_leather_armor : CatalogItem :=
  { code := "hard_leather_armor", level := 20, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 5, resEarth := 0, resWater := 0, resAir := 5
    crit := 0 }

def item_hard_leather_boots : CatalogItem :=
  { code := "hard_leather_boots", level := 20, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 45
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_hard_leather_helmet : CatalogItem :=
  { code := "hard_leather_helmet", level := 20, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_hard_leather_pants : CatalogItem :=
  { code := "hard_leather_pants", level := 20, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 0, resAir := 6
    crit := 0 }

def item_healing_aura_rune : CatalogItem :=
  { code := "healing_aura_rune", level := 20, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_healing_rune : CatalogItem :=
  { code := "healing_rune", level := 20, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_health_boost_potion : CatalogItem :=
  { code := "health_boost_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 250
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_health_potion : CatalogItem :=
  { code := "health_potion", level := 30, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_health_splash_potion : CatalogItem :=
  { code := "health_splash_potion", level := 30, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_heart_amulet : CatalogItem :=
  { code := "heart_amulet", level := 50, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 350
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_hell_armor : CatalogItem :=
  { code := "hell_armor", level := 45, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 250
    resFire := -10, resEarth := -10, resWater := -10, resAir := -10
    crit := 5 }

def item_hell_helmet : CatalogItem :=
  { code := "hell_helmet", level := 45, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 260
    resFire := -10, resEarth := -10, resWater := -10, resAir := -10
    crit := 8 }

def item_hell_legs_armor : CatalogItem :=
  { code := "hell_legs_armor", level := 45, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 240
    resFire := -10, resEarth := -10, resWater := -10, resAir := -10
    crit := 7 }

def item_hell_reaper : CatalogItem :=
  { code := "hell_reaper", level := 45, slotType := "weapon"
    attackFire := 65, attackEarth := 0, attackWater := 65, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 10 }

def item_hell_ring : CatalogItem :=
  { code := "hell_ring", level := 45, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := -10, resEarth := -10, resWater := -10, resAir := -10
    crit := 5 }

def item_hell_staff : CatalogItem :=
  { code := "hell_staff", level := 45, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 115, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_highwayman_dagger : CatalogItem :=
  { code := "highwayman_dagger", level := 15, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 23
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_hork_helmet : CatalogItem :=
  { code := "hork_helmet", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := -5, resAir := -5
    crit := 8 }

def item_hunting_bow : CatalogItem :=
  { code := "hunting_bow", level := 20, slotType := "weapon"
    attackFire := 14, attackEarth := 0, attackWater := 0, attackAir := 15
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_iron_armor : CatalogItem :=
  { code := "iron_armor", level := 10, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 2, resAir := 2
    crit := 0 }

def item_iron_axe : CatalogItem :=
  { code := "iron_axe", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_iron_boots : CatalogItem :=
  { code := "iron_boots", level := 10, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 0, resEarth := 0, resWater := 5, resAir := 5
    crit := 0 }

def item_iron_dagger : CatalogItem :=
  { code := "iron_dagger", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 17
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_iron_helm : CatalogItem :=
  { code := "iron_helm", level := 10, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 4, resEarth := 4, resWater := 0, resAir := 0
    crit := 0 }

def item_iron_legs_armor : CatalogItem :=
  { code := "iron_legs_armor", level := 10, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_iron_pickaxe : CatalogItem :=
  { code := "iron_pickaxe", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_iron_ring : CatalogItem :=
  { code := "iron_ring", level := 10, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_iron_shield : CatalogItem :=
  { code := "iron_shield", level := 10, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 4, resEarth := 4, resWater := 4, resAir := 4
    crit := 0 }

def item_iron_sword : CatalogItem :=
  { code := "iron_sword", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 24, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_jester_hat : CatalogItem :=
  { code := "jester_hat", level := 35, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 10 }

def item_king_slime_sword : CatalogItem :=
  { code := "king_slime_sword", level := 15, slotType := "weapon"
    attackFire := 9, attackEarth := 9, attackWater := 9, attackAir := 9
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_leather_armor : CatalogItem :=
  { code := "leather_armor", level := 10, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 2, resEarth := 2, resWater := 0, resAir := 0
    crit := 0 }

def item_leather_boots : CatalogItem :=
  { code := "leather_boots", level := 10, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 5, resEarth := 5, resWater := 0, resAir := 0
    crit := 0 }

def item_leather_gloves : CatalogItem :=
  { code := "leather_gloves", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 5
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_leather_hat : CatalogItem :=
  { code := "leather_hat", level := 10, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 0, resEarth := 0, resWater := 4, resAir := 4
    crit := 0 }

def item_leather_legs_armor : CatalogItem :=
  { code := "leather_legs_armor", level := 10, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_lich_crown : CatalogItem :=
  { code := "lich_crown", level := 30, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_life_amulet : CatalogItem :=
  { code := "life_amulet", level := 5, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 30
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_life_crystal : CatalogItem :=
  { code := "life_crystal", level := 30, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_life_ring : CatalogItem :=
  { code := "life_ring", level := 15, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 25
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_lifesteal_rune : CatalogItem :=
  { code := "lifesteal_rune", level := 20, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_lightning_sword : CatalogItem :=
  { code := "lightning_sword", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 22, attackWater := 0, attackAir := 50
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_lizard_boots : CatalogItem :=
  { code := "lizard_boots", level := 30, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 110
    resFire := 8, resEarth := 0, resWater := 0, resAir := 8
    crit := 0 }

def item_lizard_skin_armor : CatalogItem :=
  { code := "lizard_skin_armor", level := 25, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 5, resEarth := 0, resWater := 10, resAir := 0
    crit := 0 }

def item_lizard_skin_legs_armor : CatalogItem :=
  { code := "lizard_skin_legs_armor", level := 25, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 140
    resFire := 3, resEarth := 0, resWater := 6, resAir := 0
    crit := 0 }

def item_lost_amulet : CatalogItem :=
  { code := "lost_amulet", level := 30, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_lost_world_map : CatalogItem :=
  { code := "lost_world_map", level := 20, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_lucky_wizard_hat : CatalogItem :=
  { code := "lucky_wizard_hat", level := 15, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_magic_bow : CatalogItem :=
  { code := "magic_bow", level := 35, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 14, attackAir := 47
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_magic_shield : CatalogItem :=
  { code := "magic_shield", level := 50, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 18, resWater := 18, resAir := 0
    crit := 0 }

def item_magic_wizard_hat : CatalogItem :=
  { code := "magic_wizard_hat", level := 20, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_malefic_armor : CatalogItem :=
  { code := "malefic_armor", level := 35, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 10, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_malefic_crystal : CatalogItem :=
  { code := "malefic_crystal", level := 35, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_malefic_ring : CatalogItem :=
  { code := "malefic_ring", level := 35, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 7 }

def item_masterful_necklace : CatalogItem :=
  { code := "masterful_necklace", level := 35, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_medic_armor : CatalogItem :=
  { code := "medic_armor", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 400
    resFire := 7, resEarth := 7, resWater := 0, resAir := 0
    crit := 0 }

def item_medic_skirt : CatalogItem :=
  { code := "medic_skirt", level := 50, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 500
    resFire := 0, resEarth := 6, resWater := 0, resAir := 6
    crit := 0 }

def item_mesh_armor : CatalogItem :=
  { code := "mesh_armor", level := 45, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 7, resAir := 7
    crit := 7 }

def item_mesh_legs_armor : CatalogItem :=
  { code := "mesh_legs_armor", level := 45, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_minor_health_potion : CatalogItem :=
  { code := "minor_health_potion", level := 20, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_axe : CatalogItem :=
  { code := "mithril_axe", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_boots : CatalogItem :=
  { code := "mithril_boots", level := 40, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 8, resEarth := 8, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_fishing_rod : CatalogItem :=
  { code := "mithril_fishing_rod", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_gloves : CatalogItem :=
  { code := "mithril_gloves", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 5
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_helm : CatalogItem :=
  { code := "mithril_helm", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 6, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_pickaxe : CatalogItem :=
  { code := "mithril_pickaxe", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_platebody : CatalogItem :=
  { code := "mithril_platebody", level := 40, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 8, resEarth := 8, resWater := 0, resAir := 0
    crit := 0 }

def item_mithril_platelegs : CatalogItem :=
  { code := "mithril_platelegs", level := 40, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 250
    resFire := 7, resEarth := 0, resWater := 0, resAir := 7
    crit := 0 }

def item_mithril_ring : CatalogItem :=
  { code := "mithril_ring", level := 40, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 175
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 4 }

def item_mithril_shield : CatalogItem :=
  { code := "mithril_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 15, resEarth := 0, resWater := 0, resAir := 15
    crit := 0 }

def item_mithril_sword : CatalogItem :=
  { code := "mithril_sword", level := 40, slotType := "weapon"
    attackFire := 30, attackEarth := 0, attackWater := 70, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_moonlight_staff : CatalogItem :=
  { code := "moonlight_staff", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 96, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_mushmush_bow : CatalogItem :=
  { code := "mushmush_bow", level := 15, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 12, attackAir := 12
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_mushmush_jacket : CatalogItem :=
  { code := "mushmush_jacket", level := 15, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 60
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_mushmush_wizard_hat : CatalogItem :=
  { code := "mushmush_wizard_hat", level := 15, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_mushstaff : CatalogItem :=
  { code := "mushstaff", level := 15, slotType := "weapon"
    attackFire := 15, attackEarth := 15, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 24 }

def item_novice_guide : CatalogItem :=
  { code := "novice_guide", level := 10, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 25
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_obsidian_armor : CatalogItem :=
  { code := "obsidian_armor", level := 30, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 8, resEarth := 0, resWater := 5, resAir := 0
    crit := 0 }

def item_obsidian_battleaxe : CatalogItem :=
  { code := "obsidian_battleaxe", level := 30, slotType := "weapon"
    attackFire := 0, attackEarth := 80, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_obsidian_helmet : CatalogItem :=
  { code := "obsidian_helmet", level := 30, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 5, resEarth := 5, resWater := 0, resAir := 0
    crit := 0 }

def item_obsidian_legs_armor : CatalogItem :=
  { code := "obsidian_legs_armor", level := 30, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_old_boots : CatalogItem :=
  { code := "old_boots", level := 20, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_perfect_bow : CatalogItem :=
  { code := "perfect_bow", level := 30, slotType := "weapon"
    attackFire := 53, attackEarth := 0, attackWater := 15, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_perfect_pearl : CatalogItem :=
  { code := "perfect_pearl", level := 20, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_piggy_armor : CatalogItem :=
  { code := "piggy_armor", level := 25, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 10, resEarth := 5, resWater := 0, resAir := 0
    crit := 0 }

def item_piggy_helmet : CatalogItem :=
  { code := "piggy_helmet", level := 25, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 110
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_piggy_pants : CatalogItem :=
  { code := "piggy_pants", level := 25, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 140
    resFire := 6, resEarth := 0, resWater := 3, resAir := 0
    crit := 0 }

def item_powerful_rune : CatalogItem :=
  { code := "powerful_rune", level := 50, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_prospecting_amulet : CatalogItem :=
  { code := "prospecting_amulet", level := 30, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_protection_rune : CatalogItem :=
  { code := "protection_rune", level := 20, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_red_dragon_armor : CatalogItem :=
  { code := "red_dragon_armor", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 0, resWater := 5, resAir := 0
    crit := 0 }

def item_red_dragon_boots : CatalogItem :=
  { code := "red_dragon_boots", level := 50, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_red_dragon_legs_armor : CatalogItem :=
  { code := "red_dragon_legs_armor", level := 50, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 8, resEarth := 0, resWater := 3, resAir := 0
    crit := 3 }

def item_red_dragon_shield : CatalogItem :=
  { code := "red_dragon_shield", level := 50, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 100
    resFire := 18, resEarth := 0, resWater := 18, resAir := 0
    crit := 0 }

def item_ring_of_chance : CatalogItem :=
  { code := "ring_of_chance", level := 20, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 30
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 4 }

def item_ring_of_the_adept : CatalogItem :=
  { code := "ring_of_the_adept", level := 25, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 50
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_royal_skeleton_armor : CatalogItem :=
  { code := "royal_skeleton_armor", level := 30, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 6, resEarth := 0, resWater := 0, resAir := 6
    crit := 0 }

def item_royal_skeleton_helmet : CatalogItem :=
  { code := "royal_skeleton_helmet", level := 30, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 160
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_royal_skeleton_pants : CatalogItem :=
  { code := "royal_skeleton_pants", level := 30, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 7, resWater := 7, resAir := 0
    crit := 0 }

def item_royal_skeleton_ring : CatalogItem :=
  { code := "royal_skeleton_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 70
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_ruby_amulet : CatalogItem :=
  { code := "ruby_amulet", level := 25, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 70
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_ruby_book : CatalogItem :=
  { code := "ruby_book", level := 40, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_ruby_ring : CatalogItem :=
  { code := "ruby_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_sacred_ring : CatalogItem :=
  { code := "sacred_ring", level := 40, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sand_snakeskin_armor : CatalogItem :=
  { code := "sand_snakeskin_armor", level := 45, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 230
    resFire := 0, resEarth := 0, resWater := 7, resAir := 7
    crit := 3 }

def item_sand_snakeskin_bandana : CatalogItem :=
  { code := "sand_snakeskin_bandana", level := 45, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 260
    resFire := 0, resEarth := 0, resWater := 5, resAir := 0
    crit := 0 }

def item_sand_snakeskin_boots : CatalogItem :=
  { code := "sand_snakeskin_boots", level := 45, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 240
    resFire := 0, resEarth := 0, resWater := 8, resAir := 8
    crit := 5 }

def item_sand_snakeskin_pants : CatalogItem :=
  { code := "sand_snakeskin_pants", level := 45, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 230
    resFire := 5, resEarth := 0, resWater := 5, resAir := 0
    crit := 0 }

def item_sandwhisper_bag : CatalogItem :=
  { code := "sandwhisper_bag", level := 50, slotType := "bag"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sandwhisper_codex : CatalogItem :=
  { code := "sandwhisper_codex", level := 50, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sanguine_edge_of_rosen : CatalogItem :=
  { code := "sanguine_edge_of_rosen", level := 40, slotType := "weapon"
    attackFire := 25, attackEarth := 75, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_sapphire_amulet : CatalogItem :=
  { code := "sapphire_amulet", level := 25, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 70
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sapphire_book : CatalogItem :=
  { code := "sapphire_book", level := 40, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sapphire_ring : CatalogItem :=
  { code := "sapphire_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_satchel : CatalogItem :=
  { code := "satchel", level := 5, slotType := "bag"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_shuriken : CatalogItem :=
  { code := "shuriken", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 15, attackWater := 0, attackAir := 14
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_skeleton_armor : CatalogItem :=
  { code := "skeleton_armor", level := 20, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 5, resEarth := 0, resWater := 0, resAir := 5
    crit := 0 }

def item_skeleton_helmet : CatalogItem :=
  { code := "skeleton_helmet", level := 20, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_skeleton_pants : CatalogItem :=
  { code := "skeleton_pants", level := 20, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 6, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_skull_amulet : CatalogItem :=
  { code := "skull_amulet", level := 20, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 40
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_skull_ring : CatalogItem :=
  { code := "skull_ring", level := 20, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 20
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_skull_staff : CatalogItem :=
  { code := "skull_staff", level := 20, slotType := "weapon"
    attackFire := 40, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_skull_wand : CatalogItem :=
  { code := "skull_wand", level := 25, slotType := "weapon"
    attackFire := 25, attackEarth := 0, attackWater := 0, attackAir := 25
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_skullforged_armor : CatalogItem :=
  { code := "skullforged_armor", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 5, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_skullforged_pants : CatalogItem :=
  { code := "skullforged_pants", level := 50, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 250
    resFire := 4, resEarth := 0, resWater := 0, resAir := 4
    crit := 5 }

def item_skullforged_ring : CatalogItem :=
  { code := "skullforged_ring", level := 50, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_slime_shield : CatalogItem :=
  { code := "slime_shield", level := 20, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 7, resEarth := 7, resWater := 7, resAir := 7
    crit := 0 }

def item_small_antidote : CatalogItem :=
  { code := "small_antidote", level := 20, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_small_health_potion : CatalogItem :=
  { code := "small_health_potion", level := 5, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_snakeskin_armor : CatalogItem :=
  { code := "snakeskin_armor", level := 25, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 5, resWater := 0, resAir := 10
    crit := 0 }

def item_snakeskin_boots : CatalogItem :=
  { code := "snakeskin_boots", level := 20, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 8, resAir := 8
    crit := 0 }

def item_snakeskin_legs_armor : CatalogItem :=
  { code := "snakeskin_legs_armor", level := 25, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 140
    resFire := 0, resEarth := 3, resWater := 0, resAir := 6
    crit := 0 }

def item_sonnengott_cloak : CatalogItem :=
  { code := "sonnengott_cloak", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 350
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 8 }

def item_spruce_fishing_rod : CatalogItem :=
  { code := "spruce_fishing_rod", level := 10, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_armor : CatalogItem :=
  { code := "steel_armor", level := 20, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 5, resWater := 5, resAir := 0
    crit := 0 }

def item_steel_axe : CatalogItem :=
  { code := "steel_axe", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_battleaxe : CatalogItem :=
  { code := "steel_battleaxe", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 40, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_steel_boots : CatalogItem :=
  { code := "steel_boots", level := 20, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 8, resEarth := 8, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_fishing_rod : CatalogItem :=
  { code := "steel_fishing_rod", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_gloves : CatalogItem :=
  { code := "steel_gloves", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_helm : CatalogItem :=
  { code := "steel_helm", level := 20, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_legs_armor : CatalogItem :=
  { code := "steel_legs_armor", level := 20, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 80
    resFire := 0, resEarth := 0, resWater := 6, resAir := 0
    crit := 0 }

def item_steel_pickaxe : CatalogItem :=
  { code := "steel_pickaxe", level := 20, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_steel_ring : CatalogItem :=
  { code := "steel_ring", level := 20, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_sticky_dagger : CatalogItem :=
  { code := "sticky_dagger", level := 5, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 12
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_sticky_sword : CatalogItem :=
  { code := "sticky_sword", level := 5, slotType := "weapon"
    attackFire := 0, attackEarth := 16, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_stormforged_armor : CatalogItem :=
  { code := "stormforged_armor", level := 25, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 10, resWater := 5, resAir := 0
    crit := 0 }

def item_stormforged_pants : CatalogItem :=
  { code := "stormforged_pants", level := 25, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 140
    resFire := 0, resEarth := 6, resWater := 3, resAir := 0
    crit := 0 }

def item_strangold_armor : CatalogItem :=
  { code := "strangold_armor", level := 35, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 6, resEarth := 0, resWater := 6, resAir := 0
    crit := 0 }

def item_strangold_helmet : CatalogItem :=
  { code := "strangold_helmet", level := 35, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_strangold_legs_armor : CatalogItem :=
  { code := "strangold_legs_armor", level := 35, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 150
    resFire := 0, resEarth := 0, resWater := 7, resAir := 7
    crit := 0 }

def item_strangold_sword : CatalogItem :=
  { code := "strangold_sword", level := 35, slotType := "weapon"
    attackFire := 45, attackEarth := 0, attackWater := 0, attackAir := 40
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_topaz_amulet : CatalogItem :=
  { code := "topaz_amulet", level := 25, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 70
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_topaz_book : CatalogItem :=
  { code := "topaz_book", level := 40, slotType := "artifact"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_topaz_ring : CatalogItem :=
  { code := "topaz_ring", level := 30, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_tromatising_mask : CatalogItem :=
  { code := "tromatising_mask", level := 20, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 90
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_vampire_bow : CatalogItem :=
  { code := "vampire_bow", level := 25, slotType := "weapon"
    attackFire := 36, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_vampiric_rune : CatalogItem :=
  { code := "vampiric_rune", level := 40, slotType := "rune"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_vital_armor : CatalogItem :=
  { code := "vital_armor", level := 50, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 300
    resFire := 0, resEarth := 0, resWater := 0, resAir := 5
    crit := 5 }

def item_vital_boots : CatalogItem :=
  { code := "vital_boots", level := 50, slotType := "boots"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 170
    resFire := 0, resEarth := 8, resWater := 8, resAir := 0
    crit := 0 }

def item_voidstone_axe : CatalogItem :=
  { code := "voidstone_axe", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_voidstone_fishing_rod : CatalogItem :=
  { code := "voidstone_fishing_rod", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 5, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_voidstone_gloves : CatalogItem :=
  { code := "voidstone_gloves", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 5
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_voidstone_pickaxe : CatalogItem :=
  { code := "voidstone_pickaxe", level := 50, slotType := "weapon"
    attackFire := 0, attackEarth := 5, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_water_boost_potion : CatalogItem :=
  { code := "water_boost_potion", level := 10, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_water_bow : CatalogItem :=
  { code := "water_bow", level := 5, slotType := "weapon"
    attackFire := 0, attackEarth := 0, attackWater := 16, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_water_res_potion : CatalogItem :=
  { code := "water_res_potion", level := 40, slotType := "utility"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 10, resAir := 0
    crit := 0 }

def item_water_ring : CatalogItem :=
  { code := "water_ring", level := 15, slotType := "ring"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_water_shield : CatalogItem :=
  { code := "water_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := -10, resWater := 25, resAir := 0
    crit := 0 }

def item_white_knight_armor : CatalogItem :=
  { code := "white_knight_armor", level := 40, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 7, resEarth := 7, resWater := 0, resAir := 0
    crit := 0 }

def item_white_knight_helmet : CatalogItem :=
  { code := "white_knight_helmet", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 3 }

def item_white_knight_pants : CatalogItem :=
  { code := "white_knight_pants", level := 40, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 7, resEarth := 0, resWater := 0, resAir := 7
    crit := 0 }

def item_white_knight_shield : CatalogItem :=
  { code := "white_knight_shield", level := 40, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 15, resWater := 0, resAir := 15
    crit := 0 }

def item_wisdom_amulet : CatalogItem :=
  { code := "wisdom_amulet", level := 15, slotType := "amulet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 30
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_wolf_ears : CatalogItem :=
  { code := "wolf_ears", level := 15, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 60
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_wooden_club : CatalogItem :=
  { code := "wooden_club", level := 25, slotType := "weapon"
    attackFire := 0, attackEarth := 36, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 35 }

def item_wooden_shield : CatalogItem :=
  { code := "wooden_shield", level := 1, slotType := "shield"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 2, resEarth := 2, resWater := 2, resAir := 2
    crit := 0 }

def item_wooden_staff : CatalogItem :=
  { code := "wooden_staff", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 8, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_wooden_stick : CatalogItem :=
  { code := "wooden_stick", level := 1, slotType := "weapon"
    attackFire := 0, attackEarth := 4, attackWater := 0, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def item_wratharmor : CatalogItem :=
  { code := "wratharmor", level := 40, slotType := "body_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 0, resEarth := 0, resWater := 7, resAir := 7
    crit := 0 }

def item_wrathelmet : CatalogItem :=
  { code := "wrathelmet", level := 40, slotType := "helmet"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 200
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 0 }

def item_wrathpants : CatalogItem :=
  { code := "wrathpants", level := 40, slotType := "leg_armor"
    attackFire := 0, attackEarth := 0, attackWater := 0, attackAir := 0
    hpBonus := 180
    resFire := 7, resEarth := 7, resWater := 0, resAir := 0
    crit := 0 }

def item_wrathsword : CatalogItem :=
  { code := "wrathsword", level := 40, slotType := "weapon"
    attackFire := 0, attackEarth := 70, attackWater := 30, attackAir := 0
    hpBonus := 0
    resFire := 0, resEarth := 0, resWater := 0, resAir := 0
    crit := 5 }

def itemCatalog : List CatalogItem :=
  [item_adamantite_axe, item_adamantite_boots, item_adamantite_fishing_rod, item_adamantite_gloves, item_adamantite_mask, item_adamantite_pickaxe, item_adamantite_platebody, item_adamantite_platelegs, item_adamantite_ring, item_adamantite_shield, item_adamantite_sword, item_adventurer_boots, item_adventurer_helmet, item_adventurer_pants, item_adventurer_vest, item_air_and_water_amulet, item_air_boost_potion, item_air_res_potion, item_air_ring, item_air_shield, item_amulet_of_the_grand_master, item_ancestral_talisman, item_ancient_jean, item_antidote, item_apprentice_gloves, item_backpack, item_bandit_armor, item_battlestaff, item_batwing_helmet, item_blade_of_hell, item_bloodblade, item_bow_from_hell, item_burn_rune, item_celest_ring, item_conjurer_cloak, item_conjurer_skirt, item_copper_armor, item_copper_axe, item_copper_boots, item_copper_dagger, item_copper_helmet, item_copper_legs_armor, item_copper_pickaxe, item_copper_ring, item_corrupted_crown, item_corrupted_skull, item_corrupted_stone_amulet, item_cultist_boots, item_cultist_cloak, item_cultist_hat, item_cultist_pants, item_cursed_hat, item_cursed_sceptre, item_dark_horned_helmet, item_darkforged_boots, item_darkforged_helmet, item_darkforged_plate, item_darkforged_shield, item_death_knight_sword, item_demoniac_dagger, item_demoniac_shield, item_desert_whip, item_desert_wrap, item_diabolic_elixir, item_diamond_amulet, item_diamond_armor, item_diamond_skirt, item_diamond_sword, item_divinity_ring, item_dreadful_amulet, item_dreadful_armor, item_dreadful_battleaxe, item_dreadful_ring, item_dreadful_shield, item_dreadful_staff, item_duskarmor, item_duskpants, item_dust_amulet, item_dust_helmet, item_dust_sword, item_earth_boost_potion, item_earth_res_potion, item_earth_ring, item_earth_shield, item_elderwood_staff, item_emerald_amulet, item_emerald_book, item_emerald_ring, item_enchanted_rune, item_enchanter_boots, item_enchanter_pants, item_enhanced_antidote, item_enhanced_boost_potion, item_enhanced_health_potion, item_enhanced_health_splash_potion, item_eternal_red_ring, item_eternity_ring, item_feather_coat, item_fire_and_earth_amulet, item_fire_boost_potion, item_fire_bow, item_fire_res_potion, item_fire_ring, item_fire_shield, item_fire_staff, item_fishing_net, item_flying_boots, item_forest_ring, item_forest_staff, item_forest_whip, item_goblin_guard_shield, item_gold_axe, item_gold_boots, item_gold_fishing_rod, item_gold_helm, item_gold_mask, item_gold_pickaxe, item_gold_platebody, item_gold_platelegs, item_gold_ring, item_gold_shield, item_gold_sword, item_golden_gloves, item_greater_dreadful_amulet, item_greater_dreadful_staff, item_greater_emerald_amulet, item_greater_healing_rune, item_greater_health_potion, item_greater_lifesteal_rune, item_greater_protection_rune, item_greater_ruby_amulet, item_greater_sapphire_amulet, item_greater_topaz_amulet, item_greater_wooden_staff, item_hard_leather_armor, item_hard_leather_boots, item_hard_leather_helmet, item_hard_leather_pants, item_healing_aura_rune, item_healing_rune, item_health_boost_potion, item_health_potion, item_health_splash_potion, item_heart_amulet, item_hell_armor, item_hell_helmet, item_hell_legs_armor, item_hell_reaper, item_hell_ring, item_hell_staff, item_highwayman_dagger, item_hork_helmet, item_hunting_bow, item_iron_armor, item_iron_axe, item_iron_boots, item_iron_dagger, item_iron_helm, item_iron_legs_armor, item_iron_pickaxe, item_iron_ring, item_iron_shield, item_iron_sword, item_jester_hat, item_king_slime_sword, item_leather_armor, item_leather_boots, item_leather_gloves, item_leather_hat, item_leather_legs_armor, item_lich_crown, item_life_amulet, item_life_crystal, item_life_ring, item_lifesteal_rune, item_lightning_sword, item_lizard_boots, item_lizard_skin_armor, item_lizard_skin_legs_armor, item_lost_amulet, item_lost_world_map, item_lucky_wizard_hat, item_magic_bow, item_magic_shield, item_magic_wizard_hat, item_malefic_armor, item_malefic_crystal, item_malefic_ring, item_masterful_necklace, item_medic_armor, item_medic_skirt, item_mesh_armor, item_mesh_legs_armor, item_minor_health_potion, item_mithril_axe, item_mithril_boots, item_mithril_fishing_rod, item_mithril_gloves, item_mithril_helm, item_mithril_pickaxe, item_mithril_platebody, item_mithril_platelegs, item_mithril_ring, item_mithril_shield, item_mithril_sword, item_moonlight_staff, item_mushmush_bow, item_mushmush_jacket, item_mushmush_wizard_hat, item_mushstaff, item_novice_guide, item_obsidian_armor, item_obsidian_battleaxe, item_obsidian_helmet, item_obsidian_legs_armor, item_old_boots, item_perfect_bow, item_perfect_pearl, item_piggy_armor, item_piggy_helmet, item_piggy_pants, item_powerful_rune, item_prospecting_amulet, item_protection_rune, item_red_dragon_armor, item_red_dragon_boots, item_red_dragon_legs_armor, item_red_dragon_shield, item_ring_of_chance, item_ring_of_the_adept, item_royal_skeleton_armor, item_royal_skeleton_helmet, item_royal_skeleton_pants, item_royal_skeleton_ring, item_ruby_amulet, item_ruby_book, item_ruby_ring, item_sacred_ring, item_sand_snakeskin_armor, item_sand_snakeskin_bandana, item_sand_snakeskin_boots, item_sand_snakeskin_pants, item_sandwhisper_bag, item_sandwhisper_codex, item_sanguine_edge_of_rosen, item_sapphire_amulet, item_sapphire_book, item_sapphire_ring, item_satchel, item_shuriken, item_skeleton_armor, item_skeleton_helmet, item_skeleton_pants, item_skull_amulet, item_skull_ring, item_skull_staff, item_skull_wand, item_skullforged_armor, item_skullforged_pants, item_skullforged_ring, item_slime_shield, item_small_antidote, item_small_health_potion, item_snakeskin_armor, item_snakeskin_boots, item_snakeskin_legs_armor, item_sonnengott_cloak, item_spruce_fishing_rod, item_steel_armor, item_steel_axe, item_steel_battleaxe, item_steel_boots, item_steel_fishing_rod, item_steel_gloves, item_steel_helm, item_steel_legs_armor, item_steel_pickaxe, item_steel_ring, item_sticky_dagger, item_sticky_sword, item_stormforged_armor, item_stormforged_pants, item_strangold_armor, item_strangold_helmet, item_strangold_legs_armor, item_strangold_sword, item_topaz_amulet, item_topaz_book, item_topaz_ring, item_tromatising_mask, item_vampire_bow, item_vampiric_rune, item_vital_armor, item_vital_boots, item_voidstone_axe, item_voidstone_fishing_rod, item_voidstone_gloves, item_voidstone_pickaxe, item_water_boost_potion, item_water_bow, item_water_res_potion, item_water_ring, item_water_shield, item_white_knight_armor, item_white_knight_helmet, item_white_knight_pants, item_white_knight_shield, item_wisdom_amulet, item_wolf_ears, item_wooden_club, item_wooden_shield, item_wooden_staff, item_wooden_stick, item_wratharmor, item_wrathelmet, item_wrathpants, item_wrathsword]

/-! ## WinnableAcrossBand witness table (one row per band level 1..49)

  Each row: the winning monster + `pick_loadout` loadout + the
  production-projected `predictWin` scalars at that level. The
  projection's fidelity is pinned by
  `formal/diff/test_winnable_witness_diff.py`. -/

def winnableWitness : List WitnessRow :=
  [
    { level := 1, monsterCode := "yellow_slime", monsterLevel := 2
      loadoutCodes := ["copper_boots", "copper_dagger", "copper_helmet", "wooden_shield"]
      pCrit := 35, pMaxHp := 150, pInitiative := 100
      pAtkSum := 6, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 6, monsterHp := 70, rawMonster := 8
      mCrit := 0, mAtkSum := 8, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 2, monsterCode := "green_slime", monsterLevel := 4
      loadoutCodes := ["copper_boots", "copper_helmet", "wooden_shield", "wooden_staff"]
      pCrit := 5, pMaxHp := 155, pInitiative := 100
      pAtkSum := 8, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 8, monsterHp := 80, rawMonster := 12
      mCrit := 0, mAtkSum := 12, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 3, monsterCode := "green_slime", monsterLevel := 4
      loadoutCodes := ["copper_boots", "copper_helmet", "wooden_shield", "wooden_staff"]
      pCrit := 5, pMaxHp := 160, pInitiative := 100
      pAtkSum := 8, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 8, monsterHp := 80, rawMonster := 12
      mCrit := 0, mAtkSum := 12, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 4, monsterCode := "green_slime", monsterLevel := 4
      loadoutCodes := ["copper_boots", "copper_helmet", "wooden_shield", "wooden_staff"]
      pCrit := 5, pMaxHp := 165, pInitiative := 100
      pAtkSum := 8, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 8, monsterHp := 80, rawMonster := 12
      mCrit := 0, mAtkSum := 12, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 5, monsterCode := "red_slime", monsterLevel := 7
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "water_bow", "wooden_shield"]
      pCrit := 35, pMaxHp := 250, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 17, monsterHp := 120, rawMonster := 18
      mCrit := 0, mAtkSum := 18, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 6, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 255, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 7, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 260, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 8, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 265, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 9, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 270, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 10, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet", "novice_guide"]
      pCrit := 5, pMaxHp := 420, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 11, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet", "novice_guide"]
      pCrit := 5, pMaxHp := 425, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 12, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet", "novice_guide"]
      pCrit := 5, pMaxHp := 430, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 13, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet", "novice_guide"]
      pCrit := 5, pMaxHp := 435, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 29, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 14, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet", "novice_guide"]
      pCrit := 5, pMaxHp := 440, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 29, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 15, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["adventurer_pants", "forest_ring", "iron_armor", "iron_boots", "iron_shield", "king_slime_sword", "leather_hat", "life_ring", "novice_guide", "wisdom_amulet"]
      pCrit := 24, pMaxHp := 480, pInitiative := 100
      pAtkSum := 36, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 40, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 16, monsterCode := "skeleton", monsterLevel := 18
      loadoutCodes := ["adventurer_pants", "forest_ring", "iron_helm", "iron_shield", "king_slime_sword", "leather_armor", "leather_boots", "life_ring", "novice_guide", "wisdom_amulet"]
      pCrit := 24, pMaxHp := 485, pInitiative := 100
      pAtkSum := 36, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 39, monsterHp := 480, rawMonster := 37
      mCrit := 5, mAtkSum := 44, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 17, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["adventurer_pants", "forest_ring", "iron_armor", "iron_boots", "iron_shield", "king_slime_sword", "leather_hat", "life_ring", "novice_guide", "wisdom_amulet"]
      pCrit := 24, pMaxHp := 490, pInitiative := 100
      pAtkSum := 36, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 37, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 18, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["adventurer_pants", "forest_ring", "iron_armor", "iron_boots", "iron_shield", "king_slime_sword", "leather_hat", "life_ring", "novice_guide", "wisdom_amulet"]
      pCrit := 24, pMaxHp := 495, pInitiative := 100
      pAtkSum := 36, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 37, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 19, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["adventurer_pants", "forest_ring", "iron_armor", "iron_boots", "iron_shield", "king_slime_sword", "leather_hat", "life_ring", "novice_guide", "wisdom_amulet"]
      pCrit := 24, pMaxHp := 500, pInitiative := 100
      pAtkSum := 36, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 37, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 20, monsterCode := "spider", monsterLevel := 20
      loadoutCodes := ["battlestaff", "dreadful_amulet", "hard_leather_armor", "iron_helm", "life_ring", "lifesteal_rune", "novice_guide", "ring_of_chance", "skeleton_pants", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 625, pInitiative := 125
      pAtkSum := 40, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 61, monsterHp := 550, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 21, monsterCode := "spider", monsterLevel := 20
      loadoutCodes := ["battlestaff", "dreadful_amulet", "hard_leather_armor", "iron_helm", "life_ring", "lifesteal_rune", "novice_guide", "ring_of_chance", "skeleton_pants", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 630, pInitiative := 125
      pAtkSum := 40, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 61, monsterHp := 550, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 22, monsterCode := "spider", monsterLevel := 20
      loadoutCodes := ["battlestaff", "dreadful_amulet", "hard_leather_armor", "iron_helm", "life_ring", "lifesteal_rune", "novice_guide", "ring_of_chance", "skeleton_pants", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 635, pInitiative := 125
      pAtkSum := 40, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 61, monsterHp := 550, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 23, monsterCode := "rat", monsterLevel := 25
      loadoutCodes := ["dreadful_amulet", "hard_leather_armor", "iron_helm", "life_ring", "lifesteal_rune", "novice_guide", "ring_of_chance", "skeleton_pants", "slime_shield", "steel_battleaxe", "steel_boots"]
      pCrit := 9, pMaxHp := 640, pInitiative := 125
      pAtkSum := 40, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 60, monsterHp := 800, rawMonster := 35
      mCrit := 50, mAtkSum := 50, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 24, monsterCode := "rat", monsterLevel := 25
      loadoutCodes := ["dreadful_amulet", "hard_leather_armor", "iron_helm", "life_ring", "lifesteal_rune", "novice_guide", "ring_of_chance", "skeleton_pants", "slime_shield", "steel_battleaxe", "steel_boots"]
      pCrit := 9, pMaxHp := 645, pInitiative := 125
      pAtkSum := 40, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 60, monsterHp := 800, rawMonster := 35
      mCrit := 50, mAtkSum := 50, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 25, monsterCode := "bandit_lizard", monsterLevel := 25
      loadoutCodes := ["dreadful_staff", "emerald_amulet", "iron_helm", "lifesteal_rune", "lizard_skin_armor", "lizard_skin_legs_armor", "novice_guide", "ring_of_chance", "ring_of_the_adept", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 825, pInitiative := 200
      pAtkSum := 50, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 63, monsterHp := 780, rawMonster := 60
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 26, monsterCode := "bandit_lizard", monsterLevel := 25
      loadoutCodes := ["dreadful_staff", "emerald_amulet", "iron_helm", "lifesteal_rune", "lizard_skin_armor", "lizard_skin_legs_armor", "novice_guide", "ring_of_chance", "ring_of_the_adept", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 830, pInitiative := 200
      pAtkSum := 50, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 63, monsterHp := 780, rawMonster := 60
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 27, monsterCode := "bandit_lizard", monsterLevel := 25
      loadoutCodes := ["dreadful_staff", "emerald_amulet", "iron_helm", "lifesteal_rune", "lizard_skin_armor", "lizard_skin_legs_armor", "novice_guide", "ring_of_chance", "ring_of_the_adept", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 835, pInitiative := 200
      pAtkSum := 50, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 63, monsterHp := 780, rawMonster := 60
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 28, monsterCode := "bandit_lizard", monsterLevel := 25
      loadoutCodes := ["dreadful_staff", "emerald_amulet", "iron_helm", "lifesteal_rune", "lizard_skin_armor", "lizard_skin_legs_armor", "novice_guide", "ring_of_chance", "ring_of_the_adept", "slime_shield", "snakeskin_boots"]
      pCrit := 9, pMaxHp := 840, pInitiative := 200
      pAtkSum := 50, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 63, monsterHp := 780, rawMonster := 60
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 29, monsterCode := "imp", monsterLevel := 28
      loadoutCodes := ["emerald_amulet", "iron_helm", "lifesteal_rune", "novice_guide", "ring_of_chance", "ring_of_the_adept", "skull_wand", "slime_shield", "steel_boots", "stormforged_armor", "stormforged_pants"]
      pCrit := 9, pMaxHp := 845, pInitiative := 175
      pAtkSum := 50, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 57, monsterHp := 1750, rawMonster := 29
      mCrit := 5, mAtkSum := 45, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 30, monsterCode := "demon", monsterLevel := 30
      loadoutCodes := ["gold_shield", "greater_dreadful_staff", "life_crystal", "lifesteal_rune", "lizard_boots", "novice_guide", "obsidian_helmet", "piggy_armor", "piggy_pants", "prospecting_amulet", "ring_of_the_adept", "royal_skeleton_ring"]
      pCrit := 5, pMaxHp := 1260, pInitiative := 180
      pAtkSum := 80, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 125, monsterHp := 1250, rawMonster := 67
      mCrit := 5, mAtkSum := 110, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 31, monsterCode := "cultist_acolyte", monsterLevel := 33
      loadoutCodes := ["elderwood_staff", "gold_boots", "gold_platelegs", "gold_shield", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "prospecting_amulet", "ring_of_the_adept", "royal_skeleton_ring", "snakeskin_armor"]
      pCrit := 5, pMaxHp := 1275, pInitiative := 280
      pAtkSum := 80, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 130, monsterHp := 1500, rawMonster := 84
      mCrit := 5, mAtkSum := 130, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 32, monsterCode := "cultist_acolyte", monsterLevel := 33
      loadoutCodes := ["elderwood_staff", "gold_boots", "gold_platelegs", "gold_shield", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "prospecting_amulet", "ring_of_the_adept", "royal_skeleton_ring", "snakeskin_armor"]
      pCrit := 5, pMaxHp := 1280, pInitiative := 280
      pAtkSum := 80, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 130, monsterHp := 1500, rawMonster := 84
      mCrit := 5, mAtkSum := 130, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 33, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["death_knight_sword", "gold_boots", "gold_platelegs", "gold_shield", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "prospecting_amulet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 24, pMaxHp := 1285, pInitiative := 255
      pAtkSum := 74, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 140, monsterHp := 2300, rawMonster := 84
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 34, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["death_knight_sword", "gold_boots", "gold_platelegs", "gold_shield", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "prospecting_amulet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 24, pMaxHp := 1290, pInitiative := 255
      pAtkSum := 74, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 140, monsterHp := 2300, rawMonster := 84
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 35, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["ancestral_talisman", "ancient_jean", "cursed_sceptre", "dreadful_shield", "gold_boots", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 11, pMaxHp := 1295, pInitiative := 205
      pAtkSum := 82, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 143, monsterHp := 2300, rawMonster := 73
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 36, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["ancestral_talisman", "ancient_jean", "cursed_sceptre", "dreadful_shield", "gold_boots", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 11, pMaxHp := 1300, pInitiative := 205
      pAtkSum := 82, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 143, monsterHp := 2300, rawMonster := 73
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 37, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["ancestral_talisman", "ancient_jean", "cursed_sceptre", "dreadful_shield", "gold_boots", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 11, pMaxHp := 1305, pInitiative := 205
      pAtkSum := 82, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 143, monsterHp := 2300, rawMonster := 73
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 38, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["ancestral_talisman", "ancient_jean", "cursed_sceptre", "dreadful_shield", "gold_boots", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 11, pMaxHp := 1310, pInitiative := 205
      pAtkSum := 82, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 143, monsterHp := 2300, rawMonster := 73
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 39, monsterCode := "goblin_guard", monsterLevel := 35
      loadoutCodes := ["ancestral_talisman", "ancient_jean", "cursed_sceptre", "dreadful_shield", "gold_boots", "life_crystal", "lifesteal_rune", "novice_guide", "obsidian_helmet", "ring_of_the_adept", "royal_skeleton_ring", "stormforged_armor"]
      pCrit := 11, pMaxHp := 1315, pInitiative := 205
      pAtkSum := 82, pLifesteal := 15, pAntipoison := 0
      rawPlayer := 143, monsterHp := 2300, rawMonster := 73
      mCrit := 5, mAtkSum := 140, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 40, monsterCode := "cultist_alchemist", monsterLevel := 40
      loadoutCodes := ["air_res_potion", "air_shield", "cultist_boots", "cultist_cloak", "greater_emerald_amulet", "greater_lifesteal_rune", "leather_hat", "life_crystal", "mithril_ring", "novice_guide", "royal_skeleton_ring", "sanguine_edge_of_rosen", "strangold_legs_armor", "water_res_potion"]
      pCrit := 12, pMaxHp := 1425, pInitiative := 660
      pAtkSum := 100, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 153, monsterHp := 3000, rawMonster := 71
      mCrit := 5, mAtkSum := 150, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 41, monsterCode := "cultist_alchemist", monsterLevel := 40
      loadoutCodes := ["air_res_potion", "air_shield", "cultist_boots", "cultist_cloak", "greater_emerald_amulet", "greater_lifesteal_rune", "leather_hat", "life_crystal", "mithril_ring", "novice_guide", "royal_skeleton_ring", "sanguine_edge_of_rosen", "strangold_legs_armor", "water_res_potion"]
      pCrit := 12, pMaxHp := 1430, pInitiative := 660
      pAtkSum := 100, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 153, monsterHp := 3000, rawMonster := 71
      mCrit := 5, mAtkSum := 150, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 42, monsterCode := "sand_snake", monsterLevel := 44
      loadoutCodes := ["air_res_potion", "air_shield", "cultist_boots", "greater_emerald_amulet", "greater_lifesteal_rune", "health_boost_potion", "leather_hat", "life_crystal", "mithril_platelegs", "mithril_ring", "novice_guide", "royal_skeleton_ring", "sanguine_edge_of_rosen", "snakeskin_armor"]
      pCrit := 12, pMaxHp := 1755, pInitiative := 710
      pAtkSum := 100, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 143, monsterHp := 3200, rawMonster := 65
      mCrit := 5, mAtkSum := 180, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 43, monsterCode := "sand_snake", monsterLevel := 44
      loadoutCodes := ["air_res_potion", "air_shield", "cultist_boots", "greater_emerald_amulet", "greater_lifesteal_rune", "health_boost_potion", "leather_hat", "life_crystal", "mithril_platelegs", "mithril_ring", "novice_guide", "royal_skeleton_ring", "sanguine_edge_of_rosen", "snakeskin_armor"]
      pCrit := 12, pMaxHp := 1760, pInitiative := 710
      pAtkSum := 100, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 143, monsterHp := 3200, rawMonster := 65
      mCrit := 5, mAtkSum := 180, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 44, monsterCode := "sand_snake", monsterLevel := 44
      loadoutCodes := ["air_res_potion", "air_shield", "cultist_boots", "greater_emerald_amulet", "greater_lifesteal_rune", "health_boost_potion", "leather_hat", "life_crystal", "mithril_platelegs", "mithril_ring", "novice_guide", "royal_skeleton_ring", "sanguine_edge_of_rosen", "snakeskin_armor"]
      pCrit := 12, pMaxHp := 1765, pInitiative := 710
      pAtkSum := 100, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 143, monsterHp := 3200, rawMonster := 65
      mCrit := 5, mAtkSum := 180, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 45, monsterCode := "dusk_beetle", monsterLevel := 47
      loadoutCodes := ["bow_from_hell", "corrupted_crown", "demoniac_shield", "diabolic_elixir", "earth_res_potion", "greater_emerald_amulet", "greater_lifesteal_rune", "life_crystal", "mithril_boots", "mithril_platebody", "mithril_ring", "novice_guide", "royal_skeleton_ring", "wrathpants"]
      pCrit := 31, pMaxHp := 1810, pInitiative := 460
      pAtkSum := 106, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 229, monsterHp := 3500, rawMonster := 96
      mCrit := 5, mAtkSum := 240, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 46, monsterCode := "dusk_beetle", monsterLevel := 47
      loadoutCodes := ["bow_from_hell", "corrupted_crown", "demoniac_shield", "diabolic_elixir", "earth_res_potion", "greater_emerald_amulet", "greater_lifesteal_rune", "life_crystal", "mithril_boots", "mithril_platebody", "mithril_ring", "novice_guide", "royal_skeleton_ring", "wrathpants"]
      pCrit := 31, pMaxHp := 1815, pInitiative := 460
      pAtkSum := 106, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 229, monsterHp := 3500, rawMonster := 96
      mCrit := 5, mAtkSum := 240, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 47, monsterCode := "dusk_beetle", monsterLevel := 47
      loadoutCodes := ["bow_from_hell", "corrupted_crown", "demoniac_shield", "diabolic_elixir", "earth_res_potion", "greater_emerald_amulet", "greater_lifesteal_rune", "life_crystal", "mithril_boots", "mithril_platebody", "mithril_ring", "novice_guide", "royal_skeleton_ring", "wrathpants"]
      pCrit := 31, pMaxHp := 1820, pInitiative := 460
      pAtkSum := 106, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 229, monsterHp := 3500, rawMonster := 96
      mCrit := 5, mAtkSum := 240, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 48, monsterCode := "baby_red_dragon", monsterLevel := 50
      loadoutCodes := ["bow_from_hell", "diabolic_elixir", "enchanter_pants", "fire_res_potion", "fire_shield", "greater_emerald_amulet", "greater_lifesteal_rune", "life_crystal", "malefic_armor", "mithril_boots", "mithril_helm", "mithril_ring", "novice_guide", "royal_skeleton_ring"]
      pCrit := 36, pMaxHp := 1765, pInitiative := 710
      pAtkSum := 106, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 195, monsterHp := 4500, rawMonster := 47
      mCrit := 5, mAtkSum := 250, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 49, monsterCode := "red_dragon", monsterLevel := 51
      loadoutCodes := ["bow_from_hell", "diabolic_elixir", "enchanter_pants", "fire_res_potion", "fire_shield", "greater_emerald_amulet", "greater_lifesteal_rune", "life_crystal", "malefic_armor", "mithril_boots", "mithril_helm", "mithril_ring", "novice_guide", "royal_skeleton_ring"]
      pCrit := 36, pMaxHp := 1770, pInitiative := 710
      pAtkSum := 106, pLifesteal := 25, pAntipoison := 0
      rawPlayer := 195, monsterHp := 5000, rawMonster := 57
      mCrit := 5, mAtkSum := 300, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true }
  ]

/-- Items dropped by gatherable resources (snapshot resource_drops). -/
def gatherableItems : List String :=
  ["adamantite_ore", "ash_wood", "bass", "birch_wood", "coal", "copper_ore", "dead_wood", "enchanted_mushroom", "glowstem_leaf", "gold_ore", "gudgeon", "iron_ore", "lava_fish", "magic_wood", "maple_wood", "mithril_ore", "nettle_leaf", "palm_wood", "salmon", "shrimp", "spruce_wood", "strange_ore", "sunflower", "swordfish", "torch_cactus_flower", "trout"]

/-- Distinct items dropped by catalog monsters (snapshot monster_drops). -/
def monsterDropItems : List String :=
  ["adventurer_skull", "apple", "baby_red_dragon_scale", "bandit_armor", "bat_heart", "bat_wing", "blue_slimeball", "broken_sword", "codex_page", "corrupted_gem", "corrupted_stone", "cowhide", "cursed_book", "cursed_flask", "cursed_wood", "cyclops_eye", "dark_essence", "death_knight_sword", "demon_horn", "demoniac_dust", "desert_scorpion_carapace", "desert_scorpion_meat", "desert_wrap", "dragon_bone", "dryad_hair", "dusk_beetle_shell", "duskworm_skin", "echoless_bat_wing", "efreet_cloth", "egg", "elemental_page", "enchanted_potion", "feather", "fennec_ear", "fennec_tail", "fire_dust", "flying_wing", "forest_ring", "forest_staff", "full_moon_vampire_cape", "goblin_eye", "goblin_guard_foot", "goblin_guard_shield", "goblin_tooth", "golden_dust", "golden_egg", "green_cloth", "green_slimeball", "grimlet_bone", "hellhound_collar", "hellhound_hair", "highwayman_dagger", "imp_tail", "king_slimeball", "lava_bucket", "lich_crown", "lich_tomb_key", "life_crystal_shard", "lizard_eye", "lizard_skin", "malefic_cloth", "malefic_shard", "marauder_hand", "milk_bucket", "mushroom", "ogre_eye", "ogre_skin", "old_boots", "orc_bone", "orc_skin", "owlbear_claw", "owlbear_hair", "page_from_hell", "piece_of_obsidian", "pig_skin", "priestess_hideout_key", "priestess_orb", "rat_hide", "raw_beef", "raw_chicken", "raw_hellhound_meat", "raw_porkchop", "raw_rat_meat", "raw_wolf_meat", "red_cloth", "red_dragon_scale", "red_slimeball", "rosenblood_elixir", "sand_snake_hide", "sand_snake_poison", "sandwhisper_coin", "sandwhisper_key", "sanguine_edge_of_rosen", "skeleton_bone", "skeleton_skull", "snake_hide", "solar_desert_scorpion_tail", "sonnengott_key", "spider_leg", "vampire_blood", "vampire_tooth", "wolf_bone", "wolf_ears", "wolf_hair", "wolfrider_hair", "wolfrider_ponytail", "wooden_club", "wool", "yellow_slimeball"]

/-- Python-computed closure-acquirable code set; the kernel VERIFIES its closure property (WitnessAcquirable.lean), so a wrong cert cannot prove. -/
def acquirableCert : List String :=
  ["adamantite_bar", "adamantite_ore", "adamantite_sword", "adventurer_boots", "adventurer_helmet", "adventurer_skull", "adventurer_vest", "air_and_water_amulet", "air_res_potion", "air_ring", "antidote", "apple", "apple_pie", "apprentice_gloves", "ash_plank", "ash_wood", "baby_red_dragon_scale", "bandit_armor", "bass", "bat_heart", "bat_wing", "battlestaff", "birch_wood", "blue_slimeball", "broken_sword", "cheese", "coal", "codex_page", "cooked_bass", "cooked_beef", "cooked_chicken", "cooked_desert_scorpion_meat", "cooked_gudgeon", "cooked_hellhound_meat", "cooked_porkchop", "cooked_rat_meat", "cooked_salmon", "cooked_shrimp", "cooked_swordfish", "cooked_trout", "cooked_wolf_meat", "cookie", "copper_armor", "copper_axe", "copper_bar", "copper_boots", "copper_dagger", "copper_helmet", "copper_legs_armor", "copper_ore", "copper_pickaxe", "copper_ring", "corrupted_gem", "corrupted_stone", "cowhide", "cursed_book", "cursed_flask", "cursed_plank", "cursed_wood", "cyclops_eye", "dark_essence", "darkforged_plate", "dead_wood", "dead_wood_plank", "death_knight_sword", "demon_horn", "demoniac_dust", "desert_scorpion_carapace", "desert_scorpion_meat", "desert_whip", "desert_wrap", "dragon_bone", "dryad_hair", "dusk_beetle_shell", "duskworm_skin", "dust_sword", "earth_res_potion", "earth_ring", "echoless_bat_wing", "efreet_cloth", "egg", "elderwood_staff", "elemental_page", "enchanted_mushroom", "enchanted_potion", "enhanced_antidote", "enhanced_boost_potion", "enhanced_health_potion", "feather", "feather_coat", "fennec_ear", "fennec_tail", "fire_and_earth_amulet", "fire_bow", "fire_dust", "fire_res_potion", "fire_ring", "fire_staff", "fish_soup", "fishing_net", "flying_wing", "forest_bank_potion", "forest_ring", "forest_staff", "forest_whip", "fried_eggs", "full_moon_vampire_cape", "glowstem_leaf", "goblin_eye", "goblin_guard_foot", "goblin_guard_shield", "goblin_tooth", "gold_bar", "gold_helm", "gold_mask", "gold_ore", "gold_platebody", "gold_ring", "gold_sword", "golden_dust", "golden_egg", "greater_wooden_staff", "green_cloth", "green_slimeball", "grimlet_bone", "gudgeon", "hardwood_plank", "health_boost_potion", "health_potion", "heart_amulet", "hell_legs_armor", "hellhound_collar", "hellhound_hair", "highwayman_dagger", "hork_helmet", "hunting_bow", "imp_tail", "iron_armor", "iron_bar", "iron_boots", "iron_dagger", "iron_helm", "iron_legs_armor", "iron_ore", "iron_ring", "iron_shield", "iron_sword", "king_slimeball", "lava_bucket", "lava_fish", "lava_underground_potion", "leather_armor", "leather_boots", "leather_hat", "leather_legs_armor", "lich_crown", "lich_tomb_key", "life_amulet", "life_crystal_shard", "lizard_eye", "lizard_skin", "lost_amulet", "magic_sap", "magic_wood", "magical_plank", "malefic_cloth", "malefic_shard", "maple_plank", "maple_sap", "maple_syrup", "maple_wood", "marauder_hand", "milk_bucket", "mithril_axe", "mithril_bar", "mithril_fishing_rod", "mithril_gloves", "mithril_ore", "mithril_pickaxe", "mithril_platelegs", "mithril_ring", "mithril_shield", "mushmush_wizard_hat", "mushroom", "mushroom_soup", "nettle_leaf", "obsidian_bar", "obsidian_battleaxe", "ogre_eye", "ogre_skin", "old_boots", "orc_bone", "orc_skin", "owlbear_claw", "owlbear_hair", "page_from_hell", "palm_plank", "palm_wood", "perfect_bow", "piece_of_obsidian", "pig_skin", "piggy_helmet", "priestess_hideout_key", "priestess_orb", "rat_hide", "raw_beef", "raw_chicken", "raw_hellhound_meat", "raw_porkchop", "raw_rat_meat", "raw_wolf_meat", "recall_potion", "red_cloth", "red_dragon_scale", "red_slimeball", "rosenblood_elixir", "royal_skeleton_armor", "royal_skeleton_pants", "royal_skeleton_ring", "salmon", "sand_snake_hide", "sand_snake_poison", "sandwhisper_coin", "sandwhisper_key", "sandwhisper_potion", "sanguine_edge_of_rosen", "sap", "shrimp", "shuriken", "skeleton_armor", "skeleton_bone", "skeleton_helmet", "skeleton_pants", "skeleton_skull", "skull_amulet", "skull_staff", "small_antidote", "small_health_potion", "snake_hide", "solar_desert_scorpion_tail", "sonnengott_key", "spider_leg", "spruce_plank", "spruce_wood", "steel_bar", "steel_battleaxe", "sticky_dagger", "sticky_sword", "strange_ore", "strangold_bar", "sunflower", "swordfish", "torch_cactus_flower", "trout", "vampire_blood", "vampire_tooth", "water_bow", "water_res_potion", "water_ring", "white_knight_shield", "wolf_bone", "wolf_ears", "wolf_hair", "wolfrider_hair", "wolfrider_ponytail", "wooden_club", "wooden_shield", "wool", "yellow_slimeball"]

/-! ## Acquirable witness table (C1b)

  The same production sweep as `winnableWitness`, but over the
  pool RESTRICTED to `acquirableCert` — every loadout below is
  provably obtainable by the gather/fight/craft loop. Band
  levels with no winnable target under this restriction form
  `acquirableFrontier` (event/boss/NPC-gated gear — the honest
  remainder of the gear-progression residual). -/

def acquirableFrontier : List Int :=
  [38]

def acquirableWitness : List WitnessRow :=
  [
    { level := 1, monsterCode := "yellow_slime", monsterLevel := 2
      loadoutCodes := ["copper_boots", "copper_dagger", "copper_helmet", "wooden_shield"]
      pCrit := 35, pMaxHp := 150, pInitiative := 100
      pAtkSum := 6, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 6, monsterHp := 70, rawMonster := 8
      mCrit := 0, mAtkSum := 8, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 2, monsterCode := "yellow_slime", monsterLevel := 2
      loadoutCodes := ["copper_boots", "copper_dagger", "copper_helmet", "wooden_shield"]
      pCrit := 35, pMaxHp := 155, pInitiative := 100
      pAtkSum := 6, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 6, monsterHp := 70, rawMonster := 8
      mCrit := 0, mAtkSum := 8, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 3, monsterCode := "yellow_slime", monsterLevel := 2
      loadoutCodes := ["copper_boots", "copper_dagger", "copper_helmet", "wooden_shield"]
      pCrit := 35, pMaxHp := 160, pInitiative := 100
      pAtkSum := 6, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 6, monsterHp := 70, rawMonster := 8
      mCrit := 0, mAtkSum := 8, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 4, monsterCode := "yellow_slime", monsterLevel := 2
      loadoutCodes := ["copper_boots", "copper_dagger", "copper_helmet", "wooden_shield"]
      pCrit := 35, pMaxHp := 165, pInitiative := 100
      pAtkSum := 6, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 6, monsterHp := 70, rawMonster := 8
      mCrit := 0, mAtkSum := 8, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 5, monsterCode := "red_slime", monsterLevel := 7
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "water_bow", "wooden_shield"]
      pCrit := 35, pMaxHp := 250, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 17, monsterHp := 120, rawMonster := 18
      mCrit := 0, mAtkSum := 18, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 6, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 255, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 7, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 260, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 8, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 265, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 9, monsterCode := "cow", monsterLevel := 8
      loadoutCodes := ["copper_armor", "copper_boots", "copper_helmet", "copper_legs_armor", "life_amulet", "sticky_sword", "wooden_shield"]
      pCrit := 5, pMaxHp := 270, pInitiative := 100
      pAtkSum := 16, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 23, monsterHp := 280, rawMonster := 21
      mCrit := 0, mAtkSum := 21, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 10, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 395, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 11, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 400, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 12, monsterCode := "flying_snake", monsterLevel := 12
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 405, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 360, rawMonster := 29
      mCrit := 5, mAtkSum := 34, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 13, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 410, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 29, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 14, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "greater_wooden_staff", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 415, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 29, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 15, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "highwayman_dagger", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 35, pMaxHp := 420, pInitiative := 100
      pAtkSum := 23, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 27, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 16, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "highwayman_dagger", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 35, pMaxHp := 425, pInitiative := 100
      pAtkSum := 23, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 27, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 17, monsterCode := "highwayman", monsterLevel := 15
      loadoutCodes := ["forest_ring", "highwayman_dagger", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "leather_hat", "life_amulet"]
      pCrit := 35, pMaxHp := 430, pInitiative := 100
      pAtkSum := 23, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 27, monsterHp := 380, rawMonster := 21
      mCrit := 35, mAtkSum := 25, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 18, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "iron_sword", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 435, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 19, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_legs_armor", "iron_shield", "iron_sword", "leather_hat", "life_amulet"]
      pCrit := 5, pMaxHp := 440, pInitiative := 100
      pAtkSum := 24, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 31, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 20, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_shield", "leather_hat", "skeleton_pants", "skull_amulet", "steel_battleaxe"]
      pCrit := 5, pMaxHp := 485, pInitiative := 100
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 48, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 21, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_shield", "leather_hat", "skeleton_pants", "skull_amulet", "steel_battleaxe"]
      pCrit := 5, pMaxHp := 490, pInitiative := 100
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 48, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 22, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_shield", "leather_hat", "skeleton_pants", "skull_amulet", "steel_battleaxe"]
      pCrit := 5, pMaxHp := 495, pInitiative := 100
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 48, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 23, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_shield", "leather_hat", "skeleton_pants", "skull_amulet", "steel_battleaxe"]
      pCrit := 5, pMaxHp := 500, pInitiative := 100
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 48, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 24, monsterCode := "pig", monsterLevel := 19
      loadoutCodes := ["forest_ring", "iron_armor", "iron_boots", "iron_shield", "leather_hat", "skeleton_pants", "skull_amulet", "steel_battleaxe"]
      pCrit := 5, pMaxHp := 505, pInitiative := 100
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 48, monsterHp := 480, rawMonster := 25
      mCrit := 30, mAtkSum := 30, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 25, monsterCode := "ogre", monsterLevel := 20
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_helm", "iron_shield", "leather_boots", "skeleton_pants", "skull_amulet", "skull_staff"]
      pCrit := 10, pMaxHp := 620, pInitiative := 150
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 71, monsterHp := 650, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 26, monsterCode := "ogre", monsterLevel := 20
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_helm", "iron_shield", "leather_boots", "skeleton_pants", "skull_amulet", "skull_staff"]
      pCrit := 10, pMaxHp := 625, pInitiative := 150
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 71, monsterHp := 650, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 27, monsterCode := "ogre", monsterLevel := 20
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_helm", "iron_shield", "leather_boots", "skeleton_pants", "skull_amulet", "skull_staff"]
      pCrit := 10, pMaxHp := 630, pInitiative := 150
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 71, monsterHp := 650, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 28, monsterCode := "ogre", monsterLevel := 20
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_helm", "iron_shield", "leather_boots", "skeleton_pants", "skull_amulet", "skull_staff"]
      pCrit := 10, pMaxHp := 635, pInitiative := 150
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 71, monsterHp := 650, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 29, monsterCode := "ogre", monsterLevel := 20
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_helm", "iron_shield", "leather_boots", "skeleton_pants", "skull_amulet", "skull_staff"]
      pCrit := 10, pMaxHp := 640, pInitiative := 150
      pAtkSum := 40, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 71, monsterHp := 650, rawMonster := 65
      mCrit := 5, mAtkSum := 80, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 30, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "iron_boots", "iron_helm", "iron_shield", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 835, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 95
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 31, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "iron_boots", "iron_helm", "iron_shield", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 840, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 95
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 32, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "iron_boots", "iron_helm", "iron_shield", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 845, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 95
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 33, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "iron_boots", "iron_helm", "iron_shield", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 850, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 95
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 34, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "iron_boots", "iron_helm", "iron_shield", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 855, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 95
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 35, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "goblin_guard_shield", "iron_boots", "iron_helm", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 860, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 94
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 36, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "goblin_guard_shield", "iron_boots", "iron_helm", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 865, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 94
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 37, monsterCode := "death_knight", monsterLevel := 28
      loadoutCodes := ["bandit_armor", "death_knight_sword", "forest_ring", "goblin_guard_shield", "iron_boots", "iron_helm", "lost_amulet", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 29, pMaxHp := 870, pInitiative := 230
      pAtkSum := 74, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 122, monsterHp := 820, rawMonster := 94
      mCrit := 5, mAtkSum := 112, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 39, monsterCode := "owlbear", monsterLevel := 30
      loadoutCodes := ["bandit_armor", "forest_ring", "iron_boots", "iron_shield", "leather_hat", "lost_amulet", "obsidian_battleaxe", "royal_skeleton_pants", "royal_skeleton_ring"]
      pCrit := 10, pMaxHp := 880, pInitiative := 230
      pAtkSum := 80, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 130, monsterHp := 1450, rawMonster := 78
      mCrit := 5, mAtkSum := 105, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := false },
    { level := 40, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1290, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 41, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1295, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 42, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1300, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 43, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1305, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 44, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1310, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 45, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1315, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 46, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1320, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 47, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1325, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 48, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1330, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true },
    { level := 49, monsterCode := "goblin_wolfrider", monsterLevel := 40
      loadoutCodes := ["bandit_armor", "earth_res_potion", "health_boost_potion", "iron_helm", "leather_boots", "lost_amulet", "mithril_ring", "royal_skeleton_pants", "royal_skeleton_ring", "sanguine_edge_of_rosen", "white_knight_shield"]
      pCrit := 14, pMaxHp := 1335, pInitiative := 310
      pAtkSum := 100, pLifesteal := 0, pAntipoison := 0
      rawPlayer := 166, monsterHp := 2650, rawMonster := 77
      mCrit := 5, mAtkSum := 145, mLifesteal := 0
      mPoison := 0, mBarrier := 0, mBurn := 0
      mHealing := 0, mReconstitution := 0, mVoidDrain := 0
      mBerserk := 0, mFrenzy := 0, mBubble := 0
      playerFirst := true }
  ]

end Formal.Liveness.GameDataFixture
