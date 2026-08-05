"""The shed-reachability census: it must be GREEN on the real catalog, and it
must go RED on a synthetic violation of each defect it gates.

A census that only ever passes is decoration. These cases exhibit both
residuals — defect A (a rung licensed real work that is not selected) end to
end at the production seam, and defect B (a code both drain-licensed and still
under its bank keep cap) through the census's own verdict — and pin the
anti-vacuity rules that stop either from passing for a boring reason.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_item import DepositItemAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.bank_drain import bank_drain_excess
from artifactsmmo_cli.ai.bank_room import bank_has_room
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.shed_reachability_completeness import (
    SELL_CODE,
    ShedCell,
    ShedCellKind,
    ShedGapClass,
    _check_cell,
    _require,
    _single_code_bank,
    census_ctx,
    census_state,
    classify_gap,
    deposit_arm_is_live,
    is_contradiction,
    licensed_work,
    render_matrix,
    route_contradictions,
    run_cell,
    run_census,
    scenario_for,
    shed_cell_verdict,
    shed_grid,
    stages_withdraw_then_sale,
    summary_line,
    within_bag_bound,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


# ── green on the real catalog ────────────────────────────────────────────────

def test_census_is_green_on_the_committed_catalog(gd: GameData) -> None:
    results = run_census(gd)
    assert len(results) == len(ShedCellKind)
    bad = [r for r in results if not r.passed]
    assert not bad, [(r.kind, r.gap, r.goal, r.plan) for r in bad]


def test_summary_line_reports_both_residuals(gd: GameData) -> None:
    line = summary_line(run_census(gd))
    assert "shed_starvation_bug 0" in line
    assert "disposal_contradiction_bug 0" in line


def test_matrix_renders_every_cell(gd: GameData) -> None:
    text = render_matrix(run_census(gd))
    for kind in ShedCellKind:
        assert f"| {kind.value} |" in text
    assert "PASS" in text


def test_grid_is_total_over_the_cell_kinds(gd: GameData) -> None:
    assert [c.kind for c in shed_grid(gd)] == list(ShedCellKind)


def test_scenario_for_refuses_an_unknown_kind(gd: GameData) -> None:
    class _Fake:
        pass

    with pytest.raises(ValueError, match="no census scenario"):
        scenario_for(_Fake(), gd)  # type: ignore[arg-type]


def test_require_refuses_an_item_the_catalog_lacks(gd: GameData) -> None:
    with pytest.raises(ValueError, match="not in the game catalog"):
        _require("not_a_real_item", gd)


# ── defect A: the census goes red when a licensed rung is not selected ───────

def test_census_goes_red_when_a_licensed_drain_is_not_selected(gd: GameData) -> None:
    """DEFECT A, end to end at the production seam.

    The cell is DELIBERATELY MIS-SPECIFIED: the same live bank, but the bag is
    already over the pressure watermark, which stands the hoist down. The drain
    is still licensed ~2000 copies and still loses its cycle — precisely the
    shape the traced run showed 44 times — so the census must call it what it
    is rather than explain it away."""
    live = scenario_for(ShedCellKind.DRAIN_SELECTABLE, gd)
    pressured = dataclasses.replace(live, bag={SELL_CODE: 110})
    state = census_state(pressured, gd)
    assert licensed_work(pressured, state, gd) > 1000
    result = run_cell(pressured, gd)
    assert not result.passed
    assert result.gap == ShedGapClass.SHED_STARVATION_BUG.value
    assert result.goal != "DrainBankJunk"


def test_census_goes_red_when_a_quiet_rung_wins(gd: GameData) -> None:
    """The gate's other direction. A QUIET verdict is only earned by NOT picking
    the rung — an unconditional hoist would win here and must fail."""
    quiet = scenario_for(ShedCellKind.DRAIN_QUIET, gd)
    state = census_state(quiet, gd)
    assert not shed_cell_verdict(quiet, _FakeGoal("DrainBankJunk"),
                                 [_stub_withdraw()], False, state, 0, 0)


def test_census_goes_red_when_a_quiet_cell_has_no_plan_at_all(gd: GameData) -> None:
    quiet = scenario_for(ShedCellKind.DRAIN_QUIET, gd)
    state = census_state(quiet, gd)
    assert not shed_cell_verdict(quiet, _FakeGoal("AcceptTask"), [], False,
                                 state, 0, 0)


def test_selected_rung_with_no_plan_still_fails(gd: GameData) -> None:
    """The half of defect A a band-only check would miss: the drain WAS
    selectable in principle and returned plan_len=0."""
    live = scenario_for(ShedCellKind.DRAIN_SELECTABLE, gd)
    state = census_state(live, gd)
    assert not shed_cell_verdict(live, _FakeGoal("DrainBankJunk"), [], False,
                                 state, 0, 0)


def test_a_planner_timeout_is_the_bug_never_an_explained_gap(gd: GameData) -> None:
    live = scenario_for(ShedCellKind.DRAIN_SELECTABLE, gd)
    state = census_state(live, gd)
    assert not shed_cell_verdict(live, _FakeGoal("DrainBankJunk"),
                                 [_stub_withdraw()], True, state, 0, 0)
    assert classify_gap(live, state, gd, True, 0) is ShedGapClass.SHED_STARVATION_BUG


# ── defect B: the census goes red on a contradiction ─────────────────────────

def test_census_goes_red_on_a_synthetic_contradiction(gd: GameData) -> None:
    """DEFECT B. A live contradiction is arithmetically impossible while both
    gates read one `keep_valuation` core — that is exactly what part 1 proved —
    so the detector is exercised by handing the verdict a contradiction count.
    The wiring that produces the count is pinned by the mutation gate."""
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    state = census_state(cell, gd)
    assert not shed_cell_verdict(cell, None, [], False, state,
                                 contradictions=1, swept=400)
    assert classify_gap(cell, state, gd, False, 1) \
        is ShedGapClass.DISPOSAL_CONTRADICTION_BUG


def test_a_sweep_that_licenses_nothing_cannot_pass(gd: GameData) -> None:
    """Anti-vacuity: zero contradictions over zero licensed codes is the most
    boring possible green."""
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    state = census_state(cell, gd)
    assert not shed_cell_verdict(cell, None, [], False, state,
                                 contradictions=0, swept=0)


def test_the_real_sweep_licenses_hundreds_of_codes(gd: GameData) -> None:
    """`swept` counts the codes the DRAIN LICENSES, not the codes walked. A
    sweep that counted the whole catalog would report a healthy-looking number
    while never testing the licence gate the invariant is conditioned on."""
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    state = census_state(cell, gd)
    contradictions, swept = route_contradictions(state, gd)
    assert contradictions == 0
    catalog = len(gd.all_item_stats)
    assert 100 < swept < catalog
    licensed = sum(
        1 for code in gd.all_item_stats
        if bank_drain_excess(_single_code_bank(state, code), gd,
                             census_ctx()).get(code, 0) > 0)
    assert swept == licensed


def test_the_contradiction_predicate_reads_the_real_route(gd: GameData) -> None:
    """The detector, both ways. It is stated over the ADAPTERS' outputs — a drain
    quantity and a routed Action — so a future drift in either is what makes it
    fire; restating the arithmetic would be a tautology."""
    deposit = DepositItemAction(code=SELL_CODE, quantity=1, bank_location=(4, 1))
    delete = DeleteItemAction(code=SELL_CODE, quantity=1)
    assert is_contradiction(1, deposit)
    assert not is_contradiction(0, deposit)
    assert not is_contradiction(1, delete)


def test_the_sweep_gives_each_code_its_own_bank(gd: GameData) -> None:
    """A bank carrying all 522 codes is over the bundle's 50-entry capacity, so
    `bank_has_room` would be False and every code would DELETE for lack of room
    — a green sweep that never reached the DEPOSIT arm."""
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    base = census_state(cell, gd)
    one = _single_code_bank(base, SELL_CODE)
    assert one.bank_items is not None and set(one.bank_items) == {SELL_CODE}
    assert bank_has_room(True, one.bank_items, gd.bank_capacity)
    crowded = {code: 1 for code in gd.all_item_stats}
    assert not bank_has_room(True, crowded, gd.bank_capacity)


def test_a_world_where_nothing_is_ever_deposited_is_refused(gd: GameData) -> None:
    """Anti-vacuity for the sweep's own premise: "nothing drained is deposited"
    is worthless if NOTHING is deposited. A locked/roomless bank is such a
    world, and the cell must refuse to be built in it."""
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    state = census_state(cell, gd)
    assert deposit_arm_is_live(state, gd)
    no_bank = _bankless(gd)
    assert not deposit_arm_is_live(state, no_bank)
    with pytest.raises(ValueError, match="vacuously true"):
        _check_cell(cell, state, no_bank)


# ── the cells cannot lie about themselves ────────────────────────────────────

def test_a_liveness_cell_with_no_licensed_work_raises(gd: GameData) -> None:
    empty = ShedCell(kind=ShedCellKind.DRAIN_SELECTABLE, bag={}, bank={})
    with pytest.raises(ValueError, match="cannot exhibit starvation"):
        _check_cell(empty, census_state(empty, gd), gd)


def test_a_quiet_cell_with_licensed_work_raises(gd: GameData) -> None:
    busy = ShedCell(kind=ShedCellKind.DRAIN_QUIET, bag={},
                    bank={SELL_CODE: 703}, must_be_selected=False)
    with pytest.raises(ValueError, match="must license NOTHING"):
        _check_cell(busy, census_state(busy, gd), gd)


def test_the_coherence_cell_is_exempt_from_the_licence_premise(gd: GameData) -> None:
    cell = scenario_for(ShedCellKind.ROUTE_COHERENCE, gd)
    _check_cell(cell, census_state(cell, gd), gd)  # must not raise


# ── world-limit gap classes ──────────────────────────────────────────────────

def _bankless(gd: GameData) -> GameData:
    clone = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    clone.world.bank_tile = None
    return clone


def test_a_map_with_no_bank_explains_the_drain_cell(gd: GameData) -> None:
    no_bank = _bankless(gd)
    cell = scenario_for(ShedCellKind.DRAIN_SELECTABLE, no_bank)
    state = census_state(cell, no_bank)
    assert classify_gap(cell, state, no_bank, False, 0) \
        is ShedGapClass.BANK_UNREACHABLE


def test_a_bankless_map_does_not_explain_the_recycle_cell(gd: GameData) -> None:
    """The recycle rung sheds from the BAG and needs no bank, so the bank arm of
    the classifier must not absorb its failure."""
    no_bank = _bankless(gd)
    cell = scenario_for(ShedCellKind.RECYCLE_SELECTABLE, no_bank)
    state = census_state(cell, no_bank)
    assert classify_gap(cell, state, no_bank, False, 0) \
        is ShedGapClass.SHED_STARVATION_BUG


def test_a_code_with_no_located_buyer_explains_the_sell_cell(gd: GameData) -> None:
    clone = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    # A merchant with NO tile at all: `npc_location` reads the static map scan
    # first and the event spawn table second, so both have to go.
    clone.world.npc_tiles = {}
    clone.world.event_npc_spawns = {}
    cell = scenario_for(ShedCellKind.SELL_SELECTABLE, clone)
    state = census_state(cell, clone)
    assert classify_gap(cell, state, clone, False, 0) \
        is ShedGapClass.NO_REACHABLE_BUYER


# ── the structural plan predicates ───────────────────────────────────────────

def _stub_withdraw(quantity: int = 1) -> WithdrawItemAction:
    return WithdrawItemAction(code=SELL_CODE, quantity=quantity,
                              bank_location=(0, 0))


def _stub_sale(quantity: int = 1) -> NpcSellAction:
    return NpcSellAction(npc_code="timber_merchant", item_code=SELL_CODE,
                         quantity=quantity, npc_location=(2, 4))


class _FakeGoal:
    def __init__(self, name: str) -> None:
        self._name = name

    def __repr__(self) -> str:
        return self._name


def test_staging_requires_the_withdraw_first() -> None:
    assert stages_withdraw_then_sale([_stub_withdraw(), _stub_sale()], SELL_CODE)
    assert not stages_withdraw_then_sale([_stub_sale(), _stub_withdraw()], SELL_CODE)
    assert not stages_withdraw_then_sale([_stub_withdraw()], SELL_CODE)
    assert not stages_withdraw_then_sale([_stub_sale()], SELL_CODE)


def test_sell_cell_fails_a_plan_that_only_withdraws(gd: GameData) -> None:
    """A withdraw with no sale is the DRAIN rung wearing a sell hat."""
    cell = scenario_for(ShedCellKind.SELL_SELECTABLE, gd)
    state = census_state(cell, gd)
    assert not shed_cell_verdict(cell, _FakeGoal("SellInventory"),
                                 [_stub_withdraw()], False, state, 0, 0)


def test_the_bag_bound_rejects_an_unbounded_episode(gd: GameData) -> None:
    """The per-cycle bound made structural: a plan that withdraws more than the
    bag's free quantity is the naive re-rank this epic refused to ship."""
    cell = scenario_for(ShedCellKind.DRAIN_SELECTABLE, gd)
    state = census_state(cell, gd)
    assert within_bag_bound([_stub_withdraw(state.inventory_free)], state)
    assert not within_bag_bound([_stub_withdraw(state.inventory_free + 1)], state)
    assert not within_bag_bound(
        [_stub_withdraw(state.inventory_free), _stub_withdraw(1)], state)
    assert not shed_cell_verdict(
        cell, _FakeGoal("DrainBankJunk"),
        [_stub_withdraw(state.inventory_free + 1)], False, state, 0, 0)


def test_licensed_work_reads_each_rung_own_authority(gd: GameData) -> None:
    for kind in (ShedCellKind.DRAIN_SELECTABLE, ShedCellKind.SELL_SELECTABLE,
                 ShedCellKind.RECYCLE_SELECTABLE):
        cell = scenario_for(kind, gd)
        assert licensed_work(cell, census_state(cell, gd), gd) > 0


def test_census_ctx_can_lock_the_bank() -> None:
    assert census_ctx().bank_accessible
    assert not census_ctx(bank_accessible=False).bank_accessible
