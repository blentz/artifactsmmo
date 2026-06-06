"""Shared pytest fixtures for the test_ai package."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData


@pytest.fixture
def make_planner_gd() -> GameData:
    """Return a minimal GameData with empty dicts so the planner can run with zero actions."""
    return GameData()
