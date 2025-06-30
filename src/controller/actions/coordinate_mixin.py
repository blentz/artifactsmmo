#!/usr/bin/env python3
"""
Coordinate Standardization Mixin

This mixin provides standardized coordinate handling for all actions,
ensuring consistent parameter names and return formats across the system.
"""

from typing import Tuple, Optional, Dict, Any


class CoordinateStandardizationMixin:
    """
    Mixin to standardize coordinate handling across all actions.
    
    This ensures consistent coordinate parameter names and return formats
    to prevent coordinate passing bugs between actions.
    """
    
    @staticmethod
    def standardize_coordinate_input(x=None, y=None, target_x=None, target_y=None, 
                                   location=None, **kwargs) -> Tuple[Optional[int], Optional[int]]:
        """
        Standardize various coordinate input formats to target_x, target_y.
        
        Accepts coordinates in multiple formats and returns standardized format:
        - Direct parameters: target_x, target_y (preferred)
        - Legacy parameters: x, y  
        - Tuple format: location=(x, y)
        - Context format: from kwargs
        
        Args:
            x: X coordinate (legacy format)
            y: Y coordinate (legacy format)
            target_x: Target X coordinate (preferred format)
            target_y: Target Y coordinate (preferred format)
            location: Coordinate tuple (x, y)
            **kwargs: Additional context that may contain coordinates
            
        Returns:
            Tuple of (target_x, target_y) in standardized format
        """
        # Priority 1: Direct target_x, target_y parameters (preferred)
        if target_x is not None and target_y is not None:
            return int(target_x), int(target_y)
        
        # Priority 2: Location tuple format
        if location is not None:
            if isinstance(location, (list, tuple)) and len(location) >= 2:
                return int(location[0]), int(location[1])
        
        # Priority 3: Legacy x, y parameters  
        if x is not None and y is not None:
            return int(x), int(y)
        
        # Priority 4: Check kwargs for various coordinate formats
        if 'target_x' in kwargs and 'target_y' in kwargs:
            return int(kwargs['target_x']), int(kwargs['target_y'])
        
        if 'x' in kwargs and 'y' in kwargs:
            return int(kwargs['x']), int(kwargs['y'])
            
        if 'location' in kwargs:
            loc = kwargs['location']
            if isinstance(loc, (list, tuple)) and len(loc) >= 2:
                return int(loc[0]), int(loc[1])
        
        return None, None
    
    @staticmethod
    def standardize_coordinate_output(x: int, y: int) -> Dict[str, Any]:
        """
        Create standardized coordinate output for action responses.
        
        Returns only the standardized target_x, target_y format.
        
        Args:
            x: X coordinate
            y: Y coordinate  
            
        Returns:
            Dictionary with standardized coordinate formats
        """
        return {
            'target_x': x,
            'target_y': y
        }
    
    @staticmethod
    def validate_coordinates(target_x: Optional[int], target_y: Optional[int]) -> bool:
        """
        Validate that coordinates are provided and valid.
        
        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            
        Returns:
            True if coordinates are valid, False otherwise
        """
        return (target_x is not None and target_y is not None and 
                isinstance(target_x, int) and isinstance(target_y, int))
    
    def get_standardized_coordinates(self, **kwargs) -> Tuple[Optional[int], Optional[int]]:
        """
        Get standardized coordinates from action context.
        
        This method can be used by actions to get coordinates in a consistent format.
        
        Args:
            **kwargs: Action execution context
            
        Returns:
            Tuple of (target_x, target_y) coordinates
        """
        return self.standardize_coordinate_input(**kwargs)
    
    def create_coordinate_response(self, x: int, y: int, **additional_data) -> Dict[str, Any]:
        """
        Create a standardized coordinate response.
        
        Args:
            x: X coordinate
            y: Y coordinate
            **additional_data: Additional response data
            
        Returns:
            Dictionary with standardized coordinate response
        """
        response = self.standardize_coordinate_output(x, y)
        response.update(additional_data)
        return response


# Utility functions for use outside of classes
def standardize_coordinates(coordinate_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Utility function to standardize coordinate data.
    
    Args:
        coordinate_data: Dictionary potentially containing coordinates
        
    Returns:
        Dictionary with standardized coordinate format (target_x, target_y only)
    """
    mixin = CoordinateStandardizationMixin()
    
    # Extract coordinates using standardization logic
    target_x, target_y = mixin.standardize_coordinate_input(**coordinate_data)
    
    if target_x is not None and target_y is not None:
        # Create standardized output (target_x, target_y only)
        standardized = mixin.standardize_coordinate_output(target_x, target_y)
        
        # Replace coordinate data with standardized format
        result = {k: v for k, v in coordinate_data.items() 
                 if k not in ['x', 'y', 'location']}  # Remove legacy formats
        result.update(standardized)
        return result
    
    return coordinate_data


def extract_target_coordinates(data: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
    """
    Extract target coordinates from data in standardized format.
    
    Args:
        data: Dictionary containing coordinate data
        
    Returns:
        Tuple of (target_x, target_y) coordinates
    """
    return CoordinateStandardizationMixin.standardize_coordinate_input(**data)