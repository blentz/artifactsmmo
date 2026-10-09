"""Differential test: the live failure block table (`ai/failure_recovery_core`)
must agree with the proved `Formal.FailureRecovery` on random tables, premises
and tick counts. Keys and premises are integers on the Lean side; the Python
side names them `k<n>` and `frozenset({"<p>"})`."""
from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.failure_recovery_core import Block, blocked, tick
from formal.diff.oracle_client import run_oracle

_entry = st.tuples(st.integers(min_value=1, max_value=12), st.integers(min_value=-1, max_value=3))


def _premise(p: int) -> frozenset[str]:
    return frozenset({str(p)})


@settings(max_examples=500, deadline=None)
@given(entries=st.dictionaries(st.integers(min_value=0, max_value=20), _entry, max_size=6),
       premise=st.integers(min_value=0, max_value=3), ticks=st.integers(min_value=0, max_value=15))
def test_failure_recovery_matches_lean(entries, premise, ticks):
    table: dict[str, Block] = {
        f"k{k}": (left, None if p < 0 else _premise(p)) for k, (left, p) in entries.items()}
    for _ in range(ticks):
        table = tick(table)
    args = [premise, ticks, len(entries), *(v for k, (left, p) in entries.items() for v in (k, left, p))]
    lean = run_oracle("failure_recovery", [args])[0]
    assert blocked(table, _premise(premise)) == {f"k{k}" for k in lean["blocked"]}, args


def test_a_structural_block_outlives_any_ticks():
    assert run_oracle("failure_recovery", [[2, 500, 1, 7, 0, 2]])[0] == {"blocked": [7]}
    assert run_oracle("failure_recovery", [[3, 0, 1, 7, 0, 2]])[0] == {"blocked": []}
