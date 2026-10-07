"""Which XP the goal-action DAG demands (c-2 #5 increment 4; USER 2026-10-07:
the char/skill XP seesaw is emergent, never a phase rule)."""

import dataclasses

import artifactsmmo_cli.ai.xp_demand as mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.xp_demand import demand_roots, xp_demand
from tests.test_ai.fixtures import make_state


def test_the_roots_are_the_chosen_root_then_the_unworn_targets() -> None:
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, target_gear=frozenset({"iron_sword", "copper_ring"}),
                              near_term_targets=frozenset({"wool_cape"}))
    state = make_state(equipment={"ring1_slot": "copper_ring"})
    roots = demand_roots(ReachCharLevel(35), state, ctx)
    assert roots == [ReachCharLevel(35), ObtainItem("iron_sword", 1), ObtainItem("wool_cape", 1)]
    assert demand_roots(None, state, NO_PROFILE_CONTEXT) == []


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
