"""Phase G-B projections: throughput/yield estimates over the LearningStore.

Pure functions over recent Cycle history. Return None (or a low-sample
sentinel) when there's not enough data; callers must check and fall back to
hardcoded defaults during warm-up.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §2.
"""

import json
from dataclasses import replace

from pydantic import BaseModel, Field
from sqlalchemy.exc import SQLAlchemyError
from sqlmodel import Session, col, select

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Rank
from artifactsmmo_cli.ai.learning.cycles_for_progress_core import (
    CycleRow,
    cycles_for_progress_pure,
)
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.learning.low_yield_boundary import low_yield_fires_pure
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.observed_rate_core import rescale_observed_xp
from artifactsmmo_cli.ai.learning.rung_state_core import projected_max_hp
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.learning.yield_reprs import (
    TASK_PURSUIT_PREFIX,
    grind_xp_repr,
    grind_xp_repr_prefix,
    task_pursuit_reprs_for,
    taskmaster_for_item,
)
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

WARMUP_MIN_SAMPLES = 10
"""Minimum cycles for a projection to be considered trustworthy.

Below this, projection functions return None. Callers should fall back to
hardcoded defaults (existing goal priorities) when None is returned.
"""


class Yield(BaseModel):
    """Average per-cycle yield while a goal was selected."""

    char_xp: float = 0.0
    """Average character-XP gained per cycle."""

    skill_xp: dict[str, float] = Field(default_factory=dict)
    """Per-skill average XP per cycle (sparse — only skills with non-zero deltas)."""

    gold: float = 0.0
    """Average gold delta per cycle."""

    tasks_coins: float = 0.0
    """Average tasks_coin gained per cycle (parsed from drops_json)."""

    sample_count: int = 0
    """Number of cycles aggregated. < WARMUP_MIN_SAMPLES => low confidence."""

    char_xp_level: int | None = None
    """Character level the `char_xp` samples were taken at (mean over the aggregated
    cycles, rounded), or None when no cycle recorded a level.

    `char_xp` is a rate that DEPENDS on this level — the game's XP award is a
    function of the gap between character and monster, and goes to zero ten levels
    above it. Without this field the rate is uninterpretable away from where it was
    measured, and reusing it anyway is exactly the defect
    `observed_rate_core.rescale_observed_xp` exists to undo. Carried on the same
    object, from the same rows, at no extra query."""


class TaskProjection(BaseModel):
    """Projected completion of an in-flight items/monsters task."""

    cycles_remaining: float
    """Estimated cycles to take task_progress from current to task_total."""

    expected_char_xp: float
    """Total character XP expected over the remaining duration."""

    expected_gold: float
    """Total gold expected over the remaining duration (including completion bonus)."""

    expected_tasks_coins: float
    """Total tasks_coin expected (typically one batch on CompleteTask)."""

    confidence: float
    """0.0–1.0. 1.0 when sample size >= 3 * WARMUP_MIN_SAMPLES, scaled linearly below."""


def _parse_skill_xp(cycle: Cycle) -> dict[str, int]:
    """Parse delta_skill_xp_json from a Cycle row. Returns empty dict on bad data."""
    raw = cycle.delta_skill_xp_json or "{}"
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def _parse_drops(cycle: Cycle) -> dict[str, int]:
    """Parse drops_json. Returns empty dict for missing/malformed data."""
    raw = cycle.drops_json
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
        if not isinstance(parsed, dict):
            return {}
        return {str(k): int(v) for k, v in parsed.items()}
    except (json.JSONDecodeError, TypeError, ValueError):
        return {}


