"""short_root: collapse ObtainItem(...) reprs to a scannable short form."""

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.tui.plan_format import (
    grind_chain_lines,
    parse_supply_target,
    short_root,
    supply_banked,
    supply_detail,
    supply_progress,
)


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


# ---------------------------------------------------------------------------
# supply target: the sibling demand this character is producing for
# ---------------------------------------------------------------------------

def test_parse_supply_target_round_trips_the_players_repr():
    """The parser's input is whatever `_notify_observer` writes, so the case
    that matters is the real `repr` of the real triple, not a hand-typed
    string."""
    assert parse_supply_target(repr(("ash_wood", 62, 50))) == ("ash_wood", 62, 50)


def test_parse_supply_target_none_for_another_shape():
    """A non-triple string yields None, and the callers then render the cycle
    WITHOUT a supply line rather than showing a partial figure."""
    assert parse_supply_target("ObtainItem(code='ash_wood', quantity=1)") is None


def test_supply_banked_recovers_the_bank_reading():
    """`_pick_supply_target` builds quantity as banked + demand, so the
    difference IS the bank reading it was built from — not an estimate."""
    assert supply_banked(62, 50) == 12


def test_supply_banked_is_zero_for_an_empty_bank():
    assert supply_banked(50, 50) == 0


def test_supply_progress_reads_banked_over_target():
    assert supply_progress("ash_wood", 62, 50) == "ash_wood 12/62"


def test_supply_detail_names_both_the_progress_and_the_demand():
    assert supply_detail(62, 50) == "banked 12 / 62   demand 50"
