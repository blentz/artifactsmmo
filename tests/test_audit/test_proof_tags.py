import pytest
from artifactsmmo_cli.audit.proof_tags import ProofTags, parse_tags, build_index, cross_check


def test_parse_tags_extracts_concepts_and_properties():
    text = "-- @concept: combat, monsters @property: safety, dominance\nimport Foo\n"
    tags = parse_tags(text)
    assert tags == ProofTags(concepts=["combat", "monsters"], properties=["safety", "dominance"])


def test_parse_tags_missing_returns_none():
    assert parse_tags("import Foo\ntheorem t : True := trivial\n") is None


def test_parse_tags_rejects_unknown_property():
    with pytest.raises(ValueError, match="unknown property"):
        parse_tags("-- @concept: combat @property: optimality\n")


def test_build_index_rows_sorted_by_module():
    mods = {"Beta": ProofTags(["tasks"], ["safety"]), "Alpha": ProofTags(["bank"], ["totality"])}
    rows = build_index(mods)
    assert [r.module for r in rows] == ["Alpha", "Beta"]
    assert rows[0].concepts == ["bank"]


def test_cross_check_flags_manifest_module_without_tags():
    # Manifest references Gamma but Gamma has no tags ⇒ error listing Gamma.
    errors = cross_check(tagged={"Alpha"}, manifest_modules={"Alpha", "Gamma"})
    assert any("Gamma" in e for e in errors)


def test_cross_check_clean_when_all_tagged():
    assert cross_check(tagged={"Alpha", "Gamma"}, manifest_modules={"Alpha", "Gamma"}) == []
