"""Differential (C0b): production's exact xp VALUE ≡ proven Lean mirror, bit for bit.

`monster_catalog.xp_per_kill` was refactored to exact integer arithmetic
(round-half-even on one rational num/den — the old float path differed at
12/17400 grid points, all ±1 at half-integer ties). `Formal.XpValue.xpPerKill`
is the proven mirror; this harness pins them bit-identically over random
inputs, PLUS a deterministic sweep of the level-penalty boundaries and
engineered rounding ties (the C0a lesson: edges are enumerated, never left to
sampling). The type→mult10 map is exercised by driving production with the
type STRING and the oracle with the derived mult10. Kills the XP_VALUE
mutation group in mutate.py.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.monster_catalog import MonsterCatalog
from formal.diff.oracle_client import run_oracle

_MULT10 = {"normal": 10, "elite": 14, "boss": 20}


def _py(char_level, monster_level, monster_hp, mtype, wisdom):
    catalog = MonsterCatalog(
        levels={"m": monster_level}, hp={"m": monster_hp}, types={"m": mtype},
    )
    return catalog.xp_per_kill("m", char_level, wisdom)


@settings(max_examples=400, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=80),
    monster_level=st.integers(min_value=0, max_value=80),
    monster_hp=st.integers(min_value=0, max_value=5000),
    mtype=st.sampled_from(["normal", "elite", "boss"]),
    wisdom=st.integers(min_value=0, max_value=500),
)
def test_xp_value_python_matches_lean(char_level, monster_level, monster_hp, mtype, wisdom):
    py = _py(char_level, monster_level, monster_hp, mtype, wisdom)
    lean = run_oracle(
        "xp_value",
        [[char_level, monster_level, monster_hp, _MULT10[mtype], wisdom]],
    )[0]
    assert py == lean["xp"], (char_level, monster_level, monster_hp, mtype, wisdom, py, lean)


def test_penalty_boundaries_and_ties_exact():
    """Deterministic: penalty band edges (diff 4/5/9/10) for every type, plus a
    verified half-integer tie (bat-class case: ml=38 hp=2000 cl=8 w=100 has
    num/den = 192.5 exactly — half-even keeps 192; the old float said 193)."""
    cases = []
    for monster_level in (1, 6, 23, 38):
        for diff in (0, 4, 5, 9, 10, 11):
            char_level = monster_level + diff
            for mtype in ("normal", "elite", "boss"):
                cases.append((char_level, monster_level, 150, mtype, 0))
    cases.append((8, 38, 2000, "normal", 100))  # exact .5 tie, even floor
    batch = [[c, m, hp, _MULT10[t], w] for (c, m, hp, t, w) in cases]
    leans = run_oracle("xp_value", batch)
    for (c, m, hp, t, w), lean in zip(cases, leans):
        assert _py(c, m, hp, t, w) == lean["xp"], (c, m, hp, t, w, lean)
    # The tie case pins round-half-even specifically.
    assert _py(8, 38, 2000, "normal", 100) == 192
