"""Diagnostic: partition the census PLANNER_BUG cells into artifacts vs genuine
planner defects. For every empty-plan cell it records at/under-skill, elapsed
(fast-fail vs 10s budget wall), the directed-generator result, and is_plannable.
Parallel. NOT a shipped module — an investigation aid."""

import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.craft_plan_gen import generate_next_craft_action
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.audit.craft_census import craftable_recipes
from artifactsmmo_cli.audit.craft_completeness import (
    CraftCell, GapClass, census_state, classify_gap, craft_cell_verdict,
    craft_grid, plan_craft,
)

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")
_GD: GameData | None = None


def _init(bd: dict) -> None:
    global _GD
    _GD = GameData.from_cache_bundle(bd)


def _diag(work: tuple[str, CraftCell]) -> dict:
    recipe, cell = work
    gd = _GD
    assert gd is not None
    stats = gd.item_stats(recipe)
    craft = stats.crafting_level
    state = census_state(recipe, cell, gd)
    t0 = time.monotonic()
    plan = plan_craft(recipe, state, gd)
    el = time.monotonic() - t0
    verdict = craft_cell_verdict(recipe, plan, gd)
    if verdict.passed:
        return {"passed": True}
    # Only PLANNER_BUG-classified cells are candidate defects; the rest are
    # event/combat/material/skill gaps (expected, not planner bugs).
    if classify_gap(recipe, cell, gd) is not GapClass.PLANNER_BUG:
        return {"passed": True}
    # planner_bug cell: characterize
    objective = CharacterObjective.from_game_data(gd)
    actions = build_actions(gd, state, objective, bank_accessible=True,
                            task_exchange_min_coins=0)
    goal = GatherMaterialsGoal(target_item=recipe, needed={recipe: 1})
    gen = generate_next_craft_action(goal, state, gd, actions)
    plannable = goal.is_plannable(state, gd)
    return {
        "passed": False,
        "recipe": recipe,
        "skill": cell.skill_name,
        "craft": craft,
        "cell_skill": cell.skill_level,
        "char": cell.char_level,
        "at_skill": cell.skill_level >= craft,
        "elapsed": round(el, 2),
        "timeout": el >= 8.0,
        "gen": None if gen is None else [repr(a) for a in gen],
        "plannable": plannable,
    }


def main() -> None:
    workers = int(sys.argv[1]) if len(sys.argv) > 1 else (os.cpu_count() or 4)
    bd = json.loads(BUNDLE.read_text())
    gd = GameData.from_cache_bundle(bd)
    work = [(r, c) for r in craftable_recipes(gd) for c in craft_grid(r, gd)]
    with ProcessPoolExecutor(max_workers=workers, initializer=_init, initargs=(bd,)) as ex:
        res = list(ex.map(_diag, work, chunksize=1))
    bugs = [r for r in res if not r["passed"]]
    print(f"total cells={len(res)} empty-plan={len(bugs)}")
    # partitions
    under = [b for b in bugs if not b["at_skill"]]
    at = [b for b in bugs if b["at_skill"]]
    at_fast = [b for b in at if not b["timeout"]]
    at_timeout = [b for b in at if b["timeout"]]
    at_gen_none = [b for b in at if b["gen"] is None]
    print(f"UNDER-SKILL (artifact: production routes skill-grind): {len(under)}")
    print(f"AT-SKILL total: {len(at)}  (fast<8s={len(at_fast)}, timeout>=8s={len(at_timeout)}, gen=None={len(at_gen_none)})")
    print("\n=== AT-SKILL FAST-FAIL (clear candidates — plannable? gen?) ===")
    for b in sorted(at_fast, key=lambda x: (x["recipe"], x["char"]))[:40]:
        print(f"  {b['recipe']} {b['char']}/{b['cell_skill']} craft={b['craft']} plannable={b['plannable']} gen={b['gen']} el={b['elapsed']}")
    print("\n=== AT-SKILL TIMEOUT with gen=None (generator gap → A* timeout) — recipes ===")
    seen = {}
    for b in at_timeout:
        if b["gen"] is None:
            seen[b["recipe"]] = seen.get(b["recipe"], 0) + 1
    for r, n in sorted(seen.items()):
        print(f"  {r}: {n} cells")


if __name__ == "__main__":
    main()
