"""Stats command: summarise GOAP session data from the SQLite learning store.

Surfaces the same metrics earlier sessions computed via ad-hoc Python
scripts: outcome distribution, top goals/actions, planner load, fight
outcomes, crafts / equips / discards / deposits / withdraws, task
completions, stuck windows. Per-section flags let you drill in (e.g.
`--planner-only`) or filter the window (`--since`, `--until`,
`--character`, `--session`).

Reads from `~/.cache/artifactsmmo/learning.db` by default (matches the
same path `play` writes to via `default_learn_db_path`)."""

from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from artifactsmmo_cli.ai.trace_stats import (
    TraceStats,
    analyze,
    analyze_tree_divergence,
    list_sessions,
    load_cycles_from_db,
    load_trace_records,
)

app = typer.Typer(help="Inspect GOAP session data from the learning store")
console = Console()


def _default_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def _section_overview(s: TraceStats) -> Table:
    t = Table(title="Overview", show_header=False)
    t.add_column(style="bold")
    t.add_column()
    t.add_row("cycles", str(s.cycles))
    if s.ts_first:
        t.add_row("first ts", s.ts_first)
    if s.ts_last:
        t.add_row("last ts", s.ts_last)
    t.add_row("duration (min)", f"{s.duration_minutes:.1f}")
    t.add_row("goal changes", str(s.goal_changes))
    t.add_row("goal runs", str(s.goal_runs))
    if s.goal_runs:
        rate = 100.0 * len(s.single_cycle_goals) / s.goal_runs
        t.add_row("single-cycle goal share", f"{rate:.1f}%")
    t.add_row("useless action repeats", str(s.useless_repeats))
    return t


def _section_outcomes(s: TraceStats) -> Table:
    t = Table(title="Outcomes")
    t.add_column("outcome")
    t.add_column("count", justify="right")
    for outcome, count in s.outcomes.most_common():
        t.add_row(outcome, str(count))
    return t


def _section_errors(s: TraceStats) -> Table | None:
    if not s.errors_by_action:
        return None
    t = Table(title="Errors by action")
    t.add_column("action")
    t.add_column("outcome")
    t.add_column("count", justify="right")
    for (action, outcome), count in s.errors_by_action.most_common():
        t.add_row(action, outcome, str(count))
    return t


def _section_goals(s: TraceStats, top: int) -> Table:
    t = Table(title=f"Top {top} selected goals")
    t.add_column("goal")
    t.add_column("cycles selected", justify="right")
    for goal, count in s.selected_goals.most_common(top):
        t.add_row(goal or "(none)", str(count))
    return t


def _section_actions(s: TraceStats, top: int) -> Table:
    t = Table(title=f"Top {top} actions")
    t.add_column("action")
    t.add_column("count", justify="right")
    for action, count in s.actions.most_common(top):
        t.add_row(action or "(none)", str(count))
    return t


def _section_planner(s: TraceStats, top: int) -> Table:
    t = Table(title=f"Planner load (top {top} by max nodes)")
    t.add_column("goal")
    t.add_column("max nodes", justify="right")
    t.add_column("avg nodes", justify="right")
    t.add_column("max plen", justify="right")
    t.add_column("avg plen", justify="right")
    t.add_column("timeouts", justify="right")
    t.add_column("samples", justify="right")
    for g in s.planner[:top]:
        t.add_row(g.goal, f"{g.max_nodes}", f"{g.avg_nodes:.0f}",
                  f"{g.max_plan_len}", f"{g.avg_plan_len:.1f}",
                  str(g.timeouts), str(g.samples))
    return t


def _section_fights(s: TraceStats) -> Table | None:
    if not s.fight_attempts and not s.fight_losses:
        return None
    t = Table(title="Fights")
    t.add_column("metric")
    t.add_column("value", justify="right")
    t.add_row("attempts", str(s.fight_attempts))
    t.add_row("losses", str(len(s.fight_losses)))
    return t


