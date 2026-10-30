"""The cycle's XP demand and its tools by one fixed point (plan C Task 1,
ruling C1-a): the tools `T*` of the demanded skills are roots of their own, so
a tool's own craft skill joins the demand, and each skill's tool is looked up
once a cycle."""

from dataclasses import replace

import pytest

import artifactsmmo_cli.ai.objective_demand as mod
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.objective_codes import objective_codes
from artifactsmmo_cli.ai.objective_demand import objective_demand
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tool_objective import tool_target
from artifactsmmo_cli.ai.xp_demand import demand_roots, xp_demand
from tests.test_ai.fixtures import make_state, with_missing
from tests.test_ai.test_strategy_driver import _ctx
from tests.test_ai.test_tool_objective import HAMMER, NOW, _world


def _hammer_world() -> GameData:
    """`_world()`'s gearcrafting hammer, crafted at weaponcrafting 3: above a
    fresh character's weaponcrafting 1."""
    gd = _world()
    gd._item_stats = {**gd._item_stats,
                      HAMMER: replace(gd._item_stats[HAMMER], crafting_level=3)}
    return gd


def _shield_ctx() -> SelectionContext:
    """A gear objective missing the gearcrafting-10 `iron_shield`."""
    return with_missing(replace(_ctx(), now=NOW), ("shield_slot", "iron_shield"))


def test_a_tools_craft_skill_joins_the_demand() -> None:
    """`L*` alone demands gearcrafting; gearcrafting's tool is the hammer, a
    root of its own, whose craft demands weaponcrafting 3 the character lacks.
    The fixed point finds both, and the hammer is an objective code."""
    gd = _hammer_world()
    state = make_state(level=15)
    ctx = _shield_ctx()
    assert xp_demand(demand_roots(None, state, ctx), state, gd, ctx)[0] == {"gearcrafting"}
    out = objective_demand(None, state, gd, ctx)
    assert out.objective_tools == {HAMMER}
    assert out.skill_demand == {"gearcrafting", "weaponcrafting"}
    assert out.level_demanded is False
    assert objective_codes(out) == {"iron_shield", HAMMER}


def test_each_skills_tool_is_looked_up_once(monkeypatch: pytest.MonkeyPatch) -> None:
    gd = _hammer_world()
    asked: list[str] = []

    def counted(skill, state, game_data, ctx, now):  # type: ignore[no-untyped-def]
        asked.append(skill)
        return tool_target(skill, state, game_data, ctx, now)

    monkeypatch.setattr(mod, "tool_target", counted)
    objective_demand(None, make_state(level=15), gd, _shield_ctx())
    assert sorted(asked) == ["gearcrafting", "weaponcrafting"]


def test_an_owned_tool_is_no_objective_code() -> None:
    """The best tool already owned names no root, so its craft skill is not
    demanded."""
    gd = _hammer_world()
    out = objective_demand(None, make_state(level=15, inventory={HAMMER: 1}), gd, _shield_ctx())
    assert out.objective_tools == frozenset()
    assert out.skill_demand == {"gearcrafting"}


def test_a_held_objective_demands_no_tool() -> None:
    gd = _hammer_world()
    ctx = with_missing(replace(_ctx(), now=NOW))
    out = objective_demand(None, make_state(level=15), gd, ctx)
    assert (out.skill_demand, out.level_demanded, out.objective_tools) == (
        frozenset(), False, frozenset())
