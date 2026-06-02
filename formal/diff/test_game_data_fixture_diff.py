"""Differential: assert live game_data matches the snapshot pinned in
the Lean fixture (Phase 24-fix).

Reads `formal/sim/game_data_snapshot.json` (captured by
`snapshot_game_data.py`) and compares against the current live API.

Skips if the server is unreachable (network errors only). FAILS if the
server returns data that disagrees with the snapshot — indicating the
snapshot is stale and the Lean fixture must be regenerated.
"""

import json
from pathlib import Path

import httpx
import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

SNAPSHOT_PATH = (
    Path(__file__).resolve().parents[1] / "sim" / "game_data_snapshot.json"
)


def _load_snapshot() -> dict:
    return json.loads(SNAPSHOT_PATH.read_text())


def _load_live() -> GameData:
    try:
        cfg = Config.from_token_file()
    except ValueError as e:
        pytest.skip(f"no token: {e}")
    mgr = ClientManager()
    try:
        mgr.initialize(cfg)
        return GameData.load(mgr.client)
    except (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout,
            httpx.HTTPError) as e:
        pytest.skip(f"server unreachable: {e}")


def test_snapshot_recipes_match_live() -> None:
    snapshot = _load_snapshot()
    live = _load_live()
    snap_recipes = snapshot["crafting_recipes"]
    live_recipes = {k: dict(v) for k, v in live._crafting_recipes.items()}
    assert snap_recipes == live_recipes, (
        f"Snapshot drift: recipes diverge from live API. Regenerate via "
        f"`uv run python formal/sim/snapshot_game_data.py`. "
        f"Snapshot count: {len(snap_recipes)}, live count: {len(live_recipes)}."
    )


def test_snapshot_monster_levels_match_live() -> None:
    snapshot = _load_snapshot()
    live = _load_live()
    snap_levels = snapshot["monster_level"]
    live_levels = dict(live._monster_level)
    assert snap_levels == live_levels, (
        "Snapshot drift: monster_level diverges from live API."
    )


def test_snapshot_resource_skills_match_live() -> None:
    snapshot = _load_snapshot()
    live = _load_live()
    snap_skills = {k: tuple(v) for k, v in snapshot["resource_skill"].items()}
    live_skills = dict(live._resource_skill)
    assert snap_skills == live_skills, (
        "Snapshot drift: resource_skill diverges from live API."
    )


def test_snapshot_recipe_dag_acyclic() -> None:
    """The Lean fixture computes craftDepth via topological sort. Verify
    the snapshot's recipe DAG is genuinely acyclic by running the sort."""
    snapshot = _load_snapshot()
    recipes = snapshot["crafting_recipes"]
    depth: dict[str, int] = {}
    all_codes = set(recipes.keys())
    for ings in recipes.values():
        all_codes.update(ings.keys())
    for code in all_codes:
        if code not in recipes:
            depth[code] = 0
    changed = True
    iterations = 0
    while changed and iterations < 50:
        changed = False
        iterations += 1
        for code, ings in recipes.items():
            if code in depth:
                continue
            if all(ing in depth for ing in ings):
                depth[code] = max(depth[ing] for ing in ings) + 1
                changed = True
    missing = [c for c in recipes if c not in depth]
    assert not missing, (
        f"Recipe DAG has cycles or chains deeper than 50: {missing[:5]}"
    )


def test_snapshot_recipe_count_matches_lean_fixture() -> None:
    """The Lean fixture's snapshot_recipe_count theorem asserts an exact
    count via `rfl`. Verify the JSON snapshot matches that pinned count
    by parsing the Lean file."""
    snapshot = _load_snapshot()
    fixture_lean = (
        Path(__file__).resolve().parents[1]
        / "Formal" / "Liveness" / "GameDataFixture.lean"
    ).read_text()
    # Find "theorem snapshot_recipe_count : allRecipes.length = N"
    import re
    m = re.search(r"snapshot_recipe_count.*?length\s*=\s*(\d+)", fixture_lean)
    assert m, "Could not find snapshot_recipe_count theorem in Lean fixture"
    pinned = int(m.group(1))
    snap_count = len(snapshot["crafting_recipes"])
    assert pinned == snap_count, (
        f"Lean fixture pins {pinned} recipes; snapshot has {snap_count}. "
        f"Regenerate the Lean fixture: "
        f"`uv run python formal/sim/generate_lean_fixture.py`."
    )
