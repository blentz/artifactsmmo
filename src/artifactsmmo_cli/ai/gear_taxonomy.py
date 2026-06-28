"""Leaf module: item-type-to-slot mappings derived from CharacterSchema.

This is a LEAF — it imports only `attrs`, `CharacterSchema`, `ItemStats` (from
item_catalog), and `gear_taxonomy_core` so that `game_data.py` can import from
here without the cycle that would arise if it imported from `actions/equip.py`
(which itself imports `GameData` from `game_data`). `actions/equip.py`
re-exports these names from here for the 16+ sites that import from that path.
"""

import attrs
from artifactsmmo_api_client.models.character_schema import CharacterSchema

from artifactsmmo_cli.ai.gear_taxonomy_core import is_combat_bearing
from artifactsmmo_cli.ai.item_catalog import ItemStats

_SLOT_SUFFIX = "_slot"


def _item_type_of_slot(slot_field: str) -> str:
    """The item TYPE that fills a `<type><index?>_slot` CharacterSchema field:
    strip the `_slot` suffix and any trailing index digit (ring1 -> ring,
    artifact2 -> artifact, body_armor -> body_armor)."""
    return slot_field[: -len(_SLOT_SUFFIX)].rstrip("0123456789")


def _derive_type_to_slots() -> dict[str, list[str]]:
    """Map each equippable item type to its CharacterSchema slot field(s),
    DERIVED from the schema's `*_slot` attributes (in schema order). A type with
    several slots (ring/artifact/utility) maps to all of them, left-to-right; the
    planner fills them independently. A slot/type the server adds is picked up on
    client regen rather than silently treated as non-gear (which the recycle/junk
    path would otherwise delete)."""
    out: dict[str, list[str]] = {}
    for field in attrs.fields(CharacterSchema):
        if field.name.endswith(_SLOT_SUFFIX):
            out.setdefault(_item_type_of_slot(field.name), []).append(field.name)
    return out


# All eligible slots per item type, and the primary (first) slot per type —
# derived from CharacterSchema (see _derive_type_to_slots).
ITEM_TYPE_TO_SLOTS: dict[str, list[str]] = _derive_type_to_slots()
ITEM_TYPE_TO_SLOT: dict[str, str] = {t: slots[0] for t, slots in ITEM_TYPE_TO_SLOTS.items()}


def stats_is_combat_bearing(stats: ItemStats) -> bool:
    """Adapt ItemStats fields into the pure core's combat-bearing predicate."""
    return is_combat_bearing(
        attack=stats.attack, resistance=stats.resistance, hp_bonus=stats.hp_bonus,
        dmg=stats.dmg, dmg_elements=stats.dmg_elements,
        critical_strike=stats.critical_strike, initiative=stats.initiative,
        lifesteal=stats.lifesteal)
