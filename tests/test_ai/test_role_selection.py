from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import ROLE_CATALOG
from artifactsmmo_cli.ai.role_selection import (
    NO_ITEM_LEVELS,
    NO_SKILL_LEVELS,
    ROLE_IDLE_DWELL_CYCLES,
    ROLE_MIN_HOLD_CYCLES,
    ROLE_SWITCH_MARGIN,
    ROLE_UNSERVABLE_CYCLES,
    decide_role,
    demand_by_role,
    serves_item,
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


def _held(**by_role):
    """`{role: frozenset(holders)}` from `role=("A", "B")` kwargs — the
    `live_leases` shape, written without a frozenset literal at every site."""
    return {role: frozenset(names) for role, names in by_role.items()}


def test_claims_highest_demand_role_when_holding_none() -> None:
    d = _decide(None, 0, {}, {"miner": 10, "logger": 3})
    assert (d.claim, d.keep, d.release) == ("miner", None, None)


def test_a_role_a_sibling_holds_is_damped_not_skipped() -> None:
    # Under exclusivity this was `test_skips_roles_held_by_a_sibling` and the
    # answer was "logger" no matter how lopsided the demand. A held role is now
    # a candidate whose demand is HALVED: miner's 10 becomes 5, which still
    # beats logger's 3, so the character joins the role that actually needs the
    # work instead of being pushed to a quieter one.
    d = _decide(None, 0, _held(miner=("C3P0",)), {"miner": 10, "logger": 3})
    assert d.claim == "miner"


def test_a_sibling_holding_a_role_can_still_tip_the_claim_elsewhere() -> None:
    # The other side of the same rule: halving is not cosmetic. miner's 10
    # outranks logger's 6 when miner is unheld, and loses to it when one
    # sibling is already on miner (10/2 = 5 < 6).
    demand = {"miner": 10, "logger": 6}
    assert _decide(None, 0, {}, demand).claim == "miner"
    assert _decide(None, 0, _held(miner=("C3P0",)), demand).claim == "logger"


def test_demand_splitting_damps_each_successive_joiner() -> None:
    # The saturation rule, stated as the monotone series it is: the Nth
    # character to weigh a role sees demand/N. `logger` at 24 out-scores a
    # steady rival at 7 for the first three joiners (24, 12, 8) and loses to it
    # on the fourth (24/4 = 6), with nothing forbidden at any point.
    demand = {"logger": 24, "fisher": 7}
    holders = []
    claims = []
    for name in ("A", "B", "C", "D"):
        claims.append(_decide(None, 0, _held(logger=tuple(holders)), demand).claim)
        holders.append(name)
    assert claims == ["logger", "logger", "logger", "fisher"]


def test_three_characters_can_serve_one_role_at_once() -> None:
    # "there may be times we need ... three woodcutters". Demand large enough
    # that a third of it still dominates: nothing caps the count but the falling
    # share itself.
    d = _decide(None, 0, _held(logger=("A", "B")), {"logger": 90, "fisher": 5})
    assert d.claim == "logger"


def test_a_role_with_no_demand_attracts_no_holder() -> None:
    # "there may be times we need zero alchemists". A silent role scores at most
    # (0+1)x(1+1) = 2 and any role carrying >= 2 effective demand scores >= 3,
    # so no skill fit can pull a character onto it while a real request stands —
    # even when the character is far better suited to the silent one.
    demand = {"alchemist": 0, "miner": 4}
    assert _decide(None, 0, {}, demand, skill_levels={"alchemy": 30}).claim == "miner"


def test_no_role_is_ever_unavailable_however_crowded() -> None:
    # The exclusivity check is gone, not merely relaxed: with every role held by
    # a sibling the character used to claim NOTHING. It must now still pick the
    # best-scoring one.
    leases = {r.name: frozenset({"C3P0"}) for r in ROLE_CATALOG}
    d = _decide(None, 0, leases, {"miner": 10})
    assert d.claim == "miner"


def test_claims_a_role_even_with_zero_demand() -> None:
    d = _decide(None, 0, {}, {})
    assert d.claim is not None


def test_zero_demand_ties_break_by_catalog_order_not_last_writer() -> None:
    # Every role is tied at zero demand and none is leased. The tie MUST
    # resolve to the first catalog entry (a declared semantic order), never
    # to whichever role a >= comparison happened to visit last.
    d = _decide(None, 0, {}, {})
    assert d.claim == ROLE_CATALOG[0].name


def test_keeps_current_role_before_min_hold_even_if_another_is_better() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, _held(logger=(_ME,)),
                {"logger": 1, "miner": 100})
    assert d.keep == "logger"


