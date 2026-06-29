"""`artifactsmmo combat-loadout-report` — read-only predict_win calibration report.

Cross-character: loads ALL CombatLoadoutOutcome rows (no character filter) so the
report spans every character in the db, matching macro-research's cross-character
behavior. Read-only diagnostics; no bot behavior changed.
"""

import json
from pathlib import Path

import typer
from sqlmodel import Session as SqlSession
from sqlmodel import create_engine, select

from artifactsmmo_cli.ai.learning.models import CombatLoadoutOutcome
from artifactsmmo_cli.ai.learning.store import CombatLoadoutOutcomeRow
from artifactsmmo_cli.ai.macro.loadout_calibration import loadout_calibration_report


def _default_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def _load_all_outcome_rows(db_path: str) -> list[CombatLoadoutOutcomeRow]:
    """Load ALL CombatLoadoutOutcome rows across all characters, insertion order.

    Cross-character: no character filter, matching macro-research's all-character
    behavior in reader.load_cycle_rows.
    """
    engine = create_engine(f"sqlite:///{db_path}")
    try:
        with SqlSession(engine) as s:
            rows = s.exec(select(CombatLoadoutOutcome)).all()
        return [
            CombatLoadoutOutcomeRow(
                character=r.character,
                task_key=r.task_key,
                loadout=json.loads(r.loadout),
                predicted_win=r.predicted_win,
                actual_win=r.actual_win,
            )
            for r in rows
        ]
    finally:
        engine.dispose()


def combat_loadout_report_command(
    db: str | None = typer.Option(None, "--db", help="learning.db path"),
    out: str | None = typer.Option(None, "--out", help="write report to file"),
) -> None:
    path = db or _default_db_path()
    if not Path(path).exists():
        raise typer.BadParameter(f"learning.db not found: {path}")
    rows = _load_all_outcome_rows(path)
    report = loadout_calibration_report(rows)
    if out is not None:
        Path(out).write_text(report)
        print(f"Wrote combat-loadout-report to {out} ({len(rows)} fight outcomes)")
    else:
        print(report)
