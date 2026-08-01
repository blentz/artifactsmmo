import pytest

from artifactsmmo_cli.ai.role_catalog import (
    ROLE_CATALOG,
    Role,
    role_skills,
    validate_catalog,
)
from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)


def test_shipped_catalog_validates() -> None:
    validate_catalog(ROLE_CATALOG)


def test_catalog_covers_every_api_skill_exactly_once() -> None:
    every = GATHER_SKILLS | COMBAT_CRAFT_SKILLS | CONSUMABLE_CRAFT_SKILLS
    owned: list[str] = []
    for role in ROLE_CATALOG:
        owned.extend(sorted(role_skills(role)))
    assert set(owned) == every
    assert len(owned) == len(set(owned)), "a skill is owned by two roles"


def test_role_names_are_unique() -> None:
    names = [r.name for r in ROLE_CATALOG]
    assert len(names) == len(set(names))


def test_unknown_gather_skill_is_rejected() -> None:
    bad = (Role(name="ghost", gather="mythweaving", craft="weaponcrafting"),)
    with pytest.raises(ValueError, match="mythweaving"):
        validate_catalog(bad)


def test_unknown_craft_skill_is_rejected() -> None:
    bad = (Role(name="ghost", gather="mining", craft="mythsmithing"),)
    with pytest.raises(ValueError, match="mythsmithing"):
        validate_catalog(bad)


def test_gatherless_role_is_allowed() -> None:
    validate_catalog((Role(name="jeweler", gather=None, craft="jewelrycrafting"),))


def test_role_skills_collapses_when_gather_equals_craft() -> None:
    role = Role(name="alchemist", gather="alchemy", craft="alchemy")
    assert role_skills(role) == frozenset({"alchemy"})


def test_role_skills_gatherless_role_returns_craft_only() -> None:
    role = Role(name="jeweler", gather=None, craft="jewelrycrafting")
    assert role_skills(role) == frozenset({"jewelrycrafting"})


def test_role_skills_returns_both_when_distinct() -> None:
    role = Role(name="miner", gather="mining", craft="weaponcrafting")
    assert role_skills(role) == frozenset({"mining", "weaponcrafting"})


def test_role_is_frozen() -> None:
    role = Role(name="miner", gather="mining", craft="weaponcrafting")
    with pytest.raises(AttributeError):
        role.name = "other"  # type: ignore[misc]


def test_valid_gather_skill_passes_without_raising() -> None:
    # Exercises the `role.gather is not None` True branch combined with the
    # `in valid_gather` True sub-branch (no raise) — distinct from the
    # gatherless (None) path and the unknown-skill (raise) path.
    validate_catalog((Role(name="fisher", gather="fishing", craft="cooking"),))
