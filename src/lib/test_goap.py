import unittest
from src.lib.goap import World, Planner, Action_List
from src.lib.goap import distance_to_state, conditions_are_met, node_in_list, create_node

class TestGOAP(unittest.TestCase):

    def setUp(self):
        self.world = World()

    def tearDown(self):
        del self.world

    # World class tests
    def test_world_initialization(self):
        self.assertIsInstance(self.world, World)
        self.assertEqual(len(self.world.planners), 0)
        self.assertEqual(len(self.world.plans), 0)

    def test_add_planner(self):
        planner = Planner('key1', 'key2')
        self.world.add_planner(planner)
        self.assertEqual(len(self.world.planners), 1)
        self.assertIs(self.world.planners[0], planner)

    # Planner class tests
    def test_planner_initialization(self):
        planner = Planner('key1', 'key2')
        self.assertIsInstance(planner, Planner)
        self.assertEqual(planner.values['key1'], -1)
        self.assertEqual(planner.values['key2'], -1)

    def test_state_creation(self):
        planner = Planner('health', 'ammo')
        state = planner.state(health=100, ammo=30)
        self.assertEqual(state['health'], 100)
        self.assertEqual(state['ammo'], 30)
        self.assertEqual(state['health'] + state['ammo'], 130)  # Not -1

    def test_set_start_state(self):
        planner = Planner('health', 'ammo')
        planner.set_start_state(health=80, ammo=25)
        self.assertEqual(planner.start_state['health'], 80)
        self.assertEqual(planner.start_state['ammo'], 25)

    def test_set_goal_state(self):
        planner = Planner('health', 'ammo')
        planner.set_goal_state(health=100, ammo=30)
        self.assertEqual(planner.goal_state['health'], 100)
        self.assertEqual(planner.goal_state['ammo'], 30)

    def test_set_invalid_states(self):
        planner = Planner('health', 'ammo')
        with self.assertRaises(Exception):
            planner.set_start_state(invalid_key=10)  # Should raise exception

        with self.assertRaises(Exception):
            planner.set_goal_state(invalid_key=30)  # Should raise exception

    # Action_List class tests
    def test_action_list_initialization(self):
        action_list = Action_List()
        self.assertIsInstance(action_list, Action_List)
        self.assertEqual(len(action_list.conditions), 0)
        self.assertEqual(len(action_list.reactions), 0)
        self.assertEqual(len(action_list.weights), 0)

    def test_add_condition(self):
        action_list = Action_List()
        action_list.add_condition('reload', ammo=30)
        self.assertIn('reload', action_list.conditions)
        self.assertEqual(action_list.conditions['reload']['ammo'], 30)
        self.assertIn('reload', action_list.weights)
        self.assertEqual(action_list.weights['reload'], 1)

    def test_add_reaction(self):
        action_list = Action_List()
        action_list.add_condition('reload', ammo=30)
        action_list.add_reaction('reload', health=-5)  # Adding reaction for reload
        self.assertIn('reload', action_list.reactions)
        self.assertEqual(action_list.reactions['reload']['health'], -5)

    def test_add_unmatched_reaction(self):
        action_list = Action_List()
        with self.assertRaises(Exception):
            action_list.add_reaction('nonexistent_action')  # Should raise exception

    def test_set_weight(self):
        action_list = Action_List()
        action_list.add_condition('reload', ammo=30)
        action_list.set_weight('reload', 2)
        self.assertEqual(action_list.weights['reload'], 2)

    def test_set_unmatched_weight(self):
        action_list = Action_List()
        with self.assertRaises(Exception):
            action_list.set_weight('nonexistent_action', 2)  # Should raise exception

    # Helper functions tests
    def test_distance_to_state(self):
        state1 = {'health': 80, 'ammo': 25}
        state2 = {'health': 100, 'ammo': 30}
        distance = distance_to_state(state1, state2)
        self.assertEqual(distance, 2)  # Two differences: health and ammo

    def test_conditions_are_met(self):
        state1 = {'health': 80, 'ammo': 25}
        state2 = {'health': 80, 'ammo': 25}  # Same values
        self.assertTrue(conditions_are_met(state1, state2))

    def test_conditions_not_met(self):
        state1 = {'health': 80, 'ammo': 25}
        state2 = {'health': 100, 'ammo': 30}  # Different values
        self.assertFalse(conditions_are_met(state1, state2))

    def test_node_in_list(self):
        node1 = {"state": {'health': 80}, "name": "test"}
        node2 = {"state": {'health': 100}, "name": "test"}

        # Create a list with only node2
        nodes = {1: node2}
        self.assertFalse(node_in_list(node1, nodes))  # Different state

        # Add node1 to the list
        nodes[2] = node1
        self.assertTrue(node_in_list(node1, nodes))  # Now it should be found

    def test_create_node(self):
        path = {"nodes": {}, "node_id": 0}
        state = {'health': 80, 'ammo': 25}
        node = create_node(path, state, name="test")
        self.assertEqual(node["state"], state)
        self.assertEqual(node["name"], "test")
        self.assertIn(1, path["nodes"])  # Node should be added to the path

if __name__ == '__main__':
    unittest.main()
