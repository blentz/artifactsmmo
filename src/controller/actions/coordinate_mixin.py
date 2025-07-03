#!/usr/bin/env python3
"""
Coordinate Standardization Mixin

This mixin provides standardized coordinate handling for all actions,
ensuring consistent parameter names and return formats across the system.
"""

from typing import Any, Dict, Optional, Tuple


class CoordinateStandardizationMixin:
    """
    Mixin to standardize coordinate handling across all actions.
    
    This ensures consistent coordinate parameter names and return formats
    to prevent coordinate passing bugs between actions.
    """
    
    @staticmethod
    def standardize_coordinate_input(x=None, y=None, target_x=None, target_y=None, 
                                   location=None) -> Tuple[Optional[int], Optional[int]]:
        """
        Standardize various coordinate input formats to target_x, target_y.
        
        Accepts coordinates in multiple formats and returns standardized format:
        - Direct parameters: target_x, target_y (preferred)
        - Legacy parameters: x, y  
        - Tuple format: location=(x, y)
        
        Args:
            x: X coordinate (legacy format)
            y: Y coordinate (legacy format)
            target_x: Target X coordinate (preferred format)
            target_y: Target Y coordinate (preferred format)
            location: Coordinate tuple (x, y)
            
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
    
    
    def get_standardized_coordinates(self, context: Dict[str, Any]) -> Tuple[Optional[int], Optional[int]]:
        """
        Get standardized coordinates from action context.
        
        This method can be used by actions to get coordinates in a consistent format.
        
        Args:
            context: Action execution context dictionary
            
        Returns:
            Tuple of (target_x, target_y) coordinates
        """
        return self.standardize_coordinate_input(
            x=context.get('x'),
            y=context.get('y'),
            target_x=context.get('target_x'),
            target_y=context.get('target_y'),
            location=context.get('location')
        )
    
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
