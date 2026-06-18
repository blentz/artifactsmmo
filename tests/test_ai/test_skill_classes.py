"""Skill classification derives from the API enums + one policy seed, and the
derived sets equal the historical hand-typed literals (no behavior drift)."""

from artifactsmmo_api_client.models.craft_skill import CraftSkill
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill

from artifactsmmo_cli.ai.tiers.skill_classes import (
    COMBAT_CRAFT_SKILLS,
    CONSUMABLE_CRAFT_SKILLS,
    GATHER_SKILLS,
)


def test_sets_equal_the_historical_literals():
    """Value-preserving: the derived partition matches what strategy.py and
    prerequisite_graph.py hard-coded before."""
    assert COMBAT_CRAFT_SKILLS == {"weaponcrafting", "gearcrafting", "jewelrycrafting"}
    assert CONSUMABLE_CRAFT_SKILLS == {"alchemy", "cooking"}
    assert GATHER_SKILLS == {"mining", "woodcutting", "fishing"}


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
    assert COMBAT_CRAFT_SKILLS == craft - gather - CONSUMABLE_CRAFT_SKILLS
