"""A skill climb first fetches its best tool (spec 2026-10-18 §2.6, plan B
Task 8): `tool_target` is data-driven on `skill_effects`, the owned best tool is
never re-acquired, and the walk roots `ObtainItem(tool)` in front of the climb.
"""

from dataclasses import replace
from datetime import UTC, datetime
from fractions import Fraction

from artifactsmmo_cli.ai.decisions.root import RootWalk
from artifactsmmo_cli.ai.decisions.which_piece_is_next import fleet_piece_root
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel, no_decline
from artifactsmmo_cli.ai.tool_objective import tool_first, tool_target
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_decisions_root import _gd
from tests.test_ai.test_decisions_which_piece import SHIELD, _missing, _resolve
from tests.test_ai.test_strategy_driver import _ctx

HAMMER = "gear_hammer"
NOW = datetime(2026, 10, 25, tzinfo=UTC)


def _world(*, effect: int = -10, level: int = 1, skill: str = "gearcrafting") -> GameData:
    """`_gd()` plus a craftable tool whose only mark is its `skill_effects`."""
    gd = _gd()
    gd._item_stats = {**gd._item_stats, HAMMER: ItemStats(
        code=HAMMER, level=level, type_="weapon", skill_effects={skill: effect},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, HAMMER: {"ash_plank": 4}}
    return gd


def test_a_craft_skill_tool_qualifies_by_its_effect() -> None:
    gd = _world()
    state = make_state(level=15)
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) == HAMMER
    assert tool_target("mining", state, gd, _ctx(), NOW) is None


def test_a_climb_first_fetches_its_tool() -> None:
    gd = _world()
    resolution = _resolve(make_state(level=15), gd, _missing(SHIELD))
    assert resolution.root == ObtainItem(HAMMER, 1)
    assert resolution.blocked_target == "iron_shield"


def test_an_owned_tool_is_never_reacquired() -> None:
    gd = _world()
    climb = ReachSkillLevel(skill="gearcrafting", level=2)
    for owned in (make_state(level=15, bank_items={HAMMER: 1}),
                  make_state(level=15, inventory={HAMMER: 1}),
                  make_state(level=15, equipment={"weapon_slot": HAMMER})):
        assert tool_target("gearcrafting", owned, gd, _ctx(), NOW) is None
        assert _resolve(owned, gd, _missing(SHIELD)).root == climb


def test_a_tool_above_the_level_or_without_effect_is_no_target() -> None:
    state = make_state(level=15)
    assert tool_target("gearcrafting", state, _world(level=16), _ctx(), NOW) is None
    assert tool_target("gearcrafting", state, _world(effect=0), _ctx(), NOW) is None


def test_an_unachievable_tool_is_no_target() -> None:
    gd = _world()
    gd._crafting_recipes = {**gd._crafting_recipes, HAMMER: {"leather": 4}}
    assert tool_target("gearcrafting", make_state(level=15), gd, _ctx(), NOW) is None


def test_the_best_achievable_tool_wins_over_a_better_unreachable_one() -> None:
    gd = _world()
    gd._item_stats = {**gd._item_stats, "mythic_hammer": ItemStats(
        code="mythic_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -50},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "mythic_hammer": {"leather": 4}}
    assert tool_target("gearcrafting", make_state(level=15), gd, _ctx(), NOW) == HAMMER


def test_a_better_owned_tool_leaves_nothing_to_fetch_and_a_tie_prefers_it() -> None:
    gd = _world()
    gd._item_stats = {**gd._item_stats, "twin_hammer": ItemStats(
        code="twin_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -10})}
    state = make_state(level=15, inventory={"twin_hammer": 1})
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) is None


def test_the_better_unowned_tool_is_fetched_over_a_worse_owned_one() -> None:
    gd = _world(effect=-20)
    gd._item_stats = {**gd._item_stats, "old_hammer": ItemStats(
        code="old_hammer", level=1, type_="weapon", skill_effects={"gearcrafting": -10})}
    state = make_state(level=15, inventory={"old_hammer": 1})
    assert tool_target("gearcrafting", state, gd, _ctx(), NOW) == HAMMER


def test_the_climb_is_substituted_by_its_tool() -> None:
    gd = _world()
    state = make_state(level=15)
    assert tool_first(ReachSkillLevel(skill="gearcrafting", level=2), state, gd, _ctx(), NOW, no_decline) \
        == ObtainItem(HAMMER, 1)


def test_a_crafters_climb_in_front_of_a_fleet_piece_fetches_the_tool() -> None:
    gd = _world()
    piece = FleetPiece(code="iron_shield", skill="gearcrafting", level=10, gain=Fraction(1))
    state = make_state(level=15)
    assert fleet_piece_root(piece, state, gd, _ctx(), RootWalk()) == ObtainItem(HAMMER, 1)
    banked = replace(state, bank_items={HAMMER: 1})
    assert fleet_piece_root(piece, banked, gd, _ctx(), RootWalk()) == ReachSkillLevel(
        skill="gearcrafting", level=2)


def test_a_fishing_climb_fetches_the_fishing_net() -> None:
    gd = _gd()
    gd._item_stats = {**gd._item_stats, "fishing_net": ItemStats(
        code="fishing_net", level=1, type_="weapon", skill_effects={"fishing": -10},
        crafting_skill="weaponcrafting", crafting_level=1)}
    gd._crafting_recipes = {**gd._crafting_recipes, "fishing_net": {"ash_plank": 4}}
    climb = ReachSkillLevel(skill="fishing", level=2)
    assert tool_first(climb, make_state(level=15), gd, _ctx(), NOW, no_decline) == ObtainItem("fishing_net", 1)
    assert tool_first(climb, make_state(level=15, bank_items={"fishing_net": 1}), gd,
                      _ctx(), NOW, no_decline) == climb


def _refuse_tool(root):
    return "no plan this cycle" if root == ObtainItem(HAMMER, 1) else None


def test_a_declined_tool_step_falls_back_to_the_plain_climb() -> None:
    """The tool is model-feasible, but its step is declined this cycle (T8a):
    the root is the climb, and the piece is not declined for its tool."""
    gd = _world()
    state = make_state(level=15)
    resolution = _resolve(state, gd, _missing(SHIELD), decline={ObtainItem(HAMMER, 1): "no plan"})
    assert resolution.root == ReachSkillLevel(skill="gearcrafting", level=2)
    assert resolution.declined == ()
    assert tool_first(ReachSkillLevel(skill="gearcrafting", level=2), state, gd, _ctx(), NOW,
                      _refuse_tool) == ReachSkillLevel(skill="gearcrafting", level=2)


def test_a_declined_tool_step_leaves_a_fleet_climb_plain() -> None:
    gd = _world()
    piece = FleetPiece(code="iron_shield", skill="gearcrafting", level=10, gain=Fraction(1))
    walk = RootWalk(step_decline=_refuse_tool, now=NOW)
    assert fleet_piece_root(piece, make_state(level=15), gd, _ctx(), walk) == ReachSkillLevel(
        skill="gearcrafting", level=2)
