from unittest.mock import MagicMock

from artifactsmmo_cli.ai.game_data import GameData


def _effect(code, name):
    e = MagicMock()
    e.code, e.name = code, name
    return e


def test_build_effects_indexes_registry_by_code():
    gd = GameData()
    gd._build_effects([_effect("poison", "Poison"), _effect("lifesteal", "Lifesteal")])
    assert gd._effect_registry == {"poison": "Poison", "lifesteal": "Lifesteal"}
