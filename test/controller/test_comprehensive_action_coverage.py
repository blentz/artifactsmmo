"""Comprehensive tests to maximize action test coverage with minimal mocking complexity."""

import unittest
import tempfile
import os
from unittest.mock import Mock, patch
from src.controller.actions.transform_raw_materials import TransformRawMaterialsAction
from src.controller.actions.analyze_crafting_chain import AnalyzeCraftingChainAction
from src.controller.actions.analyze_resources import AnalyzeResourcesAction
from src.controller.actions.evaluate_weapon_recipes import EvaluateWeaponRecipesAction
from src.controller.actions.find_xp_sources import FindXpSourcesAction
from src.controller.action_executor import ActionExecutor, ActionResult, CompositeActionStep


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
        """Test TransformRawMaterialsAction basic functionality."""
        action = TransformRawMaterialsAction("player", "sword")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.target_item, "sword")
        
        # Test repr
        expected = "TransformRawMaterialsAction(player, target=sword)"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'conditions'))
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'reactions'))
        self.assertTrue(hasattr(TransformRawMaterialsAction, 'weights'))
        
        # Test no client
        result = action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_analyze_crafting_chain_basic(self):
        """Test AnalyzeCraftingChainAction basic functionality."""
        action = AnalyzeCraftingChainAction("player", "sword")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.target_item, "sword")
        
        # Test repr
        expected = "AnalyzeCraftingChainAction(player, target=sword)"
        self.assertEqual(repr(action), expected)
        
        # Test initialization data structures
        self.assertEqual(action.analyzed_items, set())
        self.assertEqual(action.resource_nodes, {})
        self.assertEqual(action.workshops, {})
        self.assertEqual(action.crafting_dependencies, {})
        self.assertEqual(action.transformation_chains, [])
        
        # Test GOAP attributes
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeCraftingChainAction, 'weights'))
        
        # Test no client
        result = action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_analyze_resources_basic(self):
        """Test AnalyzeResourcesAction basic functionality."""
        action = AnalyzeResourcesAction(character_x=10, character_y=15, character_level=5)
        self.assertEqual(action.character_x, 10)
        self.assertEqual(action.character_y, 15)
        self.assertEqual(action.character_level, 5)
        
        # Test repr
        expected = "AnalyzeResourcesAction(10, 15, level=5, radius=10)"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'conditions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'reactions'))
        self.assertTrue(hasattr(AnalyzeResourcesAction, 'weights'))
        
        # Test no client
        result = action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_evaluate_weapon_recipes_basic(self):
        """Test EvaluateWeaponRecipesAction basic functionality."""
        action = EvaluateWeaponRecipesAction("player", current_weapon="iron_sword")
        self.assertEqual(action.character_name, "player")
        self.assertEqual(action.current_weapon, "iron_sword")
        
        # Test GOAP attributes
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'conditions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'reactions'))
        self.assertTrue(hasattr(EvaluateWeaponRecipesAction, 'weights'))
        
        # Test no client
        result = action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_find_xp_sources_basic(self):
        """Test FindXpSourcesAction basic functionality."""
        action = FindXpSourcesAction("weaponcrafting", character_level=5)
        self.assertEqual(action.skill, "weaponcrafting")
        self.assertEqual(action.kwargs.get('character_level'), 5)
        
        # Test repr
        expected = "FindXpSourcesAction(skill=weaponcrafting)"
        self.assertEqual(repr(action), expected)
        
        # Test GOAP attributes
        self.assertTrue(hasattr(FindXpSourcesAction, 'conditions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'reactions'))
        self.assertTrue(hasattr(FindXpSourcesAction, 'weights'))
        
        # Test no client
        result = action.execute(None)
        self.assertFalse(result['success'])
        self.assertIn('No API client provided', result['error'])

    def test_action_executor_dataclasses(self):
        """Test ActionExecutor dataclasses."""
        # Test ActionResult
        result = ActionResult(
            success=True,
            response={'status': 'ok'},
            action_name='test_action',
            execution_time=1.5,
            error_message=None,
            metadata={'key': 'value'}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.response['status'], 'ok')
        self.assertEqual(result.action_name, 'test_action')
        self.assertEqual(result.execution_time, 1.5)
        self.assertIsNone(result.error_message)
        self.assertEqual(result.metadata['key'], 'value')
        
        # Test CompositeActionStep
        step = CompositeActionStep(
            name='test_step',
            action='move',
            required=True,
            params={'x': 5, 'y': 10},
            conditions={'character_alive': True},
            on_failure='abort'
        )
        
        self.assertEqual(step.name, 'test_step')
        self.assertEqual(step.action, 'move')
        self.assertTrue(step.required)
        self.assertEqual(step.params['x'], 5)
        self.assertEqual(step.conditions['character_alive'], True)
        self.assertEqual(step.on_failure, 'abort')

    def test_action_executor_basic_functionality(self):
        """Test ActionExecutor basic functionality."""
        executor = ActionExecutor()
        self.assertIsNotNone(executor.factory)
        self.assertIsNotNone(executor.logger)
        
        # Test loading configurations
        configs = executor.load_action_configurations()
        self.assertIsInstance(configs, dict)

    def test_analyze_resources_helper_methods(self):
        """Test AnalyzeResourcesAction helper methods."""
        action = AnalyzeResourcesAction()
        
        # Test distance calculation
        distance = action._calculate_distance(0, 0, 3, 4)
        self.assertEqual(distance, 5.0)  # 3-4-5 triangle
        
        # Test resource accessibility calculation
        accessibility = action._calculate_resource_accessibility({'level': 5}, 10)
        self.assertEqual(accessibility, 'high')
        
        accessibility = action._calculate_resource_accessibility({'level': 15}, 10)
        self.assertEqual(accessibility, 'low')
        
        accessibility = action._calculate_resource_accessibility({}, 10)
        self.assertEqual(accessibility, 'unknown')
        
        # Test resource drops analysis
        drops = action._analyze_resource_drops({
            'drop': [{'code': 'iron_ore', 'quantity': 1}]
        })
        self.assertEqual(len(drops), 1)
        self.assertEqual(drops[0]['code'], 'iron_ore')
        
        drops = action._analyze_resource_drops({})
        self.assertEqual(drops, [])

    def test_analyze_crafting_chain_helper_methods(self):
        """Test AnalyzeCraftingChainAction helper methods."""
        action = AnalyzeCraftingChainAction("player")
        
        # Test resource item detection
        self.assertTrue(action._is_resource_item({'type': 'resource'}))
        self.assertFalse(action._is_resource_item({'type': 'weapon'}))
        self.assertFalse(action._is_resource_item({}))
        
        # Test crafting requirements extraction
        requirements = action._get_crafting_requirements({
            'craft': {
                'items': [
                    {'code': 'iron', 'quantity': 3},
                    {'code': 'wood', 'quantity': 1}
                ]
            }
        })
        self.assertEqual(len(requirements), 2)
        self.assertEqual(requirements[0]['code'], 'iron')
        self.assertEqual(requirements[0]['quantity'], 3)
        
        requirements = action._get_crafting_requirements({})
        self.assertEqual(requirements, [])

    def test_transform_raw_materials_helper_methods(self):
        """Test TransformRawMaterialsAction helper methods if they exist."""
        action = TransformRawMaterialsAction("player")
        
        # Test potential helper methods (will pass if they don't exist)
        if hasattr(action, '_is_raw_material'):
            result = action._is_raw_material('copper_ore')
            self.assertIsInstance(result, bool)
        
        if hasattr(action, '_get_transformation_recipe'):
            recipe = action._get_transformation_recipe('copper_ore')
            self.assertIsInstance(recipe, (dict, type(None)))

    def test_error_handling_patterns(self):
        """Test common error handling patterns across actions."""
        actions = [
            TransformRawMaterialsAction("player"),
            AnalyzeCraftingChainAction("player"),
            AnalyzeResourcesAction(),
            EvaluateWeaponRecipesAction("player"),
            FindXpSourcesAction("skill")
        ]
        
        for action in actions:
            with self.subTest(action=action.__class__.__name__):
                # Test no client error
                result = action.execute(None)
                self.assertFalse(result['success'])
                self.assertIn('No API client provided', result['error'])
                
                # Test result structure
                self.assertIn('success', result)
                self.assertIn('error', result)

    def test_goap_attribute_consistency(self):
        """Test GOAP attribute consistency across actions."""
        action_classes = [
            TransformRawMaterialsAction,
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
                self.assertTrue(hasattr(action_class, 'weights'))
                self.assertTrue(hasattr(action_class, 'g'))
                
                # Test attributes are proper types
                self.assertIsInstance(action_class.conditions, dict)
                self.assertIsInstance(action_class.reactions, dict)
                self.assertIsInstance(action_class.weights, dict)

    def test_action_initialization_patterns(self):
        """Test action initialization patterns."""
        # Test with minimal parameters
        action1 = TransformRawMaterialsAction("player")
        self.assertEqual(action1.character_name, "player")
        self.assertIsNone(action1.target_item)
        
        action2 = AnalyzeCraftingChainAction("player")
        self.assertEqual(action2.character_name, "player")
        self.assertIsNone(action2.target_item)
        
        action3 = AnalyzeResourcesAction()
        self.assertEqual(action3.character_x, 0)
        self.assertEqual(action3.character_y, 0)
        
        action4 = EvaluateWeaponRecipesAction("player")
        self.assertEqual(action4.character_name, "player")
        self.assertEqual(action4.current_weapon, "wooden_stick")
        
        action5 = FindXpSourcesAction("skill")
        self.assertEqual(action5.skill, "skill")
        self.assertEqual(action5.kwargs, {})

    def test_action_string_representations(self):
        """Test action string representations."""
        # Test consistent repr format
        action1 = TransformRawMaterialsAction("player", "sword")
        self.assertIn("player", repr(action1))
        self.assertIn("sword", repr(action1))
        
        action2 = AnalyzeCraftingChainAction("player", "sword")
        self.assertIn("player", repr(action2))
        self.assertIn("sword", repr(action2))
        
        action3 = AnalyzeResourcesAction(character_x=5, character_y=10)
        self.assertIn("5", repr(action3))
        self.assertIn("10", repr(action3))
        
        action4 = EvaluateWeaponRecipesAction("player", current_weapon="iron_sword")
        self.assertIn("player", repr(action4))
        
        action5 = FindXpSourcesAction("weaponcrafting")
        self.assertIn("weaponcrafting", repr(action5))


if __name__ == '__main__':
    unittest.main()