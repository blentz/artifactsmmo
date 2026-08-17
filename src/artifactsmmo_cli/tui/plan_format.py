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


def supply_progress(item_code: str, quantity: int, demand: int) -> str:
    """`ash_wood →62 banked, 50 unmet` — the banked count this character's
    supply goal is producing TOWARD, and the sibling demand still unmet.

    BOTH NUMBERS ARE THE PAIR ITSELF; nothing is derived. This used to render
    `banked/target` off `quantity - demand`, which was exact while
    `GamePlayer._pick_supply_target` built the pair as `(banked + demand,
    demand)` from one reading of `state.bank_items`. It now builds `quantity`
    as `supply_batch_target_pure(banked, demand)` — the next BATCH milestone
    above the bank, clamped to `banked + demand` — so the subtraction stopped
    being the bank reading and started printing nonsense: banked=0 with
    demand=60 gives the pair (10, 60) and rendered `spruce_wood -50/10`.

    The banked count is not recoverable from the pair at all any more (many
    different bank readings map to one milestone), and inventing an estimate
    of it would be worse than not showing it, so both panes report the two
    figures the pair still carries and only those. `supply_detail` below says
    the same thing in the plan tree's idiom — same two fields, same order, no
    third number — which is the property this pair of formatters exists to
    keep: a reader switching panes sees ONE account of the commitment."""
    return f"{item_code} →{quantity} banked, {demand} unmet"


def supply_detail(quantity: int, demand: int) -> str:
    """`target 62 banked   demand 50` — the plan tree's supply-node detail, the
    same two fields `supply_progress` renders for the log pane and nothing
    derived from them (see there for why the old banked figure is gone).

    The item code is deliberately absent: this hangs off a node whose label
    already names it, and the plan pane's other details (`gear · 2.31`) are
    likewise about the node they sit on rather than repeating it."""
    return f"target {quantity} banked   demand {demand}"


def short_root(root_repr: str) -> str:
    """Collapse an ObtainItem(...) repr to `code` (quantity 1) or `Nx code`.
    Non-ObtainItem reprs are returned unchanged."""
    m = _OBTAIN_RE.fullmatch(root_repr)
    if m is None:
        return root_repr
    code, qty = m.group(1), m.group(2)
    return code if qty == "1" else f"{qty}x {code}"
