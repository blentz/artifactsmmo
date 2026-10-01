"""Gather-skill gate: is a gather's skill gate open for the search?

A skill-locked gather (iron_rocks, mining 10) cannot become applicable inside
a search: gathering raises skill XP server-side, never the planner-tracked
level. Since Phase 2d-b2 nothing in the search raises a skill either (the
`LevelSkill` macro left the action pool; a skill gate is the one walk's, opened
as a sub-grind), so a closed gather is simply not admitted.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.world_state import WorldState


def skill_open(resource_code: str, state: WorldState, game_data: GameData) -> bool:
    """True iff the resource's skill gate is open against the FIXED initial
    `state` passed to `relevant_actions`. Gathers alone never raise a skill
    (they raise skill XP server-side, not planner-tracked levels), so a gather whose
    gate is closed here cannot become applicable via gathering. Admitting one
    unconditionally is branching waste — and worse, it can WIN the yield
    narrowing and displace a workable source (derived 2026-07-08:
    salmon_spot, the rate-best small_pearls dropper at 1/100, is fishing-40-
    gated; at fishing 30 it beat bass_spot in select_gather_source and the
    pearl plan died at one node). Mirrors
    GatherAction.is_applicable's skill arm (default level 1) without its
    transient inventory-space arm — bag pressure changes in-plan."""
    req = game_data.resource_skill_level(resource_code)
    return req is None or state.skills.get(req[0], 1) >= req[1]