def test_switches_after_min_hold_when_margin_is_cleared() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 1, "miner": 100})
    assert d.release == "logger"


def test_holds_when_margin_is_not_cleared() -> None:
    # miner is better but not MARGIN times better.
    demand = {"logger": 10, "miner": int(10 * ROLE_SWITCH_MARGIN) - 1}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), demand)
    assert d.keep == "logger"


def test_switches_exactly_at_the_margin_boundary() -> None:
    # "must carry this multiple" is inclusive: exactly 2x clears the margin.
    demand = {"logger": 10, "miner": int(10 * ROLE_SWITCH_MARGIN)}
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), demand)
    assert d.release == "logger"


def test_releases_on_idle_after_min_hold_for_a_role_that_wants_work() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"miner": 3})
    assert d.release == "logger"
    assert d.unservable is False


def test_an_idle_role_is_kept_when_the_whole_board_is_silent() -> None:
    # The narrowing, stated on its own. Release-on-idle's surviving purpose is
    # to move this character OFF a dead role and ONTO a live one -- freeing the
    # role helps no sibling now that nothing is exclusive. With no live role
    # anywhere there is no destination, so releasing buys nothing and costs a
    # claim, a dwell and another release for every role in the catalog.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {})
    assert d.keep == "logger"
    assert d.release is None


def test_releases_on_idle_even_when_the_role_that_wants_work_is_crowded() -> None:
    # The gate is "somewhere to go", not "somewhere uncrowded to go": a rival
    # already worked by four siblings still reads as positive demand, and a
    # dead role is worse than a fifth of a live one. Every rival except `miner`
    # is at zero demand, so nothing but the crowded one can be what fires here.
    leases = {r.name: frozenset({_ME if r.name == "logger" else "C3P0"})
              for r in ROLE_CATALOG}
    leases["miner"] = frozenset({"C3P0", "R2D2", "K9", "TARS"})
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, leases, {"miner": 4})
    assert d.release == "logger"


def test_an_idle_role_is_kept_when_the_only_live_rival_cannot_be_claimed() -> None:
    # RESIDUAL 1, on the idle path. `miner` carries the board's only demand but
    # this character released it as UNSERVABLE, so the claim next cycle would
    # refuse it (`_claimable`) and the character would land on a zero-demand
    # role instead -- strictly worse than the role it is already on. A rival it
    # cannot take is not somewhere to go.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"miner": 500}, unservable_released=frozenset({"miner"}))
    assert d.keep == "logger"
    assert d.release is None


def test_idle_release_needs_a_full_run_of_zero_observations() -> None:
    # One cycle short of the dwell window: the role is idle RIGHT NOW, but the
    # run is not long enough to call it finished. A requester that happens to
    # sit on a level root publishes nothing at all, and those silences run for
    # dozens of consecutive cycles live -- releasing on the strength of a
    # single sample drops a role a sibling still needs.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"miner": 3},
                zero_demand_cycles=ROLE_IDLE_DWELL_CYCLES - 1)
    assert d.keep == "logger"
    assert d.release is None


def test_idle_release_fires_exactly_at_the_dwell_boundary() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"miner": 3},
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
                    live_leases=_held(logger=(_ME,)), demand_by_role={"miner": 3},
                    character=_ME, catalog=ROLE_CATALOG)
    assert d.keep == "logger"


def test_a_single_demand_flap_does_not_release_a_needed_role() -> None:
    # The traced defect, end to end. A sibling's demand is real but its
    # publication BLINKS: one cycle in every few it is on a non-ObtainItem root
    # and publishes nothing. Under the shipped single-sample rule the role was
    # released on the first blink after the dwell; under the run rule the role
    # survives the whole run, because every non-blink cycle breaks the run.
    leases = _held(logger=(_ME,))
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
    # A live rival on the board, so the dwell on `held_cycles` is the only
    # thing that can be holding the release back.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES - 1, _held(logger=(_ME,)),
                {"miner": 3})
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


