# Craft-Completeness Phase 2 — Generator + Docs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Run the Phase-1 census over all 321 craftable recipes / 1758 grid cells on the committed bundle and render `docs/craft_completeness/MATRIX.md` + `BACKLOG.md` + a SUMMARY line, so every recipe's planning status (PASS / gap-class) is enumerated and the PLANNER_BUG fix-queue is a committed, regenerable doc.

**Architecture:** Two new PURE-logic `src/` modules (`craft_census.py` = census engine that drives the Phase-1 cores per cell; `craft_report.py` = deterministic markdown renderers), plus a thin orchestration script (`scripts/gen_craft_completeness.py`) that loads the bundle, runs the census with a progress log, renders, and writes the docs. All decision logic stays in the tested `src/` cores; the script is glue. The census loads the committed offline bundle (no live API), so a regen is deterministic except for the ~16% of cells whose plan hits the 10 s wall-clock budget (documented in the generated header).

**Tech Stack:** Python 3.13, `uv`, pytest (100% coverage on `src/`), mypy strict on `src/`. Reuses `artifactsmmo_cli.audit.craft_completeness` Phase-1 cores.

## Global Constraints

- `uv run` prefix on ALL python/pytest/mypy commands (e.g. `uv run pytest`).
- No inline imports — all imports top-of-file. NEVER catch `Exception`. No `if TYPE_CHECKING`. No `...` (triple-dot) imports.
- ONE behavioral class per file; cohesive pure-data dataclasses may share a module (matches Phase-1 `craft_completeness.py`, which mixes frozen dataclasses + module functions).
- Use only API/bundle data or fail with an error — no silent defaulting.
- 100% test coverage and mypy-strict clean on everything under `src/artifactsmmo_cli/`. `scripts/` is OUTSIDE the coverage + mypy gate (pyproject `--cov=src/artifactsmmo_cli`; pre-commit runs `mypy src/`), so keep the script pure glue with all logic in the tested `src/` modules.
- TDD: failing test first, watch it fail, minimal code, watch it pass, commit.
- Commit with `--no-verify` is acceptable when the full pre-commit suite exceeds the tool time budget; document it in the report and rely on targeted `uv run pytest <files>` + module-100% + `uv run mypy src/...` as the evidence.
- Bundle path (offline census source): `tests/test_ai/scenarios/fixtures/gamedata_bundle.json`, loaded via `GameData.from_cache_bundle(json.loads(path.read_text()))`.
- Phase-1 core public API (consume verbatim, do NOT modify):
  - `CraftCell(char_level: int, skill_name: str, skill_level: int)` (frozen)
  - `craft_grid(recipe: str, game_data: GameData) -> list[CraftCell]`
  - `census_state(cell: CraftCell, game_data: GameData) -> WorldState`
  - `plan_craft(recipe: str, state: WorldState, game_data: GameData) -> list[Action]`
  - `craft_cell_verdict(recipe: str, plan: list[Action], game_data: GameData) -> CraftVerdict` where `CraftVerdict` is frozen with `.passed: bool` and `.reason: str` (`""` on pass; else `"empty" | "wait" | "unrelated:<repr(plan[0])>"`)
  - `classify_gap(recipe: str, cell: CraftCell, game_data: GameData) -> GapClass` where `GapClass` is an `Enum` with `.value` in `{"event_gated","combat_blocked","material_unreachable","skill_unreachable","planner_bug"}`
- `GameData` accessors used: `game_data.all_item_stats: Mapping[str, ItemStats]`; `game_data.item_stats(code) -> ItemStats | None` with `.crafting_skill: str` and `.crafting_level: int`; `game_data.crafting_recipe(code) -> dict | None`.
- Tier of a recipe: `T = (craft_level - 1) // 10 + 1`. Nominal char level for a recipe: `1 if craft_level <= 9 else 10 * T`.
- Out of scope (Phase 3, separate plan): the pinned CI regression subset (`tests/test_ai/scenarios/test_craft_completeness.py`) and the `plan --craft` CLI mode. Do NOT build them here.

