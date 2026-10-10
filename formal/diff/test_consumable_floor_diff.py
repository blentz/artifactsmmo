"""Differential test: the live floor share (`ai/consumable_floor_core.share`)
must agree with the proved `Formal.ConsumableFloor` on random fleets, needs and
banks — each character's share, and their sum."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.consumable_floor_core import share
from formal.diff.oracle_client import run_oracle


@settings(max_examples=500, deadline=None)
@given(needs=st.lists(st.integers(min_value=0, max_value=200), min_size=1, max_size=6),
       bank=st.integers(min_value=0, max_value=900), data=st.data())
def test_consumable_floor_share_matches_lean(needs, bank, data):
    order = [f"char{i}" for i in range(len(needs))]
    me = data.draw(st.integers(min_value=0, max_value=len(needs) - 1))
    # A character with no need may publish no row at all.
    by_name = {name: n for name, n in zip(order, needs, strict=True) if n > 0 or name == order[me]}
    args = [bank, me, len(needs), *needs]
    lean = run_oracle("consumable_floor", [args])[0]
    assert lean["share"] == share(order, by_name, order[me], bank), args
    total = sum(share(order, by_name, name, bank) for name in order)
    assert lean["total"] == total == max(0, sum(needs) - bank), args


def test_the_bank_goes_to_the_characters_in_api_order():
    order = ["Robby", "C3P0", "HAL"]
    needs = {"Robby": 20, "C3P0": 20, "HAL": 20}
    assert [share(order, needs, name, 25) for name in order] == [0, 15, 20]
    assert run_oracle("consumable_floor", [[25, 1, 3, 20, 20, 20]])[0] == {"share": 15, "total": 35}
