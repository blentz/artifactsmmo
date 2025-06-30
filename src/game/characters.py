""" Character module """

import json
import logging

from artifactsmmo_api_client.api.accounts.get_account_characters_accounts_account_characters_get import sync as account_sync
from artifactsmmo_api_client.api.characters.create_character_characters_create_post import sync as create_character
from artifactsmmo_api_client.api.characters.delete_character_characters_delete_post import sync as delete_character
from artifactsmmo_api_client.api.characters.get_character_characters_name_get import sync as get_character
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.character_skin import CharacterSkin
from artifactsmmo_api_client.models.add_character_schema import AddCharacterSchema
from artifactsmmo_api_client.models.delete_character_schema import DeleteCharacterSchema

from src.game.character.state import CharacterState

class Characters:
    """ Character class """

    _characters = []
    _account = None

    def __init__(self, account, client):
        self._account = account
        self._client = client
        self._sync()

    def __repr__(self):
        return self._characters

    def __str__(self):
        return str(self._characters)

    def __getitem__(self, idx):
        return self._characters[idx]

    def __iter__(self):
        return self._characters.__iter__()

    def __len__(self):
        return len(self._characters)

    def __contains__(self, item):
        return self._characters.__contains__(item)

    def _sync(self):
        """ Sync characters list. """
        characters = account_sync(account=self._account.name, client=self._client).data
        self._characters = [CharacterState(name=char.name, data=char.to_dict()) for char in characters]
        logging.debug(f"account: {self._account.name}, characters: {self._characters}")

    def create(self, name):
        """ Create a character. """
        schema = AddCharacterSchema(name=name, skin=CharacterSkin.MEN1) #FIXME: randomize
        response = None
        try:
            response = create_character(body=schema, client=self._client)
            logging.info(f"create character response: {response}")
            self._sync()
        except UnexpectedStatus as exc:
            parsed = json.loads(exc.content.decode(errors='ignore'))
            logging.error(f"error creating character: {parsed['error']['message']} ({exc.status_code})")
        return response

    def delete(self, name):
        """ Delete a character. """
        schema = DeleteCharacterSchema(name=name)
        response = None
        try:
            response = delete_character(body=schema, client=self._client)
            logging.debug(f"delete character response: {response}")
            self._sync()
        except UnexpectedStatus as exc:
            parsed = json.loads(exc.content.decode(errors='ignore'))
            logging.error(f"error deleting character: {parsed['error']['message']} ({exc.status_code})")
        return response

    def get(self, name):
        """ Get a character. """
        for char in self._characters:
            if char and char.name:
                logging.debug(f"character: {char}")
                return char
        response = get_character(name, client=self._client)
        logging.debug(f"get character response: {response}")
        return response