def expected_yield_per_cycle(goal_repr: str, store: LearningStore, window: int = 100) -> Yield:
    """Average per-cycle reward while `goal_repr` was the selected goal.

    Returns an empty Yield (with sample_count=0) when there's no history. Callers
    can detect cold goals via `yield.sample_count < WARMUP_MIN_SAMPLES`.
    """
    rows = store.recent_goal_cycles(goal_repr, window=window)
    if not rows:
        return Yield()

    char_xp_total = 0
    gold_total = 0
    coins_total = 0
    skill_xp_totals: dict[str, int] = {}
    # Levels the samples were taken at, gathered in the SAME pass. `char_xp` is a
    # level-dependent rate (see `Yield.char_xp_level`) and a caller that reuses it
    # at another level needs to know which one it came from; a second query for
    # that would be paid per monster per rung, and one walk already issues
    # thousands.
    levels = [cycle.level for cycle in rows if cycle.level is not None]

    for cycle in rows:
        char_xp_total += cycle.delta_xp or 0
        gold_total += cycle.delta_gold or 0
        for skill, delta in _parse_skill_xp(cycle).items():
            skill_xp_totals[skill] = skill_xp_totals.get(skill, 0) + delta
        coins_total += _parse_drops(cycle).get(TASKS_COIN_CODE, 0)

    n = len(rows)
    return Yield(
        char_xp=char_xp_total / n,
        skill_xp={s: t / n for s, t in skill_xp_totals.items() if t != 0},
        gold=gold_total / n,
        tasks_coins=coins_total / n,
        sample_count=n,
        char_xp_level=round(sum(levels) / len(levels)) if levels else None,
    )


def cycles_for_progress(goal_repr: str, store: LearningStore, window: int = 100) -> float | None:
    """Median cycles between "progress events" while pursuing `goal_repr`.

    Progress event definitions:
      - FarmItems / CompleteTask-style goals: task_progress strictly increased
        between this cycle and the next.
      - Other goals: cycles_to_satisfy was recorded (goal reached desired state).

    Returns None when fewer than WARMUP_MIN_SAMPLES progress events observed,
    so callers fall back to defaults during warm-up.
    """
    rows = store.recent_goal_cycles(goal_repr, window=window)
    # Pure-core delegation. The two-append-loop semantics is intentional —
    # see `cycles_for_progress_core.py` header and the Lean proof
    # `Formal.CyclesForProgress.cyclesForProgressPure_eq_median_concat`.
    projected = [
        CycleRow(
            cycle_index=row.cycle_index,
            task_progress=row.task_progress,
            cycles_to_satisfy=row.cycles_to_satisfy,
        )
        for row in rows
    ]
    return cycles_for_progress_pure(projected, WARMUP_MIN_SAMPLES)


class PathSegment(BaseModel):
    """One grind-this-monster-until-level-up step in a path to max level."""

    from_level: int
    to_level: int
    monster_code: str
    estimated_cycles: float
    xp_per_cycle: float
    cycles_per_kill: float


class PathPlan(BaseModel):
    """Estimated cheapest path from current level to target level."""

    target_level: int
    total_cycles: float
    segments: list[PathSegment] = Field(default_factory=list)
    blocked: bool = False
    """True when no beatable monster exists at some intermediate level —
    the path cannot complete without unlocking new combat options."""

    @property
    def next_action_monster(self) -> str | None:
        """Monster code for the first segment, or None if the path is empty."""
        return self.segments[0].monster_code if self.segments else None


FIGHT_CYCLES_PER_KILL = 1.0
"""Cycles consumed by one Fight. A cycle IS one executed action, so a fight
costs exactly one — the server cooldown that follows it is wall-clock time, not
another cycle.

This replaced `DEFAULT_FIGHT_CYCLES = 30.0` on 2026-08-07, whose docstring read
"~30s server cooldown is the typical post-fight cooldown" — i.e. it was a
duration in SECONDS, named cycles, and divided into an xp-per-kill to produce a
supposed cycles-per-level. Measured against the traces the constant was almost
exactly the real mean fight cooldown (29.10s over 2483 fights), and the
projection it fed was 80x the observed cost: `cheapest_path_to_level` reported
7698 cycles per character level where the traces show 96 fight-cycles per level.

Wall-clock cost per action is a real quantity and the learning store still
records it (`action_cost` -> median actual_cooldown_seconds). It is simply not
this projection's unit, and nothing here may divide by it. Callers that DO want
the duration — `tiers/strategic_weights`, which combines it with move and
deposit cooldowns into a round-trip time — take
`TYPICAL_FIGHT_COOLDOWN_SECONDS` below. One constant serving both meanings under
one wrong name is what made the confusion invisible."""

