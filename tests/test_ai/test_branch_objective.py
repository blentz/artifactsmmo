"""The unified objective in the branch pivot's seat (`tiers/branch_objective`).

The load-bearing test here is `test_gear_candidate_projection_sees_the_item`: the
whole wiring is worthless if a gear candidate's projection cannot tell the item
apart from not having it, and the first implementation could not. See that test's
docstring.
"""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.tiers.branch_objective import (
    TRUNK_IDENTITY,
    branch_from_ranking,
    branch_ranking,
    finite_j,
    gear_candidate,
    trunk_candidate,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    rank_candidates,
)
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _structural_candidates,
    _utility_candidates,
    decide_tree,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import Branch, GearCandidate

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"


@pytest.fixture(scope="module")
def game_data():
    return load_bundle_game_data(BUNDLE)


@pytest.fixture
def store():
    s = LearningStore(db_path=":memory:", character="probe")
    s.start_session()
    yield s
    s.close()


def _candidates(name, game_data):
    state = scenario_state(SCENARIOS[name], game_data)
    objective = CharacterObjective.from_game_data(game_data)
    gear = (_structural_candidates(state, game_data, objective)
            + _utility_candidates(state, game_data, objective))
    return state, objective, gear


def test_gear_candidate_projection_sees_the_item(game_data, store):
    """A gear candidate's projection must DIFFER from the trunk's when the item
    actually raises the ceiling. This is the test that catches the wiring's
    original defect.

    The first implementation projected by writing the item into
    `state.equipment`. That produces an INCOHERENT state: `state.attack` /
    `state.max_hp` are server-authoritative totals that already include worn
    gear, so `project_loadout_stats` correctly refuses to apply an item the
    totals claim is already counted. Every gear candidate then projected
    byte-identically to the trunk, `J` put them all in the unreachable band
    behind the trunk's zero acquisition cost, and the pivot degenerated to XP in
    100% of cycles — the exact mirror of the bug it replaces, and completely
    silent: every function returned, no exception, a plausible ranking.

    `l1_fresh` is the witness because a level-1 character's ceiling is set by
    having no real weapon, so a weapon MUST move it. Measured: reachable level 1
    without `copper_dagger`, 12 with it.
    """
    state, _objective, gear = _candidates("l1_fresh", game_data)
    dagger = next(c for c in gear if c.code == "copper_dagger")
    with store.search_cache():
        trunk = trunk_candidate(state, store, game_data)
        weapon = gear_candidate(dagger, state, store, game_data)
    assert trunk.reachable_level == state.level, (
        "a weaponless level-1 character cannot grind at all — if this changes, "
        "the witness below is no longer measuring what it claims to"
    )
    assert weapon.reachable_level > trunk.reachable_level, (
        "the projection is blind to the candidate item: holding a weapon must "
        "raise the reachable level for a character that has none"
    )


def test_gear_candidate_does_not_mutate_the_caller_state(game_data, store):
    """The projection is a private copy — the live state must survive it."""
    state, _objective, gear = _candidates("l1_fresh", game_data)
    dagger = next(c for c in gear if c.code == "copper_dagger")
    before = dict(state.inventory)
    with store.search_cache():
        gear_candidate(dagger, state, store, game_data)
    assert state.inventory == before


def test_trunk_costs_nothing_to_acquire(game_data, store):
    """The trunk is the baseline every gear candidate must beat by saving more
    cycles than it costs — which only works if grinding is free to start."""
    state, _objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    with store.search_cache():
        trunk = trunk_candidate(state, store, game_data)
    assert trunk.acquire_cost == 0
    assert trunk.identity == TRUNK_IDENTITY
    assert trunk.failed is False


def test_gear_acquisition_is_priced_in_actions(game_data, store):
    """`acquire_cost` counts ACTIONS (`min_plan_length`), so a candidate already
    held costs exactly the one Equip action — not its gold price, not its recipe
    slot count. The unit is what lets S-004 add it to a cycle count."""
    state, _objective, gear = _candidates("l1_fresh", game_data)
    dagger = next(c for c in gear if c.code == "copper_dagger")
    held = replace(state, inventory={**state.inventory, "copper_dagger": 1})
    with store.search_cache():
        from_scratch = gear_candidate(dagger, state, store, game_data)
        in_hand = gear_candidate(dagger, held, store, game_data)
    assert in_hand.acquire_cost == 1, "a held item is one Equip away"
    assert from_scratch.acquire_cost > in_hand.acquire_cost


def test_branch_is_gear_when_a_weapon_breaks_the_ceiling(game_data, store):
    """`l1_fresh`: grinding reaches level 1, `copper_dagger` reaches 12. Gear
    wins on S-006's furthest-progress key whatever it costs."""
    state, _objective, gear = _candidates("l1_fresh", game_data)
    with store.search_cache():
        ranking = branch_ranking(state, game_data, gear, store)
    assert branch_from_ranking(ranking) is Branch.GEAR
    assert ranking[0].identity == "weapon_slot:copper_dagger"


