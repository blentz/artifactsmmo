"""Pure predicate: does the equipped gear already match an optimal loadout?

`pick_loadout` returns only the slots the chosen loadout fills, using `None`
to mean "this slot should be EMPTY". `state.equipment` carries only its filled
slots. Whole-dict equality therefore always disagrees on shape, so both
`FightAction.cost` (soft LOADOUT_PENALTY) and `FightAction.is_applicable` (the
hard optimal-loadout gate) compare per-slot through this single locus — no
divergent loadout logic.
"""


def equipped_matches_loadout(
    equipment: dict[str, str | None], optimal: dict[str, str | None]
) -> bool:
    """True iff, for every slot the optimal loadout names, `equipment` holds the
    same code (`equipment.get(slot)` defaulting to None to match an absent slot
    or an explicit None target)."""
    return not any(equipment.get(slot) != code for slot, code in optimal.items())
