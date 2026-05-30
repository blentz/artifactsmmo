"""Differential test: the real Python `winnable_farm_target_pure` must agree
bit-for-bit with the proved Lean `winnableFarmTargetPure` on the 3-tier
precedence cascade.

The cascade picks the next combat target as:
    1. task_monster (winnable check bypassed)
    2. path_monster IF path_winnable
    3. pick_winnable

Hypothesis enumerates every reachable (taskCode, pathCode, pathWinnable,
pickCode) combination. Strings on the wire are encoded as small int codes
(0 → None, 1 → "A", 2 → "B", 3 → "C") so the oracle dispatcher (int-arg only)
can round-trip them; the Lean model and the Python core both operate on
arbitrary `str | None`, but the diff drives them over the same encoding for
byte-identical comparison.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.winnable_cascade import CascadeInputs, winnable_farm_target_pure
from formal.diff.oracle_client import run_oracle

_CODE_TO_OPT = {0: None, 1: "A", 2: "B", 3: "C"}


def _decode(code: int) -> str | None:
    return _CODE_TO_OPT.get(code)


@settings(max_examples=400, deadline=None)
@given(
    task_code=st.integers(min_value=0, max_value=3),
    path_code=st.integers(min_value=0, max_value=3),
    path_winnable=st.integers(min_value=0, max_value=1),
    pick_code=st.integers(min_value=0, max_value=3),
)
def test_winnable_cascade_matches_lean(task_code, path_code, path_winnable, pick_code) -> None:
    inputs = CascadeInputs(
        task_monster=_decode(task_code),
        path_monster=_decode(path_code),
        path_winnable=bool(path_winnable),
        pick_winnable=_decode(pick_code),
    )
    python = winnable_farm_target_pure(inputs)
    lean = run_oracle("winnable_cascade", [[task_code, path_code, path_winnable, pick_code]])[0]
    # Lean encodes None as JSON null, Some s as JSON string.
    assert lean["result"] == python


def test_task_tier_bypasses_winnable_check() -> None:
    """Pin: task_monster present ⇒ result is task_monster regardless of
    path_winnable or pick_winnable. Mirrors Lean `task_wins`."""
    inputs = CascadeInputs(
        task_monster="goblin",
        path_monster="dragon",
        path_winnable=True,
        pick_winnable="chicken",
    )
    assert winnable_farm_target_pure(inputs) == "goblin"


def test_path_tier_requires_winnable() -> None:
    """Pin: path_monster present but NOT winnable ⇒ falls through to
    pick_winnable. Mirrors Lean `pick_wins_when_path_not_winnable`."""
    inputs = CascadeInputs(
        task_monster=None,
        path_monster="dragon",
        path_winnable=False,
        pick_winnable="chicken",
    )
    assert winnable_farm_target_pure(inputs) == "chicken"


def test_all_none_returns_none() -> None:
    """Pin: every tier vacuous ⇒ None."""
    inputs = CascadeInputs(
        task_monster=None,
        path_monster=None,
        path_winnable=False,
        pick_winnable=None,
    )
    assert winnable_farm_target_pure(inputs) is None
