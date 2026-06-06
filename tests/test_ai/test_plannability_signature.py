"""plannability_signature: the (level, skills) key the doomed-memo invalidates on."""
from artifactsmmo_cli.ai.plannability_signature import plannability_signature
from tests.test_ai.fixtures import make_state


def test_signature_captures_level_and_skills():
    s = make_state(level=4, skills={"weaponcrafting": 2, "mining": 12})
    assert plannability_signature(s) == (4, (("mining", 12), ("weaponcrafting", 2)))


def test_signature_changes_on_level_up():
    a = make_state(level=4, skills={"weaponcrafting": 2})
    b = make_state(level=5, skills={"weaponcrafting": 2})
    assert plannability_signature(a) != plannability_signature(b)


def test_signature_changes_on_skill_up():
    a = make_state(level=4, skills={"weaponcrafting": 2})
    b = make_state(level=4, skills={"weaponcrafting": 3})
    assert plannability_signature(a) != plannability_signature(b)


def test_signature_stable_under_inventory_change():
    a = make_state(level=4, skills={"weaponcrafting": 2}, inventory={"copper_ore": 1})
    b = make_state(level=4, skills={"weaponcrafting": 2}, inventory={"copper_ore": 50})
    assert plannability_signature(a) == plannability_signature(b)