def test_branch_is_xp_when_no_candidate_moves_the_ceiling(game_data, store):
    """`l12_deep_chain_grind` offers only defensive gear, none of which lets the
    character kill anything it could not already kill. Every candidate ties the
    trunk's reachable level, so the trunk wins on acquisition cost — the case the
    legacy boolean pivot got wrong, choosing GEAR unconditionally."""
    state, _objective, gear = _candidates("l12_deep_chain_grind", game_data)
    assert gear, "scenario must offer gear candidates or this proves nothing"
    with store.search_cache():
        ranking = branch_ranking(state, game_data, gear, store)
    assert branch_from_ranking(ranking) is Branch.XP
    assert ranking[0].identity == TRUNK_IDENTITY


def test_branch_is_xp_with_no_gear_candidates(game_data, store):
    """No candidates: the trunk is the only entry and XP follows with no special
    case — `branch_pick_pure`'s "gear yields with no reachable target" arm, as a
    consequence rather than a rule."""
    state, _objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    with store.search_cache():
        ranking = branch_ranking(state, game_data, [], store)
    assert len(ranking) == 1
    assert branch_from_ranking(ranking) is Branch.XP


def test_ranking_keeps_every_candidate(game_data, store):
    """S-007: none omitted, duplicated or invented — the trunk plus each root."""
    state, _objective, gear = _candidates("l12_deep_chain_grind", game_data)
    with store.search_cache():
        ranking = branch_ranking(state, game_data, gear, store)
    assert len(ranking) == len(gear) + 1
    assert len({c.identity for c in ranking}) == len(ranking)


def test_exact_tie_breaks_toward_gear(game_data, store):
    """`branch_ranking` feeds the trunk in LAST, so `sorted`'s stability sends an
    exact `J` tie to gear. A tie means the gear pays for itself exactly, and the
    tie-break that matters keeps the loadout improving instead of freezing it."""
    paying = ProgressionCandidate(identity="weapon_slot:x", acquire_cost=40,
                                  reachable_level=TARGET_LEVEL, cycles_to_fifty=860,
                                  failed=False)
    trunk = ProgressionCandidate(identity=TRUNK_IDENTITY, acquire_cost=0,
                                 reachable_level=TARGET_LEVEL, cycles_to_fifty=900,
                                 failed=False)
    assert finite_j(paying) == finite_j(trunk) == 900
    assert branch_from_ranking(rank_candidates([paying, trunk])) is Branch.GEAR


def test_finite_j_is_none_outside_the_finite_band():
    """`objective_j` adds acquisition cost to a cycles figure S-014 declares void
    for an unreachable candidate, and the sort key never reads it there. Reporting
    the sum would publish a meaningless number under the objective's name."""
    unreachable = ProgressionCandidate(identity="g", acquire_cost=40,
                                       reachable_level=TARGET_LEVEL - 1,
                                       cycles_to_fifty=0, failed=False)
    failed = ProgressionCandidate(identity="g", acquire_cost=40,
                                  reachable_level=TARGET_LEVEL, cycles_to_fifty=10,
                                  failed=True)
    finite = ProgressionCandidate(identity="g", acquire_cost=40,
                                  reachable_level=TARGET_LEVEL, cycles_to_fifty=10,
                                  failed=False)
    assert finite_j(unreachable) is None
    assert finite_j(failed) is None
    assert finite_j(finite) == 50


def test_decide_tree_without_a_store_keeps_the_legacy_pivot(game_data):
    """No store means no projection, so the boolean pivot stands and every caller
    that does not opt in is byte-identical to before the wiring."""
    state, objective, gear = _candidates("l12_deep_chain_grind", game_data)
    assert gear, "the legacy pivot only chooses GEAR when candidates exist"
    decision = decide_tree(state, game_data, objective, band_adequate=False)
    assert decision.j_ranking == []
    assert not isinstance(decision.chosen_root, type(None))
    # band_adequate False + candidates present is branch_pick_pure's GEAR arm,
    # and J would have chosen XP here (see the xp test above) — so this pins the
    # opt-out as a real difference, not a coincidence.
    assert decision.chosen_root != decision.fallback_roots[-1]


def test_decide_tree_with_a_store_uses_the_objective(game_data, store):
    """The store is the opt-in: with one, the branch is J's and the ranking is
    attached for the trace."""
    state, objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    with store.search_cache():
        decision = decide_tree(state, game_data, objective,
                               band_adequate=False, store=store)
    assert decision.j_ranking, "the objective ran, so its ranking must be attached"
    assert decision.j_ranking[0].identity == TRUNK_IDENTITY
    trace = decision.to_trace()
    row = trace["j_ranking"][0]
    assert row["identity"] == TRUNK_IDENTITY
    assert row["acquire_cost"] == 0
    # Unreachable here, so `j` is withheld rather than reported meaninglessly.
    assert row["j"] is None
    assert row["failed"] is False


def test_unequippable_candidate_reads_as_worthless(game_data, store):
    """A candidate that cannot beat what is worn changes no monster's verdict and
    projects the trunk's own outcome — worthless, not an error."""
    state, _objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    junk = GearCandidate(slot="weapon_slot", code="wooden_stick",
                         gain=Fraction(1), level=1)
    with store.search_cache():
        trunk = trunk_candidate(state, store, game_data)
        weak = gear_candidate(junk, state, store, game_data)
    assert weak.reachable_level == trunk.reachable_level
    assert weak.acquire_cost > trunk.acquire_cost
