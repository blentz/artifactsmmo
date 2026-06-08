"""GatherMaterialsGoal prunes gathers for bank-covered chain materials.

The live trace showed GatherMaterials(wooden_shield) building 43-step / 21.7k-node
plans because it admitted a GatherAction for every recipe-chain resource even when
the bank already held the material. The bank-aware shopping_list prunes a gather
whose drop is fully bank/inventory-covered, leaving the withdraw — bounding the
search. A material with a real deficit keeps its gather (no false pruning).
"""

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10}}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    return gd


def _actions() -> list:
    return [
        GatherAction(resource_code="copper_rocks", locations=frozenset({(2, 0)})),
        WithdrawItemAction(code="copper_ore", quantity=10),
        WithdrawItemAction(code="copper_bar", quantity=6),
    ]


def test_bank_covered_gather_pruned():
    """Need 6 copper_bar; bank has 485 ore (covers the 60 ore) -> prune the
    copper_rocks gather, keep the withdraw."""
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state(bank_items={"copper_ore": 485})
    kept = goal.relevant_actions(_actions(), state, gd)
    assert not any(isinstance(a, GatherAction) for a in kept)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "copper_ore" for a in kept)


def test_gather_kept_when_bank_short():
    gd = _gd()
    goal = GatherMaterialsGoal(target_item="copper_dagger", needed={"copper_bar": 6})
    state = make_state(bank_items={"copper_ore": 5})
    kept = goal.relevant_actions(_actions(), state, gd)
    assert any(isinstance(a, GatherAction) for a in kept)
