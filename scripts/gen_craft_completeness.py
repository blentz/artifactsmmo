"""Generate docs/craft_completeness/{MATRIX,BACKLOG}.md from the committed
bundle by running the Phase-1 census over every craftable recipe.

Offline + deterministic (no live API): loads
tests/test_ai/scenarios/fixtures/gamedata_bundle.json. Serial run is ~50 min
(~1758 cells, ~16% hit the 10 s planner budget). Run:

    uv run python scripts/gen_craft_completeness.py
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import craftable_recipes, run_census
from artifactsmmo_cli.audit.craft_report import (
    render_backlog,
    render_matrix,
    summary_line,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT_DIR = Path("docs/craft_completeness")
_START = 0.0


def _progress(done: int, total: int, recipe: str) -> None:
    elapsed = time.monotonic() - _START
    print(f"[{done}/{total}] {elapsed:6.0f}s {recipe}", file=sys.stderr)


def main() -> None:
    global _START
    gd = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    _START = time.monotonic()
    results = run_census(gd, craftable_recipes(gd), progress=_progress)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "MATRIX.md").write_text(render_matrix(results))
    (OUT_DIR / "BACKLOG.md").write_text(render_backlog(results))
    print(summary_line(results))


if __name__ == "__main__":
    main()
