"""Capture a character's per-level UNEQUIPPED base stats from the LIVE API.

Workstream B Phase-1 infra for docs/PLAN_faithfulness_modeling.md. The
WinnableAcrossBand sweep needs each level's BASE combat stats (the stats the
character has with NO gear equipped). The server only ever exposes base+gear
TOTALS on the character, so the only way to read base stats is to physically
unequip every item, read the totals (which now equal base), then re-equip.

This script captures the character's CURRENT level. The human runs it once per
level reached over a long real session; runs accumulate (RESUMABLE) into
formal/sim/character_base_stats.json keyed by str(level).

Each run:
  1. GET the character -> read level + currently-equipped item code per slot
     (the ORIGINAL loadout that MUST be restored).
  2. Unequip every non-empty equipment slot, respecting the per-action cooldown
     the server returns (response.data.cooldown.remaining_seconds) -> time.sleep.
  3. GET the character again -> totals now == BASE stats. Record them.
  4. Re-equip every originally-equipped item back into its slot (also respecting
     cooldowns). Restoration runs in a `finally` so it happens even if the
     mid-run sampling raises.
  5. Merge the captured row into the JSON and write it back, sorted.

Usage:
  uv run python formal/sim/capture_base_stats.py <character_name> [output_path]

Default output: formal/sim/character_base_stats.json
"""

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from artifactsmmo_api_client.models.equip_schema import EquipSchema
from artifactsmmo_api_client.models.error_response_schema import ErrorResponseSchema
from artifactsmmo_api_client.models.item_slot import ItemSlot
from artifactsmmo_api_client.models.unequip_schema import UnequipSchema

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

# Maps each CharacterSchema `*_slot` field that holds an equippable item to the
# ItemSlot the equip/unequip endpoints expect. Utility and bag slots are also
# equipment slots and contribute to totals, so they are unequipped/re-equipped
# too; their quantities live in the *_slot_quantity fields.
EQUIP_SLOTS: tuple[tuple[str, ItemSlot], ...] = (
    ("weapon_slot", ItemSlot.WEAPON),
    ("rune_slot", ItemSlot.RUNE),
    ("shield_slot", ItemSlot.SHIELD),
    ("helmet_slot", ItemSlot.HELMET),
    ("body_armor_slot", ItemSlot.BODY_ARMOR),
    ("leg_armor_slot", ItemSlot.LEG_ARMOR),
    ("boots_slot", ItemSlot.BOOTS),
    ("ring1_slot", ItemSlot.RING1),
    ("ring2_slot", ItemSlot.RING2),
    ("amulet_slot", ItemSlot.AMULET),
    ("artifact1_slot", ItemSlot.ARTIFACT1),
    ("artifact2_slot", ItemSlot.ARTIFACT2),
    ("artifact3_slot", ItemSlot.ARTIFACT3),
    ("utility1_slot", ItemSlot.UTILITY1),
    ("utility2_slot", ItemSlot.UTILITY2),
    ("bag_slot", ItemSlot.BAG),
)

# Per-slot quantity field for the utility slots (utilities can stack); all other
# slots equip a single item.
UTILITY_QUANTITY_FIELDS: dict[ItemSlot, str] = {
    ItemSlot.UTILITY1: "utility1_slot_quantity",
    ItemSlot.UTILITY2: "utility2_slot_quantity",
}


def _cooldown_seconds(response: Any) -> int:
    """Remaining cooldown seconds the server attached to an equip/unequip action.

    Path: response.data.cooldown.remaining_seconds (EquipmentResponseSchema ->
    EquipRequestSchema -> CooldownSchema). Fail loudly if the server did not
    return it — we only act on real API data, never a default.

    Raises RuntimeError if the server returned an error (e.g. HTTP 499 character
    in cooldown, HTTP 483 item not equipped) so the caller gets a clear failure
    rather than an AttributeError on None.
    """
    if isinstance(response, ErrorResponseSchema):
        raise RuntimeError(
            f"API error during equip/unequip: {response.error.code} "
            f"{response.error.message}"
        )
    return response.data.cooldown.remaining_seconds


