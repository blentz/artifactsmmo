"""Inventory-completeness doc renderer (item-protection-authority epic,
Task 5). Pure markdown over a list of `CellResult` plus the reason-coverage
table: the reason x cell PASS/gap MATRIX and a one-line SUMMARY metric. No
planner, no game data, no I/O — the generator script owns file writes and the
census run. Mirrors `audit/craft_report.py`."""

from collections import defaultdict

from artifactsmmo_cli.ai.inventory_keep import KeepReason
from artifactsmmo_cli.audit.inventory_census import CellResult

GAP_ABBREV: dict[str, str] = {
    "keep_all_sentinel": "KA",
    "venue_unreachable": "VU",
    "bank_full": "BF",
    "no_route_available": "NR",
    "inventory_bug": "IB",
}

_GENERATED_HEADER = (
    "> GENERATED — do not hand-edit. Regenerate with "
    "`uv run python scripts/gen_inventory_completeness.py`.\n>\n"
    "> Census drives the REAL `StrategyArbiter.select` seam over the committed "
    "bundle. The cell grid is DERIVED from the `KeepReason` registry "
    "(`inventory_grid`) — nothing here is hand-picked.\n"
)


def _cell_token(r: CellResult) -> str:
    verdict = "PASS" if r.passed else GAP_ABBREV[r.gap] if r.gap else "FAIL"
    return f"{r.cap}/{r.pressure} {verdict}"


def band_summary(results: list[CellResult]) -> str:
    """PASS counts split by level-distance BAND. A band that passes only IN_BAND
    is the signature of `inventory_caps.level_distance_keep_ceiling` clamping a
    protection it has no business clamping (the two defects the band dimension was
    added to expose), so the split is reported next to the headline metric."""
    bands = sorted({r.band for r in results})
    parts = []
    for band in bands:
        cells = [r for r in results if r.band == band]
        passed = sum(1 for r in cells if r.passed)
        bugs = sum(1 for r in cells if r.gap == "inventory_bug")
        parts.append(f"{band} {passed}/{len(cells)} (inventory_bug {bugs})")
    return "by band: " + "; ".join(parts)


def summary_line(results: list[CellResult]) -> str:
    """One-line completeness metric: cell totals, overall PASS%, and per-gap
    counts (`inventory_bug` is the must-be-zero residual)."""
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    pct = 100 * passed / total if total else 0.0
    gap_counts = {v: 0 for v in GAP_ABBREV}
    for r in results:
        if r.gap is not None:
            gap_counts[r.gap] += 1
    gaps = ", ".join(f"{k} {gap_counts[k]}" for k in GAP_ABBREV)
    return f"{total} cells; PASS {passed} ({pct:.0f}%); gaps: {gaps}"


def render_matrix_rows(results: list[CellResult]) -> list[str]:
    """One markdown row per (reason, kind, band): the code, then each cell's
    cap/pressure verdict. BAND is a row key, not a cell token, so a reason's two
    bands sit side by side and a ceiling-induced FAIL is visible at a glance."""
    by_row: dict[tuple[str, str, str], list[CellResult]] = defaultdict(list)
    for r in results:
        by_row[(r.reason, r.kind, r.band)].append(r)
    rows = []
    for reason_val, kind, band in sorted(by_row):
        cells = sorted(by_row[(reason_val, kind, band)],
                       key=lambda r: (r.cap, r.pressure))
        tokens = " · ".join(_cell_token(c) for c in cells)
        rows.append(f"| {reason_val} | {kind} | {band} | {cells[0].code} | {tokens} |")
    return rows


def render_reason_coverage(coverage: dict[KeepReason, bool]) -> str:
    """The Gate-2 anti-rot table: every `KeepReason` -> whether it has earned
    a PASSing LIVENESS cell. `CURRENCY` is the one declared exemption."""
    lines = [
        "## Reason coverage (Gate 2 — anti-rot)",
        "",
        "Every `KeepReason` except `CURRENCY` must have at least one PASSing "
        "LIVENESS cell, or the reason's surplus has never been proven "
        "disposable.",
        "",
        "| KeepReason | has passing LIVENESS cell |",
        "|---|---|",
    ]
    for reason in KeepReason:
        covered = coverage[reason]
        note = " (KEEP_ALL exemption)" if reason is KeepReason.CURRENCY else ""
        lines.append(f"| {reason.value} | {'PASS' if covered else 'FAIL'}{note} |")
    lines.append("")
    return "\n".join(lines)


def render_matrix(results: list[CellResult],
                  coverage: dict[KeepReason, bool]) -> str:
    """The reason x cell MATRIX, grouped by `KeepReason`. One row per
    (reason, kind, band): its code and each cell's cap/pressure -> PASS or gap
    abbrev, followed by the reason-coverage table."""
    lines = [
        "# Inventory Keep/Disposal Completeness — Matrix",
        "",
        _GENERATED_HEADER,
        "",
        summary_line(results),
        "",
        band_summary(results),
        "",
        "Legend: " + ", ".join(f"{v}={k}" for k, v in GAP_ABBREV.items()) + ".",
        "",
        "| Reason | Kind | Band | Code | Cells (cap/pressure → verdict) |",
        "|---|---|---|---|---|",
    ]
    lines.extend(render_matrix_rows(results))
    lines.append("")
    lines.append(render_reason_coverage(coverage))
    return "\n".join(lines) + "\n"
