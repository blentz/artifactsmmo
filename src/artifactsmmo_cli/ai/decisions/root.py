"""The ROOT graph: named `Decision[MetaGoal]`s that answer "which root".

Wave 3 replaces the flat scored ranking over candidate roots
(`progression_tree.decide_tree`'s argmax) with a resolution walk over named
nodes, exactly as wave 2 replaced `objective_step_goal`'s if-pile with
`decisions/obtain_item.py`. The ranking answered "which root scores highest" —
two unrelated scales sharing one column (live 2026-08-08: gear showed 2.6e8
against the trunk's 1.0). This graph answers "which root does the tier ladder
select", and its `trail` is a named path a reader can follow instead of a
number they could not.

`decide_tree` calls `resolve_root` directly — THE FLIP (task 6,
`PLAN_wave3a_cutover`) wired it in; this is no longer groundwork sitting
uncalled, it is what every live cycle's root comes from.

One module, five behavioural classes: the same shape as
`decisions/obtain_item.py`, whose six `Decision` subclasses share a file
because they are ONE graph — each class is a branch of it, they are only ever
constructed by one another, and splitting them across five files would put
mutually-referencing halves of a single control-flow structure behind five
imports without making any of them independently usable.

THE STANDALONE SKILL ROOT IS A RESTORED CAPABILITY, NOT A NEW FEATURE.
`ef67c1d6` ("refactor(flip)!: delete the flat scalar ranking") deleted four
standalone `ReachSkillLevel` root emitters at once — craft bootstrap, the
alchemy gather-bootstrap, the recipe curve and the skill-50 long-haul — on the
premise its own message states: "skills are pure prerequisites now". That
premise is false for any skill whose output nothing equips. After it, the ONLY
producer of a `ReachSkillLevel` was `IsThisTargetBlocked` off
`GearTarget.blocking_skill`, which is a GEAR target's own crafting skill, so a
skill no gear target can name had no producer at all and the bot could not
choose to raise it. Live consequence, measured on
`~/.cache/artifactsmmo/learning.db`: 33,840 cooking XP earned, 99.6% of it as a
side effect of `Craft(cooked_*)` legs inside `RestoreHP` plans — an entire
skill levelled by accident.

`_orphan_skill_roots` restores the seam, as a rule about the CATALOGUE rather
than about cooking, and `resolve_root` offers its roots one rank BELOW the
trunk. It adds no node and no argmax: a root that has to be CHOSEN against gear
is a ranking, and deleting one is what this epic is for. `CanIClearMyTier`
records the measurement that rejected the node.

Spec: `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md` §5.1,
§5.3. One place this module deliberately departs from that spec, recorded in
`.superpowers/sdd/PLAN_wave3a_cutover/task-4-report.md` (the spec's other
disagreement at task-4 time — §5.3 saying "Six nodes" and drawing five — was
the spec's own error; the spec text has since been corrected to "Five nodes"
and no longer disagrees with this module):

* §5.3's `IsThereACombatTarget` "yes" arm names
  `ReachCharLevel(tier_of_level(game_data, state.level))`, which is a root the
  character has ALREADY satisfied (`tier_of_level` returns the highest rung at
  or below `state.level`). Task 4 transcribed it because its contract was
  "change no behaviour"; THE FLIP (task 6) is the task that decides, and it
  decided against the spec — see `_next_rung_above`.
"""

from dataclasses import dataclass, field
from fractions import Fraction

# `level_skill` is imported as a MODULE, not as `from ... import LevelSkill`,
# and that is load-bearing rather than stylistic. `actions/level_skill.py`
# imports `ai.tiers.skill_grind_target`, which runs `ai/tiers/__init__.py` ->
# `strategy` -> `progression_tree` -> THIS module: so whenever `level_skill` is
# the first of the two to be imported (it is, via `ai/actions/factory.py` from
# `ai/player.py`, and in `audit/open_rung_completeness`), root.py executes while
# `level_skill` is only half built and a NAME import raises ImportError.
# Binding the module object defers the attribute lookup to CALL time, by which
# point both halves are complete. Exactly the idiom `tiers/strategy.py:13` and
# `tiers/progression_tree.py:37` already use on each other, for this reason.
from artifactsmmo_cli.ai.actions import level_skill
from artifactsmmo_cli.ai.combat_deficit import deficit_upgrade_target
from artifactsmmo_cli.ai.decision import Decision, resolve_node

# MODULE import, same idiom as `level_skill` above and for the same reason:
# `route` imports `tiers.meta_goal`, which runs `tiers/__init__` ->
# `strategy` -> `progression_tree` -> THIS module, so whichever of the two
# is reached first executes while the other is half built. A NAME import
# of `route_price` raises ImportError when `decisions.route` is the entry.
from artifactsmmo_cli.ai.decisions import route as _route
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_horizon import HORIZON_GEAR, resolve_task_horizon
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
    contender_focus_key,
    focus_key_str,
)
from artifactsmmo_cli.ai.tiers.objective import (
    CharacterObjective,
    GearTarget,
    _gear_candidates_by_type,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    dhondt_step,
    milestone_pure,
    run_falloff,
)
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, tier_of_level
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState


