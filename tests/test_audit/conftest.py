"""Shared audit-census fixtures: the REAL game catalog, from the committed
bundle snapshot (the same fixture the scenario suite plans against). The census
must run on real game data or fail — never a synthesized catalog."""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="session")
def bundle_game_data() -> GameData:
    """The committed live-API bundle as GameData. Session-scoped: GameData is
    read-only for the census and rebuilding it per test costs seconds."""
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))
