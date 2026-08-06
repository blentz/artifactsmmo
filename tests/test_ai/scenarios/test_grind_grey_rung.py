"""The zero-xp skill-grind livelock, against the REAL catalog and the REAL
planner.

Live Robby 2026-08-05 (L22, woodcutting 15) ran 660 cycles over 14 hours and
ended at character level 22 with gold DOWN from 8431 to 5513 and a single
woodcutting level gained. Nothing errored: 660/660 cycles returned `ok`. The
damage is only visible in a derivative — `state.skill_xp["woodcutting"]` was
pinned at 4229 across cycles 0..103, ~2h of successful actions that bought
nothing.

TWO DEFECTS COMPOSE HERE, which is why one scenario carries both.

DEFECT A — the grind picked content that pays no xp. The server zeroes gather
and craft xp once the content sits `GREY_SKILL_GAP` levels below the SKILL
(`ai/skill_xp_positive`, corroborated over 2464 live gathers by
`formal/diff/gather_xp_replay.py`). Only COMBAT modelled its band; gather and
craft carried an UPPER skill bound and no lower one. At woodcutting 15 the
in-level rungs were `ash_plank` (craft level 1) and `spruce_plank` (10), and
because `mats_missing` is the ranking's first non-`wanted` key, the rung with
its materials already stockpiled won — the grey one, since cheap materials
correlate with obsolete tiers. Ordering could never have fixed it: a rung that
pays zero is worthless at any `mats_missing`, so `xp_positive` had to become a
FILTER.

DEFECT B — the grind ate the objective's materials. The committed objective was
`hardwood_plank` = 4 `ash_wood` + 6 `birch_wood`; `birch_tree` needs woodcutting
20 and the character had 15. So the arbiter gathered the reachable ash, failed on
birch, fell back to `LevelSkill(woodcutting->20)` — whose rung `ash_plank`
CONSUMES 10 `ash_wood` — and the ash demand re-armed. `skill_grind_target` had
carried a `reserved` guard for exactly this since 2026-06-11, but no production
caller ever passed one; `ctx.step_profile` (the committed step's material demand,
already the authority every keep/deposit/sell/recycle protection consults) is now
wired in.

These tests assert the PLANNER's behaviour and the SKILL-XP consequence, not that
a helper returns True: the bug was a decision that looked successful at every
individual step.
"""

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gather_skill_resource import best_gather_resource_drop
from artifactsmmo_cli.ai.level_skill_expand import next_grind_goal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.skill_grind_target import skill_grind_target
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

SCENARIO = "l22_grey_rung_grind"
SKILL = "woodcutting"
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


def test_the_premise_straight_from_the_catalog(game_data: GameData,
                                               state: WorldState) -> None:
    """The trap is a catalog fact, not a fixture artifact: at woodcutting 15
    `ash_plank` is in level, has every material in hand, and pays NOTHING —
    while the rung that does pay needs materials the character lacks."""
    assert state.skills[SKILL] == 15
    ash = game_data.item_stats("ash_plank")
    spruce = game_data.item_stats("spruce_plank")
    assert (ash.crafting_skill, ash.crafting_level) == (SKILL, 1)
    assert (spruce.crafting_skill, spruce.crafting_level) == (SKILL, 10)
    # in level, materials stockpiled -- it wins every ranking key it enters
    assert state.inventory.get("ash_wood", 0) >= game_data.crafting_recipe("ash_plank")["ash_wood"]
    # ...and pays zero, 14 levels down
    assert skill_xp_positive(ash.crafting_level, state.skills[SKILL]) is False
    assert skill_xp_positive(spruce.crafting_level, state.skills[SKILL]) is True
    # birch_wood really is out of reach, which is what strands the objective
    assert game_data.resource_skill_level("birch_tree") == (SKILL, 20)


def test_grind_rung_pays_xp(game_data: GameData, state: WorldState) -> None:
    """DEFECT A, at the selector. The rung must be the one that pays, even
    though the grey one has zero missing materials."""
    rung = skill_grind_target(SKILL, state, game_data)
    assert rung != "ash_plank", "the zero-xp rung was selected — defect A is back"
    assert rung == "spruce_plank"
    stats = game_data.item_stats(rung)
    assert skill_xp_positive(stats.crafting_level, state.skills[SKILL]) is True


def test_grind_does_not_eat_the_objective_materials(game_data: GameData,
                                                    state: WorldState) -> None:
    """DEFECT B, at the seam. With the objective's `ash_wood` reserved, the
    chosen rung's recipe must not consume it — otherwise the grind and the
    objective fight over the same pile forever."""
    reserved = frozenset({"ash_wood", "birch_wood"})
    rung = skill_grind_target(SKILL, state, game_data, reserved)
    assert rung is not None, "reservation must not empty the candidate set here"
    assert "ash_wood" not in game_data.crafting_recipe(rung)


