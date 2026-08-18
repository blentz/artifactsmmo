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
    """ON STDERR, deliberately (2026-08-18). Loading game data is a side effect of
    every CLI command, including read-only ones whose STDOUT is a machine-readable
    payload (`objective --json`). A warning on stdout there is a parse error in the
    consumer, not a warning. Asserting the STREAM and not just the text is what
    keeps that from silently regressing."""
    _gd({"poison": "Poison", "newfx": "New"}, {"poison"})._audit_effect_coverage()
    captured = capsys.readouterr()
    assert "newfx" in captured.err and "defined but on no current entity" in captured.err
    assert captured.out == ""


def test_seen_code_missing_from_registry_warns(capsys):
    """Same stream contract as the latent-code warning above."""
    _gd({"poison": "Poison"}, {"poison", "ghost"})._audit_effect_coverage()
    captured = capsys.readouterr()
    assert "ghost" in captured.err
    assert captured.out == ""


def test_fully_covered_registry_is_silent(capsys):
    # A "fully coherent" state: registry and seen are identical, and all
    # module-level carveouts appear in the registry too (as they do in
    # production where /effects returns every game effect code, including
    # carved-out ones).  All three audit checks must fire nothing.
    carveouts = _MONSTER_EFFECT_CARVEOUTS | _ITEM_EFFECT_CARVEOUTS | _RUNE_ABILITY_CARVEOUTS
    registry = {"poison": "Poison"} | {c: c for c in carveouts}
    seen = {"poison"} | carveouts
    _gd(registry, seen)._audit_effect_coverage()
    captured = capsys.readouterr()
    # BOTH streams. The warnings moved to stderr on 2026-08-18, so asserting only
    # `out` here would pass vacuously — silence on the stream nothing writes to.
    assert captured.out == ""
    assert captured.err == ""
