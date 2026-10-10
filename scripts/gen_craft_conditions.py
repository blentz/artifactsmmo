"""Generate docs/craft_completeness/CONDITIONS.md: under which conditions each
recipe plans and what wins each of its fights (`audit/craft_conditions.py`;
docs/PLAN_drop_fight_loadout.md increment 2). `--check` fails on a recipe
whose top rung is a PLANNER_BUG: a level-50 character with every skill, gold
and the events, every leaf reachable, and still no plan."""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path
from typing import Any

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.craft_census import craftable_recipes
from artifactsmmo_cli.audit.craft_conditions import ConditionsResult, climb, render_conditions, summary_line

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
OUT = Path("docs/craft_completeness/CONDITIONS.md")

_GD: GameData | None = None


def _init_worker(bundle_dict: dict[str, Any]) -> None:
    global _GD
    _GD = GameData.from_cache_bundle(bundle_dict)


def _climb(recipe: str) -> ConditionsResult:
    assert _GD is not None  # set by _init_worker in every pool worker
    return climb(recipe, _GD)


def main() -> None:
    check = "--check" in sys.argv[1:]
    bundle_dict = json.loads(BUNDLE.read_text())
    recipes = craftable_recipes(GameData.from_cache_bundle(bundle_dict))
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=os.cpu_count() or 4, initializer=_init_worker,
                             initargs=(bundle_dict,)) as ex:
        results = list(ex.map(_climb, recipes, chunksize=1))
    OUT.write_text(render_conditions(results))
    print(f"conditions done in {time.monotonic() - start:.0f}s", file=sys.stderr)
    print(summary_line(results))
    if check:
        bugs = [r.recipe for r in results if r.rung is None and r.result.gap == "planner_bug"]
        if bugs:
            print(f"CONDITIONS NOT CLEAN: {len(bugs)} PLANNER_BUG recipe(s): {bugs}", file=sys.stderr)
            sys.exit(1)
        print("CONDITIONS CLEAN: 0 PLANNER_BUG recipes.", file=sys.stderr)


if __name__ == "__main__":
    main()
