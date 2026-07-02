"""Potion-provision quantity: how many heal potions to equip for a fight,
sized to the monster's learned/seeded HP-need. Pure decision core (proved in
formal/Formal/PotionProvisionQty.lean, differential + mutation gated). Replaces
the win-rate heuristic marginal_potion_qty_pure."""


def potion_provision_qty_pure(
    hp_need: int, potion_hp_restore: int, held_heal_qty: int,
    utility_slot_filled: bool, max_stack: int,
) -> int:
    """Potions to equip = ceil(hp_need / potion_hp_restore), clamped to what is
    held and to max_stack. 0 when the slot is already filled, nothing is held, or
    the potion restores nothing (avoids divide-by-zero and a useless equip)."""
    if utility_slot_filled or held_heal_qty <= 0 or potion_hp_restore <= 0:
        return 0
    desired = (hp_need + potion_hp_restore - 1) // potion_hp_restore  # ceil
    return min(desired, held_heal_qty, max_stack)
