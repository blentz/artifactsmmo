#!/usr/bin/env python3
"""Tests for character management functionality."""

import pytest
import random
import string
import logging
from unittest.mock import Mock, patch, MagicMock

from artifactsmmo_api_client.client import AuthenticatedClient, Client
from artifactsmmo_api_client.models.add_character_schema import AddCharacterSchema
from artifactsmmo_api_client.models.delete_character_schema import DeleteCharacterSchema
from artifactsmmo_api_client.models.character_skin import CharacterSkin
from artifactsmmo_api_client.models.character_response_schema import CharacterResponseSchema

import src.main as main_module


class TestCharacterManagement:
    """Test character management functions."""

    def setup_method(self):
        """Set up test fixtures and save random state."""
        self._random_state = random.getstate()
        # Save and restore logging configuration to prevent contamination
        self._root_logger_level = logging.getLogger().level
        self._root_logger_handlers = logging.getLogger().handlers.copy()

    def teardown_method(self):
        """Clean up test fixtures and restore random state."""
        random.setstate(self._random_state)
        # Restore logging configuration
        root_logger = logging.getLogger()
        root_logger.setLevel(self._root_logger_level)
        # Ensure handlers are properly restored
        root_logger.handlers = self._root_logger_handlers

    def test_generate_random_character_name(self):
        """Test random character name generation."""
        # Test basic functionality
        name = main_module.generate_random_character_name()
        assert isinstance(name, str)
        assert len(name) == 8
        
        # Verify all characters are letters
        assert all(c in string.ascii_letters for c in name)
        
        # Test uniqueness (generate multiple names, they should be different most of the time)
        names = [main_module.generate_random_character_name() for _ in range(10)]
        assert len(set(names)) > 1  # At least some should be different
        
        # Test determinism with seeded random
        random.seed(42)
        name1 = main_module.generate_random_character_name()
        random.seed(42)
        name2 = main_module.generate_random_character_name()
        assert name1 == name2

    @patch('src.main.create_character_sync')
    @patch('src.main.generate_random_character_name')
    @patch('random.choice')
    def test_create_character_success(self, mock_random_choice, mock_generate_name, mock_api_call):
        """Test successful character creation."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_generate_name.return_value = "TestChar"
        mock_random_choice.return_value = CharacterSkin.MEN1
        mock_response = Mock(spec=CharacterResponseSchema)
        mock_api_call.return_value = mock_response
        
        # Execute
        result = main_module.create_character(mock_client)
        
        # Verify
        assert result is True
        mock_generate_name.assert_called_once()
        mock_random_choice.assert_called_once()
        mock_api_call.assert_called_once()
        
        # Verify API call parameters
        call_args = mock_api_call.call_args
        assert call_args[1]['client'] == mock_client
        character_schema = call_args[1]['body']
        assert isinstance(character_schema, AddCharacterSchema)
        assert character_schema.name == "TestChar"
        assert character_schema.skin == CharacterSkin.MEN1

    @patch('src.main.create_character_sync')
    @patch('src.main.generate_random_character_name')
    def test_create_character_unauthenticated_client(self, mock_generate_name, mock_api_call):
        """Test character creation with unauthenticated client."""
        # Setup - create a client that is NOT AuthenticatedClient
        mock_client = Mock()
        mock_client.__class__.__name__ = 'Client'  # Simulate unauthenticated client
        mock_generate_name.return_value = "TestChar"
        
        # Execute
        result = main_module.create_character(mock_client)
        
        # Verify
        assert result is False
        mock_generate_name.assert_not_called()
        mock_api_call.assert_not_called()

    @patch('src.main.create_character_sync')
    @patch('src.main.generate_random_character_name')
    def test_create_character_api_returns_none(self, mock_generate_name, mock_api_call):
        """Test character creation when API returns None."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_generate_name.return_value = "TestChar"
        mock_api_call.return_value = None
        
        # Execute
        result = main_module.create_character(mock_client)
        
        # Verify
        assert result is False
        mock_api_call.assert_called_once()

    @patch('src.main.create_character_sync')
    @patch('src.main.generate_random_character_name')
    def test_create_character_api_exception(self, mock_generate_name, mock_api_call):
        """Test character creation when API raises exception."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_generate_name.return_value = "TestChar"
        mock_api_call.side_effect = Exception("API Error")
        
        # Execute
        result = main_module.create_character(mock_client)
        
        # Verify
        assert result is False
        mock_api_call.assert_called_once()

    @patch('src.main.delete_character_sync')
    def test_delete_character_success(self, mock_api_call):
        """Test successful character deletion."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_response = Mock(spec=CharacterResponseSchema)
        mock_api_call.return_value = mock_response
        
        # Execute
        result = main_module.delete_character("TestChar", mock_client)
        
        # Verify
        assert result is True
        mock_api_call.assert_called_once()
        
        # Verify API call parameters
        call_args = mock_api_call.call_args
        assert call_args[1]['client'] == mock_client
        delete_schema = call_args[1]['body']
        assert isinstance(delete_schema, DeleteCharacterSchema)
        assert delete_schema.name == "TestChar"

    @patch('src.main.delete_character_sync')
    def test_delete_character_with_whitespace(self, mock_api_call):
        """Test character deletion with whitespace in name."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_response = Mock(spec=CharacterResponseSchema)
        mock_api_call.return_value = mock_response
        
        # Execute
        result = main_module.delete_character("  TestChar  ", mock_client)
        
        # Verify
        assert result is True
        delete_schema = mock_api_call.call_args[1]['body']
        assert delete_schema.name == "TestChar"  # Should be stripped

    @patch('src.main.delete_character_sync')
    def test_delete_character_unauthenticated_client(self, mock_api_call):
        """Test character deletion with unauthenticated client."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'Client'  # Not AuthenticatedClient
        
        # Execute
        result = main_module.delete_character("TestChar", mock_client)
        
        # Verify
        assert result is False
        mock_api_call.assert_not_called()

    @patch('src.main.delete_character_sync')
    def test_delete_character_empty_name(self, mock_api_call):
        """Test character deletion with empty name."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        
        # Test various empty name cases
        for empty_name in ["", "   ", None]:
            # Execute
            result = main_module.delete_character(empty_name, mock_client)
            
            # Verify
            assert result is False
        
        mock_api_call.assert_not_called()

    @patch('src.main.delete_character_sync')
    def test_delete_character_api_returns_none(self, mock_api_call):
        """Test character deletion when API returns None."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_api_call.return_value = None
        
        # Execute
        result = main_module.delete_character("TestChar", mock_client)
        
        # Verify
        assert result is False
        mock_api_call.assert_called_once()

    @patch('src.main.delete_character_sync')
    def test_delete_character_api_exception(self, mock_api_call):
        """Test character deletion when API raises exception."""
        # Setup
        mock_client = Mock()
        mock_client.__class__.__name__ = 'AuthenticatedClient'
        mock_api_call.side_effect = Exception("API Error")
        
        # Execute
        result = main_module.delete_character("TestChar", mock_client)
        
        # Verify
        assert result is False
        mock_api_call.assert_called_once()


