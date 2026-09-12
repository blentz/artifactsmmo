"""Bounds for the tests that drive the REAL `GOAPPlanner` over a REAL action pool.

WHY THIS EXISTS. Three tests in this suite assert that a `is_plannable(...) is
True` verdict is "backed by a real plan" by running the actual search and
asserting `plan` and `not planner.last_stats.timed_out`. They each used to pass
`budget_seconds=30.0`, which made the assertion a statement about the MACHINE:
the searches are 5.4s, 2.7s and 6.3s on an idle box, but `formal/gate.sh` runs
them inside `pytest -n auto` (one worker per core, 32 here) alongside
`test_task_horizon`'s 8-process census pool, and the gate run of 2026-09-11
took 418s for a lane-1 session that takes 125s on an idle box — i.e. the box
was ~3.2x slower. 5.4s x 3.2 is 17s; the observed loaded times were 10.9-13.9s,
and under a deliberate 3-spinners-per-CPU repro they reached 30.3s and FAILED.
Measured failure rate under that repro, before this module: supply-bank 1/4,
feather_coat 1/4, copper_boots 0/4 with a 25.4s worst case against its 30s
budget. All three were on the same cliff; only the first one happened to fall
off in the gate.

WHAT REPLACES THE CLOCK. `GOAPPlanner.plan` takes `max_nodes`, a bound on nodes
CREATED (`_MAX_SEARCH_NODES`, the memory bound), and a capped search reports
`node_capped` AND `timed_out`. Node counts are deterministic — the search is
deterministic, `_Node` ordering compares only `(f_score, depth)` and heapq
breaks the rest by insertion order — so bounding the WORK instead of the TIME
keeps exactly the assertion the tests were making ("a real search found this,
not a budget artifact") while making it independent of what else the box is
doing. That is also the unit the three docstrings already reason in: each one
records the node count its search took.

Measured (idle, 2026-09-12) at the three sites, `explored` / `created`:
    supply-bank deep_widget   18,761 / 93,142
    copper_boots from scratch 14,294 / 65,145
    feather_coat from scratch 29,488 / 160,960
"""

SEARCH_NODE_BUDGET = 400_000
"""Created-node ceiling for those searches: ~2.5x the largest of the three.

Deliberately well under the planner's own `_MAX_SEARCH_NODES` (1,000,000), so
a search that blows past this is a real regression in the search space and
fails DETERMINISTICALLY, on every box, with `node_capped` set — not a flake.
It also bounds the test's runtime: these searches create ~25k nodes/s, so the
cap is ~16s of work even in the failing case."""

NO_CLOCK = float("inf")
"""The wall-clock budget these searches run under: none.

Safe because `SEARCH_NODE_BUDGET` is what terminates them. Every iteration of
`GOAPPlanner.plan`'s loop either breaks or pops exactly one node, and pops are
bounded by nodes created, which is bounded by `max_nodes` — so the loop
terminates on work alone and needs no deadline to backstop it. A finite
"generous" budget would just be a smaller version of the 30s that failed."""
