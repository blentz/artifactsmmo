"""Generate docs/craft_completeness/CONDITIONS.md: under which conditions each
recipe plans and what wins each of its fights (`audit/craft_conditions.py`;
docs/PLAN_drop_fight_loadout.md). `--check` fails on a recipe that plans
under no condition of the ladder (USER 2026-10-10 acceptance: "a complete
crafting census that identifies conditions required to successfully plan every
item")."""

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
_ACHIEVED: GameData | None = None


def _init_worker(bundle_dict: dict[str, Any]) -> None:
    global _GD, _ACHIEVED
    _GD = GameData.from_cache_bundle(bundle_dict)
    _ACHIEVED = GameData.from_cache_bundle(bundle_dict, completed_achievements=frozenset(
        str(a["code"]) for a in bundle_dict["achievements"]))


def _climb(recipe: str) -> ConditionsResult:
    assert _GD is not None and _ACHIEVED is not None  # set by _init_worker in every pool worker
    return climb(recipe, _GD, _ACHIEVED)


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
        # USER 2026-10-10 acceptance: a condition for EVERY recipe
        unplanned = [f"{r.recipe} ({r.result.gap})" for r in results if r.rung is None]
        if unplanned:
            print(f"CONDITIONS NOT COMPLETE: {len(unplanned)} recipe(s) plan under no condition: "
                  f"{unplanned}", file=sys.stderr)
            sys.exit(1)
        print("CONDITIONS COMPLETE: every recipe plans under a named condition.", file=sys.stderr)


if __name__ == "__main__":
    main()
