"""Which XP the goal-action DAG demands (c-2 #5 increment 4; USER 2026-10-07:
the char/skill XP seesaw is emergent, never a phase rule)."""

import dataclasses
from fractions import Fraction

import artifactsmmo_cli.ai.xp_demand as mod
from artifactsmmo_cli.ai.fleet_piece import FleetPiece
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.progression.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.xp_demand import demand_roots, xp_demand
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state, with_missing


def test_the_roots_are_the_chosen_root_then_the_missing_pieces() -> None:
    ctx = with_missing(NO_PROFILE_CONTEXT, ("weapon_slot", "iron_sword"), ("body_armor_slot", "wool_cape"))
    roots = demand_roots(ReachCharLevel(35), make_state(), ctx)
    assert roots == [ReachCharLevel(35), ObtainItem("iron_sword", 1), ObtainItem("wool_cape", 1)]
    assert demand_roots(None, make_state(), NO_PROFILE_CONTEXT) == []
    assert demand_roots(None, make_state(), with_missing(NO_PROFILE_CONTEXT)) == []
    tools = dataclasses.replace(ctx, objective_tools={"mining": "copper_pickaxe"})
    assert demand_roots(None, make_state(), tools) == [
        ObtainItem("copper_pickaxe", 1), ObtainItem("iron_sword", 1), ObtainItem("wool_cape", 1)]
    bare = dataclasses.replace(NO_PROFILE_CONTEXT, objective_tools={"mining": "copper_pickaxe"})
    assert demand_roots(None, make_state(), bare) == [ObtainItem("copper_pickaxe", 1)]
    # A held `L*` piece is in the loadout but is no root: only the missing are.
    objective = with_missing(NO_PROFILE_CONTEXT, ("weapon_slot", "iron_sword")).gear_objective
    assert objective is not None
    part_held = dataclasses.replace(NO_PROFILE_CONTEXT, gear_objective=dataclasses.replace(
        objective, loadout={**objective.loadout, "ring1_slot": "copper_ring"}))
    assert demand_roots(None, make_state(), part_held) == [ObtainItem("iron_sword", 1)]


def test_skill_demand_follows_the_missing_pieces(bundle_game_data: GameData) -> None:
    """Robby (gearcrafting 23, jewelrycrafting 22) missing three level-30 `L*`
    pieces: the skill demand is exactly the skills those pieces' closures need
    above his levels, the two crafting skills and the mining for their bars.
    Once `L*` is held, gear demands no skill at all."""
    robby = make_state(level=41, skills={"gearcrafting": 23, "jewelrycrafting": 22,
                                         "weaponcrafting": 22, "mining": 25,
                                         "woodcutting": 27, "fishing": 29})
    ctx = with_missing(TIMED_NO_PROFILE_CONTEXT, ("leg_armor_slot", "royal_skeleton_pants"),
                       ("ring1_slot", "royal_skeleton_ring"), ("amulet_slot", "lost_amulet"))
    skills, _level = xp_demand(demand_roots(None, robby, ctx), robby, bundle_game_data, ctx)
    assert skills == {"gearcrafting", "jewelrycrafting", "mining"}
    assert xp_demand(demand_roots(None, robby, with_missing(TIMED_NO_PROFILE_CONTEXT)),
                     robby, bundle_game_data, ctx) == (frozenset(), False)


def test_the_fleet_food_shortfall_is_not_dag_demand() -> None:
    """Spec §2: the shortfall made fishing 'useful', which made the food cheap,
    which made the shortfall. Fishing is useful only when a gear or skill root
    needs it."""
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, supply_shortfall=(("cooked_bass", 12),))
    assert demand_roots(None, make_state(), ctx) == []


def test_the_walks_and_the_skill_root_name_the_skills(monkeypatch) -> None:
    monkeypatch.setattr(mod, "craft_demand", lambda roots, s, g, c: {"gearcrafting": 20})
    monkeypatch.setattr(mod, "gather_demand", lambda roots, s, g, c: {"mining": 25})
    state = make_state(level=30, skills={"cooking": 10})
    skills, level = xp_demand([ReachSkillLevel("cooking", 11), ReachSkillLevel("alchemy", 1)],
                              state, GameData(), NO_PROFILE_CONTEXT)
    assert skills == {"gearcrafting", "mining", "cooking"} and level is False


def test_character_level_is_demanded_by_a_level_root_or_a_gear_level(monkeypatch) -> None:
    monkeypatch.setattr(mod, "craft_demand", lambda *a: {})
    monkeypatch.setattr(mod, "gather_demand", lambda *a: {})
    gd = GameData()
    gd._item_stats = {"lich_crown": ItemStats(code="lich_crown", level=40, type_="helmet"),
                      "iron_sword": ItemStats(code="iron_sword", level=10, type_="weapon")}
    state = make_state(level=30)
    assert xp_demand([ReachCharLevel(35)], state, gd, NO_PROFILE_CONTEXT)[1]
    assert not xp_demand([ReachCharLevel(30)], state, gd, NO_PROFILE_CONTEXT)[1]
    assert xp_demand([ObtainItem("lich_crown", 1)], state, gd, NO_PROFILE_CONTEXT)[1]
    assert not xp_demand([ObtainItem("iron_sword", 1), ObtainItem("unknown", 1)],
                         state, gd, NO_PROFILE_CONTEXT)[1]


def test_a_fleet_piece_demands_its_craft_level(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    """Spec 2026-10-18 §2.5 (ruling C2-m3): a crafter's fleet pieces count as
    missing pieces of its joint objective, so each is a root at the craft
    level that gates it, after the objective codes, offered only while the
    cycle has a gear objective (as `resolve_root` offers their roots)."""
    piece = FleetPiece(code="iron_shield", skill="gearcrafting", level=10, gain=Fraction(1))
    ctx = dataclasses.replace(with_missing(NO_PROFILE_CONTEXT, ("weapon_slot", "iron_sword")),
                              fleet_pieces=(piece,))
    assert demand_roots(None, make_state(), ctx) == [
        ObtainItem("iron_sword", 1), ReachSkillLevel(skill="gearcrafting", level=10)]
    assert demand_roots(None, make_state(), dataclasses.replace(
        NO_PROFILE_CONTEXT, fleet_pieces=(piece,))) == []
    monkeypatch.setattr(mod, "craft_demand", lambda *a: {})
    monkeypatch.setattr(mod, "gather_demand", lambda *a: {})
    skills, _level = xp_demand([ReachSkillLevel(skill="gearcrafting", level=10)],
                               make_state(skills={"gearcrafting": 3}), GameData(), NO_PROFILE_CONTEXT)
    assert skills == {"gearcrafting"}