TYPICAL_FIGHT_COOLDOWN_SECONDS = 30.0
"""Fallback WALL-CLOCK cooldown of one Fight, in seconds, for callers reasoning
about elapsed time rather than cycle counts. Corroborated at 29.10s mean /
29.85s median over 2483 observed fights in the committed traces."""


def cheapest_path_to_level(
    target_level: int,
    state: WorldState,
    store: LearningStore,
    game_data: GameData,
) -> PathPlan:
    """Walk levels current → target picking the cheapest beatable monster
    at each step.

    XP per kill comes from the documented formula (`game_data.xp_per_kill`)
    — no magic guess. One kill costs exactly one cycle
    (`FIGHT_CYCLES_PER_KILL`), so xp-per-kill is already xp-per-cycle; the
    learning store supplies a measured per-cycle rate instead wherever it has
    observations.

    The returned `total_cycles` is denominated in CYCLES — planner actions —
    and counts the WHOLE combat loop: the Fight plus the Rest its damage forces
    (`fight_loop_cost.cycles_per_kill`). It is therefore comparable to the TOTAL
    cycles per level a trace shows, not the fight-cycles-per-level it used to
    match (`formal/diff/level_cost_replay.py` corroborates it).

    Returns a PathPlan with `blocked=True` and `total_cycles=inf` when no
    beatable monster exists at some intermediate level.

    Known limits:
      - Assumes each level requires `state.max_xp` XP. We don't have the
        per-level XP curve from API; new char.max_xp could be discovered
        as the bot levels up and persisted in a follow-up.
      - Doesn't model gathering/crafting detours.
      - Doesn't account for HP recovery cycles, deaths, or cooldowns
        beyond what `action_cost` captures.
    """
    if state.level >= target_level:
        return PathPlan(target_level=target_level, total_cycles=0.0, segments=[])

    segments: list[PathSegment] = []
    sim_level = state.level
    xp_to_next = max(1, state.max_xp - state.xp)
    # Project beatability at FULL HP — identical to the runtime
    # `GamePlayer._is_winnable`, which rests to max_hp before the verdict
    # because the planner inserts a Rest step before FightAction. Filtering at a
    # mid-damage `state.hp` would disagree with the executor and narrow the path
    # to lower monsters than the bot actually grinds (the 278-cycle parked bug).
    # HP is a recoverable resource, not equipment/inventory — so resting is not
    # speculative gear progression, just the normal pre-fight recovery.
    rested = replace(state, hp=state.max_hp)

    while sim_level < target_level:
        # THE BODY THIS RUNG IS FOUGHT WITH (S-015). The walk used to advance
        # `sim_level` and nothing else, so the beatability verdict at rung 40 was
        # asked of the character's rung-12 body — whether TODAY'S character can beat
        # a monster it will not meet until it is twenty-eight levels stronger. The
        # published rules grant +5 max HP per level unconditionally, so that growth
        # is not speculation about gear the character might acquire; it is arithmetic
        # the server will perform.
        #
        # The error has a direction: this figure feeds how FAR a candidate reaches,
        # so freezing the body UNDER-reports reachability and can report a target
        # unreachable that the executor will in fact reach.
        #
        # Re-equipping comes free with the level. `predict_win` (inside `is_winnable`)
        # and `project_loadout_stats` both pick the best loadout from inventory ∪
        # equipped for the state they are given, and equip conditions are evaluated
        # against that state's level — so raising the level here is exactly what makes
        # gear whose minimum-level condition the rung newly satisfies available to the
        # projection, which is S-015's second half.
        rung = replace(rested, level=sim_level,
                       max_hp=projected_max_hp(state.max_hp, state.level, sim_level),
                       hp=projected_max_hp(state.max_hp, state.level, sim_level))
        # PROJECTED wisdom, not `state.wisdom`. The latter is the server total for
        # gear already WORN, so a candidate holding a `wisdom_amulet` in inventory
        # reported the incumbent's wisdom and its +6% xp on every kill to 50 landed
        # nowhere. `is_winnable` and `expected_damage_per_fight` below already read
        # the projected loadout; wisdom was the one input still read from the raw
        # state, and that asymmetry is exactly what made every gear candidate whose
        # value is wisdom project byte-identically to the trunk.
        #
        # Per RUNG, not per walk, since S-015 makes the loadout a function of the
        # rung's level. Still not per MONSTER: the `Rank()` loadout does not depend on
        # which monster is being weighed.
        wisdom = project_loadout_stats(
            rung, pick_loadout_cached(Rank(), rung, game_data), game_data).wisdom
        # Beatable monsters at sim_level: FightAction.is_applicable allows
        # monster_level <= state.level + 1, AND is_winnable (the same rested
        # verdict the runtime uses) so projection and executor agree on the monster.
        beatable = [
            (code, lvl) for code, lvl in game_data.monster_levels.items()
            if 1 <= lvl <= sim_level + 1
            and is_winnable(rung, game_data, code, store)
        ]
        if not beatable:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)

        best_code: str | None = None
        best_xp_per_cycle = 0.0
        best_cycles_per_kill = FIGHT_CYCLES_PER_KILL
        for code, _lvl in beatable:
            observed = expected_yield_per_cycle(grind_xp_repr(code), store)
            # Cycles ONE kill of this monster really costs: the Fight plus the Rest
            # its damage forces. Per-monster, not a constant, because that is the
            # whole point — a monster that bleeds the character dry costs a rest
            # every kill while a harmless one chains, and the argmax below has to
            # see the difference or it will pick the fight with the best headline
            # xp and the worst real throughput.
            #
            # `rested` (not `state`) is the judging state, matching the `is_winnable`
            # filter above: both ask what happens starting from full HP, which is
            # what the runtime does (the planner inserts a Rest before FightAction).
            monster_cycles = cycles_per_kill(
                expected_damage_per_fight(rung, game_data, code), rung.max_hp)
            if (observed.sample_count > 0 and observed.char_xp > 0
                    and observed.char_xp_level is not None):
                # Already per-CYCLE, and per REAL cycle: `expected_yield_per_cycle`
                # averages over every cycle the goal was selected, Rests included.
                # So it must NOT be divided again — it is already whole-loop, which
                # is exactly the unit the formula branch below is converted into.
                #
                # RESTATED FOR THIS RUNG. The measured rate belongs to the level its
                # samples were taken at, and this branch used to reuse it unchanged
                # all the way up the ladder — which silently deleted the published
                # grey-mob rule (0 XP ten or more levels above a monster) from every
                # walk that had any observation at all. C3P0 thereby projected
                # reaching level 50 on a LEVEL 4 slime at a flat 7.0/cycle from rung
                # 12 to rung 49. The scaling factor is the ratio of the published
                # award at the two levels, so it carries the penalty step and the
                # base-term decay together, and it is dimensionless — the result is
                # still whole-loop XP per cycle. See `observed_rate_core`.
                xp_per_cycle = rescale_observed_xp(
                    observed.char_xp,
                    game_data.xp_per_kill(code, observed.char_xp_level, wisdom=wisdom),
                    game_data.xp_per_kill(code, sim_level, wisdom=wisdom),
                )
            else:
                # Documented formula: exact XP per kill, and one kill is one
                # cycle (FIGHT_CYCLES_PER_KILL), so per-kill IS per-cycle.
                #
                # This branch used to divide by `store.action_cost(...)`, a
                # median cooldown in SECONDS. That made it xp-per-second while
                # the branch above stayed xp-per-cycle, and the `>` below then
                # compared the two directly — so any monster with observations
                # outranked any monster without by roughly the cooldown factor
                # (~29x), whatever their real merit. Both branches now yield the
                # same unit, which is what makes this argmax meaningful at all.
                #
                # Divided by the kill's REAL cycle cost. Per-kill was treated as
                # per-cycle until 2026-08-07 on the grounds that "one kill is one
                # cycle" — true of the Fight action alone, and false of the loop:
                # measured over that day's traces every character ran ~1 Rest per
                # Fight (C3P0 22/21, Lor 31/29, Robby 4/4), so fight actions were
                # ~51% of the cycles the grind actually spent. See
                # `fight_loop_cost.rest_cycles_per_fight`.
                xp_per_cycle = (game_data.xp_per_kill(code, sim_level, wisdom=wisdom)
                                / monster_cycles)
            if xp_per_cycle > best_xp_per_cycle:
                best_code = code
                best_xp_per_cycle = xp_per_cycle
                best_cycles_per_kill = monster_cycles

        if best_code is None or best_xp_per_cycle <= 0:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)

        cycles_for_this_level = xp_to_next / best_xp_per_cycle
        segments.append(PathSegment(
            from_level=sim_level,
            to_level=sim_level + 1,
            monster_code=best_code,
            estimated_cycles=cycles_for_this_level,
            xp_per_cycle=best_xp_per_cycle,
            cycles_per_kill=best_cycles_per_kill,
        ))
        sim_level += 1
        xp_to_next = max(1, state.max_xp)

    total = sum(s.estimated_cycles for s in segments)
    return PathPlan(target_level=target_level, total_cycles=total, segments=segments)