def test_our_own_lease_never_damps_the_role_we_are_weighing() -> None:
    # current is None (e.g. process restarted) but our OWN lease on "miner" is
    # still live. `_effective_demand` counts OTHER holders only, so miner reads
    # at its full 100, not 50 -- a character must not be pushed off a role by
    # its own membership.
    d = _decide(None, 0, _held(miner=(_ME,)), {"miner": 100, "logger": 3})
    assert d.claim == "miner"


def test_a_rival_a_sibling_holds_is_damped_not_excluded_from_the_margin() -> None:
    # Under exclusivity a rival role a sibling held was skipped outright, so
    # `logger` was kept no matter how much demand `miner` carried. It is now
    # weighed at its SHARE: 1000 over two holders is 500, which clears 2x
    # logger's 5, so the character joins the role that plainly needs help.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                _held(logger=(_ME,), miner=("C3P0",)),
                {"logger": 5, "miner": 1000, "fisher": 1})
    assert d.release == "logger"


def test_enough_siblings_on_a_rival_role_stop_it_clearing_the_margin() -> None:
    # The damping is what decides it, not the raw figure: the same 1000-demand
    # rival with nine siblings already on it reads as 100... which still clears
    # 2x50. Pushed to the boundary instead: logger 50 (ours alone) against
    # miner 180 shared by two siblings -- 180/3 = 60, and 60 < 100, so we stay.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                _held(logger=(_ME,), miner=("C3P0", "R2D2")),
                {"logger": 50, "miner": 180})
    assert d.keep == "logger"


def test_siblings_piling_onto_our_role_eventually_push_us_out_of_it() -> None:
    # The self-limiting half of demand splitting, and the only place OUR side
    # of the margin is split by anything. `logger` carries 24 but two siblings
    # joined it, so our share is 8; `miner`'s 16 is untouched, and 16 >= 2 x 8
    # clears the margin. Weighing our own side RAW (24) would read the rival as
    # needing 48 and keep three characters on a role that needs one -- the
    # pile-on would be a one-way ratchet with no way back out.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                _held(logger=(_ME, "A", "B")), {"logger": 24, "miner": 16})
    assert d.release == "logger"


def test_a_role_we_share_with_nobody_is_weighed_whole_on_our_side() -> None:
    # The same demand figures with the siblings gone: `logger`'s 24 is ours
    # alone, so 16 < 2 x 24 and we stay. Splitting is what moved us above, not
    # the raw numbers.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES,
                _held(logger=(_ME,)), {"logger": 24, "miner": 16})
    assert d.keep == "logger"


def test_our_own_membership_does_not_shrink_our_side_of_the_margin() -> None:
    # `_effective_demand` subtracts `character` before counting, on BOTH sides.
    # If it did not, holding `logger` alone would read as logger/2 = 2 here and
    # the 5-demand `miner` rival (5 >= 2*2) would spuriously clear the margin.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 5, "miner": 5})
    assert d.keep == "logger"


def test_a_rival_this_character_cannot_claim_does_not_trigger_a_release() -> None:
    # RESIDUAL 1, on the margin path. `miner` carries 200x `logger`'s demand,
    # which clears the switch margin many times over -- but this character
    # released `miner` as UNSERVABLE, so `_claimable` would refuse it on the
    # very next cycle. Releasing for a rival it cannot take drops it onto a
    # worse role and repeats the lap every ROLE_MIN_HOLD_CYCLES. The rival scan
    # and the claim ranking read the same predicate, so this cannot happen.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 5, "miner": 1000},
                unservable_released=frozenset({"miner"}))
    assert d.keep == "logger"
    assert d.release is None


def test_the_same_rival_does_trigger_a_release_once_it_is_claimable() -> None:
    # The positive control for the test above: identical board, nothing
    # blocked. The margin still fires, so the filter narrowed exactly the
    # unclaimable case and nothing else.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 5, "miner": 1000})
    assert d.release == "logger"


