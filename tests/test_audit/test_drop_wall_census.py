"""The drop-wall census — `is_winnable` on DROP, named where it actually binds.

The census asserts that every candidate root priced at `UNOBTAINABLE_PER_UNIT`
is either not this census's subject or falls into a named unwinnable-dropper
wall. These tests exist to stop it becoming decorative, which for THIS census
means five things:

* it must sweep the CANDIDATES, not the argmax — `test_the_sweep_prices_the_
  alternatives_and_not_only_the_argmax` pins that the grid is wider than the
  scenario count, because a resolved-root-only sweep sees ZERO of the nine walls
  in the committed set and would report a clean grid;
* its detector must be production's — `test_the_crossing_is_the_pricers_own_
  answer` cross-reads the differential against `route_price` directly;
* every arm must be able to FIRE — the committed fixtures exercise only the
  CLOSES arm, so `WALL_DROPPER_OUT_OF_REACH` is pinned by a positive control
  over synthetic evidence. An unexercised classifier no test can make fire is
  the decorative case this file exists to prevent;
* it must be able to FAIL — `test_the_unattributed_residual_can_fire` exhibits
  the multi-wall hole the taxonomy deliberately leaves open;
* the arm counts are PINNED — `test_only_the_closes_arm_is_exercised_and_the_
  matrix_says_so` asserts 9 CLOSES and 0 OUT_OF_REACH, so the first fixture that
  changes either fails here rather than letting the claim rot. That guard is the
  one that paid off for the gold row.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.drop_wall_census import (
    GRANT,
    MIN_CELLS,
    RESIDUALS,
    DropEvidence,
    DropGap,
    DropResult,
    argmax_blindness,
    classify,
    declared_world,
    drop_evidence,
    render_matrix,
    run_census,
    summary_line,
    unwinnable_drop_items,
    witness_residual,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

CLOSES = DropGap.WALL_DROPPER_UNWINNABLE_CLOSES.value
OUT_OF_REACH = DropGap.WALL_DROPPER_OUT_OF_REACH.value


@pytest.fixture(scope="module")
def results() -> list[DropResult]:
    return run_census(BUNDLE)


def _walls(results: list[DropResult]) -> list[DropResult]:
    return [r for r in results if r.gap.startswith("wall_")]


def _result(**overrides: object) -> DropResult:
    base = DropResult(scenario="s", candidate="c", is_resolved_root=False,
                      base_price=UNOBTAINABLE_PER_UNIT, granted_price=1,
                      gate_price=UNOBTAINABLE_PER_UNIT, gap=CLOSES,
                      evidence=None)
    return dataclasses.replace(base, **overrides)  # type: ignore[arg-type]


# --- the sweep is real ------------------------------------------------------

def test_the_sweep_prices_the_alternatives_and_not_only_the_argmax(
        results: list[DropResult]) -> None:
    """The grid must be WIDER than one cell per scenario.

    This is the census's whole reason for existing. An infinite price is a veto,
    so a drop-walled candidate never becomes the argmax — measured on the
    committed bundle, ALL of the walls sit on alternatives and a resolved-root
    census sees none of them. A sweep that quietly collapsed to the argmax would
    report a clean grid and prove nothing."""
    assert len(results) >= MIN_CELLS
    assert len(results) > len(SCENARIOS)
    assert sum(1 for r in results if not r.is_resolved_root) > 0
    assert sum(1 for r in results if r.is_resolved_root) > 0


def test_no_residual_cell(results: list[DropResult]) -> None:
    """The gate condition: every unobtainable candidate that crosses on the
    collective grant has a single item owning the gap."""
    offenders = [(r.scenario, r.candidate, r.gap)
                 for r in results if r.gap in RESIDUALS]
    assert offenders == []


def test_the_closes_arm_has_a_witness(results: list[DropResult]) -> None:
    """`witness_residual` is the alarm for a census whose subject never
    appears — the state the currency census shipped in, undetected, for a whole
    section."""
    assert witness_residual(results) is None


def test_only_the_closes_arm_is_exercised_and_the_matrix_says_so(
        results: list[DropResult]) -> None:
    """PINNED COUNTS, so the day a fixture changes them this FAILS rather than
    rotting.

    9 CLOSES / 0 OUT_OF_REACH on the committed bundle. The zero is asserted
    deliberately: `WALL_DROPPER_OUT_OF_REACH` classifies nothing here, which is a
    fact about the fixture set and not a success, and the arm is kept honest by a
    positive control below rather than by this grid."""
    assert sum(1 for r in results if r.gap == CLOSES) == 9
    assert sum(1 for r in results if r.gap == OUT_OF_REACH) == 0
    assert all(not r.is_resolved_root for r in _walls(results))


def test_every_wall_names_an_item_a_dropper_and_a_chain(
        results: list[DropResult]) -> None:
    """A wall with no evidence is a name without a subject — the failure mode
    §7's `WALL_GOLD` had for two sections running."""
    for wall in _walls(results):
        assert wall.evidence is not None
        assert wall.evidence.item
        assert wall.evidence.on_live_tiles
        assert wall.granted_price < wall.base_price
        if wall.gap == CLOSES:
            assert wall.evidence.closes
            assert wall.evidence.chain