@dataclass(frozen=True)
class RootResolution:
    """The walk's answer: the root to pursue, ordered alternatives, and the
    trail that produced it.

    `alternatives` is NOT a ranking. It is the ordered remainder of the ONE
    list-valued node in the graph (`WhichSlotIsFurthestBehind`), then the
    trunk, then the orphan skill roots (`_orphan_skill_roots`) — three ordered
    groups, none of them scored against each other. It exists because
    `objective_step_goal` can still return None for a
    resolved root (`ReachCharLevel` with no combat target, the long-haul
    items-task defer) and because `_servable_promotion` still needs somewhere
    to walk. Deleting it regresses three named live traces — see
    `strategy_driver._resolve_step_goal` and `progression_tree`'s
    fallback-order comment.

    `trail` is the ordered `Decision.name`s the walk visited. It replaces the
    ranking as the plan pane's "why": a named path is a better answer to "why
    this root" than a number was.
    """

    root: MetaGoal | None
    alternatives: tuple[MetaGoal, ...]
    trail: tuple[str, ...]
    aged: bool = False
    """Whether `WhichSlotIsFurthestBehind` took the d'Hondt interleave rather
    than its unaged fast path — see `RootWalk.aged`. `decide_tree` copies it
    onto `StrategyDecision.aged_pick`, which is what gates the player's seat
    bump (`GamePlayer._charge_focus`)."""


@dataclass
class RootWalk:
    """The one mutable side-channel the walk needs, threaded through the nodes.

    Two things `resolve_node` cannot hand back on its own:

    * `trail` — `resolve_node` keeps its visited list (`seen`) private and
      only surfaces it in the `RecursionError` message. Rather than widen a
      signature three other call sites already depend on, each node appends
      its own `name` as it resolves; the result is byte-identical to `seen`
      because `resolve_node` calls each visited node's `resolve` exactly once.
    * `sibling_targets` — `WhichSlotIsFurthestBehind` ranks every blocked
      slot but a `Decision` returns ONE child. The remainder is what
      `RootResolution.alternatives` is made of, so it is deposited here.

    A node that is resolved OUTSIDE the main walk (`resolve_root` re-runs
    `IsThisTargetBlocked` once per sibling to turn it into a `MetaGoal`) is
    handed a throwaway `RootWalk`, so those visits never pollute the trail.

    * `aged` — whether `WhichSlotIsFurthestBehind` took the d'Hondt
      interleave rather than its unaged fast path. `GamePlayer._charge_focus`
      gates the SEAT bump on it, so the schedule and the ledger advance in
      lockstep. It is set by the ONE node that makes the choice and read
      straight off `RootResolution`, which is strictly better than the shape
      it replaces: `decide_tree` used to re-derive the same verdict as a
      clause-for-clause MIRROR of `focus_aging_pick`'s fast-path guard, and
      that duplicate carried its own drift warning and two mutation anchors.
    """

    trail: list[str] = field(default_factory=list)
    sibling_targets: list[tuple[str, GearTarget]] = field(default_factory=list)
    aged: bool = False


def _target_rung(game_data: GameData, code: str) -> int:
    """The ladder rung `code` sits on.

    Raises rather than defaulting when the item is absent from game data: an
    item the objective picked as a gear target and the catalogue does not know
    is a data fault, and a silently-substituted rung would rank it.
    """
    stats = game_data.item_stats(code)
    if stats is None:
        raise ValueError(
            f"gear target {code!r} has no item stats in game data — cannot "
            f"place it on the ladder")
    return tier_of_level(game_data, stats.level)


def _next_rung_above(game_data: GameData, level: int) -> int:
    """The lowest ladder rung STRICTLY ABOVE `level`; the trunk milestone when
    the ladder is exhausted.

    NOT STRICTLY ABOVE AT THE CAP, and the honest statement matters because the
    cap is exactly where the risk was flagged. Past the last rung this falls
    back to `milestone_pure`, whose L50 fixed point is `milestone_pure(50) ==
    50` — so a level-50 character gets `ReachCharLevel(50)`, which
    `is_satisfied` reports True, and all three consequences named below RETURN
    at the cap. That is not a defect this function can fix: there is no level
    above 50 to name, and `CanIClearMyTier` reaches the same fixed point by the
    same route. It is the L50 capstone's own open question
    (`project_l50_unconditional_descent`), pinned by
    `test_combat_target_root_at_the_level_cap_is_the_satisfied_capstone` so it
    cannot be rediscovered by accident.

    THE FLIP's correction to spec §5.3, which named
    `tier_of_level(game_data, state.level)` here — the highest rung AT OR BELOW
    the level, i.e. a root the character has already satisfied. Three things
    that root broke, all of them silent:

      * `chosen_root.is_satisfied(...)` is True, so the walk's answer to "what
        should this character pursue" is something it has already done;
      * `objective_needs` reads `char_xp = state.level < root.level`, so an
        already-met rung yields an EMPTY `NeedSet` and switches the arbiter's
        PURSUE_TASK worth gate OFF — a live gate disabled by a level nobody
        chose;
      * the gap `target - level` is negative, so the long-haul items-task
        stand-down in `objective_step_is_fight_pure` can never engage, whatever
        the character is actually doing.

    The rung strictly above is what the arm MEANT: this is the "there is a
    monster to fight" arm, and the reason to fight is to reach the next gear
    breakpoint. Both sibling arms name unreached levels and `CanIClearMyTier`
    already falls back on `milestone_pure`, which is also the level-50 fixed
    point (`milestone_pure(50) == 50`) once the ladder runs out.
    """
    rungs = ladder(game_data)
    if not rungs:
        # RAISES, exactly as its sibling `tier_of_level` does on the same
        # input. `ladder` is empty only for a catalogue with no equippable
        # items, which the API cannot produce; defaulting here while
        # `tier_of_level` refused would make the two disagree about the same
        # data fault, and "tier_of_level correctly refuses it" is the argument
        # six test fixtures were changed on.
        raise ValueError("no equippable items in game data — cannot derive a ladder")
    higher = [rung for rung in rungs if rung > level]
    return higher[0] if higher else milestone_pure(level)


