"""Pure core: a task's worth, and the keep/cancel/draw verdicts read off it
(Phase 5-2c-iii-c-2 #5, `docs/PLAN_task_value.md`; proved model
`formal/Formal/TaskWorth.lean`, differential `formal/diff/test_task_worth_diff.py`).

USER 2026-10-07: a task is worth working for its XP, for the gold a pending
purchase needs when the task is the faster gold source, or for drops a needed
craft uses — "part of the pareto frontier analysis central to the game's
progress loop". Before this, S-048 cancelled every no-XP draw on the spot for a
coin: 4 of 5 draws at level 29-30 on 2026-10-07, while a turn-in pays 4 coins +
300 gold.

* XP: a kill (or the producing skill) pays the character XP.
* GOLD: account gold is short of the larger of the progression reserve and the
  chosen root's purchases, AND working the task earns gold faster per cycle than
  the best other gold route ("Faster than other gold").
* DROPS: the task monster drops an item a needed craft uses ("drops alone
  count").

An infeasible task (no gear or level closes its fight) is worthless whatever its
reasons.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from fractions import Fraction


@dataclass(frozen=True)
class TaskWorthInputs:
    """The facts a task's worth is read from."""

    feasible: bool
    xp_positive: bool
    gold_short: bool
    task_gold_rate: Fraction
    other_gold_rate: Fraction
    drop_aligned: bool


@dataclass(frozen=True)
class TaskWorth:
    """The reasons a task is worth working; all False = worthless."""

    xp: bool
    gold: bool
    drops: bool

    def any(self) -> bool:
        return self.xp or self.gold or self.drops


WORTHLESS = TaskWorth(xp=False, gold=False, drops=False)


def task_worth(inputs: TaskWorthInputs) -> TaskWorth:
    if not inputs.feasible:
        return WORTHLESS
    return TaskWorth(xp=inputs.xp_positive,
                     gold=inputs.gold_short and inputs.task_gold_rate > inputs.other_gold_rate,
                     drops=inputs.drop_aligned)


def cancel_due(worth: TaskWorth, coin: bool, met: bool) -> bool:
    """Cancel a worthless task when a coin is in the pocket and it is not met.
    With no coin it is worked to clear it (USER: "Work it to clear it")."""
    return not worth.any() and coin and not met


def draw_owed(pool: Iterable[TaskWorth]) -> bool:
    """A draw is owed when a task the master can issue is worthy."""
    return any(worth.any() for worth in pool)


def dominates(a: TaskWorth, b: TaskWorth) -> bool:
    """`a`'s reasons strictly contain `b`'s ("gold plus drops is better than
    just drops")."""
    sub = ((not b.xp or a.xp) and (not b.gold or a.gold) and (not b.drops or a.drops))
    return sub and ((a.xp and not b.xp) or (a.gold and not b.gold) or (a.drops and not b.drops))


def draw_due(worthy: int, size: int, coin_reward: int) -> bool:
    """A draw from a pool of `size` tasks, `worthy` of them worth working, is
    due when the coins expected to be spent rerolling worthless draws,
    `(size - worthy) / worthy`, are at most what a completion pays (USER
    2026-10-07: "Rerolls ≤ completion coins"). Cross-multiplied, as in Lean."""
    return worthy > 0 and size - worthy <= coin_reward * worthy
