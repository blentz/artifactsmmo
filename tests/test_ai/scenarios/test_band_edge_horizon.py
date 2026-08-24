"""The band-EDGE fixtures, and the horizon property they exist to pin.

`l19_band_edge` and `l11_band_floor` carry the same gear, skills and bank as
`l21_grey_material_grind` and differ from each other in LEVEL alone. That is the
whole design: it makes band POSITION the only variable, so a difference in what
the objective can see is attributable to the horizon and to nothing else.

WHAT IS BEING PINNED. `cheapest_path_to_level` is the objective's benefit term,
and how much it can discriminate between candidates depends on how far the walk
runs. One level from the milestone every candidate arrives at the same figure and
the objective is blind; nine levels out the same candidates separate. Measured
live 2026-08-18 on the fleet: R2D2 at L19 spread 0 cycles over 9 candidates,
Lor at L16 spread 1,086 over 12. No committed scenario sat at a band edge, so the
suite could not see either pole.

These are OFFLINE numbers and much smaller than the live ones (a cold `:memory:`
store falls back to the documented XP formula instead of measured rates). The
assertions below are therefore about ORDER and about the flat pole, never about a
magnitude — a threshold copied from a scenario would be meaningless live.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.branch_objective import branch_ranking, reached_spread
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import objective_candidates
from artifactsmmo_cli.ai.tiers.progression_tree_core import milestone_pure

_BUNDLE = Path(__file__).resolve().parent / "fixtures" / "gamedata_bundle.json"


@pytest.fixture(scope="module")
def game_data():  # type: ignore[no-untyped-def]
    return load_bundle_game_data(_BUNDLE)


def _spread(scenario: str, target: int, game_data) -> tuple[int | None, int, int]:  # type: ignore[no-untyped-def]
    """`(spread, reachers, candidates)` for one scenario at one target."""
    state = scenario_state(SCENARIOS[scenario], game_data)
    objective = CharacterObjective.from_game_data(game_data)
    store = LearningStore(db_path=":memory:", character=scenario)
    store.start_session()
    try:
        candidates = objective_candidates(state, game_data, objective)
        with store.search_cache():
            ranked = branch_ranking(state, game_data, candidates, store,
                                    NO_PROFILE_CONTEXT, target)
    finally:
        store.end_session(exit_reason="normal")
        store.close()
    reachers = [c for c in ranked if not c.failed and c.reachable_level >= target]
    return reached_spread(ranked, target), len(reachers), len(ranked)


def test_the_edge_fixtures_are_one_and_nine_levels_from_the_same_milestone(game_data):
    """The design invariant. If either level drifts, the pair stops isolating band
    position and every assertion below becomes a comparison of two unrelated
    characters."""
    edge = scenario_state(SCENARIOS["l19_band_edge"], game_data)
    floor = scenario_state(SCENARIOS["l11_band_floor"], game_data)
    assert milestone_pure(edge.level) == milestone_pure(floor.level) == 20
    assert 20 - edge.level == 1
    assert 20 - floor.level == 9
    assert edge.equipment == floor.equipment
    assert edge.skills == floor.skills


def test_the_edge_fixtures_can_actually_fight(game_data):
    """NON-VACUITY GUARD, and the reason `derive_combat_stats=True` is on both.

    Without it a scenario character carries zero attack, `is_winnable` is False
    against every monster, and the walk blocks at rung one — which would make the
    benefit column flat for a reason that has nothing to do with band position.
    Every spread assertion below would then pass while measuring nothing. A
    non-empty `attack` is what rules that out."""
    for name in ("l19_band_edge", "l11_band_floor"):
        state = scenario_state(SCENARIOS[name], game_data)
        assert state.attack, f"{name} has no attack — the walk will block at rung one"


def test_a_character_one_level_from_its_milestone_is_nearly_blind(game_data):
    """THE FLAT POLE. Every candidate reaches the milestone, so the benefit term
    separates almost nothing and `J` reduces to acquisition cost — where the
    zero-cost trunk wins by costing nothing rather than by being worth more.
    Live equivalent: R2D2 at L19, spread exactly 0 over 9 candidates."""
    spread, reachers, total = _spread("l19_band_edge", 20, game_data)
    assert reachers == total, "every candidate should reach a milestone one level away"
    assert spread is not None
    assert spread <= 1


def test_the_same_character_nine_levels_out_can_discriminate(game_data):
    """THE OTHER POLE, on a fixture identical but for level. A longer walk gives
    an acquisition room to repay itself, so the same candidate set separates."""
    spread, reachers, total = _spread("l11_band_floor", 20, game_data)
    assert reachers == total
    assert spread is not None
    assert spread > 1


def test_widening_the_horizon_widens_what_the_objective_can_see(game_data):
    """The property both fixtures exist for, stated as an ORDER over three
    horizons rather than as magnitudes: discrimination is monotone in how far the
    walk runs. Asserting numbers here would pin a cold-store artefact."""
    near, _, _ = _spread("l19_band_edge", 20, game_data)
    far, _, _ = _spread("l19_band_edge", 30, game_data)
    floor_near, _, _ = _spread("l11_band_floor", 20, game_data)
    floor_far, _, _ = _spread("l11_band_floor", 30, game_data)
    assert near is not None and far is not None
    assert floor_near is not None and floor_far is not None
    assert far > near
    assert floor_far > floor_near


def test_level_fifty_is_out_of_reach_from_either_edge(game_data):
    """Why the shipped objective is inert, reproduced offline on both fixtures:
    against `TARGET_LEVEL` nothing arrives, so `J` is void for every candidate and
    S-006 decides on acquisition cost alone."""
    for name in ("l19_band_edge", "l11_band_floor"):
        spread, reachers, _ = _spread(name, 50, game_data)
        assert reachers == 0, f"{name} unexpectedly reaches L50"
        assert spread is None
