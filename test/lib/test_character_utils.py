"""Tests for character utility functions."""

import pytest
from src.lib.character_utils import (
    calculate_hp_percentage, 
    calculate_xp_percentage,
    is_character_safe,
    is_hp_critically_low,
    is_hp_sufficient_for_combat,
    get_character_hp_status
)


class TestCharacterUtils:
    """Test character utility functions."""
    
    def test_calculate_hp_percentage(self):
        """Test HP percentage calculation."""
        assert calculate_hp_percentage(100, 100) == 100.0
        assert calculate_hp_percentage(50, 100) == 50.0
        assert calculate_hp_percentage(1, 100) == 1.0
        assert calculate_hp_percentage(0, 100) == 0.0
        assert calculate_hp_percentage(100, 0) == 0.0  # Edge case
        
    def test_calculate_xp_percentage(self):
        """Test XP percentage calculation."""
        assert calculate_xp_percentage(100, 200) == 50.0
        assert calculate_xp_percentage(0, 100) == 0.0
        assert calculate_xp_percentage(150, 150) == 100.0
        assert calculate_xp_percentage(50, 0) == 0.0  # Edge case
        
    def test_is_character_safe(self):
        """Test character safety determination."""
        assert is_character_safe(100, 100, 30.0) == True  # 100% HP
        assert is_character_safe(50, 100, 30.0) == True   # 50% HP
        assert is_character_safe(30, 100, 30.0) == True   # 30% HP (threshold)
        assert is_character_safe(29, 100, 30.0) == False  # 29% HP
        assert is_character_safe(1, 100, 30.0) == False   # 1% HP
        
    def test_is_hp_critically_low(self):
        """Test critical HP determination."""
        assert is_hp_critically_low(100, 100, 10.0) == False  # 100% HP
        assert is_hp_critically_low(50, 100, 10.0) == False   # 50% HP
        assert is_hp_critically_low(10, 100, 10.0) == True    # 10% HP (threshold)
        assert is_hp_critically_low(5, 100, 10.0) == True     # 5% HP
        assert is_hp_critically_low(1, 100, 10.0) == True     # 1% HP
        
    def test_is_hp_sufficient_for_combat(self):
        """Test combat HP sufficiency."""
        assert is_hp_sufficient_for_combat(100, 100, 15.0) == True  # 100% HP
        assert is_hp_sufficient_for_combat(50, 100, 15.0) == True   # 50% HP
        assert is_hp_sufficient_for_combat(15, 100, 15.0) == True   # 15% HP (threshold)
        assert is_hp_sufficient_for_combat(14, 100, 15.0) == False  # 14% HP
        assert is_hp_sufficient_for_combat(1, 100, 15.0) == False   # 1% HP
        
    def test_get_character_hp_status(self):
        """Test comprehensive HP status."""
        char_data = {'hp': 50, 'max_hp': 100}
        status = get_character_hp_status(char_data)
        
        assert status['hp'] == 50
        assert status['max_hp'] == 100
        assert status['hp_percentage'] == 50.0
        assert status['safe'] == True  # 50% > 30%
        assert status['critically_low'] == False  # 50% > 10%
        assert status['sufficient_for_combat'] == True  # 50% > 15%
        assert status['alive'] == True  # 50 > 0
        
        # Test critical HP
        char_data_critical = {'hp': 5, 'max_hp': 100}
        status_critical = get_character_hp_status(char_data_critical)
        
        assert status_critical['hp_percentage'] == 5.0
        assert status_critical['safe'] == False
        assert status_critical['critically_low'] == True
        assert status_critical['sufficient_for_combat'] == False
        assert status_critical['alive'] == True