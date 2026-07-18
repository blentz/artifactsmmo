"""Shared audit-census fixtures: the REAL game catalog, from the committed
bundle snapshot (the same fixture the scenario suite plans against). The census
must run on real game data or fail — never a synthesized catalog."""

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.audit.inventory_census import CellResult, run_census
from artifactsmmo_cli.audit.inventory_completeness import InventoryCell, inventory_grid

BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="session")
def bundle_game_data() -> GameData:
    """The committed live-API bundle as GameData. Session-scoped: GameData is
    read-only for the census and rebuilding it per test costs seconds."""
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


@dataclass(frozen=True)
class FullCensus:
    """One full-grid census run, shared across every test that asserts a
    property of it. `progress` is the ordered `(done, total)` sequence the run
    emitted, so the progress-ordering test reads it without a second run."""

    results: list[CellResult]
    cells: list[InventoryCell]
    progress: list[tuple[int, int]]


@pytest.fixture(scope="session")
def full_census(bundle_game_data: GameData) -> FullCensus:
    """The whole 152-cell census, computed ONCE per session. Every full-grid
    census test asserts a different property of the SAME result set, so a single
    (internally parallel) run replaces five identical ~4-minute recomputations —
    the suite's dominant cost. Captures the progress callback so the ordering
    test needs no separate run."""
    cells = inventory_grid(bundle_game_data)
    progress: list[tuple[int, int]] = []
    results = run_census(bundle_game_data, cells, progress=lambda d, t: progress.append((d, t)))
    return FullCensus(results=results, cells=cells, progress=progress)