---

### Task 1: Census engine — `CellResult` + `run_cell` + `craftable_recipes` + `run_census`

**Files:**
- Create: `src/artifactsmmo_cli/audit/craft_census.py`
- Test: `tests/test_audit/test_craft_census.py`

**Interfaces:**
- Consumes (Phase-1): `CraftCell`, `craft_grid`, `census_state`, `plan_craft`, `craft_cell_verdict`, `classify_gap` from `artifactsmmo_cli.audit.craft_completeness`; `GameData` from `artifactsmmo_cli.ai.game_data`.
- Produces (for Tasks 2-3):
  - `CellResult` frozen dataclass with fields `recipe: str`, `skill: str`, `craft_level: int`, `char_level: int`, `skill_level: int`, `passed: bool`, `reason: str`, `gap: str | None`.
  - `run_cell(recipe: str, cell: CraftCell, game_data: GameData) -> CellResult`
  - `craftable_recipes(game_data: GameData) -> list[str]` (sorted by skill, craft_level, code)
  - `run_census(game_data: GameData, recipes: list[str], progress: Callable[[int, int, str], None] | None = None) -> list[CellResult]` — `recipes` is REQUIRED (the script computes `craftable_recipes(gd)` and passes it). A `None` default would make the full 321-recipe census the only way to exercise the default branch (~50 min) — untestable cheaply — so the branch is removed by design.

- [ ] **Step 1: Write the failing test for `run_cell` on a passing cell**

Add to `tests/test_audit/test_craft_census.py`:

```python
"""Craft-completeness census engine (spec 2026-07-08 Phase 2): drives the
Phase-1 pure cores over every recipe cell and records a flat CellResult."""

import json
from collections.abc import Callable
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_completeness import CraftCell
from artifactsmmo_cli.audit.craft_census import (
    CellResult,
    craftable_recipes,
    run_cell,
    run_census,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


def _gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_run_cell_records_a_passing_smelt() -> None:
    """copper_bar (mining 1) at a plausibly-geared L5/mining-5 cell plans a
    real first leg, so the CellResult passes with no gap and carries the
    recipe's craft metadata."""
    gd = _gd()
    cell = CraftCell(char_level=5, skill_name="mining", skill_level=5)
    result = run_cell("copper_bar", cell, gd)
    assert result.recipe == "copper_bar"
    assert result.skill == "mining"
    assert result.craft_level == 1
    assert result.char_level == 5
    assert result.skill_level == 5
    assert result.passed is True
    assert result.reason == ""
    assert result.gap is None
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_audit/test_craft_census.py::test_run_cell_records_a_passing_smelt -v --no-cov`
Expected: FAIL — `ModuleNotFoundError: No module named 'artifactsmmo_cli.audit.craft_census'`.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/audit/craft_census.py`:

```python
"""Craft-completeness census engine (spec 2026-07-08 Phase 2). Drives the
Phase-1 pure cores (census_state -> plan_craft -> craft_cell_verdict ->
classify_gap) over every craftable recipe's grid cells and records a flat,
render-ready CellResult per cell. No decision logic lives here — it is the
orchestration layer between the proven cores and the doc renderers."""

from collections.abc import Callable
from dataclasses import dataclass

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell,
    census_state,
    classify_gap,
    craft_cell_verdict,
    craft_grid,
    plan_craft,
)


@dataclass(frozen=True)
class CellResult:
    """One census outcome: a recipe attempted at one (char_level, skill_level)
    cell. `passed`/`reason` mirror the CraftVerdict; `gap` is the GapClass
    value string on failure (None on pass)."""

    recipe: str
    skill: str
    craft_level: int
    char_level: int
    skill_level: int
    passed: bool
    reason: str
    gap: str | None