def test_an_idle_released_rival_carrying_demand_still_triggers_a_release() -> None:
    # The two released sets have OPPOSITE re-entry rules and the shared
    # predicate must keep that distinction on the rival scan too: an
    # idle-released role is skipped only WHILE its demand is non-positive, so a
    # role that went back into real demand is a legitimate destination again.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 5, "miner": 1000}, idle_released=frozenset({"miner"}))
    assert d.release == "logger"


def test_current_role_is_skipped_inside_its_own_rival_scan() -> None:
    # Sanity check on the `role.name == current: continue` guard: with every
    # other role pinned to zero demand, "logger" must not nominate itself as
    # its own rival (which would spuriously clear the margin at demand 0).
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
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


def _join(leases, role):
    """Add `_ME` to `role`'s holder set, keeping any siblings already on it —
    a claim no longer displaces anyone."""
    leases[role] = leases.get(role, frozenset()) | {_ME}


def _leave(leases, role):
    """Drop `_ME` from `role`'s holders, and drop the KEY entirely when that
    empties it: `live_leases` omits unheld roles rather than mapping them to an
    empty set, so leaving one behind would feed `decide_role` a shape the real
    store never produces."""
    remaining = leases[role] - {_ME}
    if remaining:
        leases[role] = remaining
    else:
        del leases[role]


def _run_cycles(sibling_leases, demand, cycles, start_current=None, start_held=0,
                skill_levels=NO_SKILL_LEVELS):
    leases = dict(sibling_leases)
    if start_current is not None:
        _join(leases, start_current)
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
                    zero_demand_cycles=zero_demand_cycles,
                    skill_levels=skill_levels)
        if d.claim is not None:
            current = d.claim
            _join(leases, current)
            held_cycles = 0
            zero_demand_cycles = 0
            state_changes += 1
        elif d.release is not None:
            _leave(leases, d.release)
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


def test_an_all_zero_demand_board_settles_without_walking_the_catalog() -> None:
    # RESIDUAL 2. An all-zero board used to walk every role in turn -- claim,
    # hold ROLE_MIN_HOLD_CYCLES, release as idle, claim the next -- about 505
    # cycles of DB writes and role changes serving nothing, and under
    # non-exclusivity that is the DEFAULT shape of a quiet board, not an edge
    # case. Release-on-idle now requires a destination (some claimable role
    # with positive demand), and with the whole board silent there is none, so
    # the character claims once and stays put.
    trajectory, state_changes = _run_cycles({}, {}, cycles=600)

    assert state_changes == 1
    assert set(trajectory) == {ROLE_CATALOG[0].name}


def test_a_role_is_released_when_a_claimable_rival_starts_wanting_work() -> None:
    # The other side of the same gate: the narrowing must not make the rule
    # inert. The character is parked on `miner`, which nothing needs, while
    # `fisher` carries real demand -- so it must leave, which is the ONLY rule
    # that can move it (the margin scan is never reached on zero own demand).
    trajectory, state_changes = _run_cycles({}, {"fisher": 20}, cycles=600,
                                            start_current="miner")

    assert state_changes == 2  # release miner as idle, then claim fisher
    assert trajectory[0] == "miner"
    assert set(trajectory[-100:]) == {"fisher"}


_STUCK_MINER = {"mining": 20}
"""A character with mining levels and nothing else -- affinity 1 for `miner`
and 0 for every other role, which is what makes the re-claim below possible."""


def test_a_released_role_is_not_immediately_re_claimed_over_a_live_one() -> None:
    # `idle_released` is still load-bearing under the narrowed rule, and this
    # is exactly the state that proves it: `miner` has just been released as
    # idle because `alchemist` wants work, and the claim ranks on affinity as
    # well as demand. `miner` scores (0+1)x(1+1) = 2 on affinity alone;
    # `alchemist`'s single unit of demand is split four ways and its affinity
    # is 0, so it scores (1/4+1)x1 = 1.25. Without the skip the character takes
    # `miner` straight back and churns on it forever, one lap per dwell.
    leases = _held(alchemist=("A", "B", "C"))
    demand = {"alchemist": 1}
    assert _decide(None, 0, leases, demand, skill_levels=_STUCK_MINER).claim == "miner"
    assert _decide(None, 0, leases, demand, idle_released=frozenset({"miner"}),
                   skill_levels=_STUCK_MINER).claim == "alchemist"


