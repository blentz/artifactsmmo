"""Slot-aware inventory dimension for WorldState (Tasks 0+1).

The planner tracks inventory purely by quantity (`inventory_max`), but the
server enforces a SEPARATE slot cap (distinct-stack count) — HTTP 497 fires
when slots are full even though `inventory_free` (quantity headroom) is
positive. This module proves the slot dimension is captured from the API
response (`inventory_slots_max` = total slot count, filled + empty) and
exposes `inventory_slots_used` / `inventory_slots_free` as derived properties
distinct from the existing quantity-based `inventory_used` / `inventory_free`.
"""

import json
from pathlib import Path

from artifactsmmo_api_client.models.character_schema import CharacterSchema
from artifactsmmo_cli.ai.world_state import WorldState

FIXTURE = Path("tests/test_ai/fixtures/character_with_empty_slots.json")


def test_from_character_schema_captures_slot_capacity() -> None:
    """slots_max = total slot count (filled + empty); slots_used = filled
    stacks; slots_free = empty slots. Proves the model reads the slot cap the
    server enforces, not the quantity cap."""
    char = CharacterSchema.from_dict(json.loads(FIXTURE.read_text()))
    total = len(char.inventory)
    filled = sum(1 for s in char.inventory if s.code and s.quantity > 0)
    state = WorldState.from_character_schema(char)
    assert state.inventory_slots_max == total
    assert state.inventory_slots_used == filled
    assert state.inventory_slots_free == total - filled


def _bare_state(inventory: dict[str, int], slots_max: int) -> WorldState:
    return WorldState(
        character="t", level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
        skills={}, x=0, y=0, inventory=inventory, inventory_max=124,
        inventory_slots_max=slots_max, equipment={}, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        bank_items=None, bank_gold=None, pending_items=None,
    )


def test_slots_used_is_distinct_stack_count() -> None:
    """slots_used counts DISTINCT stacks (dict keys), not total quantity."""
    s = _bare_state({"copper_ore": 50, "feather": 3}, slots_max=20)
    assert s.inventory_slots_used == 2       # two stacks
    assert s.inventory_used == 53            # quantity unchanged
    assert s.inventory_slots_free == 18


def test_slots_free_zero_when_all_stacks_occupy_capacity() -> None:
    """20 distinct stacks at slots_max 20 -> 0 free, regardless of quantity."""
    inv = {f"item_{i}": 1 for i in range(20)}
    s = _bare_state(inv, slots_max=20)
    assert s.inventory_slots_used == 20
    assert s.inventory_slots_free == 0
    assert s.inventory_free > 0              # quantity has headroom (124-20)
