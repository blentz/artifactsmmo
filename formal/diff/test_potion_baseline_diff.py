from hypothesis import given, settings, strategies as st
from artifactsmmo_cli.ai.potion_baseline import potion_baseline_pure
from formal.diff.oracle_client import run_oracle


@settings(max_examples=500, deadline=None)
@given(level=st.integers(1, 60))
def test_potion_baseline_matches_lean(level):
    args = [level, 5, 5, 45, 100]
    py = potion_baseline_pure(level, 5, 5, 45, 100)
    lean = run_oracle("potion_baseline", [args])[0]
    assert lean["baseline"] == py
