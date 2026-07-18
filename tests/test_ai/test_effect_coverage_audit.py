from artifactsmmo_cli.ai.game_data import (
    _ITEM_EFFECT_CARVEOUTS,
    _MONSTER_EFFECT_CARVEOUTS,
    _RUNE_ABILITY_CARVEOUTS,
    GameData,
)


def _gd(registry, seen):
    gd = GameData()
    gd._effect_registry = registry
    gd._seen_effect_codes = set(seen)
    return gd


def test_latent_code_defined_but_unseen_warns(capsys):
    _gd({"poison": "Poison", "newfx": "New"}, {"poison"})._audit_effect_coverage()
    out = capsys.readouterr().out
    assert "newfx" in out and "defined but on no current entity" in out


def test_seen_code_missing_from_registry_warns(capsys):
    _gd({"poison": "Poison"}, {"poison", "ghost"})._audit_effect_coverage()
    assert "ghost" in capsys.readouterr().out


def test_fully_covered_registry_is_silent(capsys):
    # A "fully coherent" state: registry and seen are identical, and all
    # module-level carveouts appear in the registry too (as they do in
    # production where /effects returns every game effect code, including
    # carved-out ones).  All three audit checks must fire nothing.
    carveouts = _MONSTER_EFFECT_CARVEOUTS | _ITEM_EFFECT_CARVEOUTS | _RUNE_ABILITY_CARVEOUTS
    registry = {"poison": "Poison"} | {c: c for c in carveouts}
    seen = {"poison"} | carveouts
    _gd(registry, seen)._audit_effect_coverage()
    assert capsys.readouterr().out == ""
