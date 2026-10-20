"""Drop winnability judged against a projected fighter (global gear objective,
spec 2026-10-18 §2.3).

A monster-drop item is achievable iff the dropping monster is beatable by SOME
loadout of achievable items, not by the gear the character wears. `ObtainModel`
takes that loadout as `fighter`: every DROP route's WINNABLE gate is asked of
it, while stock (bag, bank, pocket) is still read from the real `state`.
"""

from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"
NOW = datetime(2026, 10, 18, tzinfo=UTC)
CTX = SelectionContext(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                       initial_xp=0, task_exchange_min_coins=0, combat_monster=None)
WINS = "artifactsmmo_cli.ai.obtain_model.drop_routes.drop_fight_winnable"
"""Patched to True where a test asks only about spawns, not about the fight."""


def _character(gd: GameData, level: int = 10, equipment: dict[str, str] | None = None,
               inventory: dict[str, int] | None = None,
               skills: dict[str, int] | None = None) -> WorldState:
    return scenario_state(ScenarioCharacter(name="fighter", level=level, derive_combat_stats=True,
                                            equipment=equipment or {}, inventory=inventory or {},
                                            skills=skills or {}), gd)


@pytest.fixture(scope="module")
def gd() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture
def fresh_gd() -> GameData:
    """A GameData of this test's own: the event overlay below mutates it."""
    return load_bundle_game_data(BUNDLE)


def test_a_fighter_that_wins_opens_the_drop_the_wearer_cannot(gd: GameData) -> None:
    """Unarmed, the character loses to a chicken (zero attack); the same
    character holding an iron sword wins. `feather` has no route but the
    chicken's drop, so only the fighter opens it."""
    state = _character(gd)
    fighter = _character(gd, equipment={"weapon_slot": "iron_sword"},
                         inventory={"iron_sword": 1})
    assert not ObtainModel(state, gd, CTX, NOW).feasible("feather", 1, PIECE_POLICY)
    assert ObtainModel(state, gd, CTX, NOW, fighter=fighter).feasible(
        "feather", 1, PIECE_POLICY)


def test_the_fighters_inventory_is_never_stock(gd: GameData) -> None:
    """The fighter is a projection: copies it holds are not in the bag. An
    unarmed fighter holding feathers cannot win the chicken, so feathers stay
    out of reach, and the walk's on hand is the real state's bag."""
    state = _character(gd)
    fighter = _character(gd, inventory={"feather": 5})
    model = ObtainModel(state, gd, CTX, NOW, fighter=fighter)
    assert model.in_bag("feather") == 0
    assert model.walk_graph("feather", PIECE_POLICY).on_hand.get("feather", 0) == 0
    assert not model.feasible("feather", 1, PIECE_POLICY)


def test_an_event_monster_that_is_not_live_drops_nothing(fresh_gd: GameData) -> None:
    """`bandit_lizard` stands only on its event's candidate maps: with no
    event live it spawns nowhere (neither `all_monster_locations` nor
    `monster_spawn_known` lists it), so `lizard_eye`, its drop alone, is out
    of reach however strong the fighter. With its event live on a read tile
    it spawns there and the drop opens."""
    state = _character(fresh_gd)
    event = fresh_gd.world.event_code_of_content["bandit_lizard"]
    with patch(WINS, return_value=True):
        assert not ObtainModel(state, fresh_gd, CTX, NOW).feasible(
            "lizard_eye", 1, PIECE_POLICY)
        x, y = fresh_gd.world.event_monster_locations["bandit_lizard"][0]
        fresh_gd.active_event_codes = {event}
        fresh_gd.active_event_maps = {event: [(x, y, "overworld")]}
        assert ObtainModel(state, fresh_gd, CTX, NOW).feasible(
            "lizard_eye", 1, PIECE_POLICY)


def test_a_static_monster_on_another_layer_still_drops(gd: GameData) -> None:
    """`goblin_guard` spawns only underground, in a reachable region: the
    overworld-only live index cannot see it, the routable-spawn predicate can,
    and the action factory builds its fight. `goblin_guard_foot` is its drop
    alone, so it is achievable only because the policy asks `spawn_known`."""
    state = _character(gd)
    assert not gd.all_monster_locations.get("goblin_guard")
    with patch(WINS, return_value=True):
        model = ObtainModel(state, gd, CTX, NOW)
        assert model.feasible("goblin_guard_foot", 1, PIECE_POLICY)
        assert not model.feasible("goblin_guard_foot", 1,
                                  replace(PIECE_POLICY, spawn_known=False))


def test_skill_gates_are_a_cost_not_a_veto(gd: GameData) -> None:
    """`mithril_shield` needs gearcrafting 40; the character is at 23 and
    holds every material. Climbing a skill is a cost, never a veto (§2.1)."""
    recipe = gd.crafting_recipe("mithril_shield")
    stats = gd.item_stats("mithril_shield")
    assert recipe is not None and stats is not None
    assert (stats.crafting_skill, stats.crafting_level) == ("gearcrafting", 40)
    state = _character(gd, skills={"gearcrafting": 23}, inventory=dict(recipe))
    model = ObtainModel(state, gd, CTX, NOW)
    assert model.feasible("mithril_shield", 1, PIECE_POLICY)
    assert not model.feasible("mithril_shield", 1,
                              replace(PIECE_POLICY, craft_skill_gate=True))


def test_grey_droppers_count(gd: GameData) -> None:
    """A level-40 fighter earns no XP from a chicken (grey), yet its feathers
    are still achievable: the objective asks what can be had, not what pays."""
    state = _character(gd, level=40, equipment={"weapon_slot": "iron_sword"})
    assert gd.xp_per_kill("chicken", 40) == 0
    model = ObtainModel(state, gd, CTX, NOW)
    assert model.feasible("feather", 1, PIECE_POLICY)
    assert not model.feasible("feather", 1, replace(PIECE_POLICY, allow_grey=False))


def test_a_fighter_per_monster_judges_each_dropper_on_its_own(gd: GameData) -> None:
    """A callable fighter is asked per dropping monster, so each monster is
    judged against its own loadout: armed for the chicken, `feather` opens;
    unarmed for it, it does not. Stock still comes from the real state."""
    state = _character(gd)
    armed = _character(gd, equipment={"weapon_slot": "iron_sword"}, inventory={"iron_sword": 1})
    asked: list[str] = []

    def per_monster(monster: str) -> WorldState:
        asked.append(monster)
        return armed if monster == "chicken" else state

    model = ObtainModel(state, gd, CTX, NOW, fighter=per_monster)
    assert model.feasible("feather", 1, PIECE_POLICY)
    assert "chicken" in asked
    assert model.in_bag("iron_sword") == 0
    assert not ObtainModel(state, gd, CTX, NOW, fighter=lambda _monster: state).feasible(
        "feather", 1, PIECE_POLICY)
