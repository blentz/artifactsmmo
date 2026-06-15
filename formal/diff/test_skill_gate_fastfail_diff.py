"""Differential test: the real Python `gather_plannable_pure` (the extracted core
of `GatherMaterialsGoal.is_plannable`) must agree with the kernel-proved Lean
`Formal.SkillGateFastFail.isPlannable` over ALL input tuples.

The Lean side carries the `fastfail_sound` theorem: when this returns False, no
plan can ever raise the owned count to `needed`, so the GOAP search is pruned
soundly (the 2026-06-15 feather_coat 99%-CPU peg avoidance). This test pins the
running Python to that proved decision so a future edit cannot silently diverge.
"""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.goals.gather_plannable_core import gather_plannable_pure
from formal.diff.oracle_client import run_oracle

_lvl = st.integers(min_value=0, max_value=50)
_qty = st.integers(min_value=0, max_value=20)


@given(
    target_in_needed=st.booleans(),
    has_gate=st.booleans(),
    cur=_lvl,
    craft=_lvl,
    owned=_qty,
    needed=_qty,
)
def test_gather_plannable_matches_oracle(target_in_needed, has_gate, cur, craft, owned, needed):
    py = gather_plannable_pure(target_in_needed, has_gate, cur, craft, owned, needed)
    lean = run_oracle(
        "gather_plannable",
        [[int(target_in_needed), int(has_gate), cur, craft, owned, needed]],
    )[0]["plannable"]
    assert py == lean, (
        f"divergence at (tin={target_in_needed}, gate={has_gate}, cur={cur}, "
        f"craft={craft}, owned={owned}, needed={needed}): py={py} lean={lean}"
    )


def test_fastfail_fires_on_closed_gate_unowned():
    """The conclusive feather_coat case: target needed, real gate, level below
    recipe, owns none → fast-fail (False) on both sides."""
    assert gather_plannable_pure(True, True, 2, 5, 0, 1) is False
    assert run_oracle("gather_plannable", [[1, 1, 2, 5, 0, 1]])[0]["plannable"] is False


def test_materials_only_goal_stays_plannable():
    """Regression for c9c0231: gathering a raw drop (target NOT in needed) is
    never pruned by the gate."""
    assert gather_plannable_pure(False, True, 0, 5, 0, 1) is True
    assert run_oracle("gather_plannable", [[0, 1, 0, 5, 0, 1]])[0]["plannable"] is True
