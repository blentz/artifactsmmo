"""nearest_tile: Manhattan-nearest tile, lex-tie-broken on (x, y).

This is the single spatial-routing primitive shared by gather/fight/move actions
and the apply/execute paths of MoveTo. The lex tie-break makes the winner unique so
plan-time (apply) and execute-time picks agree.
"""
from artifactsmmo_cli.ai.nearest_tile import nearest_tile


def test_empty_returns_none():
    assert nearest_tile(0, 0, frozenset()) is None
    assert nearest_tile(3, 7, []) is None


def test_single_tile_returned():
    assert nearest_tile(0, 0, frozenset([(4, 2)])) == (4, 2)


def test_picks_manhattan_nearest():
    # (1, 0) is distance 1, (5, 0) is distance 5 from origin (0, 0).
    assert nearest_tile(0, 0, frozenset([(5, 0), (1, 0)])) == (1, 0)


def test_distance_uses_absolute_value_both_axes():
    # origin (3, 3); (1, 1) is dist 4, (4, 4) is dist 2.
    assert nearest_tile(3, 3, frozenset([(1, 1), (4, 4)])) == (4, 4)


def test_lex_tiebreak_on_x_when_distance_ties():
    # Both at distance 5 from origin (0, 0): (5, 0) and (0, 5). Lex-min x wins -> (0, 5).
    assert nearest_tile(0, 0, frozenset([(5, 0), (0, 5)])) == (0, 5)


def test_lex_tiebreak_on_y_when_distance_and_x_tie():
    # origin (0, 0); (2, 2) dist 4, (2, -2) dist 4, same x. Lex-min y wins -> (2, -2).
    assert nearest_tile(0, 0, frozenset([(2, 2), (2, -2)])) == (2, -2)


def test_apply_execute_agree_on_distance_tie():
    # The divergence case: a tile that is Manhattan-nearest but NOT lex-min over (x, y),
    # versus a farther tile that IS the raw min(tuple). The OLD apply used min(tiles)
    # = (1, 9) (lex-min tuple, distance 10); the OLD execute used Manhattan-min = (5, 0)
    # (distance 5). Both now resolve to the Manhattan-nearest (5, 0) — they agree.
    tiles = frozenset([(1, 9), (5, 0)])
    assert nearest_tile(0, 0, tiles) == (5, 0)


def test_negative_origin_coordinates():
    assert nearest_tile(-3, -3, frozenset([(-2, -3), (5, 5)])) == (-2, -3)
