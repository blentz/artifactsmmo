"""next_grind_goal picks the grind rung for a LevelSkill and builds the
skill_grind GatherMaterials goal the player executes one leg of per cycle —
mirroring strategy_driver.py:866-871."""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def test_next_grind_goal_targets_the_rung_skill_grind() -> None:
    gd = _gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 1}), gd)
    goal = next_grind_goal("gearcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    # Descends to the rung's actionable_step: trinket's ore is unmet, so the
    # goal targets gear_ore. Behaviourally identical for this SHALLOW rung —
    # the player executes only leg 0, and Gather(gear_rocks) is the first
    # action either way — while a DEEP rung's direct goal would explode (see
    # test_next_grind_goal_descends_to_deepest_unmet_material). Once the ore is
    # held the step becomes the trinket itself and the craft earns the XP.
    assert goal.needed == {"gear_ore": 1}


def _deep_gd() -> GameData:
    """A rung whose recipe is a DEEP chain — the live fire_staff shape:
    fire_staff (weaponcrafting 5) <- {red_slimeball:2 (held), ash_plank:5}
    and ash_plank <- {ash_wood:10}. Targeting the RUNG makes the GOAP search
    interleave 50 gathers with crafts/deposits and EXPLODE (live 2026-07-12:
    1M nodes, no plan)."""
    gd = GameData()
    gd._item_stats = {
        "fire_staff": ItemStats(code="fire_staff", level=5, type_="weapon",
                                subtype="", crafting_skill="weaponcrafting",
                                crafting_level=5),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               subtype="craft", crafting_skill="woodcutting",
                               crafting_level=1),
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource",
                              subtype="woodcutting"),
        "red_slimeball": ItemStats(code="red_slimeball", level=1,
                                   type_="resource", subtype="mob"),
    }
    gd._crafting_recipes = {"fire_staff": {"red_slimeball": 2, "ash_plank": 5},
                            "ash_plank": {"ash_wood": 10}}
    gd._resource_drops = {"ash_tree": "ash_wood", "slime_pit": "red_slimeball"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1),
                          "slime_pit": ("alchemy", 1)}
    gd._resource_locations = {"ash_tree": [(5, 5)], "slime_pit": [(6, 6)]}
    gd._workshop_locations = {"weaponcrafting": (2, 2), "woodcutting": (1, 1)}
    return gd