def _wait_cooldown(response: Any) -> None:
    remaining = _cooldown_seconds(response)
    if remaining > 0:
        time.sleep(remaining)


def _read_loadout(character: Any) -> dict[ItemSlot, str]:
    """The currently-equipped item code per slot (empty slots are "")."""
    loadout: dict[ItemSlot, str] = {}
    for field, slot in EQUIP_SLOTS:
        loadout[slot] = getattr(character, field)
    return loadout


def _quantity_for(character: Any, slot: ItemSlot) -> int:
    """Stack quantity for a slot (1 unless it is a utility slot with a count)."""
    qty_field = UTILITY_QUANTITY_FIELDS.get(slot)
    if qty_field is None:
        return 1
    return getattr(character, qty_field)


def _base_stats_row(character: Any) -> dict[str, Any]:
    """Extract the BASE combat stats from an all-gear-off character."""
    return {
        "max_hp": character.max_hp,
        "attack": {
            "fire": character.attack_fire,
            "earth": character.attack_earth,
            "water": character.attack_water,
            "air": character.attack_air,
        },
        "resistance": {
            "fire": character.res_fire,
            "earth": character.res_earth,
            "water": character.res_water,
            "air": character.res_air,
        },
        "critical_strike": character.critical_strike,
        "initiative": character.initiative,
    }


def capture_base_stats(api: Any, name: str, output_path: Path) -> dict[str, Any]:
    """Capture the character's current-level base stats and merge into the JSON.

    Returns the captured row (for the summary line / tests). Restores the
    original loadout via `finally` even if sampling raises.
    """
    character = api.get_character(name).data
    level = character.level

    # Wait out any existing in-progress cooldown before touching gear — the bot
    # may be mid-action. character.cooldown is the remaining seconds per the
    # character endpoint (distinct from a per-action response cooldown).
    preflight_cd = getattr(character, "cooldown", 0) or 0
    if preflight_cd > 0:
        time.sleep(preflight_cd)

    original_loadout = _read_loadout(character)
    # Stack sizes for utility slots so re-equip restores the exact quantity.
    original_quantities = {
        slot: _quantity_for(character, slot) for slot in original_loadout
    }
    equipped = {slot: code for slot, code in original_loadout.items() if code}

    try:
        for slot in equipped:
            resp = api.action_unequip_item(
                name,
                body=UnequipSchema(slot=slot, quantity=original_quantities[slot]),
            )
            _wait_cooldown(resp)

        bare = api.get_character(name).data
        row = _base_stats_row(bare)
    finally:
        for slot, code in equipped.items():
            resp = api.action_equip_item(
                name,
                body=EquipSchema(
                    code=code, slot=slot, quantity=original_quantities[slot]
                ),
            )
            _wait_cooldown(resp)

    _merge_into_json(output_path, level, row)
    return row


def _merge_into_json(output_path: Path, level: int, row: dict[str, Any]) -> None:
    if output_path.exists():
        document = json.loads(output_path.read_text())
    else:
        document = {"base_stats": {}}

    base_stats = document.setdefault("base_stats", {})
    base_stats[str(level)] = row
    document[f"captured_at_{level}"] = datetime.now(timezone.utc).isoformat()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(document, indent=2, sort_keys=True))


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit(
            "usage: uv run python formal/sim/capture_base_stats.py "
            "<character_name> [output_path]"
        )
    name = sys.argv[1]
    output_path = (
        Path(sys.argv[2])
        if len(sys.argv) > 2
        else Path(__file__).resolve().parent / "character_base_stats.json"
    )

    cfg = Config.from_token_file()
    mgr = ClientManager()
    mgr.initialize(cfg)
    api = mgr.api

    character = api.get_character(name).data
    level = character.level
    free_slots = sum(1 for field, _ in EQUIP_SLOTS if not getattr(character, field))

    row = capture_base_stats(api, name, output_path)

    print(
        f"Captured base stats for {name} at level {level}: "
        f"max_hp={row['max_hp']}, free_slots={free_slots} "
        f"-> {output_path}"
    )


if __name__ == "__main__":
    main()