# --- the detector is production's own ---------------------------------------

def test_the_crossing_is_the_pricers_own_answer(results: list[DropResult]) -> None:
    """Cross-read against `route_price` directly: the census may not claim a
    crossing the pricer does not make.

    `gated_drop=False` on both walks, because that is the world the census
    measures — the STRUCTURAL wall, the routes `obtain_sources` serves. The
    default (gate on) is what production charges, and it is asserted separately
    below as `gate_price`; conflating the two is what made this census briefly
    report its own fix as a broken grid."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    wall = _walls(results)[0]
    scenario = SCENARIOS[wall.scenario]
    game_data = declared_world(scenario, BUNDLE, cache)
    state = scenario_state(scenario, game_data)
    resolution = resolve_root(state, game_data,
                              CharacterObjective.from_game_data(game_data),
                              NO_PROFILE_CONTEXT, None)
    candidate = next(c for c in (resolution.root, *resolution.alternatives)
                     if repr(c) == wall.candidate)
    assert wall.evidence is not None
    base = route_price(candidate, state, game_data, NO_PROFILE_CONTEXT, None,
                       gated_drop=False)
    rich = dataclasses.replace(state, inventory={
        **state.inventory,
        wall.evidence.item: state.inventory.get(wall.evidence.item, 0) + GRANT})
    granted = route_price(candidate, rich, game_data, NO_PROFILE_CONTEXT, None,
                          gated_drop=False)
    assert base >= UNOBTAINABLE_PER_UNIT
    assert granted < base
    assert (base, granted) == (wall.base_price, wall.granted_price)
    assert wall.gate_price == route_price(candidate, state, game_data,
                                          NO_PROFILE_CONTEXT, None,
                                          gated_drop=True)


def test_the_walled_set_negates_the_drop_source_conjuncts() -> None:
    """`unwinnable_drop_items` must read the same three facts
    `obtain_sources._drop_sources` gates on — and must not be empty on a
    fixture set where the wall has nine witnesses."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    scenario = SCENARIOS["l10_copper_adequate"]
    game_data = declared_world(scenario, BUNDLE, cache)
    state = scenario_state(scenario, game_data)
    walled = unwinnable_drop_items(state, game_data)
    assert "cowhide" in walled
    for item in walled:
        live = [m for m, _r, _mn, _mx in game_data.monsters_dropping(item)
                if game_data.all_monster_locations.get(m)]
        assert live, f"{item} has no live dropper — not this wall's subject"


def test_an_obtainable_candidate_is_never_walled(results: list[DropResult]) -> None:
    """A price below the ceiling is not a wall, whatever the drop tables say.
    Without this the classifier could name a wall on a route that works."""
    for result in results:
        if result.gap == DropGap.ROOT_UNRESOLVED.value:
            continue  # no candidate was priced at all — prices are placeholders
        if result.base_price < UNOBTAINABLE_PER_UNIT:
            assert result.gap == DropGap.OBTAINABLE.value


# --- every arm can fire -----------------------------------------------------

