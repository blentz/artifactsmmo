"""Resolve the ACTIVE loadout profiles (current objective + recent window) and
the deduped gear set the keep economy protects.

Parse contract for _recent_task_keys
-------------------------------------
Only two goal-repr patterns are recognised (narrow on purpose):

  ``GrindCharacterXP(<monster>)``  →  ``combat:<monster>``
  ``LevelSkill(<skill>-><n>)``     →  ``gather:<skill>``

All other selected_goal reprs (PursueTask, GatherMaterials, …) are silently
skipped: they do not reliably encode a task_key without game_data (PursueTask
may be any task type; GatherMaterials carries item codes not skill names).
Gather task_keys beyond the parsed window are always available via the
``gather_skills`` current-objective parameter of ``active_task_keys``.
"""

import re

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles_core import bank_space_cost, gear_demand
from artifactsmmo_cli.ai.world_state import WorldState

RECENT_PROFILE_WINDOW = 50  # cycles; mirrors the learning windows in LearningStore

_GRIND_RE = re.compile(r"^GrindCharacterXP\((.+)\)$")
_SKILL_RE = re.compile(r"^LevelSkill\((\w+)->")


def combat_key(monster_code: str) -> str:
    """Return the canonical task_key string for a combat task."""
    return f"combat:{monster_code}"


def gather_key(skill: str) -> str:
    """Return the canonical task_key string for a gather task."""
    return f"gather:{skill}"


def _recent_task_keys(history: LearningStore, window: int) -> set[str]:
    """Parse task_keys from the most recent `window` Cycle.selected_goal values.

    See module docstring for the exact parse contract.
    """
    keys: set[str] = set()
    for goal_repr in history.recent_selected_goals(window):
        m = _GRIND_RE.match(goal_repr)
        if m:
            keys.add(combat_key(m.group(1)))
            continue
        m = _SKILL_RE.match(goal_repr)
        if m:
            keys.add(gather_key(m.group(1)))
    return keys


def active_task_keys(
    history: LearningStore,
    combat_monster: str | None,
    gather_skills: frozenset[str],
) -> set[str]:
    """Current-objective task_keys UNION recent-window task_keys.

    Current keys come from the explicit ``combat_monster`` and
    ``gather_skills`` parameters (set by the bot for the current cycle).
    Recent keys are parsed from the last ``RECENT_PROFILE_WINDOW`` cycle
    selected_goal strings stored in ``history``.
    """
    keys: set[str] = set()
    if combat_monster:
        keys.add(combat_key(combat_monster))
    for skill in gather_skills:
        keys.add(gather_key(skill))
    keys |= _recent_task_keys(history, RECENT_PROFILE_WINDOW)
    return keys


def active_loadouts(
    state: WorldState,
    game_data: GameData,
    history: LearningStore,
    combat_monster: str | None,
    gather_skills: frozenset[str],
) -> list[dict[str, str]]:
    """Stored loadouts whose task_key is in the active set.

    ``state`` and ``game_data`` are accepted for signature uniformity with
    ``active_profile_gear`` / ``active_bank_space_cost`` but are not used here;
    the active set is resolved purely from ``history`` + the current-objective
    parameters.
    """
    stored: dict[str, dict[str, str]] = history.loadout_profiles()
    active: set[str] = active_task_keys(history, combat_monster, gather_skills)
    return [stored[k] for k in active if k in stored]


def active_profile_gear(
    state: WorldState,
    game_data: GameData,
    history: LearningStore,
    combat_monster: str | None,
    gather_skills: frozenset[str],
) -> dict[str, int]:
    """Deduped gear-demand keep set ``{code: demand}`` for all active profiles.

    ``demand[code]`` = MAX over active profiles of the count of ``code`` in
    that profile's loadout (one loadout worn at a time; rings can be 2 in one
    profile).  Mirrors ``gear_demand`` in ``loadout_profiles_core``.
    """
    return gear_demand(
        active_loadouts(state, game_data, history, combat_monster, gather_skills)
    )


def active_bank_space_cost(
    state: WorldState,
    game_data: GameData,
    history: LearningStore,
    combat_monster: str | None,
    gather_skills: frozenset[str],
) -> int:
    """Bank slots the active profiles demand beyond what is currently equipped.

    = ``|distinct codes across active loadouts| − |equipped codes|``.
    Mirrors ``bank_space_cost`` in ``loadout_profiles_core``.
    """
    loadouts = active_loadouts(state, game_data, history, combat_monster, gather_skills)
    equipped: set[str] = {c for c in state.equipment.values() if c is not None}
    return bank_space_cost(loadouts, equipped)
