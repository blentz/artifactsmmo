# formal/diff/test_leaf_attainable_diff.py
"""Differential: real `leaf_attainable_pure` must agree with the kernel-proved
`Formal.LeafAttainable.leafAttainable` over ALL boolean tuples."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from formal.diff.oracle_client import run_oracle


@given(g=st.booleans(), d=st.booleans(), t=st.booleans(), b=st.booleans())
def test_leaf_attainable_matches_oracle(g, d, t, b):
    py = leaf_attainable_pure(g, d, t, b)
    lean = run_oracle("leaf_attainable", [[int(g), int(d), int(t), int(b)]])[0]["attainable"]
    assert py == lean, f"divergence at (g={g}, d={d}, t={t}, b={b}): py={py} lean={lean}"


def test_task_earnable_alone_attainable_both_sides():
    """The C1 case: task-earnable with no other source => attainable on both sides."""
    assert leaf_attainable_pure(False, False, True, False) is True
    assert run_oracle("leaf_attainable", [[0, 0, 1, 0]])[0]["attainable"] is True
