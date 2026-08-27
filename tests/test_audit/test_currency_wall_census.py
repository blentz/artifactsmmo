"""O7: the currency-wall census (wave-6 routes design §7).

The census asserts that every currency the price walk charged at
`UNOBTAINABLE_PER_UNIT` while pricing a scenario's resolved root is either
task-earnable or a NAMED wall. These tests exist to stop it becoming decorative,
which for THIS census means four things:

* it must actually sweep something — `test_the_sweep_sees_the_whole_grid` pins
  lower bounds on cells and currencies, so a sweep that quietly discovered
  nothing fails instead of passing;
* its detector must be production's — `test_the_charge_is_the_pricers_own_answer`
  cross-reads the differential against `route_price` directly, and
  `test_granting_the_currency_clears_the_charge` shows the same cell flipping,
  so the census cannot claim a charge the pricer does not make;
* every arm must be able to FIRE — the three `WALL_*` classes are exercised by
  NOTHING in the committed fixture set (`walled 0`), so they are pinned by
  positive controls over synthetic evidence. An unexercised classifier that no
  test can make fire is the decorative case this file exists to prevent;
* it must be able to FAIL — `test_the_silent_stall_residual_can_fire` exhibits
  the contradiction the obligation exists for, and
  `test_the_unexplained_residual_can_fire` exhibits the hole the wall taxonomy
  deliberately leaves open.

`test_forcing_one_world_hides_the_only_funded_arm` is the fifth guard and the
one that matters most historically: it reproduces the defect that voided this
census's first run — pricing every scenario in a single default world — and
asserts that the `REFERENCE_SET_EMPTY` alarm fires on it. Without that test the
census could regress to a vacuous sweep and still print GATE CLEAN.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.decisions.root import resolve_root
from artifactsmmo_cli.ai.decisions.route import route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import (
    SCENARIOS,
    load_bundle_game_data,
    scenario_state,
)
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit import currency_wall_census as cwc
from artifactsmmo_cli.audit.currency_wall_census import (
    MIN_CELLS,
    RESIDUALS,
    CurrencyEvidence,
    CurrencyGap,
    CurrencyResult,
    catalogue_currencies,
    charged_currencies,
    classify_gap,
    currency_evidence,
    declared_world,
    demand_breakdown,
    reference_set_residual,
    render_matrix,
    run_census,
    summary_line,
    unattributed_wall,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")

FUNDED_CELL = "l25_currency_leaf_unfunded"
FUNDED_CURRENCY = "tasks_coin"


@pytest.fixture(scope="module")
def results() -> list[CurrencyResult]:
    return run_census(BUNDLE)


def _evidence(**overrides: object) -> CurrencyEvidence:
    """Synthetic evidence with everything empty unless named.

    The wall arms have no witness in the committed fixtures, so they are pinned
    here instead. Building the evidence directly (rather than contriving a
    scenario) keeps each control about ONE conjunct of `classify_gap`."""
    base: dict[str, object] = {
        "task_earnable": False, "droppers": (), "on_live_tiles": (),
        "winnable": (), "event_gated": (),
    }
    base.update(overrides)
    return CurrencyEvidence(**base)  # type: ignore[arg-type]


# --- the sweep is real ------------------------------------------------------

def test_the_sweep_sees_the_whole_grid(results: list[CurrencyResult]) -> None:
    """A census that discovered nothing reports 0 residuals and exits clean, so
    the floor is asserted here AND in the script (which the suite never runs)."""
    assert len(results) >= MIN_CELLS
    assert len(results) == len(SCENARIOS) * 6
    assert {r.currency for r in results} == {
        "corrupted_gem", "enchanted_coin", "event_ticket", "sandwhisper_coin",
        "sonnengott_coin", "tasks_coin"}
    assert all(r.gap in {g.value for g in CurrencyGap} for r in results)


def test_the_committed_bundle_has_no_residual(
        results: list[CurrencyResult]) -> None:
    """The gate's own claim, asserted in the suite as well as the script."""
    assert [r for r in results if r.gap in RESIDUALS] == []


def test_the_funded_arm_has_a_witness(results: list[CurrencyResult]) -> None:
    """O7's ship condition. The reference set is ONE cell, which is thin — so
    the test names it, and a fixture change that loses it fails here rather
    than silently turning the census vacuous."""
    funded = [r for r in results if r.gap == CurrencyGap.FUNDED.value]
    assert len(funded) == 1
    assert funded[0].scenario == FUNDED_CELL
    assert funded[0].currency == FUNDED_CURRENCY
    assert reference_set_residual(results) is None


