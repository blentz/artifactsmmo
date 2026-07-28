"""APIWrapper access to the character action log (GET /my/logs/{name})."""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.api_wrapper import APIWrapper


class TestGetCharacterLogs:
    def test_delegates_to_the_generated_client(self):
        client = MagicMock()
        wrapper = APIWrapper(client)

        with patch("artifactsmmo_cli.api_wrapper.get_character_logs_sync") as sync:
            wrapper.get_character_logs("Robby", page=2, size=100)

        sync.assert_called_once_with(client=client, name="Robby", page=2, size=100)

    def test_defaults_to_the_first_page(self):
        client = MagicMock()
        wrapper = APIWrapper(client)

        with patch("artifactsmmo_cli.api_wrapper.get_character_logs_sync") as sync:
            wrapper.get_character_logs("Robby")

        sync.assert_called_once_with(client=client, name="Robby", page=1, size=100)

    def test_returns_the_client_result(self):
        client = MagicMock()
        wrapper = APIWrapper(client)
        page = MagicMock()

        with patch("artifactsmmo_cli.api_wrapper.get_character_logs_sync",
                   return_value=page):
            assert wrapper.get_character_logs("Robby") is page
