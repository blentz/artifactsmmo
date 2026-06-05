"""Pure analysis of recorded GOAP cycles from the LearningStore.

`TraceStats` collects per-cycle records into the same metrics earlier
sessions reached for via ad-hoc inline scripts: outcome counts, goal/action
distributions, planner load profile, task completion timings, stuck-state
windows, fight outcomes, crafts / equips / discards / deposits / withdraws.

Reads from the SQLite learning store (`Cycle` table) rather than the
`traces.jsonl` log so stats stays consistent with the same data source the
learning projections / planner cost cache feed from. No I/O in `analyze`
— it takes an iterable of `Cycle` rows so it stays trivially testable.
The CLI layer (`commands/stats.py`) handles DB session bootstrap and rich
rendering.
"""

from collections import Counter
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime

from sqlmodel import Session as SqlSession, asc, create_engine, select

from artifactsmmo_cli.ai.learning.models import Cycle, Session


@dataclass
class GoalLoad:
    """Per-(selected-)goal planner load profile.

    Sourced from `Cycle.planner_nodes` / `Cycle.plan_len` which capture the
    WINNING goal's stats per cycle. The per-cycle breakdown of every goal
    the arbiter tried (the trace JSONL's `goals_tried` list) is not yet
    persisted; if a goal never wins selection it won't appear here. Most
    bugs surface in winner stats (timeouts on selected goals, high
    plan_len on selected goals) so this is the actionable subset."""
    goal: str
    samples: int
    max_nodes: int
    avg_nodes: float
    max_plan_len: int
    avg_plan_len: float
    timeouts: int


@dataclass
class FightLoss:
    cycle: int
    ts: str
    hp: int
    max_hp: int
    monster: str


@dataclass
class StuckWindow:
    """A run of cycles where (task, progress, inventory) didn't change."""
    start_ts: str
    task_code: str | None
    progress: int
    inventory: int
    cycles: int


@dataclass
class TaskCompletion:
    task_code: str
    units: int
    duration_minutes: float


@dataclass
class TraceStats:
    """Aggregated session statistics. Fields scale to zero on empty input."""

    cycles: int = 0
    ts_first: str | None = None
    ts_last: str | None = None
    duration_minutes: float = 0.0

    outcomes: Counter[str] = field(default_factory=Counter)
    errors_by_action: Counter[tuple[str, str]] = field(default_factory=Counter)

    goal_runs: int = 0
    goal_changes: int = 0
    single_cycle_goals: Counter[str] = field(default_factory=Counter)
    selected_goals: Counter[str] = field(default_factory=Counter)

    actions: Counter[str] = field(default_factory=Counter)

    planner: list[GoalLoad] = field(default_factory=list)

    fight_attempts: int = 0
    fight_losses: list[FightLoss] = field(default_factory=list)

    craft_events: Counter[str] = field(default_factory=Counter)
    equip_events: int = 0
    delete_events: Counter[str] = field(default_factory=Counter)
    deposit_events: int = 0
    withdraw_events: Counter[str] = field(default_factory=Counter)

    task_completions: list[TaskCompletion] = field(default_factory=list)
    stuck_windows: list[StuckWindow] = field(default_factory=list)
    useless_repeats: int = 0


def _parse_iso(ts: str) -> datetime | None:
    """Robust ISO parser tolerant of trailing `Z`. Returns None on failure."""
    try:
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except ValueError:
        return None


def _parse_paren_qty(action: str, prefix: str) -> str | None:
    """`Prefix(code×N)` -> `code`; `Prefix(code)` -> `code`. None if no match."""
    if not action.startswith(prefix):
        return None
    inside = action[len(prefix):].rstrip(")")
    return inside.split("×", 1)[0] if "×" in inside else inside


