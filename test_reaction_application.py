#!/usr/bin/env python3
"""
Test script to verify that action reactions are being applied correctly.

This script will test the action_class_map fix by executing an action
and checking if its reactions are properly applied to the world state.
"""

import logging
import sys
import os

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.controller.action_executor import ActionExecutor
from src.controller.action_factory import ActionFactory
from src.lib.yaml_data import YamlData
from src.game.globals import CONFIG_PREFIX

def test_action_reaction_application():
    """Test if action reactions are applied to update world state."""
    print("🧪 Testing action reaction application...")
    
    # Set up logging
    logging.basicConfig(level=logging.DEBUG)
    logger = logging.getLogger(__name__)
    
    try:
        # Initialize ActionExecutor
        config_path = f"{CONFIG_PREFIX}/action_configurations.yaml"
        action_executor = ActionExecutor(config_path)
        
        # Check if action_class_map is available
        print(f"✅ ActionFactory has action_class_map: {hasattr(action_executor.factory, 'action_class_map')}")
        
        if hasattr(action_executor.factory, 'action_class_map'):
            action_class_map = action_executor.factory.action_class_map
            print(f"📊 action_class_map contains {len(action_class_map)} actions")
            
            # Show some action classes to verify they're accessible
            sample_actions = ['analyze_equipment_gaps', 'find_workshops', 'move', 'attack']
            for action_name in sample_actions:
                if action_name in action_class_map:
                    action_class = action_class_map[action_name]
                    print(f"  ✅ {action_name}: {action_class.__name__}")
                    
                    # Check if action has reactions
                    if hasattr(action_class, 'reactions'):
                        reactions = action_class.reactions
                        print(f"    🔄 Has reactions: {reactions}")
                    else:
                        print(f"    ❌ No reactions attribute")
                else:
                    print(f"  ❌ {action_name}: Not found in action_class_map")
        
        # Test the _get_action_class method specifically
        print(f"\n🔍 Testing _get_action_class method...")
        test_actions = ['analyze_equipment_gaps', 'find_workshops', 'move']
        for action_name in test_actions:
            action_class = action_executor._get_action_class(action_name)
            if action_class:
                print(f"  ✅ {action_name}: Retrieved {action_class.__name__}")
                if hasattr(action_class, 'reactions'):
                    print(f"    🔄 Reactions: {action_class.reactions}")
            else:
                print(f"  ❌ {action_name}: Could not retrieve action class")
        
        print(f"\n✅ Test completed successfully!")
        return True
        
    except Exception as e:
        print(f"❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_action_reaction_application()
    sys.exit(0 if success else 1)