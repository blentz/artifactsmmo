"""The state a skill grind reasons about: `state` minus the rung's own copies.

A grind earns its XP from the CRAFT. Copies the character already carries,
banks or WEARS are therefore not a way to serve it — you cannot gain
weaponcrafting xp by owning a dagger, only by making another one. Every
question a grind asks about a rung must be asked against a state where those
copies do not exist.

This lives in its own module because BOTH halves of the grind ask it and they
import in opposite directions: `level_skill_expand` (the descent) already
imported `tiers.skill_grind_target` (the selection), so the selection cannot
import the descent back. Mirroring the projection into both would be the
failure `ai/gather_skill_gate.py` exists to document — one predicate, two call
sites, drift. One definition, two consumers.

WHY THE SELECTION NEEDS IT (live Lor + HAL, 2026-08-14): `skill_grind_target`
ranked candidates by `acquire_steps` computed against ACTUAL holdings, so a
rung the character was already carrying priced at **0** — unbeatable, and
re-selected every cycle forever. Lor carried 3 `apprentice_gloves`, so the
grind kept choosing `apprentice_gloves` and farming chickens for feathers:
**704 fights, 0 character xp, weaponcrafting 8 -> 8 across 757 grind cycles**,
while `sticky_dagger` and `fire_staff` sat at 59 steps unchosen. The DESCENT
had stripped holdings since the batching epic; the SELECTION never did.
"""

import dataclasses

from artifactsmmo_cli.ai.world_state import WorldState


def grind_probe_state(state: WorldState, rung: str) -> WorldState:
    """`state` with every carried, banked and WORN copy of `rung` removed.

    A descent/ranking state, NOT a state anything executes against.

    `prerequisites` leafs an item that is already owned, already worn, or has a
    ready withdraw source, and each of those stops a descent dead at the rung;
    `acquisition_actions` likewise prices an owned item at zero. Discounting the
    rung's own holdings is what keeps both the deficit and the cost real.

    The equipment slots matter as much as the bag: `ObtainItem.is_satisfied`
    reports an EQUIPPABLE satisfied whenever its code is worn, IGNORING
    quantity (`tiers/meta_goal.py`). A gear grind wears what it makes, so the
    very first rung the character equips would otherwise leaf the rung on the
    `is_satisfied` arm and no quantity could ever defeat it.

    Only the rung's OWN entries are dropped. Every other material and every
    other equipped item stays, so a material that IS legitimately in hand still
    leafs normally, and the combat stats behind `_producible`'s winnability gate
    lose only the one item the grind is about to make another of.
    """
    inventory = {code: qty for code, qty in state.inventory.items()
                 if code != rung}
    bank_items = (None if state.bank_items is None
                  else {code: qty for code, qty in state.bank_items.items()
                        if code != rung})
    equipment = {slot: (None if code == rung else code)
                 for slot, code in state.equipment.items()}
    return dataclasses.replace(state, inventory=inventory,
                               bank_items=bank_items, equipment=equipment)
