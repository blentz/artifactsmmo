# formal/diff/test_complete_task_income_diff.py
"""Differential: the tasks_coin count after `complete_task_apply_pure` must equal
the kernel-proved `Formal.CompleteTaskIncome.applyComplete(coins, reward)`.

The Lean side carries `applyComplete_monotone` (reward ≥ 1 ⇒ strict increase);
this pins the running Python coin-minting to that proved arithmetic."""
from hypothesis import given
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.complete_task_core import complete_task_apply_pure
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE
from formal.diff.oracle_client import run_oracle

_coins = st.integers(min_value=0, max_value=500)
_reward = st.integers(min_value=1, max_value=50)  # API floor: every task awards ≥1


@given(coins=_coins, reward=_reward)
def test_coin_count_matches_oracle(coins, reward):
    py = complete_task_apply_pure({TASKS_COIN_CODE: coins}, reward)[TASKS_COIN_CODE]
    lean = run_oracle("complete_task_income", [[coins, reward]])[0]["coins_after"]
    assert py == lean, f"divergence at (coins={coins}, reward={reward}): py={py} lean={lean}"


def test_reward_strictly_increases_both_sides():
    """Monotonicity witness: a reward ≥1 raises the count on both sides."""
    py = complete_task_apply_pure({TASKS_COIN_CODE: 7}, 1)[TASKS_COIN_CODE]
    lean = run_oracle("complete_task_income", [[7, 1]])[0]["coins_after"]
    assert py == lean == 8
    assert py > 7
