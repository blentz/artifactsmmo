"""Tests for CraftPotionsGoal: stock and wear the CHOSEN loadout's next potion
short of its carry (docs/PLAN_consumable_utility.md increment 5).

The batch is `potion_supply.potion_batch` over the goal's loadout, frozen at
construction (the seed). `value` reads the batch's equip quantity,
`is_satisfied` is "the seeded batch landed", and `batch_equip` names the one
equip, into the slot `utility_slot_for` picks with the loadout's potions kept.
The batch arithmetic itself is pinned in test_potion_supply.py.
"""

import dataclasses

from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

_HEAL = "small_health_potion"
_BOOST = "fire_boost_potion"
_OTHER = "minor_health_potion"
_INGREDIENT = "sunflower"
_RESOURCE = "sunflower_field"
_MONSTER = "wolf"


def _gd() -> GameData:
    """Two alchemy potions brewed from a gatherable sunflower."""
    gd = GameData()
    gd._item_stats = {
        _HEAL: ItemStats(code=_HEAL, level=1, type_="utility", hp_restore=30,
                         crafting_skill="alchemy", crafting_level=1),
        _BOOST: ItemStats(code=_BOOST, level=1, type_="utility", dmg_elements={"fire": 10},
                          crafting_skill="alchemy", crafting_level=1),
        _OTHER: ItemStats(code=_OTHER, level=1, type_="utility", hp_restore=10),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_HEAL: {_INGREDIENT: 1}, _BOOST: {_INGREDIENT: 1}}
    gd._resource_drops = {_RESOURCE: _INGREDIENT}
    gd._resource_locations = {_RESOURCE: [(2, 0)]}
    gd._workshop_locations = {"alchemy": (3, 0)}
    return gd


_LOADOUT = ChosenLoadout(monster=_MONSTER, potions=((_HEAL, 1), (_BOOST, 1)), food=())


def _state(slot1: str | None = None, qty1: int = 0, slot2: str | None = None,
           qty2: int = 0, **kw) -> WorldState:  # type: ignore[no-untyped-def]
    base = make_state(level=10, **kw)
    return dataclasses.replace(
        base, equipment={**base.equipment, "utility1_slot": slot1, "utility2_slot": slot2},
        utility1_slot_quantity=qty1, utility2_slot_quantity=qty2)


def _worn(state: WorldState, slot: str, code: str, qty: int) -> WorldState:
    return dataclasses.replace(state, equipment={**state.equipment, slot: code},
                               **{f"{slot}_quantity": qty})


def test_preemptive_flag():
    assert CraftPotionsGoal.preemptive is True


def test_desired_state_empty():
    assert CraftPotionsGoal().desired_state(make_state(), _gd()) == {}


def test_repr():
    assert repr(CraftPotionsGoal()) == "CraftPotionsGoal"


# ── value ────────────────────────────────────────────────────────────────────

def test_value_is_the_batch_equip_quantity():
    """Nothing worn, 3 heals held, sunflowers for the rest: the batch equips
    the heal's whole carry of 20."""
    state = _state(inventory={_HEAL: 3, _INGREDIENT: 50})
    assert CraftPotionsGoal(loadout=_LOADOUT).value(state, _gd()) == 20.0


def test_value_reads_the_next_chosen_potion_once_the_first_is_carried():
    state = _state(_HEAL, 20, inventory={_INGREDIENT: 7})
    assert CraftPotionsGoal(loadout=_LOADOUT).value(state, _gd()) == 7.0


def test_value_zero_without_a_batch():
    full = _state(_HEAL, 20, _BOOST, 20)
    assert CraftPotionsGoal(loadout=_LOADOUT).value(full, _gd()) == 0.0
    assert CraftPotionsGoal().value(_state(inventory={_INGREDIENT: 50}), _gd()) == 0.0


# ── is_satisfied ─────────────────────────────────────────────────────────────

