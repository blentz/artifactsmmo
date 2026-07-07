"""Scrolling log of per-cycle decisions. Wraps Textual's RichLog."""

from typing import Any

from textual.widgets import RichLog

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.plan_format import short_root

_OUTCOME_COLOR = {"ok": "green", "no_plan": "yellow"}


def build_log_lines(snap: CycleSnapshot) -> list[str]:
    """Rich-markup lines for one cycle: the compact decision line, plus a dim
    'why' line (chosen root score + top-2 alternatives) when a strategy ranking
    is present. Discretionary cycles (no chosen_root / empty ranking) get the
    single line only.

    Phase-3 Task 5: when the cycle carries a progression-tree shadow decision
    (`snap.tree_active`), the compact line gains a ` tree:{==|!=}` suffix — the
    same repr comparison of the shadow's chosen root against the enacted
    `chosen_root` that `analyze_tree_divergence` (Task 4) does over raw trace
    JSONL. Absent shadow (old traces, or cycles before the engine seeded)
    means no suffix at all, so old traces render unchanged."""
    outcome_color = _OUTCOME_COLOR.get(snap.outcome, "red")
    ts = snap.timestamp[11:19] if len(snap.timestamp) >= 19 else snap.timestamp
    line1 = (
        f"[dim]{ts}[/dim] "
        f"c{snap.cycle_index:>3} "
        f"[cyan]{snap.selected_goal:<25}[/cyan] "
        f"{snap.action:<35} "
        f"[{outcome_color}]{snap.outcome}[/{outcome_color}]"
    )
    if snap.tree_active:
        agree = "==" if snap.tree_chosen_root == snap.chosen_root else "!="
        line1 = f"{line1} tree:{agree}"
    if snap.chosen_root is None or not snap.strategy_ranking:
        return [line1]

    chosen = next((r for r in snap.strategy_ranking if r.root_repr == snap.chosen_root), None)
    if chosen is None:
        return [line1]
    why = f"   why: {chosen.category} {chosen.score:.2f}"
    alts = [r for r in snap.strategy_ranking if r.root_repr != snap.chosen_root][:2]
    if alts:
        alt_text = " | ".join(f"{short_root(r.root_repr)} {r.score:.2f}" for r in alts)
        why = f"{why}  alt: {alt_text}"
    return [line1, f"[dim]{why}[/dim]"]


class LogPane(RichLog):
    """Append-only decision log. Auto-scrolls to bottom."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(wrap=False, markup=True, auto_scroll=True, **kwargs)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        for line in build_log_lines(snap):
            self.write(line)
