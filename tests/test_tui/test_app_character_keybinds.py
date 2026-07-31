"""The focus keys are labelled with the character they select.

The roster strip in the status pane spent a line naming every character, which
duplicated what the key legend at the bottom of the screen could say for free:
the legend showed "Char 1".."Char 5", a number the operator already pressed and
a name they could not see. The names live in the legend now, one key per
character actually in the roster — so the strip no longer has to list them, and
a slot with no character behind it is not offered at all.
"""

from textual.widgets._footer import FooterKey

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.app import WatchApp


def _app(*characters: str) -> WatchApp:
    return WatchApp(characters=list(characters), game_data=GameData())


def test_each_character_key_is_labelled_with_that_characters_name():
    app = _app("alice", "bob")

    assert app._bindings.get_bindings_for_key("1")[0].description == "alice"
    assert app._bindings.get_bindings_for_key("2")[0].description == "bob"


def test_each_character_key_still_focuses_its_own_slot():
    """The label is cosmetic; the action behind each key must still be the slot
    that key has always meant."""
    app = _app("alice", "bob")

    assert app._bindings.get_bindings_for_key("2")[0].action == "focus_character(2)"


def test_no_key_is_offered_for_a_slot_with_no_character():
    """Five keys were bound unconditionally, so a two-character run advertised
    'Char 3'..'Char 5' — keys that could only ever do nothing."""
    app = _app("alice", "bob")

    assert "3" not in app._bindings.key_to_bindings


def test_a_single_character_run_binds_no_focus_keys_at_all():
    """Single-character play must look exactly as it did before multi-character
    support: there is nothing to switch to."""
    app = _app("alice")

    assert "1" not in app._bindings.key_to_bindings


async def test_the_footer_shows_the_character_names():
    """End to end: the names have to reach the rendered key legend, not just
    the bindings map."""
    app = _app("alice", "bob")
    async with app.run_test(size=(120, 50)) as pilot:
        await pilot.pause()
        shown = {key.description for key in app.query(FooterKey)}

        assert {"alice", "bob"} <= shown
        assert not any(d.startswith("Char ") for d in shown)
