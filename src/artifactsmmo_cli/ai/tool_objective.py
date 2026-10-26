"""The tool a skill climb fetches first (spec 2026-10-18 §2.6, plan B Task 8).

A tool is any item whose `skill_effects` name the skill (`tool_value`): the
fishing net's -10 fishing, and a Season 9 crafting tool's effect on its craft
skill alike, so no skill is special-cased. Before the character climbs a skill
it first obtains the best such tool it can: the climb's cooldown shrinks for
every action after.
"""

from datetime import datetime

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import PIECE_POLICY
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.equip_value import tool_value
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel, StepDecline
from artifactsmmo_cli.ai.world_state import WorldState


def _owned(state: WorldState) -> frozenset[str]:
    """Every code in the bag, the bank or worn."""
    bank = state.bank_items or {}
    return frozenset({code for code, n in state.inventory.items() if n > 0}
                     | {code for code in state.equipment.values() if code}
                     | {code for code, n in bank.items() if n > 0})


def tool_target(skill: str, state: WorldState, game_data: GameData,
                ctx: SelectionContext, now: datetime) -> str | None:
    """The level-legal item with the largest `tool_value` for `skill` among
    those achievable under `PIECE_POLICY` (the policy `L*` pieces are judged
    achievable by), or None when none is, or when that best one is already
    owned. A tie goes to the owned copy (nothing to fetch), then to the lower
    item level; a full tie keeps the catalogue's own order. `now` is the caller's
    cycle clock (the obtain model's event gates read it)."""
    owned = _owned(state)
    candidates = [(tool_value(stats, skill), code in owned, -stats.level, code)
                  for code, stats in game_data.items.stats.items()
                  if stats.level <= state.level and tool_value(stats, skill) > 0]
    # Stable sort, descending on the semantic key only.
    candidates.sort(key=lambda row: row[:3], reverse=True)
    model = ObtainModel(state, game_data, ctx, now)
    for _value, held, _level, code in candidates:
        if held:
            return None
        if model.feasible(code, 1, PIECE_POLICY):
            return code
    return None


def tool_first(climb: ReachSkillLevel, state: WorldState, game_data: GameData,
               ctx: SelectionContext, now: datetime,
               step_decline: StepDecline) -> ObtainItem | ReachSkillLevel:
    """The best tool's `ObtainItem` while the character does not yet own the
    best tool it could for the climbed skill (§2.6), else `climb`. The tool is
    an accelerator, not a gate (ruling T8a): a tool whose step `step_decline`
    refuses this cycle leaves the plain climb, never a declined piece."""
    tool = tool_target(climb.skill, state, game_data, ctx, now)
    if tool is None:
        return climb
    root = ObtainItem(tool, 1)
    if step_decline(root) is not None:
        return climb
    return root
