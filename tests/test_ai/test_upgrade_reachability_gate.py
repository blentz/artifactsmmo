"""UpgradeEquipmentGoal.is_plannable: the provably-sound depth-based reachability
gate (formal/Formal/PlannerDepthBound.lean).

A committed UpgradeEquipment target that needs more gather actions than the
goal's max_depth can NEVER be planned (the planner never returns a plan longer
than max_depth), so the arbiter must skip it instead of burning the 90s search
budget. copper_boots from scratch = 8 copper_bar × 10 copper_ore = 80 gathers ≫
max_depth 32 — the real Robby first-cycle stall.
"""

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from tests.test_ai.fixtures import make_state


def _gd_boots() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    return gd


def test_not_plannable_when_from_scratch_exceeds_max_depth():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={})  # boots_slot empty by default
    assert goal.is_plannable(state, _gd_boots()) is False


def test_plannable_when_materials_in_inventory():
    # 8 copper_bar in hand ⇒ 0 gathers ⇒ short craft+equip plan within max_depth.
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={"copper_bar": 8})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_materials_in_bank():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={"copper_bar": 8})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_target_already_owned():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={"copper_boots": 1})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_already_satisfied():
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(equipment={"boots_slot": "copper_boots"})
    assert goal.is_plannable(state, _gd_boots()) is True


def test_plannable_when_no_upgrade_target():
    """Uncommitted goal with no available upgrade: find_upgrade_target is None,
    so there is nothing to gate — defer to normal planning (returns True)."""
    goal = UpgradeEquipmentGoal()  # uncommitted, empty game_data ⇒ no upgrade
    state = make_state(inventory={})
    assert goal.is_plannable(state, GameData()) is True


def _gd_skill_gated() -> GameData:
    """copper_legs_armor needs gearcrafting 5 — the under-skill craftable shape
    (mats nearly in hand, skill 2 < 5). Post-P3a a LevelSkill grind makes it
    reachable, so is_plannable admits it rather than pruning at the skill gate."""
    gd = _gd_boots()
    gd._item_stats = {
        "copper_legs_armor": ItemStats(code="copper_legs_armor", level=6,
                                       type_="leg_armor", resistance={"earth": 6},
                                       crafting_skill="gearcrafting",
                                       crafting_level=5),
    }
    gd._crafting_recipes = dict(gd._crafting_recipes)
    gd._crafting_recipes["copper_legs_armor"] = {"copper_bar": 5}
    return gd


def test_plannable_when_crafting_skill_below_recipe_level():
    """LevelSkill epic P3a: an under-skill craftable equippable is NO LONGER
    pruned by is_plannable. relevant_actions admits a scoped LevelSkill, so the
    gated final craft is reachable via a grind->craft->equip sequence — the
    former crafting-skill fast-fail is retired (mirrors P2 for GatherMaterials).
    With the materials in hand the depth bound is satisfied, so the goal stays
    plannable."""
    goal = UpgradeEquipmentGoal(committed_target=("copper_legs_armor", "leg_armor_slot"))
    state = make_state(inventory={"copper_bar": 5},
                       skills={"gearcrafting": 2, "mining": 3, "woodcutting": 2,
                               "fishing": 1, "weaponcrafting": 1, "jewelrycrafting": 1,
                               "cooking": 1, "alchemy": 1})
    assert goal.is_plannable(state, _gd_skill_gated()) is True


def test_plannable_when_crafting_skill_meets_recipe_level():
    goal = UpgradeEquipmentGoal(committed_target=("copper_legs_armor", "leg_armor_slot"))
    state = make_state(inventory={"copper_bar": 5},
                       skills={"gearcrafting": 5, "mining": 3, "woodcutting": 2,
                               "fishing": 1, "weaponcrafting": 1, "jewelrycrafting": 1,
                               "cooking": 1, "alchemy": 1})
    assert goal.is_plannable(state, _gd_skill_gated()) is True


def test_skill_gate_skipped_when_target_owned():
    """Owned-but-unequipped target: only the equip remains, no craft needed —
    the skill gate must not block the short equip plan."""
    goal = UpgradeEquipmentGoal(committed_target=("copper_legs_armor", "leg_armor_slot"))
    state = make_state(inventory={"copper_legs_armor": 1},
                       skills={"gearcrafting": 2, "mining": 3, "woodcutting": 2,
                               "fishing": 1, "weaponcrafting": 1, "jewelrycrafting": 1,
                               "cooking": 1, "alchemy": 1})
    assert goal.is_plannable(state, _gd_skill_gated()) is True


def _gd_feather_coat() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "feather_coat": {"feather": 5, "ash_plank": 2},
        "ash_plank": {"ash_wood": 20},
    }
    gd._item_stats = {
        "feather_coat": ItemStats(
            code="feather_coat", level=5,
            type_="body_armor", crafting_skill="gearcrafting", crafting_level=5,
        ),
    }
    return gd


def test_is_plannable_rejects_from_scratch_feather_coat():
    """feather_coat from scratch: true plan far exceeds max_depth 32 -> is_plannable
    False (was wrongly True because min_gathers omitted crafts+equip)."""
    # owned: ash_wood:10 — 2 planks need 40 ash_wood, so 30 more ash_wood + 5 feathers;
    # min_plan_length = ceil_gathers(35,1) + min_crafts(3) + equip(1) = 39 > 32
    state = make_state(
        skills={"gearcrafting": 5},
        inventory={"ash_wood": 10},
        equipment={"body_armor_slot": None},
    )
    goal = UpgradeEquipmentGoal(
        committed_target=("feather_coat", "body_armor_slot"),
    )
    assert goal.is_plannable(state, _gd_feather_coat()) is False


def test_is_plannable_admits_short_chain():
    """Same gear with planks already in hand: plan = ceil_gathers(5,1) + 1 craft + 1 equip
    = 7 <= 15 -> True."""
    state = make_state(
        skills={"gearcrafting": 5},
        inventory={"ash_plank": 2},
        equipment={"body_armor_slot": None},
    )
    goal = UpgradeEquipmentGoal(
        committed_target=("feather_coat", "body_armor_slot"),
    )
    assert goal.is_plannable(state, _gd_feather_coat()) is True