def _tier_gap(slot: str, target: GearTarget, state: WorldState,
              game_data: GameData) -> int:
    """How many ladder rungs `slot` is behind its target.

    An EMPTY slot counts as rung 0 — strictly below the ladder's first rung,
    never `tier_of_level(game_data, 0)` (which is `rungs[0]`, the first rung).
    So an empty slot outranks an occupied slot aiming at the same rung, which
    is the empty-slot dominance the kernel already proves
    (`Formal.GearPolicy.armor_strictly_dominates_empty_slot`) and the live
    2026-06-11 trace paid for: level 6, body/leg/amulet empty, 148 consecutive
    fights at -72.8 HP each.
    """
    worn = state.equipment.get(slot)
    worn_rung = 0 if worn is None else _target_rung(game_data, worn)
    return _target_rung(game_data, target.code) - worn_rung


def _slot_order(item: tuple[str, GearTarget], state: WorldState,
                game_data: GameData) -> tuple[int, int, int]:
    """Descent key for `WhichSlotIsFurthestBehind`: furthest behind first,
    then the higher-rung target, then the API schema's own slot order.

    The last component is `EQUIPMENT_SLOTS.index`, the order the character
    schema declares its slots in — NOT `sorted(slot)`. An alphabetical
    tiebreak is the defect `feedback_no_alphabetical_tiebreak` names; the
    schema order is a declared vocabulary and is the only total order over
    slots this codebase actually publishes.
    """
    slot, target = item
    return (-_tier_gap(slot, target, state, game_data),
            -_target_rung(game_data, target.code),
            EQUIPMENT_SLOTS.index(slot))


def _gear_nameable_skills(game_data: GameData) -> frozenset[str]:
    """Every skill SOME gear target could name.

    A gear target names exactly one skill — `GearTarget.blocking_skill`, which
    `objective.classify_target` reads off the TARGET's own `crafting_skill` —
    and a gear target is whatever `objective.gear_targets_with_blockers` hands
    that classifier. So this asks the SHEET BUILDER, `_gear_candidates_by_type`,
    which items can become candidates at all, capped at the catalogue's own
    `max_character_level` because the question is about the GAME, not about this
    cycle's tier. Nothing about the candidate rule is restated here, which is
    the point: the previous version DID restate it, and drifted.

    No `EQUIPMENT_SLOTS` re-filter, deliberately. `gear_targets_with_blockers`
    writes `[s for s in ITEM_TYPE_TO_SLOTS[type_] if s in EQUIPMENT_SLOTS]`, but
    that filter is a no-op by construction: `gear_taxonomy._derive_type_to_slots`
    and `world_state.EQUIPMENT_SLOTS` are both built from the SAME
    `CharacterSchema` `*_slot` fields, so every slot the first names is in the
    second. Copying it here would be a branch no input can take.

    THE DRIFT, AND WHAT IT COST. This function used to read
    `ITEM_TYPE_TO_SLOTS` straight off `all_item_stats` and concluded that
    ALCHEMY is nameable — 20 of its 25 recipes are `utility` potions and
    `utility1_slot`/`utility2_slot` do accept them — so `_orphan_skill_roots`
    declined it. But `_gear_candidates_by_type` skips `stats.type_ ==
    "utility"` outright (the utility slots are served by the potion-supply
    path — `utility_slot.utility_slot_for` plus the `EquipAction` at
    `craft_ladder.py:140` — not by the gear sheet; this named
    `objective.utility_potion_targets` until 2026-08-27, which only DESIGNATES
    the slots — see its own docstring for what consults it), and alchemy's
    other five recipes are `consumable`, which maps to no slot. Measured on the
    committed bundle: a gear target named alchemy in 0 of the 42 scenarios, and
    could not — alchemy was as orphaned as cooking was before `b39705eb`, with
    the orphan rule refusing it on a nameability claim no code path could
    honour. The O1 census's routed count moves 194 -> 236 of 336 cells and 7 of
    8 skills -> 8 of 8 with this fix; residuals stay 0 because the rule's other
    conjunct is `LevelSkill(S, C+1).is_applicable`, the census's own predicate.

    Measured on the committed bundle after the fix: gearcrafting,
    weaponcrafting and jewelrycrafting — exactly the three skills whose output
    the gear sheet ranks."""
    nameable: set[str] = set()
    for ranked in _gear_candidates_by_type(
            game_data, game_data.max_character_level).values():
        for _value, code in ranked:
            skill = game_data.all_item_stats[code].crafting_skill
            if skill:
                nameable.add(skill)
    return frozenset(nameable)


