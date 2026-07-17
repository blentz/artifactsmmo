"""short_root: collapse ObtainItem(...) reprs to a scannable short form."""

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.tui.plan_format import grind_chain_lines, short_root


def test_obtain_quantity_one_drops_quantity():
    assert short_root("ObtainItem(code='copper_boots', quantity=1)") == "copper_boots"


def test_obtain_quantity_many_keeps_count():
    assert short_root("ObtainItem(code='copper_bar', quantity=8)") == "8x copper_bar"


def test_non_obtain_root_unchanged():
    assert short_root("ReachCharLevel(level=6)") == "ReachCharLevel(level=6)"


def _leg(label, children=()):
    return PlanTreeNode(key=label, label=label, kind="obtain", status="current",
                        children=children)


def test_grind_chain_lines_empty():
    assert grind_chain_lines(()) == []


def test_grind_chain_lines_one_per_leg():
    lines = grind_chain_lines((_leg("GatherAsh()"), _leg("CraftPlank()")))
    assert len(lines) == 2
    assert "GatherAsh()" in lines[0] and "CraftPlank()" in lines[1]


def test_grind_chain_lines_nests_children_deeper():
    nodes = (_leg("grind fishing", children=(_leg("GatherOak()"),)),)
    lines = grind_chain_lines(nodes)
    assert len(lines) == 2
    # the child line is indented further than its parent
    assert lines[1].index("GatherOak") > lines[0].index("grind fishing")
