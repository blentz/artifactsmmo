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


def test_fetch_effects_paginates_full_then_short(monkeypatch):
    """Cover lines 1555-1558: extend, len<100 break, page += 1 in _fetch_effects."""
    page1 = MagicMock()
    page1.data = [_effect(f"eff{i}", f"Effect{i}") for i in range(100)]
    page2 = MagicMock()
    page2.data = [_effect("extra", "Extra")]

    calls = []

    def mock_get_all_effects(**kwargs):
        calls.append(kwargs.get("page"))
        return page1 if kwargs.get("page") == 1 else page2

    monkeypatch.setattr("artifactsmmo_cli.ai.game_data.get_all_effects", mock_get_all_effects)
    gd = GameData()
    result = gd._fetch_effects(MagicMock())
    assert len(result) == 101
    assert calls == [1, 2]
