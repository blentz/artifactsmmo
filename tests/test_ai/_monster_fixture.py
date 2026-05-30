"""Test helper: complete monster stat fixtures.

Phase-9 fix: `GameData.monster_attack/resistance/hp/critical_strike/initiative`
now RAISE `KeyError` when the monster is unknown (CLAUDE.md "use only API
data or fail with an error" — silent zero defaults masked `predict_win`
returning True for any unknown monster).

The production `_load_monsters` always populates every stat dict atomically
for every monster code. Many test fixtures piggy-backed on the silent zero
default and only seeded `_monster_level` — that violated the production
invariant. This helper restores the invariant on demand from a fixture
that only sets `_monster_level`, defaulting unset stats to "harmless"
(zero HP / zero attack), preserving the historical fixture behavior in a
single line without re-hiding the bug.
"""

from artifactsmmo_cli.ai.game_data import GameData


def fill_monster_stat_defaults(gd: GameData) -> None:
    """Populate stat dicts with harmless defaults for every monster_level key.

    Mirrors the post-Phase-9 production invariant: every monster code present
    in `_monster_level` also has entries in every other stat dict. Tests
    that need specific stat values should set them explicitly BEFORE calling
    this helper; this only fills in the slots that have not been set."""
    for code in gd._monster_level:
        gd._monster_hp.setdefault(code, 0)
        gd._monster_attack.setdefault(code, {})
        gd._monster_resistance.setdefault(code, {})
        gd._monster_critical_strike.setdefault(code, 0)
        gd._monster_initiative.setdefault(code, 0)
        gd._monster_type.setdefault(code, "normal")
