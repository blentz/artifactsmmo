"""Shared pytest fixtures for the test_ai package."""

import pytest
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.scenario import load_bundle_game_data


@pytest.fixture
def make_planner_gd() -> GameData:
    """Return a minimal GameData with empty dicts so the planner can run with zero actions."""
    return GameData()


_BUNDLE = (Path(__file__).resolve().parents[1]
           / "test_ai" / "scenarios" / "fixtures" / "gamedata_bundle.json")


@pytest.fixture
def bundle_game_data():
    """The committed game-data bundle — the same fixture the scenario harness
    and the `plan --scenario` diagnostic load."""
    return load_bundle_game_data(_BUNDLE)
