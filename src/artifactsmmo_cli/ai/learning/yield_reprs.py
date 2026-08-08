"""The goal reprs the yield history is actually keyed by.

A `selected_goal` repr is a CONTRACT between the cycle writer and every reader
that aggregates over it, and it is an unusually easy one to break: nothing
type-checks a string, and a reader that asks for a repr nobody emits gets an
empty result rather than an error. It then behaves exactly like a cold start.

That is what happened. `8c812fb3` (2026-05-24) deleted the dormant `FarmItems`
and `FarmMonster` goals — the WRITERS — and left three readers keyed on their
reprs:

  * `projections.cheapest_path_to_level` — the learned xp-per-cycle arm
  * `goals.grind_character_xp.GrindCharacterXPGoal.value` — its own priority
  * `projections._best_alternative_repr` -> `low_yield_cancel_fires`

Measured against the live learning DB on 2026-08-07: `FarmMonster%` matched 0 of
22302 cycles and `FarmItems%` matched 0. So for ~2.5 months the first two silently
fell back to their cold-start constants, and the third could not fire at all —
`low_yield_cancel_fires` needs BOTH a current rate and an alternative, so
`LowYieldCancelGoal` and the strategy means-predicate that share it were
unreachable, not merely quiet.

The whole suite stayed green because ~60 test call-sites SYNTHESISE cycles with
these reprs. The consumers were exercised thoroughly against a producer that no
longer existed; coverage, mutation and the differential all passed, because none
of them asks whether anything in production emits the string.

Hence this module. Every repr a reader aggregates over is built here, so the
question "who writes this?" has one place to answer, and a future goal rename
breaks one file instead of going quiet in three.
"""

from artifactsmmo_cli.ai.game_data import GameData

TASKMASTER_MONSTERS = "monsters"
TASKMASTER_ITEMS = "items"
"""The two taskmasters, by content code — the same keys
`LocationCatalog.taskmaster_tiles` uses. Which master you visit determines which
task TYPE you are issued, so this is the natural grain for task-pursuit yield:
finer than one bucket for all tasks, and far coarser (so far better populated)
than one bucket per task code."""


def grind_xp_repr(monster_code: str) -> str:
    """Yield-history key for grinding character XP on `monster_code`.

    Replaces `FarmMonster(<code>)`, whose goal was deleted in `8c812fb3`.
    `GrindCharacterXPGoal` is its successor in fact as well as in name — it is
    the goal the arbiter selects to fight for character XP, and its repr is what
    `CycleObserver` records. Live DB: 914 `GrindCharacterXP(red_slime)` cycles
    against 0 for any `FarmMonster(...)`."""
    return f"GrindCharacterXP({monster_code})"


def grind_xp_repr_prefix() -> str:
    """SQL LIKE prefix matching every `grind_xp_repr`, for
    `_best_alternative_repr`'s "busiest monster goal" scan."""
    return "GrindCharacterXP("


def taskmaster_for_item(item_code: str, game_data: GameData) -> str:
    """Which taskmaster issues tasks for `item_code`'s skill.

    The game has exactly TWO masters, so "the skill related to the target item"
    resolves to a binary: an item with a PRODUCING SKILL (crafted, or gathered
    from a resource node) belongs to the ITEMS master, and one with none — i.e.
    obtainable only as a monster drop — belongs to the MONSTERS master.

    `producing_skill` is the single source of that judgement (craft skill if
    craftable, else the gathering skill of a resource that drops it), reused here
    rather than re-derived so this cannot disagree with the progression tree's
    role alignment, which routes work by the same accessor."""
    return (TASKMASTER_ITEMS if game_data.producing_skill(item_code) is not None
            else TASKMASTER_MONSTERS)


TASK_PURSUIT_PREFIX = "PursueTask("
"""LIKE prefix over every repr `PursueTaskGoal` writes. Its repr is
`PursueTask(<task_code>)` — per TASK CODE, not per taskmaster — which is the
grain the WRITER emits and therefore the only grain a reader may match on."""


def task_pursuit_code(goal_repr: str) -> str | None:
    """The task code inside a `PursueTask(<code>)` repr, or None if `goal_repr`
    is not one. Parsing the writer's repr is what lets a reader regroup history
    the writer never grouped."""
    if not goal_repr.startswith(TASK_PURSUIT_PREFIX) or not goal_repr.endswith(")"):
        return None
    return goal_repr[len(TASK_PURSUIT_PREFIX):-1] or None


def task_pursuit_reprs_for(taskmaster: str, observed_reprs: list[str],
                           game_data: GameData) -> list[str]:
    """Those of `observed_reprs` that are task pursuits belonging to `taskmaster`.

    This is the replacement for `FarmItems`, and it is a GROUPING rather than a
    single key — deliberately, because the writer's grain and the reader's grain
    genuinely differ here. `FarmItems` was one global bucket for "whatever the bot
    is currently doing"; its goal is gone, and pooling a mining task with a
    chicken hunt was never the right question anyway.

    Per-task-code would be the other extreme: `PursueTask(<code>)` fragments
    history so finely that a freshly-issued task always reads cold, and the
    low-yield comparison would never have a current rate to compare against —
    the same silent no-op this whole change exists to remove, arrived at by a
    different route.

    The taskmaster is the grain in between, and it is the one the character
    actually chooses: which master you visit decides which task type you are
    issued. Regrouping happens HERE, over reprs read back out of history, so
    `PursueTaskGoal.__repr__` keeps its per-task identity — that repr also keys
    goal suppression and commitment, and changing it to serve a yield lookup
    would be a far larger blast radius than the lookup is worth."""
    out = []
    for repr_ in observed_reprs:
        code = task_pursuit_code(repr_)
        if code is not None and taskmaster_for_item(code, game_data) == taskmaster:
            out.append(repr_)
    return out
