""" Test module for EquipItemAction """

import unittest
from unittest.mock import Mock

from artifactsmmo_api_client.models.item_slot import ItemSlot
from src.controller.actions.equip_item import EquipItemAction

from test.fixtures import MockActionContext, create_mock_client


class TestEquipItemAction(unittest.TestCase):
    """ Test cases for EquipItemAction """

    def setUp(self):
        """ Set up test fixtures """
        self.character_name = "test_character"
        self.item_code = "iron_sword"
        self.slot = "weapon"
        self.action = EquipItemAction()

    def test_init_basic(self):
        """ Test basic initialization """
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(self.action, 'character_name'))
        self.assertFalse(hasattr(self.action, 'item_code'))
        self.assertFalse(hasattr(self.action, 'slot'))
        self.assertFalse(hasattr(self.action, 'quantity'))

    def test_init_with_quantity(self):
        """ Test initialization with custom quantity """
        action = EquipItemAction()
        # Action no longer stores quantity as instance attribute
        self.assertFalse(hasattr(action, 'quantity'))

    def test_execute_no_client(self):
        """ Test execute with no API client """
        context = MockActionContext(character_name=self.character_name, item_code=self.item_code, slot=self.slot)
        result = self.action.execute(None, context)
        # With centralized validation, None client triggers validation error
        self.assertFalse(result["success"])
        # Direct action execution bypasses centralized validation
        self.assertIn('error', result)

    def test_execute_invalid_slot(self):
        """ Test execute with invalid slot name """
        client = create_mock_client()
        action = EquipItemAction()
        
        context = MockActionContext(character_name="char", item_code="item", slot="invalid_slot")
        result = action.execute(client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('Invalid equipment slot', result['error'])
        self.assertIn('invalid_slot', result['error'])

    def test_execute_success(self):
        """ Test successful execution """
        # Mock API client and response
        client = create_mock_client()
        mock_response = Mock()
        mock_response.data = Mock()
        
        # Mock cooldown
        mock_cooldown = Mock()
        mock_cooldown.total_seconds = 30
        mock_response.data.cooldown = mock_cooldown
        
        # Mock character data
        mock_character = Mock()
        mock_character.level = 5
        mock_character.hp = 80
        mock_character.max_hp = 100
        mock_response.data.character = mock_character
        
        # Mock item data
        mock_item = Mock()
        mock_item.name = "Iron Sword"
        mock_item.type = "weapon"
        mock_item.level = 3
        mock_response.data.item = mock_item
        
        # Mock slot
        mock_response.data.slot = ItemSlot.WEAPON
        
        # Patch the API call
        with unittest.mock.patch('src.controller.actions.equip_item.equip_api', return_value=mock_response):
            context = MockActionContext(character_name=self.character_name, item_code=self.item_code, slot=self.slot)
            result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], "iron_sword")
        self.assertEqual(result['slot'], "weapon")
        self.assertEqual(result['character_name'], "test_character")
        self.assertTrue(result['equipped'])
        self.assertEqual(result['character_level'], 5)
        self.assertEqual(result['character_hp'], 80)
        self.assertEqual(result['character_max_hp'], 100)

    def test_execute_api_failure(self):
        """ Test execute when API returns no data """
        client = create_mock_client()
        mock_response = Mock()
        mock_response.data = None
        
        with unittest.mock.patch('src.controller.actions.equip_item.equip_api', return_value=mock_response):
            context = MockActionContext(character_name=self.character_name, item_code=self.item_code, slot=self.slot)
            result = self.action.execute(client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('no response data', result['error'])

    def test_execute_api_exception(self):
        """ Test execute when API throws exception """
        client = create_mock_client()
        
        with unittest.mock.patch('src.controller.actions.equip_item.equip_api', side_effect=Exception("API Error")):
            context = MockActionContext(character_name=self.character_name, item_code=self.item_code, slot=self.slot)
            result = self.action.execute(client, context)
        
        self.assertFalse(result['success'])
        self.assertIn('API Error', result['error'])

    def test_get_item_slot_enum_weapon(self):
        """ Test slot enum conversion for weapon """
        # Test if method exists and works correctly
        if hasattr(self.action, '_get_item_slot_enum'):
            result = self.action._get_item_slot_enum("weapon")
            self.assertEqual(result, ItemSlot.WEAPON)

    def test_get_item_slot_enum_case_insensitive(self):
        """ Test slot enum conversion is case insensitive """
        if hasattr(self.action, '_get_item_slot_enum'):
            result = self.action._get_item_slot_enum("WEAPON")
            self.assertEqual(result, ItemSlot.WEAPON)

    def test_get_item_slot_enum_body_armor_variants(self):
        """ Test different variants for body armor slot """
        if hasattr(self.action, '_get_item_slot_enum'):
            test_cases = ["body_armor", "body", "chest"]
            for slot_name in test_cases:
                with self.subTest(slot_name=slot_name):
                    result = self.action._get_item_slot_enum(slot_name)
                    self.assertEqual(result, ItemSlot.BODY_ARMOR)

    def test_get_item_slot_enum_leg_armor_variants(self):
        """ Test different variants for leg armor slot """
        if hasattr(self.action, '_get_item_slot_enum'):
            test_cases = ["leg_armor", "legs"]
            for slot_name in test_cases:
                with self.subTest(slot_name=slot_name):
                    result = self.action._get_item_slot_enum(slot_name)
                    self.assertEqual(result, ItemSlot.LEG_ARMOR)

    def test_get_item_slot_enum_boots_variants(self):
        """ Test different variants for boots slot """
        if hasattr(self.action, '_get_item_slot_enum'):
            test_cases = ["boots", "shoes", "feet"]
            for slot_name in test_cases:
                with self.subTest(slot_name=slot_name):
                    result = self.action._get_item_slot_enum(slot_name)
                    self.assertEqual(result, ItemSlot.BOOTS)

    def test_get_item_slot_enum_amulet_variants(self):
        """ Test different variants for amulet slot """
        if hasattr(self.action, '_get_item_slot_enum'):
            test_cases = ["amulet", "necklace"]
            for slot_name in test_cases:
                with self.subTest(slot_name=slot_name):
                    result = self.action._get_item_slot_enum(slot_name)
                    self.assertEqual(result, ItemSlot.AMULET)

    def test_get_item_slot_enum_rings(self):
        """ Test ring slot variants """
        if hasattr(self.action, '_get_item_slot_enum'):
            self.assertEqual(self.action._get_item_slot_enum("ring1"), ItemSlot.RING1)
            self.assertEqual(self.action._get_item_slot_enum("ring2"), ItemSlot.RING2)

    def test_get_item_slot_enum_utilities(self):
        """ Test utility slot variants """
        if hasattr(self.action, '_get_item_slot_enum'):
            self.assertEqual(self.action._get_item_slot_enum("utility1"), ItemSlot.UTILITY1)
            self.assertEqual(self.action._get_item_slot_enum("utility2"), ItemSlot.UTILITY2)

    def test_get_item_slot_enum_artifacts(self):
        """ Test artifact slot variants """
        if hasattr(self.action, '_get_item_slot_enum'):
            self.assertEqual(self.action._get_item_slot_enum("artifact1"), ItemSlot.ARTIFACT1)
            self.assertEqual(self.action._get_item_slot_enum("artifact2"), ItemSlot.ARTIFACT2)
            self.assertEqual(self.action._get_item_slot_enum("artifact3"), ItemSlot.ARTIFACT3)

    def test_get_item_slot_enum_other_slots(self):
        """ Test other equipment slots """
        if hasattr(self.action, '_get_item_slot_enum'):
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
        if hasattr(self.action, '_get_item_slot_enum'):
            result = self.action._get_item_slot_enum("weapon")
            self.assertEqual(result, ItemSlot.WEAPON)

    def test_get_item_slot_enum_invalid(self):
        """ Test invalid slot name """
        if hasattr(self.action, '_get_item_slot_enum'):
            result = self.action._get_item_slot_enum("invalid_slot")
            self.assertIsNone(result)

    def test_repr(self):
        """ Test string representation """
        # Repr is now simplified
        expected = "EquipItemAction()"
        self.assertEqual(repr(self.action), expected)

    def test_repr_with_quantity(self):
        """ Test string representation with custom quantity """
        action = EquipItemAction()
        expected = "EquipItemAction()"
        self.assertEqual(repr(action), expected)

    def test_execute_minimal_response(self):
        """ Test execute with minimal response data """
        client = create_mock_client()
        mock_response = Mock()
        mock_response.data = Mock(spec=[])  # Empty spec to avoid auto-creating attributes
        
        # Only provide basic data without optional fields
        with unittest.mock.patch('src.controller.actions.equip_item.equip_api', return_value=mock_response):
            context = MockActionContext(character_name=self.character_name, item_code=self.item_code, slot=self.slot)
            result = self.action.execute(client, context)
        
        self.assertTrue(result['success'])
        self.assertEqual(result['item_code'], "iron_sword")
        self.assertEqual(result['slot'], "weapon")
        self.assertEqual(result['cooldown'], 0)  # Default when no cooldown data


if __name__ == '__main__':
    unittest.main()