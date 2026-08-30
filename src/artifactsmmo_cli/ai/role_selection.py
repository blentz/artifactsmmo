"""Pure hysteresis core for role claim/hold/release.

ROLES ARE NOT EXCLUSIVE. Any number of characters may hold the same role at
once, and a role may have no holder at all: zero alchemists when nothing needs
alchemy, three loggers when woodcutting demand warrants three. Exclusivity was
a fixed five-way partition of the roster wearing demand's clothes, and live
2026-08-03 showed the bill — `mining` was the strongest skill for FOUR of five
characters, exactly one `miner` lease existed, and the three that lost the
startup race cascaded into roles they had no levels in (the account's best
miner, mining 21, was serving alchemy 16 because a mining-12 sibling had won
the lease first). Under a one-holder-per-role rule that is not a bug, it is
the construction.

The one thing exclusivity genuinely bought was a cap on pile-on, and DEMAND
SPLITTING replaces it: a role's demand, as seen by a character deciding
whether to serve it, is divided by one plus the number of OTHER characters
already holding it. The first holder sees the whole board, the second sees a
half, the third a third. Nothing is forbidden and no rank is reserved — a role
carrying genuinely large demand still out-scores a quiet one at three holders,
which is precisely the "three woodcutters" case, while a role with two holders
and modest demand stops attracting a fourth on its own weight. See
`_effective_demand`.

Three hysteresis parameters, each defending a different failure:

  * ROLE_MIN_HOLD_CYCLES — thrash between two near-equal roles. Sized from the
    2026-07-31 traces: characters ran 519-587 cycles per session and the copper
    phase alone was ~300 gathers, so a dwell shorter than a production run
    means switching mid-supply-chain and stranding half-made goods in a bag.
  * ROLE_SWITCH_MARGIN — oscillation from noise on the demand board. A RATIO,
    not an absolute delta: demand magnitudes span orders (progression_tree_core
    documents a live gain ratio of 18100:2000), so any fixed threshold is
    either always or never met.
  * release-on-idle — the hole where a character that finishes its role keeps
    renewing a lease nobody needs. Because it renews, the TTL never fires and
    the role stays locked for the whole session. Gated on a RUN of zero-demand
    observations (`ROLE_IDLE_DWELL_CYCLES`), never one sample: demand is
    published from the requester's chosen root, and a root that is not an
    `ObtainItem` publishes none, so a single-sample gate mistakes a momentary
    silence for a finished role.

  * release-on-UNSERVABLE (`ROLE_UNSERVABLE_CYCLES`) — the hole
    release-on-idle does NOT cover. A role can be held by a character that
    cannot do it. Live 2026-08-01: a level-1 character held `alchemist` while
    a level-21 sibling held `miner`. Release-on-idle cannot fire here — it
    triggers on demand reading ZERO, and this demand is positive, merely
    unservable. Non-exclusivity RE-FOUNDS this rule rather than retiring it:
    the old justification ("the lease is exclusive, so no sibling may take
    over") is gone, but an incapable holder now does something exclusivity
    never let it do — it counts toward the role's holder count and DIVIDES the
    demand every capable sibling sees for it, damping the exact signal that
    would recruit one. Sitting on a role you cannot serve went from blocking
    to actively misinforming.

    It stays, but it is no longer the FIRST line of defence. Release-on-
    unservable is REACTIVE — 25 cycles of the planner finding nothing — and
    most of what it caught was knowable before the first one: live 2026-08-03,
    `Lor` (mining 8) held `miner` against iron demand every unit of which gates
    at mining 10. `demand_by_role` now drops demand this character provably
    cannot serve, so that case never recruits it at all. What is left for this
    rule is the genuinely surprising failure — a plan that dies for a reason no
    level requirement predicts — which is the only thing 25 cycles of evidence
    were ever the right way to learn.

Release-on-idle is NARROWED to the case that motivates it, and the narrowing
is what stops the rule from being pure churn. Its original justification —
"a finished role must be freed so a sibling can take it" — died with
exclusivity: nobody is ever blocked from a role now, so freeing one grants no
sibling anything it did not already have. What survives is the OTHER half:
a character parked on a dead role is not serving the roles that are alive, so
release-on-idle is the only rule that can move it (the `ROLE_SWITCH_MARGIN`
scan below is only reached when the held role's own demand is POSITIVE, so it
cannot). That reason is entirely about the destination, so the rule is now
gated on one existing: an idle role is released only when some role this
character could actually claim carries positive demand. On an all-zero board
the character keeps what it has instead of walking the whole catalog one
`ROLE_MIN_HOLD_CYCLES` dwell at a time, claiming and releasing five roles to
serve nothing (~505 cycles of DB writes on the DEFAULT shape of a quiet
board). See `decide_role`.

A fourth failure surfaced in review of the first three: release-on-idle, taken
alone, can cause infinite claim/release CHURN rather than a stable release.
The character releases its role and immediately re-claims the same one next
cycle, because the claim ranks on effective demand AND skill affinity, and
affinity is a fixed property of the character — a strong fit for the dead role
can out-score a weak fit for the live one that triggered the release (a role
at zero demand scores up to 2, and a role whose demand is split across several
holders can score less than that). It then holds ROLE_MIN_HOLD_CYCLES,
releases again, and repeats forever. `decide_role`'s `idle_released` parameter
closes this: the CALLER remembers which roles it has voluntarily released
while idle, and a role in that set is not claimable again until its own demand
turns positive. See `decide_role`'s docstring for why this must be a
parameter, not module state.

Pure: no I/O, no clock, no classes beyond the frozen result record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction
from types import MappingProxyType

from artifactsmmo_cli.ai.role_catalog import Role, role_skill_level, role_skills

NO_SKILL_LEVELS: Mapping[str, int] = MappingProxyType({})
"""The "caller supplied no skill reading" default for `skill_levels`.