def test_the_wall_arms_are_unexercised_and_the_matrix_says_so(
        results: list[CurrencyResult]) -> None:
    """A wall count of zero is a FINDING, not a success — recorded as an
    assertion so the day a fixture exercises a wall, this test fails and the
    claim in the docstring above gets revisited instead of rotting."""
    assert [r for r in results if r.gap.startswith("wall_")] == []
    assert "walled 0" in summary_line(results)


# --- the detector is production's own answer --------------------------------

def test_the_charge_is_the_pricers_own_answer() -> None:
    """The differential, cross-read against `route_price` directly. If these
    ever disagree the census is measuring something other than the price."""
    scenario = SCENARIOS[FUNDED_CELL]
    game_data = declared_world(scenario, BUNDLE, {})
    state = scenario_state(scenario, game_data)
    root = resolve_root(state, game_data,
                        CharacterObjective.from_game_data(game_data),
                        NO_PROFILE_CONTEXT, None).root
    assert root is not None
    charges = charged_currencies(root, state, game_data,
                                 catalogue_currencies(game_data))
    assert set(charges) == {FUNDED_CURRENCY}
    base, granted = charges[FUNDED_CURRENCY]
    assert base == route_price(root, state, game_data, NO_PROFILE_CONTEXT,
                               None)
    assert base >= 1_000_000 > granted


def test_granting_the_currency_clears_the_charge() -> None:
    """Proof it bites: the SAME cell with coins in the bag is not charged at
    all, so `charged` tracks the character's holdings and not the catalogue."""
    scenario = SCENARIOS[FUNDED_CELL]
    game_data = declared_world(scenario, BUNDLE, {})
    state = scenario_state(scenario, game_data)
    funded = dataclasses.replace(
        state, inventory={**state.inventory, FUNDED_CURRENCY: 500})
    root = resolve_root(funded, game_data,
                        CharacterObjective.from_game_data(game_data),
                        NO_PROFILE_CONTEXT, None).root
    assert root is not None
    assert charged_currencies(root, funded, game_data,
                              catalogue_currencies(game_data)) == {}


