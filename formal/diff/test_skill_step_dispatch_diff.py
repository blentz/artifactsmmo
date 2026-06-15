"""Differential: real Python `skill_step_dispatch_pure` ≡ the Lean hand model
`Formal.SkillStepDispatch.dispatch` (filter → proved selection → extracted
combine) over random skills, levels, committed items, and candidate lists.

The two per-candidate reserved flags are generated CONSISTENTLY — relaxed ⊆ full,
so `uses_reserved_relaxed` implies `uses_reserved_full` (the hoisting discipline
the role theorems assume). Small string pools guarantee ties, same-skill
clusters, suppression hits (committed_skill == skill at/below level), and
candidates filtered out by each reserved pass.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.skill_step_dispatch import (
    DispatchCandidate,
    combine_dispatch_pure,
    skill_step_dispatch_pure,
)
from formal.diff.oracle_client import run_oracle

_SKILLS = ["weaponcrafting", "gearcrafting", "jewelrycrafting", "mining"]
_CODES = ["copper_dagger", "copper_helmet", "wooden_shield", "iron_sword", ""]


@settings(max_examples=400, deadline=None)
@given(
    skill=st.sampled_from(_SKILLS),
    current_level=st.integers(min_value=0, max_value=10),
    committed_skill=st.sampled_from(_SKILLS + [""]),
    committed_level=st.integers(min_value=0, max_value=10),
    candidates=st.lists(
        st.tuples(
            st.sampled_from(_CODES),    # code (incl. "" edge)
            st.sampled_from(_SKILLS),   # craft_skill (cross-skill cases occur)
            st.integers(min_value=0, max_value=12),   # craft_level
            st.integers(min_value=0, max_value=20),   # mats_missing
            st.booleans(),                            # obtainable
            st.booleans(),                            # uses_reserved_full
            st.booleans(),                            # relaxed_raw
        ),
        min_size=0, max_size=8),
)
def test_python_matches_lean(skill, current_level, committed_skill,
                             committed_level, candidates):
    py_cands = []
    flat: list = [skill, current_level, committed_skill, committed_level]
    for (code, cs, cl, mm, ob, full, relaxed_raw) in candidates:
        relaxed = relaxed_raw and full   # enforce relaxed ⊆ full
        py_cands.append(DispatchCandidate(
            code=code, craft_skill=cs, craft_level=cl, mats_missing=mm,
            obtainable=ob, uses_reserved_full=full, uses_reserved_relaxed=relaxed))
        flat += [code, cs, cl, mm, 1 if ob else 0, 1 if full else 0,
                 1 if relaxed else 0]

    py = skill_step_dispatch_pure(skill, current_level, committed_skill,
                                  committed_level, py_cands)
    lean = run_oracle("skill_step_dispatch", [flat])[0]
    assert py.kind == lean["kind"] and py.code == lean["code"], (
        skill, current_level, committed_skill, committed_level, candidates,
        (py.kind, py.code), lean)


@settings(max_examples=400, deadline=None)
@given(
    skill=st.sampled_from(_SKILLS),
    current_level=st.integers(min_value=0, max_value=10),
    committed_skill=st.sampled_from(_SKILLS + [""]),
    committed_level=st.integers(min_value=0, max_value=10),
    full_pick=st.sampled_from(_CODES),     # incl. "" (no full pick)
    relaxed_pick=st.sampled_from(_CODES),  # incl. "" (no relaxed pick)
)
def test_combine_matches_lean(skill, current_level, committed_skill,
                              committed_level, full_pick, relaxed_pick):
    """Direct differential on the extracted `combine_dispatch_pure` — feeds BOTH
    picks non-empty (which the pipeline wrapper short-circuits) so the
    full-preference branch is actually exercised."""
    py = combine_dispatch_pure(skill, current_level, committed_skill,
                               committed_level, full_pick, relaxed_pick)
    lean = run_oracle("combine_dispatch", [[skill, current_level, committed_skill,
                                            committed_level, full_pick, relaxed_pick]])[0]
    assert py == (lean["kind"], lean["code"]), (
        skill, current_level, committed_skill, committed_level,
        full_pick, relaxed_pick, py, lean)
