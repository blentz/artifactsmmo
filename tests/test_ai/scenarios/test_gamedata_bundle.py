"""GameData.from_cache_bundle: the offline real-catalog loader scenarios use.

The committed bundle is a copy of the live disk cache (regen: run any CLI
command to refresh ~/.cache/artifactsmmo/gamedata-*.json, then re-copy —
same drill as formal/sim snapshot regen)."""

import json
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData

BUNDLE = Path(__file__).parent / "fixtures" / "gamedata_bundle.json"


def _load() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def test_bundle_builds_real_catalog() -> None:
    gd = _load()
    # Spot-checks against known live facts (stable game data):
    assert gd.crafting_recipe("satchel") == {
        "cowhide": 5, "feather": 2, "jasper_crystal": 1}
    assert gd.monster_level("chicken") == 1
    assert gd.npc_purchases("jasper_crystal") == [("tasks_trader", 8, "tasks_coin")]
    assert gd.bank_location() is not None
    assert gd.taskmaster_location() is not None


def test_bundle_ge_orders_empty() -> None:
    gd = _load()
    assert gd.ge_best_buy_order("copper_ore") is None
