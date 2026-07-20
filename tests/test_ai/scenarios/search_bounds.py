"""Shared node-bound assertion for scenario planner runs (extracted from
test_band_liveness so the slot-coverage net reuses the identical bound)."""

from typing import cast

from artifactsmmo_cli.ai.plan_report import PlanReport

MAX_SEARCH_NODES = 200_000
"""The feather_coat lesson (project_feather_coat_cpu_peg): an unsatisfiable
GatherMaterials goal exploded to 237K nodes/cycle before a plan-cache /
memo fix landed. A scenario that lands anywhere near that magnitude,
even while still emitting SOME plan, is a deadlock precursor — treat it as
a failure, not a warning."""


def assert_search_bounded(report: PlanReport, name: str, *,
                          expect_no_work: bool = False) -> None:
    """EVERY goal the arbiter tried this cycle must stay well under the node
    cap and must not have been node-capped or timed out — not just the
    selected goal's own entry. A non-selected goal that floods the search
    (the feather_coat 237K-node lesson: an unsatisfiable candidate can peg
    CPU even when it's later demoted and something else gets selected) is
    still a deadlock precursor; bounding only the winner's entry would let
    it slip through the net. A bounded search that still finds nothing is a
    different (legitimate) failure mode than an unbounded one that happens
    to find something.

    `expect_no_work` names a scenario that PROVABLY has nothing to try, and
    FLIPS the guard rather than skipping it: goals_tried must then be EMPTY.
    Without the flip an empty list would satisfy the loop below vacuously; with
    it, a scenario that unexpectedly gains work fails just as loudly as one that
    unexpectedly loses it.

    The only such scenario today is l48_band_adequate, whose L47-50 fight window
    is event-and-raid-only content, so a band-adequate character has nothing
    permanent to fight. That is asserted directly, both poles, in
    test_l48_raid_pair.py — this flag exists so the bounded net agrees with it
    instead of contradicting it."""
    if expect_no_work:
        assert report.goals_tried == [], (name, report.goals_tried)
        return
    assert report.goals_tried, (name, report.selected_goal)
    for entry in report.goals_tried:
        nodes = cast(int, entry["nodes"])
        node_capped = cast(bool, entry.get("node_capped", False))
        timed_out = cast(bool, entry["timed_out"])
        assert nodes < MAX_SEARCH_NODES, (name, entry)
        assert not node_capped, (name, entry)
        assert not timed_out, (name, entry)
