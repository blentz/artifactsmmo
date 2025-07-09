#!/usr/bin/env python3
"""Fix syntax errors in the analyze materials test file."""

import re

def fix_file():
    file_path = "/home/brett_lentz/git/artifactsmmo/test/controller/actions/test_analyze_materials_for_transformation.py"
    
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Fix common syntax errors
    # Fix closing parentheses after braces
    content = re.sub(r'}\)', '}', content)
    content = re.sub(r']\)', ']', content)
    
    # Fix cases where we have .set(..., [...) but missing closing paren
    lines = content.split('\n')
    fixed_lines = []
    in_set_call = False
    open_brackets = 0
    
    for line in lines:
        # Check if we're starting a set call
        if '.set(' in line and not line.strip().endswith(')'):
            in_set_call = True
            open_brackets = line.count('[') - line.count(']') + line.count('{') - line.count('}')
        
        # If we're in a set call, track brackets
        if in_set_call:
            open_brackets += line.count('[') - line.count(']') + line.count('{') - line.count('}')
            
            # If we've closed all brackets and this line doesn't end with ), add it
            if open_brackets == 0 and not line.strip().endswith(')') and not line.strip().endswith(','):
                line = line + ')'
                in_set_call = False
        
        fixed_lines.append(line)
    
    content = '\n'.join(fixed_lines)
    
    with open(file_path, 'w') as f:
        f.write(content)
    
    print("Fixed syntax errors")

if __name__ == '__main__':
    fix_file()