def _section_fight_losses(s: TraceStats) -> Table | None:
    if not s.fight_losses:
        return None
    t = Table(title="Fight losses (recent 10)")
    t.add_column("cycle", justify="right")
    t.add_column("ts")
    t.add_column("hp", justify="right")
    t.add_column("monster")
    for fl in s.fight_losses[-10:]:
        t.add_row(str(fl.cycle), fl.ts, f"{fl.hp}/{fl.max_hp}", fl.monster)
    return t


def _section_inventory_events(s: TraceStats) -> Table:
    t = Table(title="Inventory events")
    t.add_column("event")
    t.add_column("count", justify="right")
    t.add_row("crafts (total)", str(sum(s.craft_events.values())))
    t.add_row("equip / loadout", str(s.equip_events))
    t.add_row("deletes (total)", str(sum(s.delete_events.values())))
    t.add_row("deposits", str(s.deposit_events))
    t.add_row("withdraws (total)", str(sum(s.withdraw_events.values())))
    return t


def _section_breakdown(title: str, counter: Counter[str], top: int) -> Table | None:
    if not counter:
        return None
    t = Table(title=f"{title} (top {top})")
    t.add_column("item")
    t.add_column("count", justify="right")
    for code, count in counter.most_common(top):
        t.add_row(code, str(count))
    return t


def _section_task_completions(s: TraceStats) -> Table | None:
    if not s.task_completions:
        return None
    t = Table(title="Task completions")
    t.add_column("task")
    t.add_column("units", justify="right")
    t.add_column("duration (min)", justify="right")
    t.add_column("s/unit", justify="right")
    for tc in s.task_completions:
        per = tc.duration_minutes * 60 / max(1, tc.units)
        t.add_row(tc.task_code, str(tc.units), f"{tc.duration_minutes:.1f}",
                  f"{per:.1f}")
    return t


def _section_tree_divergence(s: TraceStats) -> Table | None:
    """Phase-3 progression-tree shadow divergence — populated only when
    `analyze_tree_divergence` has fed dual (strategy+tree) trace records
    into `s` (see `--trace-file`); omitted entirely otherwise, matching
    `_section_errors`'s None-when-empty style."""
    if not s.tree_dual_cycles:
        return None
    t = Table(title="Progression-tree shadow divergence")
    t.add_column("metric")
    t.add_column("value", justify="right")
    t.add_row("dual cycles", str(s.tree_dual_cycles))
    pct = 100.0 * s.tree_agree / s.tree_dual_cycles
    t.add_row("agreement", f"{s.tree_agree} ({pct:.1f}%)")
    for branch, count in s.tree_branch_counts.most_common():
        t.add_row(f"tree branch: {branch}", str(count))
    for (legacy_root, tree_root), count in s.tree_divergent_pairs.most_common(5):
        t.add_row(f"{legacy_root} != {tree_root}", str(count))
    return t


def _section_stuck(s: TraceStats) -> Table | None:
    if not s.stuck_windows:
        return None
    t = Table(title="Stuck windows (>=8 cycles no inv/progress change)")
    t.add_column("start ts")
    t.add_column("task")
    t.add_column("progress", justify="right")
    t.add_column("inv", justify="right")
    t.add_column("cycles", justify="right")
    for w in s.stuck_windows:
        t.add_row(w.start_ts, w.task_code or "(none)", str(w.progress),
                  str(w.inventory), str(w.cycles))
    return t


