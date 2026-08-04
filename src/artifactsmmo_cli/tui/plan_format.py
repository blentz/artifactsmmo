"""Shared pure formatters for the TUI plan/log views (no rendering, no state)."""

import re

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode

_OBTAIN_RE = re.compile(r"ObtainItem\(code='([^']+)', quantity=(\d+)\)")

_SUPPLY_RE = re.compile(r"\('([^']+)', (\d+), (\d+)\)")
"""`CycleSnapshot.supply_target` — `repr((item_code, quantity, demand))`.

The same idiom `_OBTAIN_RE` already uses on `chosen_root`: the snapshot carries
a `repr` (its trace twin is JSON and must stay a string), and the one reader
that needs the parts takes them back out here rather than in a widget."""


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


def parse_supply_target(target_repr: str) -> tuple[str, int, int] | None:
    """`(item_code, target banked quantity, unmet demand)` out of
    `CycleSnapshot.supply_target`, or None when the string is not that shape.

    None is a real outcome, not an error path: a caller that gets it renders
    the cycle WITHOUT the supply line rather than showing a partial or invented
    figure. The only way it can happen is an item code carrying a quote, which
    no live code does — the same deliberate silent degradation `fight_format`
    applies to the server's transcript phrases."""
    m = _SUPPLY_RE.fullmatch(target_repr)
    if m is None:
        return None
    return m.group(1), int(m.group(2)), int(m.group(3))


def supply_banked(quantity: int, demand: int) -> int:
    """Units of the target ALREADY in the bank, recovered exactly.

    Not an estimate and not a second source: `GamePlayer._pick_supply_target`
    builds the pair as `(banked + demand, demand)` from ONE reading of
    `state.bank_items`, so the difference is that reading and nothing else.
    Named here, once, so both panes ask the same question of the same two
    fields — and so this comment sits next to the arithmetic if the triple's
    construction ever changes."""
    return quantity - demand


def supply_progress(item_code: str, quantity: int, demand: int) -> str:
    """`ash_wood 12/62` — banked over the banked-count the goal targets."""
    return f"{item_code} {supply_banked(quantity, demand)}/{quantity}"


def supply_detail(quantity: int, demand: int) -> str:
    """`banked 12 / 62   demand 50` — the plan tree's supply-node detail.

    The item code is deliberately absent: this hangs off a node whose label
    already names it, and the plan pane's other details (`gear · 2.31`) are
    likewise about the node they sit on rather than repeating it."""
    return f"banked {supply_banked(quantity, demand)} / {quantity}   demand {demand}"


def short_root(root_repr: str) -> str:
    """Collapse an ObtainItem(...) repr to `code` (quantity 1) or `Nx code`.
    Non-ObtainItem reprs are returned unchanged."""
    m = _OBTAIN_RE.fullmatch(root_repr)
    if m is None:
        return root_repr
    code, qty = m.group(1), m.group(2)
    return code if qty == "1" else f"{qty}x {code}"
