"""Phase G-B projections: throughput/yield estimates over the LearningStore.

Pure functions over recent Cycle history. Return None (or a low-sample
sentinel) when there's not enough data; callers must check and fall back to
hardcoded defaults during warm-up.

Spec: docs/superpowers/specs/2026-05-18-strategic-reasoning-design.md §2.
"""

import json
from dataclasses import replace

from pydantic import BaseModel, Field

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.equipment.equip_actions_core import equip_cost
from artifactsmmo_cli.ai.equipment.loadout_cache import pick_loadout_cached
from artifactsmmo_cli.ai.equipment.projection import project_loadout_stats
from artifactsmmo_cli.ai.expected_damage import expected_damage_per_fight
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_value_core import Combat, Rank
from artifactsmmo_cli.ai.learning.fight_loop_cost import cycles_per_kill
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.observed_rate_core import (
    rescale_observed_xp,
    sample_level,
)
from artifactsmmo_cli.ai.learning.rung_state_core import projected_max_hp
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.learning.yield_reprs import grind_xp_repr
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
    function of the gap between character and monster, and goes to zero ELEVEN
    levels above it. Without this field the rate is uninterpretable away from where it was
    measured, and reusing it anyway is exactly the defect
    `observed_rate_core.rescale_observed_xp` exists to undo. Carried on the same
    object, from the same rows, at no extra query."""


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
        char_xp_level=sample_level(levels),
    )


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
this projection's unit. Callers that DO want the duration — `tiers/
strategic_weights`, which combines it with move and deposit cooldowns into a
round-trip time — take `fight_loop_cost.TYPICAL_FIGHT_COOLDOWN_SECONDS`. One
constant serving both meanings under one wrong name is what made the confusion
invisible.

Nothing here may divide a reported cost by a duration, with ONE declared
exception that lives in `fight_loop_cost`: Rest is the single action whose
cooldown is not roughly uniform, so it is priced in Fight-equivalents rather than
counted as one. Charging it flat is what shut the defensive-gear channel."""


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

    Returns a PathPlan with `blocked=True` and `total_cycles=inf` on EITHER of
    two conditions at some intermediate level, and the second is the one that
    fires in practice:

    * no beatable monster exists at all, or
    * every beatable monster is GREY — beatable, and worth zero XP, so the rung
      has nothing that advances it (`best_xp_per_cycle <= 0`).

    Measured live 2026-08-18: C3P0 at level 19 had SEVEN winnable monsters and
    still blocked, because the best of them is `cow` at level 8 — a gap of 11,
    one past the zero-XP band — while the nearest monsters that pay (`pig` 19,
    `spider` 20, `ogre` 20) are unwinnable. R2D2 blocked the same way at a
    projected level 26 with eleven winnable. A blocked walk is therefore usually
    a COMBAT WALL and not an empty map, and reading it as the latter misdiagnoses
    a character that needs gear as one that needs a monster.

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
    # What the character is WEARING as the walk starts. Each rung's chosen loadout is
    # compared against this and the difference charged as equip actions (S-020),
    # then this advances — so gear is paid for when it goes on, not every rung it
    # stays on.
    worn: dict[str, str | None] = dict(state.equipment)

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
        # THE BEATABILITY MARGIN SURVIVES. This filter (1 <= lvl <= sim_level + 1)
        # used to have two call sites, and the plan that identified player.py:2780
        # as diagnostic-only missed the second: `tiers/horizon_contribution` fed
        # the objective's GEAR-vs-XP branch ranking, which was a live decision.
        # Wave 3b deleted that whole ranking, so this is the sole call site again —
        # but it is now the DECIDING one, not a diagnostic. The filter is Lean-diff-locked
        # (`Formal/CheapestPath.lean`) and mutation-anchored (`formal/diff/mutate.py`:
        # "drop the +1 beatability margin"), so changing it carries a proof obligation.
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
                # grey-mob rule (0 XP eleven or more levels above a monster) from every
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
                # `fight_loop_cost.rest_actions_per_fight`.
                xp_per_cycle = (game_data.xp_per_kill(code, sim_level, wisdom=wisdom)
                                / monster_cycles)
            if xp_per_cycle > best_xp_per_cycle:
                best_code = code
                best_xp_per_cycle = xp_per_cycle
                best_cycles_per_kill = monster_cycles

        if best_code is None or best_xp_per_cycle <= 0:
            return PathPlan(target_level=target_level, total_cycles=float("inf"),
                            segments=segments, blocked=True)

        # THE EQUIP IS AN ACTION (S-020). Beatability above was judged with the best
        # loadout the character is CARRYING, not merely wearing — `predict_win` picks
        # from inventory ∪ equipped, which the gear branch depends on. But the
        # executor has to spend a cycle putting each piece on, and S-004's unit is
        # executed actions, so leaving it unpriced omits a real cost and hands the
        # projection its upgrade for free.
        #
        # Charged ONCE per rung, against what the character is wearing when it
        # arrives, then carried forward — so a loadout held across ten rungs is paid
        # for once rather than ten times, and a piece the rung's level newly unlocks
        # (S-015) is paid for at the rung that unlocks it.
        #
        # The loadout re-picked here is the one the CHOSEN monster's verdict would
        # use. It is OFTEN a `pick_loadout_cached` hit on work `predict_win` already
        # did, but not always: `is_winnable` short-circuits on a learned-loss veto or
        # a monotonic-win inference and never reaches `predict_win` at all, and then
        # this is a real miss. Measured cost of the whole clause, live over five
        # walks each: C3P0 297 -> 329 ms, R2D2 284 -> 319 ms, about +10%. One extra
        # pick per RUNG, never per monster.
        rung_loadout = pick_loadout_cached(
            Combat(game_data.monster_attack(best_code),
                   game_data.monster_resistance(best_code), dict(rung.attack)),
            rung, game_data)
        equips = equip_cost(worn, rung_loadout)
        worn = rung_loadout

        cycles_for_this_level = xp_to_next / best_xp_per_cycle + equips
        segments.append(PathSegment(
            from_level=sim_level,
            to_level=sim_level + 1,
            monster_code=best_code,
            estimated_cycles=cycles_for_this_level,
            xp_per_cycle=best_xp_per_cycle,
            cycles_per_kill=best_cycles_per_kill,
        ))
        sim_level += 1
        # S-019 — NO SURPLUS IS EVER FORMED. `cycles_for_this_level` is a CONTINUOUS
        # quotient with no per-rung rounding, so each rung's requirement is met
        # exactly and there is nothing left over to carry. Only the first rung starts
        # from the character's actual progress; every later rung needs a whole
        # level's worth.
        #
        # This is NOT "exactly equivalent to carrying the overshoot", which is what
        # this comment used to claim. The physical climb executes WHOLE actions, so
        # the action that crosses a boundary earns its award at the DEPARTING rung's
        # rate and spills the excess into the next rung, where this model charges it
        # at the ARRIVING rung's rate. The two agree only if the rates agree, and
        # `xp_per_kill` carries the character level in both its base term and its
        # penalty step, so they essentially never do. The gap is bounded by the
        # excess of one action per boundary and is declared in S-019 rather than
        # modelled: closing it needs the per-rung accumulator this design avoids.
        #
        # Do not "fix" this by taking integral kills per rung. That would introduce
        # the discarded surplus S-019 forbids and over-price a full climb by roughly
        # one kill per rung. `test_a_rung_is_not_charged_a_whole_extra_kill` pins it.
        xp_to_next = max(1, state.max_xp)

    total = sum(s.estimated_cycles for s in segments)
    return PathPlan(target_level=target_level, total_cycles=total, segments=segments)
