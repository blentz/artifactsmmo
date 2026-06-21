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
from artifactsmmo_cli.ai.recipe_closure import closure_demand, raw_material_units
from artifactsmmo_cli.ai.world_state import WorldState

# An equipped target is maximally progressed; dominates any in-progress material count.
_EQUIPPED_VALUE = 1_000_000_000
# Level dominates xp within a ReachCharLevel measure (a level-up is strict progress
# even if xp resets).
_LEVEL_SCALE = 100_000_000


def _obtain_progress(
    code: str, state: WorldState, game_data: GameData
) -> int:
    """Progress toward obtaining an equippable: equipped dominates; otherwise the
    raw-material-unit-weighted count of owned units across the target's WHOLE recipe
    closure (target + every transitive intermediate + raw resource), counting both
    inventory AND bank.

    The raw-unit weight (`raw_material_units`) is what makes the measure faithful
    across a CRAFT conversion: smelting 10 copper_ore (raw 1 each = 10) into 1
    copper_bar (raw 10) leaves the sum unchanged (10 -> 10), so a craft never reads
    as a regression; gathering one more raw unit strictly increases it. The shallow
    predecessor counted only DIRECT recipe inputs in INVENTORY, so during a long
    ore-gather stretch toward copper_boots the direct copper_bar count stayed flat —
    the root read as "not progressing", the sticky anchor was released every cycle,
    and a tied same-tier gear root cannibalised the shared copper_bar (the
    copper_boots never-crafted livelock, trace 2026-06-21). Counting the transitive
    closure + bank makes every ore gathered register as progress toward boots.

    Modelled and proved monotone in `formal/Formal/Liveness/ObtainProgress.lean`
    (gather ⇒ strict increase, craft ⇒ non-decrease); this is the production witness
    of the `hprogFaithful` obligation in `ZombieFreedom.lean`."""
    if code in (v for v in state.equipment.values() if v is not None):
        return _EQUIPPED_VALUE
    bank = state.bank_items or {}
    # Item-code closure = target + every transitive recipe MATERIAL (intermediates
    # AND gathered leaf items, e.g. copper_boots + copper_bar + copper_ore).
    # `closure_demand` keys on item codes; `recipe_closure` would give resource
    # codes (copper_rocks) not the ore item, so it is the wrong set here.
    demand: dict[str, int] = {}
    closure_demand(code, 1, game_data, demand, frozenset())
    nodes = set(demand) | {code}
    total = 0
    for node in nodes:
        owned = state.inventory.get(node, 0) + bank.get(node, 0)
        if owned:
            total += owned * raw_material_units(game_data, node)
    return total


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
