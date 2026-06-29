"""UpgradeEquipmentGoal prunes gather actions for bank-covered chain materials.

Live bug (Robby, level 3, wooden_stick): UpgradeEquipment(copper gear) TIMES OUT
in the GOAP planner (~20k-54k nodes) because relevant_actions admitted a
GatherAction for every recipe-chain material even though the bank already held
485 copper_ore. The fix uses the bank-aware shopping_list to PRUNE gathers for
materials fully covered by bank+inventory, leaving only the WithdrawItemAction —
so the planner builds a short withdraw->craft->equip plan instead of exploding
into the gather subtree.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon"),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._item_stats["cooked_beef"] = ItemStats(code="cooked_beef", level=1, type_="consumable")
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
        "cooked_beef": {"beef": 1},  # unrelated craft
    }
    # copper_rocks gather node drops copper_ore; ash_tree drops ash_wood (unrelated).
    gd._resource_drops = {"copper_rocks": "copper_ore", "ash_tree": "ash_wood"}
    gd._resource_locations = {"copper_rocks": [(2, 0)], "ash_tree": [(5, 5)]}
    return gd


def _actions() -> list:
    return [
        CraftAction(code="copper_dagger", quantity=1),
        CraftAction(code="copper_bar", quantity=1),
        CraftAction(code="cooked_beef", quantity=1),  # unrelated craft — must be pruned
        EquipAction(code="copper_dagger", slot="weapon_slot"),
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
        GatherAction(resource_code="ash_tree", locations=frozenset({(5, 5)})),  # unrelated gather
        WithdrawItemAction(code="copper_ore", quantity=10),
        WithdrawItemAction(code="copper_bar", quantity=6),
        WithdrawItemAction(code="cooked_beef", quantity=1),  # unrelated withdraw — must be pruned
        FightAction(monster_code="chicken", locations=frozenset({(1, 1)})),  # combat — pruned
        RecycleAction(code="copper_dagger", quantity=1),  # recycle — pruned
    ]


def test_bank_covered_gather_is_pruned():
    """Bank holds enough copper_ore for the whole chain -> the copper_rocks
    gather is dropped; the copper_ore withdraw survives."""
    gd = _gd()
    goal = UpgradeEquipmentGoal(committed_target=("copper_dagger", "weapon_slot"))
    state = make_state(bank_items={"copper_ore": 485})
    kept = goal.relevant_actions(_actions(), state, gd)
    reprs = {repr(a) for a in kept}
    assert not any(isinstance(a, GatherAction) for a in kept), reprs
    assert any(isinstance(a, WithdrawItemAction) and a.code == "copper_ore" for a in kept)
    # The chain crafts + equip stay.
    assert "Craft(copper_dagger×1)" in reprs
    assert "Craft(copper_bar×1)" in reprs
    assert "Equip(copper_dagger->weapon_slot)" in reprs
    # Unrelated actions outside the recipe closure are pruned (the real explosion
    # source: ALL crafts + Fight/Recycle/unrelated gathers/withdraws).
    assert "Craft(cooked_beef×1)" not in reprs
    assert not any(isinstance(a, FightAction) for a in kept)
    assert not any(isinstance(a, RecycleAction) for a in kept)
    assert not any(isinstance(a, WithdrawItemAction) and a.code == "cooked_beef" for a in kept)


def test_gather_kept_when_bank_short():
    """Bank covers only part of the ore -> the deficit still needs gathering, so
    the copper_rocks gather is RETAINED (never prune the only path to a deficit)."""
    gd = _gd()
    goal = UpgradeEquipmentGoal(committed_target=("copper_dagger", "weapon_slot"))
    state = make_state(bank_items={"copper_ore": 5})  # need 60, have 5
    kept = goal.relevant_actions(_actions(), state, gd)
    assert any(isinstance(a, GatherAction) for a in kept)


def test_gather_kept_when_no_bank():
    """No bank stock -> all gathers retained (no false pruning)."""
    gd = _gd()
    goal = UpgradeEquipmentGoal(committed_target=("copper_dagger", "weapon_slot"))
    state = make_state(bank_items={})
    kept = goal.relevant_actions(_actions(), state, gd)
    assert any(isinstance(a, GatherAction) for a in kept)


# ---- planner-level admissibility / end-to-end ----


def _shallow_gd() -> GameData:
    """A shallow chain (target <- bar <- ore) where a from-scratch plan fits
    inside the goal's max_depth, so the planner CAN find a gather-based plan."""
    gd = GameData()
    gd._item_stats = {
        "tin_blade": ItemStats(
            code="tin_blade", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1),
        "tin_bar": ItemStats(
            code="tin_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1),
        "tin_ore": ItemStats(code="tin_ore", level=1, type_="resource"),
    }
    # 1 blade <- 2 bar <- 2 ore each = 4 ore total -> well under max_depth 32.
    gd._crafting_recipes = {"tin_blade": {"tin_bar": 2}, "tin_bar": {"tin_ore": 2}}
    gd._resource_drops = {"tin_rocks": "tin_ore"}
    gd._resource_skill = {"tin_rocks": ("mining", 1)}
    gd._resource_locations = {"tin_rocks": [(1, 0)]}
    gd._workshop_locations = {"weaponcrafting": (0, 0), "mining": (0, 0)}
    return gd


def _shallow_actions(gd: GameData) -> list:
    return [
        CraftAction(code="tin_blade", quantity=1, workshop_location=(0, 0)),
        CraftAction(code="tin_bar", quantity=1, workshop_location=(0, 0)),
        EquipAction(code="tin_blade", slot="weapon_slot"),
        GatherAction(resource_code="tin_rocks", locations=frozenset({(1, 0)})),
        WithdrawItemAction(code="tin_ore", quantity=4),
        WithdrawItemAction(code="tin_bar", quantity=2),
    ]


def test_planner_uses_bank_short_plan():
    """Bank covers the ore -> planner finds a short WITHDRAW->craft->equip plan."""
    gd = _shallow_gd()
    goal = UpgradeEquipmentGoal(
        initial_equipment={"weapon_slot": None}, committed_target=("tin_blade", "weapon_slot"))
    state = make_state(equipment={"weapon_slot": None}, bank_items={"tin_ore": 50}, inventory_max=120)
    plan = GOAPPlanner().plan(state, goal, _shallow_actions(gd), gd)
    reprs = [repr(a) for a in plan]
    assert reprs, "expected a plan"
    assert any(isinstance(a, WithdrawItemAction) and a.code == "tin_ore" for a in plan)
    assert not any(isinstance(a, GatherAction) for a in plan)
    assert reprs[-1] == "Equip(tin_blade->weapon_slot)"


def test_planner_admissible_gather_path_when_no_bank():
    """No bank -> the reachable gather->craft->equip plan is NOT falsely pruned;
    the planner still finds it (proves admissibility is preserved)."""
    gd = _shallow_gd()
    goal = UpgradeEquipmentGoal(
        initial_equipment={"weapon_slot": None}, committed_target=("tin_blade", "weapon_slot"))
    state = make_state(equipment={"weapon_slot": None}, bank_items={}, inventory_max=120)
    plan = GOAPPlanner().plan(state, goal, _shallow_actions(gd), gd)
    assert plan, "expected a reachable gather-based plan"
    assert any(isinstance(a, GatherAction) for a in plan)
    assert repr(plan[-1]) == "Equip(tin_blade->weapon_slot)"


# ---- monster-drop chain materials (run-18 trace 2026-06-12 20:23) ----


def _feather_gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "feather_coat": ItemStats(code="feather_coat", level=5, type_="body_armor",
                                  crafting_skill="gearcrafting", crafting_level=5),
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "feather_coat": {"feather": 5, "ash_plank": 2},
        "ash_plank": {"ash_wood": 10},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._resource_locations = {"ash_tree": [(6, 1)]}
    gd._workshop_locations = {"gearcrafting": (3, 1), "woodcutting": (1, 1)}
    gd._bank_location = (4, 0)
    return gd


def test_withdraw_of_banked_monster_drop_is_kept():
    """Run-18 trace 2026-06-12 20:23: UpgradeEquipment(feather_coat ->
    body_armor_slot) was unplannable EVERY cycle (111 nodes, plan_len 0) with
    4 feathers in inventory and 3 in the bank — the withdrawable set covered
    only craftable intermediates + the target + RESOURCE drops, and feather is
    a MONSTER drop (chicken). The identical defect was already fixed in
    GatherMaterialsGoal (run-17 c94); every material in the full recipe
    closure must be withdrawable here too."""
    gd = _feather_gd()
    goal = UpgradeEquipmentGoal(
        initial_equipment={"body_armor_slot": None},
        committed_target=("feather_coat", "body_armor_slot"))
    state = make_state(
        equipment={"body_armor_slot": None},
        skills={"gearcrafting": 5, "woodcutting": 4},
        inventory={"feather": 4, "ash_plank": 3}, inventory_max=112,
        bank_items={"feather": 3},
    )
    actions = [
        WithdrawItemAction(code="feather", quantity=1, bank_location=(4, 0)),
        CraftAction(code="feather_coat", quantity=1, workshop_location=(3, 1)),
        EquipAction(code="feather_coat", slot="body_armor_slot"),
    ]
    kept = goal.relevant_actions(actions, state, gd)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "feather"
               for a in kept), {repr(a) for a in kept}


