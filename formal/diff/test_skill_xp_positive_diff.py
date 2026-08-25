"""Differential: real Python `ai/skill_xp_positive` ≡ mechanically extracted Lean
`Extracted.SkillXpPositive.skill_xp_positive` over the whole level grid.

This is the GATHER/CRAFT twin of `test_xp_positive_diff.py` (the combat gate).
The band it pins is corroborated against live play by
`formal/diff/gather_xp_replay.py` (3231 gather cycles); this file pins the
PRODUCTION function to the PROVED model, which is the other half of the chain.

The grid is swept exhaustively around the boundary rather than sampled, because
the whole defect this core exists to fix was an off-by-a-tier error: a band one
level too narrow silently reintroduces a zero-xp grind at exactly one gap.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.skill_xp_positive import GREY_SKILL_GAP, skill_xp_positive
from formal.diff.oracle_client import run_oracle

_MAX_SKILL = 50


def _lean(content: int, skill: int) -> bool:
    return run_oracle("skill_xp_positive", [[content, skill]])[0]["positive"]


@settings(max_examples=300, deadline=None)
@given(content=st.integers(min_value=-2, max_value=_MAX_SKILL),
       skill=st.integers(min_value=-2, max_value=_MAX_SKILL))
def test_python_matches_lean(content: int, skill: int) -> None:
    assert skill_xp_positive(content, skill) == _lean(content, skill), (content, skill)


def test_whole_grid_matches_lean() -> None:
    """Exhaustive over every (content, skill) pair a real character can present.
    Batched into ONE oracle call per content level to keep the sweep cheap."""
    for content in range(0, _MAX_SKILL + 1):
        batch = [[content, skill] for skill in range(0, _MAX_SKILL + 1)]
        lean = run_oracle("skill_xp_positive", batch)
        for (_, skill), out in zip(batch, lean, strict=True):
            assert skill_xp_positive(content, skill) == out["positive"], (content, skill)


def test_boundary_is_exactly_the_replayed_band() -> None:
    """The boundary the trace replay measured: a gap of GREY_SKILL_GAP - 1 still
    pays, a gap of GREY_SKILL_GAP does not. Pinned on BOTH sides so neither the
    constant nor the comparison can drift alone."""
    for content in range(1, _MAX_SKILL + 1):
        last_paying = content + GREY_SKILL_GAP - 1
        assert skill_xp_positive(content, last_paying) is True
        assert skill_xp_positive(content, last_paying + 1) is False
        assert _lean(content, last_paying) is True
        assert _lean(content, last_paying + 1) is False


def test_zero_level_content_never_pays() -> None:
    """`content_level = 0` means "no level on file" — the real-content guard that
    mirrors the combat gate's. It must never be reported as a paying target, at
    any skill level, on either side."""
    for skill in range(0, _MAX_SKILL + 1):
        assert skill_xp_positive(0, skill) is False
        assert _lean(0, skill) is False


def test_at_or_above_level_content_always_pays() -> None:
    """`gate_of_reachable`, executed: content at or above the character's skill
    is never grey. This is the liveness fact the grind filter rests on — an
    at-level rung always survives it."""
    for content in range(1, _MAX_SKILL + 1):
        for skill in range(0, content + 1):
            assert skill_xp_positive(content, skill) is True
            assert _lean(content, skill) is True