def project_task_completion(
    state: WorldState, game_data: GameData, store: LearningStore,
) -> TaskProjection | None:
    """Project remaining cycles and reward for the in-flight task.

    Requires `state.task_total > state.task_progress`. Returns None when there's
    no active task. Reward projections use FarmItems aggregates (the standard
    goal that drives task progression). The completion payout is the task's
    exact API reward (`task_gold_reward` / `task_coin_reward`), never a
    hardcoded figure.
    """
    if (not state.task_code or state.task_total == 0
            or state.task_progress >= state.task_total):
        return None

    remaining_progress = state.task_total - state.task_progress

    # Use the per-progress-event cadence; fall back to a conservative default.
    #
    # Both aggregates read `"FarmItems"` until 2026-08-07 — a goal deleted on
    # 2026-05-24 with 0 of 22302 live cycles matching — so `cycles_per_progress`
    # always took the 15.0 fallback and `farm_yield` was always empty, pinning
    # `confidence` at 0.0. That in turn made `low_yield_cancel_fires`' confidence
    # gate unsatisfiable, a second independent reason the guard could never fire.
    busiest = busiest_task_pursuit_repr(state.task_code, game_data, store)
    cycles_per_progress = (
        (cycles_for_progress(busiest, store) if busiest is not None else None) or 15.0)
    cycles_remaining = remaining_progress * cycles_per_progress

    farm_yield = task_pursuit_yield(state.task_code, game_data, store)

    # Confidence ramps from 0 at zero samples to 1.0 at 3 * WARMUP_MIN_SAMPLES.
    confidence_cap = WARMUP_MIN_SAMPLES * 3
    confidence = min(1.0, farm_yield.sample_count / confidence_cap)

    # CompleteTask's one-off payout (gold + tasks_coin batch) is the API reward
    # for this task, outside the per-cycle FarmItems yield, so add it separately.
    completion_gold = game_data.task_gold_reward(state.task_code)
    completion_coins = game_data.task_coin_reward(state.task_code)

    return TaskProjection(
        cycles_remaining=cycles_remaining,
        expected_char_xp=farm_yield.char_xp * cycles_remaining,
        expected_gold=farm_yield.gold * cycles_remaining + completion_gold,
        expected_tasks_coins=farm_yield.tasks_coins * cycles_remaining + completion_coins,
        confidence=confidence,
    )