def test_next_grind_goal_descends_to_deepest_unmet_material() -> None:
    """A rung with a DEEP recipe must NOT be targeted directly — the GOAP search
    over the gather/craft/deposit interleavings explodes (live Robby 2026-07-12:
    GatherMaterials(fire_staff) hit 1M nodes / no plan, so _execute_level_skill
    raised every cycle and the bot LIVELOCKED on error:other). Descend to the
    rung's actionable_step (the raw base material) — a FLAT gather that plans
    within budget, exactly as the gear path does (gather_step_target's docstring
    documents this same explosion)."""
    gd = _deep_gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=13, skills={"weaponcrafting": 6},
                          bank={"red_slimeball": 20}), gd)
    goal = next_grind_goal("weaponcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    # ash_wood (the deepest unmet leaf), NOT fire_staff (the rung).
    assert goal.needed == {"ash_wood": 10}


def test_next_grind_goal_targets_the_ready_source_material() -> None:
    """THE BUG, end to end (2026-07-13 live Robby trace): weaponcrafting rung
    fire_staff needs 5 ash_plank. Bag holds 7 fishing_net (recipe: 6 ash_plank
    each, crafting_skill gearcrafting), so ash_plank has a ready RECYCLE
    source — without `ctx` threaded in (the tier layer never asked
    `ai/obtain_sources`), the grind goal falls all the way to
    GatherMaterials(ash_wood, 10) (50 gathers of WOODCUTTING xp instead of
    weaponcrafting progress). With `ctx` wired in, ash_plank itself is a leaf
    and the goal targets it directly — the real planner
    (GatherMaterialsGoal.relevant_actions already admits licensed
    RecycleActions) then finds the Recycle(fishing_net) route."""
    gd = _deep_gd()
    gd._item_stats = {**gd._item_stats, "fishing_net": ItemStats(
        code="fishing_net", level=1, type_="amulet",
        crafting_skill="gearcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "fishing_net": {"ash_plank": 6}}
    gd._workshop_locations = {**gd._workshop_locations, "gearcrafting": (3, 3)}
    state = scenario_state(
        ScenarioCharacter(name="t", level=13, skills={"weaponcrafting": 6, "gearcrafting": 6},
                          bank={"red_slimeball": 20}), gd)
    assert next_grind_goal("weaponcrafting", state, gd).needed == {"ash_wood": 10}

    state_with_nets = scenario_state(
        ScenarioCharacter(name="t", level=13, skills={"weaponcrafting": 6, "gearcrafting": 6},
                          bank={"red_slimeball": 20}, inventory={"fishing_net": 7}), gd)
    goal = next_grind_goal("weaponcrafting", state_with_nets, gd, NO_PROFILE_CONTEXT)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    assert goal.needed == {"ash_plank": 5}


def test_next_grind_goal_targets_rung_when_materials_in_hand() -> None:
    """Once the rung's materials are held, its actionable_step IS the rung — so
    the goal targets the rung itself and the plan is the (cheap) craft that earns
    the skill XP. held+1 keeps the grind perpetual (craft ANOTHER for XP)."""
    gd = _deep_gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=13, skills={"weaponcrafting": 6},
                          bank={"red_slimeball": 20, "ash_plank": 5}), gd)
    goal = next_grind_goal("weaponcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"fire_staff": 1}


def test_next_grind_goal_descends_when_rung_held_but_materials_absent() -> None:
    """THE LIVELOCK (live Robby trace 2026-07-15, 38 error:other cycles @ ~10s
    CPU each): the character HOLDS copies of the rung (fire_staff x3) but NOT
    its materials (no ash_plank). `actionable_step(ObtainItem(fire_staff, 1))`
    is trivially satisfied by the 3 held, so it returns the RUNG — the grind
    goal became GatherMaterials(fire_staff, held+1=4), i.e. "craft a 4th
    fire_staff", whose ash_plank<-ash_wood chain is NOT in hand, so the sub-plan
    search EXPLODED to a 10s timeout / empty plan and `_execute_level_skill`
    raised every cycle. Descend on the grind quantity (held+1), not the default
    1: the deficit forces the recipe open and the goal targets the deepest
    actionable material.

    Here that material is ash_plank, not raw ash_wood: the 3 held fire_staff are
    themselves a ready RECYCLE source for ash_plank (fire_staff <- 5 ash_plank),
    so ash_plank has no unmet prerequisites and is the actionable leaf. The live
    planner then plans it in ~0.09s as Recycle(fire_staff) — the intended
    churn-grind — instead of exploding on "craft a 4th fire_staff"."""
    gd = _deep_gd()
    state = scenario_state(
        ScenarioCharacter(name="t", level=13, skills={"weaponcrafting": 6},
                          bank={"red_slimeball": 20},
                          inventory={"fire_staff": 3}), gd)
    goal = next_grind_goal("weaponcrafting", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    # ash_plank (recyclable from the held fire_staff), NOT fire_staff (held x3).
    assert goal.needed == {"ash_plank": 5}


def test_next_grind_goal_none_when_no_rung() -> None:
    gd = GameData()
    gd._item_stats = {
        "lonely": ItemStats(code="lonely", level=10, type_="resource",
                            subtype="craft", crafting_skill="gearcrafting",
                            crafting_level=10),
    }
    gd._crafting_recipes = {"lonely": {"gear_ore": 2}}
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"gearcrafting": 5}), gd)
    assert next_grind_goal("gearcrafting", state, gd) is None


def test_next_grind_goal_gather_arm_when_no_craft_rung() -> None:
    """A gather skill (alchemy) with no craftable rung at the current level
    grinds by GATHERING an in-skill resource: next_grind_goal targets the
    gatherable drop, not a craft (LevelSkill epic P4 gather arm)."""
    gd = GameData()
    gd._item_stats = {
        "small_potion": ItemStats(code="small_potion", level=5, type_="consumable",
                                  subtype="potion", crafting_skill="alchemy",
                                  crafting_level=5),
        "sunflower": ItemStats(code="sunflower", level=1, type_="resource",
                               subtype="alchemy"),
    }
    gd._crafting_recipes = {"small_potion": {"sunflower": 3}}
    gd._resource_drops = {"sunflower_field": "sunflower"}
    gd._resource_skill = {"sunflower_field": ("alchemy", 1)}
    gd._resource_locations = {"sunflower_field": [(4, 4)]}
    state = scenario_state(
        ScenarioCharacter(name="t", level=5, skills={"alchemy": 1}), gd)
    goal = next_grind_goal("alchemy", state, gd)
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.skill_grind is True
    assert goal.needed == {"sunflower": 1}
