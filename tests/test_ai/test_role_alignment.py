"""Tests for the role_alignment fifth ranking factor: the pure core, its
threading through progression_tree_core, and the `_role_map` assembly —
no longer live (see below), exercised here directly instead.

WAVE 3a DELETED THREE TESTS FROM THIS FILE — the no-role sweep, the
role-flips-the-pick witness, and the role-alone `aged_pick` precondition. All
three drove `decide_tree`, which no longer ranks candidates at all, so the role
factor has no path through it to test. `role_alignment_pure`, `_role_map` and
their threading through `focus_aging_pick`/`focus_aging_order` are still
exercised here directly; the factor itself is deleted in wave 3b."""

import json
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.role_alignment import ALIGNED, MISALIGNED, role_alignment_pure
from artifactsmmo_cli.ai.tiers.progression_tree import (
    _role_map,
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
# name into the per-(slot, code) multiplier. Its path through `decide_tree`
# was live at Task 14; wave 3a's resolution walk does not call it, so from
# this commit `_role_map` is test-only, kept for wave 3b to judge along with
# the rest of the ranking factor (module docstring above).
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
    role (the empty-owned-skills sentinel) produces a GENUINELY empty map, not
    a map of `Fraction(1)`s. Empty is what makes `_NO_ROLE`'s semantics exact
    — every `.get` falls through to the no-signal default and both fast-path
    guards stay inert."""
    assert _role_map(skill_candidates, frozenset(), _skill_gd()) == {}


def test_role_map_damps_off_role_candidates(skill_candidates: list[GearCandidate]) -> None:
    """`miner` owns mining + weaponcrafting: the mining-produced bar is
    ALIGNED, the gearcrafting shield is MISALIGNED, and the item with no known
    producing skill is ALIGNED (no signal is never a penalty)."""
    mapped = _role_map(skill_candidates, frozenset({"mining", "weaponcrafting"}), _skill_gd())
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
    assert set(_role_map(cands, frozenset({"mining", "weaponcrafting"}), _skill_gd())) == {
        ("ring1_slot", "copper_bar"), ("ring2_slot", "copper_bar")}