def test_the_narrowed_idle_release_still_terminates_in_a_stable_role() -> None:
    # The same scenario driven as a caller drives it. The character starts on
    # `miner`, which nothing needs; `alchemist` wants one unit, split three
    # ways. It releases `miner` after the dwell, is kept off it by
    # `idle_released`, lands on `alchemist`, and stays there -- two state
    # changes over 1400 cycles, not a lap every dwell.
    trajectory, state_changes = _run_cycles(
        _held(alchemist=("A", "B", "C")), {"alchemist": 1}, cycles=1400,
        start_current="miner", skill_levels=_STUCK_MINER)

    assert state_changes == 2
    assert set(trajectory[-1000:]) == {"alchemist"}


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

_LOR_LEASES = _held(alchemist=(_ME,))
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
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"miner": 3})
    assert d.release == "logger"
    assert d.unservable is False


def test_a_margin_release_is_not_flagged_unservable() -> None:
    # Losing a demand-margin contest says nothing about capability — the role
    # was being served fine, a rival simply carries more demand.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
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


def test_a_character_with_no_levels_in_a_needed_role_still_claims_it() -> None:
    # PREFER, never forbid: hard-excluding an ill-suited role would leave the
    # fleet's only outstanding request unanswered whenever nobody trained for
    # it. `jeweler` is the sole role carrying demand and hero has zero
    # jewelrycrafting against mining 21 — it still claims `jeweler`.
    d = _decide(None, 0, {}, {"jeweler": 10}, skill_levels=_MINER)
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


def test_no_skill_reading_leaves_the_claim_ranked_by_demand_alone() -> None:
    # A character the caller has no `state.skills` for (the NO_SKILL_LEVELS
    # default) must behave exactly as it did before skill-awareness: uniform
    # affinity, so the claim is the effective-demand argmax and nothing else.
    # Split demand and raw demand disagree here on purpose -- miner's raw 30
    # leads, but two siblings are on it (10), so `logger`'s untouched 12 wins.
    demand = {"miner": 30, "logger": 12, "fisher": 4}
    leases = _held(miner=("C3P0", "R2D2"))
    assert _decide(None, 0, leases, demand).claim == "logger"
    assert _decide(None, 0, leases, demand, skill_levels=NO_SKILL_LEVELS).claim == "logger"


# --- The observed roster, 2026-08-03 ---
# Real levels off the live account. `mining` is the strongest skill for FOUR of
# the five characters, and under one exclusive `miner` lease that is not a
# tuning problem, it is arithmetic: four of them CANNOT have it.

_ROBBY = {"mining": 21, "alchemy": 16}
"""The account's best miner. It was serving `alchemist` (alchemy 16), because
`HAL` (mining 12) won the startup race for the single `miner` lease and
`_best_free_role` skipped every leased role outright."""

_LIVE_DEMAND = {"miner": 40, "logger": 10, "alchemist": 6, "fisher": 4, "jeweler": 2}
"""Mining-led board, matching a roster whose bottleneck is ore and bars."""


def test_the_best_miner_serves_mining_even_though_a_sibling_already_mines() -> None:
    # THE OBSERVED DEFECT, and the exact input that produced it: HAL holds
    # `miner`, Robby is deciding. Splitting halves miner to 20, which with
    # Robby's perfect mining affinity scores (20+1)x2 = 42 -- far past
    # `alchemist`'s (6+1)x(1+16/21) = 12.33 and `logger`'s (10+1)x1 = 11.
    d = _decide(None, 0, _held(miner=("HAL",)), _LIVE_DEMAND, skill_levels=_ROBBY)
    assert d.claim == "miner"