def test_seeded_goal_is_satisfied_once_its_batch_is_worn():
    """Seeded on the heal batch (12 worn, 8 more): satisfied at 20 worn, and
    not before, whatever the boost's stock."""
    gd = _gd()
    seed = _state(_HEAL, 12, inventory={_INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=seed)
    assert goal.is_satisfied(seed) is False
    assert goal.is_satisfied(_worn(seed, "utility1_slot", _HEAL, 19)) is False
    assert goal.is_satisfied(_worn(seed, "utility1_slot", _HEAL, 20)) is True


def test_unseeded_goal_without_game_data_owes_nothing():
    assert CraftPotionsGoal(loadout=_LOADOUT).is_satisfied(_state()) is True


def test_unseeded_goal_with_game_data_asks_whether_there_is_a_batch():
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=_gd())
    assert goal.is_satisfied(_state(inventory={_INGREDIENT: 50})) is False
    assert goal.is_satisfied(_state(_HEAL, 20, _BOOST, 20)) is True


def test_a_goal_with_no_loadout_is_satisfied_on_construction():
    """No chosen loadout (no fight ahead): no batch is seeded and none exists."""
    state = _state(inventory={_INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=None, game_data=_gd(), state=state)
    assert goal.is_satisfied(state) is True
    assert goal.batch_equip(state) is None


# ── batch_equip / batch_obtain ──────────────────────────────────────────────

def test_batch_equip_names_the_seeded_batch_into_a_free_slot():
    gd = _gd()
    state = _state(inventory={_INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=state)
    assert goal.batch_equip(state) == EquipAction(code=_HEAL, slot="utility1_slot", quantity=20)


def test_batch_equip_shrinks_to_what_is_still_unworn_and_ends_when_worn():
    gd = _gd()
    state = _state(inventory={_INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=state)
    part = _worn(state, "utility1_slot", _HEAL, 6)
    assert goal.batch_equip(part) == EquipAction(code=_HEAL, slot="utility1_slot", quantity=14)
    assert goal.batch_equip(_worn(state, "utility1_slot", _HEAL, 20)) is None


def test_batch_equip_never_evicts_the_loadouts_other_potion():
    """Both slots full: the chosen heal (5) in slot 1, an unchosen potion (40)
    in slot 2. The boost batch displaces the unchosen stack, though it is the
    larger one; without the keep set it would evict the heal."""
    gd = _gd()
    state = _state(_HEAL, 20, _OTHER, 40, inventory={_INGREDIENT: 50})
    state = _worn(state, "utility1_slot", _HEAL, 5)
    goal = CraftPotionsGoal(
        loadout=ChosenLoadout(monster=_MONSTER, potions=((_BOOST, 1), (_HEAL, 1)), food=()),
        game_data=gd, state=state)
    equip = goal.batch_equip(state)
    assert equip is not None and equip.code == _BOOST
    assert equip.slot == "utility2_slot"


def test_batch_equip_with_no_loadout_keeps_nothing(monkeypatch):
    """A batch seeded without a loadout (only reachable by forcing the seed)
    has no potion to keep: the smaller stack goes."""
    monkeypatch.setattr("artifactsmmo_cli.ai.goals.craft_potions.potion_batch",
                        lambda *_a: (_BOOST, 0, 3))
    state = _state(_HEAL, 5, _OTHER, 40, inventory={_BOOST: 3})
    goal = CraftPotionsGoal(loadout=None, game_data=_gd(), state=state)
    assert goal.batch_equip(state) == EquipAction(code=_BOOST, slot="utility1_slot", quantity=3)


def test_batch_obtain_asks_for_the_potions_the_bag_lacks():
    gd = _gd()
    state = _state(inventory={_HEAL: 4, _INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=state)
    obtain = goal.batch_obtain(state)
    assert isinstance(obtain, GatherMaterialsGoal)
    assert obtain.needed == {_HEAL: 20}


def test_batch_obtain_none_once_the_bag_holds_the_batch():
    gd = _gd()
    state = _state(inventory={_INGREDIENT: 50})
    goal = CraftPotionsGoal(loadout=_LOADOUT, game_data=gd, state=state)
    stocked = dataclasses.replace(state, inventory={_HEAL: 20})
    assert goal.batch_obtain(stocked) is None
    assert CraftPotionsGoal().batch_obtain(state) is None
