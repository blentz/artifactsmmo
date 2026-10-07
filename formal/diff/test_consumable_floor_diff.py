"""Differential test: the live consumable floor (`ai/consumable_floor_core`)
must agree with the proved `Formal.ConsumableFloor` (tier pick, fleet deficit,
published share) on random catalogues and fleets."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.consumable_floor_core import fleet_deficit, publish_share, tier_pick
from formal.diff.oracle_client import run_oracle

_cand = st.tuples(st.integers(min_value=1, max_value=50), st.integers(min_value=0, max_value=600))


@settings(max_examples=500, deadline=None)
@given(char_level=st.integers(min_value=1, max_value=50), cands=st.lists(_cand, max_size=8),
       target=st.integers(min_value=0, max_value=100), fleet=st.integers(min_value=1, max_value=6),
       stock=st.integers(min_value=0, max_value=700))
def test_consumable_floor_matches_lean(char_level, cands, target, fleet, stock):
    args = [char_level, len(cands), *(v for c in cands for v in c), target, fleet, stock]
    lean = run_oracle("consumable_floor", [args])[0]
    pick = tier_pick(char_level, cands)
    deficit = fleet_deficit(target, fleet, stock)
    assert lean["pick"] == (-1 if pick is None else pick), args
    assert lean["deficit"] == deficit, args
    assert lean["share"] == publish_share(deficit, fleet), args


def test_ties_go_to_the_higher_level_then_catalogue_order():
    cands = [(20, 300), (30, 300), (30, 300)]
    assert tier_pick(30, cands) == 1
    assert run_oracle("consumable_floor", [[30, 3, 20, 300, 30, 300, 30, 300, 0, 1, 0]])[0]["pick"] == 1
