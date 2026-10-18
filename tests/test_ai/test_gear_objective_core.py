"""Unit tests for the gear objective's pure core (spec 2026-10-18 §2.3, §2.4):
the layered fixed point of achievable items and the missing-piece order key."""
from fractions import Fraction

import pytest

from artifactsmmo_cli.ai.gear_objective_core import (
    achievable_layers,
    layer_of,
    objective_held,
    piece_order_key,
)


def _table_unlock(table: dict[frozenset[str], frozenset[str]]):
    return lambda held: table.get(held, held)


def test_layers_stop_at_the_first_empty_layer() -> None:
    unlock = _table_unlock({
        frozenset({"a"}): frozenset({"a", "b"}),
        frozenset({"a", "b"}): frozenset({"a", "b", "c"}),
    })
    assert achievable_layers(frozenset({"a"}), unlock) == (
        frozenset({"a"}), frozenset({"b"}), frozenset({"c"}),
    )


def test_an_inert_unlock_leaves_only_the_base() -> None:
    assert achievable_layers(frozenset({"a"}), lambda held: held) == (frozenset({"a"}),)


def test_an_empty_base_is_layer_zero() -> None:
    unlock = _table_unlock({frozenset(): frozenset({"a"})})
    assert achievable_layers(frozenset(), unlock) == (frozenset(), frozenset({"a"}))


def test_a_shrinking_unlock_is_refused() -> None:
    unlock = _table_unlock({frozenset({"a", "b"}): frozenset({"a"})})
    with pytest.raises(AssertionError):
        achievable_layers(frozenset({"a", "b"}), unlock)


def test_a_later_shrink_is_refused() -> None:
    unlock = _table_unlock({
        frozenset({"a"}): frozenset({"a", "b"}),
        frozenset({"a", "b"}): frozenset({"b", "c"}),
    })
    with pytest.raises(AssertionError):
        achievable_layers(frozenset({"a"}), unlock)


def test_layer_of_names_each_item_its_layer() -> None:
    layers = (frozenset({"a"}), frozenset({"b", "d"}), frozenset({"c"}))
    assert layer_of(layers) == {"a": 0, "b": 1, "d": 1, "c": 2}


def test_layer_of_refuses_an_item_in_two_layers() -> None:
    with pytest.raises(AssertionError):
        layer_of((frozenset({"a"}), frozenset({"a"})))


def test_lower_layer_orders_first_whatever_the_gain() -> None:
    low = piece_order_key(0, Fraction(1), Fraction(100), 0)
    high = piece_order_key(1, Fraction(1000), Fraction(1), 0)
    assert low < high


def test_within_a_layer_gain_per_price_orders() -> None:
    assert piece_order_key(0, Fraction(10), Fraction(2), 0) < piece_order_key(0, Fraction(10), Fraction(5), 0)


def test_ratio_outranks_a_larger_raw_gain() -> None:
    assert piece_order_key(0, Fraction(2), Fraction(1), 0) < piece_order_key(0, Fraction(10), Fraction(100), 0)


def test_equal_ratio_prefers_the_larger_gain_then_slot_rank() -> None:
    assert piece_order_key(0, Fraction(4), Fraction(2), 0) < piece_order_key(0, Fraction(2), Fraction(1), 0)
    assert piece_order_key(0, Fraction(2), Fraction(1), 0) < piece_order_key(0, Fraction(2), Fraction(1), 3)


def test_the_key_is_layer_ratio_gain_slot_rank() -> None:
    assert piece_order_key(2, Fraction(3), Fraction(4), 5) == (2, Fraction(-3, 4), Fraction(-3), 5)


def test_a_zero_gain_is_a_legal_key() -> None:
    assert piece_order_key(0, Fraction(0), Fraction(1), 0) == (0, Fraction(0), Fraction(0), 0)


def test_a_free_price_is_refused() -> None:
    with pytest.raises(AssertionError):
        piece_order_key(0, Fraction(1), Fraction(0), 0)


def test_a_negative_price_is_refused() -> None:
    with pytest.raises(AssertionError):
        piece_order_key(0, Fraction(1), Fraction(-1), 0)


def test_held_iff_nothing_missing() -> None:
    assert objective_held(frozenset()) is True
    assert objective_held(frozenset({"copper_helmet"})) is False