def _orphan_skill_roots(state: WorldState,
                        game_data: GameData) -> tuple[ReachSkillLevel, ...]:
    """THE RULE, and the whole of it:

        a skill with an open, XP-positive rung that NO gear target can name
        still deserves a root.

    Two conjuncts, each read from production rather than restated:

    * "no gear target can name it" is `_gear_nameable_skills` — a property of
      the CATALOGUE, not of this cycle's gear sheet. Deliberately not "no
      current target names it": that would hand weaponcrafting a standalone
      root every cycle the weapon slot happens to be satisfied, which is a
      skill that IS a prerequisite doing prerequisite work. The orphans are the
      skills the prerequisite seam structurally cannot reach.
    * "an open, XP-positive rung" is `LevelSkill(S, C+1).is_applicable` — the
      SAME predicate `ReachSkillGoal`'s only action offers and the same one the
      O1 census (`audit/open_rung_completeness`) verdicts a cell on. A skill
      with no open rung gets NO root: emitting one would be the census's
      `o1_silent_stall` residual — an unplannable root with no node saying why —
      which is the failure this seam is supposed to make impossible, not one it
      may cause.

    Measured on the committed bundle the rule admits exactly four skills:
    cooking, fishing, mining and woodcutting — the four whose every recipe
    produces a `consumable` or a `resource`. Cooking is the instance the epic
    named; the other three arrive because the rule is about the catalogue.

    ORDER: ONE INTEGER, `state.level - skill level` — how far the skill trails
    the character, largest first — with ties broken by `SKILL_NAMES`, the
    schema vocabulary `world_state` derives from the API's own enums (never
    `sorted()` as a decision key; see `feedback_no_alphabetical_tiebreak`).
    The integer has a meaning: the game tiers its content by level, so the
    skill furthest behind the character is the one whose content is furthest
    from what the character can currently use, and it is the same "furthest
    behind" quantity `WhichSlotIsFurthestBehind` ranks slots on.

    DO NOT ADD A SECOND TERM. This epic exists to delete a flat scalar ranking
    that multiplied four weights into one column; the pressure that produced
    those four will apply here (wave-3 design §8 R2 says so about the sibling
    node, and this node is the same shape). A tie-break that is not the
    declared vocabulary, or a weight beside the gap, turns a named order into
    an argmax again — at which point the reader is back to a number they cannot
    follow. If the order is wrong, change WHICH integer it is, not how many.
    """
    nameable = _gear_nameable_skills(game_data)
    orphans = [
        skill for skill in SKILL_NAMES
        if skill not in nameable
        and level_skill.LevelSkill(
            skill=skill, target_level=state.skills.get(skill, 1) + 1
        ).is_applicable(state, game_data)]
    orphans.sort(key=lambda skill: (state.skills.get(skill, 1) - state.level,
                                    SKILL_NAMES.index(skill)))
    return tuple(ReachSkillLevel(skill=skill,
                                 level=state.skills.get(skill, 1) + 1)
                 for skill in orphans)


