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

from artifactsmmo_cli.ai.role_catalog import Role, role_skills

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


@dataclass(frozen=True)
class RoleDecision:
    """Exactly one field is non-None, or all three are None (nothing to do).
    Pure data; exempt from one-class-per-file."""

    keep: str | None = None
    claim: str | None = None
    release: str | None = None


def _best_free_role(live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                    character: str, catalog: tuple[Role, ...],
                    idle_released: frozenset[str]) -> tuple[str | None, int]:
    """Highest-demand role not leased by SOMEONE ELSE, with its demand.

    Ties are resolved by catalog order — a declared, semantic order, never a
    repr or alphabetical sort. Ties are also harmless: the UNIQUE constraint on
    RoleLease.role serializes concurrent claimants regardless.

    A role in `idle_released` is also skipped, but ONLY while its demand is
    still non-positive — see `decide_role` for why. The moment real demand
    shows up for it, it competes for the claim like any other role again."""
    best: str | None = None
    best_demand = -1
    for role in catalog:
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        demand = demand_by_role.get(role.name, 0)
        if role.name in idle_released and demand <= 0:
            continue
        if demand > best_demand:
            best, best_demand = role.name, demand
    return best, max(best_demand, 0)


def decide_role(current: str | None, held_cycles: int,
                live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                character: str, catalog: tuple[Role, ...],
                idle_released: frozenset[str] = frozenset(),
                zero_demand_cycles: int = 0) -> RoleDecision:
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
    `_best_free_role` stops skipping it automatically."""
    if current is None:
        best, _ = _best_free_role(live_leases, demand_by_role, character, catalog, idle_released)
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
