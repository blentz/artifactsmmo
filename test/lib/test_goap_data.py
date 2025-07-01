import os
import tempfile
import unittest
from unittest.mock import patch

from src.lib.goap_data import Action_List, GoapData, Planner


class TestGoapData(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.filename = os.path.join(self.test_dir.name, "test_goap.yaml")
        # Create an empty file to simulate file existence
        with open(self.filename, 'w') as f:
            pass

    def tearDown(self):
        self.test_dir.cleanup()

    @patch('src.lib.yaml_data.safe_load')
    def test_init_with_existing_file(self, mock_safe_load):
        # Mock the YAML content
        mock_content = {'planners': [], 'data': {}}
        mock_safe_load.return_value = mock_content

        # Create GoapData instance
        goap_data = GoapData(filename=self.filename)

        # Check if data is loaded correctly
        self.assertEqual(goap_data.data, {})
        self.assertTrue(isinstance(goap_data.planners, list))
        self.assertEqual(len(goap_data.planners), 0)
        self.assertEqual(goap_data.filename, self.filename)

    @patch('src.lib.yaml_data.os.path.exists')
    def test_init_with_nonexistent_file(self, mock_exists):
        # Mock file as not existing
        mock_exists.return_value = False

        # Create GoapData instance
        goap_data = GoapData(filename=self.filename)

        # Check if empty data is created
        self.assertEqual(goap_data.data, {})
        self.assertTrue(isinstance(goap_data.planners, list))
        self.assertEqual(len(goap_data.planners), 0)
        self.assertEqual(goap_data.filename, self.filename)

    @patch('src.lib.yaml_data.safe_load')
    def test_load(self, mock_safe_load):
        # Mock the YAML content with planners and actions
        mock_actions = {
            "reload": {
                "conditions": {"ammo": 0},
                "reactions": {"ammo": 30}
            },
            "attack": {
                "conditions": {"health": 100, "ammo": 5},
                "reactions": {"health": -5}
            }
        }
        mock_planners = [
            {
                "start_state": {"health": 80, "ammo": 30},
                "goal_state": {"health": 60, "ammo": 25},
                "actions_list": mock_actions,
                "actions_weights": {"reload": 1.0, "attack": 0.5}
            }
        ]
        mock_content = {'planners': mock_planners, 'data': {}}
        mock_safe_load.return_value = mock_content

        # Create GoapData instance and load data
        goap_data = GoapData(filename=self.filename)
        goap_data.load()

        # Check if planners are loaded correctly
        self.assertEqual(len(goap_data.planners), 1)

        planner = goap_data.planners[0]
        self.assertEqual(planner.start_state['health'], 80)
        self.assertEqual(planner.goal_state['health'], 60)

        # Check actions list
        action_list = planner.action_list
        self.assertIn('reload', action_list.conditions)
        self.assertIn('attack', action_list.conditions)

    @patch('src.lib.yaml_data.safe_dump')
    def test_save(self, mock_safe_dump):
        # Create GoapData instance with initial data
        goap_data = GoapData(filename=self.filename)
        goap_data.data = {'existing': 'data'}

        # Add a planner
        keys = {'health', 'ammo'}
        planner = Planner(*keys)
        planner.set_start_state(health=80, ammo=30)
        planner.set_goal_state(health=60, ammo=25)

        action_list = Action_List()
        action_list.add_condition('reload', ammo=0)
        action_list.add_reaction('reload', ammo=30)
        action_list.set_weight('reload', 1.0)

        planner.set_action_list(action_list=action_list)
        goap_data.planners.append(planner)

        # Save data
        goap_data.save()

        # Check if save was called with correct arguments (data and file handle)
        expected_data = {'data': {'existing': 'data'}, 'planners': [planner]}
        args, kwargs = mock_safe_dump.call_args

        # Verify the first argument is our data
        self.assertEqual(args[0], expected_data)

        # Verify it was called with a file handle
        # We can't use isinstance() directly with 'open' as it's not a type
        # Instead, check if the object has the attributes we expect from a file
        self.assertTrue(hasattr(args[1], 'write') and hasattr(args[1], 'read'))

if __name__ == '__main__':
    unittest.main()
