"""Pure hysteresis core for role claim/hold/release.

Three parameters, each defending a different failure:

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
    cannot do it: the lease is exclusive, so every request for that role's
    skills routes to the holder by design, and if the holder cannot produce
    what was asked, the demand is never served and no sibling may take over.
    Live 2026-08-01: a level-1 character held `alchemist` while a level-21
    sibling held `miner`. Release-on-idle cannot fire here — it triggers on
    demand reading ZERO, and this demand is positive, merely unservable.

A fourth failure surfaced in review of the first three: release-on-idle, taken
alone, can cause infinite claim/release CHURN rather than a stable release.
When demand is all-zero and only one role is unleased, an idle character
releases it (nothing needs it), immediately re-claims it next cycle (it is
still the only free role), holds ROLE_MIN_HOLD_CYCLES, releases again, and
repeats forever — the role never actually frees up for anyone, and the
character never rests. `decide_role`'s `idle_released` parameter closes this:
the CALLER remembers which roles it has voluntarily released while idle, and
a role in that set is not claimable again until its own demand turns
positive. See `decide_role`'s docstring for why this must be a parameter, not
module state.

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

ROLE_MIN_HOLD_CYCLES = 100
"""Cycles a role must be held before it may be voluntarily released."""

ROLE_SWITCH_MARGIN = Fraction(2)
"""A rival role must carry this multiple of the current role's unmet demand."""

ROLE_IDLE_DWELL_CYCLES = 100
"""Consecutive cycles a held role's own demand must read ZERO before the role
is released as idle.

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
wording ("stays zero for a full dwell window"): a role must be held for a
dwell window before it may be released, and its demand must have read zero for
a dwell window as well. It sits above every observed run but the 140-cycle
one, and clearing that outlier too would push the release threshold past a
whole session (519-587 cycles) and make the mechanism dead. The residual is
benign by construction: a role released during a genuinely long idle stretch
is re-claimable the instant its demand turns positive again, because
`_best_free_role` only skips an `idle_released` role WHILE its demand is
non-positive."""

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

