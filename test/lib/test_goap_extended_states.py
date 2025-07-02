"""
Test GOAP system with extended state types (strings, lists, dicts).
"""

import unittest

from src.lib.goap import _states_match, conditions_are_met, distance_to_state


class TestGOAPExtendedStates(unittest.TestCase):
    """Test GOAP functionality with non-boolean state types."""
    
    def test_states_match_strings(self):
        """Test string state matching."""
        # Exact match
        self.assertTrue(_states_match("weapon", "weapon"))
        self.assertFalse(_states_match("weapon", "armor"))
        
        # None handling
        self.assertTrue(_states_match(None, None))
        self.assertFalse(_states_match("weapon", None))
        
        # -1 handling
        self.assertTrue(_states_match("weapon", -1))
        self.assertTrue(_states_match(-1, "weapon"))
    
    def test_states_match_lists(self):
        """Test list state matching."""
        # Exact match required
        self.assertTrue(_states_match(["iron", "copper"], ["iron", "copper"]))
        self.assertFalse(_states_match(["iron", "copper"], ["iron"]))
        self.assertFalse(_states_match(["iron"], ["iron", "copper"]))
        
        # Order matters
        self.assertFalse(_states_match(["iron", "copper"], ["copper", "iron"]))
    
    def test_states_match_dicts(self):
        """Test dict state matching (subset allowed)."""
        # Subset matching - value2 can be subset of value1
        self.assertTrue(_states_match(
            {"level": 5, "type": "weapon", "material": "iron"},
            {"type": "weapon"}
        ))
        self.assertTrue(_states_match(
            {"level": 5, "type": "weapon"},
            {"level": 5, "type": "weapon"}
        ))
        
        # Not a subset
        self.assertFalse(_states_match(
            {"level": 5, "type": "weapon"},
            {"level": 6, "type": "weapon"}
        ))
        self.assertFalse(_states_match(
            {"type": "weapon"},
            {"type": "weapon", "level": 5}
        ))
    
    def test_states_match_mixed_types(self):
        """Test mixed type comparisons."""
        # Different types should not match
        self.assertFalse(_states_match("5", 5))
        self.assertFalse(_states_match(True, "true"))
        self.assertFalse(_states_match([1, 2], "1,2"))
    
    def test_distance_to_state_with_strings(self):
        """Test distance calculation with string states."""
        state1 = {
            "equipment_slot": "weapon",
            "workshop_type": "weaponcrafting",
            "character_status": "safe"
        }
        state2 = {
            "equipment_slot": "weapon",
            "workshop_type": "gearcrafting",
            "character_status": "safe"
        }
        
        # Only workshop_type differs
        self.assertEqual(distance_to_state(state1, state2), 1)
        
        # All match
        self.assertEqual(distance_to_state(state1, state1), 0)
        
        # All differ
        state3 = {
            "equipment_slot": "armor",
            "workshop_type": "jewelrycrafting",
            "character_status": "combat"
        }
        self.assertEqual(distance_to_state(state1, state3), 3)
    
    def test_distance_to_state_with_dicts(self):
        """Test distance calculation with dict states."""
        state1 = {
            "equipment": {"weapon": "iron_sword", "armor": "leather_armor"},
            "location": {"x": 5, "y": 10, "type": "workshop"}
        }
        state2 = {
            "equipment": {"weapon": "iron_sword"},  # Subset match
            "location": {"x": 5, "y": 10, "type": "workshop"}  # Exact match
        }
        
        # Both should match (subset allowed for dicts)
        self.assertEqual(distance_to_state(state1, state2), 0)
        
        # Different weapon
        state3 = {
            "equipment": {"weapon": "wooden_stick"},
            "location": {"x": 5, "y": 10, "type": "workshop"}
        }
        self.assertEqual(distance_to_state(state1, state3), 1)
    
    def test_conditions_are_met_with_complex_types(self):
        """Test condition checking with complex state types."""
        current_state = {
            "equipment_type": "weapon",
            "materials": ["iron", "copper", "wood"],
            "workshop": {"type": "weaponcrafting", "level": 2},
            "character_level": 5
        }
        
        # String match
        conditions1 = {"equipment_type": "weapon"}
        self.assertTrue(conditions_are_met(current_state, conditions1))
        
        # List match (exact)
        conditions2 = {"materials": ["iron", "copper", "wood"]}
        self.assertTrue(conditions_are_met(current_state, conditions2))
        
        # Dict subset match
        conditions3 = {"workshop": {"type": "weaponcrafting"}}
        self.assertTrue(conditions_are_met(current_state, conditions3))
        
        # Combined conditions
        conditions4 = {
            "equipment_type": "weapon",
            "workshop": {"type": "weaponcrafting"},
            "character_level": 5
        }
        self.assertTrue(conditions_are_met(current_state, conditions4))
        
        # Failed conditions
        conditions5 = {"equipment_type": "armor"}
        self.assertFalse(conditions_are_met(current_state, conditions5))
        
        conditions6 = {"workshop": {"type": "gearcrafting"}}
        self.assertFalse(conditions_are_met(current_state, conditions6))
    
    def test_consolidated_state_example(self):
        """Test a real example of consolidated states."""
        # Current state with consolidated equipment info
        current_state = {
            "equipment_status": {
                "weapon": "wooden_stick",
                "armor": None,
                "target_slot": "weapon",
                "upgrade_status": "analyzing"
            },
            "location_context": {
                "current": {"x": 0, "y": 1, "type": "spawn"},
                "workshop": {"type": "weaponcrafting", "x": 2, "y": 3},
                "target": {"x": 2, "y": 3, "reason": "crafting"}
            },
            "materials": {
                "inventory": {"ash_wood": 9, "iron_ore": 0},
                "required": {"iron_ore": 5, "coal": 2},
                "status": "gathering"
            },
            "skills": {
                "weaponcrafting": {"level": 1, "required": 2},
                "mining": {"level": 1, "required": 0}
            }
        }
        
        # Goal state requiring weapon upgrade
        goal_state = {
            "equipment_status": {
                "upgrade_status": "ready"
            },
            "materials": {
                "status": "sufficient"
            }
        }
        
        # Current state doesn't meet goal (2 differences)
        self.assertFalse(conditions_are_met(current_state, goal_state))
        self.assertEqual(distance_to_state(current_state, goal_state), 2)
        
        # Update state to meet goal
        current_state["equipment_status"]["upgrade_status"] = "ready"
        current_state["materials"]["status"] = "sufficient"
        
        # Now conditions are met
        self.assertTrue(conditions_are_met(current_state, goal_state))
        self.assertEqual(distance_to_state(current_state, goal_state), 0)


if __name__ == '__main__':
    unittest.main()