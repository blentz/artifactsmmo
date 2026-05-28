"""Phase G-C scalarizer: convert a Yield into a single comparable scalar.

The scalar's unit is "approximate character-XP equivalent per cycle". A
goal that earns 1.0 in this unit at every cycle is contributing one
character-XP-equivalent per cycle on average.

Weights are tunable constants at the top of the module. Real-play data
should inform them; for now they're designer choices documented in the
spec (docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §3).
"""

import json

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import Yield
from artifactsmmo_cli.ai.learning.scalar_core import coins_spent_from_delta, scalar_yield_pure
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

# Weights ----------------------------------------------------------------

SKILL_XP_BASELINE_WEIGHT = 0.2
"""Default contribution of 1 skill-XP per cycle to the scalar.

A skill that isn't on the critical path for the active task is still
weakly valuable (long-term progression), but well below character XP.
"""

SKILL_XP_RELEVANT_TOOL_WEIGHT = 2.0
"""Contribution of 1 skill-XP per cycle when the skill gates a craftable
tool relevant to the active task. Beats baseline by 10x so the scalar
prefers grinding the right skill first."""

GOLD_PER_XP_EQUIVALENT = 100.0
"""How many gold equal one character-XP for scoring purposes. Tunable.

A higher value down-weights gold; a lower value treats gold as more
valuable per unit.
"""

DEFAULT_COIN_VALUE_GOLD = 5.0
"""Fallback assumed gold-equivalent value of one tasks_coin before any
TaskExchange data is observed."""

CHARACTER_XP_LEVEL_SCALAR = 1.0
"""Base multiplier on character XP. Multiplied by (state.level + 1) so
late-game character XP is increasingly valuable (because higher levels
unlock more capable content)."""


def expected_coin_value_with_prices(
    store: LearningStore, sell_back_price: dict[str, int], window: int = 100,
) -> float:
    """Estimated gold-equivalent value of one tasks_coin.

    Looks at past TaskExchange outcomes (cycles where action_repr is
    "TaskExchange" and outcome=="ok"), sums the NPC sell-back gold value of
    items received, and divides by the coins actually spent. The per-exchange
    coin cost is NOT API data, so it is derived per cycle from the recorded
    inventory change: a TaskExchange only adds rewards and removes coins, so
    ``coins_spent = received_item_count - delta_inv_used``. Returns
    DEFAULT_COIN_VALUE_GOLD when there's no usable history.

    `sell_back_price`: `{item_code: gold_per_unit}` for every item an NPC
    will buy back from the player. Caller builds it from
    `GameData._npc_sell_prices` (take the max across NPCs).
    """
    rows = store.recent_goal_cycles("TaskExchange", window=window)
    total_value = 0.0
    total_coins_spent = 0
    for cycle in rows:
        if cycle.action_repr != "TaskExchange" or cycle.outcome != "ok":
            continue
        if cycle.delta_inv_used is None:
            continue  # can't derive coins spent without the inventory delta
        raw = cycle.drops_json or "{}"
        try:
            drops = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if not isinstance(drops, dict):
            continue
        received = 0
        cycle_value = 0.0
        for code, qty in drops.items():
            try:
                qty_i = int(qty)
            except (TypeError, ValueError):
                continue
            received += qty_i
            if code == TASKS_COIN_CODE:
                # Coins received as a reward aren't value (we price spending a
                # coin, not earning one) — but they DO count toward the
                # inventory delta, so they're included in `received` above.
                continue
            cycle_value += qty_i * sell_back_price.get(str(code), 0)
        # TaskExchange adds `received` items and removes the coins spent, so
        # delta_inv_used = received - coins_spent  =>  coins_spent = received - delta.
        coins_spent = coins_spent_from_delta(received, cycle.delta_inv_used)
        if coins_spent <= 0:
            continue  # implausible (bad/partial data) — skip
        total_value += cycle_value
        total_coins_spent += coins_spent
    if total_coins_spent == 0:
        return DEFAULT_COIN_VALUE_GOLD
    return total_value / total_coins_spent


def _max_sell_back_price(game_data: GameData) -> dict[str, int]:
    """Build {item_code: max NPC buy price} for the scalarizer's coin valuation."""
    best: dict[str, int] = {}
    for prices in game_data._npc_sell_prices.values():
        for item_code, price in prices.items():
            if price > best.get(item_code, 0):
                best[item_code] = price
    return best


def scalar_yield(
    yield_: Yield,
    state: WorldState,
    game_data: GameData,
    store: LearningStore | None = None,
) -> float:
    """Collapse a Yield into a single number for cross-goal comparison.

    Higher scalars are more valuable. Components:

    - char_xp * CHARACTER_XP_LEVEL_SCALAR * (state.level + 1)
    - sum(per-skill xp * weight) where weight is SKILL_XP_RELEVANT_TOOL_WEIGHT
      if the skill is in `game_data.active_gathering_skills(state.task_code, state.crafting_target)`,
      else SKILL_XP_BASELINE_WEIGHT.
    - gold / GOLD_PER_XP_EQUIVALENT
    - tasks_coins * expected_coin_value / GOLD_PER_XP_EQUIVALENT
    """
    active_skills = game_data.active_gathering_skills(state.task_code, state.crafting_target)

    if store is not None and yield_.tasks_coins > 0:
        prices = _max_sell_back_price(game_data)
        coin_value = expected_coin_value_with_prices(store, prices)
    else:
        coin_value = DEFAULT_COIN_VALUE_GOLD

    return scalar_yield_pure(
        yield_.char_xp,
        state.level,
        yield_.skill_xp,
        active_skills,
        yield_.gold,
        yield_.tasks_coins,
        coin_value,
        baseline_w=SKILL_XP_BASELINE_WEIGHT,
        relevant_w=SKILL_XP_RELEVANT_TOOL_WEIGHT,
        gold_per_xp=GOLD_PER_XP_EQUIVALENT,
        char_scalar=CHARACTER_XP_LEVEL_SCALAR,
    )
