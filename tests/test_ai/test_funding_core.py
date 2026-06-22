"""Pure core: cycles needed to fund a currency target, given a per-task floor."""
from artifactsmmo_cli.ai.goals.funding_core import funding_cycles_pure


def test_already_funded_zero_cycles():
    assert funding_cycles_pure(8, 8, 2) == 0
    assert funding_cycles_pure(10, 8, 2) == 0


def test_exact_multiple():
    assert funding_cycles_pure(0, 8, 2) == 4


def test_ceil_rounds_up():
    assert funding_cycles_pure(0, 9, 2) == 5   # ceil(9/2)
    assert funding_cycles_pure(3, 8, 2) == 3    # ceil(5/2)


def test_floor_one():
    assert funding_cycles_pure(0, 8, 1) == 8