def test_the_same_inputs_produced_the_alchemy_misallocation_under_exclusivity() -> None:
    # Pins WHY the scenario above is a fix and not a coincidence. Exclusivity is
    # simulated the only way it still can be -- by removing `miner` from the
    # catalog Robby may choose from, which is precisely what the old
    # "skip a role someone else holds" filter did. The same demand and the same
    # skills then hand Robby `alchemist`: the live misallocation, reproduced.
    without_miner = tuple(r for r in ROLE_CATALOG if r.name != "miner")
    d = decide_role(current=None, held_cycles=0, live_leases=_held(miner=("HAL",)),
                    demand_by_role=_LIVE_DEMAND, character="Robby",
                    catalog=without_miner, skill_levels=_ROBBY)
    assert d.claim == "alchemist"


def test_robby_leaves_alchemy_for_mining_once_it_may_join_a_held_role() -> None:
    # The migration path for a character ALREADY stuck where the old rule put
    # it: `alchemist`'s 6 is Robby's alone, `miner`'s 40 is shared with HAL
    # (20), and 20 >= 2 x 6 clears the switch margin. The release is not
    # flagged unservable -- Robby can serve alchemy fine, mining is simply
    # where the fleet needs it.
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES,
                _held(alchemist=(_ME,), miner=("HAL",)),
                _LIVE_DEMAND, skill_levels=_ROBBY)
    assert d.release == "alchemist"
    assert d.unservable is False


def test_skill_fit_does_not_reopen_the_margin_rule() -> None:
    # The hold/release side stays demand-driven: a well-suited rival role does
    # NOT pull a character off a role that is still carrying demand, because
    # skill fit says what this character could produce, not what the fleet needs.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
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


# --- The level gate: demand a character provably cannot serve ---------------
#
# Live 2026-08-03. `Lor` (mining 8) and `R2D2` (mining 9) both held `miner`
# while every unit of the account's iron demand gated at mining 10. R2D2
# eventually escaped via release-on-unservable — 25 cycles of the planner
# finding nothing — and became a productive `logger`. Lor never did, and was
# still parked on `miner` producing nothing. Routing on the producing SKILL
# alone cannot see the gap, and `_skill_affinity` cannot either: it divides by
# the character's OWN best skill, so mining 8 is a perfect 1.0 fit for `miner`
# when 8 is the best Lor has anywhere.
#
# Levels are the real ones off the account (the first `state.skills` of each
# character's 2026-08-03 play trace). The requirements are the real ones off
# the committed `gamedata_bundle.json`: `iron_rocks` is a mining-10 resource,
# so `iron_ore` gathers at 10, and `iron_bar`'s craft is mining 10.

_LOR_SKILLS = {"alchemy": 1, "cooking": 1, "fishing": 1, "gearcrafting": 5,
               "jewelrycrafting": 3, "mining": 8, "weaponcrafting": 1,
               "woodcutting": 5}
"""Lor, the character that stayed stuck. Mining 8 is its BEST skill anywhere,
which is exactly why affinity alone rated it a perfect `miner`."""

_ROBBY_SKILLS = {"alchemy": 16, "cooking": 12, "fishing": 4, "gearcrafting": 15,
                 "jewelrycrafting": 14, "mining": 21, "weaponcrafting": 10,
                 "woodcutting": 15}
"""Robby, the account's real miner. Mining 21 clears every iron gate."""

_IRON_DEMAND = {"iron_ore": 30, "iron_bar": 9}
_IRON_SKILL = {"iron_ore": "mining", "iron_bar": "mining"}
_IRON_LEVEL = {"iron_ore": 10, "iron_bar": 10}


def test_iron_demand_does_not_attract_lor_who_cannot_mine_it() -> None:
    # THE OBSERVED CASE. Every unit of iron demand gates at mining 10; Lor has
    # 8, so none of it counts toward `miner` and the role carries nothing.
    got = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                         _IRON_LEVEL, _LOR_SKILLS)
    assert got["miner"] == 0
    assert sum(got.values()) == 0


def test_iron_demand_still_attracts_robby_who_can_mine_it() -> None:
    # The other side, and the reason this is a gate and not a mute: the SAME
    # board reads at full strength for the character that can actually serve it.
    got = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                         _IRON_LEVEL, _ROBBY_SKILLS)
    assert got["miner"] == 39


