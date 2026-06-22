"""Differential: funding_cycles_pure must equal the kernel-proved
Formal.Liveness.CurrencyFunding.fundingCycles over all valid inputs (floor ≥ 1)."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure
from formal.diff.oracle_client import run_oracle

_n = st.integers(min_value=0, max_value=300)
_floor = st.integers(min_value=1, max_value=20)


@given(on_hand=_n, target=_n, floor=_floor)
def test_funding_cycles_matches_oracle(on_hand, target, floor):
    py = funding_cycles_pure(on_hand, target, floor)
    lean = run_oracle("currency_funding", [[on_hand, target, floor]])[0]["cycles"]
    assert py == lean, (f"divergence at (on_hand={on_hand}, target={target}, "
                        f"floor={floor}): py={py} lean={lean}")


def test_sufficiency_spotcheck_both_sides():
    """The cycle count is enough: on_hand + cycles*floor >= target."""
    on_hand, target, floor = 0, 8, 2
    cycles = funding_cycles_pure(on_hand, target, floor)
    assert run_oracle("currency_funding", [[on_hand, target, floor]])[0]["cycles"] == cycles
    assert on_hand + cycles * floor >= target
