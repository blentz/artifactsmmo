"""Reconcile predicted open-order state against API truth each cycle.

apply() predicts posts/cancels optimistically; the API's list of the character's
currently-open orders is the source of truth. An order present last cycle but gone
(or reduced in quantity) this cycle is a FILL, reported in `filled`. Still-open
orders age by one cycle (the TTL cancel reads that age).

`filled` is informational only (e.g. a debug line). Settlement — gold for a SELL,
item delivery for a BUY — is NOT driven from here: it is API-authoritative and
already reflected in the caller's fresh character/pending reads each cycle."""

from typing import NamedTuple

from artifactsmmo_cli.ai.open_order import OpenOrder


class ReconcileResult(NamedTuple):
    open_orders: tuple[OpenOrder, ...]
    filled: tuple[OpenOrder, ...]


def reconcile_open_orders(
    prev: tuple[OpenOrder, ...], api_open: tuple[OpenOrder, ...]
) -> ReconcileResult:
    by_id = {o.id: o for o in api_open}
    still_open: list[OpenOrder] = []
    filled: list[OpenOrder] = []
    for p in prev:
        current = by_id.get(p.id)
        if current is None:
            filled.append(p)                       # whole order filled/gone
            continue
        if current.qty < p.qty:
            filled.append(p._replace(qty=p.qty - current.qty))   # partial fill delta
        still_open.append(current._replace(age=p.age + 1))       # keep aging
    # Orders the API reports that we did not know about (e.g. restored session) pass
    # through un-aged so the planner still tracks them.
    known = {p.id for p in prev}
    for o in api_open:
        if o.id not in known:
            still_open.append(o)
    ordered = tuple(sorted(still_open, key=lambda o: (o.side.value, o.code, o.price, o.id)))
    return ReconcileResult(open_orders=ordered, filled=tuple(filled))
