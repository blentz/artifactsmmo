"""
Tests for StateDiagnostics class.

Comprehensive test coverage for state validation and analysis functionality.
"""

import pytest
from typing import Any

from src.ai_player.diagnostics.state_diagnostics import StateDiagnostics
from src.ai_player.state.game_state import GameState
from tests.fixtures.character_states import CharacterStateFixtures, get_test_character_state


class TestStateDiagnostics:
    """Test suite for StateDiagnostics class"""

    @pytest.fixture
    def state_diagnostics(self):
        """Create StateDiagnostics instance for testing"""
        return StateDiagnostics()

    @pytest.fixture
    def valid_state(self):
        """Create valid game state for testing"""
        return {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.CHARACTER_GOLD: 500,
            GameState.HP_CURRENT: 80,
            GameState.HP_MAX: 100,
            GameState.CURRENT_X: 5,
            GameState.CURRENT_Y: 10,
            GameState.COOLDOWN_READY: True,
            GameState.MINING_LEVEL: 5,
            GameState.MINING_XP: 200
        }

    @pytest.fixture
    def invalid_state(self):
        """Create state with validation issues"""
        return {
            GameState.CHARACTER_LEVEL: -1,  # Invalid level
            GameState.HP_CURRENT: 150,      # HP > max HP
            GameState.HP_MAX: 100,
            GameState.CHARACTER_GOLD: -50,  # Negative gold
            GameState.COOLDOWN_READY: "not_boolean"  # Wrong type
        }

    def test_init(self, state_diagnostics):
        """Test StateDiagnostics initialization"""
        assert state_diagnostics is not None
        assert hasattr(state_diagnostics, 'required_state_keys')
        assert hasattr(state_diagnostics, 'numeric_state_keys')
        assert GameState.CHARACTER_LEVEL in state_diagnostics.required_state_keys
        assert GameState.CHARACTER_LEVEL in state_diagnostics.numeric_state_keys

    def test_validate_state_enum_usage_valid(self, state_diagnostics):
        """Test enum validation with valid state keys"""
        valid_string_state = {
            "character_level": 10,
            "character_xp": 1000,
            "hp_current": 80
        }

        invalid_keys = state_diagnostics.validate_state_enum_usage(valid_string_state)
        assert len(invalid_keys) == 0

    def test_validate_state_enum_usage_invalid(self, state_diagnostics):
        """Test enum validation with invalid state keys"""
        invalid_string_state = {
            "character_level": 10,
            "invalid_key": 100,
            "another_bad_key": "value",
            123: "numeric_key"  # Non-string, non-GameState key
        }

        invalid_keys = state_diagnostics.validate_state_enum_usage(invalid_string_state)
        assert "invalid_key" in invalid_keys
        assert "another_bad_key" in invalid_keys
        assert "123" in invalid_keys  # Numeric key converted to string
        assert "character_level" not in invalid_keys

    def test_check_state_consistency_consistent(self, state_diagnostics, valid_state):
        """Test consistency check with matching states"""
        api_state = {"character_level": 10, "character_xp": 1000, "hp_current": 80}
        local_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.HP_CURRENT: 80
        }

        analysis = state_diagnostics.check_state_consistency(api_state, local_state)
        assert analysis["consistent"] is True
        assert len(analysis["discrepancies"]) == 0
        assert len(analysis["value_differences"]) == 0

    def test_check_state_consistency_inconsistent(self, state_diagnostics):
        """Test consistency check with different states"""
        api_state = {"character_level": 15, "character_xp": 2000, "new_api_key": 100}
        local_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.HP_CURRENT: 80  # Missing in API
        }

        analysis = state_diagnostics.check_state_consistency(api_state, local_state)
        assert analysis["consistent"] is False
        assert "hp_current" in analysis["missing_in_api"]
        assert "new_api_key" in analysis["missing_in_local"]
        assert len(analysis["value_differences"]) == 2  # Level and XP differences

    def test_analyze_state_changes(self, state_diagnostics):
        """Test state change analysis"""
        old_state = {
            GameState.CHARACTER_LEVEL: 10,
            GameState.CHARACTER_XP: 1000,
            GameState.HP_CURRENT: 50
        }
        new_state = {
            GameState.CHARACTER_LEVEL: 11,  # Increased
            GameState.CHARACTER_XP: 1500,   # Increased
            GameState.HP_CURRENT: 30        # Decreased
        }

        analysis = state_diagnostics.analyze_state_changes(old_state, new_state)
        assert analysis["has_changes"] is True
        assert len(analysis["changes"]) == 3
        assert len(analysis["positive_changes"]) == 2  # Level and XP
        assert len(analysis["concerning_changes"]) == 1  # HP decrease

    def test_validate_state_completeness_complete(self, state_diagnostics, valid_state):
        """Test completeness validation with complete state"""
        missing_keys = state_diagnostics.validate_state_completeness(valid_state)
        assert len(missing_keys) == 0

    def test_validate_state_completeness_incomplete(self, state_diagnostics):
        """Test completeness validation with incomplete state"""
        incomplete_state = {
            GameState.CHARACTER_LEVEL: 10,
            # Missing required keys
        }

        missing_keys = state_diagnostics.validate_state_completeness(incomplete_state)
        assert len(missing_keys) > 0
        assert GameState.CHARACTER_XP in missing_keys
        assert GameState.HP_CURRENT in missing_keys

    def test_format_state_for_display(self, state_diagnostics, valid_state):
        """Test state formatting for CLI display"""
        formatted = state_diagnostics.format_state_for_display(valid_state)

        assert "CHARACTER PROGRESSION" in formatted
        assert "HEALTH STATUS" in formatted
        assert "POSITION" in formatted
        assert "SKILLS" in formatted
        assert "character_level: 10" in formatted
        assert "hp_percentage:" in formatted

    def test_detect_invalid_state_values_valid(self, state_diagnostics, valid_state):
        """Test invalid value detection with valid state"""
        errors = state_diagnostics.detect_invalid_state_values(valid_state)
        assert len(errors) == 0

    def test_detect_invalid_state_values_invalid(self, state_diagnostics, invalid_state):
        """Test invalid value detection with invalid state"""
        errors = state_diagnostics.detect_invalid_state_values(invalid_state)

        assert len(errors) > 0
        error_text = " ".join(errors)
        assert "Invalid character level" in error_text
        assert "Current HP (150) exceeds max HP (100)" in error_text
        assert "Invalid gold" in error_text
        assert "Invalid cooldown_ready" in error_text

    def test_detect_invalid_state_values_comprehensive(self, state_diagnostics):
        """Test comprehensive invalid value detection"""
        comprehensive_invalid_state = {
            GameState.CHARACTER_LEVEL: -1,
            GameState.HP_CURRENT: -5,  # Negative HP
            GameState.HP_MAX: 0,       # Zero max HP
            GameState.MINING_LEVEL: 50,  # Above max level
            GameState.MINING_XP: -100,   # Negative XP
            GameState.CHARACTER_GOLD: -50,
            GameState.COOLDOWN_READY: "invalid"
        }

        errors = state_diagnostics.detect_invalid_state_values(comprehensive_invalid_state)

        assert len(errors) >= 6
        error_text = " ".join(errors)
        assert "Invalid character level" in error_text
        assert "Invalid current HP" in error_text
        assert "Invalid max HP" in error_text
        assert "Invalid mining_level" in error_text
        assert "Invalid mining_xp" in error_text
        assert "Invalid gold" in error_text
        assert "Invalid cooldown_ready" in error_text

    def test_get_state_statistics(self, state_diagnostics, valid_state):
        """Test state statistics generation"""
        stats = state_diagnostics.get_state_statistics(valid_state)

        assert stats["character_level"] == 10
        assert stats["total_xp"] == 1000
        assert stats["gold"] == 500
        assert stats["hp_percentage"] == 80.0
        assert "skills" in stats
        assert stats["progress_to_max"] == (10 / 45) * 100
        assert "mining" in stats["skills"]

    def test_helper_methods(self, state_diagnostics):
        """Test helper methods for change analysis"""
        # Test _classify_change
        change_type = state_diagnostics._classify_change(GameState.CHARACTER_LEVEL, 10, 11)
        assert change_type == "increased"

        change_type = state_diagnostics._classify_change(GameState.HP_CURRENT, 100, 80)
        assert change_type == "decreased"

        # Test added values (None -> value)
        change_type = state_diagnostics._classify_change(GameState.CHARACTER_LEVEL, None, 10)
        assert change_type == "added"

        # Test removed values (value -> None)
        change_type = state_diagnostics._classify_change(GameState.CHARACTER_LEVEL, 10, None)
        assert change_type == "removed"

        # Test unchanged values
        change_type = state_diagnostics._classify_change(GameState.CHARACTER_LEVEL, 10, 10)
        assert change_type == "unchanged"

        # Test non-numeric modified values
        change_type = state_diagnostics._classify_change(GameState.CHARACTER_LEVEL, "old", "new")
        assert change_type == "modified"

        # Test _is_positive_change
        positive = state_diagnostics._is_positive_change(GameState.CHARACTER_LEVEL, 10, 11)
        assert positive is True

        positive = state_diagnostics._is_positive_change(GameState.HP_CURRENT, 100, 80)
        assert positive is False

        # Test cooldown becoming ready
        positive = state_diagnostics._is_positive_change(GameState.COOLDOWN_READY, False, True)
        assert positive is True

        positive = state_diagnostics._is_positive_change(GameState.COOLDOWN_READY, True, False)
        assert positive is False

        # Test non-cooldown key that should return False
        positive = state_diagnostics._is_positive_change(GameState.CURRENT_X, 5, 10)
        assert positive is False

        # Test _is_concerning_change
        concerning = state_diagnostics._is_concerning_change(GameState.HP_CURRENT, 100, 80)
        assert concerning is True

        concerning = state_diagnostics._is_concerning_change(GameState.CHARACTER_LEVEL, 10, 11)
        assert concerning is False

        # Test cooldown going off
        concerning = state_diagnostics._is_concerning_change(GameState.COOLDOWN_READY, True, False)
        assert concerning is True

        # Test large gold decrease
        concerning = state_diagnostics._is_concerning_change(GameState.CHARACTER_GOLD, 1000, 400)
        assert concerning is True  # 60% decrease

        concerning = state_diagnostics._is_concerning_change(GameState.CHARACTER_GOLD, 1000, 800)
        assert concerning is False  # 20% decrease

    def test_analyze_state_changes_comprehensive(self, state_diagnostics):
        """Test comprehensive state change analysis with fixture data."""
        old_state = CharacterStateFixtures.get_level_10_experienced()
        new_state = CharacterStateFixtures.get_level_25_advanced()
        
        analysis = state_diagnostics.analyze_state_changes(old_state, new_state)
        
        assert analysis["has_changes"] is True
        assert len(analysis["changes"]) > 0
        assert "progression_metrics" in analysis
        assert len(analysis["positive_changes"]) > 0
        
        # Verify progression metrics
        metrics = analysis["progression_metrics"]
        assert metrics["level_gained"] == 15  # From 10 to 25
        assert metrics["xp_gained"] > 0
        assert metrics["gold_gained"] > 0
        assert len(metrics["skills_improved"]) > 0

    def test_analyze_state_changes_no_changes(self, state_diagnostics, valid_state):
        """Test state change analysis when no changes exist."""
        analysis = state_diagnostics.analyze_state_changes(valid_state, valid_state)
        
        assert analysis["has_changes"] is False
        assert len(analysis["changes"]) == 0
        assert len(analysis["positive_changes"]) == 0
        assert len(analysis["concerning_changes"]) == 0

    def test_analyze_state_changes_edge_cases(self, state_diagnostics):
        """Test state change analysis edge cases."""
        # Test with emergency low HP scenario
        normal_state = CharacterStateFixtures.get_level_10_experienced()
        emergency_state = CharacterStateFixtures.get_emergency_low_hp()
        
        analysis = state_diagnostics.analyze_state_changes(normal_state, emergency_state)
        
        assert analysis["has_changes"] is True
        assert len(analysis["concerning_changes"]) > 0
        
        # Should detect HP decrease as concerning
        hp_changes = [change for change in analysis["concerning_changes"] 
                     if change["key"] == GameState.HP_CURRENT.value]
        assert len(hp_changes) > 0

    def test_format_state_for_display_comprehensive(self, state_diagnostics):
        """Test comprehensive state formatting with all sections."""
        state = CharacterStateFixtures.get_level_25_advanced()
        formatted = state_diagnostics.format_state_for_display(state)
        
        # Check all required sections are present
        assert "=== CHARACTER PROGRESSION ===" in formatted
        assert "=== HEALTH STATUS ===" in formatted
        assert "=== POSITION ===" in formatted
        assert "=== SKILLS ===" in formatted
        assert "=== ACTION STATUS ===" in formatted
        assert "=== OTHER STATES ===" in formatted
        
        # Check specific values are displayed
        assert "character_level: 25" in formatted
        assert "character_gold: 10000" in formatted
        assert "hp_percentage:" in formatted
        assert "current_x: 45" in formatted
        assert "cooldown_ready: True" in formatted

    def test_format_state_for_display_minimal(self, state_diagnostics):
        """Test state formatting with minimal state data."""
        minimal_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.HP_CURRENT: 100,
            GameState.HP_MAX: 100
        }
        
        formatted = state_diagnostics.format_state_for_display(minimal_state)
        
        assert "character_level: 1" in formatted
        assert "hp_current: 100" in formatted
        assert "hp_percentage: 100.0%" in formatted

    def test_get_state_statistics_comprehensive(self, state_diagnostics):
        """Test comprehensive state statistics generation."""
        state = CharacterStateFixtures.get_level_25_advanced()
        stats = state_diagnostics.get_state_statistics(state)
        
        assert stats["character_level"] == 25
        assert stats["total_xp"] == 15000
        assert stats["gold"] == 10000
        assert stats["hp_percentage"] == 90.0  # 180/200 * 100
        assert stats["total_skill_levels"] > 0
        assert stats["average_skill_level"] > 1
        assert stats["progress_to_max"] > 50  # Level 25 is more than halfway to 45
        
        # Check skills dictionary structure
        assert "mining" in stats["skills"]
        assert "level" in stats["skills"]["mining"]
        assert "xp" in stats["skills"]["mining"]

    def test_get_state_statistics_edge_cases(self, state_diagnostics):
        """Test state statistics with edge cases."""
        # Test with zero/missing values - note CHARACTER_LEVEL ends with '_level' 
        # so it gets counted as a skill in the current implementation
        minimal_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.HP_CURRENT: 0,
            GameState.HP_MAX: 100
        }
        
        stats = state_diagnostics.get_state_statistics(minimal_state)
        
        assert stats["character_level"] == 1
        assert stats["total_xp"] == 0  # Default value
        assert stats["gold"] == 0  # Default value
        assert stats["hp_percentage"] == 0.0
        # CHARACTER_LEVEL gets counted as a skill because it ends with '_level'
        assert stats["total_skill_levels"] == 1  # CHARACTER_LEVEL counted
        assert stats["average_skill_level"] == 1.0

    def test_calculate_progression_metrics(self, state_diagnostics):
        """Test progression metrics calculation."""
        old_state = CharacterStateFixtures.get_level_1_starter()
        new_state = CharacterStateFixtures.get_level_10_experienced()
        
        metrics = state_diagnostics._calculate_progression_metrics(old_state, new_state)
        
        assert metrics["level_gained"] == 9  # From 1 to 10
        assert metrics["xp_gained"] > 0
        assert metrics["gold_gained"] > 0
        assert metrics["hp_change"] > 0  # HP should increase
        assert len(metrics["skills_improved"]) > 0
        
        # Check skill improvement details
        for skill_improvement in metrics["skills_improved"]:
            assert "skill" in skill_improvement
            assert "old_level" in skill_improvement
            assert "new_level" in skill_improvement
            assert "levels_gained" in skill_improvement
            assert skill_improvement["levels_gained"] > 0

    def test_edge_cases_and_error_handling(self, state_diagnostics):
        """Test edge cases and error handling scenarios."""
        # Test with empty states
        empty_analysis = state_diagnostics.check_state_consistency({}, {})
        assert empty_analysis["consistent"] is True
        
        # Test with None values
        state_with_none = {GameState.CHARACTER_LEVEL: None}
        errors = state_diagnostics.detect_invalid_state_values(state_with_none)
        assert len(errors) > 0
        
        # Test formatting with empty state
        formatted_empty = state_diagnostics.format_state_for_display({})
        assert "CHARACTER PROGRESSION" in formatted_empty
        
        # Test statistics with empty state
        stats_empty = state_diagnostics.get_state_statistics({})
        assert stats_empty["character_level"] == 0
        assert stats_empty["total_xp"] == 0

    def test_special_scenarios_with_fixtures(self, state_diagnostics):
        """Test special game scenarios using fixtures."""
        # Test inventory full scenario
        inventory_full_state = CharacterStateFixtures.get_inventory_full()
        errors = state_diagnostics.detect_invalid_state_values(inventory_full_state)
        # Should have no validation errors (inventory full is a valid state)
        assert len(errors) == 0
        
        # Test on cooldown scenario
        cooldown_state = CharacterStateFixtures.get_character_on_cooldown()
        stats = state_diagnostics.get_state_statistics(cooldown_state)
        assert stats["character_level"] == 10
        
        # Test wealthy trader scenario
        trader_state = CharacterStateFixtures.get_wealthy_trader()
        formatted = state_diagnostics.format_state_for_display(trader_state)
        assert "character_gold: 50000" in formatted

    def test_validation_boundaries(self, state_diagnostics):
        """Test validation at boundary values."""
        # Test minimum valid values
        min_valid_state = {
            GameState.CHARACTER_LEVEL: 1,
            GameState.HP_CURRENT: 0,
            GameState.HP_MAX: 1,
            GameState.CHARACTER_GOLD: 0,
            GameState.MINING_LEVEL: 1,
            GameState.MINING_XP: 0
        }
        
        errors = state_diagnostics.detect_invalid_state_values(min_valid_state)
        assert len(errors) == 0
        
        # Test maximum valid values
        max_valid_state = {
            GameState.CHARACTER_LEVEL: 45,
            GameState.HP_CURRENT: 1000,
            GameState.HP_MAX: 1000,
            GameState.CHARACTER_GOLD: 999999,
            GameState.MINING_LEVEL: 45,
            GameState.MINING_XP: 999999
        }
        
        errors = state_diagnostics.detect_invalid_state_values(max_valid_state)
        assert len(errors) == 0
        
        # Test boundary violations
        boundary_invalid_state = {
            GameState.CHARACTER_LEVEL: 0,  # Below minimum
            GameState.HP_MAX: 0,  # Invalid zero max HP
            GameState.MINING_LEVEL: 46,  # Above maximum
            GameState.CHARACTER_GOLD: -1  # Below minimum
        }
        
        errors = state_diagnostics.detect_invalid_state_values(boundary_invalid_state)
        assert len(errors) >= 4