def test_a_merely_cheaper_route_is_not_a_charge() -> None:
    """THE PRECISION OF THE CENSUS, as an assertion.

    Any cheaper route lowers the price. If the detector tested `price < base` a
    currency that merely buys a material for fewer actions than gathering it
    would read as CHARGED, and the cell would classify as a WALL on a currency
    that walls nothing. The test is a CROSSING of `UNOBTAINABLE_PER_UNIT`, so an
    obtainable root contributes no charged cells however much a grant improves
    it — asserted here over every scenario whose root is already obtainable."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    obtainable = 0
    for scenario in SCENARIOS.values():
        game_data = declared_world(scenario, BUNDLE, cache)
        state = scenario_state(scenario, game_data)
        root = resolve_root(state, game_data,
                            CharacterObjective.from_game_data(game_data),
                            NO_PROFILE_CONTEXT, None).root
        if root is None:
            continue
        base = route_price(root, state, game_data, NO_PROFILE_CONTEXT, None)
        if base >= UNOBTAINABLE_PER_UNIT:
            continue
        obtainable += 1
        assert charged_currencies(root, state, game_data,
                                  catalogue_currencies(game_data)) == {}
    assert obtainable > 1, "the claim needs obtainable roots to be about"


def test_the_evidence_decomposes_the_drop_conjuncts() -> None:
    """`currency_evidence` must ask what `_drop_sources` asks. Read on real
    catalogue data so the columns in the matrix are not fiction."""
    scenario = SCENARIOS[FUNDED_CELL]
    game_data = declared_world(scenario, BUNDLE, {})
    state = scenario_state(scenario, game_data)

    gem = currency_evidence("corrupted_gem", state, game_data)
    assert set(gem.droppers) == {"corrupted_ogre", "corrupted_owlbear",
                                 "grimlet"}
    assert gem.on_live_tiles == ()
    assert set(gem.event_gated) == set(gem.droppers)
    assert not gem.task_earnable

    sand = currency_evidence("sandwhisper_coin", state, game_data)
    assert "sandwarden" in sand.on_live_tiles
    assert sand.winnable == ()

    coin = currency_evidence(FUNDED_CURRENCY, state, game_data)
    assert coin.task_earnable
    assert coin.droppers == ()


# --- every arm can fire (positive controls over synthetic evidence) ---------

def test_an_uncharged_currency_is_not_judged() -> None:
    assert classify_gap(False, _evidence()) is CurrencyGap.NOT_DEMANDED
    assert classify_gap(False, _evidence(task_earnable=True)) is \
        CurrencyGap.NOT_DEMANDED


def test_the_funded_arm_fires_on_a_task_earnable_currency() -> None:
    assert classify_gap(True, _evidence(task_earnable=True)) is \
        CurrencyGap.FUNDED


def test_the_no_producer_wall_fires_when_nothing_drops_it() -> None:
    """`enchanted_coin`'s real shape: flavour text names a raid boss, the
    catalogue models no drop, so the census classifies on the structural fact."""
    assert classify_gap(True, _evidence()) is CurrencyGap.WALL_NO_PRODUCER


def test_the_unwinnable_wall_fires_when_a_dropper_is_reachable_but_unbeatable(
) -> None:
    """`sandwhisper_coin`'s real shape: sandwarden is standing on a live tile
    and beats every committed character."""
    gap = classify_gap(True, _evidence(droppers=("sandwarden",),
                                       on_live_tiles=("sandwarden",)))
    assert gap is CurrencyGap.WALL_UNWINNABLE_DROP


def test_the_event_only_wall_fires_when_every_dropper_is_dormant_event_content(
) -> None:
    """`corrupted_gem`'s real shape: three droppers, all event-gated, none with
    a live tile."""
    gap = classify_gap(True, _evidence(
        droppers=("corrupted_ogre", "grimlet"),
        event_gated=("corrupted_ogre", "grimlet")))
    assert gap is CurrencyGap.WALL_EVENT_ONLY


def test_the_silent_stall_residual_can_fire() -> None:
    """THE OBLIGATION'S OWN RESIDUAL. A beatable dropper on a live tile
    contradicts a million-action price: the model can see that route."""
    gap = classify_gap(True, _evidence(droppers=("chicken",),
                                       on_live_tiles=("chicken",),
                                       winnable=("chicken",)))
    assert gap is CurrencyGap.O7_SILENT_CURRENCY_STALL
    assert gap.value in RESIDUALS


def test_the_winnable_check_precedes_every_wall() -> None:
    """Order is load-bearing. Testing the walls first would launder the
    contradiction into `wall_unwinnable_drop` — the residual renaming itself as
    an explanation — so the precedence is pinned rather than assumed."""
    contradictory = _evidence(droppers=("chicken",),
                              on_live_tiles=("chicken",),
                              winnable=("chicken",),
                              event_gated=("chicken",))
    assert classify_gap(True, contradictory) is \
        CurrencyGap.O7_SILENT_CURRENCY_STALL


def test_the_unexplained_residual_can_fire() -> None:
    """The hole the taxonomy deliberately leaves open: a PERMANENT dropper with
    no live tile. Not event-dormant, not unbeatable, not absent — so the census
    refuses to name it rather than picking the nearest wall."""
    gap = classify_gap(True, _evidence(droppers=("sandwarden", "sea_marauder"),
                                       event_gated=("sea_marauder",)))
    assert gap is CurrencyGap.O7_UNEXPLAINED
    assert gap.value in RESIDUALS


# --- the gap a single-currency probe cannot attribute -----------------------

def test_an_obtainable_root_is_never_an_unattributed_wall() -> None:
    """`unattributed_wall` must not fire on the ordinary case: a root that is
    already priceable needs no currency at all, so granting every currency
    cannot be what makes it obtainable.

    The obtainable root is SEARCHED FOR rather than named. Naming one couples
    the test to a fixture's current verdict — `l1_fresh` looks like the obvious
    choice and is in fact walled, its `wooden_stick` root pricing at exactly
    `UNOBTAINABLE_PER_UNIT`."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    checked = 0
    for scenario in SCENARIOS.values():
        game_data = declared_world(scenario, BUNDLE, cache)
        state = scenario_state(scenario, game_data)
        root = resolve_root(state, game_data,
                            CharacterObjective.from_game_data(game_data),
                            NO_PROFILE_CONTEXT, None).root
        if root is None or route_price(root, state, game_data,
                                       NO_PROFILE_CONTEXT,
                                       None) >= UNOBTAINABLE_PER_UNIT:
            continue
        checked += 1
        assert not unattributed_wall(root, state, game_data,
                                     catalogue_currencies(game_data))
    assert checked > 1, "the claim needs obtainable roots to be about"