def analyze(cycles: Iterable[Cycle]) -> TraceStats:
    """Single-pass aggregation over Cycle rows (typically already filtered by
    session / character / time window at the SQL layer)."""
    stats = TraceStats()
    per_goal_nodes: dict[str, list[int]] = {}
    per_goal_plen: dict[str, list[int]] = {}
    per_goal_timeouts: Counter[str] = Counter()

    cur_goal: str | None = None
    cur_goal_count = 0
    prev_action: str | None = None
    prev_state_key: tuple[int, int, str | None] | None = None
    task_start_ts: dict[str, str] = {}
    last_task_seen: str | None = None
    prev_progress: int | None = None
    stuck_key: tuple[str | None, int, int] | None = None
    stuck_count = 0
    stuck_start_ts: str | None = None

    for c in cycles:
        ts = c.ts
        if stats.ts_first is None:
            stats.ts_first = ts
        stats.ts_last = ts
        stats.cycles += 1

        outcome = c.outcome or "ok"
        stats.outcomes[outcome] += 1
        action = c.action_repr or ""
        stats.actions[action] += 1
        if outcome != "ok":
            stats.errors_by_action[(action, outcome)] += 1

        selected = c.selected_goal
        if selected is not None:
            stats.selected_goals[selected] += 1
        if selected == cur_goal:
            cur_goal_count += 1
        else:
            if cur_goal is not None:
                stats.goal_runs += 1
                if cur_goal_count == 1:
                    stats.single_cycle_goals[cur_goal] += 1
                stats.goal_changes += 1
            cur_goal = selected
            cur_goal_count = 1

        if selected is not None and c.planner_nodes is not None:
            per_goal_nodes.setdefault(selected, []).append(int(c.planner_nodes))
            per_goal_plen.setdefault(selected, []).append(int(c.plan_len or 0))
            if c.planner_timed_out:
                per_goal_timeouts[selected] += 1

        if action.startswith("Fight("):
            stats.fight_attempts += 1
            if outcome == "error:fight_lost":
                monster = _parse_paren_qty(action, "Fight(") or "?"
                stats.fight_losses.append(FightLoss(
                    cycle=int(c.cycle_index), ts=ts,
                    hp=int(c.hp or 0), max_hp=int(c.max_hp or 0),
                    monster=monster,
                ))

        code = _parse_paren_qty(action, "Craft(")
        if code is not None:
            stats.craft_events[code] += 1
        code = _parse_paren_qty(action, "Delete(")
        if code is not None:
            stats.delete_events[code] += 1
        code = _parse_paren_qty(action, "Withdraw(")
        if code is not None:
            stats.withdraw_events[code] += 1
        if action.startswith("Equip(") or action.startswith("OptimizeLoadout"):
            stats.equip_events += 1
        if action == "DepositAll":
            stats.deposit_events += 1

        tc = c.task_code
        tp = c.task_progress
        tt = c.task_total
        if tc and tc != last_task_seen:
            task_start_ts[tc] = ts
            last_task_seen = tc
        if (
            tc and isinstance(tp, int) and isinstance(tt, int) and tt > 0
            and prev_progress is not None and prev_progress < tt <= tp
        ):
            start = task_start_ts.get(tc)
            if start:
                t0 = _parse_iso(start)
                t1 = _parse_iso(ts)
                if t0 is not None and t1 is not None:
                    stats.task_completions.append(TaskCompletion(
                        task_code=tc, units=int(tt),
                        duration_minutes=(t1 - t0).total_seconds() / 60.0,
                    ))
        prev_progress = tp if isinstance(tp, int) else prev_progress

        iv = c.inventory_used
        sk = (tc, int(tp or 0), int(iv or 0))
        if sk == stuck_key:
            stuck_count += 1
        else:
            if stuck_count >= 8 and stuck_key is not None and stuck_start_ts is not None:
                stats.stuck_windows.append(StuckWindow(
                    start_ts=stuck_start_ts,
                    task_code=stuck_key[0], progress=stuck_key[1],
                    inventory=stuck_key[2], cycles=stuck_count,
                ))
            stuck_key = sk
            stuck_count = 1
            stuck_start_ts = ts
        prev_state_key_now = (int(iv or 0), int(tp or 0), tc)
        if action == prev_action and prev_state_key_now == prev_state_key:
            stats.useless_repeats += 1
        prev_action = action
        prev_state_key = prev_state_key_now

    if cur_goal is not None:
        stats.goal_runs += 1
        if cur_goal_count == 1:
            stats.single_cycle_goals[cur_goal] += 1
    if stuck_count >= 8 and stuck_key is not None and stuck_start_ts is not None:
        stats.stuck_windows.append(StuckWindow(
            start_ts=stuck_start_ts,
            task_code=stuck_key[0], progress=stuck_key[1],
            inventory=stuck_key[2], cycles=stuck_count,
        ))

    for g, nodes in per_goal_nodes.items():
        plens = per_goal_plen.get(g, [0])
        stats.planner.append(GoalLoad(
            goal=g, samples=len(nodes),
            max_nodes=max(nodes), avg_nodes=sum(nodes) / len(nodes),
            max_plan_len=max(plens), avg_plan_len=sum(plens) / len(plens),
            timeouts=per_goal_timeouts.get(g, 0),
        ))
    stats.planner.sort(key=lambda g: -g.max_nodes)

    if stats.ts_first and stats.ts_last:
        t0 = _parse_iso(stats.ts_first)
        t1 = _parse_iso(stats.ts_last)
        if t0 is not None and t1 is not None:
            stats.duration_minutes = (t1 - t0).total_seconds() / 60.0

    return stats


def load_cycles_from_db(
    db_path: str,
    character: str | None = None,
    session_id: str | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int | None = None,
) -> list[Cycle]:
    """Query Cycle rows from the SQLite store with optional filters.

    `session_id="last"` selects the most-recently-started session for the
    given character (or the whole DB if no character). Other filters
    narrow within the selected scope. Rows come back ordered by ts asc
    so the analyzer's per-cycle streaming logic works."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with SqlSession(engine) as s:
            resolved_session = session_id
            if session_id == "last":
                sess_q = select(Session.session_id).order_by(Session.started_at.desc())  # type: ignore[attr-defined]
                if character:
                    sess_q = sess_q.where(Session.character == character)
                row = s.exec(sess_q).first()
                resolved_session = row if row else None
                if resolved_session is None:
                    return []
            q = select(Cycle).order_by(asc(Cycle.ts))
            if character:
                q = q.where(Cycle.character == character)
            if resolved_session:
                q = q.where(Cycle.session_id == resolved_session)
            if since:
                q = q.where(Cycle.ts >= since)
            if until:
                q = q.where(Cycle.ts < until)
            if limit:
                q = q.limit(limit)
            return list(s.exec(q))
    finally:
        engine.dispose()


def list_sessions(db_path: str, character: str | None = None,
                  limit: int = 20) -> list[Session]:
    """List recent sessions for browsing in the CLI."""
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with SqlSession(engine) as s:
            q = select(Session).order_by(Session.started_at.desc())  # type: ignore[attr-defined]
            if character:
                q = q.where(Session.character == character)
            q = q.limit(limit)
            return list(s.exec(q))
    finally:
        engine.dispose()
