"""Inventory-completeness doc renderer (item-protection-authority epic,
Task 5): pure markdown from a list of CellResult plus a reason-coverage
table — no planner, no game data."""

from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_census import CellResult
from artifactsmmo_cli.audit.inventory_report import (
    GAP_ABBREV,
    band_summary,
    render_matrix,
    render_reason_coverage,
    summary_line,
)


def _pass(reason: str, cap: str, kind: str, pressure: str, code: str,
          held: int = 5, keep: int = 5, band: str = "in_band") -> CellResult:
    return CellResult(reason, cap, kind, pressure, band, code, held, keep, True, None)


def _fail(reason: str, cap: str, kind: str, pressure: str, code: str, gap: str,
          held: int = 11, keep: int = 5, band: str = "in_band") -> CellResult:
    return CellResult(reason, cap, kind, pressure, band, code, held, keep, False, gap)


_FULL_COVERAGE = {reason: True for reason in KeepReason}


def test_summary_line_counts_and_percentages() -> None:
    """SUMMARY reports cell totals, overall PASS%, and one count per gap
    class, keyed by the same GAP_ABBREV legend the matrix uses."""
    results = [
        _pass("currency", "in_bag", "safety", "slot_full", "tasks_coin"),
        _pass("equipped", "owned", "liveness", "qty_full", "copper_dagger"),
        _fail("working_kit", "in_bag", "liveness", "slot_full", "copper_axe",
              "inventory_bug"),
        _fail("recipe_demand", "owned", "liveness", "slot_full", "copper_bar",
              "no_route_available"),
    ]
    line = summary_line(results)
    assert "4 cells" in line
    assert "PASS 2 (50" in line
    assert "inventory_bug 1" in line
    assert "no_route_available 1" in line


def test_summary_line_empty_results_is_zero_not_crash() -> None:
    """summary_line over no cells reports zero without dividing by zero."""
    line = summary_line([])
    assert "0 cells" in line
    assert "PASS 0 (0%)" in line


def test_gap_abbrev_covers_every_inventory_gap_class() -> None:
    """GAP_ABBREV is the legend the matrix relies on — one short code per
    InventoryGapClass value."""
    from artifactsmmo_cli.audit.inventory_completeness import InventoryGapClass
    assert set(GAP_ABBREV) == {g.value for g in InventoryGapClass}
    assert GAP_ABBREV["inventory_bug"] == "IB"


def test_render_reason_coverage_marks_currency_exempt() -> None:
    """CURRENCY is annotated as the KEEP_ALL exemption; every other reason's
    row reports PASS/FAIL from the coverage dict verbatim."""
    coverage = dict(_FULL_COVERAGE)
    coverage[KeepReason.WORKING_KIT] = False
    md = render_reason_coverage(coverage)
    assert "| currency | PASS (KEEP_ALL exemption) |" in md
    assert "| working_kit | FAIL |" in md
    assert "| equipped | PASS |" in md


def test_render_matrix_groups_by_reason_kind_and_band() -> None:
    """Matrix has the generated header, one row per (reason, kind, BAND) with
    cap/pressure tokens, and the reason-coverage table appended. BAND is a row
    key so a reason's two level-distance halves sit side by side."""
    results = [
        _pass("currency", "in_bag", "safety", "slot_full", "tasks_coin"),
        _fail("working_kit", "in_bag", "liveness", "slot_full", "copper_axe",
              "inventory_bug"),
        _fail("working_kit", "in_bag", "liveness", "qty_full", "copper_axe",
              "inventory_bug"),
        _pass("working_kit", "in_bag", "liveness", "qty_full", "copper_axe",
              band="far"),
    ]
    coverage = dict(_FULL_COVERAGE)
    coverage[KeepReason.WORKING_KIT] = False
    md = render_matrix(results, coverage)
    assert "GENERATED — do not hand-edit" in md
    assert "| currency | safety | in_band | tasks_coin | in_bag/slot_full PASS |" in md
    assert "| working_kit | liveness | far | copper_axe | in_bag/qty_full PASS |" in md
    assert "in_bag/slot_full IB" in md
    assert "in_bag/qty_full IB" in md
    assert "## Reason coverage" in md
    assert "| working_kit | FAIL |" in md


def test_band_summary_splits_pass_counts_by_level_distance() -> None:
    """The band split is the headline diagnostic for the level-distance ceiling:
    a reason that passes IN_BAND and fails FAR is a protection being clamped by a
    HOARDING heuristic, which is exactly the defect the band dimension found."""
    results = [
        _pass("recipe_demand", "owned", "safety", "qty_full", "copper_bar"),
        _fail("recipe_demand", "owned", "safety", "qty_full", "copper_bar",
              "inventory_bug", band="far"),
        _pass("currency", "in_bag", "safety", "slot_full", "tasks_coin",
              band="far"),
    ]
    line = band_summary(results)
    assert line == ("by band: far 1/2 (inventory_bug 1); "
                    "in_band 1/1 (inventory_bug 0)")
    assert band_summary([]) == "by band: "


def test_cell_token_fail_branch_when_gap_is_none() -> None:
    """A hand-built CellResult with passed=False and gap=None cannot arise
    through run_cell (which always sets a gap on failure), but _cell_token
    must still be total over any CellResult: it renders the bare FAIL token."""
    results = [CellResult("mystery", "in_bag", "safety", "slot_full", "in_band",
                          "x", 5, 5, False, None)]
    md = render_matrix(results, dict(_FULL_COVERAGE))
    assert "in_bag/slot_full FAIL" in md
