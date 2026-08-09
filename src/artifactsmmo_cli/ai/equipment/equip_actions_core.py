"""Pure core: how many equip actions separate one loadout from another.

S-020 (`docs/spec_cycle_oracle/SPEC.md`): *"Wearing it is an executed action. Where
the rung's loadout differs from the one the character arrives with, the rung's cost
includes the equip actions required to reach it, under S-005."*

WHY. The cycle oracle judges beatability with the best loadout the character is
already CARRYING, not merely what it is wearing — `predict_win` picks from
inventory ∪ equipped. That is deliberate and load-bearing: the gear branch projects
a candidate by placing the item in INVENTORY, so an oracle that only ever looked at
worn gear would make every gear candidate project byte-identically to the trunk.
That bug has already been had here; its post-mortem is in
`tiers/branch_objective.gear_candidate`.

But the projection was taking the upgrade for FREE. The executor has to spend a
cycle equipping it, and S-004's unit is executed actions, so an unpriced equip is a
cost the projection simply omits. The blind Phase 2 round found the hole from the
other side (W-006) and recommended consulting only worn gear; that would have been
the cleaner contract and would have re-broken the gear branch. Charging the action
closes the same hole without giving up the carried-gear reading.
"""


def equip_actions(worn: dict[str, str | None], target: dict[str, str | None]) -> int:
    """Equip actions to go from `worn` to `target` — one per slot that changes.

    Both maps are slot -> item code or None. A slot absent from either map and a
    slot explicitly holding None mean the same thing (empty), so the two spellings
    can never disagree: `WorldState.equipment` carries every slot including the
    empty ones, while a loadout picked for a purpose may omit slots it has no
    opinion about, and comparing those two directly would otherwise invent an
    action for every unmentioned empty slot.

    Taking a piece OFF is also an action and is counted the same way. The game
    equips into an occupied slot without a separate unequip, so a slot going from
    one item to another is ONE action rather than two — the count is over slots
    that differ, not over items moved.
    """
    return sum(
        1 for slot in set(worn) | set(target)
        if (worn.get(slot) or None) != (target.get(slot) or None)
    )