class TestCLIIntegration:
    """Test CLI integration for character management."""
    
    @patch('src.main.create_character')
    def test_main_create_character_flow(self, mock_create):
        """Test main function handles create character flow."""
        from src.cli import parse_args
        
        # Setup
        mock_create.return_value = True
        
        # Test CLI parsing
        args = parse_args(['-c'])
        assert args.create_character is True
        assert args.delete_character is None

    def test_cli_validation_create_and_delete_mutually_exclusive(self):
        """Test that create and delete character are mutually exclusive."""
        from src.cli import parse_args
        
        with pytest.raises(SystemExit):
            parse_args(['-c', '-d', 'TestChar'])

    def test_cli_examples_in_help(self):
        """Test that CLI help contains updated examples."""
        from src.cli import create_parser
        
        parser = create_parser()
        help_text = parser.format_help()
        
        assert "-c                                # Create a new character with random name" in help_text
        assert "-d OldChar                        # Delete a character" in help_text

    @patch('src.main.delete_character')
    def test_main_delete_character_flow(self, mock_delete):
        """Test main function handles delete character flow."""
        from src.cli import parse_args
        
        # Setup
        mock_delete.return_value = True
        
        # Test CLI parsing
        args = parse_args(['-d', 'TestChar'])
        assert args.create_character is False
        assert args.delete_character == 'TestChar'

    def test_character_skin_selection(self):
        """Test that all character skins are available for selection."""
        # Test that CharacterSkin enum has expected values
        expected_skins = {'men1', 'men2', 'men3', 'women1', 'women2', 'women3', 'corrupted1', 'zombie1'}
        actual_skins = {skin.value for skin in CharacterSkin}
        
        # Verify all expected skins are present
        assert expected_skins.issubset(actual_skins)
        
        # Test that we can get all skins as a list
        all_skins = list(CharacterSkin)
        assert len(all_skins) >= 8  # At least the expected skins


class TestRandomNameGeneration:
    """Detailed tests for random name generation."""
    
    def test_name_length_consistency(self):
        """Test that generated names are always 8 characters."""
        for _ in range(100):
            name = main_module.generate_random_character_name()
            assert len(name) == 8

    def test_name_character_validity(self):
        """Test that generated names only contain valid characters."""
        valid_chars = set(string.ascii_letters)
        
        for _ in range(50):
            name = main_module.generate_random_character_name()
            name_chars = set(name)
            assert name_chars.issubset(valid_chars)

    def test_name_case_variation(self):
        """Test that generated names can contain both upper and lowercase."""
        # Generate many names and check for case variation
        names = [main_module.generate_random_character_name() for _ in range(100)]
        all_names = ''.join(names)
        
        has_upper = any(c.isupper() for c in all_names)
        has_lower = any(c.islower() for c in all_names)
        
        # With 800 characters (100 names * 8 chars), we should see both cases
        assert has_upper and has_lower

    def test_name_uniqueness_probability(self):
        """Test that name generation has reasonable uniqueness."""
        # Generate a reasonable number of names
        names = [main_module.generate_random_character_name() for _ in range(100)]
        
        # With 8 characters from 52 possibilities, we should have high uniqueness
        unique_names = set(names)
        uniqueness_ratio = len(unique_names) / len(names)
        
        # Expect at least 95% uniqueness in small sample
        assert uniqueness_ratio >= 0.95