def test_a_root_walled_on_a_non_currency_leaf_is_not_an_unattributed_wall(
) -> None:
    """The other half of the guard, and the one that would make the residual
    fire constantly if it were wrong: a root walled on an ordinary ITEM stays
    exactly as unobtainable when every currency is granted, so it must NOT be
    reported as a currency gap."""
    scenario = SCENARIOS[FUNDED_CELL]
    game_data = declared_world(scenario, BUNDLE, {})
    state = scenario_state(scenario, game_data)
    # A target whose closure contains no currency at all.
    root = ObtainItem(code="mithril_bar", quantity=99)
    assert route_price(root, state, game_data, NO_PROFILE_CONTEXT,
                       None) >= UNOBTAINABLE_PER_UNIT
    assert not unattributed_wall(root, state, game_data,
                                 catalogue_currencies(game_data))


def test_the_single_currency_case_is_attributed_not_left_unnamed() -> None:
    """The witnessed gap crosses on ONE currency, so it is named and the
    combined probe is never consulted — `run_census` skips it whenever
    something was attributed."""
    scenario = SCENARIOS[FUNDED_CELL]
    game_data = declared_world(scenario, BUNDLE, {})
    state = scenario_state(scenario, game_data)
    root = resolve_root(state, game_data,
                        CharacterObjective.from_game_data(game_data),
                        NO_PROFILE_CONTEXT, None).root
    assert root is not None
    currencies = catalogue_currencies(game_data)
    assert set(charged_currencies(root, state, game_data, currencies)) == \
        {FUNDED_CURRENCY}
    # It would ALSO cross when everything is granted — which is exactly why the
    # combined probe must not be the thing that decides the verdict.
    assert unattributed_wall(root, state, game_data, currencies)


def test_the_multi_currency_residual_is_a_must_be_zero_class() -> None:
    assert CurrencyGap.O7_MULTI_CURRENCY_WALL.value in RESIDUALS


# --- the grid-level residual, and the defect it exists for ------------------

def test_the_reference_set_alarm_fires_on_a_grid_with_no_funded_cell() -> None:
    walled = [CurrencyResult(
        scenario="s", currency="corrupted_gem", root="r", base_price=1,
        granted_price=0, charged=True, evidence=_evidence(),
        gap=CurrencyGap.WALL_NO_PRODUCER.value)]
    message = reference_set_residual(walled)
    assert message is not None
    assert "reference_set_empty" in message


def test_forcing_one_world_hides_the_only_funded_arm() -> None:
    """THE DEFECT THAT VOIDED THIS CENSUS'S FIRST RUN, as a regression test.

    Every `tasks_coin` sink sells at `tasks_trader`, whose tile is gated on the
    `tasks_farmer` achievement. Price the whole set in one DEFAULT world and the
    vendor does not exist, nothing is ever charged a fundable currency, and the
    sweep is a full-sized grid that proves nothing. The alarm must fire on it —
    without this test the census could regress to that state and print
    GATE CLEAN."""
    default_world = load_bundle_game_data(BUNDLE)
    forced: list[CurrencyResult] = []
    for name, scenario in SCENARIOS.items():
        state = scenario_state(scenario, default_world)
        root = resolve_root(
            state, default_world,
            CharacterObjective.from_game_data(default_world),
            NO_PROFILE_CONTEXT, None).root
        if root is None:
            continue
        currencies = catalogue_currencies(default_world)
        charges = charged_currencies(root, state, default_world, currencies)
        for code in currencies:
            evidence = currency_evidence(code, state, default_world)
            forced.append(CurrencyResult(
                scenario=name, currency=code, root=repr(root), base_price=0,
                granted_price=0, charged=code in charges, evidence=evidence,
                gap=classify_gap(code in charges, evidence).value))

    assert len(forced) >= MIN_CELLS, "the forced grid must be full-sized"
    assert [r for r in forced if r.gap == CurrencyGap.FUNDED.value] == []
    assert reference_set_residual(forced) is not None


