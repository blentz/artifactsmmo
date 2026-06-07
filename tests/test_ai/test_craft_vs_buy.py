"""cheaper_acquisition: BUY iff affordable (gold - price >= reserve) AND buy < craft."""
from artifactsmmo_cli.ai.craft_vs_buy import Method, cheaper_acquisition


def test_buys_when_affordable_and_strictly_cheaper():
    # craft 80 cd, buy 5 cd, price 100, gold 1000, reserve 200 -> affordable, cheaper -> BUY
    assert cheaper_acquisition(80, 5, 100, 1000, 200) == Method.BUY


def test_crafts_when_unaffordable_even_if_cheaper():
    # gold 250, price 100, reserve 200 -> gold-price=150 < 200 -> not affordable -> CRAFT
    assert cheaper_acquisition(80, 5, 100, 250, 200) == Method.CRAFT


def test_crafts_when_not_strictly_cheaper():
    # buy 80 == craft 80 -> not strictly cheaper -> CRAFT
    assert cheaper_acquisition(80, 80, 100, 1000, 200) == Method.CRAFT


def test_affordability_boundary_equal_is_affordable():
    # gold-price == reserve (800-600=200) -> affordable (>=) -> BUY when cheaper
    assert cheaper_acquisition(80, 5, 600, 800, 200) == Method.BUY


def test_affordability_boundary_one_short_is_not():
    assert cheaper_acquisition(80, 5, 601, 800, 200) == Method.CRAFT
