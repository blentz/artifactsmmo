"""UpgradeEquipmentGoal.is_plannable: the depth-based reachability gate
(formal/Formal/PlannerDepthBound.lean bounds `max_depth` against a real plan's
length; `min_plan_length.py`'s own PROOF STATUS paragraph is explicit that the
SUM fed into that bound is an A*-budget heuristic, not a proven lower bound —
"provably-sound" overstated that and is not repeated here).

A committed UpgradeEquipment target that needs more gather actions than the
goal's max_depth can NEVER be planned (the planner never returns a plan longer
than max_depth), so the arbiter must skip it instead of burning the 90s search
budget.

Task 3 (planner-gather-batching) switched the mint term from raw-UNIT counting
(`ceil_gathers(min_gathers)`) to `min_gather_steps` (distinct raw leaves still
unmet). `copper_boots` (80 raw copper_ore through ONE recipe leaf) and
`feather_coat` (35 raw units through TWO leaves) both went from "rejected by
the unit count" to "admitted by the leaf count" — verified below not just by
the formula but by driving the REAL `GOAPPlanner` over the REAL
`build_actions` pool and confirming an actual plan exists within `max_depth`.
That is not automatic: a chain whose craft batching is itself bounded by
inventory space at more than one recipe tier (`steel_boots`, three tiers) can
still be admitted by leaf-counting while genuinely unplannable — see
`test_strategy_driver.py`'s still-failing `steel_boots` cases, a real residual
this task's report documents rather than hides.
"""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from tests.test_ai.fixtures import make_state


def _gd_boots() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {
        "copper_boots": {"copper_bar": 8},
        "copper_bar": {"copper_ore": 10},
    }
    return gd


def _gd_boots_plannable() -> GameData:
    """`_gd_boots` plus the map/item data `build_actions` needs to construct a
    real action pool — used only where a test drives the REAL planner, not
    just `is_plannable`, so the other `_gd_boots()` call sites (which never
    touch locations) are left alone."""
    gd = _gd_boots()
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(3, 3)]}
    gd._workshop_locations = {"mining": (2, 2), "gearcrafting": (2, 2)}
    gd._item_stats = {
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    return gd


def test_is_plannable_admits_from_scratch_copper_boots():
    """copper_boots from scratch = 8 copper_bar x 10 copper_ore = 80 raw units
    through ONE recipe leaf. Under the pre-Task-3 (raw-UNIT) mint term, 80
    units alone exceeded `max_depth` 32, so this asserted `is_plannable(...)
    is False` — "the real Robby first-cycle stall".

    Task 3 (planner-gather-batching) switched the mint term to
    `min_gather_steps`, which counts DISTINCT raw leaves still unmet, not
    units — `copper_boots` has exactly one (`copper_ore`), so the bound is now
    `min_gather_steps=1 + min_crafts=2 + equip=1 = 4`, well under 32, and
    `is_plannable` correctly flips to True. Not a mechanical rebaseline: the
    REAL `GOAPPlanner` over the REAL `build_actions` pool for this exact
    scratch state finds a 19-action plan in 14,717 nodes with no timeout, so
    the new verdict matches what the planner can actually do."""
    goal = UpgradeEquipmentGoal(committed_target=("copper_boots", "boots_slot"))
    state = make_state(inventory={}, bank_items={})  # boots_slot empty by default
    assert goal.is_plannable(state, _gd_boots()) is True

    gd = _gd_boots_plannable()
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd, None, budget_seconds=30.0)
    assert plan, "is_plannable's True verdict must be backed by a real plan"
    assert not planner.last_stats.timed_out


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


def _gd_feather_coat_plannable() -> GameData:
    """`_gd_feather_coat` plus the map/item data `build_actions` needs — see
    `_gd_boots_plannable`'s docstring for why this is a separate fixture."""
    gd = _gd_feather_coat()
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 1)
    gd._resource_drops = {"feather_source": "feather", "ash_tree": "ash_wood"}
    gd._resource_locations = {"feather_source": [(3, 3)], "ash_tree": [(4, 4)]}
    gd._workshop_locations = {"woodcutting": (2, 2), "gearcrafting": (2, 2)}
    gd._item_stats = dict(gd._item_stats)
    gd._item_stats["feather"] = ItemStats(code="feather", level=1, type_="resource")
    gd._item_stats["ash_wood"] = ItemStats(code="ash_wood", level=1, type_="resource")
    gd._item_stats["ash_plank"] = ItemStats(code="ash_plank", level=1, type_="resource",
                                            crafting_skill="woodcutting", crafting_level=1)
    return gd


def test_is_plannable_admits_from_scratch_feather_coat():
    """feather_coat from scratch: owned ash_wood:10 covers 10 of the 40 ash_wood
    two ash_plank need, leaving 30 more ash_wood + 5 feathers = 35 raw units
    through TWO recipe leaves (`ash_wood`, `feather`).

    Named (and asserted) the opposite of its predecessor
    `test_is_plannable_rejects_from_scratch_feather_coat`, which asserted
    `is_plannable(...) is False` under the pre-Task-3 raw-UNIT mint term
    (`ceil_gathers(35,1) + min_crafts(3) + equip(1) = 39 > 32`). Task 3
    (planner-gather-batching) switched the mint term to `min_gather_steps`,
    which counts distinct raw leaves still unmet, not units — TWO here, so the
    bound is `min_gather_steps=2 + min_crafts=2 + equip=1 = 5`, well under 32.
    Verified by driving the REAL `GOAPPlanner` over the REAL `build_actions`
    pool for this exact state: it finds a 10-action plan in 31,846 nodes with
    no timeout, so the new True verdict matches what the planner can actually
    do, not just what the formula claims."""
    state = make_state(
        skills={"gearcrafting": 5},
        inventory={"ash_wood": 10},
        equipment={"body_armor_slot": None},
    )
    goal = UpgradeEquipmentGoal(
        committed_target=("feather_coat", "body_armor_slot"),
    )
    assert goal.is_plannable(state, _gd_feather_coat()) is True

    gd = _gd_feather_coat_plannable()
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    planner = GOAPPlanner()
    plan = planner.plan(state, goal, actions, gd, None, budget_seconds=30.0)
    assert plan, "is_plannable's True verdict must be backed by a real plan"
    assert not planner.last_stats.timed_out


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
