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

Pure: no I/O, no clock, no classes beyond the frozen result record.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from fractions import Fraction

from artifactsmmo_cli.ai.role_catalog import Role

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
                    character: str, catalog: tuple[Role, ...]) -> tuple[str | None, int]:
    """Highest-demand role not leased by SOMEONE ELSE, with its demand.

    Ties are resolved by catalog order — a declared, semantic order, never a
    repr or alphabetical sort. Ties are also harmless: the UNIQUE constraint on
    RoleLease.role serializes concurrent claimants regardless."""
    best: str | None = None
    best_demand = -1
    for role in catalog:
        holder = live_leases.get(role.name)
        if holder is not None and holder != character:
            continue
        demand = demand_by_role.get(role.name, 0)
        if demand > best_demand:
            best, best_demand = role.name, demand
    return best, max(best_demand, 0)


def decide_role(current: str | None, held_cycles: int,
                live_leases: Mapping[str, str], demand_by_role: Mapping[str, int],
                character: str, catalog: tuple[Role, ...]) -> RoleDecision:
    """Decide whether to keep, claim, or release a role this cycle."""
    if current is None:
        best, _ = _best_free_role(live_leases, demand_by_role, character, catalog)
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
