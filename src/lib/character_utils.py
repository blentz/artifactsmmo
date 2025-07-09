"""
Character utility functions for dynamic calculations.

This module provides utility functions for calculating character-related values
that should not be stored as derived data but calculated on-demand.
"""

from typing import Dict, Any, Optional


def calculate_hp_percentage(hp: int, max_hp: int) -> float:
    """
    Calculate HP percentage dynamically.
    
    Args:
        hp: Current HP value
        max_hp: Maximum HP value
        
    Returns:
        HP percentage as float (0.0 to 100.0)
    """
    return (hp / max_hp * 100) if max_hp > 0 else 0.0


def calculate_xp_percentage(xp: int, max_xp: int) -> float:
    """
    Calculate XP percentage dynamically.
    
    Args:
        xp: Current XP value  
        max_xp: Maximum XP value for current level
        
    Returns:
        XP percentage as float (0.0 to 100.0)
    """
    return (xp / max_xp * 100) if max_xp > 0 else 0.0


def is_character_safe(hp: int, max_hp: int, safety_threshold: float = 30.0) -> bool:
    """
    Determine if character is safe based on HP percentage.
    
    Args:
        hp: Current HP value
        max_hp: Maximum HP value
        safety_threshold: HP percentage threshold for safety (default 30%)
        
    Returns:
        True if character has sufficient HP to be considered safe
    """
    hp_pct = calculate_hp_percentage(hp, max_hp)
    return hp_pct >= safety_threshold


def is_hp_critically_low(hp: int, max_hp: int, critical_threshold: float = 10.0) -> bool:
    """
    Determine if character HP is critically low.
    
    Args:
        hp: Current HP value
        max_hp: Maximum HP value
        critical_threshold: HP percentage threshold for critical status (default 10%)
        
    Returns:
        True if character HP is critically low
    """
    hp_pct = calculate_hp_percentage(hp, max_hp)
    return hp_pct <= critical_threshold


def is_hp_sufficient_for_combat(hp: int, max_hp: int, combat_threshold: float = 15.0) -> bool:
    """
    Determine if character has sufficient HP for combat.
    
    Args:
        hp: Current HP value
        max_hp: Maximum HP value
        combat_threshold: HP percentage threshold for combat (default 15%)
        
    Returns:
        True if character has sufficient HP for combat
    """
    hp_pct = calculate_hp_percentage(hp, max_hp)
    return hp_pct >= combat_threshold


def get_character_hp_status(char_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Get comprehensive HP status for character.
    
    Args:
        char_data: Character data dictionary with 'hp' and 'max_hp' keys
        
    Returns:
        Dictionary with HP status information including:
        - hp: Current HP
        - max_hp: Maximum HP  
        - hp_percentage: HP percentage
        - safe: Whether character is safe
        - critically_low: Whether HP is critically low
        - sufficient_for_combat: Whether HP is sufficient for combat
        - alive: Whether character is alive (hp > 0)
    """
    hp = char_data.get('hp', 100)
    max_hp = char_data.get('max_hp', 100)
    
    return {
        'hp': hp,
        'max_hp': max_hp,
        'hp_percentage': calculate_hp_percentage(hp, max_hp),
        'safe': is_character_safe(hp, max_hp),
        'critically_low': is_hp_critically_low(hp, max_hp),
        'sufficient_for_combat': is_hp_sufficient_for_combat(hp, max_hp),
        'alive': hp > 0
    }