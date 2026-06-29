"""The item-effect coverage guard fails loudly on an unknown equippable effect."""

import pytest

from artifactsmmo_cli.ai.game_data import GameData, _RUNE_ABILITY_CARVEOUTS
from artifactsmmo_cli.ai.game_data_error import GameDataCoverageError


def _item(code, type_, effect_codes):
    """Minimal stand-in matching the attrs ItemSchema surface _build_items reads."""
    class _Eff:
        def __init__(self, c):
            self.code = c
            self.value = 1
    class _Item:
        pass
    it = _Item()
    it.code = code
    it.type_ = type_
    it.subtype = ""
    it.level = 1
    it.effects = [_Eff(c) for c in effect_codes]
    it.craft = None
    it.conditions = []
    it.tradeable = True
    return it


def test_unknown_equippable_effect_raises():
    gd = GameData()
    with pytest.raises(GameDataCoverageError) as exc:
        gd._build_items([_item("mystery_ring", "ring", ["totally_new_code"])])
    assert "mystery_ring" in str(exc.value)
    assert "totally_new_code" in str(exc.value)


def test_deferred_rune_ability_is_carved_not_fatal():
    gd = GameData()
    # burn/frenzy/etc. are intentionally carved — must NOT raise.
    gd._build_items([_item("burn_rune", "rune", ["burn", "lifesteal"])])
    assert gd.item_stats("burn_rune") is not None


def test_all_carved_rune_abilities_ingest_without_coverage_error():
    # All 9 player-side rune ability carve-outs ingest on an equippable `rune`
    # without tripping GameDataCoverageError (the carve is intentional + complete).
    assert len(_RUNE_ABILITY_CARVEOUTS) == 9
    gd = GameData()
    items = [
        _item(f"{code}_rune", "rune", [code]) for code in sorted(_RUNE_ABILITY_CARVEOUTS)
    ]
    gd._build_items(items)  # must not raise
    for code in _RUNE_ABILITY_CARVEOUTS:
        assert gd.item_stats(f"{code}_rune") is not None


def test_unknown_effect_on_nonequippable_is_ignored():
    gd = GameData()
    # resources/consumables outside the equippable types keep today's silent-drop.
    gd._build_items([_item("weird_resource", "resource", ["totally_new_code"])])
    assert gd.item_stats("weird_resource") is not None