class IsAFightBlockingMe(Decision[MetaGoal]):
    """Is the character held on a fight it cannot win, with nothing else to fight?

    THE STANDING ARM OF `RegearEdge`, ABSORBED (wave 4). `regear_edge.py` computed
    `craftable and not winnable_alternative` and then
    `resolve_task_horizon(...).verdict == HORIZON_GEAR`, feeding
    `ctx.regear_level_up`, which fired the GEAR_REVIEW GUARD — and a guard
    preempts the objective step outright, which is what froze R2D2's character
    XP for 981 cycles / 31.6 h in 2026-08-21/22.

    IT IS A NODE AND NOT A LATCH, AND THAT IS ENFORCED BY THE TYPE. A `Decision`
    is constructed fresh by `resolve_root` every cycle and carries nothing across
    cycles, so this condition cannot become sticky. Do NOT thread `prev_level`,
    `last_outcome`, or any persisted boolean into this signature: the moment a
    node's answer depends on an event N cycles ago, this IS the guard again and
    the freeze is back under a new name.

    ONLY `HORIZON_GEAR` TAKES THE POSITIVE ARM. The other two verdicts fall
    through to the tier arm, and that is a decision with a reason on each side:

      * `HORIZON_OUT_OF_REACH` — no chain closes the fight at this level, so
        there is nothing to build for it. `tiers/means.py:277-278` fires
        `TASK_CANCEL` on exactly this verdict; this node must not compete.
      * `HORIZON_LEVEL_UP` — one level would close it, and this node only fires
        when `ctx.combat_monster is None`, i.e. with NO monster worth fighting.
        A level goal here would have no beatable monster in its
        `relevant_actions`. That verdict is served from the EDGE instead — a
        real loss or level-up, where the cascade does find something — by
        `map_guard`'s surviving LEVEL_UP arm. Pinned by
        `test_an_out_of_horizon_task_leaves_the_character_doing_its_own_work`:
        letting the objective's own XP grind run IS the level-up being pursued.

    `ctx.combat_monster`, not a separate `winnable_alternative` parameter.
    `player.py` computes `_winnable_farm_target()` ONCE and hands the same value
    to the latch and to `_selection_context`, so this is the same fact today —
    but as two parameters they could drift, and the sibling node
    `IsThereACombatTarget` already reads `ctx`. One read.

    `has_craftable_upgrade_any_slot` is NOT re-tested here. In the latch it was
    the AND-guard that stopped the standing arm firing with nothing to build; in
    the graph that job belongs to the child — `WhichSlotClosesTheFight` returns
    the tier arm when the deficit chain is empty. Re-testing it here would be a
    second, coarser opinion (`find_upgrade_target` is monster-BLIND — the
    ten-hour `iron_boots` failure) standing in front of the monster-aware one.
    """

    name = "IsAFightBlockingMe"

    def __init__(self, objective: CharacterObjective, walk: RootWalk) -> None:
        # `objective` is carried, not used, on the positive arm: both children
        # need it (`IsMyGearBehindMyTier` directly, `WhichSlotClosesTheFight`
        # for `classify_target`), and this is the walk's entry so there is
        # nowhere above it to hold one.
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        if ctx.combat_monster is not None:
            return IsMyGearBehindMyTier(self.objective, self.walk)
        horizon = resolve_task_horizon(state, game_data)
        if horizon is None or horizon.verdict != HORIZON_GEAR:
            return IsMyGearBehindMyTier(self.objective, self.walk)
        return WhichSlotClosesTheFight(self.objective, self.walk)


class WhichSlotClosesTheFight(Decision[MetaGoal]):
    """The one acquisition that most improves the margin against the held task's
    monster, per action spent.

    `combat_deficit.deficit_upgrade_target`, ABSORBED (wave 4). It was
    `map_guard`'s GEAR_REVIEW branch, the only link the bot has between "I cannot
    win this fight" and "build this". Its predecessor was a monster-BLIND
    `_best_by_value` scan that chose `iron_boots` — already worn, absent from all
    24 items that improved the pig margin — while the weapon that moved
    `rounds_to_kill` went unbuilt for ten hours.

    THIS IS NOT A FIFTH RANKING MULTIPLIER AND NOT A NEW ARGMAX. It adds no
    scoring surface: `combat_deficit`'s greedy walk already exists, is already
    called in production, and is already ranked on margin gain per acquisition
    action. Wave 4 changes WHERE it is called, not WHAT it computes. The wave-3
    precedent (`WhichSlotIsFurthestBehind`) applies verbatim: no multiplier may
    be added to this ranking. If a future need appears to weight this against the
    tier gap, that is a request for a fifth multiplier and must be refused — the
    two are in DIFFERENT ARMS of a branch, never summed, which is exactly why
    neither needs a scale.

    Falls through to the tier arm — the honest wall — when the priced walk names
    nothing. That is `combat_deficit`'s own "unwinnable and I do not know what to
    build" case, and the graph's answer to it is the objective's own next step,
    not a monster-blind guess.
    """

    name = "WhichSlotClosesTheFight"

    def __init__(self, objective: CharacterObjective, walk: RootWalk) -> None:
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)

        def actions_of(code: str, slot: str) -> int:
            # Through `route_price`, not `acquisition_actions` directly: wave 6's
            # O6 census permits exactly one pricing import under `ai/decisions/`,
            # and it is `decisions/route.py`. `equip` is derived there from
            # `goal.slot` — the old hand-written `equip=True` asserted a second
            # time a fact the slot already carried.
            return _route.route_price(ObtainItem(code, 1, slot=slot), state,
                                      game_data, ctx, history)

        target = deficit_upgrade_target(state, game_data, actions_of=actions_of)
        if target is None:
            return IsMyGearBehindMyTier(self.objective, self.walk)
        code, slot = target
        # Reuses `IsThisTargetBlocked` rather than mapping the code to a goal
        # itself: that node is the one place that reads a `GearTarget`'s four
        # shapes, and a second reader is a second chance to read them wrong.
        return IsThisTargetBlocked(
            slot, self.objective.classify_target(code, state), self.walk)


