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


class TestSecondaryDropAdmission:
    """GAP-7 (2026-07-08): gather admission is EFFECTIVE-drop precise and
    skill-gated. A rare secondary drop opens exactly its targeted override
    gather; a skill-closed source (which can never fire in-plan — skills are
    immutable during GOAP application) is excluded even when it is the
    rate-best source, so it cannot win the yield narrowing and displace a
    workable spot (the salmon_spot trap)."""

    @staticmethod
    def _gd_pearls() -> GameData:
        gd = GameData()
        gd._item_stats = {
            "small_pearls": ItemStats(code="small_pearls", level=1, type_="resource"),
            "bass": ItemStats(code="bass", level=1, type_="resource"),
            "salmon": ItemStats(code="salmon", level=1, type_="resource"),
        }
        gd._crafting_recipes = {}
        gd._resource_drops = {"bass_spot": "bass", "salmon_spot": "salmon"}
        gd._resource_drops_full = {
            "bass_spot": [("bass", 1, 1, 1), ("small_pearls", 300, 1, 1)],
            "salmon_spot": [("salmon", 1, 1, 1), ("small_pearls", 100, 1, 1)],
        }
        gd._resource_skill = {"bass_spot": ("fishing", 30),
                              "salmon_spot": ("fishing", 40)}
        gd._bank_location = (4, 0)
        gd._taskmaster_location = (1, 2)
        return gd

    def _actions(self):
        return [
            GatherAction(resource_code="bass_spot", locations=frozenset([(0, 1)])),
            GatherAction(resource_code="bass_spot", locations=frozenset([(0, 1)]),
                         drop_item_override="small_pearls"),
            GatherAction(resource_code="salmon_spot", locations=frozenset([(0, 2)]),
                         drop_item_override="small_pearls"),
        ]

    def test_override_gather_admitted_primary_variant_dropped(self):
        """Only the pearl-producing variant of the workable spot survives:
        the primary bass gather produces nothing the closure needs, and
        salmon_spot (fishing 40 > 30) is skill-closed."""
        gd = self._gd_pearls()
        state = make_state(skills={"fishing": 30})
        goal = GatherMaterialsGoal("small_pearls", {"small_pearls": 1})
        relevant = goal.relevant_actions(self._actions(), state, gd)
        gathers = [(a.resource_code, a.drop_item_override)
                   for a in relevant if isinstance(a, GatherAction)]
        assert gathers == [("bass_spot", "small_pearls")]

    def test_skill_open_source_wins_narrowing_when_reachable(self):
        """At fishing 40 both spots are open and the yield narrowing keeps
        the rate-best source (salmon_spot, 1/100 beats 1/300 — proven
        select_gather_source core, now judged on the EFFECTIVE drop)."""
        gd = self._gd_pearls()
        state = make_state(skills={"fishing": 40})
        goal = GatherMaterialsGoal("small_pearls", {"small_pearls": 1})
        relevant = goal.relevant_actions(self._actions(), state, gd)
        gathers = [(a.resource_code, a.drop_item_override)
                   for a in relevant if isinstance(a, GatherAction)]
        assert gathers == [("salmon_spot", "small_pearls")]
