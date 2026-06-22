"""Pure core of `CompleteTaskAction.apply`'s coin-minting bookkeeping.

Extracted so the formal differential test (`formal/diff/test_complete_task_income_diff.py`)
can exercise the exact tasks_coin-count change against the kernel-proved Lean
`Formal.CompleteTaskIncome.applyComplete` (`formal/Formal/CompleteTaskIncome.lean`),
whose `applyComplete_monotone` theorem proves: a reward of ≥1 strictly raises the
coin count — so a funding plan that completes tasks makes monotone progress toward
a `tasks_coin ≥ N` target.

Mirrors `npc_buy_currency_apply_pure`: mint into one key, preserve the rest.
"""
from collections.abc import Mapping

from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE


def complete_task_apply_pure(inventory: Mapping[str, int],
                             coin_reward: int) -> dict[str, int]:
    """Return a new inventory with `tasks_coin += coin_reward`; all other entries
    preserved. The coin count after equals the count before plus `coin_reward`
    (the quantity the Lean `applyComplete` models)."""
    new_inventory = dict(inventory)
    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward
    return new_inventory
