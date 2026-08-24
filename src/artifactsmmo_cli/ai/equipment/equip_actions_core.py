"""Pure core: what it costs to go from one loadout to another.

S-020 (`docs/spec_cycle_oracle/SPEC.md`). The cycle oracle judges beatability with
the best loadout the character is already CARRYING, not merely what it is wearing —
`predict_win` picks from inventory ∪ equipped. That is deliberate and load-bearing:
the gear branch projects a candidate by placing the item in INVENTORY, so an oracle
that only ever looked at worn gear would make every gear candidate project
byte-identically to the trunk. That bug has already been had here; its post-mortem
lived in `tiers/branch_objective.gear_candidate`, which wave 3b deleted with the
rest of the retired ranking — the reading it justifies is unchanged.

But the projection was taking the upgrade for FREE. The executor has to spend time
putting each piece on, and S-004's unit is executed actions, so an unpriced equip is
a cost the projection simply omits. The blind Phase 2 round found the hole from the
other side (W-006) and recommended consulting only worn gear; that would have been
the cleaner contract and would have re-broken the gear branch. Charging the change
closes the same hole without giving up the carried-gear reading.

TWO SERVER RULES, BOTH PUBLISHED, BOTH PREVIOUSLY GUESSED WRONG HERE. The first
version of this module counted one action per differing SLOT, on a docstring that
asserted "the game equips into an occupied slot without a separate unequip". The
OpenAPI schema says otherwise, and says it in an error code:

    POST /my/{name}/action/equip     491: The equipment slot is not empty.
    POST /my/{name}/action/unequip   491: The equipment slot is empty.

So a slot going from one item to another is TWO item movements, not one — the old
item must come off before the new one goes on. Counting slots under-charged every
upgrade a character makes after its first, which is every upgrade that matters.

The second rule runs the other way, and is larger:

    "Equip multiple items on your character. The cooldown will be 3 seconds
     multiplied by the number of different items equipped."

An equip is 3 seconds per item, not a full action. Against S-004's unit — one Fight
— charging a whole fight-equivalent per piece over-priced a loadout change by an
order of magnitude, and on a bare character's first rung it invented sixteen fights'
worth of cost out of nothing.

The two errors were not cancelling. One is a factor of two on swaps only; the other
is a factor of ten on everything.

DELIBERATELY NOT MODELLED: the executor's failure modes on this path — `497` when
inventory is full, `483` when removing an HP-granting piece would drop the character
too low. Those are conditions on whether the change can be made at all, which is the
executor's and the loadout selection's problem (S-020 places both in background),
not a component of what it costs when it can.
"""

from artifactsmmo_cli.ai.learning.fight_loop_cost import TYPICAL_FIGHT_COOLDOWN_SECONDS

EQUIP_SECONDS_PER_ITEM = 3.0
"""Published cooldown contributed by ONE item moved, in seconds.

The endpoints charge "3 seconds multiplied by the number of different items", so a
batch of `n` costs `3n` however it is grouped into requests. That makes the item —
not the request and not the slot — the unit this module counts."""


def items_moved(worn: dict[str, str | None], target: dict[str, str | None]) -> int:
    """Item movements to go from `worn` to `target`.

    Both maps are slot -> item code or None. A slot absent from either map and a
    slot explicitly holding None mean the same thing (empty), so the two spellings
    can never disagree: `WorldState.equipment` carries every slot including the
    empty ones, while a loadout picked for a purpose may omit slots it has no
    opinion about, and comparing those two directly would otherwise invent a
    movement for every unmentioned empty slot.

    A slot that gains an item costs one movement, a slot that loses one costs one,
    and a slot that SWAPS costs two — the server refuses to equip into an occupied
    slot (`491`), so the outgoing piece must come off first. Counting differing
    slots instead, as this module first did, silently prices every swap as if the
    old item evaporated.
    """
    return sum(
        (1 if (worn.get(slot) or None) is not None else 0)
        + (1 if (target.get(slot) or None) is not None else 0)
        for slot in set(worn) | set(target)
        if (worn.get(slot) or None) != (target.get(slot) or None)
    )


def equip_cost(worn: dict[str, str | None], target: dict[str, str | None]) -> float:
    """Cost of the loadout change, in Fight-equivalents (S-004).

    Each item movement is a published 3 seconds, converted by the duration of one
    Fight because that is the unit. A whole sixteen-slot outfitting therefore costs
    about 1.6 fights' worth of time rather than sixteen fights.
    """
    return (items_moved(worn, target) * EQUIP_SECONDS_PER_ITEM
            / TYPICAL_FIGHT_COOLDOWN_SECONDS)
