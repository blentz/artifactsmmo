"""The root-group classifier: which branch of the root walk produced this root."""

import pytest

from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachCharLevel, ReachSkillLevel
from artifactsmmo_cli.ai.tiers.root_group import ROOT_GROUPS, root_group_of


def test_guard_wins_over_every_root() -> None:
    # A selected guard preempted the walk, so whatever root was resolved did not run.
    assert root_group_of("RestoreHP", ReachCharLevel(level=30), None, None) == "guard"


def test_trunk() -> None:
    assert root_group_of(None, ReachCharLevel(level=30), None, None) == "trunk"


def test_skill_gate_is_a_blocked_gear_target() -> None:
    root = ReachSkillLevel(skill="weaponcrafting", level=15)
    assert root_group_of(None, root, "iron_sword", None) == "skill_gate"


def test_orphan_skill_has_no_blocked_target() -> None:
    root = ReachSkillLevel(skill="cooking", level=12)
    assert root_group_of(None, root, None, None) == "orphan_skill"


def test_gear_is_every_other_resolved_root() -> None:
    assert root_group_of(None, ObtainItem(code="copper_boots"), None, None) == "gear"


def test_no_root_resolved() -> None:
    assert root_group_of(None, None, None, None) == "none"


def test_a_promoted_gear_pick_is_grouped_as_gear_not_as_the_trunk() -> None:
    """Servability promotion walks the tree's pick to the trunk sitting at
    fallback index 0 (live 2026-07-27: 9 of 15 cycles logged `ReachCharLevel`
    when the tree had chosen GEAR every time). The census exists to measure
    whether the trunk-first ordering costs anything, so counting a promoted
    cycle as the trunk winning states the opposite of what happened."""
    assert root_group_of(None, ReachCharLevel(level=30), None,
                         ObtainItem(code="copper_boots")) == "gear"


def test_a_promoted_pick_pairs_blocked_target_with_the_walks_own_root() -> None:
    """`decide_tree` publishes `blocked_target` even when promotion moved the
    root — deliberately, because fleet demand is a fact about what this
    character cannot make. Grouping on the FINAL root would then label a
    promoted orphan `ReachSkillLevel` a `skill_gate` on a gate belonging to a
    different root. Grouping on the walk's own pick keeps gate and root paired,
    because both come from the same `RootResolution`."""
    promoted_to = ReachSkillLevel(skill="cooking", level=12)
    # The walk's own pick was the gear target whose crafting gate set
    # `blocked_target`; promotion left an orphan-looking skill root running.
    assert root_group_of(None, promoted_to, "iron_sword",
                         ObtainItem(code="iron_sword")) == "gear"


def test_a_selected_guard_beats_even_a_promoted_pick() -> None:
    assert root_group_of("DepositInventory", ReachCharLevel(level=30), None,
                         ObtainItem(code="copper_boots")) == "guard"


@pytest.mark.parametrize("guard,root,blocked,promoted", [
    ("RestoreHP", None, None, None),
    (None, ReachCharLevel(level=30), None, None),
    (None, ReachSkillLevel(skill="cooking", level=2), "x", None),
    (None, ReachSkillLevel(skill="cooking", level=2), None, None),
    (None, ObtainItem(code="copper_boots"), None, None),
    (None, None, None, None),
    (None, ReachCharLevel(level=30), None, ObtainItem(code="copper_boots")),
])
def test_every_returned_label_is_declared(guard, root, blocked, promoted) -> None:
    # The census groups on ROOT_GROUPS; a label outside it would be counted nowhere.
    assert root_group_of(guard, root, blocked, promoted) in ROOT_GROUPS


def test_the_declared_set_is_exactly_what_is_reachable() -> None:
    reachable = {
        root_group_of("RestoreHP", None, None, None),
        root_group_of(None, ReachCharLevel(level=30), None, None),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), "x", None),
        root_group_of(None, ReachSkillLevel(skill="cooking", level=2), None, None),
        root_group_of(None, ObtainItem(code="copper_boots"), None, None),
        root_group_of(None, None, None, None),
    }
    assert reachable == ROOT_GROUPS
