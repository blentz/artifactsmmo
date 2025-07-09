"""Comprehensive tests to maximize action test coverage with minimal mocking complexity."""

import os
import tempfile
import unittest

from src.controller.action_executor import ActionExecutor
from src.controller.actions.base import ActionResult
from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from src.controller.actions.analyze_resources import AnalyzeResourcesAction
from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.controller.actions.find_xp_sources import FindXpSourcesAction
from src.controller.actions.transform_materials_coordinator import TransformMaterialsCoordinatorAction

from test.fixtures import MockActionContext


class TestComprehensiveActionCoverage(unittest.TestCase):
    """Comprehensive test cases to maximize action coverage."""

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

    def test_transform_raw_materials_basic(self):
        """Test TransformMaterialsCoordinatorAction basic functionality."""
        action = TransformMaterialsCoordinatorAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))
        
        # Test repr
        expected = "TransformMaterialsCoordinatorAction()"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(TransformMaterialsCoordinatorAction, 'conditions'))
        self.assertTrue(hasattr(TransformMaterialsCoordinatorAction, 'reactions'))
        self.assertTrue(hasattr(TransformMaterialsCoordinatorAction, 'weight'))
        
        # Test no client
        context = MockActionContext(character_name="player", target_item="sword")
        result = action.execute(None, context)
        self.assertFalse(result.success)
        self.assertFalse(result.success)

    def test_analyze_crafting_chain_basic(self):
        """Test AnalyzeCraftingChainAction basic functionality."""
        action = AnalyzeCraftingChainAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))
        
        # Test repr
        expected = "AnalyzeCraftingChainAction()"
        self.assertEqual(repr(action), expected)
        
        # Test initialization data structures if they exist
        if hasattr(action, 'analyzed_items'):
            self.assertEqual(action.analyzed_items, set())
        if hasattr(action, 'resource_nodes'):
            self.assertEqual(action.resource_nodes, {})
        if hasattr(action, 'workshops'):
            self.assertEqual(action.workshops, {})
        if hasattr(action, 'crafting_dependencies'):
            self.assertEqual(action.crafting_dependencies, {})
        if hasattr(action, 'transformation_chains'):
            self.assertEqual(action.transformation_chains, [])
        
        # Test GOAP attributes
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'weight'))
        
        # Test no client
        context = MockActionContext(character_name="player", target_item="sword")
        result = action.execute(None, context)
        self.assertFalse(result.success)
        self.assertFalse(result.success)

    def test_analyze_resources_basic(self):
        """Test AnalyzeResourcesAction basic functionality."""
        action = AnalyzeResourcesAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        self.assertFalse(hasattr(action, 'character_level'))
        
        # Test repr
        expected = "AnalyzeResourcesAction()"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weight'))
        
        # Test no client
        context = MockActionContext(character_x=10, character_y=15, character_level=5)
        result = action.execute(None, context)
        self.assertFalse(result.success)
        self.assertFalse(result.success)

    def test_evaluate_weapon_recipes_basic(self):
        """Test EvaluateWeaponRecipesAction basic functionality."""
        action = EvaluateWeaponRecipesAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'current_weapon'))
        
        # Test GOAP attributes
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'conditions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'reactions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'weight'))
        
        # Test no client
        context = MockActionContext(character_name="player", current_weapon="iron_sword")
        result = action.execute(None, context)
        self.assertFalse(result.success)
        self.assertFalse(result.success)

    def test_find_xp_sources_basic(self):
        """Test FindXpSourcesAction basic functionality."""
        action = FindXpSourcesAction()
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'skill'))
        self.assertFalse(hasattr(action, 'kwargs'))
        
        # Test repr
        expected = "FindXpSourcesAction()"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(FindXpSourcesAction, 'conditions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'reactions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'weight'))
        
        # Test no client
        context = MockActionContext(skill="weaponcrafting", character_level=5)
        result = action.execute(None, context)
        self.assertFalse(result.success)
        self.assertFalse(result.success)

    def test_action_executor_dataclasses(self):
        """Test ActionExecutor dataclasses."""
        # Test ActionResult
        result = ActionResult(
            success=True,
            message='Test action completed',
            data={'status': 'ok'},
            action_name='test_action'
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.data['status'], 'ok')
        self.assertEqual(result.action_name, 'test_action')
        self.assertIsNone(result.error)

    def test_action_executor_basic_functionality(self):
        """Test ActionExecutor basic functionality."""
        executor = ActionExecutor()
        self.assertIsNotNone(executor.factory)
        self.assertIsNotNone(executor.logger)
        
        # Test that config_data is loaded
        self.assertIsNotNone(executor.config_data)
        self.assertIsInstance(executor.config_data.data, dict)

    def test_analyze_resources_helper_methods(self):
        """Test AnalyzeResourcesAction helper methods."""
        action = AnalyzeResourcesAction()
        
        # Test resource accessibility calculation if method exists
        if hasattr(action, '_calculate_resource_accessibility'):
            accessibility = action._calculate_resource_accessibility({'level': 5}, 10)
            self.assertEqual(accessibility, 'high')
            
            accessibility = action._calculate_resource_accessibility({'level': 15}, 10)
            self.assertEqual(accessibility, 'low')
        
        # Action no longer has these as instance attributes
        self.assertFalse(hasattr(action, 'character_x'))
        self.assertFalse(hasattr(action, 'character_y'))
        self.assertFalse(hasattr(action, 'character_level'))
        self.assertFalse(hasattr(action, 'analysis_radius'))
        
        # Test methods if they exist
        if hasattr(action, '_calculate_resource_accessibility'):
            accessibility = action._calculate_resource_accessibility({}, 10)
            self.assertEqual(accessibility, 'unknown')
        
        # Test resource drops analysis if method exists
        if hasattr(action, '_analyze_resource_drops'):
            drops = action._analyze_resource_drops({
                'drop': [{'code': 'iron_ore', 'quantity': 1}]
            })
            self.assertEqual(len(drops), 1)
            self.assertEqual(drops[0]['code'], 'iron_ore')
            
            drops = action._analyze_resource_drops({})
            self.assertEqual(drops, [])

    def test_analyze_crafting_chain_helper_methods(self):
        """Test AnalyzeCraftingChainAction helper methods."""
        action = AnalyzeCraftingChainAction()
        
        # Action no longer stores these as instance attributes
        self.assertFalse(hasattr(action, 'character_name'))
        self.assertFalse(hasattr(action, 'target_item'))
        
        # Test attributes if they exist
        if hasattr(action, 'analyzed_items'):
            self.assertIsInstance(action.analyzed_items, set)
            self.assertEqual(len(action.analyzed_items), 0)
        if hasattr(action, 'resource_nodes'):
            self.assertIsInstance(action.resource_nodes, dict)
            self.assertEqual(len(action.resource_nodes), 0)
        if hasattr(action, 'workshops'):
            self.assertIsInstance(action.workshops, dict)
        if hasattr(action, 'crafting_dependencies'):
            self.assertIsInstance(action.crafting_dependencies, dict)
        if hasattr(action, 'transformation_chains'):
            self.assertIsInstance(action.transformation_chains, list)

    def test_transform_raw_materials_helper_methods(self):
        """Test TransformMaterialsCoordinatorAction helper methods if they exist."""
        action = TransformMaterialsCoordinatorAction()
        
        # Test potential helper methods (will pass if they don't exist)
        if hasattr(action, '_is_raw_material'):
            # Set up context for the method
            action._context = MockActionContext(action_config={})
            result = action._is_raw_material('copper_ore')
            self.assertIsInstance(result, bool)
        
        if hasattr(action, '_get_transformation_recipe'):
            # Set up context if needed
            if not hasattr(action, '_context'):
                action._context = MockActionContext()
            recipe = action._get_transformation_recipe('copper_ore')
            self.assertIsInstance(recipe, (dict, type(None)))

    def test_error_handling_patterns(self):
        """Test common error handling patterns across actions."""
        actions = [
            TransformMaterialsCoordinatorAction(),
            AnalyzeCraftingChainAction(),
            AnalyzeResourcesAction(),
            EvaluateWeaponRecipesAction(),
            FindXpSourcesAction()
        ]
        
        for action in actions:
            with self.subTest(action=action.__class__.__name__):
                # Test no client error
                context = MockActionContext(character_name="player", skill="skill")
                result = action.execute(None, context)
                self.assertFalse(result.success)
                self.assertFalse(result.success)
                
                # Test result structure
                self.assertTrue(hasattr(result, 'success'))
                self.assertTrue(hasattr(result, 'error'))

    def test_goap_attribute_consistency(self):
        """Test GOAP attribute consistency across actions."""
        action_classes = [
            TransformMaterialsCoordinatorAction,
            AnalyzeCraftingChainAction,
            AnalyzeResourcesAction,
            EvaluateWeaponRecipesAction,
            FindXpSourcesAction
        ]
        
        for action_class in action_classes:
            with self.subTest(action_class=action_class.__name__):
                # Test required GOAP attributes exist
                self.assertTrue(hasattr(action_class, 'conditions'))
                self.assertTrue(hasattr(action_class, 'reactions'))
                self.assertTrue(hasattr(action_class, 'weight'))
                
                # Test attributes are proper types
                self.assertIsInstance(action_class.conditions, dict)
                self.assertIsInstance(action_class.reactions, dict)
                self.assertIsInstance(action_class.weight, (int, float))

    def test_action_initialization_patterns(self):
        """Test action initialization patterns."""
        # Test with no parameters
        action1 = TransformMaterialsCoordinatorAction()
        self.assertFalse(hasattr(action1, 'character_name'))
        self.assertFalse(hasattr(action1, 'target_item'))
        
        action2 = AnalyzeCraftingChainAction()
        self.assertFalse(hasattr(action2, 'character_name'))
        self.assertFalse(hasattr(action2, 'target_item'))
        
        action3 = AnalyzeResourcesAction()
        self.assertFalse(hasattr(action3, 'character_x'))
        self.assertFalse(hasattr(action3, 'character_y'))
        
        action4 = EvaluateWeaponRecipesAction()
        self.assertFalse(hasattr(action4, 'character_name'))
        self.assertFalse(hasattr(action4, 'current_weapon'))
        
        action5 = FindXpSourcesAction()
        self.assertFalse(hasattr(action5, 'skill'))
        self.assertFalse(hasattr(action5, 'kwargs'))

    def test_action_string_representations(self):
        """Test action string representations."""
        # Test consistent repr format
        action1 = TransformMaterialsCoordinatorAction()
        self.assertEqual("TransformMaterialsCoordinatorAction()", repr(action1))
        
        action2 = AnalyzeCraftingChainAction()
        self.assertEqual("AnalyzeCraftingChainAction()", repr(action2))
        
        action3 = AnalyzeResourcesAction()
        self.assertEqual("AnalyzeResourcesAction()", repr(action3))
        
        action4 = EvaluateWeaponRecipesAction()
        self.assertEqual("EvaluateWeaponRecipesAction()", repr(action4))
        
        action5 = FindXpSourcesAction()
        self.assertEqual("FindXpSourcesAction()", repr(action5))


if __name__ == '__main__':
    unittest.main()