# DEFECT B is checked on GEARCRAFTING, not woodcutting. At woodcutting 15 the
# grey filter already leaves exactly ONE paying rung, so reservation cannot
# change the answer there and a test written against it would pass whether or not
# the guard is wired — vacuous. Gearcrafting 15 in this same state has several
# paying rungs with disjoint materials, so the reservation is the only thing that
# can move the choice. It is also the ORIGINAL 2026-06-11 case named in
# `skill_grind_target`'s docstring: the grind reaching for copper_legs_armor's
# copper_bar while the objective is accumulating it.
_RESERVE_SKILL = "gearcrafting"


def test_reservation_reaches_the_grind_through_the_context(
        game_data: GameData, state: WorldState) -> None:
    """THE WIRING. `next_grind_goal` must READ `ctx.step_profile`. Before the fix
    the `reserved` parameter existed and no production caller ever passed one, so
    this is the test that would have caught a dead guard.

    Unreserved, the grind reaches for `copper_legs_armor` and descends to
    `copper_ore`. With the objective's copper reserved it must pick a rung that
    leaves it alone — `iron_shield`, descending to `iron_ore`."""
    plain = next_grind_goal(_RESERVE_SKILL, state, game_data, NO_PROFILE_CONTEXT)
    assert repr(plain) == "GatherMaterials(copper_ore, {copper_ore:10})"

    ctx = dataclasses.replace(NO_PROFILE_CONTEXT,
                              step_profile={"copper_bar": 5, "feather": 2})
    reserved = next_grind_goal(_RESERVE_SKILL, state, game_data, ctx)
    assert reserved is not None, "grind must still produce a goal under reservation"
    assert repr(reserved) == "GatherMaterials(iron_ore, {iron_ore:10})", (
        "the grind ignored ctx.step_profile — the reserved guard is dead again")


def test_reservation_never_creates_a_dead_end(game_data: GameData,
                                              state: WorldState) -> None:
    """LIVENESS. `LevelSkill.is_applicable` gates on the UNRESERVED target and has
    no ctx to pass; if reservation could empty the candidate set, the applicable
    action would raise "no grind rung at execution" — the selection-says-yes /
    emission-says-no split behind the wool livelock. Reserving EVERY material the
    skill's rungs consume must therefore STILL yield a goal."""
    every_material = {code: 1 for code in (
        "copper_bar", "feather", "iron_bar", "wool", "cowhide",
        "yellow_slimeball", "blue_slimeball", "green_slimeball", "red_slimeball")}
    ctx = dataclasses.replace(NO_PROFILE_CONTEXT, step_profile=every_material)
    assert next_grind_goal(_RESERVE_SKILL, state, game_data, ctx) is not None
    # ...and the woodcutting grind at the heart of this scenario likewise.
    assert next_grind_goal(SKILL, state, game_data, ctx) is not None


def test_gather_fallback_refuses_a_grey_resource(game_data: GameData,
                                                 state: WorldState) -> None:
    """The other half of defect A. Robby also burned 24 cycles on
    `Gather(sunflower_field)` at alchemy 17 — the highest alchemy resource in
    range is level 1, so every gather paid nothing. Because the helper picks the
    HIGHEST resource in range, a grey best means every candidate is grey and the
    honest answer is None."""
    assert best_gather_resource_drop("alchemy", state.skills["alchemy"], game_data) is None
    # ...while a skill whose best in-range resource is in band still gathers.
    assert best_gather_resource_drop(SKILL, state.skills[SKILL], game_data) is not None


def test_full_grind_cycle_plans_and_pays(player: GamePlayer, game_data: GameData,
                                         state: WorldState) -> None:
    """END TO END through the production seam. The goal `_execute_level_skill`
    builds must PLAN (a leg exists) and every gather it plans must be against
    xp-paying content — the property whose absence pinned Robby's woodcutting xp
    at 4229 for 104 consecutive successful cycles."""
    goal = next_grind_goal(SKILL, state, game_data, player._last_ctx)
    assert goal is not None
    plan = player.planner.plan(state, goal, player._build_actions(), game_data,
                               budget_seconds=BUDGET)
    assert plan, "LevelSkill(woodcutting) grind produced no leg"
    for action in plan:
        if isinstance(action, GatherAction):
            req = game_data.resource_skill_level(action.resource_code)
            assert req is not None
            assert skill_xp_positive(req[1], state.skills[req[0]]) is True, (
                f"grind plans a zero-xp gather: {action!r}")
