"""Unit tests for formal/sim/generate_base_stats_table.py.

Pins the max_hp formula (115 + 5*level), the two live-validated anchors
(L1=120, L6=145), and the level-invariant zero combat stats / initiative=100
so game-rule drift is caught.

The module under test lives outside the normal src/ tree; import it via
importlib (same pattern as test_capture_base_stats.py).
"""

import importlib.util
import json
from pathlib import Path

from artifactsmmo_cli.ai.scenario import base_combat_stats

_MODULE_PATH = (
    Path(__file__).resolve().parents[2]
    / "formal"
    / "sim"
    / "generate_base_stats_table.py"
)
_spec = importlib.util.spec_from_file_location("generate_base_stats_table", _MODULE_PATH)
assert _spec is not None and _spec.loader is not None
generate_base_stats_table = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(generate_base_stats_table)


def test_table_has_all_band_levels() -> None:
    """The generated table must contain exactly levels 1..49 (all 49 keys)."""
    doc = generate_base_stats_table.generate_table()
    base_stats = doc["base_stats"]
    expected_keys = {str(lvl) for lvl in range(1, 50)}
    assert set(base_stats.keys()) == expected_keys
    assert len(base_stats) == 49


def test_max_hp_follows_formula() -> None:
    """max_hp = 115 + 5 * level for every level in the band."""
    doc = generate_base_stats_table.generate_table()
    base_stats = doc["base_stats"]
    for level in range(1, 50):
        row = base_stats[str(level)]
        expected = 115 + 5 * level
        assert row["max_hp"] == expected, (
            f"level {level}: expected max_hp {expected}, got {row['max_hp']}"
        )


def test_live_anchor_level_1() -> None:
    """Level 1 must have max_hp=120 (game-start value, live anchor)."""
    doc = generate_base_stats_table.generate_table()
    assert doc["base_stats"]["1"]["max_hp"] == 120


def test_live_anchor_level_6() -> None:
    """Level 6 must have max_hp=145 (algebraic capture live anchor)."""
    doc = generate_base_stats_table.generate_table()
    assert doc["base_stats"]["6"]["max_hp"] == 145


def test_the_2026_10_31_live_anchors_match_their_rows() -> None:
    """Every read-only capture of 2026-10-31 (a live sheet less its worn gear,
    review M2: each value measured per character) is its own subtraction, and
    agrees with the derived row at its level (max_hp, initiative, crit,
    attack, resistance) and with the level-invariant `combat_stats` block the
    scenario harness reads (`scenario.base_combat_stats`)."""
    doc = generate_base_stats_table.generate_table()
    combat = doc["provenance"]["combat_stats"]
    anchors = [a for a in doc["provenance"]["live_anchors"] if a.get("captured_at") == "2026-10-31"]
    assert sorted(a["character"] for a in anchors) == ["C3P0", "HAL", "Lor", "R2D2", "Robby"]
    for anchor in anchors:
        for stat in ("initiative", "max_hp", "critical_strike"):
            assert anchor["sheet"][stat] - anchor["gear"][stat] == anchor[stat], anchor["character"]
        row = doc["base_stats"][str(anchor["level"])]
        assert (row["max_hp"], row["initiative"], row["critical_strike"]) == (
            anchor["max_hp"], anchor["initiative"], anchor["critical_strike"])
        assert (row["attack"], row["resistance"]) == (anchor["attack"], anchor["resistance"])
        assert (combat["initiative"], combat["critical_strike"]) == (
            anchor["initiative"], anchor["critical_strike"])
        assert base_combat_stats() == (anchor["initiative"], anchor["critical_strike"])


def test_combat_stats_zero_and_initiative_100() -> None:
    """attack and resistance are all-zero; critical_strike=0; initiative=100 at sampled levels."""
    doc = generate_base_stats_table.generate_table()
    base_stats = doc["base_stats"]
    elements = {"fire", "earth", "water", "air"}
    # Check at sampled levels: 1, 6, 25, 49
    for level in (1, 6, 25, 49):
        row = base_stats[str(level)]
        for elem in elements:
            assert row["attack"][elem] == 0, f"L{level} attack.{elem} != 0"
            assert row["resistance"][elem] == 0, f"L{level} resistance.{elem} != 0"
        assert row["critical_strike"] == 0, f"L{level} critical_strike != 0"
        assert row["initiative"] == 100, f"L{level} initiative != 100"


def test_provenance_block_present() -> None:
    """The document must contain a provenance block with the formula + anchors."""
    doc = generate_base_stats_table.generate_table()
    prov = doc["provenance"]
    assert "formula" in prov
    assert prov["formula"] == "max_hp = 115 + 5 * level"
    anchors = prov["live_anchors"]
    anchor_levels = {a["level"] for a in anchors}
    assert 1 in anchor_levels
    assert 6 in anchor_levels


def test_write_table_produces_valid_json(tmp_path: Path) -> None:
    """write_table writes a valid JSON file with the expected shape."""
    out = tmp_path / "stats.json"
    generate_base_stats_table.write_table(out)
    doc = json.loads(out.read_text())
    assert "base_stats" in doc
    assert "provenance" in doc
    assert len(doc["base_stats"]) == 49
    # Spot-check L6 from disk.
    assert doc["base_stats"]["6"]["max_hp"] == 145
