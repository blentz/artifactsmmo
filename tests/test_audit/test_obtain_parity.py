"""The obtain-model PARITY census (one-obtain-model epic, Task 7 — the ACCEPTANCE
gate). This is the census that makes the seven-inert-commits divergence bug
unshippable: the bot's two plan producers (the O(closure) descent and the A*
search) must AGREE about what is obtainable, or a cell classifies
`obtain_parity_bug` and CI fails.

Every cell drives the REAL `StrategyArbiter.select` seam over the committed
bundle — the seam at which `license_destructive_actions` runs. A harness that
planned through a lower seam would see the UNLICENSED factory pool and the RECYCLE
cell's POOL⊆MODEL check would fire on a recycle the keep authority forbade.
"""

import pytest

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.wait import WaitAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.wait import WaitGoal
from artifactsmmo_cli.ai.obtain_sources import SourceKind
from artifactsmmo_cli.audit import obtain_parity_completeness as opc
from artifactsmmo_cli.audit.obtain_parity_completeness import (
    ParityCell,
    ParityGapClass,
    ParityResult,
    ParitySourceKind,
    _assert_obtainable,
    _assert_reproduction_faithful,
    _check_goal,
    _check_premise,
    _kinds_without_withdraw,
    action_source_kind,
    action_yields,
    census_state,
    classify_gap,
    expected_goal_repr,
    model_kinds,
    parity_cell_verdict,
    parity_grid,
    plan_kinds,
    render_matrix,
    run_cell,
    run_census,
    scenario_for,
    summary_line,
)


def _cells(game_data: GameData) -> dict[ParitySourceKind, ParityCell]:
    return {cell.kind: cell for cell in parity_grid(game_data)}


def _result(game_data: GameData, kind: ParitySourceKind) -> ParityResult:
    return run_cell(_cells(game_data)[kind], game_data)


# ---------------------------------------------------------------------------
# The whole grid is clean, and every cell exercises its named route.
# ---------------------------------------------------------------------------

def test_the_whole_grid_is_clean(bundle_game_data: GameData) -> None:
    results = run_census(bundle_game_data)
    assert len(results) == len(ParitySourceKind)
    bugs = [r for r in results
            if r.gap == ParityGapClass.OBTAIN_PARITY_BUG.value]
    assert bugs == []
    assert all(r.passed for r in results)
    assert summary_line(results) == "6 cells; PASS 6; obtain_parity_bug 0"


def test_grid_is_total_over_the_kind_registry(bundle_game_data: GameData) -> None:
    kinds = {cell.kind for cell in parity_grid(bundle_game_data)}
    assert kinds == set(ParitySourceKind)


def test_gather_cell_both_producers_gather(bundle_game_data: GameData) -> None:
    r = _result(bundle_game_data, ParitySourceKind.GATHER)
    assert r.passed
    assert r.model_kinds == ("gather",)
    assert r.pool_applicable_kinds == ("gather",)
    assert r.descent_kinds == r.astar_kinds == ("gather",)


def test_craft_cell_both_producers_gather_then_craft(bundle_game_data: GameData) -> None:
    r = _result(bundle_game_data, ParitySourceKind.CRAFT)
    assert r.passed
    assert r.model_kinds == ("craft",)
    # CRAFT is inapplicable at t=0 (no inputs yet), so it is absent from the
    # applicable pool — POOL⊆MODEL holds trivially and MODEL⊆POOL holds on
    # existence.
    assert r.pool_applicable_kinds == ()
    assert r.descent_kinds == r.astar_kinds == ("craft", "gather")


def test_withdraw_carveout_cell_both_withdraw_the_banked_input(
        bundle_game_data: GameData) -> None:
    """The banked recipe INPUT (copper_ore) is served by the descent's OWN
    recipe-input withdraw, not a map WITHDRAW leg. Both producers emit
    Withdraw+Craft; after WITHDRAW is carved out, the compared kind-sets are
    {craft} == {craft}."""
    cell = _cells(bundle_game_data)[ParitySourceKind.WITHDRAW]
    state = census_state(cell, bundle_game_data)
    drive = opc._drive(cell, state, bundle_game_data)
    assert isinstance(drive.goal, GatherMaterialsGoal)
    plan = opc.descent_plan(drive.goal, drive.licensed, drive.ctx, state,
                            bundle_game_data)
    assert any(isinstance(a, WithdrawItemAction) and a.code == "copper_ore"
               for a in plan)
    r = run_cell(cell, bundle_game_data)
    assert r.passed
    assert r.descent_kinds == r.astar_kinds == ("craft",)


