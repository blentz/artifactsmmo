""" Test module for UnequipItemAction """

import unittest
from unittest.mock import Mock, MagicMock
from src.controller.actions.unequip_item import UnequipItemAction
from artifactsmmo_api_client.models.item_slot import ItemSlot


class TestUnequipItemAction(unittest.TestCase):
    """ Test cases for UnequipItemAction """

    def setUp(self):
        """ Set up test fixtures """
        self.character_name = "test_character"
        self.slot = "weapon"
        self.action = UnequipItemAction(self.character_name, self.slot)

    def test_init_basic(self):
        """ Test basic initialization """
        self.assertEqual(self.action.character_name, "test_character")
        self.assertEqual(self.action.slot, "weapon")
        self.assertEqual(self.action.quantity, 1)

    def test_init_with_quantity(self):
        """ Test initialization with custom quantity """
        action = UnequipItemAction("char", "utility1", quantity=3)
        self.assertEqual(action.quantity, 3)

    def test_execute_no_client(self):
        """ Test execute with no API client """
        result = self.action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_execute_invalid_slot(self):
        """ Test execute with invalid slot name """
        client = Mock()
        action = UnequipItemAction("char", "invalid_slot")
        
        result = action.execute(client)
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid equipment slot', result['error'])
        self.assertIn('invalid_slot', result['error'])

    def test_execute_success(self):
        """ Test successful execution """
        # Mock API client and response
        client = Mock()
        mock_response = Mock()
        mock_response.data = Mock()
        
        # Mock cooldown
        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 20
        mock_response.data.cooldown = mock_cooldown
        
        # Mock character data
        mock_character = Mock()
        mock_character.level = 5
        mock_character.hp = 85
        mock_character.max_hp = 100
        mock_response.data.character = mock_character
        
        # Mock item data (the item that was unequipped)
        mock_item = Mock()
        mock_item.code = "iron_sword"
        mock_item.name = "Iron Sword"
        mock_item.type = "weapon"
        mock_item.level = 3
        mock_response.data.item = mock_item
        
        # Mock slot
        mock_response.data.slot = ItemSlot.WEAPON
        
        # Patch the API call
        with unittest.mock.patch('src.controller.actions.unequip_item.unequip_api', return_value=mock_response):
            result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['slot'], "weapon")
        self.assertEqual(result['quantity'], 1)
        self.assertEqual(result['cooldown'], 20)
        self.assertEqual(result['character_level'], 5)
        self.assertEqual(result['character_hp'], 85)
        self.assertEqual(result['character_max_hp'], 100)
        self.assertEqual(result['unequipped_item_code'], "iron_sword")
        self.assertEqual(result['unequipped_item_name'], "Iron Sword")
        self.assertEqual(result['unequipped_item_type'], "weapon")
        self.assertEqual(result['unequipped_item_level'], 3)
        self.assertEqual(result['unequipped_slot'], "weapon")

    def test_execute_api_failure(self):
        """ Test execute when API returns no data """
        client = Mock()
        mock_response = Mock()
        mock_response.data = None
        
        with unittest.mock.patch('src.controller.actions.unequip_item.unequip_api', return_value=mock_response):
            result = self.action.execute(client)
        
        self.assertFalse(result['success'])
        self.assertIn('no response data', result['error'])

    def test_execute_api_exception(self):
        """ Test execute when API throws exception """
        client = Mock()
        
        with unittest.mock.patch('src.controller.actions.unequip_item.unequip_api', side_effect=Exception("API Error")):
            result = self.action.execute(client)
        
        self.assertFalse(result['success'])
        self.assertIn('API Error', result['error'])

    def test_get_item_slot_enum_weapon(self):
        """ Test slot enum conversion for weapon """
        result = self.action._get_item_slot_enum("weapon")
        self.assertEqual(result, ItemSlot.WEAPON)

    def test_get_item_slot_enum_case_insensitive(self):
        """ Test slot enum conversion is case insensitive """
        result = self.action._get_item_slot_enum("HELMET")
        self.assertEqual(result, ItemSlot.HELMET)

    def test_get_item_slot_enum_body_armor_variants(self):
        """ Test different variants for body armor slot """
        test_cases = ["body_armor", "body", "chest"]
        for slot_name in test_cases:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, ItemSlot.BODY_ARMOR)

    def test_get_item_slot_enum_leg_armor_variants(self):
        """ Test different variants for leg armor slot """
        test_cases = ["leg_armor", "legs"]
        for slot_name in test_cases:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, ItemSlot.LEG_ARMOR)

    def test_get_item_slot_enum_boots_variants(self):
        """ Test different variants for boots slot """
        test_cases = ["boots", "shoes", "feet"]
        for slot_name in test_cases:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, ItemSlot.BOOTS)

    def test_get_item_slot_enum_amulet_variants(self):
        """ Test different variants for amulet slot """
        test_cases = ["amulet", "necklace"]
        for slot_name in test_cases:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, ItemSlot.AMULET)

    def test_get_item_slot_enum_rings(self):
        """ Test ring slot variants """
        self.assertEqual(self.action._get_item_slot_enum("ring1"), ItemSlot.RING1)
        self.assertEqual(self.action._get_item_slot_enum("ring2"), ItemSlot.RING2)

    def test_get_item_slot_enum_utilities(self):
        """ Test utility slot variants """
        self.assertEqual(self.action._get_item_slot_enum("utility1"), ItemSlot.UTILITY1)
        self.assertEqual(self.action._get_item_slot_enum("utility2"), ItemSlot.UTILITY2)

    def test_get_item_slot_enum_artifacts(self):
        """ Test artifact slot variants """
        self.assertEqual(self.action._get_item_slot_enum("artifact1"), ItemSlot.ARTIFACT1)
        self.assertEqual(self.action._get_item_slot_enum("artifact2"), ItemSlot.ARTIFACT2)
        self.assertEqual(self.action._get_item_slot_enum("artifact3"), ItemSlot.ARTIFACT3)

    def test_get_item_slot_enum_other_slots(self):
        """ Test other equipment slots """
        test_cases = [
            ("helmet", ItemSlot.HELMET),
            ("shield", ItemSlot.SHIELD),
            ("bag", ItemSlot.BAG),
            ("rune", ItemSlot.RUNE)
        ]
        for slot_name, expected_enum in test_cases:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, expected_enum)

    def test_get_item_slot_enum_direct_enum_value(self):
        """ Test using direct enum value """
        result = self.action._get_item_slot_enum("shield")
        self.assertEqual(result, ItemSlot.SHIELD)

    def test_get_item_slot_enum_invalid(self):
        """ Test invalid slot name """
        result = self.action._get_item_slot_enum("invalid_slot")
        self.assertIsNone(result)

    def test_repr(self):
        """ Test string representation """
        expected = "UnequipItemAction(test_character, weapon, qty=1)"
        self.assertEqual(repr(self.action), expected)

    def test_repr_with_quantity(self):
        """ Test string representation with custom quantity """
        action = UnequipItemAction("char", "utility2", quantity=2)
        expected = "UnequipItemAction(char, utility2, qty=2)"
        self.assertEqual(repr(action), expected)

    def test_execute_minimal_response(self):
        """ Test execute with minimal response data """
        client = Mock()
        mock_response = Mock()
        mock_response.data = Mock(spec=[])  # Empty spec to avoid auto-creating attributes
        
        # Only provide basic data without optional fields
        with unittest.mock.patch('src.controller.actions.unequip_item.unequip_api', return_value=mock_response):
            result = self.action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['slot'], "weapon")
        self.assertEqual(result['cooldown'], 0)  # Default when no cooldown data

    def test_execute_utility_slot_with_quantity(self):
        """ Test execute for utility slot with custom quantity """
        client = Mock()
        action = UnequipItemAction("char", "utility1", quantity=3)
        
        mock_response = Mock()
        mock_response.data = Mock()
        
        # Mock utility item data
        mock_item = Mock()
        mock_item.code = "health_potion"
        mock_item.name = "Health Potion"
        mock_item.type = "utility"
        mock_item.level = 1
        mock_response.data.item = mock_item
        
        mock_response.data.slot = ItemSlot.UTILITY1
        
        with unittest.mock.patch('src.controller.actions.unequip_item.unequip_api', return_value=mock_response):
            result = action.execute(client)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['quantity'], 3)
        self.assertEqual(result['unequipped_item_code'], "health_potion")
        self.assertEqual(result['unequipped_item_type'], "utility")

    def test_all_equipment_slots_mapping(self):
        """ Test that all equipment slots can be mapped correctly """
        # Test all ItemSlot enum values can be mapped
        all_slots = [
            ("weapon", ItemSlot.WEAPON),
            ("helmet", ItemSlot.HELMET),
            ("body_armor", ItemSlot.BODY_ARMOR),
            ("leg_armor", ItemSlot.LEG_ARMOR),
            ("boots", ItemSlot.BOOTS),
            ("shield", ItemSlot.SHIELD),
            ("ring1", ItemSlot.RING1),
            ("ring2", ItemSlot.RING2),
            ("amulet", ItemSlot.AMULET),
            ("artifact1", ItemSlot.ARTIFACT1),
            ("artifact2", ItemSlot.ARTIFACT2),
            ("artifact3", ItemSlot.ARTIFACT3),
            ("utility1", ItemSlot.UTILITY1),
            ("utility2", ItemSlot.UTILITY2),
            ("bag", ItemSlot.BAG),
            ("rune", ItemSlot.RUNE)
        ]
        
        for slot_name, expected_enum in all_slots:
            with self.subTest(slot_name=slot_name):
                result = self.action._get_item_slot_enum(slot_name)
                self.assertEqual(result, expected_enum)


if __name__ == '__main__':
    unittest.main()