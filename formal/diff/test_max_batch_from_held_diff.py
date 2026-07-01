"""Differential test: `max_batch_from_held_pure` (Python) == `maxBatchFromHeld`
(Lean) over random recipes through the `max_batch_from_held` oracle kind.

Locks the float-free "max craftable now" core — `min_i(held_i // need_i) * yield`
— to its kernel-checked Nat mirror. The oracle takes a length-prefixed list
`[yield, n, need_0, held_0, need_1, held_1, ...]` (yield first, then `n`
`[need, held]` records), so the test sends ONE request and reads result `[0]`.

Sampling follows the brief: `needs` in `[1,5]` (real recipes never have a 0
ingredient quantity — the Lean `need == 0` guard is defensive and unexercised
here), `held` in `[0,50]` (incl. 0 so the any-ingredient-short -> 0 path fires),
`yield` in `[1,5]`. The `@example` anchors pin the exact-divisor and
short-ingredient boundaries that the floor-div / min / yield-multiply mutants
diverge on.
"""
from hypothesis import example, given, settings, strategies as st

from artifactsmmo_cli.ai.max_batch_from_held import max_batch_from_held_pure
from formal.diff.oracle_client import run_oracle

_ingredient = st.tuples(
    st.integers(min_value=1, max_value=5),    # need (>= 1, real recipe quantity)
    st.integers(min_value=0, max_value=50),   # held (incl. 0 -> short)
)


def _oracle_args(recipe: list[tuple[int, int]], yield_per_craft: int) -> list[int]:
    """Flatten into the oracle's `[yield, n, need_0, held_0, ...]` arg array."""
    args: list[int] = [yield_per_craft, len(recipe)]
    for need, held in recipe:
        args.extend([need, held])
    return args


# Exact divisor: held a multiple of need, two ingredients tie on runs.
@example(recipe=[(2, 10), (3, 6)], yield_per_craft=1)
# yield multiplies the run count, not just the +0 case.
@example(recipe=[(2, 10), (3, 6)], yield_per_craft=5)
# One ingredient short (held 0) -> min floor 0 -> 0 batch regardless of others.
@example(recipe=[(2, 10), (3, 0)], yield_per_craft=4)
# Single ingredient, non-exact floor division (10 // 3 == 3).
@example(recipe=[(3, 10)], yield_per_craft=1)
@settings(max_examples=500, deadline=None)
@given(
    recipe=st.lists(_ingredient, min_size=1, max_size=6),
    yield_per_craft=st.integers(min_value=1, max_value=5),
)
def test_max_batch_from_held_matches_lean(recipe, yield_per_craft):
    needs = [need for need, _ in recipe]
    held = [h for _, h in recipe]
    py = max_batch_from_held_pure(needs, held, yield_per_craft)
    lean = run_oracle("max_batch_from_held", [_oracle_args(recipe, yield_per_craft)])[0]
    assert lean["batch"] == py
