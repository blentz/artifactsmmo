"""The utility slots: which one a consumable goes into, and how much one holds.

The two utility slots are the only equipment slots that carry a QUANTITY, and
the only ones a craft ladder ever targets.  `utility_slot_for` is the SOLE
producer of the answer "which of the two" — `craft_ladder.craft_utility_ladder`
and `ProvisionMarginalFightGoal` both ASK it rather than each hard-coding
`"utility1_slot"`, which is what they did until 2026-08-25 and which made the
CRAFT_POTIONS boost-stock arm equip its boost over the heal stack whose
satisfaction had gated the arm (a two-cycle alternation, no fixed point).
"""

from artifactsmmo_cli.ai.world_state import WorldState

UTILITY_SLOTS: tuple[str, str] = ("utility1_slot", "utility2_slot")

_QTY_ATTR = {"utility1_slot": "utility1_slot_quantity",
             "utility2_slot": "utility2_slot_quantity"}


def utility_slot_quantity(state: WorldState, slot: str) -> int:
    """Units held in `slot`; 0 for any non-utility slot, which carries no
    quantity at all (an equipment slot holds exactly one item)."""
    attr = _QTY_ATTR.get(slot)
    return 0 if attr is None else int(getattr(state, attr))


def utility_slot_for(code: str, state: WorldState) -> str:
    """The utility slot `code` should be equipped into.  Three rules, in order:

    1. **The slot already holding `code`.**  Not a preference, a REQUIREMENT:
       utility is not in `DUPLICATE_SLOT_TYPES`, so the server refuses (HTTP
       485) a code already worn in the sibling slot, and `EquipAction.apply`
       models the same-code utility equip as ADDITIVE (M + q).  Any other
       answer here is non-executable.
    2. **A free slot, `utility1_slot` first.**  Preferring free over occupied
       is the whole fix: nothing is displaced, so no stocked consumable is
       destroyed to make room for another.  Slot 1 first is deterministic and
       agrees with `ObjectiveTiers.utility_potion_targets`, which designates
       slot 1 for the primary heal and slot 2 for the secondary.
    3. **Both occupied by OTHER codes — displace the SMALLER stack**, ties
       broken to `utility2_slot`.  Something has to go, and quantity is the
       honest measure of how much provisioning the displacement costs (a
       displaced stack returns to inventory, so the cost is bag pressure plus
       a re-equip, not destruction).  The tie-break keeps slot 1 — the
       primary-heal slot — stable, so a boost evicts the secondary rather
       than the heal the character actually fights with.

    Deliberately NOT a value or effect ranking: pricing consumables against
    each other would be a second reading of the potion-provisioning value the
    goals already own, and this function has no game data to do it with.
    """
    for slot in UTILITY_SLOTS:
        if state.equipment.get(slot) == code:
            return slot
    for slot in UTILITY_SLOTS:
        if state.equipment.get(slot) is None:
            return slot
    first, second = UTILITY_SLOTS
    if utility_slot_quantity(state, first) < utility_slot_quantity(state, second):
        return first
    return second


def already_provisioned(state: WorldState) -> bool:
    """Whether a utility slot already holds a consumable.

    SOLE definition of "provisioned".  `ProvisionMarginalFightGoal.is_satisfied`
    is this predicate, and `strategy_driver._marginal_provision_goal` early-exits
    to the grind on it — the emitter has to answer the question BEFORE it can
    build the goal that would answer it, so the two ask this function rather
    than the goal asking itself and the emitter re-deriving it.

    They were byte-identical hand-copies until 2026-08-25, and the suite did not
    notice: narrowing the emitter to `utility1_slot` alone left all 6040 tests
    in `tests/test_ai` green, because each site had its own tests and nothing
    tested that they AGREE.  One definition makes that drift unrepresentable.
    """
    return any(state.equipment.get(slot) is not None for slot in UTILITY_SLOTS)
