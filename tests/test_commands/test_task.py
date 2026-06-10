"""Tests for task commands."""

from unittest.mock import Mock, patch

from artifactsmmo_cli.commands.task import app
from tests.test_commands.conftest import api_error, api_response, cooldown_status, unexpected_status


class TestTaskCommands:
    """Test task command functionality."""

    def test_new_task_success(self, runner, stub_api):
        """Test successful new task command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["new", "testchar"])

            assert result.exit_code == 0
            assert "testchar accepted a new task" in result.stdout
            mock_api.assert_called_once()

    def test_complete_task_success(self, runner, stub_api):
        """Test successful complete task command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["complete", "testchar"])

            assert result.exit_code == 0
            assert "testchar completed task" in result.stdout
            mock_api.assert_called_once()

    def test_exchange_task_success(self, runner, stub_api):
        """Test successful exchange task command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 0
            assert "testchar exchanged task" in result.stdout
            mock_api.assert_called_once()

    def test_trade_task_success(self, runner, stub_api):
        """Test successful trade task command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["trade", "testchar", "copper_ore"])

            assert result.exit_code == 0
            assert "testchar traded 1x copper_ore" in result.stdout
            mock_api.assert_called_once()

    def test_cancel_task_success(self, runner, stub_api):
        """Test successful cancel task command."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_cancel_my_name_action_task_cancel_post.sync"
        ) as mock_api:
            mock_api.return_value = api_response(Mock())

            result = runner.invoke(app, ["cancel", "testchar"])

            assert result.exit_code == 0
            assert "testchar cancelled task" in result.stdout
            mock_api.assert_called_once()

    def test_list_tasks_success(self, runner, stub_api):
        """Test successful list tasks command."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            # Mock task
            mock_task = Mock()
            mock_task.code = "kill_monsters"
            mock_task.type = "combat"
            mock_task.level = 5
            mock_task.skill = "combat"
            mock_task.rewards = [Mock(code="gold", quantity=100)]

            mock_data = Mock()
            mock_data.data = [mock_task]

            mock_api.return_value = api_response(mock_data)

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            mock_api.assert_called_once()
            assert "kill_monsters" in result.stdout

    def test_list_tasks_missing_fields_render_marker(self, runner, stub_api):
        """Test list tasks renders the MISSING marker when API task fields are absent."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            mock_task = Mock()
            mock_task.code = None
            mock_task.type = None
            mock_task.level = None
            mock_task.skill = None
            mock_task.rewards = [Mock(code="gold", quantity=None)]

            mock_data = Mock()
            mock_data.data = [mock_task]

            mock_api.return_value = api_response(mock_data)

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "—" in result.stdout

    def test_list_tasks_with_filters(self, runner, stub_api):
        """Test list tasks command with filters."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            mock_api.return_value = api_response(Mock(data=[]))

            result = runner.invoke(app, ["list", "--task-type", "monsters", "--skill", "mining", "--level", "5"])

            assert result.exit_code == 0
            mock_api.assert_called_once()

    def test_list_tasks_empty(self, runner, stub_api):
        """Test list tasks with no tasks."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            mock_api.return_value = api_response(Mock(data=[]))

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0
            assert "No tasks found" in result.stdout

    def test_task_validation_error(self, runner):
        """Test task commands with invalid character name."""
        result = runner.invoke(app, ["new", ""])
        assert result.exit_code == 1

    def test_api_error_handling(self, runner, stub_api):
        """Test API error handling in task commands."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["new", "testchar"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout

    def test_task_status_success(self, runner, stub_api):
        """Test successful task status command."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api:
            # Mock character with task
            mock_character = Mock()
            mock_character.task = "chicken"
            mock_character.task_type = "monsters"
            mock_character.task_progress = 3
            mock_character.task_total = 153

            mock_api.return_value = api_response(mock_character)

            with patch("artifactsmmo_api_client.api.tasks.get_task_tasks_list_code_get.sync") as mock_task_api:
                mock_task_api.side_effect = unexpected_status(404, "Task not found")

                result = runner.invoke(app, ["status", "testchar"])

                assert result.exit_code == 0
                assert "chicken" in result.stdout
                assert "monsters" in result.stdout
                assert "3/153" in result.stdout
                mock_api.assert_called_once()

    def test_task_status_no_task(self, runner, stub_api):
        """Test task status command when character has no task."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api:
            # Mock character without task
            mock_character = Mock()
            mock_character.task = None

            mock_api.return_value = api_response(mock_character)

            result = runner.invoke(app, ["status", "testchar"])

            assert result.exit_code == 1
            assert "has no active task" in result.stdout
            mock_api.assert_called_once()

    # Error handling tests for all commands
    def test_new_task_error_response(self, runner, stub_api):
        """Test new task command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(489, "Task error")

            result = runner.invoke(app, ["new", "testchar"])

            assert result.exit_code == 1
            assert "Task error" in result.stdout

    def test_new_task_exception_cooldown(self, runner, stub_api):
        """Test new task command exception with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(30)

            result = runner.invoke(app, ["new", "testchar"])

            assert result.exit_code == 1
            assert "cooldown" in result.stdout.lower()

    def test_new_task_location_error(self, runner, stub_api):
        """Test new task command with location error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_accept_new_task_my_name_action_task_new_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(598)

            result = runner.invoke(app, ["new", "testchar"])

            assert result.exit_code == 1
            assert "Wrong location for this action" in result.stdout
            assert "Tasks Master location" in result.stdout

    def test_complete_task_error_response(self, runner, stub_api):
        """Test complete task command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(488, "Complete error")

            result = runner.invoke(app, ["complete", "testchar"])

            assert result.exit_code == 1
            assert "Complete error" in result.stdout

    def test_complete_task_exception_cooldown(self, runner, stub_api):
        """Test complete task command exception with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(45)

            result = runner.invoke(app, ["complete", "testchar"])

            assert result.exit_code == 1
            assert "cooldown" in result.stdout.lower()

    def test_complete_task_location_error(self, runner, stub_api):
        """Test complete task command with location error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_complete_task_my_name_action_task_complete_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(598)

            result = runner.invoke(app, ["complete", "testchar"])

            assert result.exit_code == 1
            assert "content not found at this location" in result.stdout
            assert "Tasks Master location" in result.stdout

    def test_exchange_task_error_response(self, runner, stub_api):
        """Test exchange task command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(478, "Exchange error")

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 1
            assert "Exchange error" in result.stdout

    def test_exchange_task_exception_cooldown(self, runner, stub_api):
        """Test exchange task command exception with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(60)

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 1
            assert "cooldown" in result.stdout.lower()

    def test_exchange_task_location_error(self, runner, stub_api):
        """Test exchange task command with location error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_exchange_my_name_action_task_exchange_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(598)

            result = runner.invoke(app, ["exchange", "testchar"])

            assert result.exit_code == 1
            assert "Wrong location for this action" in result.stdout
            assert "Tasks Master location" in result.stdout

    def test_trade_task_error_response(self, runner, stub_api):
        """Test trade task command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(474, "Trade error")

            result = runner.invoke(app, ["trade", "testchar", "copper_ore", "--quantity", "5"])

            assert result.exit_code == 1
            assert "Trade error" in result.stdout

    def test_trade_task_exception_cooldown(self, runner, stub_api):
        """Test trade task command exception with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(20)

            result = runner.invoke(app, ["trade", "testchar", "copper_ore"])

            assert result.exit_code == 1
            assert "cooldown" in result.stdout.lower()

    def test_trade_task_location_error(self, runner, stub_api):
        """Test trade task command with location error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_trade_my_name_action_task_trade_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(598)

            result = runner.invoke(app, ["trade", "testchar", "copper_ore"])

            assert result.exit_code == 1
            assert "content not found at this location" in result.stdout
            assert "Tasks Master location" in result.stdout

    def test_cancel_task_error_response(self, runner, stub_api):
        """Test cancel task command with error response."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_cancel_my_name_action_task_cancel_post.sync"
        ) as mock_api:
            mock_api.return_value = api_error(487, "Cancel error")

            result = runner.invoke(app, ["cancel", "testchar"])

            assert result.exit_code == 1
            assert "Cancel error" in result.stdout

    def test_cancel_task_exception_cooldown(self, runner, stub_api):
        """Test cancel task command exception with cooldown."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_cancel_my_name_action_task_cancel_post.sync"
        ) as mock_api:
            mock_api.side_effect = cooldown_status(15)

            result = runner.invoke(app, ["cancel", "testchar"])

            assert result.exit_code == 1
            assert "cooldown" in result.stdout.lower()

    def test_cancel_task_location_error(self, runner, stub_api):
        """Test cancel task command with location error."""
        with patch(
            "artifactsmmo_api_client.api.my_characters.action_task_cancel_my_name_action_task_cancel_post.sync"
        ) as mock_api:
            mock_api.side_effect = unexpected_status(598)

            result = runner.invoke(app, ["cancel", "testchar"])

            assert result.exit_code == 1
            assert "Wrong location for this action" in result.stdout
            assert "Tasks Master location" in result.stdout

    def test_task_status_with_details_and_rewards(self, runner, stub_api):
        """Test task status command with task details and rewards."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_char_api:
            # Mock character with task
            mock_character = Mock()
            mock_character.task = "chicken"
            mock_character.task_type = "monsters"
            mock_character.task_progress = 3
            mock_character.task_total = 153

            mock_char_api.return_value = api_response(mock_character)

            # Mock task details API
            with patch("artifactsmmo_api_client.api.tasks.get_task_tasks_list_code_get.sync") as mock_task_api:
                mock_task_details = Mock()
                mock_task_details.skill = "combat"
                mock_task_details.level = 5
                mock_task_details.description = "Kill chickens"

                # Mock rewards
                mock_reward = Mock()
                mock_reward.code = "gold"
                mock_reward.quantity = 100
                mock_task_details.rewards = [mock_reward]

                mock_task_api.return_value = api_response(mock_task_details)

                result = runner.invoke(app, ["status", "testchar"])

                assert result.exit_code == 0
                assert "chicken" in result.stdout
                assert "combat" in result.stdout
                assert "Kill chickens" in result.stdout
                assert "gold" in result.stdout
                assert "100" in result.stdout

    def test_task_status_missing_fields_render_marker(self, runner, stub_api):
        """Test task status renders the MISSING marker when API task fields are absent."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api:
            mock_character = Mock()
            mock_character.task = "chicken"
            mock_character.task_type = None
            mock_character.task_progress = None
            mock_character.task_total = None

            mock_api.return_value = api_response(mock_character)

            with patch("artifactsmmo_api_client.api.tasks.get_task_tasks_list_code_get.sync") as mock_task_api:
                mock_task_api.side_effect = unexpected_status(404, "Task not found")

                result = runner.invoke(app, ["status", "testchar"])

                assert result.exit_code == 0
                assert "chicken" in result.stdout
                assert "—" in result.stdout

    def test_task_status_character_not_found(self, runner, stub_api):
        """Test task status command when character is not found."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api:
            mock_api.return_value = api_error(498, "Character not found")

            result = runner.invoke(app, ["status", "testchar"])

            assert result.exit_code == 1
            assert "Character not found" in result.stdout

    def test_task_status_exception_handling(self, runner, stub_api):
        """Test task status command exception handling."""
        with patch("artifactsmmo_api_client.api.characters.get_character_characters_name_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["status", "testchar"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout

    def test_list_tasks_invalid_skill(self, runner, stub_api):
        """Test list tasks command with invalid skill."""
        result = runner.invoke(app, ["list", "--skill", "invalid_skill"])

        assert result.exit_code == 1
        assert "Invalid skill: invalid_skill" in result.stdout

    def test_list_tasks_invalid_task_type(self, runner, stub_api):
        """Test list tasks command with invalid task type."""
        result = runner.invoke(app, ["list", "--task-type", "invalid_type"])

        assert result.exit_code == 1
        assert "Invalid task type: invalid_type" in result.stdout

    def test_list_tasks_api_error(self, runner, stub_api):
        """Test list tasks command with API error."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            mock_api.return_value = api_error(500, "API Error")

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 0  # List command doesn't exit with error code
            assert "API Error" in result.stdout

    def test_list_tasks_exception_handling(self, runner, stub_api):
        """Test list tasks command exception handling."""
        with patch("artifactsmmo_api_client.api.tasks.get_all_tasks_tasks_list_get.sync") as mock_api:
            mock_api.side_effect = unexpected_status(500, "API Error")

            result = runner.invoke(app, ["list"])

            assert result.exit_code == 1
            assert "API Error" in result.stdout
