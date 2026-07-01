"""Differential: real Python next_tier_cap_pure / next_tier_dampened_pure ≡ proved
Lean nextTierCap / nextTierDampened over random char levels and item tables.
Skill keys are interned to small Ints (the Lean hand model is Int-keyed)."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.next_tier_cap import next_tier_cap_pure, next_tier_dampened_pure
from artifactsmmo_cli.ai.tiers.skill_target_curve import SkillItem
from formal.diff.oracle_client import run_oracle
from formal.diff.test_skill_target_curve_diff import _SKILLS, _SID


@settings(max_examples=300, deadline=None)
@given(
    char_level=st.integers(min_value=1, max_value=50),
    max_skill=st.integers(min_value=1, max_value=50),
    query_skill=st.sampled_from(_SKILLS),
    items=st.lists(
        st.tuples(
            st.sampled_from(_SKILLS),
            st.integers(min_value=1, max_value=99),  # craft_level
            st.integers(min_value=1, max_value=60),  # item_level
            st.booleans(),                           # gear_relevant
        ),
        max_size=8,
    ),
)
def test_next_tier_cap_python_matches_lean(char_level, max_skill, query_skill, items):
    py_items = [SkillItem(s, cl, il, gr) for (s, cl, il, gr) in items]
    py = next_tier_cap_pure(query_skill, char_level, py_items, max_skill)
    args = [char_level, max_skill, _SID[query_skill]]
    for (s, cl, il, gr) in items:
        args += [_SID[s], cl, il, 1 if gr else 0]
    lean = run_oracle("next_tier_cap", [args])[0]
    assert py == lean["cap"], (char_level, max_skill, query_skill, items, py, lean)


@settings(max_examples=200, deadline=None)
@given(
    current_skill=st.integers(min_value=0, max_value=60),
    cap=st.integers(min_value=0, max_value=60),
)
def test_next_tier_dampened_python_matches_lean(current_skill, cap):
    py = next_tier_dampened_pure(current_skill, cap)
    lean = run_oracle("next_tier_dampened", [[current_skill, cap]])[0]
    assert py == bool(lean["dampened"]), (current_skill, cap, py, lean)
