"""
Comprehensive tests for CooldownManager to achieve 100% code coverage.

This module tests all methods and edge cases in the CooldownManager class
including character cooldown tracking, ready status checking, and cooldown
waiting functionality.
"""

import asyncio
from datetime import datetime, timedelta, UTC
from unittest.mock import Mock

import pytest

from src.game_data.cooldown_manager import CooldownManager
from src.game_data.cooldown_info import CooldownInfo


class TestCooldownManager:
    """Test CooldownManager functionality and edge cases"""

    @pytest.fixture
    def cooldown_manager(self):
        """Create CooldownManager instance for testing"""
        return CooldownManager()

    def test_init(self, cooldown_manager):
        """Test CooldownManager initialization"""
        assert cooldown_manager.character_cooldowns == {}

    def test_update_from_character_with_expiration(self, cooldown_manager):
        """Test updating from character with cooldown expiration timestamp"""
        # Create mock character with cooldown expiration
        character = Mock()
        character.name = "test_character"
        character.cooldown = 30
        character.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=30)

        cooldown_manager.update_from_character(character)

        assert "test_character" in cooldown_manager.character_cooldowns
        cooldown_info = cooldown_manager.character_cooldowns["test_character"]
        assert cooldown_info.character_name == "test_character"
        assert cooldown_info.total_seconds == 30
        assert cooldown_info.remaining_seconds == 30
        assert cooldown_info.reason == "unknown"

    def test_update_from_character_without_expiration_but_with_cooldown(self, cooldown_manager):
        """Test updating from character with cooldown but no expiration timestamp"""
        # Create mock character without cooldown_expiration but with cooldown > 0
        character = Mock()
        character.name = "test_character"
        character.cooldown = 15
        # Simulate character not having cooldown_expiration attribute
        delattr(character, 'cooldown_expiration') if hasattr(character, 'cooldown_expiration') else None

        cooldown_manager.update_from_character(character)

        assert "test_character" in cooldown_manager.character_cooldowns
        cooldown_info = cooldown_manager.character_cooldowns["test_character"]
        assert cooldown_info.character_name == "test_character"
        assert cooldown_info.total_seconds == 15
        assert cooldown_info.remaining_seconds == 15
        assert cooldown_info.reason == "unknown"

    def test_update_from_character_with_none_expiration_but_with_cooldown(self, cooldown_manager):
        """Test updating from character with None expiration but cooldown > 0"""
        # Create mock character with None cooldown_expiration but cooldown > 0
        character = Mock()
        character.name = "test_character"
        character.cooldown = 20
        character.cooldown_expiration = None

        cooldown_manager.update_from_character(character)

        assert "test_character" in cooldown_manager.character_cooldowns
        cooldown_info = cooldown_manager.character_cooldowns["test_character"]
        assert cooldown_info.character_name == "test_character"
        assert cooldown_info.total_seconds == 20
        assert cooldown_info.remaining_seconds == 20
        assert cooldown_info.reason == "unknown"

    def test_update_from_character_ready_removes_existing_cooldown(self, cooldown_manager):
        """Test that ready character removes existing cooldown"""
        # First add a cooldown
        character = Mock()
        character.name = "test_character"
        character.cooldown = 30
        character.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=30)
        cooldown_manager.update_from_character(character)
        assert "test_character" in cooldown_manager.character_cooldowns

        # Now update with ready character (cooldown = 0)
        ready_character = Mock()
        ready_character.name = "test_character"
        ready_character.cooldown = 0
        ready_character.cooldown_expiration = None
        cooldown_manager.update_from_character(ready_character)

        assert "test_character" not in cooldown_manager.character_cooldowns

    def test_update_from_character_ready_no_existing_cooldown(self, cooldown_manager):
        """Test updating from ready character when no existing cooldown"""
        character = Mock()
        character.name = "test_character"
        character.cooldown = 0
        character.cooldown_expiration = None

        cooldown_manager.update_from_character(character)

        # Should not add any cooldown entry
        assert "test_character" not in cooldown_manager.character_cooldowns

    def test_is_ready_no_cooldown(self, cooldown_manager):
        """Test is_ready when character has no cooldown"""
        assert cooldown_manager.is_ready("test_character") is True

    def test_is_ready_with_cooldown(self, cooldown_manager):
        """Test is_ready when character has active cooldown"""
        # Add a cooldown that's still active
        future_time = datetime.now(UTC) + timedelta(seconds=30)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        assert cooldown_manager.is_ready("test_character") is False

    def test_is_ready_expired_cooldown(self, cooldown_manager):
        """Test is_ready when character's cooldown has expired"""
        # Add a cooldown that has already expired
        past_time = datetime.now(UTC) - timedelta(seconds=5)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=past_time.isoformat(),
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        assert cooldown_manager.is_ready("test_character") is True

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_ready(self, cooldown_manager):
        """Test wait_for_cooldown when character is already ready"""
        # Character has no cooldown, should return immediately
        await cooldown_manager.wait_for_cooldown("test_character")
        # If we get here without hanging, the test passes

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_with_short_cooldown(self, cooldown_manager):
        """Test wait_for_cooldown with a very short cooldown"""
        # Add a very short cooldown (should be expired by the time we check)
        past_time = datetime.now(UTC) + timedelta(seconds=1)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=past_time.isoformat(),
            total_seconds=1,
            remaining_seconds=1,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        # This should complete quickly since the cooldown expires almost immediately
        await cooldown_manager.wait_for_cooldown("test_character")

    def test_get_remaining_time_no_cooldown(self, cooldown_manager):
        """Test get_remaining_time when character has no cooldown"""
        assert cooldown_manager.get_remaining_time("test_character") == 0.0

    def test_get_remaining_time_with_cooldown(self, cooldown_manager):
        """Test get_remaining_time when character has active cooldown"""
        # Add a cooldown with 30 seconds remaining
        future_time = datetime.now(UTC) + timedelta(seconds=30)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        remaining = cooldown_manager.get_remaining_time("test_character")
        # Should be close to 30 seconds (within 1 second tolerance)
        assert 29.0 <= remaining <= 30.0

    def test_get_remaining_time_expired_cooldown(self, cooldown_manager):
        """Test get_remaining_time when cooldown has expired"""
        # Add an expired cooldown
        past_time = datetime.now(UTC) - timedelta(seconds=5)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=past_time.isoformat(),
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        assert cooldown_manager.get_remaining_time("test_character") == 0.0

    def test_update_cooldown(self, cooldown_manager):
        """Test update_cooldown method with mock cooldown schema"""
        # Create a mock CooldownSchema object
        mock_cooldown_schema = Mock()
        mock_cooldown_schema.expiration = datetime.now(UTC) + timedelta(seconds=30)
        mock_cooldown_schema.total_seconds = 30
        mock_cooldown_schema.remaining_seconds = 30
        # Mock reason as an enum with .value attribute
        mock_reason = Mock()
        mock_reason.value = "action"
        mock_cooldown_schema.reason = mock_reason

        cooldown_manager.update_cooldown("test_character", mock_cooldown_schema)

        assert "test_character" in cooldown_manager.character_cooldowns
        cooldown_info = cooldown_manager.character_cooldowns["test_character"]
        assert cooldown_info.character_name == "test_character"
        assert cooldown_info.total_seconds == 30
        assert cooldown_info.remaining_seconds == 30
        assert cooldown_info.reason == "action"

    def test_clear_cooldown(self, cooldown_manager):
        """Test clear_cooldown method"""
        # First add a cooldown
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=datetime.now(UTC).isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="action"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info
        assert "test_character" in cooldown_manager.character_cooldowns

        # Clear the cooldown
        cooldown_manager.clear_cooldown("test_character")

        assert "test_character" not in cooldown_manager.character_cooldowns

    def test_clear_cooldown_nonexistent(self, cooldown_manager):
        """Test clear_cooldown for character that doesn't have cooldown"""
        # Should not raise an error
        cooldown_manager.clear_cooldown("nonexistent_character")
        # Test passes if no exception is raised

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_integration(self, cooldown_manager):
        """Integration test for wait_for_cooldown with realistic scenario"""
        # Set up a character with a short cooldown that will expire during the wait
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=future_time.isoformat(),
            total_seconds=1,
            remaining_seconds=1,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        # Wait for the cooldown - should complete when cooldown expires
        start_time = datetime.now(UTC)
        await cooldown_manager.wait_for_cooldown("test_character")
        end_time = datetime.now(UTC)

        # Should have waited at least a bit but not too long
        wait_duration = (end_time - start_time).total_seconds()
        assert 0.8 <= wait_duration <= 1.5  # Allow some tolerance for timing


