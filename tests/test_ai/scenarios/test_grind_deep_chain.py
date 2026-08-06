"""The deep-chain mispricing, against the REAL catalog.

Live R2D2 2026-08-06 (L12, weaponcrafting 5): 129 `LevelSkill(weaponcrafting->10)`
cycles across two runs moved weaponcrafting XP exactly ZERO times. Every cycle
returned `ok`. The skill sat at level 5 with 664 XP the whole time.

MECHANISM. The grind picked `sticky_sword` — a perfectly valid rung: same skill,
in level, obtainable, and xp-positive (craft level 5 at skill 5, so the craft
really would pay). The rung was never the problem. The RANKING was: the selector
ordered candidates by `mats_missing`, the count of recipe entries not currently
held, and

    sticky_sword      recipe {copper_bar: 5, yellow_slimeball: 2}   -> 5 missing
    apprentice_gloves recipe {feather: 6}                           -> 6 missing

so the sword won by one. But each `copper_bar` is 10 `copper_ore`, so the sword
is ~51 actions and the gloves are 7. Worse, at mining 12 the `copper_rocks`
gather that mints that ore is itself grey (gap 11), so each of those ~50 cycles
paid nothing in EITHER skill, and the chain never reached the craft that would
have paid weaponcrafting.

THE ARCHITECTURAL POINT. This was the THIRD recurrence of one flaw — a cost proxy
that cannot see past the first level of a recipe. The first two (`apprentice_gloves`
over `copper_dagger` 2026-06-24; grey `ash_plank` over `spruce_plank` 2026-08-05)
were each patched by adding ANOTHER key to the ordering — `wanted`, then the
`xp_positive` filter. Both were correct on their own terms and neither touched the
proxy that was lying. `acquire_steps` replaces it with the whole-closure action
count (`min_gathers + min_crafts`), reusing the SAME proved bound the planner's
reachability gate uses, so the codebase has one notion of "how much work is this"
instead of two that disagree.

These tests assert the SELECTED RUNG and its real cost against the live catalog —
not that a helper returns a number — because the bug was a decision that looked
correct at every individual step.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.min_crafts import min_crafts
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.skill_xp_positive import skill_xp_positive
from artifactsmmo_cli.ai.tiers.skill_grind_target import (
    build_grind_candidates,
    skill_grind_target,
)
from artifactsmmo_cli.ai.world_state import WorldState

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"

SCENARIO = "l12_deep_chain_grind"
SKILL = "weaponcrafting"


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture
def state(game_data: GameData) -> WorldState:
    return scenario_state(SCENARIOS[SCENARIO], game_data)


def _steps(code: str, state: WorldState, game_data: GameData) -> int:
    bank = state.bank_items or {}
    owned = {c: state.inventory.get(c, 0) + bank.get(c, 0)
             for c in set(state.inventory) | set(bank)}
    recipes = game_data.crafting_recipes
    return (min_gathers(code, 1, recipes, owned)
            + min_crafts(code, 1, recipes, owned))


def test_scenario_registered() -> None:
    assert SCENARIO in SCENARIOS


def test_the_premise_straight_from_the_catalog(game_data: GameData,
                                               state: WorldState) -> None:
    """The trap is a catalog fact. Both rungs are same-skill, in-level and
    xp-positive — the ONLY thing separating them is cost, and the old proxy got
    that backwards."""
    assert state.skills[SKILL] == 5
    for code in ("sticky_sword", "apprentice_gloves"):
        stats = game_data.item_stats(code)
        assert stats.crafting_skill == SKILL
        assert stats.crafting_level <= state.skills[SKILL]
        assert skill_xp_positive(stats.crafting_level, state.skills[SKILL]) is True

    bank = state.bank_items or {}
    owned = {c: state.inventory.get(c, 0) + bank.get(c, 0)
             for c in set(state.inventory) | set(bank)}
    # The OLD key: recipe entries not held. It ranks the sword CHEAPER.
    def mats_missing(code: str) -> int:
        return sum(max(0, qty - owned.get(mat, 0))
                   for mat, qty in game_data.crafting_recipe(code).items())
    assert mats_missing("sticky_sword") < mats_missing("apprentice_gloves")
    # The REAL cost inverts it, by a wide margin.
    assert _steps("sticky_sword", state, game_data) > \
        3 * _steps("apprentice_gloves", state, game_data)


def test_grind_picks_the_cheap_chain(game_data: GameData, state: WorldState) -> None:
    """THE REGRESSION. The rung must be the one that is actually cheap to build,
    not the one that merely lists fewer recipe lines."""
    rung = skill_grind_target(SKILL, state, game_data)
    assert rung != "sticky_sword", (
        "the deep chain was selected — the one-level cost proxy is back")
    assert rung == "apprentice_gloves"


def test_selected_rung_is_the_cheapest_feasible_one(game_data: GameData,
                                                    state: WorldState) -> None:
    """Stronger and proxy-independent: whatever is selected must minimise
    `acquire_steps` over every feasible candidate. This is the property the
    ordering theorems state, checked against the real catalog rather than
    hand-built candidates."""
    lvl = state.skills[SKILL]
    feasible = [c for c in build_grind_candidates(SKILL, state, game_data)
                if c.craft_skill == SKILL and c.craft_level <= lvl
                and c.obtainable and c.xp_positive]
    assert feasible, "scenario must offer at least one feasible rung"
    rung = skill_grind_target(SKILL, state, game_data)
    chosen = next(c for c in feasible if c.code == rung)
    assert chosen.acquire_steps == min(c.acquire_steps for c in feasible)


def test_hoisted_cost_counts_the_whole_chain(game_data: GameData,
                                             state: WorldState) -> None:
    """The hoist must cost the CLOSURE, not the first level. `copper_bar` is not
    held, so sticky_sword's cost has to include the ore behind the bars — the
    exact term the old proxy omitted."""
    cands = {c.code: c for c in build_grind_candidates(SKILL, state, game_data)}
    sword = cands["sticky_sword"]
    # 5 bars x 10 ore each, less the single ore held, plus the crafts.
    assert sword.acquire_steps >= 45, sword.acquire_steps
    assert sword.acquire_steps == _steps("sticky_sword", state, game_data)
    # And holdings genuinely discount it: the banked slimeballs are not re-bought.
    assert cands["apprentice_gloves"].acquire_steps < 15
