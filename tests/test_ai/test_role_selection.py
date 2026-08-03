from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    NO_SKILL_LEVELS,
    ROLE_IDLE_DWELL_CYCLES,
    ROLE_MIN_HOLD_CYCLES,
    ROLE_SWITCH_MARGIN,
    ROLE_UNSERVABLE_CYCLES,
    decide_role,
    demand_by_role,
)

_ME = "HAL"


def _decide(current, held_cycles, leases, demand, idle_released=frozenset(),
            zero_demand_cycles=ROLE_IDLE_DWELL_CYCLES, **kwargs):
    """Default the zero-demand RUN to a full dwell window.

    Every pre-existing case here is about the OTHER hysteresis parameters, and
    reads most clearly when the idle run is not what is being varied. Tests
    that exercise the run itself pass it explicitly.

    `kwargs` forwards the later parameters (`unservable_released`,
    `unservable_cycles`, `skill_levels`) so the cases about THOSE stay explicit
    while every case predating them keeps their conservative defaults."""
    return decide_role(current=current, held_cycles=held_cycles,
                       live_leases=leases, demand_by_role=demand,
                       character=_ME, catalog=ROLE_CATALOG,
                       idle_released=idle_released,
                       zero_demand_cycles=zero_demand_cycles, **kwargs)


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


def test_idle_release_needs_a_full_run_of_zero_observations() -> None:
    # One cycle short of the dwell window: the role is idle RIGHT NOW, but the
    # run is not long enough to call it finished. A requester that happens to
    # sit on a level root publishes nothing at all, and those silences run for
    # dozens of consecutive cycles live -- releasing on the strength of a
    # single sample drops a role a sibling still needs.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, {},
                zero_demand_cycles=ROLE_IDLE_DWELL_CYCLES - 1)
    assert d.keep == "logger"
    assert d.release is None


def test_idle_release_fires_exactly_at_the_dwell_boundary() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, {},
                zero_demand_cycles=ROLE_IDLE_DWELL_CYCLES)
    assert d.release == "logger"


def test_idle_dwell_never_exceeds_the_min_hold() -> None:
    # Load-bearing inequality, not a coincidence. `GamePlayer` does NOT reset
    # the zero-demand run when it claims a role, because the run is only
    # consulted after `held_cycles >= ROLE_MIN_HOLD_CYCLES` and that counter
    # DOES restart on every claim. While this holds, a run carried across a
    # re-claim can never be the binding constraint; if the dwell were made the
    # longer of the two, a stale run could release a freshly claimed role early
    # and the caller would need an explicit reset.
    assert ROLE_IDLE_DWELL_CYCLES <= ROLE_MIN_HOLD_CYCLES


def test_no_zero_demand_run_never_releases_on_idle() -> None:
    # The parameter's default: a caller that does not track the run gets the
    # conservative behaviour (hold), never a release from a single sample.
    d = decide_role(current="logger", held_cycles=ROLE_MIN_HOLD_CYCLES,
                    live_leases={"logger": _ME}, demand_by_role={},
                    character=_ME, catalog=ROLE_CATALOG)
    assert d.keep == "logger"


def test_a_single_demand_flap_does_not_release_a_needed_role() -> None:
    # The traced defect, end to end. A sibling's demand is real but its
    # publication BLINKS: one cycle in every few it is on a non-ObtainItem root
    # and publishes nothing. Under the shipped single-sample rule the role was
    # released on the first blink after the dwell; under the run rule the role
    # survives the whole run, because every non-blink cycle breaks the run.
    leases = {"logger": _ME}
    current, zero_run = "logger", 0
    releases = 0
    for held, cycle in enumerate(range(400)):
        demand = {} if cycle % 7 == 0 else {"logger": 12}
        if demand.get(current, 0) <= 0:
            zero_run += 1
        else:
            zero_run = 0
        d = _decide(current, held, leases, demand, zero_demand_cycles=zero_run)
        if d.release is not None:
            releases += 1
            break

    assert releases == 0, "a blinking-but-real demand must never release the role"


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
# real caller would -- updating `current`/`held_cycles`/`idle_released` from
# the returned RoleDecision and folding claims/releases back into the leases
# the function sees next cycle -- and asserts the (current) trajectory goes
# flat and stays flat, rather than oscillating for the length of the run.
#
# `idle_released` is threaded exactly as `decide_role`'s docstring promises a
# caller may: a role name is added on EVERY release (idle or margin-driven)
# and never removed -- membership only matters while that role's demand is
# non-positive, so this is safe even for a margin-driven release of a role
# that still has positive demand at the moment it is released.


