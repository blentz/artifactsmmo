"""Gather-skill gate: which skill-locked gathers a LevelSkill grind can open.

A closure material whose ONLY gather source is skill-locked (iron_ore <-
iron_rocks, mining 10) is unreachable by gathering alone, because gathering
raises skill XP server-side but never the planner-tracked skill level. The fix
(epic P3b, commit 7b6b4408) is to admit a `LevelSkill(skill -> level)` that opens
the gate plus the locked gather itself, so the plan becomes LevelSkill -> Gather
instead of a dead branch.

This module exists because that logic was previously written once, inside
`GatherMaterialsGoal.relevant_actions`, and *mirrored by comment* into
`UpgradeEquipmentGoal.relevant_actions`. The mirror drifted: P3b extended the
gatherer and never reached the equipment goal, whose comment went on claiming
parity that no longer held. Sharing the code removes the class of bug rather
than the instance.
"""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import gather_serves_closure
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
    pearl plan died at one node). A skill-closed gather is therefore admitted
    ONLY through the `openable_gather_grinds` fallback — when the
    LevelSkill action can raise the gate mid-search (`LevelSkill.apply` DOES
    mutate `state.skills`) and the drop has no open source, so the plan is
    LevelSkill→Gather rather than a wasted branch. Mirrors
    GatherAction.is_applicable's skill arm (default level 1) without its
    transient inventory-space arm — bag pressure changes in-plan."""
    req = game_data.resource_skill_level(resource_code)
    return req is None or state.skills.get(req[0], 1) >= req[1]


def level_below_and_grindable(req: tuple[str, int], state: WorldState,
                              game_data: GameData) -> bool:
    """True when the character is UNDER the gather-skill gate `req` = (skill,
    level) and that level is reachable by a LevelSkill grind (level within the
    server skill ceiling). Gates the fallback admission of a skill-locked gather
    to ones a LevelSkill can actually open — a source gated above
    max_skill_level stays excluded (no route), preserving skill_open's
    permanently-closed exclusion."""
    skill, level = req
    return (state.skills.get(skill, 1) < level
            and level <= game_data.max_skill_level)


def openable_gather_grinds(
    actions: list[Action],
    state: WorldState,
    game_data: GameData,
    chain: dict[str, int],
    covered: set[str],
) -> tuple[set[str], set[tuple[str, int]]]:
    """Find skill-locked closure gathers a LevelSkill grind can open.

    Returns `(resource_codes, skill_levels)` — the locked gathers to admit and
    the `(skill, level)` pairs whose LevelSkill must be admitted alongside them.

    Restricted to drops with NO currently-open source: a workable open source
    must never be displaced by a locked one that would force a needless grind
    (the fishing-40 salmon vs fishing-30 bass narrowing hazard, see
    `skill_open`). Materials in `covered` are supplied from bank/inventory and
    are skipped entirely.
    """
    open_drops: set[str] = set()
    locked_by_drop: dict[str, list[tuple[str, str, int]]] = {}
    for action in actions:
        if not isinstance(action, GatherAction):
            continue
        if not gather_serves_closure(action.resource_code,
                                     action.drop_item_override,
                                     game_data.resource_drops, chain):
            continue
        drop = (action.drop_item_override
                or game_data.resource_drop_item(action.resource_code))
        if drop is None or drop in covered:
            continue
        if skill_open(action.resource_code, state, game_data):
            open_drops.add(drop)
            continue
        req = game_data.resource_skill_level(action.resource_code)
        # skill_open above returned False, so this gather IS skill-gated —
        # req is non-None (an unskilled gather reads as open, not gated).
        assert req is not None
        if level_below_and_grindable(req, state, game_data):
            locked_by_drop.setdefault(drop, []).append(
                (action.resource_code, req[0], req[1]))
    resource_codes: set[str] = set()
    skill_levels: set[tuple[str, int]] = set()
    for drop, locked in locked_by_drop.items():
        if drop in open_drops:
            continue  # a workable open source exists — no forced grind
        for res, skill, level in locked:
            resource_codes.add(res)
            skill_levels.add((skill, level))
    return resource_codes, skill_levels