Read-only so the shared default can never be mutated by a caller, and empty so
`_skill_affinity` gives every role the SAME affinity — which makes the claim
fall back to demand alone, exactly the pre-skill-awareness ranking."""

NO_ITEM_LEVELS: Mapping[str, int] = MappingProxyType({})
"""The "caller knows no item level requirements" default for `level_of_item`.

Separate constant from `NO_SKILL_LEVELS` despite the identical value: they are
read by `serves_item` as two INDEPENDENT unknowns (what the item demands, what
the character has), and either one being absent is enough to leave the demand
ungated. Collapsing them into one name would tie two defaults that must be
allowed to move apart."""

ROLE_MIN_HOLD_CYCLES = 100
"""Cycles a role must be held before it may be voluntarily released."""

ROLE_SWITCH_MARGIN = Fraction(2)
"""A rival role must carry this multiple of the current role's unmet demand.

Both sides of the comparison are now EFFECTIVE demand — split by holder count
(`_effective_demand`) — rather than raw. Comparing raw demand would make the
margin blind to the only thing that changed: a role with 1000 raw demand and
four holders is already being worked on by four characters and is a far worse
place to go than a role with 300 and none. Splitting both sides is also what
makes joining a crowded role self-limiting rather than a one-way ratchet — a
character's own share shrinks as siblings pile in behind it, so the margin
eventually points back out."""

ROLE_IDLE_WINDOW = 100
"""Observations of a held role's own demand that must be on record before the
role can be released as idle, and the window the idle RATE is measured over.

Release-on-idle shipped as a SINGLE-SAMPLE read, which is not what it defends
against. A character publishes demand from `closure_demand` of its CHOSEN
ROOT, and a root that is not an `ObtainItem` (a level root, a task root)
publishes nothing at all — `publish_demand` replaces the row wholesale, so
that character's demand row goes to zero for as long as it stays on such a
root. Measured over the 39 live `play-trace-*.jsonl` sessions: 4.8% of 8765
cycles carried a non-`ObtainItem` step, but they arrive in RUNS, and the runs
are long and CORRELATED across the roster (two characters in the same session
both ran ~60 consecutive such cycles; the longest single run was 140). A
one-sample gate fires on every one of those runs, releasing a role a sibling
genuinely needs.

100 is the same window as `ROLE_MIN_HOLD_CYCLES`, and that is the spec's own
wording ("stays zero for a full dwell window"). A partial window never
releases: three zeros out of three observations is 100% idle and no evidence at
all, and releasing on it is the single-sample failure by another name."""

ROLE_IDLE_FRACTION = Fraction(9, 10)
"""Share of the window that must read ZERO for the role to count as idle.