def test_the_out_of_reach_arm_fires_on_a_monster_no_chain_closes(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """POSITIVE CONTROL for the arm the committed fixtures do not exercise.

    Nine cells classify CLOSES and none OUT_OF_REACH, so without this the second
    arm is a branch no test can make fire — an unexercised classifier that could
    be wrong in any way at all and never say so."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    scenario = SCENARIOS["l10_copper_adequate"]
    game_data = declared_world(scenario, BUNDLE, cache)
    state = scenario_state(scenario, game_data)
    monkeypatch.setattr("artifactsmmo_cli.audit.drop_wall_census.combat_deficit",
                        lambda *_a, **_kw: None)
    evidence = drop_evidence("cowhide", state, game_data)
    assert evidence.on_live_tiles
    assert evidence.closes == ()
    assert evidence.chain == ()


def test_the_unattributed_residual_can_fire(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """The hole the taxonomy leaves open: the collective grant crosses and no
    single item does, so two or more drop walls hold the candidate up together
    and this probe cannot say which owns the gap.

    Exhibited by making the pricer answer as such a candidate would — the
    collective probe cheap, every single probe still walled."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    scenario = SCENARIOS["l10_copper_adequate"]
    game_data = declared_world(scenario, BUNDLE, cache)
    state = scenario_state(scenario, game_data)
    walled = unwinnable_drop_items(state, game_data)
    calls: list[int] = []

    def fake_price(_candidate, priced_state, *_args, **_kwargs) -> int:
        calls.append(len(priced_state.inventory))
        granted = len(priced_state.inventory) - len(state.inventory)
        return 1 if granted > 1 else UNOBTAINABLE_PER_UNIT

    monkeypatch.setattr("artifactsmmo_cli.audit.drop_wall_census.route_price",
                        fake_price)
    gap, base, granted, _gate, evidence = classify(
        object(), state, game_data, walled)  # type: ignore[arg-type]
    assert gap == DropGap.DROP_WALL_UNATTRIBUTED.value
    assert base == UNOBTAINABLE_PER_UNIT
    assert granted == 1
    assert evidence is None
    assert len(calls) == 3 + len(walled)


def test_a_candidate_with_no_walled_items_is_not_this_censuss_subject(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """An unobtainable candidate in a world where every dropper is beatable is
    `not_drop_walled` — and the census must not spend a price walk finding that
    out."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    scenario = SCENARIOS["l10_copper_adequate"]
    game_data = declared_world(scenario, BUNDLE, cache)
    state = scenario_state(scenario, game_data)
    calls: list[object] = []

    def fake_price(*_args, **_kwargs) -> int:
        calls.append(None)
        return UNOBTAINABLE_PER_UNIT

    monkeypatch.setattr("artifactsmmo_cli.audit.drop_wall_census.route_price",
                        fake_price)
    gap, base, granted, gate, evidence = classify(object(), state, game_data, ())  # type: ignore[arg-type]
    assert gap == DropGap.NOT_DROP_WALLED.value
    assert (base, granted, gate, evidence) == (UNOBTAINABLE_PER_UNIT,
                                               UNOBTAINABLE_PER_UNIT,
                                               UNOBTAINABLE_PER_UNIT, None)
    assert len(calls) == 1


def test_a_root_the_walk_cannot_resolve_is_a_visible_row(
        results: list[DropResult]) -> None:
    """A scenario whose walk offers nothing contributes a ROW, not silence — but
    it is not a residual, on the same reading its currency sibling takes."""
    unresolved = [r for r in results if r.gap == DropGap.ROOT_UNRESOLVED.value]
    assert DropGap.ROOT_UNRESOLVED.value not in RESIDUALS
    for row in unresolved:
        assert row.candidate == "-"
        assert row.passed


# --- the report says what it measured ---------------------------------------

def test_the_summary_reports_the_arm_counts(results: list[DropResult]) -> None:
    line = summary_line(results)
    assert "candidate cells" in line
    assert "gate opens 2 of 9 walls (store-less)" in line
    assert "closes 9" in line
    assert "out_of_reach 0" in line
    assert "on ALTERNATIVES" in line


def test_the_blindness_line_is_computed_not_transcribed(
        results: list[DropResult]) -> None:
    """`argmax_blindness` IS §2 of the design, and it must be derived from the
    grid so it cannot rot into a comment about a fixture set that has moved."""
    line = argmax_blindness(results)
    walls = _walls(results)
    on_root = sum(1 for r in walls if r.is_resolved_root)
    assert f"{on_root} of {len(walls)} walls" in line
    assert f"misses {len(walls) - on_root}" in line


def test_the_matrix_renders_every_cell_and_flags_residuals() -> None:
    """Rendering is pure markdown over the results — including a residual row,
    which must be visibly marked rather than folded into the PASS column."""
    rows = [_result(gap=DropGap.OBTAINABLE.value, base_price=3,
                    granted_price=3),
            _result(gap=DropGap.DROP_WALL_UNATTRIBUTED.value),
            _result(gap=CLOSES, evidence=DropEvidence(
                item="cowhide", droppers=("cow",), on_live_tiles=("cow",),
                closes=("cow",), chain=("iron_sword",)))]
    matrix = render_matrix(rows)
    assert matrix.count("| s |") == 3
    assert f"**{DropGap.DROP_WALL_UNATTRIBUTED.value}**" in matrix
    assert "iron_sword" in matrix
    assert "drop_wall_unwitnessed" not in matrix


def test_the_matrix_carries_the_unwitnessed_alarm_when_no_arm_fires() -> None:
    """The alarm must reach the DOCUMENT, not only the gate — a matrix that
    reads clean while measuring nothing is the failure this census inherits from
    its sibling."""
    matrix = render_matrix([_result(gap=DropGap.OBTAINABLE.value)])
    assert "drop_wall_unwitnessed" in matrix


def test_the_census_keeps_counting_a_wall_the_gate_now_prices(
        results: list[DropResult]) -> None:
    """THE GUARD THAT FIRED ON CONTACT, kept as a test.

    `_gated_drop_option` prices part of this census's own subject away. Priced
    with the gate ON the grid dropped from 9 walls to 7 and `witness_residual`
    started reporting the FIX as a broken census — a thermometer that melts. So
    every price here is taken with `gated_drop=False` (the structural wall) and
    `gate_price` reports separately which walls the gate opens.

    Store-less, so this is the floor rather than the live figure: every unlock in
    the committed set is gear whose own craft is skill-gated, and with an
    observed grind rate the gate opens 3 of the 9 rather than 2."""
    walls = _walls(results)
    assert len(walls) == 9
    opened = [w for w in walls if w.gate_price < UNOBTAINABLE_PER_UNIT]
    assert len(opened) == 2
    for wall in opened:
        assert wall.base_price >= UNOBTAINABLE_PER_UNIT
        assert wall.gate_price < wall.base_price
