"""Pure core of `owned_count`: total owned units of an item across inventory,
bank, and equipped slots, over already-fetched primitives.

Separated from `meta_goal.py` (which holds the MetaGoal/ObtainItem behavioral
classes) so the count logic is a standalone, differentially-verifiable function
(see `formal/Formal/OwnedCount.lean`)."""

from collections.abc import Collection, Mapping


def owned_count_pure(
    inventory: Mapping[str, int],
    bank: Mapping[str, int] | None,
    equipped_codes: Collection[str],
    code: str,
) -> int:
    """Total owned units of `code` = spare copies + bank copies + equipped copy.

    The `+1` for an equipped item is NOT a double-count: the ArtifactsMMO server
    tracks the equipped copy in a dedicated equipment SLOT, separate from the
    inventory list. `CharacterSchema` exposes each equipment slot as its own
    `<slot>: str` field and the inventory separately as
    `inventory: list[InventorySlot]`; `WorldState.from_character_schema` builds
    `inventory` from the inventory slots and reads equipment from the slot fields
    separately. Equipping DECREMENTS inventory by 1 (`EquipAction.apply`), so
    `inventory.get(code)` counts only the UNEQUIPPED (spare) copies and never
    includes the equipped copy. Hence the three terms are disjoint stores summed
    additively.

    A character CAN hold spare copies of an item it has equipped (e.g. 1 equipped
    sword + 1 spare in inventory → 2), and that count of 2 is correct: two swords
    are physically owned. There is no "equipped codes never in inventory"
    invariant — only the equipped/inventory STORES are separate.
    """
    total = inventory.get(code, 0)
    if bank is not None:
        total += bank.get(code, 0)
    if code in equipped_codes:
        total += 1
    return total
