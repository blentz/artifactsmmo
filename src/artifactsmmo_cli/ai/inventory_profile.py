"""Per-goal inventory profile: the SOFT target quantities the active
goal/objective-step wants on hand.

A profile is a pure value object `dict[item_code -> target_qty]` — the
recipe-closure quantity map of what the currently-active goal is trying to
accumulate. It is NOT a hard cap; deposit/discard steer toward it but never
bank or delete a profile item below its target (the keep-set ∪ profile
guarantee). See spec docs/superpowers/specs/2026-06-07-inventory-profiles-design.md.

Sources of the active profile (all derived purely from state + ctx flags):
  * `state.crafting_target` — the committed upgrade/craft target.
  * `target_gear` / `target_tools` — the CharacterObjective's long-term gear
    and tool codes (from the SelectionContext).
  * the active items-task item + its recipe inputs (sized to the remaining
    task quantity).

Each root contributes its recipe-closure raw materials x required quantities.
"""

from collections.abc import Iterable

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.recipe_closure import closure_demand
from artifactsmmo_cli.ai.world_state import WorldState


def inventory_profile(
    state: WorldState, game_data: GameData,
    target_gear: Iterable[str] = (),
    target_tools: Iterable[str] = (),
) -> dict[str, int]:
    """Return the active goal's SOFT inventory profile: item_code -> target_qty.

    Pure. Combines the recipe closures of `state.crafting_target`, the
    `target_gear` / `target_tools` codes, and the active items-task item
    (sized to its remaining quantity). The result is the set of materials the
    active goal wants on hand AND how many — the floor deposit/discard must
    never bank/delete below.
    """
    profile: dict[str, int] = {}

    # crafting_target / gear / tools: one batch each (the goal accumulates a
    # craft's worth of materials at a time).
    roots: list[str] = []
    if state.crafting_target:
        roots.append(state.crafting_target)
    roots.extend(target_gear)
    roots.extend(target_tools)
    for root in roots:
        closure_demand(root, 1, game_data, profile, frozenset())

    # Active items-task: size to the remaining task quantity so the whole
    # remaining batch of inputs is protected (mirrors bank_selection's task
    # keep-set discipline).
    if state.task_type == "items" and state.task_code:
        remaining = max(0, state.task_total - state.task_progress)
        if remaining > 0:
            closure_demand(state.task_code, remaining, game_data, profile,
                           frozenset())

    return profile
