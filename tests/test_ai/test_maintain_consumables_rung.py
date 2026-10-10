"""The MAINTAIN_CONSUMABLES rung: it fires exactly when heal prep for the fight
ahead has a goal (`grind_heal_prep.maintain_consumables_goal`), and
`strategy_driver.map_means` builds that same goal (docs/PLAN_consumable_utility.md
increment 5: the chosen loadout's food, stocked to its carry)."""

from dataclasses import replace

import pytest

from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, food_carry
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import MeansKind, _fires
from tests.test_ai.fixtures import make_state

CARRY = food_carry(1)


def _gd() -> GameData:
    """Cooked fish crafted from raw fish, which has no route: the carry is
    suppliable only from raw fish already held."""
    gd = GameData()
    gd._item_stats = {
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=50, crafting_skill="cooking", crafting_level=1),
        "raw_fish": ItemStats(code="raw_fish", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"cooked_fish": {"raw_fish": 1}}
    gd._workshop_locations = {"cooking": (3, 0)}
    return gd


def _state(inventory: dict[str, int]):
    return make_state(skills={"cooking": 5}, x=1, y=1, inventory=inventory,
                      inventory_max=200)


def _ctx(*, combat_monster: str | None = "chicken",
         food: tuple[tuple[str, int], ...] = (("cooked_fish", 1),)) -> SelectionContext:
    return replace(NO_PROFILE_CONTEXT, combat_monster=combat_monster,
                   loadout=ChosenLoadout(monster="chicken", potions=(), food=food))


def test_fires_when_the_chosen_food_is_short_and_suppliable():
    assert _fires(MeansKind.MAINTAIN_CONSUMABLES, _state({"raw_fish": CARRY}), _gd(),
                  None, _ctx()) is True


def test_does_not_fire_when_the_chosen_food_is_carried():
    assert _fires(MeansKind.MAINTAIN_CONSUMABLES,
                  _state({"cooked_fish": CARRY, "raw_fish": CARRY}), _gd(),
                  None, _ctx()) is False


def test_does_not_fire_when_the_loadout_rests():
    assert _fires(MeansKind.MAINTAIN_CONSUMABLES, _state({"raw_fish": CARRY}), _gd(),
                  None, _ctx(food=())) is False


def test_does_not_fire_without_combat():
    assert _fires(MeansKind.MAINTAIN_CONSUMABLES, _state({"raw_fish": CARRY}), _gd(),
                  None, _ctx(combat_monster=None)) is False


def test_map_means_builds_the_heal_prep_goal():
    goal = map_means(MeansKind.MAINTAIN_CONSUMABLES, _gd(), _ctx(),
                     _state({"raw_fish": CARRY}))
    assert isinstance(goal, GatherMaterialsGoal)
    assert goal.needed == {"cooked_fish": CARRY}


def test_map_means_refuses_when_the_rung_is_not_due():
    with pytest.raises(ValueError, match="MAINTAIN_CONSUMABLES"):
        map_means(MeansKind.MAINTAIN_CONSUMABLES, _gd(), _ctx(),
                  _state({"cooked_fish": CARRY}))
