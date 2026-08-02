"""Tests for the role_alignment fifth ranking factor: the pure core, its
threading through progression_tree_core, and — since Task 14 — the LIVE
`_role_map` assembly and its path through `decide_tree`."""

import json
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.role_alignment import ALIGNED, MISALIGNED, role_alignment_pure
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _achievability_map,
    _role_map,
    _structural_candidates,
    _utility_candidates,
    decide_tree,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    GearCandidate,
    _scaled_weights,
    focus_aging_order,
    focus_aging_pick,
)


def test_candidate_in_our_skills_is_unpenalised() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "weaponcrafting") == ALIGNED


def test_candidate_outside_our_skills_is_damped() -> None:
    assert role_alignment_pure(frozenset({"mining", "weaponcrafting"}),
                               "gearcrafting") == MISALIGNED


def test_unknown_producing_skill_is_unpenalised() -> None:
    """No signal must never become a penalty — the no-invented-data rule."""
    assert role_alignment_pure(frozenset({"mining"}), None) == ALIGNED


def test_no_role_is_identity() -> None:
    assert role_alignment_pure(frozenset(), "weaponcrafting") == ALIGNED


def test_damping_never_reorders_below_zero() -> None:
    assert MISALIGNED > 0
    assert MISALIGNED < ALIGNED
    assert isinstance(MISALIGNED, Fraction)


@pytest.fixture
def gear_candidates() -> list[GearCandidate]:
    return [
        GearCandidate(slot="weapon_slot", code="iron_sword", gain=Fraction(100), level=10),
        GearCandidate(slot="ring1_slot", code="iron_ring", gain=Fraction(50), level=8),
        GearCandidate(slot="ring2_slot", code="iron_ring", gain=Fraction(50), level=8),
    ]


def test_default_role_is_inert(gear_candidates: list[GearCandidate]) -> None:
    """The inert-landing proof.

    Comparing the default call against `role=_NO_ROLE` explicitly would be
    VACUOUS: `_NO_ROLE` IS the default, so both sides invoke the identical
    object no matter what that object holds — a `_NO_ROLE` poisoned with a
    real `(slot, code)` entry would still make the two sides equal to each
    other (review finding, Task 13). Comparing against an INDEPENDENTLY
    constructed empty mapping instead means this test actually depends on
    `_NO_ROLE` being empty: if the default sentinel were ever poisoned, the
    poisoned default (left side) would diverge from the genuinely empty map
    (right side) and this test would fail."""
    focus: dict = {}
    seats: dict = {}
    truly_empty: dict[tuple[str, str], Fraction] = {}
    assert (_scaled_weights(gear_candidates, focus)
            == _scaled_weights(gear_candidates, focus, role=truly_empty))
    assert (focus_aging_pick(gear_candidates, focus, seats)
            is focus_aging_pick(gear_candidates, focus, seats, role=truly_empty))
    assert (focus_aging_order(gear_candidates, focus, seats)
            == focus_aging_order(gear_candidates, focus, seats, role=truly_empty))


def test_nonempty_role_map_changes_weight_pick_and_order() -> None:
    """Sanity check for the comparison methodology `test_default_role_is_inert`
    relies on: a role map that actually penalizes a candidate MUST change the
    weight, the pick, AND the order — demonstrating the comparison is capable
    of detecting a difference at all. Without this, a byte-identical assertion
    is evidence of nothing (review finding, Task 13)."""
    off_role = GearCandidate(slot="artifact3_slot", code="trophy", gain=Fraction(25050), level=20)
    on_role = GearCandidate(slot="ring1_slot", code="life_ring", gain=Fraction(21020), level=15)
    cands = [off_role, on_role]
    focus: dict = {}
    seats: dict = {}
    role = {("artifact3_slot", "trophy"): MISALIGNED}

    default_weights = dict(_scaled_weights(cands, focus))
    penalized_weights = dict(_scaled_weights(cands, focus, role=role))
    assert penalized_weights["artifact3_slot"] != default_weights["artifact3_slot"]
    assert penalized_weights["artifact3_slot"] == default_weights["artifact3_slot"] * MISALIGNED
    assert penalized_weights["ring1_slot"] == default_weights["ring1_slot"]

    default_pick = focus_aging_pick(cands, focus, seats)
    penalized_pick = focus_aging_pick(cands, focus, seats, role=role)
    assert default_pick is not None and penalized_pick is not None
    assert default_pick.code == "trophy"
    assert penalized_pick.code == "life_ring"

    default_order = [c.code for c in focus_aging_order(cands, focus, seats)]
    penalized_order = [c.code for c in focus_aging_order(cands, focus, seats, role=role)]
    assert default_order == ["trophy", "life_ring"]
    assert penalized_order == ["life_ring", "trophy"]
    assert default_order != penalized_order