def test_planner_crafts_gear_from_banked_monster_drop():
    """Planner-level run-18 repro: 4/5 feathers in inventory, 1 short, 3 in
    the bank, planks on hand, skill met -> withdraw(feather) -> craft ->
    equip, not plan_len 0."""
    gd = _feather_gd()
    goal = UpgradeEquipmentGoal(
        initial_equipment={"body_armor_slot": None},
        committed_target=("feather_coat", "body_armor_slot"))
    state = make_state(
        x=3, y=-2,
        equipment={"body_armor_slot": None},
        skills={"gearcrafting": 5, "woodcutting": 4},
        inventory={"feather": 4, "ash_plank": 3}, inventory_max=112,
        bank_items={"feather": 3},
    )
    actions = [
        WithdrawItemAction(code="feather", quantity=1, bank_location=(4, 0)),
        CraftAction(code="feather_coat", quantity=1, workshop_location=(3, 1)),
        EquipAction(code="feather_coat", slot="body_armor_slot"),
    ]
    plan = GOAPPlanner().plan(state, goal, actions, gd)
    assert plan, "expected withdraw->craft->equip plan for bank-stocked feather_coat"
    assert any(isinstance(a, WithdrawItemAction) and a.code == "feather" for a in plan)
    assert repr(plan[-1]) == "Equip(feather_coat->body_armor_slot)"