WHY NOT LONGER. Every cycle of this run is a cycle in which the whole fleet's
demand for these skills is parked behind one character that cannot serve it. At
100 the role would stay locked for a fifth of a traced session (519-587 cycles)
before anyone else could try; 25 caps that at ~5%.

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
    caller re-derive the verdict from its own counter."""

    keep: str | None = None
    claim: str | None = None
    release: str | None = None
    unservable: bool = False


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


def _best_free_role(live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                    character: str, catalog: tuple[Role, ...],
                    idle_released: frozenset[str],
                    unservable_released: frozenset[str],
                    skill_levels: Mapping[str, int]) -> tuple[str | None, int]:
    """Best-scoring role not leased by SOMEONE ELSE, with its raw demand.

    SCORE = (demand + 1) x (1 + affinity). Demand and skill fit BOTH matter, so
    neither may be a filter:

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

    Fractions, not floats: this is a decision, and an exact ratio makes the tie
    boundary reproducible rather than a rounding artifact.

    Ties are resolved by catalog order — a declared, semantic order, never a
    repr or alphabetical sort. Ties are also harmless: the UNIQUE constraint on
    RoleLease.role serializes concurrent claimants regardless, which is what
    makes the cold-start allocator converge on distinct roles.

    A role in `idle_released` is skipped, but ONLY while its demand is still
    non-positive — see `decide_role` for why. The moment real demand shows up
    for it, it competes for the claim like any other role again. A role in
    `unservable_released` is skipped UNCONDITIONALLY: it was given up BECAUSE
    its demand was positive and this character could not serve it, so positive
    demand is precisely the wrong signal to re-open it on. The caller owns when
    that set shrinks (see `decide_role`)."""
    affinity = _skill_affinity(catalog, skill_levels)
    best: str | None = None
    best_demand = 0
    # Sentinel below every reachable score, the same role the old `-1` played
    # for raw demand: role demand is a sum of published quantities and never
    # negative, so the lowest real score is (0 + 1) x (1 + 0) = 1. A separate
    # `best is None` guard would be a second, unobservable test of the same
    # condition.
    best_score = Fraction(-1)
    for role in catalog:
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        demand = demand_by_role.get(role.name, 0)
        if role.name in idle_released and demand <= 0:
            continue
        if role.name in unservable_released:
            continue
        score = (Fraction(demand) + 1) * (1 + affinity[role.name])
        if score > best_score:
            best, best_demand, best_score = role.name, demand, score
    return best, max(best_demand, 0)


def decide_role(current: str | None, held_cycles: int,
                live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                character: str, catalog: tuple[Role, ...],
                idle_released: frozenset[str] = frozenset(),
                zero_demand_cycles: int = 0,
                unservable_released: frozenset[str] = frozenset(),
                unservable_cycles: int = 0,
                skill_levels: Mapping[str, int] = NO_SKILL_LEVELS) -> RoleDecision:
    """Decide whether to keep, claim, or release a role this cycle.

    `zero_demand_cycles`: how many CONSECUTIVE cycles — including this one —
    the caller has observed `demand_by_role[current]` at or below zero.
    Release-on-idle needs a run, not a sample: a requester that happens to be
    on a level root this cycle publishes no demand at all, and on the real
    traced roster that is 4.8% of cycles arriving in runs up to 140 long, so a
    single-sample release drops a role that is genuinely needed (see
    `ROLE_IDLE_DWELL_CYCLES`). Like `idle_released`, the COUNTER is the
    caller's to own — this function stays pure (no I/O, no clock, no
    module-level state) — and the caller restarts it on any positive
    observation and while it holds no role at all. The default of 0 means "no
    run recorded yet", so a caller that does not track it never releases on
    idle.

    `idle_released`: roles THIS caller has previously released while idle
    (demand was non-positive at release time). Without it, a character with
    nowhere better to go re-claims the very role it just released on the next
    cycle -- release-on-idle alone produces claim/release CHURN, not a stable
    release, whenever it is the only unleased role. The caller owns this set
    (decide_role stays pure: no I/O, no clock, no module-level state); it adds
    a role on every `release` this function returns and never needs to remove
    one for correctness, because a role's presence in the set only matters
    while its demand is non-positive -- once demand turns positive,
    `_best_free_role` stops skipping it automatically.

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

    `skill_levels`: this character's skill -> level map (the caller's
    `state.skills`). Used ONLY to bias the claim (see `_best_free_role`); the
    hold/release rules stay demand-driven, because skill fit is a statement
    about what this character could produce, not about what the fleet needs."""
    if current is None:
        best, _ = _best_free_role(live_leases, demand_by_role, character, catalog,
                                  idle_released, unservable_released, skill_levels)
        return RoleDecision(claim=best) if best is not None else RoleDecision()

    if live_leases.get(current) != character:
        # Our lease lapsed (TTL expired during a stall) or a sibling took it.
        # Re-claim rather than assume we still hold it.
        return RoleDecision(claim=current)

    if held_cycles < ROLE_MIN_HOLD_CYCLES:
        return RoleDecision(keep=current)

    own_demand = demand_by_role.get(current, 0)
    if own_demand <= 0:
        if zero_demand_cycles >= ROLE_IDLE_DWELL_CYCLES:
            return RoleDecision(release=current)
        # Idle, but not for long enough to be sure. Hold the role: a
        # requester on a level root is momentarily silent, not finished.
        return RoleDecision(keep=current)

    # Positive demand from here down. A role whose demand exists but has gone
    # unserved for a full run is worse than an idle one: the exclusive lease
    # routes every request for these skills here, so nobody else can serve them
    # either. Checked BEFORE the margin scan because it is not a comparison
    # against a rival -- there may be no rival at all, and the release is still
    # the right move.
    if unservable_cycles >= ROLE_UNSERVABLE_CYCLES:
        return RoleDecision(release=current, unservable=True)

    rival_best = -1
    for role in catalog:
        if role.name == current:
            continue
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        rival_best = max(rival_best, demand_by_role.get(role.name, 0))

    if rival_best >= own_demand * ROLE_SWITCH_MARGIN:
        return RoleDecision(release=current)
    return RoleDecision(keep=current)


def demand_by_role(item_demand: Mapping[str, int],
                   skill_of_item: Mapping[str, str | None],
                   catalog: tuple[Role, ...]) -> dict[str, int]:
    """Aggregate item-keyed demand into role-keyed demand.

    `skill_of_item` maps an item code to the skill that PRODUCES it (its craft
    skill, or its gathering skill for a raw resource), or None when the API
    exposes no producing skill -- in which case no role owns it and the demand
    is dropped rather than assigned to an arbitrary role.

    Passed in rather than derived from GameData so this module stays pure and
    testable without a game-data fixture."""
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
        totals[role_name] += quantity
    return totals
