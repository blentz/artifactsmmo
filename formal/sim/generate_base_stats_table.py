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
live-validated at level 6 (algebraic capture) and level 1 (game start), and
on 2026-10-31 by read-only algebraic capture of all five fleet characters at
levels 36-41 (`LIVE_ANCHORS_2026_10_31`: initiative 100 and max_hp
115 + 5 * level on every one).

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
# Read-only algebraic captures, 2026-10-31: each live sheet (GET
# /characters/{name}) less the catalogue stats of every worn non-utility piece
# (the bundle's item stats). Each value is written as measured, per character:
# `sheet` is the live total, `gear` the worn pieces' sum, and the base the
# difference. Attack and resistance read 0 on every element after the
# subtraction, recorded per character.
_ZERO_ELEMENTS = {"fire": 0, "earth": 0, "water": 0, "air": 0}
LIVE_ANCHORS_2026_10_31 = [
    {"character": "Robby", "level": 41, "captured_at": "2026-10-31",
     "source": "algebraic_subtraction_from_equipped_character_stats",
     "sheet": {"initiative": 330, "max_hp": 845, "critical_strike": 38},
     "gear": {"initiative": 230, "max_hp": 525, "critical_strike": 38},
     "initiative": 100, "max_hp": 320, "critical_strike": 0,
     "attack": dict(_ZERO_ELEMENTS), "resistance": dict(_ZERO_ELEMENTS)},
    {"character": "R2D2", "level": 37, "captured_at": "2026-10-31",
     "source": "algebraic_subtraction_from_equipped_character_stats",
     "sheet": {"initiative": 330, "max_hp": 1040, "critical_strike": 28},
     "gear": {"initiative": 230, "max_hp": 740, "critical_strike": 28},
     "initiative": 100, "max_hp": 300, "critical_strike": 0,
     "attack": dict(_ZERO_ELEMENTS), "resistance": dict(_ZERO_ELEMENTS)},
    {"character": "C3P0", "level": 36, "captured_at": "2026-10-31",
     "source": "algebraic_subtraction_from_equipped_character_stats",
     "sheet": {"initiative": 250, "max_hp": 945, "critical_strike": 14},
     "gear": {"initiative": 150, "max_hp": 650, "critical_strike": 14},
     "initiative": 100, "max_hp": 295, "critical_strike": 0,
     "attack": dict(_ZERO_ELEMENTS), "resistance": dict(_ZERO_ELEMENTS)},
    {"character": "HAL", "level": 39, "captured_at": "2026-10-31",
     "source": "algebraic_subtraction_from_equipped_character_stats",
     "sheet": {"initiative": 305, "max_hp": 880, "critical_strike": 18},
     "gear": {"initiative": 205, "max_hp": 570, "critical_strike": 18},
     "initiative": 100, "max_hp": 310, "critical_strike": 0,
     "attack": dict(_ZERO_ELEMENTS), "resistance": dict(_ZERO_ELEMENTS)},
    {"character": "Lor", "level": 36, "captured_at": "2026-10-31",
     "source": "algebraic_subtraction_from_equipped_character_stats",
     "sheet": {"initiative": 410, "max_hp": 1075, "critical_strike": 24},
     "gear": {"initiative": 310, "max_hp": 780, "critical_strike": 24},
     "initiative": 100, "max_hp": 295, "critical_strike": 0,
     "attack": dict(_ZERO_ELEMENTS), "resistance": dict(_ZERO_ELEMENTS)},
]

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
            "live_anchors": [LIVE_ANCHOR_LEVEL_1, LIVE_ANCHOR_LEVEL_6, *LIVE_ANCHORS_2026_10_31],
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