def test_the_declared_world_is_read_off_the_scenario() -> None:
    """The fix, asserted at its seam: the achievement cell gets a world where
    the vendor exists, every other cell does not, and the cache keys on the
    declaration rather than on the scenario name."""
    cache: dict[tuple[bool, tuple[str, ...]], GameData] = {}
    unlocked = declared_world(SCENARIOS[FUNDED_CELL], BUNDLE, cache)
    locked = declared_world(SCENARIOS["l1_fresh"], BUNDLE, cache)
    assert unlocked.npc_location("tasks_trader") == (5, 11)
    assert locked.npc_location("tasks_trader") is None
    assert len(cache) == 2
    assert declared_world(SCENARIOS[FUNDED_CELL], BUNDLE, cache) is unlocked
    assert len(cache) == 2


# --- catalogue faults and unrooted scenarios --------------------------------

def test_an_empty_currency_catalogue_is_a_residual(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """A bundle that lost its currency rows must not sweep zero cells and exit
    clean. `MIN_CELLS` would also catch it; both floors are kept because they
    fail for different reasons."""
    monkeypatch.setattr(cwc, "catalogue_currencies", lambda _gd: ())
    results = run_census(BUNDLE)
    assert len(results) == len(SCENARIOS)
    assert {r.gap for r in results} == {
        CurrencyGap.CURRENCY_CATALOGUE_EMPTY.value}
    assert all(r.gap in RESIDUALS for r in results)


def test_an_unrooted_scenario_still_emits_its_cells(
        results: list[CurrencyResult]) -> None:
    """A silently skipped scenario shrinks the grid without shrinking the
    headline claim, so the cells are emitted and named instead."""
    unrooted = [r for r in results
                if r.gap == CurrencyGap.ROOT_UNRESOLVED.value]
    assert unrooted, "the committed set contains scenarios with no root"
    assert len(unrooted) % 6 == 0
    assert all(r.evidence is None and not r.charged for r in unrooted)
    assert all(r.passed for r in unrooted)


# --- the rendered artifact --------------------------------------------------

def test_the_summary_prints_every_residual_class(
        results: list[CurrencyResult]) -> None:
    line = summary_line(results)
    for gap in (CurrencyGap.O7_SILENT_CURRENCY_STALL,
                CurrencyGap.O7_UNEXPLAINED,
                CurrencyGap.CURRENCY_CATALOGUE_EMPTY):
        assert gap.value in line
    assert f"{len(results)} cells" in line


def test_the_demand_breakdown_states_the_residual_scope(
        results: list[CurrencyResult]) -> None:
    """The claim that stops "0 residuals over 264 cells" being read as a sweep:
    only CHARGED cells can ever be a residual, and there is one."""
    line = demand_breakdown(results)
    assert "1 of 264 cells are CHARGED" in line
    assert FUNDED_CURRENCY in line
    assert demand_breakdown([]) .endswith(
        "An uncharged currency can only be not_demanded.")
    assert "none" in demand_breakdown([])


def test_the_matrix_renders_every_cell(results: list[CurrencyResult]) -> None:
    matrix = render_matrix(results)
    assert matrix.startswith("# O7 Currency-Wall Census — Matrix")
    assert matrix.count("\n|") == len(results) + 2  # header + separator
    assert FUNDED_CELL in matrix
    assert "reference_set_empty" not in matrix


def test_the_matrix_shouts_when_the_reference_set_is_empty() -> None:
    """A vacuous grid must say so in the ARTIFACT, not only in the exit code —
    the doc outlives the pipeline run."""
    walled = [CurrencyResult(
        scenario="s", currency="corrupted_gem", root="r", base_price=1,
        granted_price=0, charged=True, evidence=_evidence(),
        gap=CurrencyGap.WALL_NO_PRODUCER.value)]
    assert "reference_set_empty" in render_matrix(walled)


def test_a_catalogue_empty_row_renders_without_evidence() -> None:
    """The evidence-less row has its own render path; a matrix that crashed on
    it would hide the data fault it exists to report."""
    empty = [CurrencyResult(
        scenario="s", currency="-", root="-", base_price=0, granted_price=0,
        charged=False, evidence=None,
        gap=CurrencyGap.CURRENCY_CATALOGUE_EMPTY.value)]
    assert "| s | - | **currency_catalogue_empty** | - | - | - |" in \
        render_matrix(empty)
