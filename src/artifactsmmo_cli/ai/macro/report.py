"""Render the macro-research findings as a markdown report."""

from artifactsmmo_cli.ai.macro.cost import CostStat, parse_goal_type
from artifactsmmo_cli.ai.macro.cycle_row import CycleRow
from artifactsmmo_cli.ai.macro.scoring import MacroCandidate


def goal_repr_variants(rows: list[CycleRow]) -> dict[str, list[str]]:
    seen: dict[str, set[str]] = {}
    for r in rows:
        if r.selected_goal is None:
            continue
        seen.setdefault(parse_goal_type(r.selected_goal), set()).add(r.selected_goal)
    return {gt: sorted(v) for gt, v in seen.items()}


def _chain_str(chain: tuple[tuple[str, str], ...]) -> str:
    return " -> ".join(f"{g}/{a}" for g, a in chain)


def format_report(cost: list[CostStat], candidates: list[MacroCandidate],
                  variants: dict[str, list[str]], top_n: int) -> str:
    lines: list[str] = ["# Macro-candidate research", ""]

    lines.append("## A* search cost by goal type")
    lines.append("")
    lines.append("| goal type | cycles | total nodes | mean nodes | timeouts |")
    lines.append("|---|---|---|---|---|")
    for s in cost:
        lines.append(
            f"| {s.goal_type} | {s.n_cycles} | {s.total_nodes} | "
            f"{s.mean_nodes:.1f} | {s.timeouts} |")
    lines.append("")

    lines.append(f"## Top {top_n} macro candidates (by value = occurrences x nodes)")
    lines.append("")
    lines.append(
        "> **How to read:** candidates are ranked by distinct characters first "
        "(cross-character recurrence = stability across characters until the seasonal reset), "
        "then by value (= occurrences x total search nodes saved). "
        "A high mean nodes/band with low distinct chars is a volatile single-character chain, "
        "not a stable macro.")
    lines.append("")
    lines.append(
        "| kind | value | occurrences | distinct chars | total nodes | mean nodes/band | chain | example keys |"
    )
    lines.append("|---|---|---|---|---|---|---|---|")
    for c in candidates[:top_n]:
        mean_nodes = c.total_nodes / c.occurrences
        lines.append(
            f"| {c.kind} | {c.value} | {c.occurrences} | {c.distinct_characters} | "
            f"{c.total_nodes} | {mean_nodes:.0f} | {_chain_str(c.chain)} | {', '.join(c.example_keys)} |")
    lines.append("")

    lines.append("## Goal-repr variants (key-canonicalization evidence)")
    lines.append("")
    for gt in sorted(variants):
        lines.append(f"- **{gt}** ({len(variants[gt])} distinct):")
        for repr_str in variants[gt]:
            lines.append(f"  - `{repr_str}`")
    lines.append("")
    return "\n".join(lines)