def test_lor_claims_a_role_it_can_serve_instead_of_parking_on_miner() -> None:
    # End to end through the claim. Iron dominates the board 30:6, so before
    # the gate Lor took `miner` (mining 8 scores affinity 1.0 against its own
    # best skill) and sat there. With the iron gated out, `miner` scores at most
    # (0+1)x(1+1) = 2 and the ash_wood demand Lor's woodcutting 5 CAN serve wins.
    item_demand = {"iron_ore": 30, "ash_wood": 6}
    skill_of_item = {"iron_ore": "mining", "ash_wood": "woodcutting"}
    level_of_item = {"iron_ore": 10, "ash_wood": 1}
    by_role = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG,
                             level_of_item, _LOR_SKILLS)
    assert _decide(None, 0, {}, by_role, skill_levels=_LOR_SKILLS).claim == "logger"
    # Ungated, the same inputs hand Lor the role it cannot serve — the live bug.
    ungated = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG)
    assert _decide(None, 0, {}, ungated, skill_levels=_LOR_SKILLS).claim == "miner"


def test_a_role_carrying_both_servable_and_unservable_demand_keeps_the_servable() -> None:
    # Mixed demand on ONE role: copper gates at mining 1, iron at 10. Lor's
    # mining 8 serves the copper and not the iron, so `miner` attracts on the
    # copper alone rather than all-or-nothing in either direction.
    item_demand = {"copper_ore": 4, "iron_ore": 30}
    skill_of_item = {"copper_ore": "mining", "iron_ore": "mining"}
    level_of_item = {"copper_ore": 1, "iron_ore": 10}
    got = demand_by_role(item_demand, skill_of_item, ROLE_CATALOG,
                         level_of_item, _LOR_SKILLS)
    assert got["miner"] == 4


def test_an_item_with_no_known_requirement_still_counts() -> None:
    # No entry in `level_of_item` means the catalog exposes no requirement for
    # the item, NOT that it requires something unreachable. Refusing on an
    # unknown would silently starve the role, so it counts.
    got = demand_by_role({"iron_ore": 30, "mystery_ore": 7}, _IRON_SKILL | {
        "mystery_ore": "mining"}, ROLE_CATALOG, _IRON_LEVEL, _LOR_SKILLS)
    assert got["miner"] == 7


def test_a_requirement_of_zero_gates_nothing() -> None:
    # `ItemStats.crafting_level` is 0 for an item the API records no craft
    # level for. Zero is a real requirement that every reading meets, so it
    # must pass the comparison rather than be special-cased into an unknown.
    got = demand_by_role({"trinket": 5}, {"trinket": "mining"}, ROLE_CATALOG,
                         {"trinket": 0}, {"mining": 0})
    assert got["miner"] == 5


def test_a_requirement_exactly_at_the_characters_level_is_servable() -> None:
    # The boundary itself: mining 10 serves a mining-10 gate. Off by one here
    # and R2D2 at mining 9 would look capable, or Robby at 21 would not.
    servable = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                              _IRON_LEVEL, {"mining": 10})
    walled = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                            _IRON_LEVEL, {"mining": 9})
    assert (servable["miner"], walled["miner"]) == (39, 0)


def test_no_skill_reading_leaves_demand_ungated() -> None:
    # The `NO_SKILL_LEVELS` caller: no reading for the producing skill is not
    # evidence of level 0, so nothing is gated and the aggregate is exactly the
    # pre-gate one. This is the path every single-character run takes.
    gated = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                           _IRON_LEVEL, NO_SKILL_LEVELS)
    assert gated == demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG)
    assert gated["miner"] == 39


def test_the_gate_defaults_are_empty_and_change_nothing() -> None:
    # No hidden default state, the same guarantee `NO_SKILL_LEVELS` carries for
    # `decide_role`: omitting both maps must equal passing the exported empties.
    assert demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG) == demand_by_role(
        _IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG, NO_ITEM_LEVELS, NO_SKILL_LEVELS)
    assert dict(NO_ITEM_LEVELS) == {}


