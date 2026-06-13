"""Differential: real Python skill_curve_target_pure ≡ proved Lean
skillCurveTarget over random char levels, lookaheads, and item tables.
Skill keys are interned to small ints (the Lean oracle is Int-keyed)."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem, skill_curve_target_pure
from formal.diff.oracle_client import run_oracle

_SKILLS = ["weaponcrafting", "gearcrafting", "mining", "cooking"]
_SID = {s: i for i, s in enumerate(_SKILLS)}


@settings(max_examples=300, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=50),
    lookahead=st.integers(min_value=0, max_value=5),
    max_skill=st.integers(min_value=1, max_value=50),
    query_skill=st.sampled_from(_SKILLS),
    items=st.lists(
        st.tuples(
            st.sampled_from(_SKILLS),
            st.integers(min_value=0, max_value=60),   # craft_level (incl. >50)
            st.integers(min_value=1, max_value=60),   # item_level
            st.booleans(),                            # gear_relevant
        ),
        min_size=0, max_size=12),
)
def test_python_matches_lean(char_level, lookahead, max_skill, query_skill, items):
    py_items = [SkillItem(s, cl, il, gr) for (s, cl, il, gr) in items]
    py = skill_curve_target_pure(query_skill, char_level, py_items, lookahead, max_skill)
    args = [char_level, lookahead, max_skill, _SID[query_skill]]
    for (s, cl, il, gr) in items:
        args += [_SID[s], cl, il, 1 if gr else 0]
    lean = run_oracle("skill_target_curve", [args])[0]
    assert py == lean["target"], (query_skill, char_level, lookahead, max_skill, items, py, lean)
