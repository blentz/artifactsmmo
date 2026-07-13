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
    (reason, kind): its code and each cell's cap/pressure -> PASS or gap
    abbrev, followed by the reason-coverage table."""
    by_reason_kind: dict[tuple[str, str], list[CellResult]] = defaultdict(list)
    for r in results:
        by_reason_kind[(r.reason, r.kind)].append(r)
    lines = [
        "# Inventory Keep/Disposal Completeness — Matrix",
        "",
        _GENERATED_HEADER,
        "",
        summary_line(results),
        "",
        "Legend: " + ", ".join(f"{v}={k}" for k, v in GAP_ABBREV.items()) + ".",
        "",
        "| Reason | Kind | Code | Cells (cap/pressure → verdict) |",
        "|---|---|---|---|",
    ]
    for reason_val, kind in sorted(by_reason_kind):
        cells = sorted(by_reason_kind[(reason_val, kind)],
                       key=lambda r: (r.cap, r.pressure))
        code = cells[0].code
        tokens = " · ".join(_cell_token(c) for c in cells)
        lines.append(f"| {reason_val} | {kind} | {code} | {tokens} |")
    lines.append("")
    lines.append(render_reason_coverage(coverage))
    return "\n".join(lines) + "\n"