def test_a_reading_for_another_skill_does_not_stand_in_for_the_producing_one() -> None:
    # `skill_levels` is read at the PRODUCING skill's key, never at whatever
    # else the character happens to have. Lor's gearcrafting 5 says nothing
    # about mining, and a lookup that fell back to any reading would leave the
    # gate answering a question about the wrong skill.
    got = demand_by_role(_IRON_DEMAND, _IRON_SKILL, ROLE_CATALOG,
                         _IRON_LEVEL, {"gearcrafting": 50})
    assert got["miner"] == 39  # no `mining` reading at all -> ungated, not walled


def test_serves_item_is_the_shared_predicate_both_readers_call() -> None:
    # Pinned directly, because `GamePlayer._pick_supply_target` reads it too and
    # the two must not drift (see its docstring). Each of the three verdicts.
    assert serves_item("iron_ore", "mining", _IRON_LEVEL, _ROBBY_SKILLS) is True
    assert serves_item("iron_ore", "mining", _IRON_LEVEL, _LOR_SKILLS) is False
    assert serves_item("iron_ore", "mining", {}, _LOR_SKILLS) is True
    assert serves_item("iron_ore", "mining", _IRON_LEVEL, {}) is True


# ---------------------------------------------------------------------------
# RoleDecision.reason — the rule that fired, named where it fired
#
# The TUI log renders a role transition as a discrete event, and the operator's
# first question about one is WHY. The caller cannot answer it: it sees
# `release="miner"` and would have to re-implement the branch it just called to
# tell idle from outranked. So the reason is written at each return, and every
# phrase is built only from arguments this function was given.
# ---------------------------------------------------------------------------

def test_a_claim_reports_the_demand_it_claimed_on() -> None:
    d = _decide(None, 0, {}, {"miner": 10, "logger": 3})
    assert d.claim == "miner"
    assert d.reason == "demand 10"


def test_no_claimable_role_says_so() -> None:
    # Every role blocked as unservable: nothing to claim, and the reason names
    # the eligibility wall rather than leaving the no-op unexplained.
    blocked = frozenset(role.name for role in ROLE_CATALOG)
    d = _decide(None, 0, {}, {"miner": 10}, unservable_released=blocked)
    assert (d.claim, d.keep, d.release) == (None, None, None)
    assert d.reason == "no claimable role"


def test_a_lapsed_lease_reclaim_says_the_lease_lapsed() -> None:
    d = _decide("miner", ROLE_MIN_HOLD_CYCLES, {}, {"miner": 10})
    assert d.claim == "miner"
    assert d.reason == "lease lapsed"


def test_the_min_hold_keep_reports_its_progress_through_the_dwell() -> None:
    d = _decide("miner", 7, _held(miner=(_ME,)), {"miner": 10})
    assert d.keep == "miner"
    assert d.reason == f"held 7/{ROLE_MIN_HOLD_CYCLES}"


def test_an_idle_release_reports_the_run_of_silent_cycles() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"miner": 3})
    assert d.release == "logger"
    assert d.reason == f"no demand for {ROLE_IDLE_DWELL_CYCLES} cycles"


def test_an_idle_keep_reports_the_run_so_far() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {},
                zero_demand_cycles=4)
    assert d.keep == "logger"
    assert d.reason == "idle 4 cycles"


def test_an_unservable_release_reports_the_demand_and_the_failed_run() -> None:
    d = _decide("alchemist", ROLE_MIN_HOLD_CYCLES, _LOR_LEASES, _LOR_DEMAND,
                unservable_cycles=ROLE_UNSERVABLE_CYCLES)
    assert d.release == "alchemist"
    assert d.reason == f"demand 40 unserved for {ROLE_UNSERVABLE_CYCLES} cycles"


def test_a_margin_release_reports_both_sides_of_the_comparison() -> None:
    # Exact `Fraction` arithmetic all the way to the string: the comparison is
    # a decision boundary and the log must show the numbers it was decided on.
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)),
                {"logger": 1, "miner": 100})
    assert d.release == "logger"
    assert d.reason == "outranked 100 vs 1"


def test_a_working_keep_reports_the_demand_it_is_serving() -> None:
    d = _decide("logger", ROLE_MIN_HOLD_CYCLES, _held(logger=(_ME,)), {"logger": 12})
    assert d.keep == "logger"
    assert d.reason == "demand 12"
