"""Differential: currency_afford_plannable_pure must equal the kernel-proved
Formal.CurrencyAffordFastFail.isPlannable over all inputs."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.goals.currency_afford_core import currency_afford_plannable_pure
from formal.diff.oracle_client import run_oracle

_qty = st.integers(min_value=0, max_value=20)


@given(tic=st.booleans(), aff=st.booleans(), owned=_qty, needed=_qty)
def test_currency_afford_matches_oracle(tic, aff, owned, needed):
    py = currency_afford_plannable_pure(tic, aff, owned, needed)
    lean = run_oracle("currency_afford", [[int(tic), int(aff), owned, needed]])[0]["plannable"]
    assert py == lean, f"divergence at (tic={tic}, aff={aff}, owned={owned}, needed={needed}): py={py} lean={lean}"


def test_fastfail_fires_unaffordable_unowned_both_sides():
    """Closure leaf, unaffordable, unowned -> fast-fail (False) both sides."""
    assert currency_afford_plannable_pure(True, False, 0, 1) is False
    assert run_oracle("currency_afford", [[1, 0, 0, 1]])[0]["plannable"] is False
