"""Generate docs/behavioral_completeness/JOINT_WALK_MATRIX.md: the joint-walk
census (Phase 2d-L1), offline over the committed bundle.

Report-only. It counts where the joint walk corrects the replaced independent
walk (SHARED_SHORTAGE) and where the greedy walk misses an answer an exact
search finds (GREEDY_FALSE_NEGATIVE); neither is gated, since the greedy
contract accepts false negatives.

    uv run python scripts/gen_joint_walk.py
"""

import json
import sys
import time
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.joint_walk_census import render_matrix, run_census, summary_line

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT = Path("docs/behavioral_completeness/JOINT_WALK_MATRIX.md")


def main() -> None:
    game_data = GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
    start = time.monotonic()
    cells = run_census(game_data)
    OUT.write_text(render_matrix(cells))
    print(f"census done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(cells))


if __name__ == "__main__":
    main()