LOW_YIELD_CONFIDENCE_THRESHOLD = 0.5
"""Don't cancel until projection confidence >= this. Below the threshold we
defer to existing hardcoded priorities and let the task run."""

LOW_YIELD_ALTERNATIVE_MARGIN = 1.5
"""Cancel only when the alternative's char-XP rate is at least this multiple
of the current task's rate. Higher = more conservative cancels."""


def _best_alternative_repr(history: LearningStore) -> str | None:
    """Find the char-XP grind repr with the most observed cycles.

    Grind reprs are per-monster, e.g. "GrindCharacterXP(chicken)". The
    canonical alternative for this comparison is whichever monster the
    bot has actually been fighting. None rows are skipped; returns None
    when no such cycles exist or on DB error.

    Matched `FarmMonster(%` until 2026-08-07, and that goal was deleted on
    2026-05-24 — so this returned None for every real character, and
    `low_yield_cancel_fires` (which needs an alternative) could not fire at all.
    """
    try:
        with Session(history._engine) as s:
            stmt = (
                select(Cycle.selected_goal)
                .where(
                    col(Cycle.character) == history._character,
                    col(Cycle.selected_goal).like(f"{grind_xp_repr_prefix()}%"),
                )
                .order_by(col(Cycle.id).desc())
                .limit(50)
            )
            rows = list(s.exec(stmt))
    except SQLAlchemyError:
        return None
    if not rows:
        return None
    counts: dict[str, int] = {}
    for r in rows:
        if r is not None:
            counts[r] = counts.get(r, 0) + 1
    if not counts:
        return None
    return max(counts, key=lambda k: counts[k])


