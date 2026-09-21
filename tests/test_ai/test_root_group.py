"""The root-group classifier: which branch of the root walk produced this root."""

import pytest

from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS, root_group_of


def test_guard_wins_over_every_root() -> None:
    # A guard preempted the walk, so whatever root was resolved did not run.
    assert root_group_of("HP_CRITICAL", ReachCharLevel(level=30), None) == "guard"


def test_trunk() -> None:
    assert root_group_of(None, ReachCharLevel(level=30), None) == "trunk"


def test_skill_gate_is_a_blocked_gear_target() -> None:
    root = ReachSkillLevel(skill="weaponcrafting", level=15)
    assert root_group_of(None, root, "iron_sword") == "skill_gate"


def test_orphan_skill_has_no_blocked_target() -> None:
    root = ReachSkillLevel(skill="cooking", level=12)
    assert root_group_of(None, root, None) == "orphan_skill"


def test_gear_is_every_other_resolved_root() -> None:
    assert root_group_of(None, ObtainItem(code="copper_boots"), None) == "gear"


def test_no_root_resolved() -> None:
    assert root_group_of(None, None, None) == "none"


@pytest.mark.parametrize("interrupt,root,blocked", [
    ("HP_CRITICAL", None, None),
    (None, ReachCharLevel(level=30), None),
    (None, ReachSkillLevel(skill="cooking", level=2), "x"),
    (None, ReachSkillLevel(skill="cooking", level=2), None),
    (None, ObtainItem(code="copper_boots"), None),
    (None, None, None),
])
def test_every_returned_label_is_declared(interrupt, root, blocked) -> None:
    # The census groups on ROOT_GROUPS; a label outside it would be counted nowhere.
    assert root_group_of(interrupt, root, blocked) in ROOT_GROUPS


def test_the_declared_set_is_exactly_what_is_reachable() -> None:
    reachable = {
        root_group_of("HP_CRITICAL", None, None),
        root_group_of(None, ReachCharLevel(level=30), None),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), "x"),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), None),
        root_group_of(None, ObtainItem(code="copper_boots"), None),
        root_group_of(None, None, None),
    }
    assert reachable == ROOT_GROUPS
