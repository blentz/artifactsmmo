"""Simple tests to improve action test coverage without complex mocking."""

import os
import tempfile
import unittest

from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from src.controller.actions.analyze_resources import AnalyzeResourcesAction
from src.controller.actions.check_inventory import CheckInventoryAction
from src.controller.actions.check_location import CheckLocationAction
from src.controller.actions.check_skill_requirement import CheckSkillRequirementAction
from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.controller.actions.find_correct_workshop import FindCorrectWorkshopAction
from src.controller.actions.find_xp_sources import FindXpSourcesAction
from src.controller.actions.move_to_resource import MoveToResourceAction
from src.controller.actions.move_to_workshop import MoveToWorkshopAction
from src.controller.actions.transform_raw_materials import TransformRawMaterialsAction

from test.fixtures import MockActionContext


class TestSimpleActionCoverage(unittest.TestCase):
    """Simple test cases to improve action coverage."""

    def setUp(self):
        """Set up test fixtures."""
        self.temp_dir = tempfile.mkdtemp()
        self.original_data_prefix = os.environ.get('DATA_PREFIX', '')
        os.environ['DATA_PREFIX'] = self.temp_dir

    def tearDown(self):
        """Clean up test fixtures."""
        os.environ['DATA_PREFIX'] = self.original_data_prefix
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_find_xp_sources_basic(self):
        """Test FindXpSourcesAction basic functionality."""
        action = FindXpSourcesAction()
        # Action no longer stores skill as instance attribute
        self.assertFalse(hasattr(action, 'skill'))
        
        # Test repr
        self.assertEqual("FindXpSourcesAction()", repr(action))
        
        # Test no client
        context = MockActionContext(skill="weaponcrafting")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_check_skill_requirement_basic(self):
        """Test CheckSkillRequirementAction basic functionality."""
        action = CheckSkillRequirementAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))
        
        # Test repr
        self.assertEqual("CheckSkillRequirementAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player", target_item="sword")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_evaluate_weapon_recipes_basic(self):
        """Test EvaluateWeaponRecipesAction basic functionality."""
        action = EvaluateWeaponRecipesAction()
        # Action no longer stores character_name as instance attribute
        self.assertFalse(hasattr(action, 'character_name'))
        
        # Test repr
        self.assertEqual("EvaluateWeaponRecipesAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_find_correct_workshop_basic(self):
        """Test FindCorrectWorkshopAction basic functionality."""
        action = FindCorrectWorkshopAction()
        # Action no longer stores item_code as instance attribute
        self.assertFalse(hasattr(action, 'item_code'))
        
        # Test repr
        self.assertEqual("FindCorrectWorkshopAction()", repr(action))
        
        # Test no client
        context = MockActionContext(item_code="sword")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_analyze_crafting_chain_basic(self):
        """Test AnalyzeCraftingChainAction basic functionality."""
        action = AnalyzeCraftingChainAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))
        
        # Test repr
        self.assertEqual("AnalyzeCraftingChainAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player", target_item="sword")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_transform_raw_materials_basic(self):
        """Test TransformRawMaterialsAction basic functionality."""
        action = TransformRawMaterialsAction()
        # Action no longer stores character_name as instance attribute
        self.assertFalse(hasattr(action, 'character_name'))
        
        # Test repr
        self.assertEqual("TransformRawMaterialsAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_analyze_resources_basic(self):
        """Test AnalyzeResourcesAction basic functionality."""
        action = AnalyzeResourcesAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        
        # Test repr
        self.assertEqual("AnalyzeResourcesAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_x=5, character_y=10)
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_check_inventory_basic(self):
        """Test CheckInventoryAction basic functionality."""
        action = CheckInventoryAction()
        # Action no longer stores character_name as instance attribute
        self.assertFalse(hasattr(action, 'character_name'))
        
        # Test repr
        self.assertEqual("CheckInventoryAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_check_location_basic(self):
        """Test CheckLocationAction basic functionality."""
        action = CheckLocationAction()
        # Action no longer stores character_name as instance attribute
        self.assertFalse(hasattr(action, 'character_name'))
        
        # Test repr
        self.assertEqual("CheckLocationAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player")
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_move_to_resource_basic(self):
        """Test MoveToResourceAction basic functionality."""
        action = MoveToResourceAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_x'))
        self.assertFalse(hasattr(action, 'target_y'))
        
        # Test repr
        self.assertEqual("MoveToResourceAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player", target_x=5, target_y=10)
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_move_to_workshop_basic(self):
        """Test MoveToWorkshopAction basic functionality."""
        action = MoveToWorkshopAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_x'))
        self.assertFalse(hasattr(action, 'target_y'))
        
        # Test repr
        self.assertEqual("MoveToWorkshopAction()", repr(action))
        
        # Test no client
        context = MockActionContext(character_name="player", target_x=5, target_y=10)
        result = action.execute(None, context)
        self.assertFalse(result['success'])

    def test_goap_attributes(self):
        """Test that actions have GOAP attributes."""
        actions = [
            FindXpSourcesAction(),
            CheckSkillRequirementAction(),
            EvaluateWeaponRecipesAction(),
            FindCorrectWorkshopAction(),
            AnalyzeCraftingChainAction(),
            TransformRawMaterialsAction(),
            AnalyzeResourcesAction(),
            CheckInventoryAction(),
            CheckLocationAction(),
            MoveToResourceAction(),
            MoveToWorkshopAction()
        ]
        
        for action in actions:
            with self.subTest(action=action.__class__.__name__):
                # Test that they have GOAP attributes
                self.assertTrue(hasattr(action.__class__, 'conditions'))
                self.assertTrue(hasattr(action.__class__, 'reactions'))
                self.assertTrue(hasattr(action.__class__, 'weights'))
                self.assertTrue(hasattr(action.__class__, 'g'))


if __name__ == '__main__':
    unittest.main()