# ---------------------------------------------------------------------------
# ACTIVATION (Task 14): `_role_map`, the impure assembly that turns a held role
# name into the per-(slot, code) multiplier, and its live path through
# `decide_tree`.
# ---------------------------------------------------------------------------

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json")


def _bundle() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _skill_gd() -> GameData:
    """A tiny GameData whose producing skills are known exactly.

    `copper_bar` crafts with mining, `wooden_shield` crafts with gearcrafting,
    `mystery_relic` has neither a recipe nor a resource that drops it, so
    `producing_skill` returns None for it — the no-signal case."""
    gd = GameData()
    gd._item_stats = {
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource",
                                crafting_skill="mining", crafting_level=1),
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "mystery_relic": ItemStats(code="mystery_relic", level=1, type_="artifact"),
    }
    gd._crafting_recipes = {"copper_bar": {"copper_ore": 10},
                            "wooden_shield": {"ash_plank": 6}}
    gd._resource_drops = {}
    gd._resource_skill = {}
    return gd


@pytest.fixture
def skill_candidates() -> list[GearCandidate]:
    return [
        GearCandidate(slot="weapon_slot", code="copper_bar", gain=Fraction(100), level=1),
        GearCandidate(slot="shield_slot", code="wooden_shield", gain=Fraction(50), level=1),
        GearCandidate(slot="artifact1_slot", code="mystery_relic", gain=Fraction(10), level=1),
    ]


def test_role_map_is_empty_without_a_role(skill_candidates: list[GearCandidate]) -> None:
    """The no-role identity, at the assembly layer: a character holding no
    role produces a GENUINELY empty map, not a map of `Fraction(1)`s. Empty is
    what makes `_NO_ROLE`'s semantics exact — every `.get` falls through to the
    no-signal default and both fast-path guards stay inert."""
    assert _role_map(skill_candidates, None, _skill_gd()) == {}


def test_role_map_damps_off_role_candidates(skill_candidates: list[GearCandidate]) -> None:
    """`miner` owns mining + weaponcrafting: the mining-produced bar is
    ALIGNED, the gearcrafting shield is MISALIGNED, and the item with no known
    producing skill is ALIGNED (no signal is never a penalty)."""
    mapped = _role_map(skill_candidates, "miner", _skill_gd())
    assert set(mapped.values()) <= {ALIGNED, MISALIGNED}
    assert all(isinstance(k, tuple) and len(k) == 2 for k in mapped)
    assert mapped == {
        ("weapon_slot", "copper_bar"): ALIGNED,
        ("shield_slot", "wooden_shield"): MISALIGNED,
        ("artifact1_slot", "mystery_relic"): ALIGNED,
    }


def test_role_map_keys_two_same_code_candidates_separately() -> None:
    """`(slot, code)` keying, same as `focus`/`synergy`/`achievability`: two
    candidates sharing a code but targeting different slots stay distinct
    entries, so keying by code alone would collapse them."""
    cands = [
        GearCandidate(slot="ring1_slot", code="copper_bar", gain=Fraction(10), level=1),
        GearCandidate(slot="ring2_slot", code="copper_bar", gain=Fraction(10), level=1),
    ]
    assert set(_role_map(cands, "miner", _skill_gd())) == {
        ("ring1_slot", "copper_bar"), ("ring2_slot", "copper_bar")}


def test_role_map_rejects_a_role_outside_the_catalog(
        skill_candidates: list[GearCandidate]) -> None:
    """A role name the catalog does not know is a consistency failure, not a
    missing-data case. Degrading it to `{}` would silently switch the whole
    fifth factor off — the invisible-inertness failure this epic keeps
    guarding against — so it raises."""
    with pytest.raises(ValueError, match="not in ROLE_CATALOG"):
        _role_map(skill_candidates, "blacksmith", _skill_gd())


def _tree_candidates(state, gd, objective) -> list[GearCandidate]:
    return _structural_candidates(state, gd, objective) + _utility_candidates(
        state, gd, objective)


