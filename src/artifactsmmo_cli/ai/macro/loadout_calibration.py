"""Pure aggregator + markdown formatter for predict_win calibration diagnostics.

Consumes CombatLoadoutOutcomeRow records (Task 1 / D) and emits a markdown
report grouping by task_key, ranked worst-calibrated-first (largest over-estimate
rate). No bot behavior or decision logic — read-only diagnostics only.
"""

import json
from collections import defaultdict
from fractions import Fraction

from artifactsmmo_cli.ai.learning.store import CombatLoadoutOutcomeRow


def _loadout_key(loadout: dict[str, str]) -> str:
    """Stable string key for a worn loadout dict (json sorted keys)."""
    return json.dumps(loadout, sort_keys=True)


def _over_estimate_rate(over: int, total: int) -> float:
    """Fraction of fights where we predicted win but actually lost."""
    return over / total if total > 0 else 0.0


def _percent(x: float) -> str:
    """A whole-number-or-one-decimal percentage: 0.5 -> '50%', 0.645 -> '64.5%'."""
    text = f"{100.0 * x:.1f}"
    return (text[:-2] if text.endswith(".0") else text) + "%"


def _p_win_buckets(rows: list[CombatLoadoutOutcomeRow]) -> list[str]:
    """The `## P(win) calibration` section: fights bucketed by the win
    probability recorded for them, with the mean predicted and the observed win
    rate per bucket. Rows with no recorded p_win are left out."""
    buckets: dict[int, list[CombatLoadoutOutcomeRow]] = defaultdict(list)
    for r in rows:
        if r.p_win is not None:
            buckets[min(int(r.p_win * 10), 9)].append(r)
    lines = ["## P(win) calibration", ""]
    if not buckets:
        lines.append("No P(win) recorded yet.")
        lines.append("")
        return lines
    lines.append("| bucket | fights | mean predicted | observed |")
    lines.append("|---|---|---|---|")
    for b in sorted(buckets):
        members = buckets[b]
        predicted = sum(m.p_win for m in members if m.p_win is not None) / len(members)
        observed = sum(1 for m in members if m.actual_win) / len(members)
        lines.append(f"| {b / 10:.1f}-{(b + 1) / 10:.1f} | {len(members)} "
                     f"| {_percent(predicted)} | {_percent(observed)} |")
    lines.append("")
    return lines


def _beyond_liveness_lines(beyond: dict[str, list[tuple[str, Fraction]]]) -> list[str]:
    """The (character, monster) pairs whose win threshold is above the 99/100
    the leveling liveness proof covers (`win_threshold_core.LIVENESS_THETA`).
    θ is never capped (USER 2026-10-16), so this is where a pair outside the
    proof's hypothesis shows."""
    lines = ["## Win thresholds beyond the liveness bound (θ > 0.99)", ""]
    pairs = [(character, monster, theta) for character, found in beyond.items()
             for monster, theta in found]
    if not pairs:
        return [*lines, "None: every measured threshold is within the liveness bound.", ""]
    lines += ["| character | monster | θ |", "|---|---|---|"]
    lines += [f"| {character} | {monster} | {float(theta):.3f} |"
              for character, monster, theta in pairs]
    return [*lines, ""]


def loadout_calibration_report(rows: list[CombatLoadoutOutcomeRow],
                               beyond: dict[str, list[tuple[str, Fraction]]] | None = None) -> str:
    """Build a markdown calibration report from CombatLoadoutOutcomeRow records.

    Groups by task_key; per task: predicted-win rate, actual-win rate, the two
    mis-prediction buckets (over-estimate = predicted-win & not actual-win;
    under-estimate = not predicted-win & actual-win); per distinct worn loadout:
    win/loss tally. Tasks ranked worst-calibration-first (largest over-estimate
    rate first). Empty input returns an empty-state message. `beyond` (per
    character, `win_threshold_core.beyond_liveness`) adds the thresholds above
    the liveness bound.
    """
    if not rows:
        return "# Combat-loadout calibration\n\nNo fight outcome data recorded yet.\n"

    # Aggregate per task_key
    task_total: dict[str, int] = defaultdict(int)
    task_pred_win: dict[str, int] = defaultdict(int)
    task_actual_win: dict[str, int] = defaultdict(int)
    task_over_estimate: dict[str, int] = defaultdict(int)   # predicted-win but lost
    task_under_estimate: dict[str, int] = defaultdict(int)  # predicted-loss but won

    # Per task: per loadout key → (wins, losses)
    task_loadout_tally: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))

    for r in rows:
        tk = r.task_key
        task_total[tk] += 1
        if r.predicted_win:
            task_pred_win[tk] += 1
        if r.actual_win:
            task_actual_win[tk] += 1
        if r.predicted_win and not r.actual_win:
            task_over_estimate[tk] += 1
        if not r.predicted_win and r.actual_win:
            task_under_estimate[tk] += 1
        lk = _loadout_key(r.loadout)
        tally = task_loadout_tally[tk][lk]
        if r.actual_win:
            tally[0] += 1
        else:
            tally[1] += 1

    # Rank tasks by over-estimate rate descending (worst calibration first)
    task_keys = sorted(
        task_total.keys(),
        key=lambda tk: _over_estimate_rate(task_over_estimate[tk], task_total[tk]),
        reverse=True,
    )

    lines: list[str] = ["# Combat-loadout calibration", ""]
    lines.append("Tasks ranked by over-estimate rate (predicted-win but lost) — worst first.")
    lines.append("")
    lines.append("| task | fights | pred-win% | actual-win% | over-estimate | under-estimate |")
    lines.append("|---|---|---|---|---|---|")
    for tk in task_keys:
        total = task_total[tk]
        pred_pct = 100.0 * task_pred_win[tk] / total
        actual_pct = 100.0 * task_actual_win[tk] / total
        over = task_over_estimate[tk]
        under = task_under_estimate[tk]
        lines.append(
            f"| {tk} | {total} | {pred_pct:.0f}% | {actual_pct:.0f}% "
            f"| {over} (over-estimate) | {under} (under-estimate) |"
        )
    lines.append("")

    # Per-task loadout tallies
    lines.append("## Per-task loadout win/loss tally")
    lines.append("")
    for tk in task_keys:
        lines.append(f"### {tk}")
        lines.append("")
        lines.append("| loadout | wins | losses |")
        lines.append("|---|---|---|")
        loadouts = task_loadout_tally[tk]
        for lk in sorted(loadouts.keys()):
            wins, losses = loadouts[lk]
            loadout_dict: dict[str, str] = json.loads(lk)
            # Render as slot=code pairs for readability
            loadout_repr = ", ".join(f"{s}={c}" for s, c in sorted(loadout_dict.items()))
            lines.append(f"| {loadout_repr} | {wins} | {losses} |")
        lines.append("")

    lines.extend(_p_win_buckets(rows))
    if beyond is not None:
        lines.extend(_beyond_liveness_lines(beyond))
    return "\n".join(lines)
