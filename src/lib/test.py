"""Tests."""
import logging
import random
import string

# from game.account import Account
# from game.characters import Characters
# from game.map.state import MapState


def test_me(client):
    account = Account(name="wakko666", client=client)
    characters = Characters(account=account, client=client)
    logging.info(f"characters: {characters}")

    # char_name = ''.join(random.choice(string.ascii_lowercase) for i in range(10))
    # characters.create(char_name)

    # char_name = 'xivhlnsodv'
    # characters.get(char_name)
    # characters.delete(char_name)

    # mapstate = MapState(client=client)
    # mapstate.scan_around(origin=(0,0), radius=1)
    # mapstate.save()
