"""`currency_buy_batch_pure`: how much of an item-currency buy fits one bag-load."""

from artifactsmmo_cli.ai.currency_buy_batch import currency_buy_batch_pure


def test_whole_need_when_it_fits() -> None:
    """Five units at 10 each need 5*(10+1) = 55 of a 144-item bag — no reason
    to split the trip."""
    assert currency_buy_batch_pure(needed=5, price=10, inventory_max=144) == 5


def test_shrinks_to_one_bag_load() -> None:
    """THE LIVE HAL CASE. Five `lich_race_medal` at 100 `event_ticket` each is
    500 tickets; the bag holds 144. One medal per trip — 100 tickets carried
    plus the medal itself is 101 of 144."""
    assert currency_buy_batch_pure(needed=5, price=100, inventory_max=144) == 1


def test_the_bound_leaves_room_for_the_bought_item() -> None:
    """`npc_buy_currency_is_applicable_pure` needs `free >= quantity` AS WELL
    AS the pay stack, so a batch is bounded by `quantity * (price + 1)`, not by
    `quantity * price`. At price 10 and a 20-item bag the loose bound would say
    2 (20 units of currency) and the buy would then have no slot to put them
    in; the correct answer is 1."""
    assert currency_buy_batch_pure(needed=9, price=10, inventory_max=20) == 1
    assert 1 * (10 + 1) <= 20 < 2 * (10 + 1)


def test_zero_when_not_even_one_unit_can_ever_fit() -> None:
    """An honest refusal, so the caller emits NO edge rather than one that is
    inapplicable forever. 100 tickets cannot coexist with a bought item in a
    100-item bag at any moment, whatever is deposited first."""
    assert currency_buy_batch_pure(needed=5, price=100, inventory_max=100) == 0


def test_gold_price_passes_straight_through() -> None:
    """A non-positive price is not an item-currency purchase — gold pays from
    `state.gold` and costs no bag space. This function must never shrink a gold
    buy, and `_buy_batch` also short-circuits on the currency code itself."""
    assert currency_buy_batch_pure(needed=7, price=0, inventory_max=20) == 7
    assert currency_buy_batch_pure(needed=7, price=-1, inventory_max=20) == 7


def test_nothing_needed_is_nothing_bought() -> None:
    assert currency_buy_batch_pure(needed=0, price=100, inventory_max=144) == 0
