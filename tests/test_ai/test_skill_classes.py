"""Skill classification derives from the API enums + one policy seed, and the
derived sets equal the historical hand-typed literals (no behavior drift)."""

from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill

from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)
from artifactsmmo_cli.ai.world_state import SKILL_NAMES


def test_skill_names_is_the_derived_schema_vocabulary():
    """SKILL_NAMES = CraftSkill ∪ GatheringSkill (the 8 trainable skills), derived
    not hand-typed, and still the historical membership (combat excluded)."""
    expected = {s.value for s in CraftSkill} | {s.value for s in GatheringSkill}
    assert set(SKILL_NAMES) == expected
    assert set(SKILL_NAMES) == {
        "mining", "woodcutting", "fishing", "weaponcrafting",
        "gearcrafting", "jewelrycrafting", "cooking", "alchemy",
    }
    assert "combat" not in SKILL_NAMES  # combat xp is tracked separately
    assert sorted(SKILL_NAMES) == SKILL_NAMES  # deterministic order
    assert len(SKILL_NAMES) == len(set(SKILL_NAMES))  # no dupes


def test_sets_equal_the_historical_literals():
    """Value-preserving: the derived partition matches what strategy.py and
    prerequisite_graph.py hard-coded before."""
    assert {"weaponcrafting", "gearcrafting", "jewelrycrafting"} == COMBAT_CRAFT_SKILLS
    assert {"alchemy", "cooking"} == CONSUMABLE_CRAFT_SKILLS
    assert {"mining", "woodcutting", "fishing"} == GATHER_SKILLS


def test_partition_is_disjoint_and_drawn_from_the_enums():
    """The three classes are disjoint and every member is a real schema skill."""
    craft = {s.value for s in CraftSkill}
    gather = {s.value for s in GatheringSkill}
    vocab = craft | gather
    assert COMBAT_CRAFT_SKILLS.isdisjoint(GATHER_SKILLS)
    assert COMBAT_CRAFT_SKILLS.isdisjoint(CONSUMABLE_CRAFT_SKILLS)
    assert GATHER_SKILLS.isdisjoint(CONSUMABLE_CRAFT_SKILLS)
    for s in COMBAT_CRAFT_SKILLS | CONSUMABLE_CRAFT_SKILLS | GATHER_SKILLS:
        assert s in vocab


def test_combat_craft_is_craft_minus_gather_minus_kitchen():
    """The combat set is pure set algebra over the enums + the kitchen seed —
    no independent membership list to drift."""
    craft = {s.value for s in CraftSkill}
    gather = {s.value for s in GatheringSkill}
    assert craft - gather - CONSUMABLE_CRAFT_SKILLS == COMBAT_CRAFT_SKILLS
