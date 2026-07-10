"""Craft-completeness doc renderers (spec 2026-07-08 Phase 2). Pure markdown
over a list of CellResult: the recipe x cell PASS/gap MATRIX, the ranked
PLANNER_BUG BACKLOG, and a one-line SUMMARY metric. No planner, no game data,
no I/O — the generator script owns file writes and the census run."""

from collections import defaultdict

from artifactsmmo_cli.audit.craft_census import CellResult
from artifactsmmo_cli.audit.craft_completeness import nominal_char_level, tier_of

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
        if r.char_level == nominal_char_level(r.craft_level) and r.skill_level == r.craft_level
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
        groups[(head.skill, tier_of(head.craft_level))].append(row)
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