class IsMyGearBehindMyTier(Decision[MetaGoal]):
    """Does the gear-target tier want anything this character does not wear?

    `gear_targets_with_blockers` is the wave-2 objective walk that reports a
    target per slot TOGETHER with what stands in front of it, instead of
    dropping the unattainable ones on the floor the way `near_term_gear` does.
    This is its first production consumer.
    """

    name = "IsMyGearBehindMyTier"

    def __init__(self, objective: CharacterObjective, walk: RootWalk) -> None:
        self.objective = objective
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        targets = self.objective.gear_targets_with_blockers(state, history)
        if not targets:
            return IsThereACombatTarget(self.walk)
        return WhichSlotIsFurthestBehind(targets, self.walk)


class WhichSlotIsFurthestBehind(Decision[MetaGoal]):
    """The largest tier gap among the blocked slots wins — UNTIL the winner has
    held the decision past its farm window, at which point the d'Hondt
    interleave hands cycles to the alternatives. The rest become
    `RootResolution.alternatives`, in `_slot_order`.

    `targets` is never empty: the only constructor call site is
    `IsMyGearBehindMyTier.resolve`, inside its `if not targets` NEGATIVE arm.

    THE ANTI-STARVATION FIX LIVES HERE (reconnected, wave 3a fix-round 1).
    `_slot_order` alone is a pure, history-free total order over a set that
    does not change while the character makes no progress, so it re-elects the
    same slot every cycle forever. That is precisely the ring2 shape the
    arbiter-starvation epic was written for: a target whose only route is an
    unbeatable monster's drop, held once, so it is a live candidate that PLANS
    (a `Fight`) and never completes. Nothing else in the walk catches it —
    `_servable_promotion` demotes what the planner CANNOT SERVE, and this root
    can be; and it does not leave the sheet either, because
    `gear_targets_with_blockers` deliberately keeps unattainable targets.

    Two arms, inherited from the shape `focus_aging_pick` had before wave 3b
    deleted it (this node is now the only place that shape exists):

    * every candidate inside the flat farm window (`focus <= FOCUS_FLAT`) —
      the head is `_slot_order`'s argmax, BIT-IDENTICAL to the history-free
      walk. No jitter for fresh roots, and every ledger-free caller (the whole
      offline scenario set, `NO_PROFILE_CONTEXT`) is unaffected.
    * otherwise — the head is one `dhondt_step` over `tier_gap * falloff(focus)`
      GIVEN the seats handed out so far, so a decayed stuck root sheds cycles
      to reachable alternatives without ever being abandoned (`FOCUS_FLOOR` is
      strictly positive). `walk.aged` records that this happened; the player
      bumps exactly one seat for it.

    The weight is the TIER GAP, not `pursuit_value`: the gap is what
    `_slot_order` already ranks on, so the aged and unaged arms decay the same
    quantity and a fully-inert ledger cannot reorder anything.
    """

    name = "WhichSlotIsFurthestBehind"

    def __init__(self, targets: dict[str, GearTarget], walk: RootWalk) -> None:
        self.targets = targets
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        ranked = sorted(self.targets.items(),
                        key=lambda item: _slot_order(item, state, game_data))
        head = self._aged_head(ranked, state, game_data, ctx, history)
        self.walk.sibling_targets = [item for item in ranked if item is not head]
        slot, target = head
        return IsThisTargetBlocked(slot, target, self.walk)

    def _ledger_key(self, slot: str, target: GearTarget, state: WorldState,
                    game_data: GameData, ctx: SelectionContext,
                    history: LearningStore | None) -> tuple[str, str]:
        """The ledger key this slot would be charged under if it won.

        Keyed on the ROOT the slot RESOLVES TO, not on `(slot, target.code)`,
        because that root is what `GamePlayer._charge_focus` charges. The two
        differ for exactly the cases the flip introduced: a skill-gated slot
        resolves to a `ReachSkillLevel` and a material-gated one to a slot-less
        `ObtainItem`. Reading the sheet entry here while the player wrote the
        resolved root would leave the two halves permanently unable to meet —
        the fix-round-2 defect.

        NEVER None, and by the TYPE rather than by a runtime check:
        `IsThisTargetBlocked.resolve` returns `ObtainItem | ReachSkillLevel`,
        which is exactly `contender_focus_key`'s domain. `focus_key`'s nullable
        arms exist for `GamePlayer`, whose committed root can be the trunk or
        the wall; neither can arrive here, and the `key is None` fallbacks this
        used to feed were dead lines the coverage gate could not see
        (`branch = false`). Their named failure mode is worth keeping in view:
        a future arm returning `ReachCharLevel` would have been weighted under
        its raw `slot` while the player wrote nothing for it, so that root
        would never take a seat and could monopolise the interleave —
        starvation reintroduced by a different door. The union above is what
        now makes that unrepresentable.

        A throwaway `RootWalk`: this is a conversion, not a visit, so it must
        not append to the trail. Same idiom as `resolve_root`'s sibling
        conversion — and passed the SAME `history`, not `None`, so the two
        conversions cannot disagree if `IsThisTargetBlocked.resolve` ever
        grows a history-dependent arm (inert today: it does not read
        `history`)."""
        return contender_focus_key(IsThisTargetBlocked(
            slot, target, RootWalk()).resolve(state, game_data, ctx, history))

    def _aged_head(self, ranked: list[tuple[str, GearTarget]], state: WorldState,
                   game_data: GameData, ctx: SelectionContext,
                   history: LearningStore | None) -> tuple[str, GearTarget]:
        """`ranked[0]`, or the interleave's pick once anything has aged."""
        keys = [self._ledger_key(slot, target, state, game_data, ctx, history)
                for slot, target in ranked]
        focus = [ctx.gear_focus.get(key, 0) for key in keys]
        if all(level <= FOCUS_FLAT for level in focus):
            return ranked[0]
        # Apportioned over `focus_key_str`, the SAME scalar the player's seat
        # ledger is keyed by. Two slots that resolve to one root (two slots
        # gated on the same skill) collapse onto one entry ON PURPOSE — it is
        # one piece of work — and `next(...)` below then returns the
        # highest-ranked of them, which is `_slot_order`'s own answer.
        #
        # `max(1, gap)`: a slot can only be a target because something wants
        # replacing, but an equal-rung swap scores 0 and a zero weight is one
        # `dhondt_step` can never elect — which would be starvation reinstated
        # by the very mechanism that exists to prevent it.
        # `run_falloff`, not `falloff`: the weight is sampled once per
        # INTERLEAVE_RUN so it does not move between seat bumps. Otherwise the
        # decay band re-thrashes — the seat cadence holds the QUOTIENT still,
        # but inside the band `falloff` shrank the winner's weight every cycle
        # and the argmax flipped anyway (81% of transitions, median run 1).
        # Past the band the two are identical by construction.
        weighted = [
            (focus_key_str(key),
             Fraction(max(1, _tier_gap(slot, target, state, game_data)))
             * run_falloff(level))
            for (slot, target), key, level in zip(ranked, keys, focus, strict=True)]
        winner = dhondt_step(weighted, ctx.interleave_seats)
        assert winner is not None  # `ranked` is non-empty; see the docstring
        self.walk.aged = True
        return next(item for item, weight in zip(ranked, weighted, strict=True)
                    if weight[0] == winner)