@app.command("summary")
def summary(
    db: str = typer.Option(_default_db_path(), "--db",
                           help="Path to learning.db"),
    character: str | None = typer.Option(None, "--character", "-c",
                                         help="Filter by character"),
    session: str | None = typer.Option(
        "last", "--session", "-s",
        help='Session id (or "last" = most recent; "all" = no filter)'),
    since: str | None = typer.Option(None, "--since",
                                     help="ISO ts filter (Cycle.ts >=)"),
    until: str | None = typer.Option(None, "--until",
                                     help="ISO ts filter (Cycle.ts <)"),
    top: int = typer.Option(10, "--top", "-n",
                            help="Top-N row count for ranked tables"),
    planner_only: bool = typer.Option(False, "--planner-only",
                                      help="Show only the planner load table"),
    goals_only: bool = typer.Option(False, "--goals-only",
                                    help="Show only the selected-goal distribution"),
    trace_file: str | None = typer.Option(
        None, "--trace-file",
        help="Path to a trace JSONL log (e.g. play-trace-<char>.jsonl) — "
             "enables the progression-tree shadow divergence section, "
             "which the DB alone cannot populate (the shadow decision is "
             "traced-only, never persisted to the learning store)"),
) -> None:
    """Summarise GOAP session data from the SQLite learning store.

    By default scopes to the most recent session for the given character
    (or globally if no --character). Pass `--session all` to scan every
    session in the DB, or `--session <id>` for a specific one."""
    if not Path(db).exists():
        console.print(f"[red]DB not found: {db}[/red]")
        raise typer.Exit(1)
    if trace_file is not None and not Path(trace_file).exists():
        console.print(f"[red]Trace file not found: {trace_file}[/red]")
        raise typer.Exit(1)

    resolved = None if session == "all" else session
    cycles = load_cycles_from_db(
        db_path=db, character=character,
        session_id=resolved, since=since, until=until,
    )
    s = analyze(cycles)

    if trace_file is not None:
        tree_stats = analyze_tree_divergence(load_trace_records(trace_file))
        s.tree_dual_cycles = tree_stats.tree_dual_cycles
        s.tree_agree = tree_stats.tree_agree
        s.tree_branch_counts = tree_stats.tree_branch_counts
        s.tree_divergent_pairs = tree_stats.tree_divergent_pairs

    if s.cycles == 0 and not s.tree_dual_cycles:
        console.print("[yellow]no cycles matched the filter[/yellow]")
        return

    if planner_only:
        console.print(_section_planner(s, top))
        return
    if goals_only:
        console.print(_section_goals(s, top))
        return

    sections = [
        _section_overview(s),
        _section_outcomes(s),
        _section_errors(s),
        _section_goals(s, top),
        _section_actions(s, top),
        _section_planner(s, top),
        _section_fights(s),
        _section_fight_losses(s),
        _section_inventory_events(s),
        _section_breakdown("Crafts", s.craft_events, top),
        _section_breakdown("Deletes", s.delete_events, top),
        _section_breakdown("Withdraws", s.withdraw_events, top),
        _section_task_completions(s),
        _section_stuck(s),
        _section_tree_divergence(s),
    ]
    for section in sections:
        if section is not None:
            console.print(section)
            console.print()


@app.command("sessions")
def sessions(
    db: str = typer.Option(_default_db_path(), "--db",
                           help="Path to learning.db"),
    character: str | None = typer.Option(None, "--character", "-c",
                                         help="Filter by character"),
    limit: int = typer.Option(20, "--limit", "-n",
                              help="Max sessions to list (most recent first)"),
) -> None:
    """List recent sessions in the learning store."""
    if not Path(db).exists():
        console.print(f"[red]DB not found: {db}[/red]")
        raise typer.Exit(1)
    sess = list_sessions(db, character=character, limit=limit)
    if not sess:
        console.print("[yellow]no sessions found[/yellow]")
        return
    t = Table(title=f"Sessions (most recent {limit})")
    t.add_column("session_id")
    t.add_column("character")
    t.add_column("started_at")
    t.add_column("ended_at")
    t.add_column("cycles", justify="right")
    t.add_column("exit_reason")
    for r in sess:
        t.add_row(r.session_id, r.character, r.started_at,
                  r.ended_at or "(running)", str(r.cycle_count),
                  r.exit_reason or "(none)")
    console.print(t)
