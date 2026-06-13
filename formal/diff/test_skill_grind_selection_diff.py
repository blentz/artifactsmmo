"""Differential: real Python skill_grind_selection_pure ≡ mechanically extracted
Lean Extracted.SkillGrindSelection.skill_grind_selection_pure over random skills,
levels, and candidate lists.

Strings (skill, code, craft_skill) are passed to the oracle as JSON strings (the
oracle reads them via `strArg`), so the String-keyed `craft_skill == skill` /
`code` comparisons run identically on both sides — no interning. Small string
pools guarantee ties, same-skill clusters, and cross-skill candidates that must
be filtered out identically.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)
from formal.diff.oracle_client import run_oracle

_SKILLS = ["weaponcrafting", "gearcrafting", "mining", "cooking"]
_CODES = ["copper_dagger", "wooden_staff", "iron_sword", "ash_plank", "cooked_chicken"]


@settings(max_examples=400, deadline=None)
@given(
    skill=st.sampled_from(_SKILLS),
    current_level=st.integers(min_value=0, max_value=10),
    candidates=st.lists(
        st.tuples(
            st.sampled_from(_CODES),    # code
            st.sampled_from(_SKILLS),   # craft_skill (cross-skill cases occur)
            st.integers(min_value=0, max_value=12),   # craft_level
            st.integers(min_value=0, max_value=20),   # mats_missing
            st.booleans(),                            # obtainable
        ),
        min_size=0, max_size=8),
)
def test_python_matches_lean(skill, current_level, candidates):
    py_cands = [
        GrindCandidate(code, cs, cl, mm, ob)
        for (code, cs, cl, mm, ob) in candidates
    ]
    py = skill_grind_selection_pure(skill, current_level, py_cands)

    args: list = [skill, current_level]
    for (code, cs, cl, mm, ob) in candidates:
        args += [code, cs, cl, mm, 1 if ob else 0]

    lean = run_oracle("skill_grind_selection", [args])[0]
    assert py == lean["code"], (skill, current_level, candidates, py, lean)
