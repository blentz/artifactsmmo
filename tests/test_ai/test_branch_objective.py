"""The unified objective in the branch pivot's seat (`tiers/branch_objective`).

The load-bearing test here is `test_gear_candidate_projection_sees_the_item`: the
whole wiring is worthless if a gear candidate's projection cannot tell the item
apart from not having it, and the first implementation could not. See that test's
docstring.

WAVE 3a DELETED TEN TESTS FROM THIS FILE. Each one drove `decide_tree` and
asserted what it did with `J` — the store opt-in, the justifying filter, the
demoted tail, the `j`/`reachable_level` display columns, and the `aged_pick`
mirror. `decide_tree` does not consult `J` any more; the root is RESOLVED by
`ai/decisions/root.py`, not ranked. Those tests had no subject left, so they
were removed rather than re-pointed at some other function they never tested.
Everything they shared with the surviving tests — `branch_ranking`,
`branch_from_ranking`, `justifying_identities`, `finite_j`,
`candidate_identity`, `_j_by_identity` — is still exercised here directly. `J`
itself is deleted in wave 3b.
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
    candidate_identity,
    finite_j,
    gear_candidate,
    justifying_identities,
    trunk_candidate,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_choice import (
    TARGET_LEVEL,
    ProgressionCandidate,
    rank_candidates,
)
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _j_by_identity,
    _structural_candidates,
    _utility_candidates,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    Branch,
    GearCandidate,
)

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


def test_justifying_set_is_the_candidates_that_beat_the_trunk():
    """The gear branch may only pursue a candidate that justified choosing it.
    R2D2's live board, 2026-08-07."""
    trunk = ProgressionCandidate(identity=TRUNK_IDENTITY, acquire_cost=0,
                                 reachable_level=18, cycles_to_fifty=0, failed=False)
    staff = ProgressionCandidate(identity="weapon_slot:greater_wooden_staff",
                                 acquire_cost=2, reachable_level=25,
                                 cycles_to_fifty=0, failed=False)
    vest = ProgressionCandidate(identity="body_armor_slot:adventurer_vest",
                                acquire_cost=4, reachable_level=18,
                                cycles_to_fifty=0, failed=False)
    assert justifying_identities(rank_candidates([staff, vest, trunk])) == {
        "weapon_slot:greater_wooden_staff"}


def test_justifying_set_is_empty_on_the_xp_branch():
    """Nothing beats the trunk, so nothing is filtered — there is no gear root
    being pursued to filter."""
    trunk = ProgressionCandidate(identity=TRUNK_IDENTITY, acquire_cost=0,
                                 reachable_level=17, cycles_to_fifty=0, failed=False)
    junk = ProgressionCandidate(identity="helmet_slot:iron_helm", acquire_cost=2,
                                reachable_level=17, cycles_to_fifty=0, failed=False)
    assert justifying_identities(rank_candidates([junk, trunk])) == frozenset()


def test_justifying_set_without_a_trunk_is_empty():
    """No trunk means no baseline to beat — filter nothing rather than
    everything."""
    lone = ProgressionCandidate(identity="weapon_slot:x", acquire_cost=2,
                                reachable_level=25, cycles_to_fifty=0, failed=False)
    assert justifying_identities([lone]) == frozenset()


def test_candidate_identity_matches_the_projected_identity(game_data, store):
    """`justifying_identities` filters on strings minted by `gear_candidate`; if
    the two disagreed the filter would match nothing and silently empty the
    eligible list."""
    state, _objective, gear = _candidates("l1_fresh", game_data)
    c = gear[0]
    with store.search_cache():
        projected = gear_candidate(c, state, store, game_data)
    assert projected.identity == candidate_identity(c)


def test_j_by_identity_maps_only_finite_band_candidates():
    """The display map carries a value only where `J` means something.

    Built as a direct unit because the committed offline scenarios cannot reach
    the finite band at all — every candidate there is unreachable, so a
    scenario-driven test would exercise the empty case and quietly prove nothing.
    The live characters DID reach it on 2026-08-08, once the delta_xp fix let the
    projection complete a path to 50."""
    finite = ProgressionCandidate(identity="weapon_slot:staff", acquire_cost=2,
                                  reachable_level=TARGET_LEVEL,
                                  cycles_to_fifty=9986, failed=False)
    unreachable = ProgressionCandidate(identity="helmet_slot:iron_helm",
                                       acquire_cost=2, reachable_level=17,
                                       cycles_to_fifty=0, failed=False)
    mapping = _j_by_identity([finite, unreachable])
    assert mapping == {"weapon_slot:staff": 9988}
    assert "helmet_slot:iron_helm" not in mapping, (
        "a void J must be absent, not reported as a number"
    )


