#!/usr/bin/env python3
"""Fix all syntax errors in the analyze materials test file."""

import re

def fix_all_syntax():
    file_path = "/home/brett_lentz/git/artifactsmmo/test/controller/actions/test_analyze_materials_for_transformation.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix unmatched closing parentheses after dictionaries and lists
    content = re.sub(r'}\)\s*$', '}', content, flags=re.MULTILINE)
    content = re.sub(r']\)\s*$', ']', content, flags=re.MULTILINE)
    
    # Fix specific patterns that were messed up by the replacement
    # Lines that should end with ]) for set calls
    content = re.sub(r'\.set\(StateParameters\.[^,]+, \[[^\]]*\]\s*$', lambda m: m.group(0) + ')', content, flags=re.MULTILINE)
    content = re.sub(r'\.set\(StateParameters\.[^,]+, \{[^}]*\}\s*$', lambda m: m.group(0) + ')', content, flags=re.MULTILINE)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fixed all syntax errors")

if __name__ == '__main__':
    fix_all_syntax()