def test_recycle_cell_both_producers_recycle(bundle_game_data: GameData) -> None:
    r = _result(bundle_game_data, ParitySourceKind.RECYCLE)
    assert r.passed
    assert set(r.model_kinds) == {"craft", "recycle"}
    assert "recycle" in r.pool_applicable_kinds
    assert r.descent_kinds == r.astar_kinds == ("recycle",)


def test_buy_cell_both_producers_buy(bundle_game_data: GameData) -> None:
    r = _result(bundle_game_data, ParitySourceKind.BUY)
    assert r.passed
    assert r.model_kinds == ("buy",)
    assert r.descent_kinds == r.astar_kinds == ("buy",)


def test_drop_cell_both_producers_hunt(bundle_game_data: GameData) -> None:
    r = _result(bundle_game_data, ParitySourceKind.DROP)
    assert r.passed
    assert r.model_kinds == ("drop",)
    assert r.descent_kinds == r.astar_kinds == ("drop",)


# ---------------------------------------------------------------------------
# THE FALSIFIABILITY WITNESS — the carveout is NOT a hole.
# ---------------------------------------------------------------------------

def test_deleting_the_recycle_arm_turns_the_recycle_cell_red(
        bundle_game_data: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """THE required falsifiability proof (Task 7 brief). Delete the RECYCLE arm
    from the shared obtain model and the RECYCLE cell goes RED — on BOTH POOL⊆MODEL
    (the licensed pool still recycles, the model no longer names it) AND PLAN
    PARITY (the descent, robbed of the recycle source, RE-ROUTES to craft+gather
    while A* still recycles). That craft+gather-vs-recycle split IS the
    seven-inert-commits divergence this census exists to catch, and RECYCLE
    surviving the deletion PROVES the WITHDRAW carveout does not swallow it."""
    import artifactsmmo_cli.ai.obtain_sources as osmod
    monkeypatch.setattr(osmod, "_recycle_sources", lambda *a, **k: [])

    r = _result(bundle_game_data, ParitySourceKind.RECYCLE)
    assert not r.passed
    assert r.gap == ParityGapClass.OBTAIN_PARITY_BUG.value
    assert r.pool_subset_model is False
    assert r.plan_parity is False
    assert r.model_kinds == ("craft",)
    assert "recycle" in r.pool_applicable_kinds
    assert "recycle" in r.astar_kinds
    assert "recycle" not in r.descent_kinds


def test_deleting_the_gather_arm_turns_the_gather_cell_red(
        bundle_game_data: GameData, monkeypatch: pytest.MonkeyPatch) -> None:
    """A SECOND witness, biting a different check arm and a different kind: delete
    the GATHER arm and the GATHER cell fails POOL⊆MODEL — the applicable pool still
    gathers copper_ore, the model no longer names GATHER. (The descent gathers via
    `game_data.gatherable_drop_items`, not the source map, so PLAN PARITY still
    holds — proving POOL⊆MODEL bites independently.)"""
    import artifactsmmo_cli.ai.obtain_sources as osmod
    monkeypatch.setattr(osmod, "_gather_sources", lambda *a, **k: [])

    r = _result(bundle_game_data, ParitySourceKind.GATHER)
    assert not r.passed
    assert r.pool_subset_model is False
    assert r.plan_parity is True
    assert r.model_kinds == ()
    assert r.pool_applicable_kinds == ("gather",)


# ---------------------------------------------------------------------------
# A planner timeout is a BUG, never an explained gap.
# ---------------------------------------------------------------------------

def test_planner_timeout_is_a_bug_before_any_other_arm(
        bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[ParitySourceKind.GATHER]
    state = census_state(cell, bundle_game_data)
    assert classify_gap(cell, state, bundle_game_data, planner_failed=True) \
        is ParityGapClass.OBTAIN_PARITY_BUG


def test_a_conclusive_disagreement_is_the_same_residual(
        bundle_game_data: GameData) -> None:
    """There are no world-limit arms — a parity disagreement is never explained —
    so a conclusive FAIL falls through to the same residual class."""
    cell = _cells(bundle_game_data)[ParitySourceKind.GATHER]
    state = census_state(cell, bundle_game_data)
    assert classify_gap(cell, state, bundle_game_data, planner_failed=False) \
        is ParityGapClass.OBTAIN_PARITY_BUG


def test_a_timed_out_search_fails_the_verdict_before_any_check(
        bundle_game_data: GameData) -> None:
    """An inconclusive search proves nothing: a cell that "passed" because A*
    timed out (and so planned no divergence) would be pure laundering."""
    assert parity_cell_verdict(True, True, True, planner_failed=True) is False


def test_verdict_needs_all_three_checks(bundle_game_data: GameData) -> None:
    assert parity_cell_verdict(True, True, True, planner_failed=False) is True
    assert parity_cell_verdict(False, True, True, planner_failed=False) is False
    assert parity_cell_verdict(True, False, True, planner_failed=False) is False
    assert parity_cell_verdict(True, True, False, planner_failed=False) is False


# ---------------------------------------------------------------------------
# The action <-> source-kind vocabulary bridge.
# ---------------------------------------------------------------------------

def test_action_source_kind_maps_every_obtain_action() -> None:
    assert action_source_kind(
        WithdrawItemAction(code="copper_ore", quantity=1)) is SourceKind.WITHDRAW
    assert action_source_kind(
        RecycleAction(code="water_bow", quantity=1,
                      workshop_location=(1, 1))) is SourceKind.RECYCLE
    assert action_source_kind(CraftAction(code="copper_bar")) is SourceKind.CRAFT
    assert action_source_kind(
        GatherAction(resource_code="copper_rocks")) is SourceKind.GATHER
    assert action_source_kind(
        NpcBuyAction(npc_code="tailor", item_code="cloth")) is SourceKind.BUY
    assert action_source_kind(
        FightAction(monster_code="chicken")) is SourceKind.DROP
    # A scaffolding leg obtains nothing.
    assert action_source_kind(WaitAction()) is None


def test_action_yields_uses_the_per_kind_target_relation(
        bundle_game_data: GameData) -> None:
    gd = bundle_game_data
    assert action_yields(GatherAction(resource_code="copper_rocks"),
                         "copper_ore", gd)
    assert action_yields(CraftAction(code="copper_bar"), "copper_bar", gd)
    assert action_yields(WithdrawItemAction(code="copper_ore", quantity=1),
                         "copper_ore", gd)
    # Recycling water_bow yields its recipe ingredient ash_plank.
    assert action_yields(RecycleAction(code="water_bow", quantity=1,
                                       workshop_location=(1, 1)), "ash_plank", gd)
    assert action_yields(NpcBuyAction(npc_code="tailor", item_code="cloth"),
                         "cloth", gd)
    assert action_yields(FightAction(monster_code="chicken"), "feather", gd)
    # Non-matches and a non-obtain action yield nothing.
    assert not action_yields(GatherAction(resource_code="copper_rocks"),
                             "iron_ore", gd)
    assert not action_yields(WaitAction(), "copper_ore", gd)


def test_kinds_without_withdraw_is_the_narrow_carveout() -> None:
    assert _kinds_without_withdraw(
        {SourceKind.WITHDRAW, SourceKind.RECYCLE, SourceKind.CRAFT}
    ) == frozenset({SourceKind.RECYCLE, SourceKind.CRAFT})
    assert _kinds_without_withdraw({SourceKind.WITHDRAW}) == frozenset()


def test_plan_kinds_drops_withdraw_and_scaffolding() -> None:
    plan = [
        WithdrawItemAction(code="copper_ore", quantity=1),
        CraftAction(code="copper_bar"),
        WaitAction(),
    ]
    assert plan_kinds(plan) == frozenset({SourceKind.CRAFT})


def test_model_kinds_carves_out_withdraw(bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[ParitySourceKind.WITHDRAW]
    state = census_state(cell, bundle_game_data)
    drive = opc._drive(cell, state, bundle_game_data)
    # copper_ore is banked here, so obtain_sources names WITHDRAW + GATHER; the
    # carveout drops WITHDRAW.
    kinds = model_kinds("copper_ore", state, bundle_game_data, drive.ctx)
    assert SourceKind.WITHDRAW not in kinds
    assert SourceKind.GATHER in kinds


# ---------------------------------------------------------------------------
# Cell / grid construction: a cell that does not test what it names RAISES.
# ---------------------------------------------------------------------------

def _thin_gd() -> GameData:
    """A real (empty-catalog) GameData — `scenario_for` must fail loud on it
    rather than synthesize a cell from data the game does not have."""
    return GameData()


def test_scenario_for_rejects_an_unregistered_kind(
        bundle_game_data: GameData) -> None:
    with pytest.raises(ValueError, match="no census scenario"):
        scenario_for("not_a_kind", bundle_game_data)  # type: ignore[arg-type]


def test_missing_catalog_item_fails_loud() -> None:
    with pytest.raises(ValueError, match="not in the game catalog"):
        scenario_for(ParitySourceKind.GATHER, _thin_gd())


def test_a_cell_that_already_holds_the_material_is_vacuous(
        bundle_game_data: GameData) -> None:
    cell = ParityCell(kind=ParitySourceKind.GATHER, material="copper_ore",
                      needed=5, bag={"copper_ore": 1}, bank={})
    state = census_state(cell, bundle_game_data)
    with pytest.raises(ValueError, match="the goal is satisfied"):
        _check_premise(cell, state)


def test_check_goal_rejects_a_none_or_mismatched_goal(
        bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[ParitySourceKind.GATHER]
    with pytest.raises(ValueError, match="the arbiter ran"):
        _check_goal(cell, None)
    with pytest.raises(ValueError, match="the arbiter ran"):
        _check_goal(cell, WaitGoal())


def test_check_goal_accepts_the_expected_step(bundle_game_data: GameData) -> None:
    cell = _cells(bundle_game_data)[ParitySourceKind.GATHER]
    goal = GatherMaterialsGoal(target_item=cell.material,
                               needed={cell.material: cell.needed})
    assert repr(goal) == expected_goal_repr(cell)
    _check_goal(cell, goal)  # does not raise


# ---------------------------------------------------------------------------
# The two integrity guards (extracted so they are directly falsifiable).
# ---------------------------------------------------------------------------

def test_reproduction_faithful_guard() -> None:
    gather = GatherAction(resource_code="copper_rocks")
    craft = CraftAction(code="copper_bar")
    # Equal plans, and an empty descent, both pass.
    _assert_reproduction_faithful("gather", [gather], [gather])
    _assert_reproduction_faithful("gather", [], [craft])
    # A non-empty descent that differs from what the arbiter returned means the
    # census's licensed-pool reproduction has drifted.
    with pytest.raises(ValueError, match="reproduction has drifted"):
        _assert_reproduction_faithful("gather", [gather], [craft])


def test_obtainable_guard() -> None:
    gather = GatherAction(resource_code="copper_rocks")
    # At least one producer serves -> ok. A timed-out both-empty -> ok (the
    # timeout is the story, classified elsewhere).
    _assert_obtainable("gather", "copper_ore", [gather], [], planner_failed=False)
    _assert_obtainable("gather", "copper_ore", [], [], planner_failed=True)
    # A CONCLUSIVE both-empty is a vacuous cell (the bundle changed under it).
    with pytest.raises(ValueError, match="neither producer can serve"):
        _assert_obtainable("gather", "copper_ore", [], [], planner_failed=False)


# ---------------------------------------------------------------------------
# Rendering.
# ---------------------------------------------------------------------------

def test_render_matrix_shows_pass_and_bug_rows() -> None:
    passed = ParityResult(
        kind="gather", material="copper_ore", needed=5,
        model_kinds=("gather",), pool_applicable_kinds=("gather",),
        descent_kinds=("gather",), astar_kinds=("gather",),
        pool_subset_model=True, model_subset_pool=True, plan_parity=True,
        planner_failed=False, goal="GatherMaterials(copper_ore, {copper_ore:5})",
        passed=True, gap=None)
    bug = ParityResult(
        kind="recycle", material="ash_plank", needed=4,
        model_kinds=(), pool_applicable_kinds=("recycle",),
        descent_kinds=(), astar_kinds=("recycle",),
        pool_subset_model=False, model_subset_pool=True, plan_parity=False,
        planner_failed=False, goal="GatherMaterials(ash_plank, {ash_plank:4})",
        passed=False, gap=ParityGapClass.OBTAIN_PARITY_BUG.value)
    text = render_matrix([passed, bug])
    assert "| PASS |" in text
    assert f"**{ParityGapClass.OBTAIN_PARITY_BUG.value}**" in text
    # The empty-kind cell renders the "·" placeholder, the populated one a CSV.
    assert "| · |" in text
    assert "gather" in text and "recycle" in text
    assert summary_line([passed, bug]) == "2 cells; PASS 1; obtain_parity_bug 1"
