"""CharacterRoster: stable slot, colour, and sprite per character."""

import pytest

from artifactsmmo_cli.tui.character_roster import ROSTER_COLORS, CharacterRoster
from artifactsmmo_cli.tui.sprites import PLAYER_SPRITE


def test_slots_are_one_based_and_follow_account_order():
    roster = CharacterRoster(["carol", "alice", "bob"])
    assert roster.at(1) == "carol"
    assert roster.at(3) == "bob"
    assert roster.at(4) is None


def test_colors_are_distinct_and_assigned_by_index():
    roster = CharacterRoster(["a", "b", "c", "d", "e"])
    colors = [roster.color(n) for n in roster.names]
    assert colors == list(ROSTER_COLORS)
    assert len(set(colors)) == 5


def test_sprites_share_the_silhouette_but_differ_in_tunic():
    roster = CharacterRoster(["a", "b"])
    first, second = roster.sprite("a"), roster.sprite("b")
    assert first.rows == PLAYER_SPRITE.rows == second.rows
    assert first.palette["b"] != second.palette["b"]


def test_sprite_objects_are_stable_across_calls():
    """MapPane's per-line cache keys on sprite identity; a fresh object every
    frame would defeat it and re-style the whole viewport."""
    roster = CharacterRoster(["a"])
    assert roster.sprite("a") is roster.sprite("a")


def test_more_than_five_characters_is_rejected():
    with pytest.raises(ValueError, match="at most 5"):
        CharacterRoster(["a", "b", "c", "d", "e", "f"])


def test_an_empty_roster_is_rejected():
    with pytest.raises(ValueError, match="at least one"):
        CharacterRoster([])


def test_duplicate_names_are_rejected():
    with pytest.raises(ValueError, match="duplicate"):
        CharacterRoster(["a", "a"])


def test_an_unknown_name_is_an_error():
    with pytest.raises(KeyError):
        CharacterRoster(["a"]).color("b")


def test_index_is_the_zero_based_account_position():
    roster = CharacterRoster(["carol", "alice", "bob"])
    assert roster.index("carol") == 0
    assert roster.index("bob") == 2
