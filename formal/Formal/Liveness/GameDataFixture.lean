import Formal.Liveness.RecipeChainClosure
import Formal.Liveness.SkillGapClosure
import Formal.Liveness.TaskCompleteReachable
import Formal.Liveness.Measure
import Formal.Liveness.TaskLifecyclePhase
import Mathlib.Tactic

/-! # GameDataFixture — Phase 24 LIVE SNAPSHOT

  Captured: 2026-06-02T19:54:09.159314+00:00
  API: https://api.artifactsmmo.com
  Counts: 48 monsters, 485 items, 306 recipes, 24 resources.

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

open Formal.Liveness.Plan
open Formal.Liveness.PlanAction
open Formal.Liveness.Measure
open Formal.Liveness.TaskLifecyclePhase
open Formal.Liveness.TaskCompleteReachable
open Formal.Liveness.SkillGapClosure
open Formal.Liveness.RecipeChainClosure

/-- Snapshot timestamp (UTC ISO 8601). -/
def snapshotCapturedAt : String := "2026-06-02T19:54:09.159314+00:00"

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
    ingredients := [("adamantite_bar", 12), ("diamond", 1), ("dusk_beetle_shell", 4), ("enchanted_fabric", 2), ("golden_dust", 3), ("wolfrider_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_fishing_rod` (craftDepth 2). -/
def recipe_adamantite_fishing_rod : Recipe :=
  { output := "adamantite_fishing_rod"
    ingredients := [("adamantite_bar", 5), ("astralyte_crystal", 2), ("cursed_flask", 3), ("cursed_plank", 3), ("desert_scorpion_carapace", 4), ("lava_bucket", 4), ("palm_plank", 5)]
    craftDepth := 2 }

/-- Recipe for `adamantite_gloves` (craftDepth 2). -/
def recipe_adamantite_gloves : Recipe :=
  { output := "adamantite_gloves"
    ingredients := [("adamantite_bar", 10), ("astralyte_crystal", 3), ("desert_scorpion_carapace", 4), ("efreet_cloth", 4), ("goblin_guard_foot", 4), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `adamantite_mask` (craftDepth 2). -/
def recipe_adamantite_mask : Recipe :=
  { output := "adamantite_mask"
    ingredients := [("adamantite_bar", 12), ("alexandrite", 1), ("cursed_book", 5), ("duskworm_skin", 3), ("hellhound_collar", 3), ("jasper_crystal", 2)]
    craftDepth := 2 }

/-- Recipe for `adamantite_pickaxe` (craftDepth 2). -/
def recipe_adamantite_pickaxe : Recipe :=
  { output := "adamantite_pickaxe"
    ingredients := [("adamantite_bar", 10), ("astralyte_crystal", 2), ("broken_sword", 2), ("dark_essence", 4), ("efreet_cloth", 4), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `adamantite_platebody` (craftDepth 2). -/
def recipe_adamantite_platebody : Recipe :=
  { output := "adamantite_platebody"
    ingredients := [("adamantite_bar", 12), ("adventurer_skull", 3), ("desert_scorpion_carapace", 3), ("enchanted_fabric", 2), ("golden_dust", 4), ("malefic_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `adamantite_platelegs` (craftDepth 2). -/
def recipe_adamantite_platelegs : Recipe :=
  { output := "adamantite_platelegs"
    ingredients := [("adamantite_bar", 12), ("duskworm_skin", 3), ("enchanted_fabric", 2), ("golden_dust", 3), ("marauder_hand", 3), ("sand_snakeskin", 3)]
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
    ingredients := [("bat_wing", 5), ("cursed_flask", 5), ("enchanted_fabric", 2), ("rosenblood_elixir", 1), ("strangold_bar", 6), ("topaz", 1)]
    craftDepth := 2 }

/-- Recipe for `blade_of_hell` (craftDepth 2). -/
def recipe_blade_of_hell : Recipe :=
  { output := "blade_of_hell"
    ingredients := [("book_from_hell", 1), ("broken_sword", 2), ("lava_bucket", 4), ("orc_bone", 6), ("strangold_bar", 11)]
    craftDepth := 2 }

/-- Recipe for `bloodblade` (craftDepth 2). -/
def recipe_bloodblade : Recipe :=
  { output := "bloodblade"
    ingredients := [("astralyte_crystal", 2), ("broken_sword", 1), ("goblin_tooth", 5), ("mithril_bar", 8), ("wolfrider_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `bow_from_hell` (craftDepth 2). -/
def recipe_bow_from_hell : Recipe :=
  { output := "bow_from_hell"
    ingredients := [("book_from_hell", 1), ("demon_horn", 4), ("efreet_cloth", 3), ("imp_tail", 5), ("magical_plank", 10)]
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
    ingredients := [("cyclops_eye", 5), ("demon_horn", 4), ("enchanted_fabric", 1), ("obsidian_bar", 6), ("owlbear_hair", 4)]
    craftDepth := 2 }

/-- Recipe for `conjurer_skirt` (craftDepth 2). -/
def recipe_conjurer_skirt : Recipe :=
  { output := "conjurer_skirt"
    ingredients := [("lizard_eye", 4), ("obsidian_bar", 6), ("owlbear_claw", 3), ("vampire_tooth", 4), ("vermin_leather", 3)]
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
    ingredients := [("astralyte_crystal", 2), ("hellhound_collar", 4), ("malefic_cloth", 2), ("maple_plank", 8), ("red_cloth", 3)]
    craftDepth := 2 }

/-- Recipe for `cultist_hat` (craftDepth 2). -/
def recipe_cultist_hat : Recipe :=
  { output := "cultist_hat"
    ingredients := [("astralyte_crystal", 2), ("hellhound_hair", 5), ("malefic_cloth", 1), ("maple_plank", 8), ("orc_skin", 4)]
    craftDepth := 2 }

/-- Recipe for `cultist_pants` (craftDepth 2). -/
def recipe_cultist_pants : Recipe :=
  { output := "cultist_pants"
    ingredients := [("cursed_plank", 8), ("hellhound_hair", 3), ("magical_cure", 4), ("malefic_cloth", 2), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `cursed_hat` (craftDepth 2). -/
def recipe_cursed_hat : Recipe :=
  { output := "cursed_hat"
    ingredients := [("cursed_book", 4), ("cursed_plank", 8), ("diamond", 1), ("enchanted_fabric", 1), ("malefic_cloth", 2), ("owlbear_hair", 4)]
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
    ingredients := [("duskworm_skin", 4), ("hellhound_collar", 4), ("jasper_crystal", 3), ("palm_plank", 10), ("sand_snake_poison", 3), ("topaz", 2)]
    craftDepth := 2 }

/-- Recipe for `darkforged_boots` (craftDepth 2). -/
def recipe_darkforged_boots : Recipe :=
  { output := "darkforged_boots"
    ingredients := [("astralyte_crystal", 3), ("dark_essence", 5), ("lava_bucket", 4), ("maple_plank", 10), ("sand_snakeskin", 2)]
    craftDepth := 2 }

/-- Recipe for `darkforged_helmet` (craftDepth 2). -/
def recipe_darkforged_helmet : Recipe :=
  { output := "darkforged_helmet"
    ingredients := [("dark_essence", 5), ("enchanted_fabric", 3), ("grimlet_bone", 4), ("marauder_hand", 2), ("mithril_bar", 10)]
    craftDepth := 2 }

/-- Recipe for `darkforged_plate` (craftDepth 2). -/
def recipe_darkforged_plate : Recipe :=
  { output := "darkforged_plate"
    ingredients := [("cursed_plank", 10), ("efreet_cloth", 5), ("grimlet_bone", 4), ("rosenblood_elixir", 1), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `darkforged_shield` (craftDepth 2). -/
def recipe_darkforged_shield : Recipe :=
  { output := "darkforged_shield"
    ingredients := [("bat_wing", 4), ("cursed_plank", 10), ("dark_essence", 5), ("diamond", 1), ("marauder_hand", 4)]
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
    ingredients := [("cursed_flask", 2), ("desert_scorpion_carapace", 3), ("duskworm_skin", 3), ("efreet_cloth", 3), ("palm_plank", 12), ("sand_snake_poison", 3)]
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
    ingredients := [("enchanted_fabric", 1), ("goblin_guard_foot", 4), ("obsidian_bar", 8), ("ogre_eye", 5), ("priestess_orb", 2)]
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
    ingredients := [("adamantite_bar", 10), ("dusk_beetle_shell", 3), ("duskworm_skin", 4), ("enchanted_fabric", 3), ("orc_skin", 4), ("sapphire", 2)]
    craftDepth := 2 }

/-- Recipe for `duskpants` (craftDepth 2). -/
def recipe_duskpants : Recipe :=
  { output := "duskpants"
    ingredients := [("dusk_beetle_shell", 3), ("duskworm_skin", 4), ("enchanted_fabric", 3), ("goblin_guard_foot", 4), ("palm_plank", 10), ("priestess_orb", 2)]
    craftDepth := 2 }

/-- Recipe for `dust_amulet` (craftDepth 2). -/
def recipe_dust_amulet : Recipe :=
  { output := "dust_amulet"
    ingredients := [("adamantite_bar", 10), ("alexandrite", 1), ("dark_essence", 4), ("demoniac_dust", 3), ("duskworm_skin", 4), ("golden_dust", 4)]
    craftDepth := 2 }

/-- Recipe for `dust_helmet` (craftDepth 2). -/
def recipe_dust_helmet : Recipe :=
  { output := "dust_helmet"
    ingredients := [("adventurer_skull", 3), ("astralyte_crystal", 2), ("corrupted_stone", 3), ("desert_scorpion_carapace", 4), ("golden_dust", 4), ("palm_plank", 10)]
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
    ingredients := [("emerald", 1), ("hardwood_plank", 8), ("jasper_crystal", 2), ("wolf_hair", 5)]
    craftDepth := 2 }

/-- Recipe for `emerald_ring` (craftDepth 2). -/
def recipe_emerald_ring : Recipe :=
  { output := "emerald_ring"
    ingredients := [("emerald", 1), ("gold_bar", 8), ("magical_cure", 2), ("obsidian_bar", 4), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `enchanted_antidote` (craftDepth 2). -/
def recipe_enchanted_antidote : Recipe :=
  { output := "enchanted_antidote"
    ingredients := [("magic_sap", 1), ("strangold_bar", 2), ("torch_cactus_flower", 1)]
    craftDepth := 2 }

/-- Recipe for `enchanted_boost_potion` (craftDepth 2). -/
def recipe_enchanted_boost_potion : Recipe :=
  { output := "enchanted_boost_potion"
    ingredients := [("bat_wing", 1), ("glowstem_leaf", 2), ("magic_sap", 1)]
    craftDepth := 2 }

/-- Recipe for `enchanted_bow` (craftDepth 2). -/
def recipe_enchanted_bow : Recipe :=
  { output := "enchanted_bow"
    ingredients := [("demon_horn", 2), ("gold_bar", 8), ("ogre_eye", 4), ("red_cloth", 3), ("spider_leg", 3)]
    craftDepth := 2 }

/-- Recipe for `enchanted_health_potion` (craftDepth 2). -/
def recipe_enchanted_health_potion : Recipe :=
  { output := "enchanted_health_potion"
    ingredients := [("glowstem_leaf", 2), ("magic_sap", 1), ("sunflower", 1)]
    craftDepth := 2 }

/-- Recipe for `enchanted_health_splash_potion` (craftDepth 2). -/
def recipe_enchanted_health_splash_potion : Recipe :=
  { output := "enchanted_health_splash_potion"
    ingredients := [("coconut", 1), ("magic_sap", 1), ("torch_cactus_flower", 2)]
    craftDepth := 2 }

/-- Recipe for `enchanter_boots` (craftDepth 2). -/
def recipe_enchanter_boots : Recipe :=
  { output := "enchanter_boots"
    ingredients := [("enchanted_fabric", 1), ("lizard_eye", 4), ("magical_plank", 8), ("priestess_orb", 2), ("vermin_leather", 5)]
    craftDepth := 2 }

/-- Recipe for `enchanter_pants` (craftDepth 2). -/
def recipe_enchanter_pants : Recipe :=
  { output := "enchanter_pants"
    ingredients := [("cursed_book", 3), ("demon_horn", 2), ("enchanted_fabric", 1), ("magical_plank", 8), ("owlbear_claw", 4), ("spider_leg", 2)]
    craftDepth := 2 }

/-- Recipe for `eternal_red_ring` (craftDepth 2). -/
def recipe_eternal_red_ring : Recipe :=
  { output := "eternal_red_ring"
    ingredients := [("adamantite_bar", 12), ("alexandrite", 1), ("desert_scorpion_carapace", 2), ("duskworm_skin", 4), ("golden_dust", 4), ("sand_snake_poison", 4)]
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
    ingredients := [("demon_horn", 2), ("demoniac_dust", 4), ("gold_bar", 8), ("owlbear_hair", 3), ("red_cloth", 3)]
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
    ingredients := [("astralyte_crystal", 2), ("cursed_flask", 6), ("emerald", 2), ("emerald_amulet", 1), ("maple_plank", 8)]
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
    ingredients := [("nettle_leaf", 2), ("sap", 1), ("shrimp", 1)]
    craftDepth := 2 }

/-- Recipe for `health_potion` (craftDepth 2). -/
def recipe_health_potion : Recipe :=
  { output := "health_potion"
    ingredients := [("nettle_leaf", 2), ("sap", 1), ("sunflower", 1)]
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
    ingredients := [("cursed_plank", 10), ("demon_horn", 5), ("efreet_cloth", 5), ("grimlet_bone", 3), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `hell_helmet` (craftDepth 2). -/
def recipe_hell_helmet : Recipe :=
  { output := "hell_helmet"
    ingredients := [("enchanted_fabric", 3), ("lava_bucket", 5), ("maple_plank", 10), ("orc_skin", 4), ("wolfrider_ponytail", 3)]
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
    ingredients := [("diamond", 2), ("efreet_cloth", 3), ("goblin_eye", 5), ("grimlet_bone", 4), ("strangold_bar", 10)]
    craftDepth := 2 }

/-- Recipe for `hell_staff` (craftDepth 2). -/
def recipe_hell_staff : Recipe :=
  { output := "hell_staff"
    ingredients := [("book_from_hell", 1), ("cursed_plank", 10), ("efreet_cloth", 3), ("imp_tail", 5), ("obsidian_bar", 5)]
    craftDepth := 2 }

/-- Recipe for `hork_helmet` (craftDepth 2). -/
def recipe_hork_helmet : Recipe :=
  { output := "hork_helmet"
    ingredients := [("bat_wing", 3), ("dark_essence", 3), ("orc_skin", 4), ("owlbear_claw", 3), ("strangold_bar", 7)]
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
    ingredients := [("cursed_book", 3), ("cursed_plank", 8), ("enchanted_fabric", 1), ("goblin_guard_foot", 3), ("owlbear_hair", 3), ("vampire_tooth", 2)]
    craftDepth := 2 }

/-- Recipe for `king_slime_sword` (craftDepth 2). -/
def recipe_king_slime_sword : Recipe :=
  { output := "king_slime_sword"
    ingredients := [("iron_bar", 8), ("jasper_crystal", 1), ("king_slimeball", 6)]
    craftDepth := 2 }

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
    ingredients := [("broken_sword", 1), ("goblin_eye", 5), ("hellhound_hair", 4), ("magical_cure", 3), ("maple_plank", 7)]
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
    ingredients := [("alexandrite", 1), ("desert_scorpion_carapace", 5), ("grimlet_bone", 4), ("marauder_hand", 4), ("palm_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `magic_wizard_hat` (craftDepth 2). -/
def recipe_magic_wizard_hat : Recipe :=
  { output := "magic_wizard_hat"
    ingredients := [("blue_slimeball", 10), ("hardwood_plank", 2), ("ogre_skin", 2), ("wolf_hair", 4)]
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

/-- Recipe for `mesh_armor` (craftDepth 2). -/
def recipe_mesh_armor : Recipe :=
  { output := "mesh_armor"
    ingredients := [("efreet_cloth", 5), ("grimlet_bone", 3), ("hellhound_hair", 5), ("mithril_bar", 10), ("rosenblood_elixir", 1)]
    craftDepth := 2 }

/-- Recipe for `mesh_legs_armor` (craftDepth 2). -/
def recipe_mesh_legs_armor : Recipe :=
  { output := "mesh_legs_armor"
    ingredients := [("dark_essence", 4), ("efreet_cloth", 5), ("mithril_bar", 10), ("orc_skin", 4), ("rosenblood_elixir", 1)]
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
    ingredients := [("diamond", 1), ("enchanted_fabric", 2), ("goblin_eye", 5), ("hellhound_hair", 5), ("mithril_bar", 7)]
    craftDepth := 2 }

/-- Recipe for `mithril_fishing_rod` (craftDepth 2). -/
def recipe_mithril_fishing_rod : Recipe :=
  { output := "mithril_fishing_rod"
    ingredients := [("cursed_flask", 3), ("cursed_plank", 3), ("goblin_guard_foot", 3), ("hellhound_hair", 3), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `mithril_gloves` (craftDepth 2). -/
def recipe_mithril_gloves : Recipe :=
  { output := "mithril_gloves"
    ingredients := [("cursed_book", 3), ("cursed_flask", 3), ("hellhound_collar", 3), ("imp_tail", 3), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `mithril_helm` (craftDepth 2). -/
def recipe_mithril_helm : Recipe :=
  { output := "mithril_helm"
    ingredients := [("diamond", 1), ("goblin_tooth", 3), ("jasper_crystal", 5), ("mithril_bar", 8), ("wolfrider_ponytail", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_pickaxe` (craftDepth 2). -/
def recipe_mithril_pickaxe : Recipe :=
  { output := "mithril_pickaxe"
    ingredients := [("broken_sword", 1), ("dark_essence", 3), ("mithril_bar", 8), ("owlbear_claw", 3), ("vampire_blood", 5)]
    craftDepth := 2 }

/-- Recipe for `mithril_platebody` (craftDepth 2). -/
def recipe_mithril_platebody : Recipe :=
  { output := "mithril_platebody"
    ingredients := [("bat_wing", 3), ("enchanted_fabric", 2), ("goblin_guard_foot", 3), ("goblin_tooth", 4), ("mithril_bar", 8)]
    craftDepth := 2 }

/-- Recipe for `mithril_platelegs` (craftDepth 2). -/
def recipe_mithril_platelegs : Recipe :=
  { output := "mithril_platelegs"
    ingredients := [("demoniac_dust", 3), ("lizard_eye", 2), ("mithril_bar", 8), ("owlbear_hair", 4), ("vampire_tooth", 3)]
    craftDepth := 2 }

/-- Recipe for `mithril_ring` (craftDepth 2). -/
def recipe_mithril_ring : Recipe :=
  { output := "mithril_ring"
    ingredients := [("dark_essence", 3), ("hellhound_hair", 4), ("lizard_eye", 2), ("mithril_bar", 8), ("wolfrider_hair", 3)]
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
    ingredients := [("demon_horn", 4), ("demoniac_dust", 4), ("obsidian_bar", 6), ("ruby", 1), ("spider_leg", 5)]
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

/-- Recipe for `piggy_armor` (craftDepth 2). -/
def recipe_piggy_armor : Recipe :=
  { output := "piggy_armor"
    ingredients := [("dead_wood_plank", 5), ("jasper_crystal", 2), ("ogre_skin", 4), ("pig_skin", 5)]
    craftDepth := 2 }

/-- Recipe for `piggy_helmet` (craftDepth 2). -/
def recipe_piggy_helmet : Recipe :=
  { output := "piggy_helmet"
    ingredients := [("cyclops_eye", 2), ("pig_skin", 6), ("steel_bar", 6), ("vampire_blood", 2)]
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
    ingredients := [("hardwood_plank", 8), ("jasper_crystal", 2), ("ruby", 1), ("wolf_hair", 5)]
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
    ingredients := [("adventurer_skull", 4), ("astralyte_crystal", 2), ("corrupted_stone", 3), ("desert_scorpion_carapace", 4), ("lava_bucket", 3), ("palm_plank", 10)]
    craftDepth := 2 }

/-- Recipe for `skullforged_pants` (craftDepth 2). -/
def recipe_skullforged_pants : Recipe :=
  { output := "skullforged_pants"
    ingredients := [("adventurer_skull", 3), ("astralyte_crystal", 2), ("demon_horn", 4), ("desert_scorpion_carapace", 4), ("dusk_beetle_shell", 3), ("palm_plank", 10)]
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
    ingredients := [("jasper_crystal", 1), ("skeleton_bone", 5), ("snakeskin", 2), ("vampire_blood", 4)]
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
    ingredients := [("magical_cure", 1), ("spider_leg", 4), ("steel_bar", 4), ("vampire_blood", 4), ("vermin_leather", 2)]
    craftDepth := 2 }

/-- Recipe for `vital_armor` (craftDepth 2). -/
def recipe_vital_armor : Recipe :=
  { output := "vital_armor"
    ingredients := [("duskworm_skin", 4), ("enchanted_fabric", 3), ("lava_bucket", 4), ("palm_plank", 10), ("ruby", 2), ("sand_snake_poison", 4)]
    craftDepth := 2 }

/-- Recipe for `vital_boots` (craftDepth 2). -/
def recipe_vital_boots : Recipe :=
  { output := "vital_boots"
    ingredients := [("desert_scorpion_carapace", 3), ("duskworm_skin", 3), ("efreet_cloth", 3), ("enchanted_fabric", 2), ("palm_plank", 12), ("sand_snake_poison", 3)]
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
    ingredients := [("blue_slimeball", 20), ("hellhound_collar", 3), ("rosenblood_elixir", 1), ("sapphire", 1), ("strangold_bar", 6)]
    craftDepth := 2 }

/-- Recipe for `white_knight_armor` (craftDepth 2). -/
def recipe_white_knight_armor : Recipe :=
  { output := "white_knight_armor"
    ingredients := [("corrupted_stone", 3), ("enchanted_fabric", 2), ("hellhound_hair", 3), ("mithril_bar", 8), ("wolfrider_ponytail", 4)]
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
    ingredients := [("goblin_eye", 4), ("hellhound_hair", 3), ("lizard_eye", 3), ("maple_plank", 7), ("wolfrider_hair", 3)]
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
    ingredients := [("enchanted_fabric", 2), ("goblin_eye", 4), ("hellhound_collar", 5), ("mithril_bar", 8), ("rosenblood_elixir", 1)]
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
    recipe_cooked_rat_meat,
    recipe_cooked_salmon,
    recipe_cooked_shrimp,
    recipe_cooked_swordfish,
    recipe_cooked_trout,
    recipe_cooked_wolf_meat,
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
    recipe_enchanted_antidote,
    recipe_enchanted_boost_potion,
    recipe_enchanted_bow,
    recipe_enchanted_health_potion,
    recipe_enchanted_health_splash_potion,
    recipe_enchanter_boots,
    recipe_enchanter_pants,
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
    recipe_piggy_armor,
    recipe_piggy_helmet,
    recipe_piggy_pants,
    recipe_prospecting_amulet,
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
theorem snapshot_recipe_count : allRecipes.length = 306 := by
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
  bankUnlockMonsterPresent := false
  initialXp := 0
  unlockMonsterLevel := 0
  bankRequiredLevel := 0
  hasOverstockItems := false
  selectBankDepositsNonempty := false
  pendingItemsNonempty := false
  sellableInventoryNonempty := false
  taskCoinsTotal := 0
  taskExchangeMinCoins := 1
  lowYieldCancelFires := false
  taskCancelFires := false
  pursueTaskFires := false
  objectiveStepFires := false
  craftReliefFires := false
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

end Formal.Liveness.GameDataFixture
