"""Differential test: the live loss surcharge (`ai/loss_risk_core`) must agree
with the proved `Formal.LossRisk` on random fight records and loss costs."""
from fractions import Fraction

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.loss_risk_core import loss_surcharge
from formal.diff.oracle_client import run_oracle


@settings(max_examples=500, deadline=None)
@given(samples=st.integers(min_value=0, max_value=60), wins=st.integers(min_value=0, max_value=60),
       min_samples=st.integers(min_value=0, max_value=10),
       cost_num=st.integers(min_value=0, max_value=400), cost_den=st.integers(min_value=1, max_value=60))
def test_loss_risk_matches_lean(samples, wins, min_samples, cost_num, cost_den):
    args = [samples, wins, min_samples, cost_num, cost_den]
    lean = run_oracle("loss_risk", [args])[0]
    assert Fraction(lean["num"], lean["den"]) == loss_surcharge(*args), args


def test_the_r2d2_king_slime_witness():
    """22 fights, 14 wins, a loss = the Fight + a full-bar Rest = 130/30."""
    assert loss_surcharge(22, 14, 5, 130, 30) == Fraction(1040, 420)
    assert run_oracle("loss_risk", [[22, 14, 5, 130, 30]])[0] == {"num": 1040, "den": 420}
