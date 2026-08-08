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
    candidate_identity,
    finite_j,
    gear_candidate,
    justifying_identities,
    trunk_candidate,
)
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel
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
    decide_tree,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    FOCUS_SPAN,
    Branch,
    GearCandidate,
    focus_aging_pick,
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


def test_gear_root_is_the_one_that_justified_the_branch(game_data, store):
    """The live R2D2 defect, as a test.

    `J` chose GEAR because a weapon raised the reachable level, while the gear
    branch committed to a body armour with zero ceiling gain.

    NOT THE GUARD FOR THAT FIX — this one passes with the filter removed, because
    in every committed scenario the raw-gain argmax already IS the ceiling-raiser.
    It pins the agreement that must hold; `test_aged_weapon_still_wins_the_gear_
    branch` is the test that bites."""
    state, objective, gear = _candidates("l1_fresh", game_data)
    with store.search_cache():
        ranking = branch_ranking(state, game_data, gear, store)
        decision = decide_tree(state, game_data, objective,
                               band_adequate=False, store=store)
    assert branch_from_ranking(ranking) is Branch.GEAR
    assert justifying_identities(ranking) == {"weapon_slot:copper_dagger"}, (
        "fixture drift: this test only bites while exactly one candidate "
        "justifies the branch"
    )
    assert isinstance(decision.chosen_root, ObtainItem)
    assert decision.chosen_root.code == "copper_dagger", (
        "the gear branch pursued a root that did not justify choosing it"
    )


def test_aged_weapon_still_wins_the_gear_branch(game_data, store):
    """The R2D2 shape, reproduced through the mechanism that actually caused it.

    In every committed scenario the raw-gain argmax happens to BE the
    ceiling-raiser (weapons carry the top gain), so the plain decision cannot
    exhibit the split — an earlier version of the test above passed with the
    filter removed, i.e. it was vacuous. What diverged live was the five
    selection factors: a focus ledger, synergy, achievability or role steering
    the pick away from the one candidate the objective had endorsed.

    Here the weapon is aged far past `FOCUS_FLAT`, so `focus_aging_pick` decays it
    and hands the cycle to another candidate. That is correct anti-starvation
    behaviour among interchangeable roots — and wrong when the decayed root is the
    ONLY one buying progression, because the alternatives it rotates to cannot
    advance the character at all. The objective's filter has to win that argument.
    """
    state, objective, gear = _candidates("l1_fresh", game_data)
    aged = {("weapon_slot", "copper_dagger"): FOCUS_FLAT + FOCUS_SPAN}
    seats: dict[str, int] = {}

    unfiltered = focus_aging_pick(gear, aged, dict(seats))
    assert unfiltered is not None and unfiltered.code != "copper_dagger", (
        "fixture drift: aging no longer moves the pick off the weapon, so this "
        "test would prove nothing"
    )

    with store.search_cache():
        decision = decide_tree(state, game_data, objective, band_adequate=False,
                               focus=aged, seats=seats, store=store)
    assert isinstance(decision.chosen_root, ObtainItem)
    assert decision.chosen_root.code == "copper_dagger", (
        "aging rotated the gear branch onto a root that buys no progression, "
        "while the root that justified choosing the branch went unpursued"
    )


def test_demoted_candidates_stay_reachable_behind_the_trunk(game_data, store):
    """Filtering must not cost liveness: every demoted root stays in the fallback
    list, after the trunk, so a board whose justifying pick AND trunk are both
    unservable cannot deadlock — while a root that buys no progression is never
    tried ahead of simply grinding."""
    state, objective, gear = _candidates("l1_fresh", game_data)
    with store.search_cache():
        decision = decide_tree(state, game_data, objective,
                               band_adequate=False, store=store)
    codes = [r.code for r in decision.fallback_roots if isinstance(r, ObtainItem)]
    demoted = {c.code for c in gear if c.code != "copper_dagger"}
    assert demoted <= set(codes), "a demoted candidate vanished from the fallbacks"
    trunk_at = next(i for i, r in enumerate(decision.fallback_roots)
                    if isinstance(r, ReachCharLevel))
    demoted_positions = [i for i, r in enumerate(decision.fallback_roots)
                         if isinstance(r, ObtainItem) and r.code in demoted]
    assert min(demoted_positions) > trunk_at


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


def test_display_ranking_carries_the_objective_value(game_data, store):
    """The display must show the scale the pivot decided on.

    `score` is `pursuit_value` for gear and a constant `Fraction(1)` for the xp
    trunk — two unrelated scales in one column. Read as a ranking it showed gear
    ahead 2.6e8 to 1.0 on live cycles where `J` had the trunk winning by 0.006%,
    which is what sent a reader looking for a bug in the pivot (2026-08-08).
    `j` is the row's real standing, and lower wins."""
    state, objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    with store.search_cache():
        decision = decide_tree(state, game_data, objective,
                               band_adequate=False, store=store)
    trunk_row = next(r for r in decision.ranking if r.category == "char_level")
    # Still the legacy constant — deliberately NOT overwritten with J, which is
    # lower-is-better and would invert the field's meaning.
    assert trunk_row.score == Fraction(1)
    by_identity = {c.identity: finite_j(c) for c in decision.j_ranking}
    assert trunk_row.j == by_identity[TRUNK_IDENTITY]


def test_display_ranking_has_no_objective_value_without_a_store(game_data):
    """No store means no objective, so every row reports `j=None` rather than a
    number the pivot never computed."""
    state, objective, _gear = _candidates("l12_deep_chain_grind", game_data)
    decision = decide_tree(state, game_data, objective, band_adequate=False)
    assert all(r.j is None for r in decision.ranking)


def test_display_ranking_keeps_the_demoted_candidates(game_data, store):
    """The `ranking` rows are a diagnostic — a reader comparing them against
    `j_ranking` must see the roots the objective ruled out."""
    state, objective, gear = _candidates("l1_fresh", game_data)
    with store.search_cache():
        decision = decide_tree(state, game_data, objective,
                               band_adequate=False, store=store)
    assert len(decision.ranking) == len(gear) + 1  # + the trunk row