class IsThisTargetBlocked(Decision[MetaGoal]):
    """What actually stands in front of this slot's target.

    `GearTarget` carries the blocker as TYPED fields, and its one producer
    (`objective.classify_target`, objective.py:447-457) emits exactly FOUR
    shapes, read here with no guessing and no string parsing:

        blocking_skill=S, blocking_skill_level=L, blocker=None -> skill-gated
        blocker=None,     blocking_skill=None                  -> attainable
        blocker=<code> == self.code                            -> its OWN blocker
        blocker=<code> != self.code                            -> material-gated

    Spec §5.3's table names only the first three; the fourth is the last arm
    of `classify_target` and is handled below.

    The skill test runs FIRST because a skill-gated target also has
    `blocker=None`; testing `blocker is None` first would report it as
    attainable. That is the same masking defect `classify_target`'s own
    docstring warns against, one layer up.

    `resolve` narrows its return type all the way to `ObtainItem |
    ReachSkillLevel`: every arm returns one of those two, this node has no
    `Decision` child and no None arm. The narrowing is load-bearing twice over
    — it lets `resolve_root` reuse this node to convert a sibling target
    without inventing an unreachable None branch, and (fix-round 3) it lets
    `_ledger_key` return a NON-optional key straight from
    `meta_goal.contender_focus_key`, instead of carrying `key is None`
    fallbacks that could never run and that `branch = false` hid from the
    coverage gate.
    """

    name = "IsThisTargetBlocked"

    def __init__(self, slot: str, target: GearTarget, walk: RootWalk) -> None:
        self.slot = slot
        self.target = target
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "ObtainItem | ReachSkillLevel":
        self.walk.trail.append(self.name)
        if self.target.blocking_skill is not None:
            # +1, not `blocking_skill_level`: the graph re-derives from live
            # state every cycle, so the increment advances on its own and
            # nothing has to plan the whole climb in one shot. Same rule as
            # `decisions/obtain_item.CanICraftCurrentTier`, and it reads the
            # character's skills the same way that site does.
            current = state.skills.get(self.target.blocking_skill, 1)
            return ReachSkillLevel(skill=self.target.blocking_skill,
                                   level=current + 1)
        if self.target.blocker is None:
            return ObtainItem(code=self.target.code, quantity=1, slot=self.slot)
        if self.target.blocker == self.target.code:
            # `classify_target`'s LAST arm: the target is its own blocker —
            # it has no recipe, or every recipe material is reachable and the
            # item still is not. There is no material to route to, so the
            # root is the item itself and the step graph owns the rest.
            return ObtainItem(code=self.target.code, quantity=1, slot=self.slot)
        recipe = game_data.crafting_recipe(self.target.code)
        if recipe is None or self.target.blocker not in recipe:
            raise ValueError(
                f"gear target {self.target.code!r} is blocked on "
                f"{self.target.blocker!r}, which is not in its recipe")
        return ObtainItem(code=self.target.blocker,
                          quantity=recipe[self.target.blocker])