def run_cell(recipe: str, cell: CraftCell, game_data: GameData) -> CellResult:
    """Drive the Phase-1 cores for one recipe/cell and record the outcome.
    The recipe's craft_level is read from game data (used only for grouping/
    tier in the renderers)."""
    stats = game_data.item_stats(recipe)
    if stats is None or not stats.crafting_skill:
        raise ValueError(f"{recipe} is not a craftable recipe")
    state = census_state(cell, game_data)
    plan = plan_craft(recipe, state, game_data)
    verdict = craft_cell_verdict(recipe, plan, game_data)
    gap = None if verdict.passed else classify_gap(recipe, cell, game_data).value
    return CellResult(
        recipe=recipe,
        skill=cell.skill_name,
        craft_level=stats.crafting_level,
        char_level=cell.char_level,
        skill_level=cell.skill_level,
        passed=verdict.passed,
        reason=verdict.reason,
        gap=gap,
    )


def craftable_recipes(game_data: GameData) -> list[str]:
    """Every item with a non-empty crafting recipe, sorted deterministically
    by (craft skill, craft level, code)."""
    out: list[str] = []
    for code, stats in game_data.all_item_stats.items():
        if stats.crafting_skill and game_data.crafting_recipe(code):
            out.append(code)
    return sorted(
        out,
        key=lambda c: (
            game_data.item_stats(c).crafting_skill,  # type: ignore[union-attr]
            game_data.item_stats(c).crafting_level,  # type: ignore[union-attr]
            c,
        ),
    )


def run_census(
    game_data: GameData,
    recipes: list[str],
    progress: Callable[[int, int, str], None] | None = None,
) -> list[CellResult]:
    """Run the census over `recipes`: for each, every grid cell. The caller
    supplies the recipe list (the generator passes `craftable_recipes(gd)`;
    tests pass a tiny explicit list). `progress(done, total, recipe)` is called
    after each recipe if supplied."""
    results: list[CellResult] = []
    for i, recipe in enumerate(recipes):
        for cell in craft_grid(recipe, game_data):
            results.append(run_cell(recipe, cell, game_data))
        if progress is not None:
            progress(i + 1, len(recipes), recipe)
    return results
```

Note the `# type: ignore[union-attr]` on the sort key: `item_stats` returns `ItemStats | None`, but `craftable_recipes` only appends codes whose `item_stats` is non-None with a truthy `crafting_skill`, so the sort-key access is safe. mypy cannot narrow across the loop boundary; the ignore is the honest minimal annotation. If mypy strict rejects the specific ignore code, run `uv run mypy src/artifactsmmo_cli/audit/craft_census.py` and use the exact error code it reports.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/test_audit/test_craft_census.py::test_run_cell_records_a_passing_smelt -v --no-cov`
Expected: PASS.

- [ ] **Step 5: Write the failing test for a failing cell (gap recorded)**

Add to `tests/test_audit/test_craft_census.py`:

```python
def test_run_cell_records_gap_on_failure() -> None:
    """A recipe that cannot plan at its cell records passed=False, a non-empty
    reason, and a gap-class string. iron_boots at a low under-skill cell is a
    known non-planner (10s-budget empty plan in the scout); assert the shape
    of a FAIL rather than a specific gap class."""
    gd = _gd()
    cell = CraftCell(char_level=8, skill_name="gearcrafting", skill_level=5)
    result = run_cell("iron_boots", cell, gd)
    if result.passed:
        assert result.gap is None and result.reason == ""
    else:
        assert result.gap in {
            "event_gated", "combat_blocked", "material_unreachable",
            "skill_unreachable", "planner_bug",
        }
        assert result.reason != ""
```

- [ ] **Step 6: Run it — verify it passes** (the implementation from Step 3 already covers both branches)

Run: `uv run pytest tests/test_audit/test_craft_census.py::test_run_cell_records_gap_on_failure -v --no-cov`
Expected: PASS.

- [ ] **Step 7: Write the failing test for `craftable_recipes` + `run_census` (restricted list + progress callback)**

Add to `tests/test_audit/test_craft_census.py`:

