"""
Simple tests for APIClientWrapper to avoid circular import issues.

This test module provides focused coverage for the API client wrapper,
testing the core functionality while avoiding import complexity.
"""

from unittest.mock import Mock, patch

import pytest

# Mock the problematic modules to avoid circular imports
with patch.dict('sys.modules', {
    'src.ai_player.action_executor': Mock(),
    'src.ai_player': Mock()
}):
    import sys
    sys.path.insert(0, '/home/brett_lentz/git/artifactsmmo')


class TestAPIClientWrapperCore:
    """Test core APIClientWrapper functionality."""

    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    def test_init_with_mocked_imports(self, mock_auth_client, mock_token_config):
        """Test initialization with mocked imports."""
        # Setup mocks
        mock_token_instance = Mock()
        mock_token_instance.token = "test_token_123"
        mock_token_config.from_file.return_value = mock_token_instance
        mock_client_instance = Mock()
        mock_auth_client.return_value = mock_client_instance

        # Import and test within the patched context
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            from src.game_data.api_client_wrapper import APIClientWrapper

            wrapper = APIClientWrapper()

            mock_token_config.from_file.assert_called_once_with("TOKEN")
            mock_auth_client.assert_called_once_with(
                base_url="https://api.artifactsmmo.com",
                token="test_token_123"
            )
            assert wrapper.token_config == mock_token_instance
            assert wrapper.client == mock_client_instance

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    @patch('src.game_data.api_client_wrapper.create_character_asyncio_detailed')
    async def test_create_character_validation(self, mock_create_char, mock_auth_client, mock_token_config):
        """Test character creation with validation."""
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            from src.game_data.api_client_wrapper import APIClientWrapper

            # Setup wrapper
            mock_token_instance = Mock()
            mock_token_instance.token = "test_token"
            mock_token_config.from_file.return_value = mock_token_instance

            wrapper = APIClientWrapper()

            # Test invalid skin
            with patch('src.game_data.api_client_wrapper.CharacterSkin') as mock_skin:
                mock_skin.side_effect = ValueError("Invalid skin")

                with pytest.raises(ValueError, match="Invalid skin"):
                    await wrapper.create_character("test", "invalid_skin")

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    async def test_rate_limit_handling(self, mock_auth_client, mock_token_config):
        """Test rate limit handling."""
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            from src.game_data.api_client_wrapper import APIClientWrapper

            wrapper = APIClientWrapper()

            mock_response = Mock()
            mock_response.headers = {"Retry-After": "30"}

            with patch('asyncio.sleep') as mock_sleep:
                await wrapper._handle_rate_limit(mock_response)
                mock_sleep.assert_called_once_with(30)

    @pytest.mark.asyncio
    @patch('src.game_data.api_client_wrapper.TokenConfig')
    @patch('src.game_data.api_client_wrapper.AuthenticatedClient')
    async def test_response_processing(self, mock_auth_client, mock_token_config):
        """Test response processing."""
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            from src.game_data.api_client_wrapper import APIClientWrapper

            wrapper = APIClientWrapper()

            # Test successful response
            mock_response = Mock()
            mock_response.status_code = 200
            mock_response.parsed = {"data": "test"}

            result = await wrapper._process_response(mock_response)
            assert result == {"data": "test"}

            # Test error response
            mock_response.status_code = 404
            with pytest.raises(ValueError, match="Resource not found"):
                await wrapper._process_response(mock_response)


class TestAPIClientWrapperIntegration:
    """Test integration scenarios."""

    def test_imports_work_with_patching(self):
        """Test that imports work when properly patched."""
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            # Should not raise import error
            from src.game_data.api_client_wrapper import APIClientWrapper
            assert APIClientWrapper is not None

    def test_cooldown_manager_integration(self):
        """Test cooldown manager integration."""
        with patch.dict('sys.modules', {
            'src.ai_player.action_executor': Mock(),
            'src.ai_player': Mock(),
            'src.ai_player.models.character': Mock(),
        }):
            with patch('src.game_data.api_client_wrapper.TokenConfig'):
                with patch('src.game_data.api_client_wrapper.AuthenticatedClient'):
                    from src.game_data.api_client_wrapper import APIClientWrapper
                    from src.game_data.cooldown_manager import CooldownManager

                    wrapper = APIClientWrapper()
                    assert wrapper.cooldown_manager is not None
                    assert isinstance(wrapper.cooldown_manager, CooldownManager)
