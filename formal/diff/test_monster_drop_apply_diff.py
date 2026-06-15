"""Differential: real Python `apply_monster_drops_pure` ≡ the Lean
`Formal.MonsterDropApply.applyDrops` over random drop lists, capacities, and
starting `used` (from an empty initial inventory). Bridges the Fight.apply
drop-loop reachability theorems (`applyDrops_monotone` / `fight_drop_reachable`)
to the running code. The `used` near `cap` cases exercise the cap-break.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.actions.gather_apply_core import (
    GatherInv,
    apply_monster_drops_pure,
)
from formal.diff.oracle_client import run_oracle

_DROPS = ["feather", "raw_chicken", "egg", "golden_egg"]


@settings(max_examples=400, deadline=None)
@given(
    used=st.integers(min_value=0, max_value=12),
    cap=st.integers(min_value=0, max_value=12),
    drops=st.lists(st.sampled_from(_DROPS), min_size=0, max_size=6),
    query=st.lists(st.sampled_from(_DROPS), min_size=1, max_size=4, unique=True),
)
def test_monster_drop_apply_matches_lean(used, cap, drops, query):
    out = apply_monster_drops_pure(
        GatherInv(used=used, cap=cap, item_count={}), tuple(drops))
    py_counts = [out.item_count.get(k, 0) for k in query]
    args = [used, cap, len(drops), len(query)] + drops + query
    lean = run_oracle("monster_drop_apply", [args])[0]
    assert out.used == lean["used"] and py_counts == lean["counts"], (
        used, cap, drops, query, out.used, py_counts, lean)