def _run_cycles(sibling_leases, demand, cycles, start_current=None, start_held=0):
    leases = dict(sibling_leases)
    if start_current is not None:
        leases[start_current] = _ME
    current = start_current
    held_cycles = start_held
    idle_released = frozenset()
    # Mirrors `GamePlayer._update_coordination` exactly: the caller owns the
    # zero-demand run, extends or breaks it BEFORE deciding, and resets it on a
    # successful claim. Simulating it any other way would prove something about
    # a caller that does not exist.
    zero_demand_cycles = 0
    trajectory = []
    state_changes = 0
    for _ in range(cycles):
        if current is not None and demand.get(current, 0) <= 0:
            zero_demand_cycles += 1
        else:
            zero_demand_cycles = 0
        d = _decide(current, held_cycles, leases, demand, idle_released,
                    zero_demand_cycles=zero_demand_cycles)
        if d.claim is not None:
            current = d.claim
            leases[current] = _ME
            held_cycles = 0
            zero_demand_cycles = 0
            state_changes += 1
        elif d.release is not None:
            del leases[d.release]
            idle_released = idle_released | {d.release}
            current = None
            held_cycles = 0
            state_changes += 1
        elif d.keep is not None:
            held_cycles += 1
        # else: a genuine no-op (RoleDecision() with every field None) --
        # nothing free and nothing held, so current/held_cycles don't move.
        trajectory.append(current)
    return trajectory, state_changes


def test_decide_role_never_oscillates_under_a_fixed_demand_snapshot() -> None:
    demand = {"miner": 15, "logger": 14, "fisher": 5}
    trajectory, _ = _run_cycles({}, demand, cycles=400)

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
    trajectory, _ = _run_cycles({}, demand, cycles=400)

    tail = trajectory[150:]
    assert len(set(tail)) == 1

    stabilized_at = trajectory.index(tail[0])
    assert trajectory[stabilized_at:] == [tail[0]] * (len(trajectory) - stabilized_at)


def test_decide_role_switches_once_then_never_reverts() -> None:
    # Coordinator review Finding 1: both prior scenarios started at
    # current=None, so _best_free_role grabbed the global argmax on cycle 0
    # and the trajectory was flat from the start -- that proves
    # "grab-the-max-and-stay", not "switch-then-never-revert", which is the
    # actual risk the hysteresis exists to prevent. Start HELD on a role that
    # is NOT the argmax (logger, demand 14) while miner (100) -- the true
    # argmax -- sits unleased. logger must be held through ROLE_MIN_HOLD_CYCLES
    # (the dwell defends exactly this), switch to miner exactly once when the
    # margin clears, and then never switch again for the rest of the run.
    demand = {"miner": 100, "logger": 14, "fisher": 1}
    trajectory, state_changes = _run_cycles({}, demand, cycles=400,
                                            start_current="logger", start_held=0)

    # Held through the dwell: no state change for the first
    # ROLE_MIN_HOLD_CYCLES cycles.
    assert trajectory[:ROLE_MIN_HOLD_CYCLES] == ["logger"] * ROLE_MIN_HOLD_CYCLES

    # Exactly one release (dwell ends, margin cleared) and one claim (grabs
    # the true argmax on the very next cycle) -- matching what the reviewer
    # observed (2 state changes over 300 cycles) -- then nothing else moves.
    assert state_changes == 2

    # Never reverts to logger once the dwell ends, and settles on the true
    # argmax (miner) for the remainder of the run.
    assert "logger" not in trajectory[ROLE_MIN_HOLD_CYCLES:]
    assert set(trajectory[-100:]) == {"miner"}