class IsThereACombatTarget(Decision[MetaGoal]):
    """Is there a monster this character should be fighting right now?

    `ctx.combat_monster` is fed by `band_target.band_combat_target` — the
    band's best winnable monster, or None when nothing in the band is
    beatable.

    The level it names is the next ladder rung STRICTLY ABOVE the character's
    — see `_next_rung_above` for why that is not what spec §5.3 wrote.
    """

    name = "IsThereACombatTarget"

    def __init__(self, walk: RootWalk) -> None:
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        if ctx.combat_monster is not None:
            return ReachCharLevel(level=_next_rung_above(game_data, state.level))
        return CanIClearMyTier(self.walk)


class CanIClearMyTier(Decision[MetaGoal]):
    """The end of the ladder, or an honest wall.

    Reached only when the gear sheet wants nothing AND no monster in the band
    is winnable. If every rung is cleared, the ladder is finished and the
    trunk milestone is the root. Otherwise there is a rung left, nothing to
    gear for, and nothing to fight: that is a WALL, and it is reported as
    `None` rather than dressed up as a root the character cannot make progress
    on. `MAX_RESOLVE_DEPTH` never sees it — `None` terminates the walk.

    THE ORPHAN SKILL ROOTS DO NOT GO HERE, and that was MEASURED rather than
    assumed. A sixth node on this arm — "before you call it a wall, is there a
    skill nothing can name?" — reads well and is wrong: `chosen_root is None`
    is what `strategy_driver._build_candidates` keys `step_is_real` on, and a
    non-None root there demotes the raid candidates below the objective step.
    Measured on the scenario set, that turned `l48_raid_active` from
    `ParticipateRaid(enchanted_fairy)` into a cooking grind — a time-limited
    event traded for a skill climb — and dissolved the wall three suites pin as
    a designed verdict (`scenarios/test_band_liveness.py`,
    `scenarios/test_no_deadlock.py`). The wall is a real answer, and a skill
    with an open rung is an ALTERNATIVE to it, not a replacement for it: see
    `resolve_root`, which offers the same roots one rank below the trunk.
    """

    name = "CanIClearMyTier"

    def __init__(self, walk: RootWalk) -> None:
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        if next_uncleared_tier(state, game_data, history) is None:
            return ReachCharLevel(level=milestone_pure(state.level))
        return None


def resolve_root(state: WorldState, game_data: GameData,
                 objective: CharacterObjective, ctx: SelectionContext,
                 history: LearningStore | None) -> RootResolution:
    """Walk the tier graph from `IsAFightBlockingMe` to a root MetaGoal."""
    walk = RootWalk()
    # Locally annotated, not inlined into the call: mypy 1.18.1 infers
    # `Leaf = Never` for a bare `Decision[X]` argument to `resolve_node` and
    # reports arg-type. Same fix as the `strategy_driver.py` call site.
    entry: Decision[MetaGoal] | MetaGoal | None = IsAFightBlockingMe(
        objective, walk)
    root = resolve_node(entry, state, game_data, ctx, history)

    ordered: list[MetaGoal] = [
        # A throwaway RootWalk: this is a conversion, not a visit, so it must
        # not append to the trail.
        IsThisTargetBlocked(slot, target, RootWalk()).resolve(
            state, game_data, ctx, history)
        for slot, target in walk.sibling_targets
    ]
    ordered.append(ReachCharLevel(level=milestone_pure(state.level)))
    # THE RESTORED SEAM: the orphan skill roots, after the gear siblings and
    # after the trunk. Produced here, beside the trunk, and for the same reason
    # the trunk is produced here — neither is a question the tier walk asks,
    # both are roots the resolution OFFERS for when the walk's own answer
    # cannot be served. Nothing is ranked against anything: three groups
    # concatenated in a fixed order, and `_orphan_skill_roots` orders its own
    # group on one integer.
    #
    # BEHIND THE TRUNK, AND THAT POSITION WAS MEASURED. Ahead of it reads
    # better — the trunk is documented as the fallback of fallbacks — but the
    # trunk's step goal is NOT only `GrindCharacterXP`: `objective_step_goal`'s
    # `ReachCharLevel` arm runs `_marginal_provision_goal` first, so the trunk
    # slot is also how the objective's own provisioning gets planned. Placed
    # ahead of it, a cooking climb displaced `GatherMaterials(mithril_bar)` at
    # `l48_band_adequate` — the mithril gear that BREAKS the L38-48 wall,
    # pinned by three suites — and an orphan skill climb unblocks nothing.
    # Behind it, an orphan root is reached exactly when no gear step and no
    # trunk step can be served, which is where the bot used to emit `Wait`.
    ordered.extend(_orphan_skill_roots(state, game_data))

    alternatives: list[MetaGoal] = []
    for alt in ordered:
        if alt != root and alt not in alternatives:
            alternatives.append(alt)
    return RootResolution(root=root, alternatives=tuple(alternatives),
                          trail=tuple(walk.trail), aged=walk.aged)
