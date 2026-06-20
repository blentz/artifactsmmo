"""Per-root progress value — the production `progressed` signal for the sticky gate.

`root_progress_value(root, state, game_data)` returns a monotone scalar that STRICTLY
INCREASES exactly when the committed objective root advances toward completion. The
player layer compares it across cycles: a strict increase means the root progressed, so
its sticky anchor is kept (`sticky_select_core.next_last(repr, progressed=True)`); a flat
value means the root is frozen (the weaponcrafting zombie: skill xp stuck at 75 for 1028
cycles), so the anchor is released and the highest-value plannable root wins next cycle.

This is the model<->code trust boundary the Lean proof names `hprogFaithful`
(`Formal/Liveness/ZombieFreedom.lean`): the abstract no-zombie theorem assumes the
`progressed` Bool witnesses a strict reach-50 measure descent. The value here is the
production witness of that descent, keyed to the root TYPE so progress on the WRONG axis
(mining xp while committed to weaponcrafting) does NOT count as progress for the
committed root — that mismatch was the whole livelock.
"""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.world_state import WorldState

# An equipped target is maximally progressed; dominates any in-progress material count.
_EQUIPPED_VALUE = 1_000_000_000
# Level dominates xp within a ReachCharLevel measure (a level-up is strict progress
# even if xp resets).
_LEVEL_SCALE = 100_000_000


def _obtain_progress(
    code: str, state: WorldState, game_data: GameData
) -> int:
    """Progress toward obtaining an equippable: equipped dominates; otherwise count the
    owned units of the target plus the owned units of its direct recipe inputs (which
    rise as the bot gathers/crafts toward the item)."""
    if code in (v for v in state.equipment.values() if v is not None):
        return _EQUIPPED_VALUE
    owned = state.inventory.get(code, 0)
    recipe = game_data.crafting_recipe(code)
    if recipe is not None:
        owned += sum(state.inventory.get(mat, 0) for mat in recipe)
    return owned


def root_progress_value(
    root: MetaGoal, state: WorldState, game_data: GameData
) -> int:
    """Monotone progress scalar for the committed objective root. Strictly increases
    when (and only when) the root advances on ITS OWN axis."""
    if isinstance(root, ReachSkillLevel):
        return state.skill_xp.get(root.skill, 0)
    if isinstance(root, ReachCharLevel):
        return state.level * _LEVEL_SCALE + state.xp
    if isinstance(root, ObtainItem):
        return _obtain_progress(root.code, state, game_data)
    return 0