def test_decide_role_stabilizes_the_idle_churn_scenario() -> None:
    # Coordinator review Finding 2 (reviewer-constructed repro): demand
    # all-zero, sibling leases cover every role except one. Without
    # idle_released, decide_role loops claim -> hold -> release -> claim on
    # that same role forever (observed: 7 non-keep events over 350 cycles).
    # With idle_released threaded as the caller would, the character claims
    # the free role once, holds it out ROLE_MIN_HOLD_CYCLES, releases it
    # once, and then reaches a genuine no-op state (nothing free, nothing
    # held) for the rest of the run -- exactly 2 state changes, not an
    # unbounded, periodic churn.
    leases = {r.name: "C3P0" for r in ROLE_CATALOG if r.name != "logger"}
    trajectory, state_changes = _run_cycles(leases, {}, cycles=350)

    assert state_changes == 2
    # Once released, "logger" never reappears as `current` -- no re-claim.
    last_held_at = max(i for i, c in enumerate(trajectory) if c == "logger")
    assert all(c is None for c in trajectory[last_held_at + 1:])


def test_idle_released_role_is_claimable_again_once_demand_turns_positive() -> None:
    # A role that was released while idle is not claimable while it stays at
    # zero demand, but the caller never has to clear `idle_released` for
    # correctness: real demand alone re-opens it.
    d = _decide(None, 0, {}, {"logger": 5}, idle_released=frozenset({"logger"}))
    assert d.claim == "logger"


def test_idle_released_default_is_empty_and_changes_nothing() -> None:
    # decide_role's default `idle_released=frozenset()` must be behaviorally
    # identical to passing an explicit empty set -- no hidden default state.
    args = (None, 0, {}, {"miner": 10, "logger": 3})
    assert _decide(*args) == _decide(*args, idle_released=frozenset())


# --- Release on UNSERVABLE demand (Gap A, live run 2026-08-01) ---
# Release-on-idle triggers on demand reading ZERO. The hole it leaves: a role
# whose demand is POSITIVE but which the holder cannot serve. Because the lease
# is exclusive, every request for those skills routes to the holder by design,
# so the demand is never served and no sibling may take over. Live: a level-1
# character held `alchemist` while a level-21 sibling held `miner`.

_LOR_LEASES = {"alchemist": _ME}
_LOR_DEMAND = {"alchemist": 40}


def test_releases_a_role_whose_positive_demand_it_cannot_serve() -> None:
    # THE LOR SCENARIO. Demand is positive (so the idle rule cannot fire) and
    # has gone unserved for a full run: give the role up so a sibling can take
    # it. The `unservable` flag rides along because the caller has to know WHY
    # -- see the reclaim test below.
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES, _LOR_LEASES, _LOR_DEMAND,
                unservable_cycles=ROLE_UNSERVABLE_CYCLES)
    assert d.release == "alchemist"
    assert d.unservable is True


def test_a_servable_role_with_positive_demand_is_not_released() -> None:
    # The whole point of the counter: a role being SERVED (the run never
    # accumulates) must be held, no matter how long it has been held for.
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES * 10, _LOR_LEASES, _LOR_DEMAND,
                unservable_cycles=0)
    assert d.keep == "alchemist"
    assert d.release is None


def test_unservable_release_needs_a_full_run_of_failed_attempts() -> None:
    # One cycle short. A single failed search is a cheap-budget timeout or a
    # momentarily missing ingredient, not an inability.
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES, _LOR_LEASES, _LOR_DEMAND,
                unservable_cycles=ROLE_UNSERVABLE_CYCLES - 1)
    assert d.keep == "alchemist"
    assert d.release is None


def test_no_unservable_run_never_releases_on_unservability() -> None:
    # The parameter's default: a caller that does not track the run gets the
    # conservative behaviour (hold), exactly as with `zero_demand_cycles`.
    d = decide_role(current="alchemist", held_cycles=ROLE_MIN_HOLD_CYCLES,
                    live_leases=_LOR_LEASES, demand_by_role=_LOR_DEMAND,
                    character=_ME, catalog=ROLE_CATALOG)
    assert d.keep == "alchemist"