def observed_task_pursuit_reprs(history: LearningStore, window: int = 200) -> list[str]:
    """Distinct `PursueTask(<code>)` reprs this character has actually recorded.

    Read back out of history rather than enumerated from the catalogue: the point
    is to group the reprs the WRITER emitted, and only history knows which those
    were."""
    try:
        with Session(history._engine) as s:
            stmt = (
                select(Cycle.selected_goal)
                .where(
                    col(Cycle.character) == history._character,
                    col(Cycle.selected_goal).like(f"{TASK_PURSUIT_PREFIX}%"),
                )
                .order_by(col(Cycle.id).desc())
                .limit(window)
            )
            rows = list(s.exec(stmt))
    except SQLAlchemyError:
        return []
    seen: list[str] = []
    for r in rows:
        if r is not None and r not in seen:
            seen.append(r)
    return seen


def busiest_task_pursuit_repr(task_code: str, game_data: GameData,
                              history: LearningStore) -> str | None:
    """The most-recorded task-pursuit repr in `task_code`'s taskmaster, or None.

    A single repr rather than the pool, because `cycles_for_progress` returns a
    MEDIAN cadence and medians do not pool — averaging medians across tasks of
    different lengths would invent a cadence no task ever had. The busiest repr
    is the same choice `_best_alternative_repr` makes for the monster side."""
    reprs = task_pursuit_reprs_for(
        taskmaster_for_item(task_code, game_data),
        observed_task_pursuit_reprs(history), game_data)
    if not reprs:
        return None
    return max(reprs, key=lambda r: expected_yield_per_cycle(r, history).sample_count)


