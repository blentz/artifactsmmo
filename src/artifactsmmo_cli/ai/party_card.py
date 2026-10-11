"""A character's party card: the state its siblings judge a party fight with
(docs/PLAN_group_fights.md increment 4a).

Each character publishes its card every cycle (`CoordinationStore.
publish_party_card`); a sibling rebuilds it as a `WorldState`
(`card_state`) for `WorldState.party`. The card carries exactly what a party
fight reads of a member, and what readiness reads:

* the fight — level, HP, the combat stats `combat.combat_terms` projects
  (attack, dmg, per-element dmg, resistance, critical strike, initiative,
  wisdom, prospecting), the worn gear and the bag (`pick_loadout_cached`'s
  pool), the skills and gold and bank items (`loadout_win.stockable_potions`:
  what potions it can stock), the utility-slot stacks;
* readiness — position (layer, x, y) and cooldown expiry
  (`party_lease_core.assembled`).

Everything else a `WorldState` must carry is left at an inert value: a card
is never planned FOR, only fought beside."""

import json
from datetime import datetime
from typing import Any

from artifactsmmo_cli.ai.world_state import WorldState


def card_json(state: WorldState) -> str:
    """`state`'s card as JSON (see the module doc)."""
    card: dict[str, Any] = {
        "character": state.character, "level": state.level, "hp": state.hp,
        "max_hp": state.max_hp, "gold": state.gold, "skills": state.skills,
        "x": state.x, "y": state.y, "layer": state.layer,
        "inventory": state.inventory, "inventory_max": state.inventory_max,
        "inventory_slots_max": state.inventory_slots_max,
        "equipment": state.equipment,
        "cooldown_expires": (state.cooldown_expires.isoformat()
                             if state.cooldown_expires is not None else None),
        "bank_items": state.bank_items, "wisdom": state.wisdom,
        "prospecting": state.prospecting, "attack": state.attack, "dmg": state.dmg,
        "dmg_elements": state.dmg_elements, "resistance": state.resistance,
        "critical_strike": state.critical_strike, "initiative": state.initiative,
        "utility1_slot_quantity": state.utility1_slot_quantity,
        "utility2_slot_quantity": state.utility2_slot_quantity,
    }
    return json.dumps(card, sort_keys=True)


def card_state(card: str) -> WorldState:
    """The `WorldState` a published card describes (see the module doc)."""
    c = json.loads(card)
    expires = c["cooldown_expires"]
    return WorldState(
        character=c["character"], level=c["level"], xp=0, max_xp=0, hp=c["hp"],
        max_hp=c["max_hp"], gold=c["gold"], skills=c["skills"], x=c["x"], y=c["y"],
        inventory=c["inventory"], inventory_max=c["inventory_max"],
        inventory_slots_max=c["inventory_slots_max"], equipment=c["equipment"],
        cooldown_expires=datetime.fromisoformat(expires) if expires is not None else None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=c["bank_items"], bank_gold=None, pending_items=None,
        wisdom=c["wisdom"], prospecting=c["prospecting"], attack=c["attack"], dmg=c["dmg"],
        dmg_elements=c["dmg_elements"], resistance=c["resistance"],
        critical_strike=c["critical_strike"], initiative=c["initiative"],
        utility1_slot_quantity=c["utility1_slot_quantity"],
        utility2_slot_quantity=c["utility2_slot_quantity"], layer=c["layer"],
    )
