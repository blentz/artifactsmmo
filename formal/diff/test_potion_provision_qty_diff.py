"""Differential test: `potion_provision_qty_pure` (Python) == `potionProvisionQty` (Lean).

Locks the HP-need-scaled potion-provision core to its kernel-checked Int mirror
over random hp-need / potion-restore / held / slot-state / max-stack inputs through
the `potion_provision_qty` oracle kind.

Inputs are non-negative (restore down to 0): in the live branch restore >= 1 and
hp_need >= 0, so the integer `ceilDiv` matches Python's floor `//` bit-for-bit.
The `@example` anchors pin the mutation-boundary cases (ceil->floor, held clamp,
max_stack clamp, slot-filled guard) that random sampling could otherwise miss.
"""
from hypothesis import example, given, settings, strategies as st

from artifactsmmo_cli.ai.potion_provision_qty import potion_provision_qty_pure
from formal.diff.oracle_client import run_oracle


# ceil boundary, divisible hp_need: deleting the `- 1` overshoots (2 -> 3).
@example(hp_need=6, potion_restore=3, held=100, slot_filled=0, max_stack=100)
# ceil boundary, non-divisible hp_need: a genuine floor undershoots (3 -> 2).
@example(hp_need=7, potion_restore=3, held=100, slot_filled=0, max_stack=100)
# desired > held: dropping the held clamp diverges (held vs desired).
@example(hp_need=90, potion_restore=1, held=5, slot_filled=0, max_stack=100)
# desired > max_stack: dropping the max_stack clamp diverges (max_stack vs desired).
@example(hp_need=90, potion_restore=1, held=100, slot_filled=0, max_stack=5)
# slot filled: guard must return 0 (flipping the guard diverges).
@example(hp_need=90, potion_restore=3, held=100, slot_filled=1, max_stack=100)
# restore == 0: guard must return 0 (no divide-by-zero).
@example(hp_need=90, potion_restore=0, held=100, slot_filled=0, max_stack=100)
@settings(max_examples=500, deadline=None)
@given(
    hp_need=st.integers(min_value=0, max_value=2000),
    potion_restore=st.integers(min_value=0, max_value=200),
    held=st.integers(min_value=0, max_value=100),
    slot_filled=st.integers(min_value=0, max_value=1),
    max_stack=st.integers(min_value=0, max_value=120),
)
def test_potion_provision_qty_matches_lean(hp_need, potion_restore, held,
                                           slot_filled, max_stack):
    args = [hp_need, potion_restore, held, slot_filled, max_stack]
    py = potion_provision_qty_pure(hp_need, potion_restore, held,
                                   bool(slot_filled), max_stack)
    lean = run_oracle("potion_provision_qty", [args])[0]
    assert lean["qty"] == py
