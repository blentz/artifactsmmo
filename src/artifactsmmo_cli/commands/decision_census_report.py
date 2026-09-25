"""`artifactsmmo decision-census` — read-only Phase 0 yardstick.

Prints `audit/decision_census.census` for each named character over one
wall-clock window of the learning DB, so every phase of
`docs/PLAN_decision_architecture_redesign.md` is measured the same way before
and after it ships. Reads `cycles` and `sessions` only; no API calls, no writes.
"""

from datetime import UTC, datetime, timedelta

import typer

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.audit.decision_census import CharacterCensus, census
from artifactsmmo_cli.learning_db_path import default_learn_db_path


def _pct(value: float | None) -> str:
    return "n/a" if value is None else f"{value:.1%}"


def _num(value: int | None) -> str:
    return "n/a" if value is None else str(value)


def _render(c: CharacterCensus) -> str:
    errors = ", ".join(f"{k}={v}" for k, v in sorted(c.error_classes.items(), key=lambda kv: -kv[1]))
    exits = ", ".join(f"{k}={v}" for k, v in sorted(c.session_exits.items()))
    mechanisms = ", ".join(f"{k}={v}" for k, v in sorted(c.mechanisms.items(), key=lambda kv: -kv[1]))
    return "\n".join([
        f"== {c.character} ==",
        f"  cycles {c.cycles} ({c.cycles_per_hour:.1f}/h)  ok {_pct(c.ok_share)}  "
        f"waits {c.wait_cycles}  longest same-failure streak {c.longest_failure_streak}",
        f"  errors: {errors or 'none'}",
        f"  LevelSkill share {_pct(c.level_skill_share)}  goal switches {_pct(c.goal_switch_share)}",
        f"  planner timed out {_pct(c.timed_out_share)}  nodes p50/p95/max "
        f"{_num(c.nodes_p50)}/{_num(c.nodes_p95)}/{_num(c.nodes_max)}",
        f"  char xp/h {c.char_xp_per_hour:.0f}  skill xp/h {c.skill_xp_per_hour:.0f}  "
        f"cooldown share {c.cooldown_share:.1%}",
        f"  sessions ended: {exits or 'none'}",
        f"  mechanisms: {mechanisms or 'none recorded'}",
    ])


def decision_census_command(
    characters: list[str] = typer.Argument(..., help="Characters to measure"),
    hours: float = typer.Option(24.0, help="Window length in hours"),
    until: str | None = typer.Option(
        None, help="Window end, ISO-8601 UTC (default: now)"),
) -> None:
    """Print the Phase 0 decision census for CHARACTERS over one window."""
    end = datetime.fromisoformat(until) if isinstance(until, str) else datetime.now(tz=UTC)
    start = end - timedelta(hours=hours)
    since, stop = start.isoformat(), end.isoformat()
    print(f"window {since} .. {stop} ({hours:g} h)")
    for character in characters:
        store = LearningStore(default_learn_db_path(), character=character)
        try:
            result = census(character, store.cycles_between(since, stop),
                            store.sessions_ended_between(since, stop),
                            store.decision_events_between(since, stop), hours)
        finally:
            store.close()
        print(_render(result))
