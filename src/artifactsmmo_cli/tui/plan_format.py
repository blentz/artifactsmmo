"""Shared pure formatters for the TUI plan/log views (no rendering, no state)."""

import re

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")


def grind_chain_lines(nodes: tuple[PlanTreeNode, ...], indent: int = 0) -> list[str]:
    """Flatten a grind-expansion node tuple into dim, indented Rich-markup log
    lines — one per leg, each leg's children nested a level deeper — so the log
    shows the whole action chain a LevelSkill step expands into."""
    lines: list[str] = []
    for node in nodes:
        prefix = "  " * (indent + 1)
        lines.append(f"[dim]{prefix}↳ {node.label}[/dim]")
        lines.extend(grind_chain_lines(node.children, indent + 1))
    return lines


def short_root(root_repr: str) -> str:
    """Collapse an ObtainItem(...) repr to `code` (quantity 1) or `Nx code`.
    Non-ObtainItem reprs are returned unchanged."""
    m = _OBTAIN_RE.fullmatch(root_repr)
    if m is None:
        return root_repr
    code, qty = m.group(1), m.group(2)
    return code if qty == "1" else f"{qty}x {code}"