def test_unservable_release_waits_for_the_min_hold_like_every_other_release() -> None:
    # The dwell that defends against thrash is checked FIRST, so a role claimed
    # this cycle is never dropped on a run carried in from a previous holding.
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES - 1, _LOR_LEASES, _LOR_DEMAND,
                unservable_cycles=ROLE_UNSERVABLE_CYCLES * 10)
    assert d.keep == "alchemist"


def test_unservable_dwell_never_exceeds_the_min_hold() -> None:
    # Same load-bearing inequality `ROLE_IDLE_DWELL_CYCLES` carries, for the
    # same reason: the run is only consulted once `held_cycles >=
    # ROLE_MIN_HOLD_CYCLES`, and THAT counter restarts on every claim, so a run
    # carried across a re-claim can never be the binding constraint.
    assert ROLE_UNSERVABLE_CYCLES <= ROLE_MIN_HOLD_CYCLES


def test_an_idle_release_is_not_flagged_unservable() -> None:
    # Zero demand is a different verdict: the role is FINISHED, not impossible.
    # It must stay re-claimable the moment demand returns, so the caller must
    # not be told to block it.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME}, {})
    assert d.release == "logger"
    assert d.unservable is False


def test_a_margin_release_is_not_flagged_unservable() -> None:
    # Losing a demand-margin contest says nothing about capability — the role
    # was being served fine, a rival simply carries more demand.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME},
                {"logger": 1, "miner": 100}, unservable_cycles=0)
    assert d.release == "logger"
    assert d.unservable is False


def test_an_unservable_released_role_is_not_reclaimed_despite_positive_demand() -> None:
    # The churn hole specific to THIS release: positive demand is exactly what
    # triggered it, so the `idle_released` rule (which only skips a role while
    # its demand is non-positive) would hand the role straight back next cycle.
    d = _decide(None, 0, {}, _LOR_DEMAND,
                unservable_released=frozenset({"alchemist"}))
    assert d.claim is not None
    assert d.claim != "alchemist"


def test_an_unservable_released_role_is_claimable_again_once_the_block_lifts() -> None:
    # The caller drops the role from the set when the verdict could have
    # changed (GamePlayer: when the character's level in one of the role's own
    # skills has risen). With the block lifted, the role competes normally and
    # wins on its demand.
    d = _decide(None, 0, {}, _LOR_DEMAND, unservable_released=frozenset())
    assert d.claim == "alchemist"


def test_every_role_blocked_or_leased_claims_nothing() -> None:
    # The unconditional skip must be able to empty the candidate set entirely
    # (the `best is None` path) rather than fall through to a blocked role.
    d = _decide(None, 0, {}, {r.name: 5 for r in ROLE_CATALOG},
                unservable_released=frozenset(r.name for r in ROLE_CATALOG))
    assert (d.claim, d.keep, d.release) == (None, None, None)


# --- Level-aware claiming (Gap B, live run 2026-08-01) ---
# Allocation used to be decided purely by demand, so which character got which
# role came down to who won the startup race: a level-21 character holding
# `jeweler` while a level-1 character held `miner` was perfectly reachable.

_JEWELER = {"jewelrycrafting": 20}
_MINER = {"mining": 21}


def test_skill_fit_breaks_a_comparable_demand_toward_the_suited_role() -> None:
    # Equal demand on miner and jeweler. Demand alone resolves this by catalog
    # order (miner is first), which is how a trained jeweler ended up mining.
    demand = {"miner": 10, "jeweler": 10}
    assert _decide(None, 0, {}, demand).claim == "miner"
    assert _decide(None, 0, {}, demand, skill_levels=_JEWELER).claim == "jeweler"
    assert _decide(None, 0, {}, demand, skill_levels=_MINER).claim == "miner"


def test_skill_fit_never_vetoes_a_role_the_fleet_actually_needs() -> None:
    # A perfectly-suited character must not sit idle when the only demand is
    # elsewhere: affinity maxes at 1, so it can at most DOUBLE effective demand.
    d = _decide(None, 0, {}, {"miner": 100}, skill_levels=_JEWELER)
    assert d.claim == "miner"


def test_skill_fit_decides_when_the_board_is_completely_quiet() -> None:
    # Cold start with nothing published. Without the `+ 1` offset every role
    # would score zero and the tie would fall to catalog order, so a trained
    # jeweler would claim `miner` on cycle 0 of every session.
    assert _decide(None, 0, {}, {}, skill_levels=_JEWELER).claim == "jeweler"


