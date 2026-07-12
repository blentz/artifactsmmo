"""Craft-completeness doc renderers (spec 2026-07-08 Phase 2): pure markdown
from a list of CellResult — no planner, no game data."""

from artifactsmmo_cli.audit.craft_census import CellResult
from artifactsmmo_cli.audit.craft_completeness import GapClass
from artifactsmmo_cli.audit.craft_report import (
    GAP_ABBREV,
    render_backlog,
    render_matrix,
    summary_line,
)


def _pass(recipe: str, skill: str, lvl: int, char: int, sk: int) -> CellResult:
    return CellResult(recipe, skill, lvl, char, sk, True, "", None)


def _fail(recipe: str, skill: str, lvl: int, char: int, sk: int,
          gap: str, reason: str = "empty") -> CellResult:
    return CellResult(recipe, skill, lvl, char, sk, False, reason, gap)


def test_gap_abbrev_exports_all_gap_classes() -> None:
    """GAP_ABBREV is the public code table Task 3 (and the matrix legend)
    depend on: every gap class has a short code."""
    assert set(GAP_ABBREV) == {g.value for g in GapClass}
    assert GAP_ABBREV["planner_bug"] == "PB"


def test_summary_line_counts_and_percentages() -> None:
    """SUMMARY reports recipe/cell totals, overall PASS%, the at-skill nominal
    PASS%, and one count per gap class."""
    results = [
        _pass("copper_bar", "mining", 1, 1, 1),      # nominal at-skill (1==nominal, 1==L)
        _pass("copper_bar", "mining", 1, 8, 1),
        _fail("iron_boots", "gearcrafting", 10, 10, 10, "planner_bug"),  # nominal at-skill
        _fail("iron_boots", "gearcrafting", 10, 8, 5, "combat_blocked"),
    ]
    line = summary_line(results)
    assert "2 recipes" in line
    assert "4 cells" in line
    assert "PASS 2 (50" in line          # 2/4 overall
    assert "nominal-at-skill PASS 1/2" in line  # copper_bar nominal passes, iron_boots nominal fails
    assert "planner_bug 1" in line
    assert "combat_blocked 1" in line


def test_summary_line_empty_results_is_zero_not_crash() -> None:
    """summary_line over no cells reports zeros without dividing by zero."""
    line = summary_line([])
    assert "0 recipes, 0 cells" in line
    assert "PASS 0 (0%)" in line


def test_render_matrix_groups_by_skill_and_tier() -> None:
    """Matrix has the generated-header, a per-(skill,tier) section, and one
    row per recipe with each cell rendered as char/skill + verdict."""
    results = [
        _pass("copper_bar", "mining", 1, 1, 1),
        _fail("copper_bar", "mining", 1, 12, 1, "planner_bug"),
        _pass("iron_bar", "mining", 10, 8, 5),
    ]
    md = render_matrix(results)
    assert "GENERATED — do not hand-edit" in md
    assert "## mining — tier 1" in md      # copper_bar (L1) and iron_bar (L10) both tier 1
    assert "1/1 PASS" in md
    assert "12/1 PB" in md
    assert "| copper_bar | 1 |" in md
    # iron_bar is craft_level 10 -> still tier 1 (decade-inclusive)
    assert "| iron_bar | 10 |" in md


def test_render_backlog_ranks_planner_bugs_most_broken_first() -> None:
    """Backlog ranks recipes by count of planner_bug cells desc; a recipe with
    2 bug cells outranks one with 1."""
    results = [
        _fail("recall_potion", "alchemy", 12, 1, 1, "planner_bug"),
        _fail("recall_potion", "alchemy", 12, 8, 1, "planner_bug"),
        _fail("air_ring", "jewelrycrafting", 20, 18, 15, "planner_bug"),
        _fail("iron_boots", "gearcrafting", 10, 8, 5, "combat_blocked"),  # not a bug
    ]
    md = render_backlog(results)
    assert "| 1 | recall_potion |" in md    # 2 bug cells -> rank 1
    assert "| 2 | air_ring |" in md          # 1 bug cell -> rank 2
    assert "iron_boots" not in md            # combat_blocked excluded from bug queue


def test_render_backlog_empty_when_no_planner_bugs() -> None:
    """When no cell is a planner_bug the backlog states the fix-queue is empty
    rather than emitting a header-only table."""
    results = [
        _pass("copper_bar", "mining", 1, 1, 1),
        _fail("iron_boots", "gearcrafting", 10, 8, 5, "combat_blocked"),
    ]
    md = render_backlog(results)
    assert "No PLANNER_BUG cells" in md
    assert "| Rank |" not in md


def test_cell_token_fail_branch_when_gap_is_none() -> None:
    """A hand-built CellResult with passed=False and gap=None cannot arise
    through run_cell (which always sets gap on failure), but _cell_token must
    still be total over any CellResult: it renders the bare FAIL token."""
    results = [CellResult("mystery_item", "mining", 1, 1, 1, False, "empty", None)]
    md = render_matrix(results)
    assert "1/1 FAIL" in md