def _gear_order(decision) -> list[str]:
    """The gear rows of a decision's ranking, in order (row 0 is the trunk)."""
    return [row.root_repr for row in decision.ranking[1:]]


def test_decide_tree_without_a_role_matches_the_four_factor_ranking() -> None:
    """THE NO-ROLE PROOF, over every scenario that offers gear candidates.

    The expected order is recomputed INDEPENDENTLY from the cores with the
    role argument never supplied at all — literally the four-factor call that
    existed before activation — and compared against what `decide_tree` now
    produces for a role-less character. So this does not merely assert that
    two role-less calls agree with each other (which would hold even if
    `_role_map` returned junk for None); it asserts the live five-factor path
    reproduces the four-factor function exactly.

    `aged_pick` is checked too: the seat-ledger verdict must not start firing
    on a character that has no role."""
    gd = _bundle()
    objective = CharacterObjective.from_game_data(gd)
    checked = 0
    for name in sorted(SCENARIOS):
        state = scenario_state(SCENARIOS[name], gd)
        candidates = _tree_candidates(state, gd, objective)
        if not candidates:
            continue
        checked += 1
        achievability = _achievability_map(candidates, state, gd)
        # The pre-activation call: no `role` argument, no `_NO_ROLE`, nothing.
        expected = focus_aging_order(candidates, {}, {}, {}, achievability)
        expected_reprs = [repr(ObtainItem(code=c.code, quantity=1, slot=c.slot))
                          for c in expected]
        decision = decide_tree(state, gd, objective,
                               ctx=replace(NO_PROFILE_CONTEXT, role=None))
        assert _gear_order(decision) == expected_reprs, name
        assert _role_map(candidates, None, gd) == {}, name
    assert checked >= 5, "the sweep must actually exercise scenarios with gear"


def test_decide_tree_role_flips_the_gear_pick() -> None:
    """The factor is LIVE, not merely threaded: on a real scenario a jeweler
    demotes the gearcrafting boots (raw-gain leader) below the jewelrycrafting
    amulet its own skill produces. Without the `role` argument reaching
    `focus_aging_pick`/`focus_aging_order` inside `decide_tree`, both calls
    return the role-less pick and this fails."""
    gd = _bundle()
    objective = CharacterObjective.from_game_data(gd)
    state = scenario_state(SCENARIOS["l12_gearcrafting_gap"], gd)

    roleless = decide_tree(state, gd, objective, ctx=NO_PROFILE_CONTEXT)
    jeweler = decide_tree(state, gd, objective,
                          ctx=replace(NO_PROFILE_CONTEXT, role="jeweler"))

    assert roleless.chosen_root == ObtainItem(
        code="iron_boots", quantity=1, slot="boots_slot")
    assert jeweler.chosen_root == ObtainItem(
        code="air_and_water_amulet", quantity=1, slot="amulet_slot")
    # The fallback ORDER moves with the head — `focus_aging_order` must get the
    # same role map, or `decide_tree`'s `ordered[0] == pick` assert would fire.
    assert _gear_order(jeweler) != _gear_order(roleless)
    assert _gear_order(jeweler)[0] == repr(jeweler.chosen_root)


def test_decide_tree_role_signal_alone_makes_the_pick_aged() -> None:
    """The Task-13 review's MANDATORY precondition, exercised.

    `l10_bag_pursuit` offers a single gearcrafting candidate with focus,
    synergy and achievability ALL inert — so `aged_pick` is False for a
    role-less character and for a `logger` (which owns gearcrafting, hence
    ALIGNED). A `miner` misaligns it, `focus_aging_pick` takes the d'Hondt
    interleave, and `aged_pick` MUST flip to True or the player skips its seat
    bump and the interleave schedule drifts from the seat ledger.

    Drop the role clause from `decide_tree`'s `aged_pick` guard and the miner
    case reads False — the exact silent drift the guard's comment warns of."""
    gd = _bundle()
    objective = CharacterObjective.from_game_data(gd)
    state = scenario_state(SCENARIOS["l10_bag_pursuit"], gd)

    def aged(role: str | None) -> bool:
        return decide_tree(state, gd, objective,
                           ctx=replace(NO_PROFILE_CONTEXT, role=role)).aged_pick

    assert aged(None) is False
    assert aged("logger") is False    # gearcrafting: ALIGNED, still inert
    assert aged("miner") is True      # off-role: a real signal, so aged
