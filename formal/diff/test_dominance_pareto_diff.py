"""Differential: the real Python `pareto_dominates` must agree bit-for-bit with
the proved Lean `Formal.DominancePareto.paretoDominates`, via the
`pareto_dominates` oracle command.

This bridges the model↔code gap for the per-monster dominance filter: the live
function that decides whether a peer stat-vector strictly dominates an item
stat-vector (`pareto_dominates`) is the SAME function the kernel proved
(`pareto_irreflexive`, `geqAll_of_paretoDominates`, `gtSome_of_paretoDominates`, …).
"""
from hypothesis import given, settings
from hypothesis import strategies as st
from artifactsmmo_cli.ai.dominance_pareto import pareto_dominates
from formal.diff.oracle_client import run_oracle


@settings(max_examples=400)
@given(st.lists(st.tuples(st.integers(-100, 100), st.integers(-100, 100)),
                min_size=0, max_size=8))
def test_pareto_matches_lean(pairs):
    peer = [p for p, _ in pairs]
    item = [i for _, i in pairs]
    args = [len(peer), *peer, *item]
    lean = run_oracle("pareto_dominates", [args])[0]
    assert pareto_dominates(peer, item) == lean["dominated"], (
        f"mismatch peer={peer} item={item} "
        f"py={pareto_dominates(peer, item)} lean={lean['dominated']}")
