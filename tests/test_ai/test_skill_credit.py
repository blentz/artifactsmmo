"""Actions of a skill the DAG demands are not a cost of what they make
(docs/superpowers/specs/2026-10-13-fleet-food-role-design.md §2; USER
2026-10-13 "useful XP only")."""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost_core import BANK_VENUE, RouteOption
from artifactsmmo_cli.ai.consumable_price import make_seconds
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.skill_credit import credit_demanded_skills, route_skill
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json")


def _gd(monkeypatch: pytest.MonkeyPatch) -> GameData:
    gd = GameData()
    gd._item_stats = {"cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                               crafting_skill="cooking", crafting_level=1)}
    monkeypatch.setattr(gd, "resource_skill_level",
                        lambda code: ("fishing", 1) if code == "fish_spot" else None)
    return gd


GATHER = RouteOption(kind="gather", venue="fish_spot", actions_per_application=1, yield_per=1,
                     capacity=UNBOUNDED_CAPACITY)
WITHDRAW = RouteOption(kind="withdraw", venue="bank", actions_per_application=1, yield_per=1,
                       capacity=5)
CRAFT = RouteOption(kind="craft", venue="cooking", actions_per_application=1, yield_per=1,
                    capacity=UNBOUNDED_CAPACITY, inputs={"fish": 1})


def test_a_gather_trains_its_resource_skill_and_a_craft_its_item_skill(monkeypatch):
    gd = _gd(monkeypatch)
    assert route_skill("fish", GATHER, gd) == "fishing"
    assert route_skill("cooked_fish", CRAFT, gd) == "cooking"
    assert route_skill("fish", WITHDRAW, gd) is None
    with pytest.raises(ValueError, match="no gathering skill"):
        route_skill("fish", dataclasses.replace(GATHER, venue="rock"), gd)


def test_a_siblings_craft_trains_none_of_this_characters_skills(monkeypatch):
    """`_sibling_craft_option` is a CRAFT at the bank venue: a SIBLING crafts
    it, so this character's demanded cooking is not trained and the route keeps
    its price."""
    gd = _gd(monkeypatch)
    sibling = dataclasses.replace(CRAFT, venue=BANK_VENUE)
    assert route_skill("cooked_fish", sibling, gd) is None
    credited = credit_demanded_skills({"cooked_fish": [sibling]}, frozenset({"cooking"}), gd)
    assert credited["cooked_fish"][0].actions_per_application == 1


def test_only_the_demanded_skills_routes_are_free(monkeypatch):
    gd = _gd(monkeypatch)
    options = {"fish": [GATHER, WITHDRAW], "cooked_fish": [CRAFT]}
    credited = credit_demanded_skills(options, frozenset({"fishing"}), gd)
    assert [r.actions_per_application for r in credited["fish"]] == [0, 1]
    assert [r.actions_per_application for r in credited["cooked_fish"]] == [1]
    assert credit_demanded_skills(options, frozenset(), gd) == options


def test_the_make_price_drops_the_demanded_skills_actions():
    """cooked_gudgeon on the bundle: hop + gather + hop + cook = 4 actions.
    Fishing demanded frees the gather; fishing and cooking free both; the two
    hops always cost."""
    gd = load_bundle_game_data(_BUNDLE)
    state = scenario_state(ScenarioCharacter(name="hero", level=10,
                                             skills={"fishing": 10, "cooking": 10}), gd)

    def price(skills: frozenset[str]):  # type: ignore[no-untyped-def]
        return make_seconds("cooked_gudgeon", state, gd,
                            dataclasses.replace(TIMED_NO_PROFILE_CONTEXT, skill_demand=skills), None)

    action = TIMED_NO_PROFILE_CONTEXT.action_seconds_of()
    assert price(frozenset()) == 4 * action
    assert price(frozenset({"fishing"})) == 3 * action
    assert price(frozenset({"fishing", "cooking"})) == 2 * action
