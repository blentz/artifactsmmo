from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    ROLE_MIN_HOLD_CYCLES,
    ROLE_SWITCH_MARGIN,
    decide_role,
)

_ME = "HAL"


def _decide(current, held_cycles, leases, demand):
    return decide_role(current=current, held_cycles=held_cycles,
                       live_leases=leases, demand_by_role=demand,
                       character=_ME, catalog=ROLE_CATALOG)


def test_claims_highest_demand_role_when_holding_none() -> None:
    d = _decide(None, 0, {}, {"miner": 10, "logger": 3})
    assert (d.claim, d.keep, d.release) == ("miner", None, None)


def test_skips_roles_held_by_a_sibling() -> None:
    d = _decide(None, 0, {"miner": "C3P0"}, {"miner": 10, "logger": 3})
    assert d.claim == "logger"


def test_claims_nothing_when_every_role_is_leased() -> None:
    leases = {r.name: "C3P0" for r in ROLE_CATALOG}
    d = _decide(None, 0, leases, {"miner": 10})
    assert (d.claim, d.keep, d.release) == (None, None, None)


def test_claims_an_unleased_role_even_with_zero_demand() -> None:
    d = _decide(None, 0, {}, {})
    assert d.claim is not None


def test_zero_demand_ties_break_by_catalog_order_not_last_writer() -> None:
    # Every role is tied at zero demand and none is leased. The tie MUST
    # resolve to the first catalog entry (a declared semantic order), never
    # to whichever role a >= comparison happened to visit last.
    d = _decide(None, 0, {}, {})
    assert d.claim == ROLE_CATALOG[0].name


def test_keeps_current_role_before_min_hold_even_if_another_is_better() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, {"logger": _ME},
                {"logger": 1, "miner": 100})
    assert d.keep == "logger"


def test_switches_after_min_hold_when_margin_is_cleared() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME},
                {"logger": 1, "miner": 100})
    assert d.release == "logger"


def test_holds_when_margin_is_not_cleared() -> None:
    # miner is better but not MARGIN times better.
    demand = {"logger": 10, "miner": int(10 * ROLE_SWITCH_MARGIN) - 1}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, demand)
    assert d.keep == "logger"


def test_switches_exactly_at_the_margin_boundary() -> None:
    # "must carry this multiple" is inclusive: exactly 2x clears the margin.
    demand = {"logger": 10, "miner": int(10 * ROLE_SWITCH_MARGIN)}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, demand)
    assert d.release == "logger"


def test_releases_on_idle_after_min_hold_with_no_better_alternative() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, {})
    assert d.release == "logger"


def test_releases_on_idle_even_when_every_rival_role_is_leased_away() -> None:
    # The idle guard (own_demand <= 0) must fire on its OWN: with no free
    # rival role, the margin loop's rival_best stays at its -1 sentinel and
    # -1 >= 0 is False, so a weakened "own_demand < 0" guard would wrongly
    # keep the role here even though nothing needs it.
    leases = {r.name: (_ME if r.name == "logger" else "C3P0") for r in ROLE_CATALOG}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, leases, {})
    assert d.release == "logger"


def test_idle_role_is_kept_before_min_hold() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, {"logger": _ME}, {})
    assert d.keep == "logger"


def test_reclaims_when_our_lease_vanished() -> None:
    # TTL expired mid-session while we still believed we held it.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES + 5, {}, {"logger": 5})
    assert d.claim == "logger"


def test_margin_is_exactly_two() -> None:
    assert Fraction(2) == ROLE_SWITCH_MARGIN


# --- Additional branch-coverage tests (controller-required: `branch = false`
# in this project's coverage config means statement coverage alone can miss a
# conditional whose false side is never exercised, so every `if` below is
# proven in both directions). ---


def test_best_free_role_treats_a_role_still_leased_to_self_as_available() -> None:
    # current is None (e.g. process restarted) but our OWN lease on "miner"
    # is still live. _best_free_role must not treat "holder == character" as
    # "leased by someone else" -- we should reclaim our own role.
    d = _decide(None, 0, {"miner": _ME}, {"miner": 100, "logger": 3})
    assert d.claim == "miner"


def test_rival_role_held_by_a_sibling_is_excluded_from_the_margin_check() -> None:
    # miner carries huge demand but is leased to C3P0, so it must NOT count
    # toward the margin comparison; only the unleased "fisher" may.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                {"logger": _ME, "miner": "C3P0"},
                {"logger": 5, "miner": 1000, "fisher": 1})
    assert d.keep == "logger"


def test_rival_role_leased_to_self_still_counts_toward_the_margin() -> None:
    # A role other than `current` that happens to show ourself as holder
    # (degenerate/defensive case) is not "leased by someone else" and its
    # demand must still be weighed as a genuine rival.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                {"logger": _ME, "miner": _ME},
                {"logger": 5, "miner": 100})
    assert d.release == "logger"


def test_current_role_is_skipped_inside_its_own_rival_scan() -> None:
    # Sanity check on the `role.name == current: continue` guard: with every
    # other role pinned to zero demand, "logger" must not nominate itself as
    # its own rival (which would spuriously clear the margin at demand 0).
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME},
                {"logger": 5, "miner": 0, "fisher": 0})
    assert d.keep == "logger"


# --- Oscillation property ---
# The entire point of the hysteresis constants is that a fixed demand
# snapshot and a fixed set of sibling leases must never cause a character to
# ping-pong between two roles. This drives decide_role in a loop the way a
# real caller would -- updating `current`/`held_cycles` from the returned
# RoleDecision and folding claims/releases back into the leases the function
# sees next cycle -- and asserts the (current) trajectory goes flat and stays
# flat, rather than oscillating for the length of the run.


def _run_cycles(sibling_leases, demand, cycles):
    leases = dict(sibling_leases)
    current = None
    held_cycles = 0
    trajectory = []
    for _ in range(cycles):
        d = _decide(current, held_cycles, leases, demand)
        if d.claim is not None:
            current = d.claim
            leases[current] = _ME
            held_cycles = 0
        elif d.release is not None:
            del leases[d.release]
            current = None
            held_cycles = 0
        else:
            assert d.keep is not None
            held_cycles += 1
        trajectory.append(current)
    return trajectory


def test_decide_role_never_oscillates_under_a_fixed_demand_snapshot() -> None:
    demand = {"miner": 15, "logger": 14, "fisher": 5}
    trajectory = _run_cycles({}, demand, cycles=400)

    # Reaches a fixed point and never leaves it: once stabilized, the tail of
    # the trajectory is a single repeated role, not an alternating sequence.
    tail = trajectory[150:]
    assert len(set(tail)) == 1
    assert tail[0] is not None

    # Never ping-pongs: the number of distinct (current) values visited over
    # the WHOLE run is small and, past the point it first stabilizes, constant.
    stabilized_at = trajectory.index(tail[0])
    assert trajectory[stabilized_at:] == [tail[0]] * (len(trajectory) - stabilized_at)


def test_decide_role_stabilizes_even_with_a_near_margin_rival() -> None:
    # miner (20) is close to -- but does not clear -- 2x logger's (14) demand
    # once logger is held; this is the shape most likely to thrash under a
    # buggy (non-hysteretic) implementation.
    demand = {"miner": 20, "logger": 14, "fisher": 1}
    trajectory = _run_cycles({}, demand, cycles=400)

    tail = trajectory[150:]
    assert len(set(tail)) == 1

    stabilized_at = trajectory.index(tail[0])
    assert trajectory[stabilized_at:] == [tail[0]] * (len(trajectory) - stabilized_at)
