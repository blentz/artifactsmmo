"""Taskmaster choice (spec 2026-07-19 §4): pick which tasks master to walk to by
the expected synergy of its task pool against the character's live gear needs.

The lever is binary — a monsters master issues combat tasks (their output is
character XP + monster drops), an items master issues craft/gather tasks (their
output is the task item and its skill XP). The player picks the DISTRIBUTION; the
server rolls the draw. R1 (resolved 2026-07-23, live OpenAPI): a task completes at
ANY tasks master, so a mis-chosen master never strands the character — the choice
optimises the task-type distribution only, with no completion travel penalty.

B here is the live GEAR demand (`ctx.target_gear`), NOT the tree's full B: the
char-level trunk is deliberately excluded, because it always demands `char_xp`
and would make every combat task score a perfect 1, pinning the choice to
monsters. Against gear demand alone the comparison is meaningful — a combat task
aligns only when the pursued gear routes through drops, a craft task when it
shares the gear's materials or skills.
"""

from collections.abc import Iterable, Mapping
from fractions import Fraction

from artifactsmmo_api_client.models.task_full_schema import TaskFullSchema

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_graph_memo import CHAR_XP
from artifactsmmo_cli.ai.tiers.synergy_core import expected_pool_synergy, synergy_pure
from artifactsmmo_cli.ai.world_state import WorldState


def _live_gear_demand(game_data: GameData,
                      target_gear: Iterable[str]) -> Mapping[str, int]:
    """The union (SUM) of the enriched requirement multisets of the pursued gear —
    the B the task pool is scored against. No trunk char_xp (see module docstring)."""
    memo = game_data.requirement_graph
    total: dict[str, int] = {}
    for code in target_gear:
        for token, qty in memo.requirement_multiset_for(code).items():
            total[token] = total.get(token, 0) + qty
    return total


def _task_synergy(task: TaskFullSchema, game_data: GameData,
                  gear_demand: Mapping[str, int]) -> Fraction:
    """One task's synergy with the live gear demand. A monsters task produces
    character progression, modelled by a `char_xp` token; any other task by its
    item's enriched requirement multiset. No leave-one-out — the task is a
    candidate to accept, not itself a live root."""
    if getattr(task.type_, "value", task.type_) == "monsters":
        own: Mapping[str, int] = {CHAR_XP: 1}
    else:
        own = game_data.requirement_graph.requirement_multiset_for(task.code)
    total = sum(own.values())
    shared = sum(qty for token, qty in own.items() if gear_demand.get(token, 0) > 0)
    return synergy_pure(shared, total)


def _distance(tile: tuple[int, int], state: WorldState) -> int:
    """Manhattan distance from the character to a tile — the tie-break only, never
    the score (cost stays out of the synergy per spec §4.4)."""
    return abs(tile[0] - state.x) + abs(tile[1] - state.y)


def choose_taskmaster(state: WorldState, game_data: GameData,
                      target_gear: Iterable[str]
                      ) -> tuple[str, tuple[int, int]] | None:
    """The synergy-best tasks master as `(code, tile)`, or None when there is no
    choice to make: fewer than two masters discovered, or neither master has a
    task at the character's level. `None` means "fall back to today's default
    master" (spec §4.4 edge cases). Ties on expected synergy break to the nearer
    tile — travel is a legitimate tie-break, never part of the score."""
    tiles = game_data.taskmaster_tiles
    if len(tiles) < 2:
        return None
    gear_demand = _live_gear_demand(game_data, target_gear)
    scored: dict[str, tuple[Fraction, tuple[int, int]]] = {}
    for code, tile in tiles.items():
        pool = game_data.tasks_for(code, state.level)
        if not pool:
            continue
        synergies = [_task_synergy(task, game_data, gear_demand) for task in pool]
        scored[code] = (expected_pool_synergy(synergies), tile)
    if not scored:
        return None
    best = max(scored, key=lambda c: (scored[c][0], -_distance(scored[c][1], state)))
    return best, scored[best][1]
