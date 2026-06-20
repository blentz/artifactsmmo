"""Differential: production `servable_filter.keep_servable` must compute the same
function as the kernel-proved Lean `ServableFilter.keepServable` — the filter decide()
applies so chosen_root is a plannable-step root. Items are their indices; the oracle
returns the kept indices.
"""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.tiers.servable_filter import keep_servable
from formal.diff.oracle_client import run_oracle


@settings(max_examples=300)
@given(flags=st.lists(st.booleans(), min_size=1, max_size=8))
def test_keep_servable_matches_oracle(flags):
    items = list(range(len(flags)))
    py = keep_servable(items, flags)
    args = [len(flags)] + [1 if f else 0 for f in flags]
    oracle = run_oracle("keep_servable", [args])[0]
    assert oracle == py, f"flags={flags}: oracle={oracle} python={py}"
