"""nearest_tile (Python) must agree with Formal.NearestTile.nearestTile (Lean) over
hundreds of random origin + tile-list inputs.

The oracle takes a flattened arg array `[originX, originY, N, x0, y0, x1, y1, ...]`
(origin coords, tile count, then N (x, y) Int pairs), so the test sends ONE request
and reads result `[0]`. The Python `nearest_tile` returns the selected `(x, y)` tuple
(or `None`); the Lean side emits `present` + `x`/`y`, and the test asserts they agree
exactly — including the lex `(x, y)` tie-break on distance ties (the determinism fact
that closes the MoveTo apply/execute divergence).

Tiles are unique per list so the selected tile is well-defined.
"""
from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.nearest_tile import nearest_tile
from formal.diff.oracle_client import run_oracle

_coord = st.integers(min_value=-20, max_value=20)
_tile = st.tuples(_coord, _coord)


def _oracle_args(ox: int, oy: int, tiles: list[tuple[int, int]]) -> list[int]:
    """Flatten origin + tiles into the oracle's `[ox, oy, N, ...x,y pairs]` array."""
    args: list[int] = [ox, oy, len(tiles)]
    for x, y in tiles:
        args.extend([x, y])
    return args


@settings(max_examples=500)
@given(
    ox=_coord,
    oy=_coord,
    tiles=st.lists(_tile, min_size=0, max_size=10, unique=True),
)
def test_selection_matches_lean(ox, oy, tiles):
    py = nearest_tile(ox, oy, tiles)
    lean = run_oracle("nearest_tile", [_oracle_args(ox, oy, tiles)])[0]
    if py is None:
        assert lean["present"] is False
    else:
        assert lean["present"] is True
        assert (lean["x"], lean["y"]) == (py[0], py[1])


def test_lex_tiebreak_closes_apply_execute_divergence():
    """The exact divergence case: origin (0, 0); (1, 9) is the raw `min(tiles)`
    (lex-min tuple, distance 10) — what the OLD MoveTo.apply picked — while (5, 0)
    is the Manhattan-min (distance 5) — what the OLD execute picked. Both models must
    now pick the Manhattan-nearest (5, 0); apply and execute agree."""
    tiles = [(1, 9), (5, 0)]
    py = nearest_tile(0, 0, tiles)
    lean = run_oracle("nearest_tile", [_oracle_args(0, 0, tiles)])[0]
    assert py == (5, 0)
    assert (lean["x"], lean["y"]) == (5, 0)


def test_lex_tiebreak_on_equal_distance():
    """Two tiles equidistant from origin (0, 0): (3, 0) and (0, 3), both distance 3.
    The lex `(x, y)` tie-break picks the smaller x -> (0, 3). Pins the tie-break
    against a list-order regression (where Python `min` would first-win on (3, 0))."""
    tiles = [(3, 0), (0, 3)]
    py = nearest_tile(0, 0, tiles)
    lean = run_oracle("nearest_tile", [_oracle_args(0, 0, tiles)])[0]
    assert py == (0, 3)
    assert (lean["x"], lean["y"]) == (0, 3)


def test_empty_is_none():
    py = nearest_tile(2, 2, [])
    lean = run_oracle("nearest_tile", [_oracle_args(2, 2, [])])[0]
    assert py is None
    assert lean["present"] is False