def test_a_character_with_no_levels_in_the_free_role_still_claims_it() -> None:
    # PREFER, never forbid: hard-excluding an ill-suited role would leave a
    # fresh character permanently unspecialized. Every role but `jeweler` is
    # leased away and hero has zero jewelrycrafting — it still claims it.
    leases = {r.name: "C3P0" for r in ROLE_CATALOG if r.name != "jeweler"}
    d = _decide(None, 0, leases, {}, skill_levels=_MINER)
    assert d.claim == "jeweler"


def test_skills_no_role_owns_leave_the_claim_demand_ranked() -> None:
    # `best` level over the catalog's own skills is 0 here, so affinity is
    # uniform and the ranking is demand's alone — the same answer as passing
    # no skills at all.
    d = _decide(None, 0, {}, {"miner": 3, "logger": 9}, skill_levels={"unowned": 40})
    assert d.claim == "logger"


def test_skill_levels_default_is_empty_and_changes_nothing() -> None:
    # No hidden default state: omitting `skill_levels` must be identical to
    # passing the exported empty default.
    args = (None, 0, {}, {"miner": 10, "logger": 3})
    assert _decide(*args) == _decide(*args, skill_levels=NO_SKILL_LEVELS)
    assert dict(NO_SKILL_LEVELS) == {}


def test_skill_fit_does_not_reopen_the_margin_rule() -> None:
    # The hold/release side stays demand-driven: a well-suited rival role does
    # NOT pull a character off a role that is still carrying demand, because
    # skill fit says what this character could produce, not what the fleet needs.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, {"logger": _ME},
                {"logger": 10, "jeweler": 15}, skill_levels=_JEWELER)
    assert d.keep == "logger"


# --- demand_by_role: bridges item-keyed sibling demand onto role-keyed demand ---


def test_demand_routes_to_the_role_owning_the_producing_skill() -> None:
    item_demand = {"copper_bar": 6, "ash_plank": 4}
    skill_of_item = {"copper_bar": "mining", "ash_plank": "woodcutting"}
    got = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
    assert got["miner"] == 6
    assert got["logger"] == 4


def test_demand_for_an_unowned_skill_is_dropped() -> None:
    got = demand_by_role({"mystery": 5}, {"mystery": None}, ROLE_CATALOG)
    assert sum(got.values()) == 0


def test_demand_sums_when_two_items_share_a_role() -> None:
    item_demand = {"copper_bar": 6, "iron_bar": 3}
    skill_of_item = {"copper_bar": "mining", "iron_bar": "mining"}
    assert demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)["miner"] == 9


def test_every_role_appears_even_with_no_demand() -> None:
    got = demand_by_role({}, {}, ROLE_CATALOG)
    assert set(got) == {r.name for r in ROLE_CATALOG}
    assert set(got.values()) == {0}


def test_demand_for_an_item_missing_from_skill_of_item_is_dropped() -> None:
    # skill_of_item.get(item_code) returns None both when the value IS None
    # and when the key is absent entirely -- both must be dropped, not raise.
    got = demand_by_role({"unmapped_item": 3}, {}, ROLE_CATALOG)
    assert sum(got.values()) == 0


def test_demand_routes_to_the_alchemist_whose_gather_and_craft_collapse() -> None:
    # alchemist's gather and craft are both "alchemy" -- role_skills collapses
    # to a single-element set. The owner map must still route "alchemy" demand
    # to "alchemist" without double-counting or raising on the collapse.
    item_demand = {"life_potion": 5}
    skill_of_item = {"life_potion": "alchemy"}
    got = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
    assert got["alchemist"] == 5


def test_demand_for_a_skill_no_role_owns_is_dropped_even_when_present() -> None:
    # A skill string that IS in skill_of_item's values but that no catalog
    # role owns (owner.get(skill) is None) must be dropped, not KeyError.
    item_demand = {"raw_fish": 5}
    skill_of_item = {"raw_fish": "fishing_prep_unowned"}
    got = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
    assert sum(got.values()) == 0
