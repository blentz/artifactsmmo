"""Generate the full band table for character base stats (levels 1..49).

Single responsibility: write ``formal/sim/character_base_stats.json`` from the
game's deterministic base-stat rule, live-validated at two anchor points.

## Formula

    max_hp = 115 + 5 * level

Live anchors (verified by algebraic capture against the real API):
  * Level 1: max_hp = 120 = 115 + 5×1  (game-start value, publicly documented)
  * Level 6: max_hp = 145 = 115 + 5×6  (algebraic capture: character totals
    minus item effects, performed 2026-06-20 by capture_base_stats.py)

All other base combat stats are level-invariant:
  * attack = {fire:0, earth:0, water:0, air:0}  (base chars have no innate
    elemental attack; all attack comes from gear)
  * resistance = {fire:0, earth:0, water:0, air:0}
  * critical_strike = 0
  * initiative = 100

## Honest framing

This is NOT a 49-point physical capture (Robby is level 6; unequipping at 49
levels is impractical). It is a fully-derived table from the formula above,
live-validated at level 6 (algebraic capture) and level 1 (game start).

Usage::

    ~/.local/bin/uv run python formal/sim/generate_base_stats_table.py [output_path]

Default output: formal/sim/character_base_stats.json  (overwrites in full).
"""

import json
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Level band and formula constants
# ---------------------------------------------------------------------------

BAND_LO = 1
BAND_HI = 50  # exclusive — levels 1..49 inclusive

# max_hp = HP_BASE + HP_PER_LEVEL * level
HP_BASE = 115
HP_PER_LEVEL = 5

# Live-validated anchors used for in-code documentation and written into the
# provenance block so downstream readers can verify the formula.
LIVE_ANCHOR_LEVEL_1 = {"level": 1, "max_hp": 120, "source": "game_start"}
LIVE_ANCHOR_LEVEL_6 = {
    "level": 6,
    "max_hp": 145,
    "source": "algebraic_subtraction_from_equipped_character_stats",
    "captured_at": "2026-06-20T15:31:40.332273+00:00",
}

_DEFAULT_OUTPUT = Path(__file__).resolve().parent / "character_base_stats.json"


def _make_row(level: int) -> dict[str, Any]:
    """Derive one base-stats row for ``level`` from the game formula."""
    return {
        "max_hp": HP_BASE + HP_PER_LEVEL * level,
        "attack": {"fire": 0, "earth": 0, "water": 0, "air": 0},
        "resistance": {"fire": 0, "earth": 0, "water": 0, "air": 0},
        "critical_strike": 0,
        "initiative": 100,
    }


def generate_table() -> dict[str, Any]:
    """Return the full document: provenance + all rows for levels 1..49.

    The returned dict is ready to JSON-serialise and write to disk.
    """
    base_stats = {str(lvl): _make_row(lvl) for lvl in range(BAND_LO, BAND_HI)}
    return {
        "provenance": {
            "description": (
                "Per-level base stats derived from the documented base-hp rule "
                "max_hp=115+5*level with level-invariant zero base combat stats "
                "(attack/resistance/critical_strike) and initiative=100. "
                "NOT a 49-point physical capture."
            ),
            "formula": "max_hp = 115 + 5 * level",
            "live_anchors": [LIVE_ANCHOR_LEVEL_1, LIVE_ANCHOR_LEVEL_6],
            "combat_stats": {
                "attack": "zero at all levels (all attack comes from gear)",
                "resistance": "zero at all levels (all resistance comes from gear)",
                "critical_strike": 0,
                "initiative": 100,
            },
        },
        "base_stats": base_stats,
    }


def write_table(output_path: Path = _DEFAULT_OUTPUT) -> None:
    """Generate the full 1..49 table and write it to ``output_path``."""
    document = generate_table()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True))


def main() -> None:
    output_path = Path(sys.argv[1]) if len(sys.argv) > 1 else _DEFAULT_OUTPUT
    write_table(output_path)
    doc = json.loads(output_path.read_text())
    bs = doc["base_stats"]
    anchors = ", ".join(
        f"L{a['level']}={bs[str(a['level'])]['max_hp']}"
        for a in doc["provenance"]["live_anchors"]
    )
    print(
        f"Generated {len(bs)} rows (levels {BAND_LO}..{BAND_HI - 1}). "
        f"Anchor check: {anchors}. -> {output_path}"
    )


if __name__ == "__main__":
    main()
