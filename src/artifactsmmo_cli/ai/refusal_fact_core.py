"""Does a recorded categorical refusal still hold? (Phase 5-1 of
docs/PLAN_decision_architecture_redesign.md.)

A categorical refusal (`action_rejection.CATEGORICAL_REJECTIONS`) is a fact
about an item and an action kind, not about the moment it was answered, so it
is kept as a fact rather than re-probed on a timer. Mirrored by
`Formal/RefusalFact.lean`.
"""

ALREADY_EQUIPPED = 485
""""This item is already equipped": a fact about the worn loadout, not about the
item. It holds exactly while the code is worn — unequip it and the same equip
succeeds."""


def refusal_holds(http_code: int, recorded_type: str | None,
                  current_type: str | None, worn: bool) -> bool:
    """Is the refused action still refused?

    485 holds while the code is worn. Every other categorical refusal ("not
    recyclable", "NPC does not buy this", ...) is a fact of game data and holds
    while the item's game-data type is the one recorded at the refusal: a season
    reset that redefines the item voids it."""
    if http_code == ALREADY_EQUIPPED:
        return worn
    return recorded_type == current_type
