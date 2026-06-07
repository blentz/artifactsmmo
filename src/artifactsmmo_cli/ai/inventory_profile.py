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
from artifactsmmo_cli.ai.world_state import WorldState


def _closure_demand(root: str, multiplier: int, game_data: GameData,
                    out: dict[str, int], visited: frozenset[str]) -> None:
    """Accumulate the recipe-closure demand of `root` (x `multiplier`) into
    `out`. The root itself and every transitive material are recorded at their
    cumulative required quantity (max across roots). Cycle-safe via `visited`.
    """
    if root in visited:
        return
    sub_visited = visited | {root}
    # Record the root at its own demanded quantity (max across contributors).
    if multiplier > out.get(root, 0):
        out[root] = multiplier
    recipe = game_data.crafting_recipe(root) or {}
    for mat, qty_per in recipe.items():
        if qty_per <= 0:
            continue
        _closure_demand(mat, multiplier * qty_per, game_data, out, sub_visited)


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
        _closure_demand(root, 1, game_data, profile, frozenset())

    # Active items-task: size to the remaining task quantity so the whole
    # remaining batch of inputs is protected (mirrors bank_selection's task
    # keep-set discipline).
    if state.task_type == "items" and state.task_code:
        remaining = max(0, state.task_total - state.task_progress)
        if remaining > 0:
            _closure_demand(state.task_code, remaining, game_data, profile,
                            frozenset())

    return profile
