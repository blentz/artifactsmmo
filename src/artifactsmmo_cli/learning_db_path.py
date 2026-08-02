"""The default on-disk location for the learning/coordination SQLite DB.

Extracted so `multi/multi_run.py` can reuse the SAME default `commands/play.py`
uses (when `--learn` is on, coordination reuses the learning DB path rather
than creating a temp file — see `MultiRun._prepare_coordination_db_path`)
without `multi_run.py` importing `commands/play.py`, which already imports
`MultiRun` and would make that a cycle.
"""

from pathlib import Path


def default_learn_db_path() -> str:
    """Return ~/.cache/artifactsmmo/learning.db (parent dirs created on first use)."""
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")
