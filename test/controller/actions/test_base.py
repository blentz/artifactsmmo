"""Test module for ActionBase class."""

import unittest
from unittest.mock import Mock

from src.controller.actions.base import ActionBase, ActionResult
from src.lib.action_context import ActionContext


class TestActionBase(unittest.TestCase):
    """Test cases for ActionBase class."""
    
    def test_validate_goap_metadata_missing_conditions(self):
        """Test that action raises error when conditions are missing."""
        # Create a class without conditions (override the inherited one with None)
        class MissingConditionsAction(ActionBase):
            conditions = None  # Override inherited conditions to simulate missing
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            MissingConditionsAction()
        self.assertIn("must define 'conditions' as a dict", str(cm.exception))
    
    def test_validate_goap_metadata_invalid_conditions(self):
        """Test that action raises error when conditions are not a dict."""
        # Create a class with invalid conditions type
        class InvalidConditionsAction(ActionBase):
            conditions = "not a dict"  # Invalid type
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            InvalidConditionsAction()
        self.assertIn("must define 'conditions' as a dict", str(cm.exception))
    
    def test_validate_goap_metadata_missing_reactions(self):
        """Test that action raises error when reactions are missing."""
        # Create a class without reactions (override inherited one with None)
        class MissingReactionsAction(ActionBase):
            conditions = {}
            reactions = None  # Override inherited reactions to simulate missing
            weight = 1.0
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            MissingReactionsAction()
        self.assertIn("must define 'reactions' as a dict", str(cm.exception))
    
    def test_validate_goap_metadata_invalid_reactions(self):
        """Test that action raises error when reactions are not a dict."""
        # Create a class with invalid reactions type
        class InvalidReactionsAction(ActionBase):
            conditions = {}
            reactions = ["not", "a", "dict"]  # Invalid type
            weight = 1.0
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            InvalidReactionsAction()
        self.assertIn("must define 'reactions' as a dict", str(cm.exception))
    
    def test_validate_goap_metadata_missing_weight(self):
        """Test that action raises error when weight is missing."""
        # Create a class without weight (override inherited one with None)
        class MissingWeightAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = None  # Override inherited weight to simulate missing
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            MissingWeightAction()
        self.assertIn("must define 'weight' as a number", str(cm.exception))
    
    def test_validate_goap_metadata_invalid_weight(self):
        """Test that action raises error when weight is not a number."""
        # Create a class with invalid weight type
        class InvalidWeightAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = "not a number"  # Invalid type
            
            def execute(self, client, context):
                pass
                
        # Should raise ValueError
        with self.assertRaises(ValueError) as cm:
            InvalidWeightAction()
        self.assertIn("must define 'weight' as a number", str(cm.exception))
    
    def test_valid_action_class(self):
        """Test that a valid action class can be instantiated."""
        # Create a valid action class
        class ValidAction(ActionBase):
            conditions = {"test": True}
            reactions = {"result": "success"}
            weight = 1.5
            
            def execute(self, client, context):
                return self.create_success_result("Test")
                
        # Should instantiate without error
        action = ValidAction()
        self.assertIsInstance(action, ActionBase)
        self.assertEqual(action.conditions, {"test": True})
        self.assertEqual(action.reactions, {"result": "success"})
        self.assertEqual(action.weight, 1.5)
    
    def test_create_success_result(self):
        """Test create_success_result method."""
        class TestAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                return self.create_success_result("Success", key1="value1", key2=42)
                
        action = TestAction()
        result = action.execute(None, ActionContext())
        
        self.assertIsInstance(result, ActionResult)
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Success")
        self.assertEqual(result.data["key1"], "value1")
        self.assertEqual(result.data["key2"], 42)
    
    def test_create_error_result(self):
        """Test create_error_result method."""
        class TestAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                return self.create_error_result("Error occurred", error_code=500)
                
        action = TestAction()
        result = action.execute(None, ActionContext())
        
        self.assertIsInstance(result, ActionResult)
        self.assertFalse(result.success)
        self.assertEqual(result.error, "Error occurred")
        self.assertEqual(result.data["error_code"], 500)
    
    def test_action_result_structure(self):
        """Test ActionResult dataclass structure."""
        # Test basic result
        result = ActionResult(
            success=True,
            message="Test message",
            data={"test": "data"},
            error=None,
            state_changes={"state": "changed"}
        )
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "Test message")
        self.assertEqual(result.data, {"test": "data"})
        self.assertIsNone(result.error)
        self.assertEqual(result.state_changes, {"state": "changed"})
        
        # Test error result
        error_result = ActionResult(
            success=False,
            message="",
            data={},
            error="Test error",
            state_changes={}
        )
        
        self.assertFalse(error_result.success)
        self.assertEqual(error_result.error, "Test error")
    
    def test_action_result_post_init_none_data(self):
        """Test ActionResult post_init with None data."""
        result = ActionResult(
            success=True,
            message="Test",
            data=None,  # This should trigger line 25
            state_changes=None
        )
        
        self.assertEqual(result.data, {})
        self.assertEqual(result.state_changes, {})
    
    def test_action_result_request_subgoal(self):
        """Test request_subgoal method."""
        result = ActionResult(success=True)
        
        # Test with all parameters
        result.request_subgoal(
            goal_name="test_goal",
            parameters={"param1": "value1"},
            preserve_context=["key1", "key2"]
        )
        
        self.assertEqual(result.subgoal_request["goal_name"], "test_goal")
        self.assertEqual(result.subgoal_request["parameters"], {"param1": "value1"})
        self.assertEqual(result.subgoal_request["preserve_context"], ["key1", "key2"])
        
        # Test with default parameters
        result2 = ActionResult(success=True)
        result2.request_subgoal("another_goal")
        
        self.assertEqual(result2.subgoal_request["goal_name"], "another_goal")
        self.assertEqual(result2.subgoal_request["parameters"], {})
        self.assertEqual(result2.subgoal_request["preserve_context"], [])
    
    def test_create_result_with_state_changes(self):
        """Test create_result_with_state_changes method."""
        class TestAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                return self.create_result_with_state_changes(
                    success=True,
                    state_changes={"inventory": "updated", "location": "changed"},
                    message="State changed",
                    extra_key="extra_value"
                )
                
        action = TestAction()
        result = action.execute(None, ActionContext())
        
        self.assertTrue(result.success)
        self.assertEqual(result.message, "State changed")
        self.assertEqual(result.state_changes, {"inventory": "updated", "location": "changed"})
        self.assertEqual(result.data["extra_key"], "extra_value")
        self.assertEqual(result.action_name, "TestAction")
    
    def test_repr_method(self):
        """Test __repr__ method."""
        class TestAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = 2.5
            
            def execute(self, client, context):
                pass
                
        action = TestAction()
        self.assertEqual(repr(action), "TestAction(weight=2.5)")
    
    def test_execute_base_implementation(self):
        """Test that execute method stores context and logs."""
        class TestAction(ActionBase):
            conditions = {}
            reactions = {}
            weight = 1.0
            
            def execute(self, client, context):
                # Call parent execute to trigger lines 95-96
                super().execute(client, context)
                # We'll check the context outside this method since this isn't a TestCase
                return self.create_success_result("Success")
                
        action = TestAction()
        context = ActionContext()
        result = action.execute(None, context)
        
        self.assertTrue(result.success)
        # Verify context was stored
        self.assertEqual(action._context, context)


if __name__ == '__main__':
    unittest.main()