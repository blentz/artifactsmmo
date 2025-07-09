#!/usr/bin/env python3
"""
Script to find missing StateParameters from test failures.
"""
import subprocess
import re

def find_missing_parameters():
    """Run tests and extract missing parameters."""
    # Run tests and capture output
    result = subprocess.run(['python', '-m', 'pytest', 'test/controller/actions/', '--tb=short', '-v'], 
                          capture_output=True, text=True)
    
    output = result.stdout + result.stderr
    
    # Extract missing parameters from error messages
    missing_params = set()
    pattern = r"Parameter '([^']+)' not registered in StateParameters"
    matches = re.findall(pattern, output)
    
    for param in matches:
        missing_params.add(param)
    
    return sorted(missing_params)

if __name__ == '__main__':
    missing = find_missing_parameters()
    print("Missing StateParameters:")
    for param in missing:
        print(f"  {param}")
    print(f"Total: {len(missing)}")