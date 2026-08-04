"""The skill-grind grey-material livelock, against the REAL catalog and the
REAL planner.

Live Robby 2026-08-03 (L21, jewelrycrafting 14) burned 8 of 16 consecutive
cycles on

    LevelSkill(jewelrycrafting->15) -> error:other
      "grind produced no leg — goal=GatherMaterials(wool, {wool:2})
       nodes=4 depth=2"

with no progress and no escape; the same action accounts for every one of the
54 "produced no leg" records across 39 older traces.

MECHANISM (confirmed offline before any fix): `wool` is `type=resource,
subtype=mob` — not gatherable. Its only source is the level-5 `sheep`, GREY at
character level 21, so `GatherMaterialsGoal.relevant_actions` asked
`grey_farm_allowed("wool", ...)`, which said False (every recipe consuming wool
has a same-family next tier within `GREY_FARM_NEXT_TIER_MARGIN`), and
`select_drop_fight` therefore emitted NO fight. The goal had no acquisition edge
at all — hence `nodes=4 depth=2`, a search that gave up immediately.

Meanwhile `skill_grind_target.is_obtainable` calls that same rung obtainable (it
asks only winnable + spawn-known, never the grey policy), so `LevelSkill`
stayed applicable and the arbiter re-picked it forever. The fix — the
skill-grind exemption in `GatherMaterialsGoal.relevant_actions` — makes the two
models agree again.

These tests assert a PLAN EXISTS, not that a helper returns True: the bug was
the absence of a plan, so only the planner can prove it gone.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.grey_farm import grey_farm_allowed
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

SCENARIO = "l21_grey_material_grind"
SKILL = "jewelrycrafting"
BUDGET = 10.0


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture
def state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[SCENARIO], game_data)


@pytest.fixture
def player(game_data: GameData, state: WorldState) -> GamePlayer:
    p = GamePlayer(character=SCENARIO, history=None)
    p.seed_offline(state, game_data)
    return p


def test_scenario_registered() -> None:
    assert SCENARIO in SCENARIOS


def test_wool_really_is_a_grey_mob_drop_only(game_data: GameData,
                                             state: WorldState) -> None:
    """The premise, straight from the catalog: no gather source, one dropper,
    and that dropper yields zero xp at this level."""
    stats = game_data.item_stats("wool")
    assert stats is not None and stats.subtype == "mob"
    assert "wool" not in game_data.resource_drops.values()
    droppers = [code for code, _rate, _mn, _mx in game_data.monsters_dropping("wool")]
    assert droppers == ["sheep"]
    assert game_data.xp_per_kill("sheep", state.level) == 0


def test_grind_descends_to_the_live_wool_goal(game_data: GameData,
                                              state: WorldState) -> None:
    """The scenario reproduces the live decision exactly: rung iron_ring, and
    the descent lands on its mob-drop material."""
    assert skill_grind_target(SKILL, state, game_data) == "iron_ring"
    goal = next_grind_goal(SKILL, state, game_data)
    assert repr(goal) == "GatherMaterials(wool, {wool:2})"


def test_real_planner_finds_a_plan_for_wool(player: GamePlayer,
                                            game_data: GameData,
                                            state: WorldState) -> None:
    """THE REGRESSION: a plan must EXIST for the grind's wool demand. Before
    the fix this was `[]` at nodes=4 — no acquisition edge in the action set."""
    goal = GatherMaterialsGoal(target_item="wool", needed={"wool": 2},
                               skill_grind=True,
                               exclude_recycle=frozenset({"iron_ring"}))
    plan = player.planner.plan(state, goal, player._build_actions(),
                               game_data, budget_seconds=BUDGET)
    assert plan, "no plan for the grind's wool demand — the livelock is back"
    assert [repr(a) for a in plan] == ["Fight(sheep)", "Fight(sheep)"]
    assert all(a.drop_farm for a in plan if isinstance(a, FightAction))


def test_full_grind_cycle_produces_a_leg(player: GamePlayer,
                                         game_data: GameData,
                                         state: WorldState) -> None:
    """End to end through the production seam: the goal `_execute_level_skill`
    builds must plan, and its first step is the leg the player executes."""
    goal = next_grind_goal(SKILL, state, game_data, player._last_ctx)
    assert goal is not None
    plan = player.planner.plan(state, goal, player._build_actions(),
                               game_data, budget_seconds=BUDGET)
    assert plan, "LevelSkill(jewelrycrafting) grind produced no leg"
    assert isinstance(plan[0], FightAction)


def test_ordinary_gather_still_obeys_the_suppression(player: GamePlayer,
                                                     game_data: GameData,
                                                     state: WorldState) -> None:
    """The 2026-07-06 directive is routed around, not deleted: the SAME item,
    the SAME state, without the skill-grind flag, still finds no grey fight —
    the policy verdict itself is untouched."""
    assert grey_farm_allowed("wool", state, game_data) is False
    goal = GatherMaterialsGoal(target_item="wool", needed={"wool": 2})
    relevant = goal.relevant_actions(player._build_actions(), state, game_data)
    assert not [a for a in relevant
                if isinstance(a, FightAction) and a.monster_code == "sheep"]
    assert not player.planner.plan(state, goal, player._build_actions(),
                                   game_data, budget_seconds=BUDGET)
