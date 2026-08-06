"""Differential: real Python skill_grind_selection_pure ≡ mechanically extracted
Lean Extracted.SkillGrindSelection.skill_grind_selection_pure over random skills,
levels, and candidate lists.

Strings (skill, code, craft_skill) are passed to the oracle as JSON strings (the
oracle reads them via `strArg`), so the String-keyed `craft_skill == skill` /
`code` comparisons run identically on both sides — no interning. Small string
pools guarantee ties, same-skill clusters, and cross-skill candidates that must
be filtered out identically.

`xp_positive` is drawn INDEPENDENTLY of `craft_level` rather than derived from
it: the differential's job is to pin the SELECTOR's treatment of the flag over
the whole input space, including combinations the live hoist would never
produce. The hoist itself (`skill_xp_positive` applied to the real craft level)
is pinned separately by `test_skill_xp_positive_diff.py`.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.skill_grind_selection import (
    GrindCandidate,
    skill_grind_selection_pure,
)
from formal.diff.oracle_client import run_oracle

_SKILLS = ["weaponcrafting", "gearcrafting", "mining", "cooking"]
_CODES = ["copper_dagger", "wooden_staff", "iron_sword", "ash_plank", "cooked_chicken"]


def _args(skill: str, level: int, candidates) -> list:
    args: list = [skill, level]
    for (code, cs, cl, mm, ob, wt, xp) in candidates:
        args += [code, cs, cl, mm, 1 if ob else 0, 1 if wt else 0, 1 if xp else 0]
    return args


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
            st.booleans(),                            # wanted (objective gear/tool target)
            st.booleans(),                            # xp_positive (pays skill xp)
        ),
        min_size=0, max_size=8),
)
def test_python_matches_lean(skill, current_level, candidates):
    py_cands = [
        GrindCandidate(code, cs, cl, mm, ob, wt, xp)
        for (code, cs, cl, mm, ob, wt, xp) in candidates
    ]
    py = skill_grind_selection_pure(skill, current_level, py_cands)

    lean = run_oracle("skill_grind_selection", [_args(skill, current_level, candidates)])[0]
    assert py == lean["code"], (skill, current_level, candidates, py, lean)


def test_wanted_beats_cheaper_throwaway_diff():
    """The reported inversion: a WANTED keeper (more missing materials) must beat
    a cheaper throwaway. Pins the wanted-first key on both sides."""
    cands = [
        ("apprentice_gloves", "weaponcrafting", 1, 0, True, False, True),
        ("copper_dagger", "weaponcrafting", 1, 2, True, True, True),
    ]
    py = skill_grind_selection_pure(
        "weaponcrafting", 5, [GrindCandidate(*c) for c in cands])
    lean = run_oracle("skill_grind_selection", [_args("weaponcrafting", 5, cands)])[0]
    assert py == "copper_dagger"
    assert py == lean["code"]


def test_unwanted_never_displaces_a_wanted_incumbent_diff():
    """The OTHER half of the wanted-first key: `_beats`'s shield clause
    (`best.wanted and not c.wanted -> False`). The test above lists the wanted
    candidate SECOND, so it only ever exercises the first clause; this one lists
    it FIRST, so the shield is the only thing keeping the cheaper throwaway from
    displacing the keeper.

    Deterministic on purpose. The randomised sweep above used to catch this
    clause incidentally, but adding the `xp_positive` dimension (2026-08-06)
    filters out roughly half of each generated candidate list before it reaches
    `_beats`, which diluted the search enough that the "invert wanted shield"
    mutant started surviving. A ranking clause deserves its own pin rather than
    a probabilistic one."""
    cands = [
        ("copper_dagger", "weaponcrafting", 1, 5, True, True, True),      # wanted, costly
        ("apprentice_gloves", "weaponcrafting", 1, 0, True, False, True),  # cheap throwaway
    ]
    py = skill_grind_selection_pure(
        "weaponcrafting", 5, [GrindCandidate(*c) for c in cands])
    lean = run_oracle("skill_grind_selection", [_args("weaponcrafting", 5, cands)])[0]
    assert py == "copper_dagger", "an unwanted throwaway displaced the wanted keeper"
    assert py == lean["code"]


def test_zero_xp_rung_never_selected_diff():
    """THE 2026-08-05 LIVELOCK, at the selection layer. A grey rung with its
    materials ALREADY IN HAND (mats_missing 0 — the top of the ranking) must lose
    to a costlier rung that actually pays xp. Ordering could not fix this: the
    grey rung wins every ranking key it participates in, so the filter is the
    only thing standing between the bot and 288 zero-xp cycles.

    Both sides must agree, so a regression here is a differential failure and not
    just a Python-side assertion."""
    cands = [
        # ash_plank: woodcutting 1, materials stockpiled, pays NOTHING at 15.
        ("ash_plank", "mining", 1, 0, True, False, False),
        # spruce_plank equivalent: costlier, but in-band.
        ("iron_sword", "mining", 10, 6, True, False, True),
    ]
    py = skill_grind_selection_pure("mining", 15, [GrindCandidate(*c) for c in cands])
    lean = run_oracle("skill_grind_selection", [_args("mining", 15, cands)])[0]
    assert py == "iron_sword", "the zero-xp rung was selected — the livelock is back"
    assert py == lean["code"]


def test_all_candidates_grey_selects_nothing_diff():
    """When EVERY in-level rung is grey the selector returns "" rather than
    picking one anyway. That empty result is what lets `next_grind_goal` fall
    through to the gather fallback (and, failing that, report "cannot grind from
    here") instead of committing the cycle to a craft with no xp behind it."""
    cands = [
        ("ash_plank", "mining", 1, 0, True, True, False),
        ("copper_dagger", "mining", 2, 0, True, False, False),
    ]
    py = skill_grind_selection_pure("mining", 15, [GrindCandidate(*c) for c in cands])
    lean = run_oracle("skill_grind_selection", [_args("mining", 15, cands)])[0]
    assert py == ""
    assert py == lean["code"]
