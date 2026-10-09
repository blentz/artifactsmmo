"""The goal reprs the yield history is actually keyed by.

A `selected_goal` repr is a CONTRACT between the cycle writer and every reader
that aggregates over it, and it is an unusually easy one to break: nothing
type-checks a string, and a reader that asks for a repr nobody emits gets an
empty result rather than an error. It then behaves exactly like a cold start.

That is what happened. `8c812fb3` (2026-05-24) deleted the dormant `FarmItems`
and `FarmMonster` goals — the WRITERS — and left readers keyed on their reprs
(`projections.cheapest_path_to_level`'s learned xp-per-cycle arm and
`GrindCharacterXPGoal.value`'s own priority among them). Measured against the
live learning DB on 2026-08-07: `FarmMonster%` matched 0 of 22302 cycles and
`FarmItems%` matched 0. So for ~2.5 months those readers silently fell back to
their cold-start constants.

The whole suite stayed green because ~60 test call-sites SYNTHESISE cycles with
these reprs. The consumers were exercised thoroughly against a producer that no
longer existed; coverage, mutation and the differential all passed, because none
of them asks whether anything in production emits the string.

Hence this module. Every repr a reader aggregates over is built here, so the
question "who writes this?" has one place to answer, and a future goal rename
breaks one file instead of going quiet in several.

The task-pursuit grouping (`PursueTask(<code>)` reprs pooled per taskmaster) and
the busiest-grind prefix scan lived here too; their only reader was the retired
low-yield cancel predicate, and they were deleted with it (Phase 5-2c-iii
cleanup increment 1).
"""


def grind_xp_repr(monster_code: str) -> str:
    """Yield-history key for grinding character XP on `monster_code`.

    Replaces `FarmMonster(<code>)`, whose goal was deleted in `8c812fb3`.
    `GrindCharacterXPGoal` is its successor in fact as well as in name — it is
    the goal the arbiter selects to fight for character XP, and its repr is what
    `CycleObserver` records. Live DB: 914 `GrindCharacterXP(red_slime)` cycles
    against 0 for any `FarmMonster(...)`."""
    return f"GrindCharacterXP({monster_code})"
