"""Differential test: the real Python calculate_path must agree with the proved Lean def."""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.utils.pathfinding import calculate_path
from formal.diff.oracle_client import run_oracle

coord = st.integers(min_value=-40, max_value=40)


@settings(max_examples=400)
@given(sx=coord, sy=coord, ex=coord, ey=coord)
def test_python_matches_lean(sx, sy, ex, ey):
    py = calculate_path(sx, sy, ex, ey)
    lean = run_oracle([(sx, sy, ex, ey)])[0]
    assert [[s.x, s.y] for s in py.steps] == lean["steps"]
    assert py.total_distance == lean["total_distance"]
