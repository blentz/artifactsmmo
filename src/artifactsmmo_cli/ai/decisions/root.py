"""The ROOT graph: named `Decision[MetaGoal]`s that answer "which root".

Wave 3 replaces the flat scored ranking over candidate roots
(`progression_tree.decide_tree`'s argmax) with a resolution walk over named
nodes, exactly as wave 2 replaced `objective_step_goal`'s if-pile with
`decisions/obtain_item.py`. The ranking answered "which root scores highest" —
two unrelated scales sharing one column (live 2026-08-08: gear showed 2.6e8
against the trunk's 1.0). This graph answers "which root does the tier ladder
select", and its `trail` is a named path a reader can follow instead of a
number they could not.

NOTHING CALLS THIS YET. `decide_tree` is flipped over to `resolve_root` in a
later task of `PLAN_wave3a_cutover`; until then this module is groundwork and
changes no runtime behaviour.

One module, five behavioural classes: the same shape as
`decisions/obtain_item.py`, whose six `Decision` subclasses share a file
because they are ONE graph — each class is a branch of it, they are only ever
constructed by one another, and splitting them across five files would put
mutually-referencing halves of a single control-flow structure behind five
imports without making any of them independently usable.

Spec: `docs/superpowers/specs/2026-08-23-wave3-resolution-design.md` §5.1,
§5.3. Two places this module deliberately departs from that spec, both
recorded in `.superpowers/sdd/PLAN_wave3a_cutover/task-4-report.md`:

* §5.3's prose says "Six nodes" and then draws five. Five are implemented;
  no sixth node is invented to make the count true.
* §5.3's `IsThereACombatTarget` "yes" arm names
  `ReachCharLevel(tier_of_level(game_data, state.level))`, which is a root the
  character has ALREADY satisfied (`tier_of_level` returns the highest rung at
  or below `state.level`). Task 4 transcribed it because its contract was
  "change no behaviour"; THE FLIP (task 6) is the task that decides, and it
  decided against the spec — see `_next_rung_above`.
"""

from dataclasses import dataclass, field
from fractions import Fraction

from artifactsmmo_cli.ai.decision import Decision, resolve_node
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, GearTarget
from artifactsmmo_cli.ai.tiers.progression_tree_core import (
    FOCUS_FLAT,
    dhondt_step,
    falloff,
    milestone_pure,
)
from artifactsmmo_cli.ai.tiers.tier_ladder import ladder, tier_of_level
from artifactsmmo_cli.ai.tiers.tier_progress import next_uncleared_tier
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState


@dataclass(frozen=True)
class RootResolution:
    """The walk's answer: the root to pursue, ordered alternatives, and the
    trail that produced it.

    `alternatives` is NOT a ranking. It is the ordered remainder of the ONE
    list-valued node in the graph (`WhichSlotIsFurthestBehind`), plus the trunk
    last. It exists because `objective_step_goal` can still return None for a
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

    Two arms, mirroring `focus_aging_pick`'s own shape:

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
        head = self._aged_head(ranked, state, game_data, ctx)
        self.walk.sibling_targets = [item for item in ranked if item is not head]
        slot, target = head
        return IsThisTargetBlocked(slot, target, self.walk)

    def _aged_head(self, ranked: list[tuple[str, GearTarget]], state: WorldState,
                   game_data: GameData, ctx: SelectionContext
                   ) -> tuple[str, GearTarget]:
        """`ranked[0]`, or the interleave's pick once anything has aged."""
        if all(ctx.gear_focus.get((slot, target.code), 0) <= FOCUS_FLAT
               for slot, target in ranked):
            return ranked[0]
        # `max(1, gap)`: a slot can only be a target because something wants
        # replacing, but an equal-rung swap scores 0 and a zero weight is one
        # `dhondt_step` can never elect — which would be starvation reinstated
        # by the very mechanism that exists to prevent it.
        weighted = [(slot, Fraction(max(1, _tier_gap(slot, target, state, game_data)))
                     * falloff(ctx.gear_focus.get((slot, target.code), 0)))
                    for slot, target in ranked]
        winner = dhondt_step(weighted, ctx.interleave_seats)
        assert winner is not None  # `ranked` is non-empty; see the docstring
        self.walk.aged = True
        return next(item for item in ranked if item[0] == winner)


class IsThisTargetBlocked(Decision[MetaGoal]):
    """What actually stands in front of this slot's target.

    `GearTarget` carries the blocker as TYPED fields, and its one producer
    (`objective._classify_target`, objective.py:447-457) emits exactly FOUR
    shapes, read here with no guessing and no string parsing:

        blocking_skill=S, blocking_skill_level=L, blocker=None -> skill-gated
        blocker=None,     blocking_skill=None                  -> attainable
        blocker=<code> == self.code                            -> its OWN blocker
        blocker=<code> != self.code                            -> material-gated

    Spec §5.3's table names only the first three; the fourth is the last arm
    of `_classify_target` and is handled below.

    The skill test runs FIRST because a skill-gated target also has
    `blocker=None`; testing `blocker is None` first would report it as
    attainable. That is the same masking defect `_classify_target`'s own
    docstring warns against, one layer up.

    `resolve` narrows its return type to `MetaGoal`: every arm returns a leaf,
    this node has no `Decision` child and no None arm, and the narrowing is
    what lets `resolve_root` reuse it to convert a sibling target without
    inventing an unreachable None branch to satisfy the type checker.
    """

    name = "IsThisTargetBlocked"

    def __init__(self, slot: str, target: GearTarget, walk: RootWalk) -> None:
        self.slot = slot
        self.target = target
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> MetaGoal:
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
            # `_classify_target`'s LAST arm: the target is its own blocker —
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
    """Walk the tier graph from `IsMyGearBehindMyTier` to a root MetaGoal."""
    walk = RootWalk()
    # Locally annotated, not inlined into the call: mypy 1.18.1 infers
    # `Leaf = Never` for a bare `Decision[X]` argument to `resolve_node` and
    # reports arg-type. Same fix as the `strategy_driver.py` call site.
    entry: Decision[MetaGoal] | MetaGoal | None = IsMyGearBehindMyTier(
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

    alternatives: list[MetaGoal] = []
    for alt in ordered:
        if alt != root and alt not in alternatives:
            alternatives.append(alt)
    return RootResolution(root=root, alternatives=tuple(alternatives),
                          trail=tuple(walk.trail), aged=walk.aged)
