"""Differential (C0a): production's combat-xp positivity verdict ≡ proven gate.

Production targeting gates on ``xp_per_kill(code, level) > 0`` (player.py:1574
→ combat_picker), computed through the FLOAT xp formula in
``monster_catalog.xp_per_kill`` (level_penalty bands + type multiplier +
wisdom bonus + round). The Lean core ``Formal.XpPositive.xpPositiveGate``
proves the verdict is EXACTLY the integer band ``1 ≤ monster_level ∧
char_level < monster_level + 10`` — this harness pins the real float path to
the proven gate over random catalogs (levels, hp, type, wisdom), including the
out-of-band, unknown-monster (level 0), and band-edge cases. Kills the
XP_POSITIVE mutation group in mutate.py.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.monster_catalog import MonsterCatalog
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=80),
    monster_level=st.integers(min_value=0, max_value=80),
    monster_hp=st.integers(min_value=0, max_value=3000),
    mtype=st.sampled_from(["normal", "elite", "boss"]),
    wisdom=st.integers(min_value=0, max_value=300),
)
def test_xp_positive_python_matches_lean(char_level, monster_level, monster_hp, mtype, wisdom):
    catalog = MonsterCatalog(
        levels={"m": monster_level},
        hp={"m": monster_hp},
        types={"m": mtype},
    )
    py = catalog.xp_per_kill("m", char_level, wisdom) > 0
    lean = run_oracle("xp_positive", [[char_level, monster_level]])[0]
    assert py == lean["positive"], (char_level, monster_level, monster_hp, mtype, wisdom, py, lean)


def test_band_edges_exact():
    """DETERMINISTIC edge sweep: the gate flips exactly at diff = 10. Random
    sampling missed the edge once and let a `>= 11` mutant survive — every
    boundary-adjacent diff is enumerated here for a spread of monster levels
    and hp values (including hp = 0, where only the level term pays)."""
    cases = []
    for monster_level in (1, 4, 11, 27, 40):
        for diff in (-2, 0, 4, 5, 9, 10, 11, 20):
            char_level = monster_level + diff
            if char_level < 1:
                continue
            for hp in (0, 50, 2000):
                cases.append((char_level, monster_level, hp))
    batch = [[c, m] for (c, m, _hp) in cases]
    leans = run_oracle("xp_positive", batch)
    for (char_level, monster_level, hp), lean in zip(cases, leans):
        catalog = MonsterCatalog(
            levels={"m": monster_level}, hp={"m": hp}, types={"m": "normal"},
        )
        expected = char_level < monster_level + 10
        assert (catalog.xp_per_kill("m", char_level) > 0) == expected, (
            char_level, monster_level, hp)
        assert lean["positive"] == expected, (char_level, monster_level)
