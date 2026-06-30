"""Differential test: `marginal_potion_qty_pure` (Python) == `marginalPotionQty` (Lean).

Locks the win-rate-scaled potion-quantity core to its kernel-checked Nat mirror
over random win-permille / sample / max-stack / held / slot-state inputs through
the `marginal_potion_qty` oracle kind.

`max_stack` is varied down to 0: the `max(1, ceil(...))` floor and the
`win <= full_stack` branch only diverge from their perturbations at the
degenerate `max_stack == 0` / boundary win-rates, so the explicit `@example`
anchors below pin those cases (they kill the full-stack-comparator and
floor-at-1 mutants, which are equivalent under a fixed positive max_stack).
"""
from hypothesis import example, given, settings, strategies as st

from artifactsmmo_cli.ai.marginal_potion_qty import marginal_potion_qty_pure
from formal.diff.oracle_client import run_oracle

_MIN_SAMPLES = 5
_THRESHOLD = 950
_FULL_STACK = 500


# Full-stack boundary at max_stack==0: `<=`->`<` flip diverges (0 vs floored 1).
@example(samples=5, win_permille=_FULL_STACK, max_stack=0, slot_filled=0, held=1)
# Else-branch numerator==0 at max_stack==0: dropping the max(1,..) floor diverges.
@example(samples=5, win_permille=700, max_stack=0, slot_filled=0, held=3)
# Threshold boundary: `>=`->`>` flip diverges (0 vs floored 1).
@example(samples=5, win_permille=_THRESHOLD, max_stack=100, slot_filled=0, held=1)
# desired > held: dropping the held clamp diverges (held vs desired).
@example(samples=5, win_permille=940, max_stack=100, slot_filled=0, held=1)
@settings(max_examples=500, deadline=None)
@given(
    samples=st.integers(min_value=0, max_value=40),
    win_permille=st.integers(min_value=0, max_value=1000),
    max_stack=st.integers(min_value=0, max_value=120),
    slot_filled=st.integers(min_value=0, max_value=1),
    held=st.integers(min_value=0, max_value=100),
)
def test_marginal_potion_qty_matches_lean(samples, win_permille, max_stack,
                                          slot_filled, held):
    args = [samples, win_permille, _MIN_SAMPLES, _THRESHOLD, _FULL_STACK,
            max_stack, slot_filled, held]
    py = marginal_potion_qty_pure(samples, win_permille, _MIN_SAMPLES, _THRESHOLD,
                                  _FULL_STACK, max_stack, bool(slot_filled), held)
    lean = run_oracle("marginal_potion_qty", [args])[0]
    assert lean["qty"] == py
