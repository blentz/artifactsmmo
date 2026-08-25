"""Which server rejections mean the MODEL is wrong, not the state.

Most API errors are contingent: the bag is full, the gold is short, the
character is on cooldown. The state changes and the action becomes possible, so
retrying is correct.

A few are categorical. They say *this item is not eligible for this action*,
which is a fact about game data and no amount of playing changes it. Retrying
one is pure waste against the per-IP rate budget that binds the fleet, and the
bot has no other feedback path from a refusal back into its own model of what is
possible.

Live 2026-08-23: `Recycle(water_boost_potion x1)` was sent 37 times over eight
hours, every one answered 473. `RecycleAction.is_applicable` admits anything
with a craft recipe whose skill gate is met, and the potion has one (alchemy 10,
character at 13) — but the server recycles EQUIPMENT only. Inferred from every
recycle outcome ever recorded: amulet, body_armor, boots, helmet, leg_armor,
ring, shield and weapon are accepted; `utility` is refused.

Codes come from `utils/helpers.ERROR_MESSAGES`, which is the transcribed API
error taxonomy.
"""

CATEGORICAL_REJECTIONS = frozenset({
    472,  # Invalid equipment item
    473,  # Invalid item for recycling
    476,  # Invalid consumable item
    485,  # This item is already equipped
    437,  # Invalid item for Grand Exchange
    441,  # Item not for sale from NPC
    442,  # NPC does not buy this item
})
"""Rejections that mean "this item is ineligible for this action", full stop.

Six of the seven name a pure ITEM/ACTION mismatch. Deliberately excluded, though
they might look similar: 493 ("does not meet skill level requirements") is a
gate a level-up opens, and 471/478 (quantity/materials) are answered by
acquiring more. Those are contingent and must keep retrying.

485 IS THE ODD ONE AND IT IS DELIBERATE. "This item is already equipped" is not
a fact about game data — unequip the worn copy and the same equip succeeds — so
on the letter of the rule above it is contingent. It is here because of what it
tells us: 485 fires only when the planner believed a code could occupy a second
slot, i.e. when our per-code occupancy MODEL disagrees with the server. That is
precisely the "our model of what is possible is wrong" condition this module
exists to feed back, and no amount of playing fixes a wrong model.

Live 2026-08-22: Lor sent the same `Equip(lich_race_medal -> artifact2/3_slot)`
55 times in 50 minutes through four different goals, every one answered 485,
because `DUPLICATE_SLOT_TYPES` asserted (never probed) that artifacts were
multi-slot. Zero progress, whole per-IP budget. The model has since been
corrected — but a corrected model is exactly what was believed on 2026-07-03,
and the point of this entry is that the NEXT wrong occupancy assertion costs one
cycle instead of a day.

The unequip that would make a 485-refused equip legal changes `state.equipment`,
which `plannability_signature` does NOT carry (it is `(level, skills)`), so this
poisoning does not self-heal on that specific change — it heals on a level/skill
change or when `DoomedMemo`'s escalating re-probe window elapses (20 → 160
cycles). That bound is the whole point and the cost is nil: while the code is
still worn the server refuses anyway, and once it is unequipped the loadout
picker re-derives the equip from the free slot on the next re-probe.
"""


def is_categorical_rejection(code: int) -> bool:
    """Does `code` mean the action can never succeed for this target?

    Defaults FALSE for anything unclassified. That direction is deliberate: a
    wrong `True` silently disables an action the bot needs, while a wrong
    `False` only costs the retries it already pays today.
    """
    return code in CATEGORICAL_REJECTIONS


def rejection_key(action: object) -> str | None:
    """Quantity-free identity for poisoning an action, or None if it has no item.

    NOT `learning_key()` / `repr`. `_build_actions`' existing backoff filter
    carries the warning: the factory builds unsized actions (`Gather(x×1)`)
    while blocks are recorded from goal-sized ones (`Gather(x×47)`), so a repr
    match "would silently match nothing". Recycle has the same exposure — the
    live log holds `Recycle(water_boost_potion×1)` and
    `Recycle(fire_boost_potion×2)`.

    A categorical rejection is a fact about the ITEM and the ACTION KIND:
    "water_boost_potion is not recyclable" holds at every quantity. Keying on
    (class, code) is therefore both the honest identity and the one that cannot
    walk into that trap.

    None when the action carries no `code`, because every categorical rejection
    is an item-eligibility fact and there is nothing to poison without an item.
    """
    code = getattr(action, "code", None)
    if not isinstance(code, str) or not code:
        return None
    return f"{type(action).__name__}:{code}"
