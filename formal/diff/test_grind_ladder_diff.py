"""Differential: real Python `dispatch_candidate_flags` / `cannibalize_pure`
≡ the Lean `Formal.GrindLadder.flagsFor` / `cannibalizeModel` over random
candidates, reserved sets, ownership, and cannibalize flags.

These are the impure flag-hoisting cores the grind ladder (2026-06-15 fixes)
added; the liveness theorems `grind_when_unowned_target` / `grind_when_all_owned`
are proved over the SAME defs the oracle evaluates here, so this bridges them to
the running code. Small code pools guarantee reserved/recipe overlaps, target +
owned combinations, and the exempt / cannibalize corners.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.tiers.skill_step_dispatch import (
    FlagInputs,
    cannibalize_pure,
    dispatch_candidate_flags,
)
from formal.diff.oracle_client import run_oracle

_MATS = ["copper_bar", "ash_plank", "feather", "iron_bar"]


@settings(max_examples=400, deadline=None)
@given(
    cl=st.integers(min_value=0, max_value=8),
    craft_level=st.integers(min_value=0, max_value=10),
    is_target=st.booleans(),
    owned=st.booleans(),
    cann=st.booleans(),
    recipe=st.lists(st.sampled_from(_MATS), min_size=0, max_size=4),
    reserved_full=st.lists(st.sampled_from(_MATS), min_size=0, max_size=4),
    reserved_relaxed=st.lists(st.sampled_from(_MATS), min_size=0, max_size=4),
)
def test_flags_match_lean(cl, craft_level, is_target, owned, cann,
                          recipe, reserved_full, reserved_relaxed):
    fi = FlagInputs(code="x", recipe_mats=tuple(recipe), craft_level=craft_level,
                    obtainable=True, is_target=is_target, owned=owned)
    py_full, py_relaxed = dispatch_candidate_flags(
        fi, cl, frozenset(reserved_full), frozenset(reserved_relaxed), cann)
    args = [cl, craft_level, 1 if is_target else 0, 1 if owned else 0,
            1 if cann else 0, len(recipe), len(reserved_full), len(reserved_relaxed)]
    args += recipe + reserved_full + reserved_relaxed
    lean = run_oracle("candidate_flags", [args])[0]
    assert (py_full, py_relaxed) == (lean["full"], lean["relaxed"]), (
        cl, craft_level, is_target, owned, cann, recipe,
        reserved_full, reserved_relaxed, (py_full, py_relaxed), lean)


@settings(max_examples=300, deadline=None)
@given(
    cl=st.integers(min_value=0, max_value=8),
    cands=st.lists(
        st.tuples(
            st.integers(min_value=0, max_value=10),  # craft_level
            st.booleans(),                           # obtainable
            st.booleans(),                           # owned
        ),
        min_size=0, max_size=6),
)
def test_cannibalize_matches_lean(cl, cands):
    py_cands = [FlagInputs(code=f"c{i}", recipe_mats=(), craft_level=lv,
                           obtainable=ob, is_target=False, owned=ow)
                for i, (lv, ob, ow) in enumerate(cands)]
    py = cannibalize_pure(cl, py_cands)
    flat = [cl, len(cands)]
    for (lv, ob, ow) in cands:
        flat += [lv, 1 if ob else 0, 1 if ow else 0]
    lean = run_oracle("cannibalize", [flat])[0]
    assert py == lean["cannibalize"], (cl, cands, py, lean)
