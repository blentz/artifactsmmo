"""grind_leg_nodes: the runtime skill-grind sub-plan rendered as PlanTreeNodes
for the TUI plan tree / log (the whole action chain below a LevelSkill step)."""

from dataclasses import dataclass

from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.ai.grind_expansion import grind_leg_nodes


@dataclass(frozen=True)
class _Leg:
    """Stand-in for a concrete grind action (Move/Gather/Craft) — only its repr
    and non-LevelSkill type matter to the builder."""

    name: str

    def __repr__(self) -> str:
        return f"{self.name}()"


def _ls(skill: str) -> LevelSkill:
    return LevelSkill(skill=skill, target_level=30)


def test_flat_legs_become_leaf_nodes():
    legs = [_Leg("GatherAsh"), _Leg("CraftPlank")]
    nodes = grind_leg_nodes("woodcutting", legs)
    assert [n.label for n in nodes] == ["GatherAsh()", "CraftPlank()"]
    assert all(n.kind == "obtain" for n in nodes)
    assert [n.children for n in nodes] == [(), ()]


def test_first_leg_is_current_rest_unmet():
    legs = [_Leg("GatherAsh"), _Leg("CraftPlank"), _Leg("CraftBow")]
    nodes = grind_leg_nodes("woodcutting", legs)
    assert nodes[0].status == "current"
    assert nodes[1].status == "unmet"
    assert nodes[2].status == "unmet"


def test_empty_legs_return_empty():
    assert grind_leg_nodes("woodcutting", []) == ()


def test_consecutive_duplicate_legs_collapse_with_count():
    legs = [_Leg("GatherAsh")] * 3
    nodes = grind_leg_nodes("woodcutting", legs)
    assert len(nodes) == 1
    assert nodes[0].label == "GatherAsh() ×3"
    assert nodes[0].status == "current"


def test_single_leg_has_no_count_suffix():
    nodes = grind_leg_nodes("woodcutting", [_Leg("GatherAsh")])
    assert nodes[0].label == "GatherAsh()"


def test_collapse_then_distinct_group():
    legs = [_Leg("GatherAsh"), _Leg("GatherAsh"), _Leg("CraftPlank")]
    nodes = grind_leg_nodes("woodcutting", legs)
    assert [n.label for n in nodes] == ["GatherAsh() ×2", "CraftPlank()"]
    assert nodes[0].status == "current" and nodes[1].status == "unmet"


def test_non_adjacent_duplicates_stay_separate():
    # Order matters: a run is only collapsed when contiguous.
    legs = [_Leg("GatherAsh"), _Leg("CraftPlank"), _Leg("GatherAsh")]
    nodes = grind_leg_nodes("woodcutting", legs)
    assert [n.label for n in nodes] == ["GatherAsh()", "CraftPlank()", "GatherAsh()"]


def test_collapsed_group_keys_are_unique():
    legs = [_Leg("GatherAsh"), _Leg("CraftPlank"), _Leg("GatherAsh")]
    nodes = grind_leg_nodes("woodcutting", legs)
    keys = [n.key for n in nodes]
    assert len(set(keys)) == len(keys)


def test_first_leg_levelskill_wraps_nested_children():
    nested = (PlanTreeNode(key="inner", label="GatherOak()", kind="obtain",
                           status="current"),)
    legs = [_ls("woodcutting"), _Leg("CraftPlank")]
    nodes = grind_leg_nodes("gearcrafting", legs, nested)
    wrapper = nodes[0]
    assert wrapper.kind == "step"
    assert "woodcutting" in wrapper.label
    assert wrapper.status == "current"
    assert wrapper.children == nested
    # the trailing craft leg is a plain unmet leaf
    assert nodes[1].kind == "obtain" and nodes[1].status == "unmet"


def test_non_first_levelskill_leg_is_leaf_not_wrapper():
    # Only leg[0] is the one the player recursed into this cycle; a later
    # LevelSkill leg has no captured expansion, so it renders as a leaf.
    nested = (PlanTreeNode(key="inner", label="x", kind="obtain", status="current"),)
    legs = [_Leg("GatherAsh"), _ls("woodcutting")]
    nodes = grind_leg_nodes("gearcrafting", legs, nested)
    assert nodes[1].kind == "obtain"
    assert nodes[1].children == ()
