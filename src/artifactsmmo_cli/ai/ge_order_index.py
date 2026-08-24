"""The ONE reduction from a set of open Grand-Exchange orders to the best order
per item, on one side of the book.

Two callers need this rule and they must not each carry a copy:

* `GameData._load_ge_orders` pages the live API every startup, and
* `GameData.from_cache_bundle(..., with_ge_orders=True)` hydrates the order book
  captured into the committed scenario fixture.

Keeping the rule here is what lets the fixture hold the API's orders VERBATIM —
all of them, several per item — instead of a pre-reduced index that would bake
in this function's answer and leave the tie-breaking untested offline.

The side is passed in rather than read off `order.type_` because the live pager
ASKED the API for one side and got that side back; the request is the
authoritative statement of which half of the book a page belongs to.
"""

from collections.abc import Iterable

from artifactsmmo_api_client.models.ge_order_schema import GEOrderSchema
from artifactsmmo_api_client.models.ge_order_type import GEOrderType


def index_best_ge_orders(
    orders: Iterable[GEOrderSchema], side: GEOrderType
) -> dict[str, tuple[str, int, int]]:
    """`item_code -> (order_id, price, quantity)`, the best order per item.

    BUY keeps the HIGHEST price: filling a buy order sells the item for immediate
    gold, so the best one pays the most. SELL keeps the LOWEST price: filling a
    sell order buys the item for immediate, guaranteed acquisition, so the best
    one costs the least. Ties break by larger quantity, then by order id, so the
    index is a deterministic function of the book and two runs over the same
    orders cannot disagree.

    Orders are the API's; nothing here fabricates, filters or reprices one.
    """
    sign = 1 if side is GEOrderType.BUY else -1
    best: dict[str, tuple[str, int, int]] = {}
    for order in orders:
        current = best.get(order.code)
        if current is None or (sign * order.price, order.quantity, order.id) > (
            sign * current[1], current[2], current[0]
        ):
            best[order.code] = (order.id, order.price, order.quantity)
    return best
