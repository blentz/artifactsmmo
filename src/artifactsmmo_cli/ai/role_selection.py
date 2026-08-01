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
    the role stays locked for the whole session.

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
                idle_released: frozenset[str] = frozenset()) -> RoleDecision:
    """Decide whether to keep, claim, or release a role this cycle.

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
        return RoleDecision(release=current)

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
