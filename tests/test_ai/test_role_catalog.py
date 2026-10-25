import pytest

from artifactsmmo_cli.ai.role_catalog import (
    ROLE_CATALOG,
    ROLES_BY_NAME,
    Role,
    role_skill_level,
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
    # `in GATHERING_SKILLS` True sub-branch (no raise) — distinct from the
    # gatherless (None) path and the unknown-skill (raise) path.
    validate_catalog((Role(name="fisher", gather="fishing", craft="cooking"),))


def test_craft_only_skill_declared_as_gather_is_rejected() -> None:
    # "cooking" is a real CraftSkill but NOT a GatheringSkill. Validating
    # against the raw GATHERING_SKILLS vocabulary (rather than the
    # ranking-prior partition, which folds cooking into
    # CONSUMABLE_CRAFT_SKILLS and would wrongly accept it here) must reject
    # this. Regression test for the reviewer-found mirror defect.
    bad = (Role(name="ghost", gather="cooking", craft="weaponcrafting"),)
    with pytest.raises(ValueError, match="cooking"):
        validate_catalog(bad)


def test_gather_only_skill_declared_as_craft_is_rejected() -> None:
    # "fishing" is a real GatheringSkill but NOT a CraftSkill. Validating
    # against the raw CRAFT_SKILLS vocabulary (rather than the partition,
    # which folds fishing into GATHER_SKILLS and would wrongly accept it
    # here) must reject this. Regression test for the originally-shipped
    # defect this brief's Step 3 code contained.
    bad = (Role(name="ghost", gather="mining", craft="fishing"),)
    with pytest.raises(ValueError, match="fishing"):
        validate_catalog(bad)


def test_mining_is_accepted_in_both_gather_and_craft_slots() -> None:
    # `mining` is a member of BOTH raw enums (extraction AND a craft step) —
    # that overlap is a real schema property, not an error, and must keep
    # validating in either slot.
    validate_catalog((Role(name="miner", gather="mining", craft="mining"),))


def test_woodcutting_is_accepted_in_both_gather_and_craft_slots() -> None:
    validate_catalog((Role(name="logger", gather="woodcutting", craft="woodcutting"),))


# --- ROLES_BY_NAME / role_skill_level (level-aware claiming, 2026-08-02) ---


def test_roles_by_name_indexes_the_whole_catalog() -> None:
    assert set(ROLES_BY_NAME) == {r.name for r in ROLE_CATALOG}
    assert all(ROLES_BY_NAME[r.name] is r for r in ROLE_CATALOG)


def test_role_skill_level_takes_the_best_of_the_owned_skills() -> None:
    # miner owns {mining, weaponcrafting}: the deeper of the two is what makes
    # the character suited to the role, so max, not min or mean.
    role = Role(name="miner", gather="mining", craft="weaponcrafting")
    assert role_skill_level(role, {"mining": 21, "weaponcrafting": 3}) == 21
    assert role_skill_level(role, {"mining": 3, "weaponcrafting": 21}) == 21


def test_role_skill_level_reads_a_missing_skill_as_zero() -> None:
    # Absence is "no reading", NOT the API's level-1 floor: an unknown skill
    # must not look identical to a genuinely untrained one.
    role = Role(name="miner", gather="mining", craft="weaponcrafting")
    assert role_skill_level(role, {"mining": 4}) == 4
    assert role_skill_level(role, {}) == 0


def test_role_skill_level_handles_the_collapsed_alchemist_role() -> None:
    # gather == craft collapses `role_skills` to ONE entry; the max must still
    # be well-formed over a single-element set.
    role = Role(name="alchemist", gather="alchemy", craft="alchemy")
    assert role_skill_level(role, {"alchemy": 7}) == 7
