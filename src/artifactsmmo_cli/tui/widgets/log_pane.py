"""Scrolling log of per-cycle decisions. Wraps Textual's RichLog."""

from collections.abc import Iterable
from typing import Any

from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, RoleChange
from artifactsmmo_cli.tui.fight_format import fight_summary_line
from artifactsmmo_cli.tui.plan_format import (
    grind_chain_lines,
    parse_supply_target,
    short_root,
    supply_progress,
)

_OUTCOME_COLOR = {"ok": "green", "no_plan": "yellow"}

_NO_ROLE = "none"
"""How a null role reads in the log. A release leaves the character holding
nothing, and `previous`/`current` are `None` for exactly that; spelling it out
beats an empty gap the operator has to interpret."""


def _role_name(role: str | None) -> str:
    return _NO_ROLE if role is None else role


def _role_event_line(ts: str, cycle_index: int, change: RoleChange) -> str:
    """The peer line a role transition gets: same timestamp/cycle gutter as the
    decision line, so it reads as its own event rather than as a note on the
    cycle's action.

    The reason clause is omitted entirely when the decision named none —
    `RoleDecision.reason` is written by the rule that fired, and an empty one
    means nothing was recorded, which is not the same as a reason worth
    inventing."""
    reason = f"  [dim]({change.reason})[/dim]" if change.reason else ""
    return (
        f"[dim]{ts}[/dim] "
        f"c{cycle_index:>3} "
        f"[magenta]* role: {_role_name(change.previous)} -> "
        f"{_role_name(change.current)}[/magenta]{reason}"
    )


def _supply_line(snap: CycleSnapshot) -> list[str]:
    """The dim `role:` continuation, on supply cycles only — at most one line,
    and none at all on the cycles of every single-character run.

    Returns a list rather than `str | None` so the caller stays a single
    `lines.extend(...)` with no branch of its own, matching how the grind chain
    is spliced in directly above it."""
    if snap.supply_target is None:
        return []
    target = parse_supply_target(snap.supply_target)
    if target is None:
        return []
    return [f"[dim]   role: {_role_name(snap.role)}   "
            f"supplying {supply_progress(*target)} for siblings[/dim]"]


def build_log_lines(snap: CycleSnapshot) -> list[str]:
    """Rich-markup lines for one cycle: the compact decision line, an optional
    dim 'why' line (chosen root score + top-2 alternatives) when a strategy
    ranking is present, and — on a LevelSkill cycle — the captured grind chain
    (the concrete gather/craft legs the step expands into), and — on a fight
    cycle — a structured one-line fight summary. Discretionary cycles (no
    chosen_root / empty ranking) get the single line plus any grind chain.

    Cross-character specialization adds two more, both silent unless something
    profile-related actually happened this cycle: a role transition is a peer
    EVENT line above the decision line, and a cycle serving a sibling's demand
    gets a dim `role:` continuation below the `why`. A character with no role
    and nothing to supply — every cycle of every single-character run — renders
    byte-identically to before this existed."""
    outcome_color = _OUTCOME_COLOR.get(snap.outcome, "red")
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    line1 = (
        f"[dim]{ts}[/dim] "
        f"c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal:<25}[/cyan] "
        f"{snap.action:<35} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}]"
    )
    lines = ([] if snap.role_change is None
             else [_role_event_line(ts, snap.cycle_index, snap.role_change)])
    lines.append(line1)
    chosen = (next((r for r in snap.strategy_ranking if r.root_repr == snap.chosen_root), None)
              if snap.chosen_root is not None and snap.strategy_ranking else None)
    if chosen is not None:
        # Name the chosen root, not just its category+score — otherwise a currency
        # grind (e.g. GatherMaterials(event_ticket)) shows in the log with no link
        # to the target it funds (e.g. lich_race_medal), which reads as a pointless
        # grind. The name is already on the snapshot; it was just not rendered.
        why = f"   why: {short_root(chosen.root_repr)}  {chosen.category} {chosen.score:.2f}"
        alts = [r for r in snap.strategy_ranking if r.root_repr != snap.chosen_root][:2]
        if alts:
            alt_text = " | ".join(f"{short_root(r.root_repr)} {r.score:.2f}" for r in alts)
            why = f"{why}  alt: {alt_text}"
        lines.append(f"[dim]{why}[/dim]")
    lines.extend(_supply_line(snap))
    lines.extend(grind_chain_lines(snap.grind_expansion))
    if snap.fight is not None:
        lines.append(fight_summary_line(snap.fight))
    return lines


class LogPane(RichLog):
    """Append-only decision log. Auto-scrolls to bottom."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(wrap=False, markup=True, auto_scroll=True, **kwargs)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        for line in build_log_lines(snap):
            self.write(line)

    def replace_history(self, snaps: Iterable[CycleSnapshot]) -> None:
        """Re-bind the log to a different character's history.

        This pane is append-only, so a focus switch that merely appended the
        new character's latest cycle left the operator reading a MIXTURE of two
        characters' logs with nothing marking where one ended and the other
        began. Switching replaces the contents outright.
        """
        self.clear()
        for snap in snaps:
            self.update_snapshot(snap)
