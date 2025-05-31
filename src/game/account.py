""" Account module """
import logging

from artifactsmmo_api_client.api.accounts.get_account import sync


class Account:
    """ Account class """
    _account = None
    _client = None
    name = None

    def __init__(self, name, client):
        self._account = sync(account=name, client=client)
        self._client = client
        self.name = name
        logging.debug(f"account: {self._account}")

    def __repr__(self):
        return f"Account({self.name})"