```python
def test_craftable_recipes_sorted_and_nonempty() -> None:
    """The census enumerates the game's craftables, sorted by (skill, level,
    code), and only includes items that actually have a crafting recipe."""
    gd = _gd()
    recipes = craftable_recipes(gd)
    assert "copper_bar" in recipes
    assert "copper_ore" not in recipes  # raw gather, not craftable
    keys = [
        (gd.item_stats(c).crafting_skill, gd.item_stats(c).crafting_level, c)
        for c in recipes
    ]
    assert keys == sorted(keys)


def test_run_census_restricted_list_with_progress() -> None:
    """run_census over an explicit one-recipe list yields one CellResult per
    grid cell and fires the progress callback once per recipe."""
    gd = _gd()
    seen: list[tuple[int, int, str]] = []

    def progress(done: int, total: int, recipe: str) -> None:
        seen.append((done, total, recipe))

    results = run_census(gd, ["copper_bar"], progress=progress)
    expected_cells = 3  # copper_bar: char {1,8,12} x skill {1} (collapsed)
    assert len(results) == expected_cells
    assert all(isinstance(r, CellResult) for r in results)
    assert all(r.recipe == "copper_bar" for r in results)
    assert seen == [(1, 1, "copper_bar")]


def test_run_census_multiple_recipes_no_progress() -> None:
    """run_census over an explicit multi-recipe list with NO progress callback
    (covers the progress-None branch) reaches every requested recipe."""
    gd = _gd()
    results = run_census(gd, ["copper_bar", "copper_helmet"])
    recipes_in = {r.recipe for r in results}
    assert recipes_in == {"copper_bar", "copper_helmet"}
```

- [ ] **Step 8: Run the new tests — verify they pass**

Run: `uv run pytest tests/test_audit/test_craft_census.py -v --no-cov`
Expected: all PASS. If `expected_cells` for copper_bar differs, correct it to `len(craft_grid("copper_bar", gd))` — do not guess; read the actual grid.

- [ ] **Step 9: Verify module coverage 100% + mypy + ruff**

Run:
```
uv run pytest tests/test_audit/test_craft_census.py --cov=artifactsmmo_cli.audit.craft_census --cov-report=term-missing -q 2>&1 | grep -i "craft_census\|TOTAL"
uv run mypy src/artifactsmmo_cli/audit/craft_census.py
uv run ruff check src/artifactsmmo_cli/audit/craft_census.py tests/test_audit/test_craft_census.py
```
Expected: `craft_census.py` 100%; mypy `Success`; ruff `All checks passed!`.

- [ ] **Step 10: Commit**

```bash
git add src/artifactsmmo_cli/audit/craft_census.py tests/test_audit/test_craft_census.py
git commit --no-verify -m "feat(audit): craft_census engine — CellResult + run_cell/run_census"
```

---

### Task 2: Deterministic markdown renderers — `craft_report.py`

**Files:**
- Create: `src/artifactsmmo_cli/audit/craft_report.py`
- Test: `tests/test_audit/test_craft_report.py`

**Interfaces:**
- Consumes: `CellResult` from `artifactsmmo_cli.audit.craft_census`.
- Produces (for Task 3):
  - `GAP_ABBREV: dict[str, str]` mapping gap-class value → short code.
  - `summary_line(results: list[CellResult]) -> str`
  - `render_matrix(results: list[CellResult]) -> str`
  - `render_backlog(results: list[CellResult]) -> str`

These are PURE functions over `CellResult` lists — no planner, no game data, no I/O. Fully unit-testable with hand-built results.

- [ ] **Step 1: Write the failing test for `summary_line`**

Create `tests/test_audit/test_craft_report.py`:

```python
"""Craft-completeness doc renderers (spec 2026-07-08 Phase 2): pure markdown
from a list of CellResult — no planner, no game data."""

from artifactsmmo_cli.audit.craft_census import CellResult
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
```

- [ ] **Step 2: Run it — verify it fails**

Run: `uv run pytest tests/test_audit/test_craft_report.py::test_summary_line_counts_and_percentages -v --no-cov`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

Create `src/artifactsmmo_cli/audit/craft_report.py`:

```python
"""Craft-completeness doc renderers (spec 2026-07-08 Phase 2). Pure markdown
over a list of CellResult: the recipe x cell PASS/gap MATRIX, the ranked
PLANNER_BUG BACKLOG, and a one-line SUMMARY metric. No planner, no game data,
no I/O — the generator script owns file writes and the census run."""

from collections import defaultdict

from artifactsmmo_cli.audit.craft_census import CellResult

GAP_ABBREV: dict[str, str] = {
    "event_gated": "EG",
    "combat_blocked": "CB",
    "material_unreachable": "MU",
    "skill_unreachable": "SU",
    "planner_bug": "PB",
}

_GENERATED_HEADER = (
    "> GENERATED — do not hand-edit. Regenerate with "
    "`uv run python scripts/gen_craft_completeness.py`.\n>\n"
    "> Census drives the REAL planner over the committed bundle. Cells whose "
    "plan hits the 10 s wall-clock budget (~16% of cells) can vary between "
    "regens; treat their verdict as approximate.\n"
)


def _tier(craft_level: int) -> int:
    return (craft_level - 1) // 10 + 1


def _nominal(craft_level: int) -> int:
    return 1 if craft_level <= 9 else 10 * _tier(craft_level)


def _cell_token(r: CellResult) -> str:
    verdict = "PASS" if r.passed else GAP_ABBREV[r.gap] if r.gap else "FAIL"
    return f"{r.char_level}/{r.skill_level} {verdict}"


def summary_line(results: list[CellResult]) -> str:
    """One-line completeness metric: recipe/cell totals, overall PASS%, the
    at-skill nominal PASS ratio (the realistic cell per recipe), and per-gap
    counts."""
    recipes = {r.recipe for r in results}
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    nominal_cells = [
        r for r in results
        if r.char_level == _nominal(r.craft_level) and r.skill_level == r.craft_level
    ]
    nominal_pass = sum(1 for r in nominal_cells if r.passed)
    pct = 100 * passed / total if total else 0.0
    gap_counts = {v: 0 for v in GAP_ABBREV}
    for r in results:
        if r.gap is not None:
            gap_counts[r.gap] += 1
    gaps = ", ".join(f"{k} {gap_counts[k]}" for k in GAP_ABBREV)
    return (
        f"{len(recipes)} recipes, {total} cells; "
        f"PASS {passed} ({pct:.0f}%); "
        f"nominal-at-skill PASS {nominal_pass}/{len(nominal_cells)}; "
        f"gaps: {gaps}"
    )


def render_matrix(results: list[CellResult]) -> str:
    """The recipe x cell MATRIX, grouped by (craft skill, tier). One row per
    recipe: its craft level and each cell's char/skill -> PASS or gap abbrev."""
    groups: dict[tuple[str, int], list[str]] = defaultdict(list)
    by_recipe: dict[str, list[CellResult]] = defaultdict(list)
    for r in results:
        by_recipe[r.recipe].append(r)
    for recipe in sorted(by_recipe):
        cells = sorted(by_recipe[recipe], key=lambda r: (r.char_level, r.skill_level))
        head = cells[0]
        tokens = " · ".join(_cell_token(c) for c in cells)
        row = f"| {recipe} | {head.craft_level} | {tokens} |"
        groups[(head.skill, _tier(head.craft_level))].append(row)
    lines = [
        "# Craft-Planning Completeness — Matrix",
        "",
        _GENERATED_HEADER,
        "",
        summary_line(results),
        "",
        "Legend: " + ", ".join(f"{v}={k}" for k, v in GAP_ABBREV.items()) + ".",
        "",
    ]
    for skill, tier in sorted(groups):
        lines.append(f"## {skill} — tier {tier}")
        lines.append("")
        lines.append("| Recipe | Craft lvl | Cells (char/skill → verdict) |")
        lines.append("|---|---|---|")
        lines.extend(groups[(skill, tier)])
        lines.append("")
    return "\n".join(lines) + "\n"


def render_backlog(results: list[CellResult]) -> str:
    """The ranked PLANNER_BUG fix-queue: recipes with one or more planner_bug
    cells, ranked by count of such cells (desc), then craft level (asc), then
    code. Each row lists the failing cells and a representative reason."""
    bugs: dict[str, list[CellResult]] = defaultdict(list)
    for r in results:
        if r.gap == "planner_bug":
            bugs[r.recipe].append(r)
    ranked = sorted(
        bugs.items(),
        key=lambda kv: (-len(kv[1]), kv[1][0].craft_level, kv[0]),
    )
    lines = [
        "# Craft-Planning Completeness — PLANNER_BUG Backlog",
        "",
        _GENERATED_HEADER,
        "",
        summary_line(results),
        "",
    ]
    if not ranked:
        lines.append("No PLANNER_BUG cells — every FAIL is a game limit "
                     "(combat/event/material/skill). The planner produces a "
                     "directional plan for every reachable recipe cell.")
        return "\n".join(lines) + "\n"
    lines.append("| Rank | Recipe | Skill | Craft lvl | # bug cells | Cells | Reason |")
    lines.append("|---|---|---|---|---|---|---|")
    for rank, (recipe, cells) in enumerate(ranked, start=1):
        ordered = sorted(cells, key=lambda r: (r.char_level, r.skill_level))
        head = ordered[0]
        cell_list = ", ".join(f"{c.char_level}/{c.skill_level}" for c in ordered)
        lines.append(
            f"| {rank} | {recipe} | {head.skill} | {head.craft_level} | "
            f"{len(ordered)} | {cell_list} | {head.reason} |"
        )
    return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run the summary test — verify it passes**

Run: `uv run pytest tests/test_audit/test_craft_report.py::test_summary_line_counts_and_percentages -v --no-cov`
Expected: PASS. (If the exact substring assertions miss due to rounding/format, adjust the TEST strings to the real output — the format is the source of truth — but keep every distinct fact asserted.)

- [ ] **Step 5: Write the failing tests for `render_matrix` and `render_backlog`**

Add to `tests/test_audit/test_craft_report.py`:

```python
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
```

- [ ] **Step 6: Run them — verify they pass**

Run: `uv run pytest tests/test_audit/test_craft_report.py -v --no-cov`
Expected: all PASS. Adjust test literal strings to the real rendered format where needed (format is source of truth), but keep each behavior asserted.

- [ ] **Step 7: Verify module coverage 100% + mypy + ruff**

Run:
```
uv run pytest tests/test_audit/test_craft_report.py --cov=artifactsmmo_cli.audit.craft_report --cov-report=term-missing -q 2>&1 | grep -i "craft_report\|TOTAL"
uv run mypy src/artifactsmmo_cli/audit/craft_report.py
uv run ruff check src/artifactsmmo_cli/audit/craft_report.py tests/test_audit/test_craft_report.py
```
Expected: `craft_report.py` 100% (add a targeted test for any uncovered branch — e.g. a `FAIL`-token result where `passed=False` and `gap is None`, which `_cell_token` renders as `FAIL`; if that branch is unreachable in practice, cover it with an explicit `_fail(..., gap=None)` case or drop the branch and let `gap` be assumed non-None on fail — do NOT leave dead code); mypy `Success`; ruff clean.

Note on the `_cell_token` `FAIL` branch: a failing CellResult always carries a gap in the real census (`run_cell` sets `gap` whenever `not passed`), so `gap is None` on a failing cell cannot occur through `run_cell`. Either (a) cover it with a hand-built `CellResult(..., passed=False, reason="empty", gap=None)` unit test asserting the token is `"... FAIL"`, or (b) simplify `_cell_token` to `GAP_ABBREV[r.gap]` on the else-branch and assert in a test that `run_cell` never yields `passed=False, gap=None`. Pick (a) — it keeps the renderer total over any CellResult and is a one-line test.

- [ ] **Step 8: Commit**

```bash
git add src/artifactsmmo_cli/audit/craft_report.py tests/test_audit/test_craft_report.py
git commit --no-verify -m "feat(audit): craft_report — MATRIX/BACKLOG/SUMMARY renderers"
```

---

### Task 3: Generator script + generated docs + README

**Files:**
- Create: `scripts/gen_craft_completeness.py`
- Create: `docs/craft_completeness/README.md`
- Create (generated by running the script): `docs/craft_completeness/MATRIX.md`, `docs/craft_completeness/BACKLOG.md`

**Interfaces:**
- Consumes: `run_census` from `artifactsmmo_cli.audit.craft_census`; `render_matrix`, `render_backlog`, `summary_line` from `artifactsmmo_cli.audit.craft_report`; `GameData.from_cache_bundle`.
- Produces: the two generated docs + a stdout SUMMARY line. No test (scripts are outside the coverage/mypy gate); correctness comes from the tested `src/` cores it calls.

- [ ] **Step 1: Write the generator script**

Create `scripts/gen_craft_completeness.py`:

```python
"""Generate docs/craft_completeness/{MATRIX,BACKLOG}.md from the committed
bundle by running the Phase-1 census over every craftable recipe.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json. Serial run is ~50 min
(~1758 cells, ~16% hit the 10 s planner budget). Run:

    uv run python scripts/gen_craft_completeness.py
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import craftable_recipes, run_census
from artifactsmmo_cli.audit.craft_report import (
    render_backlog,
    render_matrix,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/craft_completeness")
_START = 0.0


def _progress(done: int, total: int, recipe: str) -> None:
    elapsed = time.monotonic() - _START
    print(f"[{done}/{total}] {elapsed:6.0f}s {recipe}", file=sys.stderr)


def main() -> None:
    global _START
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    _START = time.monotonic()
    results = run_census(gd, craftable_recipes(gd), progress=_progress)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "MATRIX.md").write_text(render_matrix(results))
    (OUT_DIR / "BACKLOG.md").write_text(render_backlog(results))
    print(summary_line(results))


if __name__ == "__main__":
    main()
```

Note: `time.monotonic()` is allowed here (a plain script, not a workflow). The `global _START` pattern avoids threading a start time through `_progress`; if the reviewer prefers, wrap state in a small closure instead — either is acceptable in a glue script.

- [ ] **Step 2: Smoke-run the script on a tiny subset to prove the pipeline wires end-to-end**

Temporarily verify wiring WITHOUT the full 50-min run by driving the census on one recipe from a REPL-style check (do not edit the script):

```bash
uv run python -c "
import json
from pathlib import Path
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import run_census
from artifactsmmo_cli.audit.craft_report import render_matrix, render_backlog, summary_line
gd = GameData.from_cache_bundle(json.loads(Path('tests/test_ai/scenarios/fixtures/gamedata_bundle.json').read_text()))
res = run_census(gd, recipes=['copper_bar','iron_boots'])
print(summary_line(res))
print(render_matrix(res)[:400])
print(render_backlog(res)[:400])
"
```
Expected: a SUMMARY line, a matrix fragment with `## mining — tier 1` and a `## gearcrafting — tier ...` section, and a backlog fragment. No exceptions.

- [ ] **Step 3: Write the README**

Create `docs/craft_completeness/README.md`:

```markdown
# Craft-Planning Completeness

Census of the AI player's planner: of the game's craftable recipes, for how
many can the planner produce a *directional* plan toward making the item, from
a plausible under-progressed state? The analogue of
`docs/behavioral_completeness/` for crafting recipes — it validates the RUNNING
planner (not a proof), turning "gap discovered by chance" (GAP-8, GAP-9) into
"enumerated".

- [`MATRIX.md`](MATRIX.md) — every craftable recipe x its level/skill census
  cells → PASS or gap-class, grouped by craft skill × tier. Generated.
- [`BACKLOG.md`](BACKLOG.md) — the ranked `PLANNER_BUG` fix-queue (recipes the
  planner failed on despite every closure leaf being reachable). Generated.
- Spec: [`../superpowers/specs/2026-07-08-craft-planning-completeness-design.md`](../superpowers/specs/2026-07-08-craft-planning-completeness-design.md)
- Plan: [`../superpowers/plans/2026-07-09-craft-completeness-phase2-generator.md`](../superpowers/plans/2026-07-09-craft-completeness-phase2-generator.md)

## Gap classes

`PLANNER_BUG` (actionable — the planner should have planned), `COMBAT_BLOCKED`,
`EVENT_GATED`, `MATERIAL_UNREACHABLE`, `SKILL_UNREACHABLE` (game limits).

## How to regenerate

```
uv run python scripts/gen_craft_completeness.py
```

Offline (loads the committed bundle, no API). Serial ≈ 50 min over ~1758 cells;
~16% of cells hit the planner's 10 s wall-clock budget and their verdict can
vary between regens — treat borderline cells as approximate. The SUMMARY line
printed at the end is the completeness metric tracked over time.
```

- [ ] **Step 4: Commit the script + README (before the long run)**

```bash
git add scripts/gen_craft_completeness.py docs/craft_completeness/README.md
git commit --no-verify -m "feat(audit): gen_craft_completeness script + census README"
```

- [ ] **Step 5: Run the full census to generate the committed docs (~50 min, background)**

Run in the background (it writes both docs and prints the SUMMARY):
```bash
uv run python scripts/gen_craft_completeness.py > /tmp/craft_census_summary.txt 2>/tmp/craft_census_progress.txt
```
Wait for completion. Confirm:
- `docs/craft_completeness/MATRIX.md` and `docs/craft_completeness/BACKLOG.md` exist and are non-empty.
- The SUMMARY (`cat /tmp/craft_census_summary.txt`) shows `321 recipes, 1758 cells` (or the current bundle's counts) with a PASS% and per-gap counts.
- Spot-check MATRIX.md: `grep -c "^| " docs/craft_completeness/MATRIX.md` ≈ 321 recipe rows; sections for each craft skill present.
- Spot-check BACKLOG.md: it lists PLANNER_BUG recipes (or states the queue is empty).

- [ ] **Step 6: Commit the generated docs**

```bash
git add docs/craft_completeness/MATRIX.md docs/craft_completeness/BACKLOG.md
git commit --no-verify -m "docs(craft): generated MATRIX + BACKLOG census over 321 recipes"
```

- [ ] **Step 7: Final module verification**

Run:
```
uv run pytest tests/test_audit/ --cov=artifactsmmo_cli.audit.craft_census --cov=artifactsmmo_cli.audit.craft_report --cov-report=term-missing -q 2>&1 | grep -iE "craft_census|craft_report|TOTAL|passed|failed"
uv run mypy src/artifactsmmo_cli/audit/craft_census.py src/artifactsmmo_cli/audit/craft_report.py
```
Expected: both modules 100%, all `tests/test_audit/` green, mypy `Success`.

---

## Notes for the executor

- The SUMMARY's headline metric is `nominal-at-skill PASS n/m` — the realistic cell per recipe. That ratio, plus the PLANNER_BUG count, is what Phase 4 triages and what a future regression watches.
- Determinism caveat (documented in the generated header + README): the ~16% of cells that hit the 10 s wall-clock budget can flip between regens. This is inherent to driving the real planner with a time budget (spec-accepted). A node-count budget would make it deterministic — logged as a Phase-3/4 follow-up, NOT in scope here.
- `render_backlog`'s "closure leaf that blocked" from the spec is rendered as the CraftVerdict `reason` (`empty`/`wait`/`unrelated:<repr>`) — for a PLANNER_BUG every leaf is reachable, so there is no single blocking leaf; the reason is the honest diagnostic. Note this in the Task-2 report.
- Known minor inherited from Phase 1 (do not fix here, note for Phase-2 review awareness): `_closure_item_set`'s comment over-claims `resource_drop_items ⊆ ingredient-union`; harmless.
```
