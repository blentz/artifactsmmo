"""`artifactsmmo macro-research` — read-only analysis of learning.db to find
recurring long-horizon progression chains and where A* search still costs."""

from pathlib import Path

import typer

from artifactsmmo_cli.ai.macro.cost import cost_by_goal_type
from artifactsmmo_cli.ai.macro.reader import load_cycle_rows
from artifactsmmo_cli.ai.macro.report import format_report, goal_repr_variants
from artifactsmmo_cli.ai.macro.scoring import score_candidates
from artifactsmmo_cli.ai.macro.segmentation import segment_bands


def _default_db_path() -> str:
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


def macro_research(
    db: str | None = typer.Option(None, "--db", help="learning.db path"),
    out: str | None = typer.Option(None, "--out", help="write report to file"),
    top_n: int = typer.Option(20, "--top-n", help="macro candidates to show"),
) -> None:
    path = db or _default_db_path()
    if not Path(path).exists():
        raise typer.BadParameter(f"learning.db not found: {path}")
    rows = load_cycle_rows(path)
    cost = cost_by_goal_type(rows)
    bands = segment_bands(rows, "level") + segment_bands(rows, "skill")
    candidates = score_candidates(bands)
    report = format_report(cost, candidates, goal_repr_variants(rows), top_n)
    if out is not None:
        Path(out).write_text(report)
        print(f"Wrote macro-research report to {out} "
              f"({len(rows)} cycles, {len(candidates)} candidate chains)")
    else:
        print(report)
