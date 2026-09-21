"""How many units of an item-currency purchase fit in ONE bag-load.

`NpcBuyAction`'s non-gold branch (via the proved
`Formal.NpcBuyInventory.isApplicableCurrency` /
`npc_buy_core.npc_buy_currency_is_applicable_pure`) requires BOTH at the moment
of purchase:

    free >= quantity                      (a slot for each bought unit)
    currency_on_hand >= price * quantity  (the pay stack, IN THE BAG)

so the peak occupancy of a `quantity`-unit trip is `quantity * price` currency
units plus the `quantity` items they turn into. A batch sized to the whole
remaining need is therefore not merely unaffordable today — it is unsatisfiable
at ANY moment, because no sequence of deposits can make a 144-item bag hold 500
event tickets.

Live HAL, 2026-09-20. `lich_race_trophy` costs 10 `lich_race_medal`, the fleet
held 6, and 581 `event_ticket` sat in the bank — enough for the 5 more medals
that close it. `GatherMaterials(lich_race_medal, x5)` materialised one
indivisible buy and one withdraw sized to the whole need::

    Withdraw(event_ticket x498)               applicable=False   bag 122/144
    NpcBuy(lich_race_medal x5@archaeologist)  applicable=False   500 at once
    GatherMaterials(lich_race_medal, x5)      explored=4  plan_len=0

and behind that the whole fleet-currency turn-in — `SurrenderCurrencyGoal`,
which has the four siblings unequip and bank their worn medals — stayed gated
on a fleet total that could never rise.

THE BOUND IS `inventory_max`, NOT CURRENT FREE SPACE. The goal's own pool
already carries `DepositAll`, so the planner can clear the bag as part of the
plan; what it can never do is carry more than the bag holds. Sizing to current
free space instead would make the batch flap with whatever junk happens to be
carried, and would emit nothing at all on the cycles that need it most.
"""


def currency_buy_batch_pure(needed: int, price: int, inventory_max: int) -> int:
    """Units of an item-currency purchase to attempt in one trip.

    `needed` when the whole need already fits, otherwise the largest batch that
    does, and 0 when not even one unit can ever fit — an honest refusal, so the
    caller emits no edge rather than one that is inapplicable forever.

    A non-positive `price` is not an item-currency purchase (gold pays from
    `state.gold`, which costs no bag space) and passes `needed` straight
    through: this function must never shrink a gold buy.
    """
    if needed <= 0:
        return 0
    if price <= 0:
        return needed
    return min(needed, inventory_max // (price + 1))
