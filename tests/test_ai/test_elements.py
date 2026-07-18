"""ELEMENTS is derived from the API schema, and the re-exports are consistent."""

import attrs
from artifactsmmo_api_client.models.monster_schema import MonsterSchema

from artifactsmmo_cli.ai.elements import ELEMENTS
from artifactsmmo_cli.ai.equipment.elements import ELEMENTS as EQUIPMENT_ELEMENTS


def test_elements_match_schema_attack_fields():
    """The vocabulary is exactly the schema's `attack_<elem>` field suffixes, in
    field-definition order — derived, not hand-typed."""
    expected = tuple(
        f.name[len("attack_"):]
        for f in attrs.fields(MonsterSchema)
        if f.name.startswith("attack_")
    )
    assert expected == ELEMENTS
    assert ELEMENTS == ("fire", "earth", "water", "air")


def test_every_element_has_matching_resistance_field():
    """Each element also has a `res_<elem>` schema field — the scoring loops read
    both, so a mismatch would silently zero a real axis."""
    res_fields = {f.name for f in attrs.fields(MonsterSchema)}
    for elem in ELEMENTS:
        assert f"res_{elem}" in res_fields


def test_equipment_reexport_is_the_single_source():
    """equipment.elements re-exports the one derived tuple (no second copy)."""
    assert EQUIPMENT_ELEMENTS is ELEMENTS
