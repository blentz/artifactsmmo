"""Tests for WorldState.from_character_schema()."""

from unittest.mock import MagicMock

from artifactsmmo_api_client.types import UNSET

from artifactsmmo_cli.ai.world_state import WorldState


def make_char(x=1, y=2, hp=80, max_hp=100, level=5, xp=50, max_xp=200, gold=30,
              task="chicken", task_type="monsters", task_progress=3, task_total=10,
              inventory_slots=None, cooldown=None):
    char = MagicMock()
    char.name = "hero"
    char.level = level
    char.xp = xp
    char.max_xp = max_xp
    char.hp = hp
    char.max_hp = max_hp
    char.gold = gold
    char.x = x
    char.y = y
    char.inventory_max_items = 20
    char.task = task
    char.task_type = task_type
    char.task_progress = task_progress
    char.task_total = task_total
    char.cooldown_expiration = cooldown if cooldown is not None else UNSET
    char.inventory = inventory_slots if inventory_slots is not None else UNSET
    for slot in ["weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                 "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot",
                 "amulet_slot", "artifact1_slot", "artifact2_slot", "artifact3_slot",
                 "utility1_slot", "utility2_slot", "bag_slot", "rune_slot"]:
        setattr(char, slot, "")
    for skill_attr in ["mining_level", "woodcutting_level", "fishing_level", "weaponcrafting_level",
                       "gearcrafting_level", "jewelrycrafting_level", "cooking_level", "alchemy_level"]:
        setattr(char, skill_attr, 1)
    return char


class TestFromCharacterSchema:
    def test_basic_fields(self):
        char = make_char(x=3, y=7, hp=80, max_hp=100, level=5, gold=30, xp=50, max_xp=200)
        state = WorldState.from_character_schema(char)
        assert state.character == "hero"
        assert state.x == 3
        assert state.y == 7
        assert state.hp == 80
        assert state.max_hp == 100
        assert state.level == 5
        assert state.gold == 30

    def test_task_fields(self):
        char = make_char(task="chicken", task_type="monsters", task_progress=3, task_total=10)
        state = WorldState.from_character_schema(char)
        assert state.task_code == "chicken"
        assert state.task_type == "monsters"
        assert state.task_progress == 3
        assert state.task_total == 10

    def test_empty_task(self):
        char = make_char(task="", task_type="")
        state = WorldState.from_character_schema(char)
        assert state.task_code is None
        assert state.task_type is None

    def test_inventory_slots_converted_to_dict(self):
        slot1 = MagicMock()
        slot1.code = "copper_ore"
        slot1.quantity = 5
        slot2 = MagicMock()
        slot2.code = "iron_ore"
        slot2.quantity = 2
        char = make_char(inventory_slots=[slot1, slot2])
        state = WorldState.from_character_schema(char)
        assert state.inventory["copper_ore"] == 5
        assert state.inventory["iron_ore"] == 2

    def test_unset_inventory_is_empty(self):
        char = make_char(inventory_slots=None)
        state = WorldState.from_character_schema(char)
        assert state.inventory == {}

    def test_bank_args_propagated(self):
        char = make_char()
        state = WorldState.from_character_schema(char, bank_items={"gold_ore": 3}, bank_gold=500)
        assert state.bank_items == {"gold_ore": 3}
        assert state.bank_gold == 500

    def test_cooldown_unset(self):
        char = make_char(cooldown=UNSET)
        state = WorldState.from_character_schema(char)
        assert state.cooldown_expires is None

    def test_cooldown_set(self):
        from datetime import datetime, timezone
        dt = datetime(2026, 5, 12, 12, 0, 0, tzinfo=timezone.utc)
        char = make_char(cooldown=dt)
        state = WorldState.from_character_schema(char)
        assert state.cooldown_expires == dt
