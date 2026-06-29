"""PURE proved cores for loadout-profile dedup + bank-space cost (extracted;
mirrors Formal/LoadoutProfiles.lean). No GameData/IO. See
docs/superpowers/specs/2026-06-28-gear-loadout-profiles-design.md."""

from collections.abc import Mapping, Sequence, Set


def _counts(loadout: Mapping[str, str]) -> dict[str, int]:
    out: dict[str, int] = {}
    for code in loadout.values():
        out[code] = out.get(code, 0) + 1
    return out


def gear_demand(active_loadouts: Sequence[Mapping[str, str]]) -> dict[str, int]:
    """For each gear code, the MAX over active loadouts of its count in that
    loadout (one loadout worn at a time -> shared gear held once; rings can be 2
    in one loadout). Mirrors Formal.LoadoutProfiles.gearDemand."""
    demand: dict[str, int] = {}
    for loadout in active_loadouts:
        for code, n in _counts(loadout).items():
            if n > demand.get(code, 0):
                demand[code] = n
    return demand


def bank_space_cost(active_loadouts: Sequence[Mapping[str, str]],
                    equipped: Set[str]) -> int:
    """Distinct gear across active loadouts that is NOT currently equipped — the
    bank room the active profiles demand. Mirrors Formal.LoadoutProfiles.bankSpaceCost."""
    distinct = {code for loadout in active_loadouts for code in loadout.values()}
    return len(distinct - set(equipped))