class TestCooldownManagerEdgeCases:
    """Test edge cases and error conditions"""

    @pytest.fixture
    def cooldown_manager(self):
        """Create CooldownManager instance for testing"""
        return CooldownManager()

    def test_update_from_character_malformed_data(self, cooldown_manager):
        """Test update_from_character with malformed character data"""
        # Character without required attributes
        character = Mock()
        character.name = "test_character"
        # Missing cooldown and cooldown_expiration attributes
        if hasattr(character, 'cooldown'):
            delattr(character, 'cooldown')
        if hasattr(character, 'cooldown_expiration'):
            delattr(character, 'cooldown_expiration')

        # Should handle gracefully without crashing
        try:
            cooldown_manager.update_from_character(character)
            # If no exception, test passes
        except AttributeError:
            # Expected behavior - method may require these attributes
            pass

    def test_multiple_character_management(self, cooldown_manager):
        """Test managing cooldowns for multiple characters"""
        # Add cooldowns for multiple characters
        characters = ["char1", "char2", "char3"]
        
        for i, char_name in enumerate(characters):
            character = Mock()
            character.name = char_name
            character.cooldown = (i + 1) * 10  # 10, 20, 30 seconds
            character.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=(i + 1) * 10)
            cooldown_manager.update_from_character(character)

        # Check all characters have cooldowns
        for char_name in characters:
            assert char_name in cooldown_manager.character_cooldowns
            assert not cooldown_manager.is_ready(char_name)

        # Clear one character's cooldown
        ready_char = Mock()
        ready_char.name = "char1"
        ready_char.cooldown = 0
        ready_char.cooldown_expiration = None
        cooldown_manager.update_from_character(ready_char)

        # Check that only char1 is ready
        assert cooldown_manager.is_ready("char1")
        assert not cooldown_manager.is_ready("char2")
        assert not cooldown_manager.is_ready("char3")

    def test_repeated_updates_same_character(self, cooldown_manager):
        """Test repeated updates for the same character"""
        character = Mock()
        character.name = "test_character"
        
        # First update - add cooldown
        character.cooldown = 30
        character.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=30)
        cooldown_manager.update_from_character(character)
        assert not cooldown_manager.is_ready("test_character")

        # Second update - different cooldown
        character.cooldown = 15
        character.cooldown_expiration = datetime.now(UTC) + timedelta(seconds=15)
        cooldown_manager.update_from_character(character)
        cooldown_info = cooldown_manager.character_cooldowns["test_character"]
        assert cooldown_info.total_seconds == 15

        # Third update - ready
        character.cooldown = 0
        character.cooldown_expiration = None
        cooldown_manager.update_from_character(character)
        assert cooldown_manager.is_ready("test_character")
        assert "test_character" not in cooldown_manager.character_cooldowns

    def test_get_cooldown_info_exists(self, cooldown_manager):
        """Test get_cooldown_info when cooldown exists"""
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=datetime.now(UTC).isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info

        result = cooldown_manager.get_cooldown_info("test_character")
        assert result == cooldown_info

    def test_get_cooldown_info_not_exists(self, cooldown_manager):
        """Test get_cooldown_info when cooldown doesn't exist"""
        result = cooldown_manager.get_cooldown_info("nonexistent_character")
        assert result is None

    def test_clear_expired_cooldowns(self, cooldown_manager):
        """Test clear_expired_cooldowns method"""
        # Add expired cooldown
        past_time = datetime.now(UTC) - timedelta(seconds=5)
        expired_cooldown = CooldownInfo(
            character_name="expired_character",
            expiration=past_time.isoformat(),
            total_seconds=30,
            remaining_seconds=0,
            reason="test"
        )
        cooldown_manager.character_cooldowns["expired_character"] = expired_cooldown

        # Add active cooldown
        future_time = datetime.now(UTC) + timedelta(seconds=30)
        active_cooldown = CooldownInfo(
            character_name="active_character",
            expiration=future_time.isoformat(),
            total_seconds=30,
            remaining_seconds=30,
            reason="test"
        )
        cooldown_manager.character_cooldowns["active_character"] = active_cooldown

        # Clear expired cooldowns
        cooldown_manager.clear_expired_cooldowns()

        # Only the active cooldown should remain
        assert "expired_character" not in cooldown_manager.character_cooldowns
        assert "active_character" in cooldown_manager.character_cooldowns

    def test_clear_all_cooldowns(self, cooldown_manager):
        """Test clear_all_cooldowns method"""
        # Add multiple cooldowns
        for i in range(3):
            cooldown_info = CooldownInfo(
                character_name=f"character_{i}",
                expiration=datetime.now(UTC).isoformat(),
                total_seconds=30,
                remaining_seconds=30,
                reason="test"
            )
            cooldown_manager.character_cooldowns[f"character_{i}"] = cooldown_info

        assert len(cooldown_manager.character_cooldowns) == 3

        cooldown_manager.clear_all_cooldowns()

        assert len(cooldown_manager.character_cooldowns) == 0

    def test_get_remaining_time_exception_handling(self, cooldown_manager):
        """Test get_remaining_time exception handling path"""
        # Create a cooldown info with invalid expiration data that will cause an exception
        invalid_cooldown = Mock()
        invalid_cooldown.expiration = "invalid_date_format"
        cooldown_manager.character_cooldowns["test_character"] = invalid_cooldown
        
        # Should return 0.0 when exception occurs during parsing
        remaining = cooldown_manager.get_remaining_time("test_character")
        assert remaining == 0.0

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_exact_sleep_scenarios(self, cooldown_manager):
        """Test wait_for_cooldown specific sleep calculation paths"""
        # Test the path where we use get_remaining_time when expiration is available
        # but calculation differs (lines 131-133)
        future_time = datetime.now(UTC) + timedelta(seconds=1)
        cooldown_info = CooldownInfo(
            character_name="test_character",
            expiration=future_time.isoformat(),
            total_seconds=2,  # Different from actual remaining time
            remaining_seconds=2,  # This will be different from calculated time
            reason="test"
        )
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info
        
        # This should trigger the path where we recalculate remaining time
        start_time = datetime.now(UTC)
        await cooldown_manager.wait_for_cooldown("test_character")
        end_time = datetime.now(UTC)
        
        # Should have waited approximately 1 second (the actual remaining time)
        wait_duration = (end_time - start_time).total_seconds()
        assert 0.8 <= wait_duration <= 1.5

    @pytest.mark.asyncio 
    async def test_wait_for_cooldown_no_time_remaining_property(self, cooldown_manager):
        """Test wait_for_cooldown when cooldown info has no time_remaining property"""
        # Create cooldown without time_remaining property (lines 131)
        cooldown_info = Mock(spec=['expiration', 'character_name', 'reason', 'is_ready'])  # Include is_ready but exclude time_remaining
        cooldown_info.expiration = datetime.now(UTC).isoformat()
        cooldown_info.is_ready = False  # Make sure it's not ready so we enter cooldown logic
        cooldown_manager.character_cooldowns["test_character"] = cooldown_info
        
        # Mock get_remaining_time to return 0 (ready) to avoid actual waiting
        original_get_remaining_time = cooldown_manager.get_remaining_time
        cooldown_manager.get_remaining_time = Mock(return_value=0.0)
        
        try:
            await cooldown_manager.wait_for_cooldown("test_character")
            
            # Verify get_remaining_time was called (line 131)
            cooldown_manager.get_remaining_time.assert_called_with("test_character")
        finally:
            # Restore original method
            cooldown_manager.get_remaining_time = original_get_remaining_time

    @pytest.mark.asyncio
    async def test_wait_for_cooldown_no_character_in_cooldowns(self, cooldown_manager):
        """Test wait_for_cooldown when character not in cooldowns dict but is_ready returns False"""
        # Character not in character_cooldowns dict
        assert "test_character" not in cooldown_manager.character_cooldowns
        
        # Mock is_ready to return False to enter cooldown logic, then get_remaining_time returns 0
        original_is_ready = cooldown_manager.is_ready
        original_get_remaining_time = cooldown_manager.get_remaining_time
        cooldown_manager.is_ready = Mock(return_value=False)
        cooldown_manager.get_remaining_time = Mock(return_value=0.0)
        
        try:
            await cooldown_manager.wait_for_cooldown("test_character")
            
            # Verify get_remaining_time was called (line 133)
            cooldown_manager.get_remaining_time.assert_called_with("test_character")
        finally:
            # Restore original methods
            cooldown_manager.is_ready = original_is_ready
            cooldown_manager.get_remaining_time = original_get_remaining_time