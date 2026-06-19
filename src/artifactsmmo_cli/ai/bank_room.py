"""Pure predicate: can the bank physically accept a deposited item?

`bank_capacity is None` = capacity unknown (NOT room); `bank_items is None` =
bank never visited (NOT room). Distinct from the `bank_capacity == 0` divide-
guard in BANK_EXPAND. Mirrors `Formal.Liveness.ProductionLadder.bankHasRoom`.

Takes primitive args (not full objects) to avoid an import cycle:
`guards.py` consumes `bank_has_room` and defines `SelectionContext`; if
`bank_room` imported `SelectionContext`, the cycle would be:
  guards → bank_room → guards."""


def bank_has_room(bank_accessible: bool,
                  bank_items: dict[str, int] | None,
                  bank_capacity: int | None) -> bool:
    if not bank_accessible:
        return False
    if bank_items is None or bank_capacity is None:
        return False
    return len(bank_items) < bank_capacity
