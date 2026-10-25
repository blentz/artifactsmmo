"""Who climbs a skill for the fleet (spec 2026-10-18 §2.5): the one place the
fleet's climber is read off live coordination data, for every reader — the
role claim (`role_selection.decide_role`), the role demand
(`GamePlayer._update_coordination`) and the sibling route's price
(`acquisition_cost._sibling_craft_option`) — so the three cannot name
different climbers.

Pure: plain mappings in, a character name out. It imports nothing from the
role catalogue (the caller names the role owning the skill), so the pricer can
read it without the catalogue's import cycle.
"""

from collections.abc import Mapping, Sequence
from fractions import Fraction

from artifactsmmo_cli.ai.fleet_climb_core import climber


def fleet_climber(skill: str, demanded: int, character: str,
                  skill_levels: Mapping[str, int],
                  sibling_skill_levels: Mapping[str, Mapping[str, int]],
                  live_leases: Mapping[str, frozenset[str]],
                  owner: str,
                  fleet_order: Sequence[str]) -> str:
    """The ONE character that climbs `skill` to `demanded` for the fleet:
    `fleet_climb_core.climber` over this character (`skill_levels`) and every
    sibling in `fleet_order` (`sibling_skill_levels`).

    Remaining climb is the LEVELS still to climb, `max(0, demanded - level)`.
    The published ledger carries levels only, and every character climbs the
    same per-level xp curve (`skill_grind_cost_core`: the API exposes no curve,
    one level's requirement stands for every level), so this orders the
    candidates exactly as remaining xp does: the character already highest in
    the skill (the spec's own gloss). A missing level reads 0, as in
    `role_catalog.role_skill_level`. Other committed work is the live roles a
    candidate holds besides `owner`, the role that owns `skill`.

    The fleet is `fleet_order`: a ledger row outside it is not this run's fleet
    and does not compete, and this character must be in it (`climber` raises
    otherwise)."""
    levels: dict[str, Mapping[str, int]] = {
        name: sibling for name, sibling in sibling_skill_levels.items() if name in fleet_order}
    levels[character] = skill_levels
    remaining = {name: Fraction(max(0, demanded - held.get(skill, 0)))
                 for name, held in levels.items()}
    committed = {name: sum(1 for role, holders in live_leases.items()
                           if name in holders and role != owner)
                 for name in levels}
    return climber(remaining, committed, fleet_order)
