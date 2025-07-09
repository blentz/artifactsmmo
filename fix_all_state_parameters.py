#!/usr/bin/env python3
"""
Comprehensive script to fix all remaining StateParameters issues.
"""

import subprocess
import re
import time

def get_missing_parameters():
    """Get all missing parameters from test failures."""
    result = subprocess.run(['python', '-m', 'pytest', 'test/controller/actions/', '--tb=short', '-v'], 
                          capture_output=True, text=True)
    
    output = result.stdout + result.stderr
    
    # Extract missing parameters from error messages
    missing_params = set()
    
    # Pattern for "Parameter 'X' not registered in StateParameters"
    pattern = r"Parameter '([^']+)' not registered in StateParameters"
    matches = re.findall(pattern, output)
    
    for param in matches:
        missing_params.add(param)
    
    return sorted(missing_params)

def add_missing_parameters(missing_params):
    """Add missing parameters to StateParameters."""
    if not missing_params:
        return
    
    # Read the current StateParameters file
    with open('src/lib/state_parameters.py', 'r') as f:
        content = f.read()
    
    # Find the insertion point (before the Combat Context Parameters section)
    insertion_point = content.find('    # Combat Context Parameters')
    if insertion_point == -1:
        # Find the end of the file
        insertion_point = content.rfind('\n')
    
    # Create new parameter lines
    new_lines = []
    for param in missing_params:
        # Convert to constant name (e.g., "raw_material_needs" -> "RAW_MATERIAL_NEEDS")
        const_name = param.upper().replace('.', '_').replace(' ', '_')
        new_lines.append(f'    {const_name} = "{param}"')
    
    # Insert the new parameters
    new_content = content[:insertion_point] + '\n'.join(new_lines) + '\n    \n' + content[insertion_point:]
    
    # Write back
    with open('src/lib/state_parameters.py', 'w') as f:
        f.write(new_content)
    
    print(f"Added {len(missing_params)} missing parameters:")
    for param in missing_params:
        print(f"  - {param}")

def main():
    """Main function to fix all StateParameters issues."""
    print("🔍 Finding missing StateParameters...")
    
    # Get missing parameters
    missing_params = get_missing_parameters()
    
    if not missing_params:
        print("✅ No missing parameters found!")
        return
    
    print(f"Found {len(missing_params)} missing parameters")
    
    # Add missing parameters
    add_missing_parameters(missing_params)
    
    print("✅ Added missing parameters to StateParameters")
    
    # Run tests again to see improvement
    print("\n🧪 Running tests to check improvement...")
    result = subprocess.run(['python', '-m', 'pytest', 'test/controller/actions/', '--tb=no', '-q'], 
                          capture_output=True, text=True)
    
    # Extract test results
    output = result.stdout + result.stderr
    lines = output.split('\n')
    
    for line in lines:
        if 'failed' in line and 'passed' in line:
            print(f"📊 Test results: {line}")
            break

if __name__ == '__main__':
    main()