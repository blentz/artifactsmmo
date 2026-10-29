"""Who climbs which skill for the fleet (spec 2026-10-18 §2.5, ruling T7a): the
one place the fleet's climbers are read off live coordination data, for every
reader — the role demand (`GamePlayer._update_coordination`) and the sibling
route's price (`acquisition_cost._sibling_craft_option`) — so they cannot name
different climbers.

Climbers are an ASSIGNMENT. A character holds one role and only a role-holder
supplies, so a character named the climber of two skills could serve at most
one of them, and the other's receivers would wait on a crafter that never
crafts. The demanded craft skills are taken in descending summed fleet gain
(ties in the role catalogue's declared order), and each picks
`fleet_climb_core.climber` over the characters no earlier skill took
(`assign_climbers`).

Pure: plain mappings in, names out. It imports nothing from the role catalogue
(the caller names each skill's owning role and the skill order), so the pricer
can read it without the catalogue's import cycle.
"""

from collections.abc import Mapping, Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.fleet_climb_core import assign_climbers
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles


def climb_ranks(skill: str, demanded: int, levels: Mapping[str, Mapping[str, int]],
                rates: Mapping[str, Mapping[str, float]], max_xp: int) -> dict[str, Fraction]:
    """Each candidate's rank for climbing `skill` to `demanded`, in CYCLES
    (ruling T14d-6): `skill_grind_cycles` from its level at its rate (`rates`:
    its own, else the fleet's, positive only; `acquisition_cost.climber_rate`),
    the measure the sibling route's price uses. A candidate already at the
    level is 0 cycles. One with no positive rate (or no known `max_xp`) has no
    price, and ranks after every priced candidate, ordered among themselves by
    the levels still to climb: `1 + the largest priced cycles + levels`."""
    left = {name: max(0, demanded - held.get(skill, 0)) for name, held in levels.items()}
    priced: dict[str, int] = {}
    for name, held in levels.items():
        rate = rates.get(name, {}).get(skill)
        if left[name] == 0:
            priced[name] = 0
        elif rate is not None and max_xp > 0:
            priced[name] = skill_grind_cycles(held.get(skill, 0), 0, max_xp, demanded, rate)
    ceiling = 1 + max(priced.values(), default=0)
    return {name: Fraction(priced[name] if name in priced else ceiling + left[name])
            for name in levels}


def fleet_climbers(demanded: Mapping[str, int], gain: Mapping[str, Fraction],
                   owners: Mapping[str, str], skill_rank: Sequence[str], character: str,
                   skill_levels: Mapping[str, int],
                   sibling_skill_levels: Mapping[str, Mapping[str, int]],
                   live_leases: Mapping[str, frozenset[str]],
                   fleet_order: Sequence[str],
                   rates: Mapping[str, Mapping[str, float]],
                   max_xp: Mapping[str, int]) -> dict[str, str]:
    """craft skill -> the ONE character that climbs it for the fleet.

    `demanded` is the level the fleet's `L*` pieces demand of each producing
    skill; only the craft skills in `owners` (skill -> the role owning it) are
    climbed. They are taken in descending `gain` (the fleet's gain summed over
    the pieces each gates), ties in `skill_rank` order, and each assigned
    `climber` over this character (`skill_levels`) and the siblings in
    `fleet_order` (`sibling_skill_levels`) that no earlier skill took.

    Remaining climb is in CYCLES (`climb_ranks`, ruling T14d-6), the measure
    the sibling route prices it in: the levels still to climb at this
    character's per-level xp (`max_xp`: the API exposes no curve, one level's
    requirement stands for every level, `skill_grind_cost_core`) over each
    candidate's grind rate (`rates`). The published ledger carries levels only,
    so within-level xp is unknown and every candidate climbs from the start of
    its level, as the price does. A candidate with no rate ranks after every
    priced one, by levels. A missing level reads 0, as in
    `role_catalog.role_skill_level`. Other committed work is the live roles a
    candidate holds besides the skill's owning role.

    The fleet is `fleet_order`: a ledger row outside it is not this run's fleet
    and does not compete, and this character must be in it
    (`fleet_climb_core.climber` raises otherwise)."""
    levels: dict[str, Mapping[str, int]] = {
        name: sibling for name, sibling in sibling_skill_levels.items() if name in fleet_order}
    levels[character] = skill_levels
    skills = sorted((skill for skill in demanded if skill in owners),
                    key=lambda skill: (-gain.get(skill, Fraction(0)), skill_rank.index(skill)))
    return assign_climbers(
        [(skill,
          climb_ranks(skill, demanded[skill], levels, rates, max_xp.get(skill, 0)),
          {name: sum(1 for role, holders in live_leases.items()
                     if name in holders and role != owners[skill])
           for name in levels})
         for skill in skills],
        fleet_order)


def serving_climbers(climbers: Mapping[str, str], owners: Mapping[str, str],
                     live_leases: Mapping[str, frozenset[str]]) -> dict[str, str]:
    """The climbers that serve their skill (rulings T7a, T7f): each HOLDS that
    skill's owning role, the only role whose supply run banks the fleet's
    pieces. A climber holding another role, or none yet, supplies nothing for
    the skill this cycle, so its receivers price their own climb instead of
    waiting on it. A roleless climber keeps its assignment: its `climbing`
    demand recruits it to the role, and the cycle after it claims, receivers
    switch to the sibling route."""
    return {skill: who for skill, who in climbers.items()
            if who in live_leases.get(owners[skill], frozenset())}
