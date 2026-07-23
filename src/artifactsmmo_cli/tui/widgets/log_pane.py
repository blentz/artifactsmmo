"""Scrolling log of per-cycle decisions. Wraps Textual's RichLog."""

from typing import Any

from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.plan_format import grind_chain_lines, short_root

_OUTCOME_COLOR = {"ok": "green", "no_plan": "yellow"}


def build_log_lines(snap: CycleSnapshot) -> list[str]:
    """Rich-markup lines for one cycle: the compact decision line, an optional
    dim 'why' line (chosen root score + top-2 alternatives) when a strategy
    ranking is present, and — on a LevelSkill cycle — the captured grind chain
    (the concrete gather/craft legs the step expands into). Discretionary cycles
    (no chosen_root / empty ranking) get the single line plus any grind chain."""
    outcome_color = _OUTCOME_COLOR.get(snap.outcome, "red")
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    line1 = (
        f"[dim]{ts}[/dim] "
        f"c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal:<25}[/cyan] "
        f"{snap.action:<35} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}]"
    )
    lines = [line1]
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
    lines.extend(grind_chain_lines(snap.grind_expansion))
    return lines


class LogPane(RichLog):
    """Append-only decision log. Auto-scrolls to bottom."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(wrap=False, markup=True, auto_scroll=True, **kwargs)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        for line in build_log_lines(snap):
            self.write(line)
