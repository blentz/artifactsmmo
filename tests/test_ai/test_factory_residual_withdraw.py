"""Residual-extraction (x1) withdraws restore the gather-prune admissibility.

The bank-aware gather pruning (shopping_list.fully_covered_materials, used by
GatherMaterialsGoal / UpgradeEquipmentGoal.relevant_actions) credits inventory
+ bank stock at UNIT granularity: a chain material with NET deficit 0 loses its
GatherAction. That is only admissible if every credited unit is actually
extractable — but build_actions used to emit WithdrawItemAction only in fixed
batch quanta (full-chain xN, per-craft xn, plus x1 for equippables), so bank
stock below the smallest batch was credited yet unreachable and the planner
returned no plan. The fix adds one x1 WithdrawItemAction per material in the
withdraw set (bounded: at most one extra action per material, no per-quantity
ladders), making "net 0 ⇒ extractable" true.
"""

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.progression import UpgradeEquipmentGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


def _copper_chain_gd() -> GameData:
    """Copper-helmet chain: copper_helmet ← 6xcopper_bar ← 10xcopper_ore each
    (6 bars x 10 ore = 60 ore from scratch)."""
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "copper_helmet": {"copper_bar": 6},
        "copper_bar": {"copper_ore": 10},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    gd._workshop_locations = {"gearcrafting": (3, 0), "mining": (5, 0)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


def _build(gd: GameData, state: WorldState) -> list:
    return build_actions(
        game_data=gd,
        state=state,
        objective=None,
        bank_accessible=True,
        task_exchange_min_coins=6,
    )


def _withdraws(actions: list, code: str) -> list[WithdrawItemAction]:
    return [a for a in actions if isinstance(a, WithdrawItemAction) and a.code == code]


class TestTraceRegression:
    def test_cycle64_net_zero_coverage_still_plans(self):
        """Pins the 2026-06-09 trace cycle-64 failure: inv 22 copper_ore + bank
        {copper_ore: 28, copper_bar: 1} → shopping_list nets ore to 0 (the bank
        bar credits 10 ore: 6x10 − 10 = 50 needed, 22+28 = 50 held), so the
        gather is pruned — but the only ore withdraws were x10/x60 and the only
        bar withdraw x6, stranding 8 ore + the bar in the bank (reachable ore
        42 < 60 without the bar). The planner returned no plan after 9 nodes.
        crafting_target is set (player.py writes it from the chosen step), so
        the deposit keep-set protects the chain materials and DepositAll cannot
        launder residues back into batch-sized bank stacks — exactly the live
        conditions. With the x1 residual withdraws every credited unit is
        extractable and the same planner construction player.py uses must find
        a plan."""
        gd = _copper_chain_gd()
        state = make_state(
            inventory={"copper_ore": 22},
            inventory_max=100,
            bank_items={"copper_ore": 28, "copper_bar": 1},
            skills={"mining": 3, "gearcrafting": 3},
            crafting_target="copper_helmet",
        )
        goal = GatherMaterialsGoal(target_item="copper_helmet",
                                   needed={"copper_helmet": 1})
        actions = _build(gd, state)
        # The prune precondition really holds: net 0 ⇒ the gather is dropped.
        relevant = goal.relevant_actions(actions, state, gd)
        assert not any(isinstance(a, GatherAction) for a in relevant)
        plan = GOAPPlanner().plan(state, goal, actions, gd, None, budget_seconds=20.0)
        assert plan, "net-0 bank coverage must yield a withdraw/craft plan, not no_plan"

    def test_upgrade_equipment_prune_covered_by_same_fix(self):
        """UpgradeEquipmentGoal.relevant_actions has the identical net-0 gather
        prune; the factory's x1 withdraws restore its admissibility too. Bank
        residues (2 ore below the x10 batch, 1 bar below the x6 batch) are
        extractable only via x1, and the equip plan fits max_depth 32."""
        gd = _copper_chain_gd()
        state = make_state(
            inventory={"copper_ore": 48},
            inventory_max=100,
            bank_items={"copper_ore": 2, "copper_bar": 1},
            skills={"mining": 3, "gearcrafting": 3},
            crafting_target="copper_helmet",
        )
        goal = UpgradeEquipmentGoal(committed_target=("copper_helmet", "helmet_slot"))
        actions = _build(gd, state)
        relevant = goal.relevant_actions(actions, state, gd)
        assert not any(isinstance(a, GatherAction) for a in relevant)
        # The residual withdraws survive the closure-locked prune.
        assert any(a.quantity == 1 for a in _withdraws(relevant, "copper_ore"))
        assert any(a.quantity == 1 for a in _withdraws(relevant, "copper_bar"))
        plan = GOAPPlanner().plan(state, goal, actions, gd, None, budget_seconds=20.0)
        assert plan, "net-0 bank coverage must yield a withdraw/craft/equip plan"


class TestFactoryResidualWithdraws:
    def test_unit_withdraw_emitted_for_non_equippable_chain_materials(self):
        """Every material in the withdraw set gets a x1 withdraw alongside the
        batched quanta, so net-0 coverage implies an extraction path."""
        gd = _copper_chain_gd()
        actions = _build(gd, make_state())
        ore_qtys = {a.quantity for a in _withdraws(actions, "copper_ore")}
        bar_qtys = {a.quantity for a in _withdraws(actions, "copper_bar")}
        assert ore_qtys == {1, 10, 60}  # x1 residual + per-craft x10 + full-chain x60
        assert bar_qtys == {1, 6}       # x1 residual + full-chain x6

    def test_no_duplicate_when_batch_quantity_is_already_one(self):
        """A material whose full-chain quantity is already 1 gets no second x1."""
        gd = GameData()
        gd._item_stats = {
            "feather_cap": ItemStats(code="feather_cap", level=1, type_="helmet",
                                     crafting_skill="gearcrafting", crafting_level=1),
            "feather": ItemStats(code="feather", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"feather_cap": {"feather": 1}}
        gd._workshop_locations = {"gearcrafting": (3, 0)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        actions = _build(gd, make_state())
        unit = [a for a in _withdraws(actions, "feather") if a.quantity == 1]
        assert len(unit) == 1

    def test_no_duplicate_when_per_craft_quantity_is_already_one(self):
        """A leaf whose per-craft quantity is 1 already has its x1 withdraw from
        the per-craft pass; only the intermediate gains a residual x1."""
        gd = GameData()
        gd._item_stats = {
            "boots": ItemStats(code="boots", level=1, type_="boots",
                               crafting_skill="gearcrafting", crafting_level=1),
            "plank": ItemStats(code="plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
            "wood": ItemStats(code="wood", level=1, type_="resource"),
        }
        gd._crafting_recipes = {"boots": {"plank": 2}, "plank": {"wood": 1}}
        gd._workshop_locations = {"gearcrafting": (3, 0), "woodcutting": (5, 0)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        actions = _build(gd, make_state())
        wood_unit = [a for a in _withdraws(actions, "wood") if a.quantity == 1]
        assert len(wood_unit) == 1  # from the per-craft pass, not duplicated
        plank_qtys = {a.quantity for a in _withdraws(actions, "plank")}
        assert plank_qtys == {1, 2}  # residual x1 added next to the full x2

    def test_no_duplicate_for_equippable_recipe_input(self):
        """An equippable that is also a recipe input already has its equip x1
        withdraw; the residual pass must not add a second one."""
        gd = GameData()
        gd._item_stats = {
            "great_sword": ItemStats(code="great_sword", level=1, type_="weapon",
                                     crafting_skill="weaponcrafting", crafting_level=1),
            "short_sword": ItemStats(code="short_sword", level=1, type_="weapon",
                                     crafting_skill="weaponcrafting", crafting_level=1),
            "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
        }
        gd._crafting_recipes = {
            "great_sword": {"short_sword": 2},
            "short_sword": {"iron_ore": 3},
        }
        gd._workshop_locations = {"weaponcrafting": (3, 0)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        actions = _build(gd, make_state())
        sword_unit = [a for a in _withdraws(actions, "short_sword") if a.quantity == 1]
        assert len(sword_unit) == 1  # the equip-withdraw only
        assert {a.quantity for a in _withdraws(actions, "short_sword")} == {1, 2}