A RATE, NOT A CONSECUTIVE RUN, and the difference is the whole point. The run
form left a held role with NO EXIT under flickering demand: the margin scan
below is reached only on positive own demand, so on a zero cycle it cannot
run, and any single positive cycle reset the run to zero — so a role whose
demand blipped positive once per hundred cycles could never be released however
much better a rival was.

MEASURED LIVE 2026-08-30, which is what this replaces: all five characters held
`logger` while `miner` carried 64 against their own logger share of 2.4 — a 26x
rival — and `decide_role` returned `keep` with reason `idle 0 cycles` for every
one of them. The counter was at 0 because a blip had just reset it. A full
4-hour session (205-245 cycles per character, twice the dwell) recorded not one
role change.

9/10 rather than 1: the defence is against a role that is genuinely being asked
for going quiet, and a role answering one request in ten is not that. It sits
above the observed silence structure — the longest measured run of publishing
cycles inside an otherwise idle stretch is far short of a tenth of the window —
while a role in real use (the anti-churn case, half the window positive) stays
held. Exact `Fraction`, never a float: this is a decision boundary, and
`idle_zeros >= 9/10 * idle_samples` must compare reproducibly.

`ROLE_IDLE_DWELL_CYCLES` is GONE rather than redefined. Its name says
"consecutive" and its meaning is now "of the last hundred", and a constant that
quietly changes what it counts is the drift this module documents everywhere
else."""

ROLE_UNSERVABLE_CYCLES = 25
"""Consecutive cycles a held role's POSITIVE demand must go unserved before the
role is released as unservable.

WHY A SEPARATE, SHORTER RUN THAN `ROLE_IDLE_DWELL_CYCLES` (100). The two
counters answer different questions and are exposed to different noise:

  * The idle counter measures an ABSENCE — no demand was published. Absence is
    produced in long, roster-correlated RUNS by a perfectly healthy sibling that
    happens to sit on a non-`ObtainItem` root (measured runs up to 140 cycles),
    so the threshold has to sit above that noise or it fires constantly.
  * This counter measures POSITIVE EVIDENCE — the arbiter built this
    character's `SupplyBankGoal`, searched for a plan, and came back with none.
    Its noise is per-cycle and independent (a cheap-budget timeout on a plan the
    full budget would find, a momentarily unreachable ingredient), not
    run-structured, and it only advances on cycles where the goal was ACTUALLY
    attempted — a cycle where a guard preempted selection contributes nothing
    either way. 25 consecutive independent failed searches is decisive.

WHY NOT LONGER. Under exclusivity the answer was that the whole fleet's demand
for these skills sat parked behind one character that could not serve it. That
argument died with the exclusive lease — a capable sibling can now join the
role without waiting for anyone. What did NOT die is milder and still real:
every cycle an incapable holder stays, it divides the role's advertised demand
for every character weighing it (see `_effective_demand`), so the fleet is told
the role is better covered than it is. At 100 the misinformation would stand
for a fifth of a traced session (519-587 cycles); 25 caps it at ~5%. The
constant is UNCHANGED — its lower bound (25 consecutive independent failed
searches is decisive) never depended on exclusivity, and re-tuning a measured
threshold on a changed rationale with no new measurement would be guessing.

