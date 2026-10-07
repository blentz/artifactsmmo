"""A task's worth from live data (Phase 5-2c-iii-c-2 #5, increment 2,
`docs/PLAN_task_value.md`). The verdict itself is the proved pure core
`task_worth_core`; this module reads its inputs.

* feasible: the task's fight is won, or gear or one level closes it
  (`resolve_task_horizon`; only OUT_OF_REACH is infeasible). An items task is
  feasible: its producing chain is the objective walk's to find.
* XP: `task_alignment.task_advances_progression`.
* GOLD short: `ctx.gold_short` — account gold (pocket + bank) below the
  larger of the progression reserve and the gold the chosen root will spend at
  vendors (USER "Both, the larger"; computed by the player, which owns both).
* task gold per cycle: the task's completion gold plus its kills' fight gold,
  over the kills' cycles (a fight and its forced rests each, `cycles_per_kill`).
  An items task: its completion gold over the actions to obtain the items.
* other gold per cycle: the fight gold of what the character would otherwise
  fight (`ctx.combat_monster`) — USER "The grind target's gold".
* DROPS: the task monster drops an item still SHORT for the unmet target gear
  or near-term targets, the bag and bank used up first (`short_items`).
"""

from collections import Counter
from dataclasses import replace
from fractions import Fraction

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_alignment import task_advances_progression
from artifactsmmo_cli.ai.task_horizon import HORIZON_OUT_OF_REACH, resolve_task_horizon
from artifactsmmo_cli.ai.task_worth_core import TaskWorth, TaskWorthInputs, cancel_due, task_worth
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def _fight_gold_rate(state: WorldState, game_data: GameData, monster: str) -> Fraction:
    """Mean fight gold per cycle of farming `monster`."""
    gold = Fraction(game_data.monster_min_gold(monster) + game_data.monster_max_gold(monster), 2)
    per_kill = Fraction(cycles_per_kill(expected_damage_per_fight(state, game_data, monster),
                                        state.max_hp))
    return gold / per_kill


def short_items(state: WorldState, game_data: GameData, ctx: SelectionContext) -> frozenset[str]:
    """The items still SHORT for one copy of each unmet target (target gear not
    worn, and the near-term targets): the recipe closure walked with
    quantities, the bag and the bank used up first. A drop already banked in
    enough copies is no reason to work a task (live 2026-10-07: wolf, pig and
    skeleton all read "aligned" by an unquantified closure while the bank held
    their drops)."""
    stock: Counter[str] = Counter(state.inventory)
    stock.update(state.bank_items or {})
    short: set[str] = set()
    worn = {code for code in state.equipment.values() if code is not None}
    stack = [(code, 1) for code in ctx.target_gear | ctx.near_term_targets if code not in worn]
    while stack:
        code, qty = stack.pop()
        have = min(stock[code], qty)
        stock[code] -= have
        rest = qty - have
        if rest <= 0:
            continue
        short.add(code)
        recipe = game_data.crafting_recipe(code)
        if recipe is None:
            continue
        runs = -(-rest // game_data.craft_yield(code))
        stack.extend((material, need * runs) for material, need in recipe.items())
    return frozenset(short)


def task_worth_for(code: str, task_type: str | None, remaining: int, state: WorldState,
                   game_data: GameData, ctx: SelectionContext,
                   history: LearningStore | None) -> TaskWorth:
    """The worth of `remaining` units of task `code` for this character."""
    probe = replace(state, task_code=code, task_type=task_type,
                    task_progress=0, task_total=remaining)
    reward = game_data.task_gold_reward(code)
    if task_type == "monsters":
        horizon = resolve_task_horizon(probe, game_data)
        feasible = horizon is None or horizon.verdict != HORIZON_OUT_OF_REACH
        per_kill = Fraction(cycles_per_kill(expected_damage_per_fight(state, game_data, code),
                                            state.max_hp))
        fight_gold = Fraction(game_data.monster_min_gold(code) + game_data.monster_max_gold(code), 2)
        task_rate = (reward + remaining * fight_gold) / (remaining * per_kill)
        short = short_items(state, game_data, ctx)
        drop_aligned = any(item in short for item, *_ in game_data.monster_drops(code))
    else:
        feasible = True
        actions = acquisition_actions(code, remaining, state, game_data, ctx, equip=False,
                                      store=history)
        task_rate = Fraction(reward, max(1, actions))
        drop_aligned = False
    other = (_fight_gold_rate(state, game_data, ctx.combat_monster)
             if ctx.combat_monster is not None else Fraction(0))
    return task_worth(TaskWorthInputs(
        feasible=feasible,
        xp_positive=task_advances_progression(probe, game_data),
        gold_short=ctx.gold_short,
        task_gold_rate=task_rate,
        other_gold_rate=other,
        drop_aligned=drop_aligned))


def held_task_cancel_due(state: WorldState, game_data: GameData, ctx: SelectionContext,
                         history: LearningStore | None) -> bool:
    """The held task is worthless, a pocket coin can cancel it, and it is not
    met (`task_worth_core.cancel_due`). Without a coin it is worked to clear it
    (USER: "Work it to clear it"), so the worth is not even read."""
    if not state.task_code or state.task_progress >= state.task_total:
        return False
    if state.inventory.get(TASKS_COIN_CODE, 0) < 1:
        return False
    worth = task_worth_for(state.task_code, state.task_type,
                           state.task_total - state.task_progress,
                           state, game_data, ctx, history)
    return cancel_due(worth, coin=True, met=False)
