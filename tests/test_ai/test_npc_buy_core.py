"""Pure core: NPC purchase inventory bookkeeping (`npc_buy_core.py`).

`npc_buy_currency_apply_pure` draws the pay-currency stack down by
`total_spent`; a purchase that spends the exact on-hand balance must leave
NO zero-quantity key behind (matches the `del`-on-zero guard used by
`EquipAction.apply` / `WithdrawItemAction.apply`) — a phantom `code: 0` key
would otherwise be miscounted as an occupied inventory SLOT by
`WorldState.inventory_slots_used` (see test_world_state_slots.py).
"""
from artifactsmmo_cli.ai.actions.npc_buy_core import (
    npc_buy_apply_pure,
    npc_buy_currency_apply_pure,
    npc_buy_currency_is_applicable_pure,
    npc_buy_is_applicable_pure,
)


def test_currency_apply_deletes_currency_key_at_exact_balance() -> None:
    """Spending the exact on-hand currency balance removes the key entirely."""
    post = npc_buy_currency_apply_pure(
        {"rune": 0, "coin": 100}, "rune", 1, "coin", 100)
    assert "coin" not in post
    assert post["rune"] == 1


def test_currency_apply_keeps_currency_key_when_balance_remains() -> None:
    """A partial spend leaves the currency key in place with the remainder."""
    post = npc_buy_currency_apply_pure({"coin": 150}, "rune", 1, "coin", 100)
    assert post["coin"] == 50


def test_currency_apply_preserves_other_entries() -> None:
    post = npc_buy_currency_apply_pure(
        {"coin": 100, "other": 3}, "rune", 1, "coin", 100)
    assert "coin" not in post
    assert post["other"] == 3
    assert post["rune"] == 1


def test_currency_apply_does_not_mutate_input() -> None:
    inv = {"coin": 100}
    npc_buy_currency_apply_pure(inv, "rune", 1, "coin", 100)
    assert inv == {"coin": 100}


def test_is_applicable_true_when_slot_and_gold_ok() -> None:
    assert npc_buy_is_applicable_pure(
        inv_used=0, inv_max=10, quantity=1, gold=10, price=10) is True


def test_is_applicable_false_when_slot_short() -> None:
    assert npc_buy_is_applicable_pure(
        inv_used=10, inv_max=10, quantity=1, gold=1000, price=1) is False


def test_is_applicable_false_when_gold_short() -> None:
    assert npc_buy_is_applicable_pure(
        inv_used=0, inv_max=10, quantity=1, gold=1, price=10) is False


def test_apply_mints_item() -> None:
    assert npc_buy_apply_pure({}, "x", 3) == {"x": 3}


def test_currency_is_applicable_true_when_slot_and_currency_ok() -> None:
    assert npc_buy_currency_is_applicable_pure(
        inv_used=0, inv_max=10, quantity=1,
        currency_on_hand=100, total_spent=100) is True


def test_currency_is_applicable_false_when_currency_short() -> None:
    assert npc_buy_currency_is_applicable_pure(
        inv_used=0, inv_max=10, quantity=1,
        currency_on_hand=50, total_spent=100) is False