25 <= ROLE_MIN_HOLD_CYCLES, which is the same inequality
`ROLE_IDLE_DWELL_CYCLES` relies on and for the same reason: the run is only
consulted once `held_cycles >= ROLE_MIN_HOLD_CYCLES`, and that counter restarts
on every claim, so a run carried across a re-claim can never be the binding
constraint. Pinned by a test."""


@dataclass(frozen=True)
class RoleDecision:
    """Exactly one of keep/claim/release is non-None, or all three are None
    (nothing to do). Pure data; exempt from one-class-per-file.

    `unservable` is not a fourth outcome — it QUALIFIES a release, telling the
    caller WHY the role was given up. The caller has to know: an unservable
    release must also block this character from re-claiming the role (the
    demand that triggered it is still positive, so the `idle_released` rule,
    which only skips a role while its demand is non-positive, would let it
    re-claim on the very next cycle). Returning the reason here keeps
    `ROLE_UNSERVABLE_CYCLES`'s threshold in ONE place instead of having the
    caller re-derive the verdict from its own counter.

    `reason` is the same argument carried one step further, for a reader rather
    than for control flow: a short human phrase naming the rule that fired and
    the numbers it fired on. Written at each `return` below, because that is
    the only place the rule is known — the caller sees `release="miner"` and
    cannot tell idle from outranked without re-implementing the branch it just
    called, which is exactly the two-copies-of-three-lines drift `_claimable`
    exists to prevent. It does NOT duplicate `unservable`: that is a boolean the
    caller ACTS on, this is prose carrying counters the boolean cannot hold, and
    nothing branches on it.

    Every phrase is built from arguments this function was given. Nothing here
    infers a cause it was not told (e.g. WHICH item's demand moved the board, or
    which level gate dropped it) — that lives in `demand_by_role`'s inputs and
    is not reconstructible from the aggregate."""

    keep: str | None = None
    claim: str | None = None
    release: str | None = None
    unservable: bool = False
    reason: str = ""


def _skill_affinity(catalog: tuple[Role, ...],
                    skill_levels: Mapping[str, int]) -> dict[str, Fraction]:
    """How well this character's invested skill levels fit each role, in [0, 1].

    RELATIVE, not absolute: each role's best owned skill level over the best
    level the character has in ANY role's skills. A level-21 miner scores 1 for
    `miner` and 1/21 for the roles it never trained; a fresh character with
    every skill at the level-1 floor scores 1 everywhere, which is the same as
    expressing no preference at all. That is deliberate — affinity must be a
    statement about THIS character's own investment, and normalizing against an
    absolute cap would make every low-level character look like a bad fit for
    everything and let the tie fall to catalog order forever.

    `skill_levels` empty (the `NO_SKILL_LEVELS` default, and every caller that
    has no reading) yields a uniform 1, so the claim ranks by demand exactly as
    it did before skill-awareness existed."""
    best = max((role_skill_level(role, skill_levels) for role in catalog), default=0)
    if best <= 0:
        return {role.name: Fraction(1) for role in catalog}
    return {role.name: Fraction(role_skill_level(role, skill_levels), best)
            for role in catalog}


def _effective_demand(demand_by_role: Mapping[str, int], role_name: str,
                      live_leases: Mapping[str, frozenset[str]],
                      character: str) -> Fraction:
    """`role_name`'s demand as THIS character should read it: the raw board
    figure divided by one plus the number of OTHER characters already holding
    the role.

    This is the whole replacement for exclusivity. A role is never unavailable,
    so nothing stops a pile-on except the shrinking return of joining one: the
    first character to weigh a role sees its full demand, a second sees a half,
    a third a third, and the series falls away fast enough that a quiet role
    out-scores a crowded one long before the roster runs out. It is not a cap —
    a role carrying eight times another's demand still wins at four holders,
    which is exactly the "sometimes we need three woodcutters" case the fixed
    partition could not express.

    OTHER characters, not all holders: a character weighing the role it already
    holds must see the same figure it would see as a newcomer, or `decide_role`
    would compare its own role against rivals on a scale its own membership had
    shrunk, and every holder would want to leave the moment it arrived.

    Exact `Fraction`, never float: this is a decision boundary (`>=
    ROLE_SWITCH_MARGIN`, `>` on scores), and 100/3 must compare reproducibly
    rather than to whatever the last bit of a double happens to say. Negative
    raw demand cannot occur — `publish_demand` drops non-positive rows and
    `demand_by_role` sums — and is not defended against here, because clamping
    would hide a corrupted board instead of letting it read as the zero it is.
    """
    others = len(live_leases.get(role_name, frozenset()) - {character})
    return Fraction(demand_by_role.get(role_name, 0), others + 1)


def _claimable(role_name: str, demand_by_role: Mapping[str, int],
               idle_released: frozenset[str],
               unservable_released: frozenset[str]) -> bool:
    """Whether this character may take `role_name` at all this cycle.

    THE eligibility rule, and deliberately the ONLY one: every part of the
    decision that weighs a role other than the one being held reads it — the
    claim ranking (`_best_role`) and the rival scan inside `decide_role`. The
    two used to disagree. The ranking skipped the released sets and the scan
    did not, so a character could give up its role because some rival looked
    better on the board and then be refused that very rival on the next cycle,
    landing somewhere worse and repeating the lap every `ROLE_MIN_HOLD_CYCLES`.
    One predicate with two readers cannot drift back apart; two copies of the
    same three lines can, and did.

    `unservable_released` is unconditional: the role was given up BECAUSE its
    demand was positive and this character could not serve it, so positive
    demand is precisely the wrong signal to re-open it on. The caller owns when
    that set shrinks (see `decide_role`).

    `idle_released` is conditional on the role's own demand still being
    non-positive — it was given up as FINISHED, and real demand un-finishes it.

    That conditionality makes the `idle_released` half arithmetically INERT in
    the rival scan, and it is still read there on purpose. A role it skips has
    non-positive demand, hence a zero share, and a zero share can never clear
    `own_share * ROLE_SWITCH_MARGIN` on the only path that scan is compared on
    (`own_demand > 0`, so `own_share > 0`); it can never be the positive rival
    the idle rule looks for either. Reading the whole predicate anyway costs
    one comparison over five roles and removes the drift, whereas a rival scan
    that filtered on `unservable_released` alone would be a second, subtly
    different copy of the rule — the exact defect this function exists to
    close."""
    if role_name in unservable_released:
        return False
    return role_name not in idle_released or demand_by_role.get(role_name, 0) > 0


def _best_role(live_leases: Mapping[str, frozenset[str]],
               demand_by_role: Mapping[str, int],
               character: str, catalog: tuple[Role, ...],
               idle_released: frozenset[str],
               unservable_released: frozenset[str],
               skill_levels: Mapping[str, int]) -> str | None:
    """The best role for this character to serve, or None if it may serve none.

    Not "best FREE role" any more — no role is ever taken. Every catalog entry
    is a candidate on every cycle; what used to be a hard skip for a role a
    sibling held is now a division of that role's demand by its holder count
    (`_effective_demand`).

    SCORE = (effective demand + 1) x (1 + affinity). Demand and skill fit BOTH
    matter, so neither may be a filter:

      * Skill fit cannot veto. Affinity maxes out at 1, so it can at most DOUBLE
        a role's effective demand — a role carrying more than twice the demand
        still wins on demand alone, and a character with no relevant levels
        anywhere still claims SOMETHING (every role scores, none is excluded).
        A hard "only roles you have levels for" filter would leave a fresh
        character permanently unspecialized, which is the opposite of the goal.
      * Demand cannot veto either, which is what the `+ 1` buys: at demand 0
        every role would otherwise score 0 and the tie would fall to catalog
        order, so a character would claim `miner` at cold start no matter what
        it had actually trained. With the offset, a quiet board still ranks by
        fit while a single unit of real demand elsewhere already outweighs a
        one-step fit advantage.

    The offset is also what makes "a role nobody needs attracts nobody" true
    rather than merely likely: a zero-demand role scores at most (0+1)x(1+1) =
    2, and any role carrying two or more units of effective demand scores at
    least 3, so no amount of skill fit can pull a character onto a role the
    fleet is silent about while a real request is outstanding.

    Ties are resolved by catalog order — a declared, semantic order, never a
    repr or alphabetical sort. Ties are harmless in a way they were not under
    exclusivity: two characters agreeing on the same role is now a legal
    outcome, not a race one of them has to lose.

    Which roles are candidates at all is `_claimable`'s business, not this
    function's — the same predicate `decide_role`'s rival scan reads, so a
    rival that can trigger a release is always a rival that can be claimed."""
    affinity = _skill_affinity(catalog, skill_levels)
    best: str | None = None
    # Sentinel below every reachable score: effective demand is never negative,
    # so the lowest real score is (0 + 1) x (1 + 0) = 1. A separate
    # `best is None` guard would be a second, unobservable test of the same
    # condition.
    best_score = Fraction(-1)
    for role in catalog:
        if not _claimable(role.name, demand_by_role, idle_released, unservable_released):
            continue
        share = _effective_demand(demand_by_role, role.name, live_leases, character)
        score = (share + 1) * (1 + affinity[role.name])
        if score > best_score:
            best, best_score = role.name, score
    return best


def decide_role(current: str | None, held_cycles: int,
                live_leases: Mapping[str, frozenset[str]],
                demand_by_role: Mapping[str, int],
                character: str, catalog: tuple[Role, ...],
                idle_released: frozenset[str] = frozenset(),
                idle_zeros: int = 0,
                idle_samples: int = 0,
                unservable_released: frozenset[str] = frozenset(),
                unservable_cycles: int = 0,
                skill_levels: Mapping[str, int] = NO_SKILL_LEVELS) -> RoleDecision:
    """Decide whether to keep, claim, or release a role this cycle.

    `idle_zeros` / `idle_samples`: of the last `ROLE_IDLE_WINDOW` observations
    of `demand_by_role[current]` the caller has taken, how many read at or below
    zero, and how many observations there are. Release-on-idle needs EVIDENCE,
    not a sample: a requester that happens to be on a level root this cycle
    publishes no demand at all, and on the real traced roster that is 4.8% of
    cycles arriving in runs up to 140 long, so a single-sample release drops a
    role that is genuinely needed.

    A RATE, NOT A RUN, and that is a fix rather than a refinement: a
    consecutive-run gate is reset by one positive cycle, so a role with
    flickering demand could never be released while the margin scan below —
    reachable only on POSITIVE own demand — could never run either. Live
    2026-08-30, five characters held `logger` at a 26x disadvantage to `miner`
    with the reason `idle 0 cycles`. See `ROLE_IDLE_FRACTION`.

    Like `idle_released`, the WINDOW is the caller's to own — this function
    stays pure (no I/O, no clock, no module-level state) — and the caller clears
    it when the role changes. The defaults of 0 mean "nothing observed yet", so
    a caller that does not track them never releases on idle.

    A full window is NECESSARY but not SUFFICIENT: the idle release also requires
    an eligible rival role carrying positive demand. Exclusivity used to supply
    the other half of the justification (free the role so a sibling may have
    it), and that half is gone -- no sibling is blocked from any role now. What
    remains is only worth a release when there is a live role to move to; with
    the whole board silent, releasing serves nobody, and the character would
    claim, hold, and release its way through the entire catalog to end up
    exactly as idle as it started.

    `idle_released`: roles THIS caller has previously released while idle
    (demand was non-positive at release time). Without it a character can
    re-claim the very role it just released on the next cycle, because the
    claim ranks on skill affinity as well as demand and a strong fit for the
    dead role can out-score a weak fit for the live one whose demand triggered
    the release -- release-on-idle alone is then claim/release CHURN, not a
    stable release. The caller owns this set
    (decide_role stays pure: no I/O, no clock, no module-level state); it adds
    a role on every `release` this function returns and never needs to remove
    one for correctness, because a role's presence in the set only matters
    while its demand is non-positive -- once demand turns positive,
    `_claimable` stops skipping it automatically.

    `unservable_cycles`: how many CONSECUTIVE cycles -- including this one --
    the caller has observed the held role's POSITIVE demand go unserved. Owned
    by the caller for the third time and for the same reason: the observation
    is an I/O-shaped fact (did the planner find a plan for this cycle's supply
    goal?) and this function is pure. The default of 0 means "no run recorded",
    so a caller that does not track it never releases on unservability.

    `unservable_released`: roles this caller released as UNSERVABLE and must
    not re-claim. Separate from `idle_released` because the two need OPPOSITE
    re-entry rules: an idle-released role re-opens the moment its demand turns
    positive, whereas an unservable-released role was given up WITH positive
    demand, so that same signal must not re-open it. The caller decides when to
    drop a role from this set -- `GamePlayer` drops it when the character's
    level in one of the role's own skills has RISEN since the release, i.e.
    when the verdict "I cannot serve this" could have changed. Note the role
    itself is released from the shared lease either way, so a better-suited
    sibling can take it immediately; only this character is held back.

    `live_leases`: `{role: {holder, ...}}` — every holder of every role, not
    one holder per role. Roles are not exclusive, so a single holder can no
    longer describe the board, and the COUNT is what the whole allocation now
    rests on (`_effective_demand`). A role with no live holder is absent from
    the mapping, so read it with `.get(name, frozenset())`.

    `skill_levels`: this character's skill -> level map (the caller's
    `state.skills`). Used ONLY to bias the claim (see `_best_role`); the
    hold/release rules stay demand-driven, because skill fit is a statement
    about what this character could produce, not about what the fleet needs."""
    if current is None:
        best = _best_role(live_leases, demand_by_role, character, catalog,
                          idle_released, unservable_released, skill_levels)
        if best is None:
            return RoleDecision(reason="no claimable role")
        return RoleDecision(claim=best,
                            reason=f"demand {demand_by_role.get(best, 0)}")

    if character not in live_leases.get(current, frozenset()):
        # Our lease lapsed — the TTL expired during a stall and nothing renewed
        # it. A sibling can no longer take a role FROM us (its own claim writes
        # its own row and leaves ours alone), so this is now purely a liveness
        # fact about our own row. Re-claim rather than assume we still hold it:
        # every sibling reads holder counts off this table, and a character
        # supplying for a role with no live row is invisible to all of them.
        return RoleDecision(claim=current, reason="lease lapsed")

    if held_cycles < ROLE_MIN_HOLD_CYCLES:
        return RoleDecision(keep=current,
                            reason=f"held {held_cycles}/{ROLE_MIN_HOLD_CYCLES}")

    # ONE scan over the rivals, feeding BOTH release rules below. A rival a
    # sibling holds is not off-limits, it is merely already partly served,
    # which the EFFECTIVE-demand division already says; a rival this character
    # could not claim (`_claimable`) is excluded outright, because a release it
    # triggered would be answered next cycle by a claim that is refused it.
    #
    # Sentinel below every reachable share (never negative), so a scan that
    # finds no eligible rival at all can neither clear the margin nor read as
    # somewhere to go.
    rival_best = Fraction(-1)
    for role in catalog:
        if role.name == current:
            continue
        if not _claimable(role.name, demand_by_role, idle_released, unservable_released):
            continue
        rival_best = max(
            rival_best,
            _effective_demand(demand_by_role, role.name, live_leases, character))

    # RAW, not split. "Is anyone asking for this role's output at all" is a
    # property of the board, not of how many characters serve it, and splitting
    # cannot change the answer anyway: a positive demand stays positive over
    # any holder count, and zero stays zero. Using the share here would read as
    # if crowding could make a role idle, which it cannot.
    own_demand = demand_by_role.get(current, 0)
    if own_demand <= 0:
        # Release-on-idle, gated on there being SOMEWHERE TO GO. `rival_best >
        # 0` is exactly "some role this character could claim carries positive
        # demand" -- splitting divides by a positive integer, so a share is
        # positive precisely when its raw demand is.
        #
        # The gate is the whole rule's justification made into a condition.
        # Freeing a finished role no longer helps a sibling (nobody is blocked
        # from a role any more); the one thing a release still buys is moving
        # THIS character off a dead role onto a live one, and the margin scan
        # below cannot do it because it is only reached on positive own demand.
        # With no live role anywhere, releasing serves nothing and costs a
        # claim, a hold, and another release per role -- on an all-zero board
        # that walked the entire catalog before settling.
        # A RATE over a full window, never a consecutive run. The run form had
        # no exit under flickering demand — see `ROLE_IDLE_FRACTION` for the
        # live measurement that replaced it. A partial window is no evidence
        # and never releases.
        if (idle_samples >= ROLE_IDLE_WINDOW
                and idle_zeros >= ROLE_IDLE_FRACTION * idle_samples
                and rival_best > 0):
            return RoleDecision(
                release=current,
                reason=f"no demand in {idle_zeros} of {idle_samples} cycles")
        # Idle with nowhere better, or not idle ENOUGH to be sure: a requester
        # on a level root is momentarily silent, not finished.
        return RoleDecision(keep=current,
                            reason=f"idle {idle_zeros}/{idle_samples} cycles")

    # Positive demand from here down. A role whose demand exists but has gone
    # unserved for a full run is worse than an idle one: this character counts
    # as a holder, so it is dividing the role's advertised demand for every
    # capable sibling weighing it while producing nothing itself. Decided
    # BEFORE the margin comparison because it is not a comparison against a
    # rival -- there may be no eligible rival at all, and the release is still
    # the right move.
    if unservable_cycles >= ROLE_UNSERVABLE_CYCLES:
        return RoleDecision(release=current, unservable=True,
                            reason=f"demand {own_demand} unserved for "
                                   f"{unservable_cycles} cycles")

    # Our own side is split the same way the rivals are -- `_effective_demand`
    # counts only OTHER holders, so a role we hold alone reads at full strength
    # and one we share reads at our real share.
    own_share = _effective_demand(demand_by_role, current, live_leases, character)
    if rival_best >= own_share * ROLE_SWITCH_MARGIN:
        return RoleDecision(release=current,
                            reason=f"outranked {rival_best} vs {own_share}")
    return RoleDecision(keep=current, reason=f"demand {own_demand}")


def serves_item(item_code: str, skill: str,
                level_of_item: Mapping[str, int],
                skill_levels: Mapping[str, int]) -> bool:
    """Whether a character at `skill_levels` can produce `item_code` at all,
    given that `skill` is what produces it.

    THE one level gate, with three readers -- `demand_by_role` here,
    `GamePlayer._pick_supply_target`, and the self-servable computation in
    `GamePlayer._update_coordination`. They must agree: role demand says WHICH
    role to serve, the supply target says WHICH ITEM to make for it, and the
    self-servable flag says whether the ASKER could have made it itself, so a
    role recruited on servable demand that then targets an unservable item is
    the same stall by a longer route -- and a request published as asymmetric
    that no consumer can select is the same stall with nobody even trying.
    `_claimable`'s lesson, applied to a third reader: two copies of three lines
    drift, and did.

    Both unknowns default to SERVABLE, and neither default is a guess:

      * No requirement recorded for the item (`level_of_item` has no entry).
        Refusing on an unknown requirement would starve a role of demand the
        character may well be able to serve, on no evidence at all -- inventing
        a gate is exactly as wrong as inventing a level.
      * No reading for the producing skill (`skill_levels` has no entry). This
        is the `NO_SKILL_LEVELS` caller, and it must rank by demand alone,
        exactly as it did before any of this existed. A live character never
        takes this path: `WorldState.skills` carries every trainable skill off
        the character schema, so absence really does mean "no reading", never
        "level 0".

    Level 0 is not special-cased: a recorded requirement of 0 is met by any
    reading, which is what a requirement of 0 means."""
    required = level_of_item.get(item_code)
    if required is None:
        return True
    owned = skill_levels.get(skill)
    if owned is None:
        return True
    return owned >= required


def demand_by_role(item_demand: Mapping[str, int],
                   skill_of_item: Mapping[str, str | None],
                   catalog: tuple[Role, ...],
                   level_of_item: Mapping[str, int] = NO_ITEM_LEVELS,
                   skill_levels: Mapping[str, int] = NO_SKILL_LEVELS) -> dict[str, int]:
    """Aggregate item-keyed demand into role-keyed demand, AS ONE CHARACTER
    SHOULD READ IT.

    `skill_of_item` maps an item code to the skill that PRODUCES it (its craft
    skill, or its gathering skill for a raw resource), or None when the API
    exposes no producing skill -- in which case no role owns it and the demand
    is dropped rather than assigned to an arbitrary role.

    PER-CHARACTER, not a shared board. `level_of_item` (the level the producing
    skill must reach) and `skill_levels` (this character's own levels) turn the
    result from "what the fleet wants" into "what the fleet wants THAT I COULD
    PRODUCE", and demand this character cannot serve is dropped rather than
    counted toward its attraction to the role. Live 2026-08-03: `iron_rocks` /
    `iron_ore` / `iron_bar` all gate at mining 10, `Lor` had mining 8 and `R2D2`
    9, and both were nonetheless recruited to `miner` by the account's iron
    demand and parked there producing nothing. Routing on the producing SKILL
    alone cannot see that, and `_skill_affinity` cannot either -- it measures a
    character against its OWN best skill, so mining 8 scores a perfect 1.0 for
    `miner` when 8 is the best that character has anywhere.

    This does NOT retire release-on-unservable (`ROLE_UNSERVABLE_CYCLES`),
    which still covers the plan that fails for reasons no level gate predicts.
    It removes the 25 wasted cycles for the case that WAS predictable: the
    requirement is in the item catalog and the level is on the character.

    Nothing is gated when the caller supplies neither map (the defaults), so a
    caller with no readings gets the pre-existing demand-only aggregate --
    see `serves_item` for why both unknowns read as servable.

    All four maps are passed in rather than derived from GameData so this
    module stays pure and testable without a game-data fixture."""
    totals = {role.name: 0 for role in catalog}
    owner: dict[str, str] = {}
    for role in catalog:
        for owned_skill in role_skills(role):
            owner[owned_skill] = role.name
    for item_code, quantity in item_demand.items():
        skill = skill_of_item.get(item_code)
        if skill is None:
            continue
        role_name = owner.get(skill)
        if role_name is None:
            continue
        if not serves_item(item_code, skill, level_of_item, skill_levels):
            continue
        totals[role_name] += quantity
    return totals