def task_pursuit_yield(task_code: str, game_data: GameData,
                       history: LearningStore) -> Yield:
    """Per-cycle yield of pursuing tasks from the master that issues `task_code`'s
    skill — the current-activity rate `low_yield_cancel_fires` compares against.

    Pools every recorded `PursueTask(<code>)` whose code maps to the same
    taskmaster, weighting each by its own sample count so the result is a true
    per-cycle mean over the union and not a mean of means (which would let a
    3-cycle task outvote a 300-cycle one).

    An empty pool returns an empty `Yield`, i.e. sample_count 0 — a cold start,
    which the caller already treats as "no comparison possible". That is the
    honest answer for a character with no task history, and it is the state every
    character is in today: 0 of 22302 live cycles carry ANY task goal, so this
    guard stays quiet for a real reason now instead of a broken one."""
    taskmaster = taskmaster_for_item(task_code, game_data)
    reprs = task_pursuit_reprs_for(
        taskmaster, observed_task_pursuit_reprs(history), game_data)
    total_cycles = 0
    char_xp_total = 0.0
    gold_total = 0.0
    coins_total = 0.0
    skill_xp_totals: dict[str, float] = {}
    for goal_repr in reprs:
        y = expected_yield_per_cycle(goal_repr, history)
        # No `sample_count == 0` skip: `reprs` are read back out of THIS
        # character's own history, so every one of them has at least one cycle. A
        # zero would contribute zero to every total anyway and the
        # `total_cycles == 0` check below already returns the cold-start Yield —
        # the guard was redundant, and a line that cannot execute is a line no
        # test can honestly cover.
        total_cycles += y.sample_count
        char_xp_total += y.char_xp * y.sample_count
        gold_total += y.gold * y.sample_count
        coins_total += y.tasks_coins * y.sample_count
        for skill, rate in y.skill_xp.items():
            skill_xp_totals[skill] = skill_xp_totals.get(skill, 0.0) + rate * y.sample_count
    if total_cycles == 0:
        return Yield()
    return Yield(
        char_xp=char_xp_total / total_cycles,
        skill_xp={s: t / total_cycles for s, t in skill_xp_totals.items() if t != 0},
        gold=gold_total / total_cycles,
        tasks_coins=coins_total / total_cycles,
        sample_count=total_cycles,
    )


def low_yield_cancel_fires(
    state: WorldState, game_data: GameData, history: LearningStore | None
) -> bool:
    """True when the held task should be cancelled for a clearly-better monster
    alternative. Single source of truth for both LowYieldCancelGoal and the
    strategy means predicate.

    Fires when: a task is held (task_code set AND task_total > 0), there is
    FarmItems yield history and a best FarmMonster alternative with samples, and
    either the current char-XP/cycle is 0 while the alternative is positive
    (zero fast-path), OR project_task_completion confidence >= 0.5 and the
    alternative rate >= current rate * 1.5.

    The pure decision boundary is delegated to `low_yield_fires_pure` in
    `low_yield_boundary.py`; this function is the impure shell that fetches
    the LearningStore aggregates.
    """
    if history is None or not state.task_code or state.task_total <= 0:
        return False

    # The CURRENT activity's rate: task pursuit, pooled over the taskmaster that
    # issues tasks for the held item's skill (`yield_reprs.task_pursuit_reprs_for`).
    #
    # Was `expected_yield_per_cycle("FarmItems", ...)`, whose goal was deleted on
    # 2026-05-24 — 0 of 22302 live cycles matched, so this returned early every
    # single time and the guard was unreachable rather than merely quiet.
    farm_items_yield = task_pursuit_yield(state.task_code, game_data, history)
    if farm_items_yield.sample_count == 0:
        return False
    current_char_xp_per_cycle = farm_items_yield.char_xp

    alt_repr = _best_alternative_repr(history)
    if alt_repr is None:
        return False
    alt_yield = expected_yield_per_cycle(alt_repr, history)
    if alt_yield.sample_count == 0:
        return False
    alternative_char_xp_per_cycle = alt_yield.char_xp

    projection = project_task_completion(state, game_data, history)
    # Projection.None contributes confidence 0.0, which the pure boundary
    # rejects via the min_confidence gate UNLESS the zero-fast-path fires.
    confidence = projection.confidence if projection is not None else 0.0

    return low_yield_fires_pure(
        has_task=True,
        current_xp=current_char_xp_per_cycle,
        alt_xp=alternative_char_xp_per_cycle,
        confidence=confidence,
        farm_samples=farm_items_yield.sample_count,
        alt_samples=alt_yield.sample_count,
        margin=LOW_YIELD_ALTERNATIVE_MARGIN,
        min_confidence=LOW_YIELD_CONFIDENCE_THRESHOLD,
    )
