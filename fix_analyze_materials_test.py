#!/usr/bin/env python3
"""
Script to fix the test_analyze_materials_for_transformation.py file
"""

import re

def fix_analyze_materials_test():
    """Fix the test file to use StateParameters."""
    file_path = "/home/brett_lentz/git/artifactsmmo/test/controller/actions/test_analyze_materials_for_transformation.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Dictionary-style access patterns to fix
    replacements = [
        # inventory parameter
        (r"self\.context\['inventory'\]", "self.context.set(StateParameters.MATERIALS_INVENTORY"),
        (r"context\['inventory'\]", "context.set(StateParameters.MATERIALS_INVENTORY"),
        
        # required_materials parameter  
        (r"self\.context\['required_materials'\]", "self.context.set(StateParameters.MATERIALS_REQUIRED_MATERIALS"),
        (r"context\['required_materials'\]", "context.set(StateParameters.MATERIALS_REQUIRED_MATERIALS"),
        
        # action_config parameter
        (r"self\.context\['action_config'\]", "self.context.set(StateParameters.ACTION_CONFIG"),
        (r"context\['action_config'\]", "context.set(StateParameters.ACTION_CONFIG"),
        
        # Legacy character_name setting
        (r"context\.character_name = \"test_character\"", "context.set(StateParameters.CHARACTER_NAME, \"test_character\")"),
        
        # Fix get calls
        (r"context\.get\('target_item'\)", "context.get(StateParameters.MATERIALS_TARGET_ITEM)"),
        (r"context\.get\('transformations_needed'\)", "context.get('transformations_needed')"),
        
        # Fix = [ patterns to use proper assignment
        (r"= \[", ", ["),
        (r"= \{", ", {"),
        
        # Fix assignment operators that got messed up in previous replacements
        (r"self\.context\.set\(StateParameters\.MATERIALS_INVENTORY, \[", "self.context.set(StateParameters.MATERIALS_INVENTORY, ["),
        (r"self\.context\.set\(StateParameters\.MATERIALS_REQUIRED_MATERIALS, \{", "self.context.set(StateParameters.MATERIALS_REQUIRED_MATERIALS, {"),
        (r"self\.context\.set\(StateParameters\.ACTION_CONFIG, \{", "self.context.set(StateParameters.ACTION_CONFIG, {"),
        (r"context\.set\(StateParameters\.MATERIALS_INVENTORY, \[", "context.set(StateParameters.MATERIALS_INVENTORY, ["),
        (r"context\.set\(StateParameters\.ACTION_CONFIG, \{", "context.set(StateParameters.ACTION_CONFIG, {"),
        
    ]
    
    # Apply replacements
    for pattern, replacement in replacements:
        content = re.sub(pattern, replacement, content)
    
    # Write back
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fixed analyze_materials_for_transformation test file")

if __name__ == '__main__':
    fix_analyze_materials_test()