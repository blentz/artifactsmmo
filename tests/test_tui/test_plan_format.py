"""short_root: collapse ObtainItem(...) reprs to a scannable short form."""

import re

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode
from artifactsmmo_cli.tui.plan_format import (
    grind_chain_lines,
    parse_supply_target,
    short_root,
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


def test_supply_progress_reports_the_batch_target_and_the_unmet_demand():
    """Both numbers come straight out of the pair, undisturbed: `quantity` is
    the banked count the goal is producing TOWARD, `demand` the units still
    unmet."""
    assert supply_progress("ash_wood", 62, 50) == "ash_wood →62 banked, 50 unmet"


def test_supply_progress_does_not_subtract_the_demand_from_the_target():
    """The measured breakage, and the test that fails if `quantity - demand`
    ever comes back: `_pick_supply_target` now builds `quantity` as a BATCH
    milestone, so banked=0 with demand=60 gives the pair (10, 60) and the old
    subtraction rendered `spruce_wood -50/10` — a negative bank count on
    screen. The bank reading is simply not in the pair any more."""
    rendered = supply_progress("spruce_wood", 10, 60)
    assert rendered == "spruce_wood →10 banked, 60 unmet"
    assert "-50" not in rendered


def test_supply_detail_names_both_the_target_and_the_demand():
    assert supply_detail(62, 50) == "target 62 banked   demand 50"


def test_both_panes_report_the_same_two_numbers():
    """The property the formatters exist to protect: the log line and the plan
    tree's supply detail ask the SAME question of the SAME fields, so a reader
    switching panes never sees two different accounts of one commitment. A pane
    that derived a third figure from the pair — the retired `quantity - demand`
    — would show a number the other one does not."""
    for pair in ((62, 50), (10, 60)):
        assert re.findall(r"-?\d+", supply_progress("ash_wood", *pair)) == [
            str(pair[0]), str(pair[1])]
        assert re.findall(r"-?\d+", supply_detail(*pair)) == [
            str(pair[0]), str(pair[1])]
