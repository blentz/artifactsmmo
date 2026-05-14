"""Tests for GameHTTPStatus — ensures game-specific codes don't crash the client."""

import pytest

from artifactsmmo_api_client.types import GameHTTPStatus


class TestGameHTTPStatus:
    def test_standard_code_works(self):
        s = GameHTTPStatus(200)
        assert int(s) == 200

    def test_standard_code_phrase(self):
        assert GameHTTPStatus(200).phrase == "OK"

    def test_game_cooldown_code(self):
        s = GameHTTPStatus(499)
        assert int(s) == 499
        assert "cooldown" in s.phrase.lower()

    def test_game_missing_item_code(self):
        assert int(GameHTTPStatus(478)) == 478
        assert len(GameHTTPStatus(478).phrase) > 5

    def test_game_level_too_low_code(self):
        assert "low" in GameHTTPStatus(493).phrase.lower()

    def test_unknown_code_does_not_crash(self):
        s = GameHTTPStatus(555)
        assert "555" in s.phrase

    def test_is_int_subclass(self):
        assert isinstance(GameHTTPStatus(200), int)
        assert GameHTTPStatus(200) == 200

    def test_repr(self):
        assert repr(GameHTTPStatus(499)) == "GameHTTPStatus(499)"

    @pytest.mark.parametrize("code", [
        461, 462, 471, 472, 473, 478, 479, 486, 487, 488,
        489, 490, 491, 492, 493, 494, 495, 496, 497, 498,
        499, 598, 599,
    ])
    def test_all_game_codes_have_phrase(self, code: int):
        phrase = GameHTTPStatus(code).phrase
        assert len(phrase) > 5
        assert str(code) not in phrase  # not falling back to "Game status NNN"
