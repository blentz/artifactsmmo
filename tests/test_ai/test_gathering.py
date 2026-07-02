"""Tests for GatherMaterialsGoal.relevant_actions — intermediate craft batching.

Covers:
- When a target needs >= 6 of a craftable intermediate and the raw materials
  are ample in inventory, the emitted intermediate CraftAction.quantity must
  be > 1 (inventory-bounded demand, not a hard-coded 1).
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from tests.test_ai.fixtures import make_state


def _gd_copper_dagger() -> GameData:
    """copper_dagger → copper_bar:6 (per dagger) → copper_ore:10 (per bar).

    Closure: copper_dagger (craftable, weaponcrafting lv1),
             copper_bar (craftable, mining lv1),
             copper_ore (raw; produced by copper_rocks resource).
    """
    gd = GameData()
    gd._item_stats = {
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(
            code="copper_bar", level=1, type_="resource",
            crafting_skill="mining", crafting_level=1,
        ),
        "copper_dagger": ItemStats(
            code="copper_dagger", level=1, type_="weapon",
            crafting_skill="weaponcrafting", crafting_level=1,
        ),
    }
    gd._crafting_recipes = {
        "copper_bar": {"copper_ore": 10},
        "copper_dagger": {"copper_bar": 6},
    }
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._workshop_locations = {"mining": (1, 5), "weaponcrafting": (3, 1)}
    gd._bank_location = (4, 0)
    gd._taskmaster_location = (1, 2)
    return gd


class TestIntermediateCraftSizedToDemand:
    """Intermediate CraftAction batched to inventory-bounded closure demand."""

    def test_intermediate_craft_quantity_gt_one_when_multiple_needed(self):
        """copper_dagger needs 6 copper_bars; 60 ore in inventory → CraftAction(copper_bar).quantity == 6."""
        gd = _gd_copper_dagger()
        # 60 ore in inventory: enough for 6 bars, leaving 40 free slots.
        state = make_state(
            inventory={"copper_ore": 60},
            inventory_max=100,
            bank_items={},
            skills={"mining": 5, "weaponcrafting": 5},
        )
        goal = GatherMaterialsGoal("copper_dagger", {"copper_dagger": 1})
        actions = [
            GatherAction(resource_code="copper_rocks", locations=frozenset([(0, 1)])),
            CraftAction(code="copper_bar", workshop_location=(1, 5)),
            CraftAction(code="copper_dagger", workshop_location=(3, 1)),
        ]

        relevant = goal.relevant_actions(actions, state, gd)

        craft_bars = [
            a for a in relevant
            if isinstance(a, CraftAction) and a.code == "copper_bar"
        ]
        assert craft_bars, "expected CraftAction for copper_bar in relevant_actions"
        assert craft_bars[0].quantity > 1, (
            f"intermediate craft should be batched to demand, "
            f"got quantity={craft_bars[0].quantity}"
        )
