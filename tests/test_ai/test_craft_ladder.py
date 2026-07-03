"""Tests for craft_utility_ladder (craft_ladder.py).

Verifies the shared action-filter helper emits CraftAction + EquipAction for a
utility target, standalone (not via CraftPotionsGoal).  The CraftPotions suite
exercises the full action-filter through the goal; this file proves the helper
is independently correct.
"""

from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.craft_ladder import craft_utility_ladder
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_craft_potions import (
    _INGREDIENT,
    _POTION,
    _RESOURCE,
    _craft_action,
    _gd_potion,
)


def test_craft_utility_ladder_emits_craft_and_equip():
    gd = _gd_potion()
    state = make_state(level=1, inventory={_INGREDIENT: 10})
    actions = [
        _craft_action(),
        GatherAction(resource_code=_RESOURCE, locations=frozenset({(2, 0)})),
        MoveAction(x=0, y=0),
    ]
    out = craft_utility_ladder(_POTION, runs=1, equip_qty=1, actions=actions,
                               state=state, game_data=gd)
    assert any(isinstance(a, CraftAction) for a in out)
    assert any(isinstance(a, EquipAction) and a.slot == "utility1_slot" for a in out)
