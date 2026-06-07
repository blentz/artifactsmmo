"""cheaper_acquisition (Python) must agree with Formal.CraftVsBuy.cheaperAcquisition."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.craft_vs_buy import Method, cheaper_acquisition
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(craft=st.integers(0, 200), buy=st.integers(0, 200), price=st.integers(0, 500),
       gold=st.integers(0, 2000), reserve=st.integers(0, 1000))
def test_decision_matches_lean(craft, buy, price, gold, reserve):
    py = cheaper_acquisition(craft, buy, price, gold, reserve)
    lean = run_oracle("craft_vs_buy", [[craft, buy, price, gold, reserve]])[0]
    assert lean["method"] == (1 if py is Method.BUY else 0)
