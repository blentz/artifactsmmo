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


def fleet_climbers(demanded: Mapping[str, int], gain: Mapping[str, Fraction],
                   owners: Mapping[str, str], skill_rank: Sequence[str], character: str,
                   skill_levels: Mapping[str, int],
                   sibling_skill_levels: Mapping[str, Mapping[str, int]],
                   live_leases: Mapping[str, frozenset[str]],
                   fleet_order: Sequence[str]) -> dict[str, str]:
    """craft skill -> the ONE character that climbs it for the fleet.

    `demanded` is the level the fleet's `L*` pieces demand of each producing
    skill; only the craft skills in `owners` (skill -> the role owning it) are
    climbed. They are taken in descending `gain` (the fleet's gain summed over
    the pieces each gates), ties in `skill_rank` order, and each assigned
    `climber` over this character (`skill_levels`) and the siblings in
    `fleet_order` (`sibling_skill_levels`) that no earlier skill took.

    Remaining climb is the LEVELS still to climb, `max(0, demanded - level)`.
    The published ledger carries levels only, and every character climbs the
    same per-level xp curve (`skill_grind_cost_core`: the API exposes no curve,
    one level's requirement stands for every level), so this orders the
    candidates exactly as remaining xp does: the character already highest in
    the skill (the spec's own gloss). A missing level reads 0, as in
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
          {name: Fraction(max(0, demanded[skill] - held.get(skill, 0)))
           for name, held in levels.items()},
          {name: sum(1 for role, holders in live_leases.items()
                     if name in holders and role != owners[skill])
           for name in levels})
         for skill in skills],
        fleet_order)


def serving_climbers(climbers: Mapping[str, str], owners: Mapping[str, str],
                     live_leases: Mapping[str, frozenset[str]]) -> dict[str, str]:
    """The climbers that can serve their skill (ruling T7a): each holds that
    skill's owning role, or no role at all and so is free to claim it. A
    climber holding another role supplies nothing for this skill, so its
    receivers price their own climb instead of waiting on it."""
    return {skill: who for skill, who in climbers.items()
            if all(role == owners[skill]
                   for role, holders in live_leases.items() if who in holders)}
