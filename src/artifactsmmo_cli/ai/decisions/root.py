"""The ROOT graph: named `Decision[MetaGoal]`s that answer "which root".

`resolve_root` walks from `WhichPieceIsNext` (spec 2026-10-18 §2.4): the next
missing piece of the cycle's gear objective `L*` (`ctx.gear_objective`), or
one more character level once `L*` is held, or None when the cycle has no gear
objective (the wall). `IsThisTargetBlocked` converts a piece's target into the
root its blocker asks for. `trail` names the nodes the walk visited, the plan
pane's "why".

The resolution then OFFERS, never ranked against each other, the rest of the
missing pieces, a crafter's fleet pieces, the trunk, the held task
(`_task_root`), the fleet work (`_fleet_roots`) and the orphan skill roots
(`_orphan_skill_roots`), in that fixed order.

THE STANDALONE SKILL ROOT IS A RESTORED CAPABILITY, NOT A NEW FEATURE.
`ef67c1d6` ("refactor(flip)!: delete the flat scalar ranking") deleted four
standalone `ReachSkillLevel` root emitters at once on the premise "skills are
pure prerequisites now". That premise is false for any skill whose output
nothing equips: live, on `~/.cache/artifactsmmo/learning.db`, 33,840 cooking
XP earned, 99.6% of it as a side effect of `Craft(cooked_*)` legs inside
`RestoreHP` plans — an entire skill levelled by accident.

`_orphan_skill_roots` restores the seam, as a rule about DAG DEMAND rather
than about cooking (USER 2026-10-08: "Only when demanded" — a skill climbs when
the goal-action DAG asks for it), and `resolve_root` offers its roots one rank
BELOW the trunk. It adds no node and no argmax: a root that has to be CHOSEN
against gear is a ranking.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime

# MODULE import, same idiom as `_skill_grindable` and `_route` below, and for the
# same reason but the OTHER direction: `gather_demand` imports
# `progression.meta_goal` and `progression.skill_grind_target`, both of which run
# `ai/progression/__init__` -> `strategy` -> `progression_tree` -> THIS module. So an
# entry that imports `gather_demand` FIRST (e.g. `import
# artifactsmmo_cli.ai.gather_demand` on its own) reaches this line while
# `gather_demand` is only half built, and a NAME import of `gather_demand`/
# `craft_demand` raises ImportError. Binding the module object defers both
# attribute lookups to CALL time, by which point it is complete.
from artifactsmmo_cli.ai import craft_demand as _craft_demand
from artifactsmmo_cli.ai import food_producer as _food_producer
from artifactsmmo_cli.ai import gather_demand as _gather_demand

# `skill_grindable` is imported as a MODULE, not as `from ... import
# skill_is_grindable`, and that is load-bearing rather than stylistic. It
# imports `ai.progression.skill_grind_target`, which runs `ai/progression/__init__.py` ->
# `strategy` -> `progression_tree` -> THIS module: so whenever it is the first
# of the two to be imported, root.py executes while it is only half built and a
# NAME import raises ImportError. Binding the module object defers the
# attribute lookup to CALL time, by which point both halves are complete.
# Exactly the idiom `progression/strategy.py:13` and `progression/progression_tree.py:37`
# already use on each other, for this reason. (It used to be `level_skill`,
# whose `LevelSkill.is_applicable` wrapped this same predicate.)
from artifactsmmo_cli.ai import skill_grindable as _skill_grindable
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.decision import Decision, resolve_node

# MODULE import, same idiom as `_skill_grindable` above and for the same reason:
# `route` imports `progression.meta_goal`, which runs `progression/__init__` ->
# `strategy` -> `progression_tree` -> THIS module, so whichever of the two
# is reached first executes while the other is half built. A NAME import
# of `route_price` raises ImportError when `decisions.route` is the entry.
from artifactsmmo_cli.ai.decisions import route as _route

# MODULE import, same idiom and reason: `which_piece_is_next` reads this
# module's `RootWalk` / `IsThisTargetBlocked`, and this module builds its entry.
from artifactsmmo_cli.ai.decisions import which_piece_is_next as _which_piece
from artifactsmmo_cli.ai.fleet_work import (
    FLEET_SUPPLY,
    FLEET_TURN_IN,
    fleet_work_code,
    supply_due,
    turn_in_due,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import gear_objective_for, task_rate
from artifactsmmo_cli.ai.heal_catalog import FOOD
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_accept import accept_due
from artifactsmmo_cli.ai.task_coins import tasks_coin_total
from artifactsmmo_cli.ai.task_horizon import HORIZON_GEAR, resolve_task_horizon
from artifactsmmo_cli.ai.task_worth import task_worth_for
from artifactsmmo_cli.ai.progression.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachFleetOutcome,
    ReachSkillLevel,
    ReachTaskOutcome,
    StepDecline,
    no_decline,
)
from artifactsmmo_cli.ai.progression.objective import (
    CharacterObjective,
    GearTarget,
)
from artifactsmmo_cli.ai.tool_objective import tool_first
from artifactsmmo_cli.ai.world_state import SKILL_NAMES, WorldState


@dataclass(frozen=True)
class RootResolution:
    """The walk's answer: the root to pursue, ordered alternatives, and the
    trail that produced it.

    `alternatives` is NOT a ranking. It is the missing `L*` pieces in their
    own order, the fleet pieces, the trunk, then the task, fleet and orphan
    skill roots (`resolve_root`) — ordered groups, none of them scored against
    each other. It exists because
    `objective_step_goal` can still return None for a
    resolved root (`ReachCharLevel` with no combat target, a paying held
    items task) and the arbiter walks it when the chosen step does not
    plan. Deleting it regresses three named live traces — see
    `strategy_driver._resolve_step_goal` and `progression_tree`'s
    fallback-order comment.

    `trail` is the ordered `Decision.name`s the walk visited. It replaces the
    ranking as the plan pane's "why": a named path is a better answer to "why
    this root" than a number was.
    """

    root: MetaGoal | None
    alternatives: tuple[MetaGoal, ...]
    trail: tuple[str, ...]
    blocked_target: str | None = None
    """The gear code a crafting-skill gate turned into this walk's
    `ReachSkillLevel` — see `RootWalk.blocked_target`. `decide_tree` copies it
    onto `StrategyDecision.blocked_target`, which the trace's `root_group`
    reads to tell a skill gate from an orphan climb."""

    declined: tuple[tuple[str, str], ...] = ()
    """`(root repr, reason)` for every gear target the walk passed over because
    its step cannot be served this cycle — see `RootWalk.declined`. The named
    blocker the plan pane shows instead of a bare demotion."""


@dataclass
class RootWalk:
    """The one mutable side-channel the walk needs, threaded through the nodes.

    What `resolve_node` cannot hand back on its own:

    * `trail` — `resolve_node` keeps its visited list (`seen`) private and
      only surfaces it in the `RecursionError` message. Rather than widen a
      signature three other call sites already depend on, each node appends
      its own `name` as it resolves; the result is byte-identical to `seen`
      because `resolve_node` calls each visited node's `resolve` exactly once.

    A node that is resolved OUTSIDE the main walk (`resolve_root` re-runs
    `IsThisTargetBlocked` once per missing piece to turn it into a `MetaGoal`) is
    handed a throwaway `RootWalk`, so those visits never pollute the trail.

    * `blocked_target` — the gear code whose CRAFTING-SKILL GATE turned this
      walk into a `ReachSkillLevel`. The walk's answer is then a skill climb
      and the target itself is dropped, which is exactly the item a sibling
      could have made: measured on the live fleet, `SupplyBank` has run 0 times
      in 105,159 cycles because a blocked character publishes NO demand at all.
      Deposited by the ONE node that reads the gate — a re-derivation in the
      player would be a second classifier, and `classify_target`'s own
      docstring records what masking costs.

    * `step_decline` / `declined` — the walk asks each gear target's step
      whether it can be served (`StepDecline`) and lets only a served one head
      the resolution (Phase 3-2: goal choice reads the walk's answer, which
      replaced promoting past an unservable pick after the fact). A declined
      target is recorded with its reason and stays an alternative, so it is
      visible and re-asked every cycle: it heads the walk again exactly when
      its blocker clears.
    """

    trail: list[str] = field(default_factory=list)
    blocked_target: str | None = None
    step_decline: StepDecline = no_decline
    declined: dict[str, str] = field(default_factory=dict)
    # The walk's one clock (the obtain model's event gates read it): the
    # caller's, else read once when the walk is made.
    now: datetime = field(default_factory=lambda: datetime.now(UTC))

    def serves(self, slot: str, target: GearTarget, state: WorldState,
               game_data: GameData, ctx: SelectionContext,
               history: LearningStore | None) -> bool:
        """Can this target's step be served this cycle? Records the reason when
        it cannot. The root is converted on a throwaway walk, as everywhere a
        target is converted outside the main visit."""
        root = IsThisTargetBlocked(
            slot, target, RootWalk(step_decline=self.step_decline, now=self.now)).resolve(
            state, game_data, ctx, history)
        reason = self.step_decline(root)
        if reason is None:
            return True
        self.declined[repr(root)] = reason
        return False


def _is_food(code: str, game_data: GameData) -> bool:
    """Whether `code` is a FOOD (`heal_catalog.FOOD`) in the catalogue."""
    stats = game_data.item_stats(code)
    return stats is not None and stats.type_ == FOOD


def _orphan_skill_roots(state: WorldState, game_data: GameData,
                        offered: Sequence[MetaGoal],
                        ctx: SelectionContext) -> tuple[ReachSkillLevel, ...]:
    """THE RULE, and the whole of it:

        a skill gets a standalone climb exactly when the goal-action DAG
        DEMANDS it above its current level, and it has an open, XP-positive
        rung.

    USER 2026-10-08, "Only when demanded": "a skill climbs only when the
    goal-action DAG demands it (gear, the consumable floor's tier food, a
    task). Cooking rises when a better tier food is due, not before." The
    character-XP / skill-XP seesaw is EMERGENT from the DAG's demand
    (`feedback_seesaw_is_emergent`), so no skill is admitted for being behind.

    THE DEMAND is read off the roots on offer plus the fleet consumable
    shortfall (`ctx.supply_shortfall`, the floor's tier food). A FOOD row is
    read only when this character makes that food
    (`food_producer.may_make_food`, spec 2026-10-13 §4): a sibling of a live
    fisher fetches or rests, so its share of the shortfall demands no fishing
    or cooking climb. Potion rows are read for everyone (spec non-goal).
    `xp_demand.demand_roots` does NOT read the shortfall. Two passes:

    * CRAFT demand (`craft_demand`): every crafting skill some root's
      requirement closure names above the character's level — the gear
      targets, the task, the tier food.
    * GATHER demand (`gather_demand`) over the same roots PLUS a provisional
      climb for each craft-demanded skill. The second pass is how a demanded
      cooking climb asks for the fish its own rungs consume: a
      `ReachSkillLevel` names no item, so `gather_demand._seed` stands its
      grind target in for it. A gathering skill never seeds itself
      (`_seed`'s guard), so nothing admits itself.

    The level offered is the level ASKED FOR, never a one-rung `C+1` nudge
    with no destination. A skill a root on offer already climbs (the
    walk's skill-gated target, a supply-link climb) is left to that root.

    WHAT THIS REPLACED. The old gate admitted every skill no gear target could
    name (cooking and alchemy unconditionally) and a gear-nameable skill when
    nothing demanded it. Live 2026-10-08 the orphan `ReachSkillLevel(cooking,
    32)` pulled `fishing 30` in through its grind target and four characters
    spent ~100 cycles each on `Gather(trout_spot)` with nothing asking for a
    fish. An empty group is now legitimate: the trunk is always on offer
    ahead of it.

    "an open, XP-positive rung" is `skill_is_grindable(S, C+1)` — the SAME
    predicate `ReachSkillGoal`'s only action offers (the O1 census,
    `audit/skill_climb_completeness`, verdicts its cells on it too: deleted by
    ruling X, restored by ruling AK of the global gear objective), so no
    unplannable root is emitted.

    ORDER: ONE INTEGER, `state.level - skill level` — how far the skill trails
    the character, largest first — with ties broken by `SKILL_NAMES`, the
    schema vocabulary `world_state` derives from the API's own enums (never
    `sorted()` as a decision key; see `feedback_no_alphabetical_tiebreak`).
    DO NOT ADD A SECOND TERM: if the order is wrong, change WHICH integer it
    is, not how many.
    """
    shortfall = [ObtainItem(code, qty) for code, qty in ctx.supply_shortfall
                 if not _is_food(code, game_data)
                 or _food_producer.may_make_food(code, ctx.role, ctx.fleet_roles, game_data)]
    roots = [*offered, *shortfall]
    demand = _craft_demand.craft_demand(roots, state, game_data, ctx)
    climbs = [ReachSkillLevel(skill=skill, level=level) for skill, level in demand.items()]
    for skill, level in _gather_demand.gather_demand(
            [*roots, *climbs], state, game_data, ctx).items():
        demand[skill] = max(level, demand.get(skill, 0))
    # A skill some root on offer already climbs is owned by that root: a second
    # climb of it at another level would be churn, not a route.
    climbing = {root.skill for root in offered if isinstance(root, ReachSkillLevel)}
    orphans = [
        skill for skill in SKILL_NAMES
        if skill in demand and skill not in climbing
        and _skill_grindable.skill_is_grindable(
            skill, state.skills.get(skill, 1) + 1, state, game_data)]
    orphans.sort(key=lambda skill: (state.skills.get(skill, 1) - state.level,
                                    SKILL_NAMES.index(skill)))
    return tuple(ReachSkillLevel(skill=skill, level=demand[skill]) for skill in orphans)


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
    `Decision` child and no None arm. The narrowing is load-bearing: it lets
    `resolve_root` (and `RootWalk.serves`) reuse this node to convert a
    target without inventing an unreachable None branch.
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
            # THE ASK, recorded before the target is dropped. A sibling that
            # already holds this skill can make this item; nothing else in the
            # walk carries the code past here, and the demand board is what
            # turns it into a request. Sibling conversions get a THROWAWAY
            # `RootWalk` (see `resolve_root`), so this records the CHOSEN
            # target only.
            self.walk.blocked_target = self.target.code
            # +1, not `blocking_skill_level`: the graph re-derives from live
            # state every cycle, so the increment advances on its own and
            # nothing has to plan the whole climb in one shot. Same rule as
            # `decisions/obtain_item.CanICraftCurrentTier`, and it reads the
            # character's skills the same way that site does.
            current = state.skills.get(self.target.blocking_skill, 1)
            return tool_first(
                ReachSkillLevel(skill=self.target.blocking_skill, level=current + 1),
                ctx, self.walk.step_decline)
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


def _task_root(state: WorldState, game_data: GameData, ctx: SelectionContext,
               history: LearningStore | None) -> MetaGoal | None:
    """The held monsters task as a root alternative, or None.

    USER 2026-10-05: a held task that pays no progression XP is ROTATED IN, not
    left inert. Live, three tasks had been held 15 days with no task fight (R2D2
    `ogre` 0/327, Lor `spider` 0/206, C3P0 `pig` 5/104): the task was no root,
    so it had no turn, and its grey monster was no fight.

    * winnable (projected to max hp, with the learned-loss veto — the same
      verdict `GamePlayer._is_winnable` gives the cascade): the task itself,
      `ReachTaskOutcome`, whose step is one more kill;
    * NOT winnable — USER ruling: the task ASKS FOR GEAR. The root is the
      first missing piece of `L*` of the task monster
      (`gear_objective_for`), in its slot, on the horizon's `HORIZON_GEAR`
      verdict (`resolve_task_horizon`, plan C Task 2), read here so the root
      and the task's worth are one reading. Only this arm prices the pieces;
    * no gear closes the gap (any other verdict): None. The task waits, inert,
      for a coin to cancel it (S-052).

    * a WORTHLESS task (no XP, no GOLD, no DROPS reason — `task_worth_core`)
      with a pocket coin to cancel it: the task itself, whose step is the
      cancel (c-2 #5, USER 2026-10-07: this was the TASK_CANCEL rung and, before
      it, the LOW_YIELD_CANCEL rung). Without a coin a worthless MONSTERS task
      is worked to clear it; a worthless ITEMS task stays HELD, not worked
      (spec 2026-10-14 items-task-pays §4, USER approach 1: the rotation would
      otherwise give it half the turns, as HAL's 5.5 h at 0 character XP did);

    * a held, unmet items task that pays (an XP, GOLD or DROPS verdict): the
      task itself, worked (c-2 #4 was the PURSUE_TASK rung; #5 drops its PIVOT
      gate — a task is cancelled by its worth or worked).

    * a held, MET task: the task itself, whose step is the turn-in (c-2 #6:
      this was the COMPLETE_TASK collect rung). Turned in on the task
      objective's turn, as a draw is taken."""
    if state.task_code and 0 < state.task_total <= state.task_progress:
        return ReachTaskOutcome(state.task_code)
    if state.task_code and _route.task_cancel_due(state, game_data, ctx, history):
        return ReachTaskOutcome(state.task_code)
    if not state.task_code and accept_due(state, ctx):
        # c-2 #3 (was the ACCEPT_TASK collect rung): an owed draw is taken on
        # the task objective's turn (USER: no task is drawn until then).
        return ReachTaskOutcome(None)
    if tasks_coin_total(state) >= ctx.task_exchange_min_coins:
        # c-2 #2 (was the TASK_EXCHANGE rung): earned coins are the task
        # objective's to exchange, task held or not.
        return ReachTaskOutcome(state.task_code or None)
    if (state.task_type == "items" and state.task_code
            and state.task_progress < state.task_total):
        # c-2 #4/#5: a held items task not cancelled for its worth is worked on
        # the task objective's turn -- unless it is worthless and no coin
        # cancels it (the cancel arm above came first): then it stays HELD
        # (spec 2026-10-14 items-task-pays §4), so the rotation never works it.
        worth = task_worth_for(state.task_code, state.task_type,
                               state.task_total - state.task_progress,
                               state, game_data, ctx, history)
        return ReachTaskOutcome(state.task_code) if worth.any() else None
    if (state.task_type != "monsters" or not state.task_code
            or state.task_progress >= state.task_total):
        return None
    if is_winnable(replace(state, hp=state.max_hp), game_data, state.task_code, history):
        return ReachTaskOutcome(state.task_code)
    horizon = resolve_task_horizon(state, game_data, ctx, history)
    if horizon is None or horizon.verdict != HORIZON_GEAR:
        return None
    # GEAR is `gear_closes_for`: a missing piece by the same `_missing` and
    # `_gain` over the same inputs, so the first piece exists.
    first = gear_objective_for(state.task_code, state, game_data, ctx, history,
                               task_rate).missing[0]
    return ObtainItem(first.code, 1, slot=first.slot)


def _fleet_roots(ctx: SelectionContext) -> list[ReachFleetOutcome]:
    """The fleet work the context names, in a fixed order: the turn-in (a
    resolved election waits on this character) before the supply run."""
    roots: list[ReachFleetOutcome] = []
    for kind, due in ((FLEET_TURN_IN, turn_in_due), (FLEET_SUPPLY, supply_due)):
        if due(ctx):
            roots.append(ReachFleetOutcome(kind, fleet_work_code(kind, ctx)))
    return roots


def resolve_root(state: WorldState, game_data: GameData,
                 objective: CharacterObjective, ctx: SelectionContext,
                 history: LearningStore | None,
                 step_decline: StepDecline = no_decline,
                 now: datetime | None = None) -> RootResolution:
    """Walk the root graph from `WhichPieceIsNext` to a root MetaGoal (spec
    2026-10-18 §2.4): the next missing `L*` piece, or one more character level
    once `L*` is held, or None when the cycle has no gear objective (the wall).

    `step_decline` is the cycle's answer for a root's step (`StepDecline`); a
    piece whose step it declines cannot head the walk, and its reason is in
    `RootResolution.declined`.

    The alternatives, in a fixed order and never ranked against each other:
    every missing piece in `missing`'s own order, then a crafter's fleet
    pieces' steps (§2.5, `ctx.fleet_pieces`), the trunk ONLY when `L*` is held and
    no fleet piece waits (no fight is chosen for XP while a piece is missing,
    §6.2, nor while fleet demand the crafter's role serves exists), then the
    task, fleet and orphan-skill roots."""
    walk = RootWalk(step_decline=step_decline) if now is None else RootWalk(
        step_decline=step_decline, now=now)
    # Locally annotated, not inlined into the call: mypy 1.18.1 infers
    # `Leaf = Never` for a bare `Decision[X]` argument to `resolve_node` and
    # reports arg-type. Same fix as the `strategy_driver.py` call site.
    entry: Decision[MetaGoal] | MetaGoal | None = _which_piece.WhichPieceIsNext(
        objective, walk)
    root = resolve_node(entry, state, game_data, ctx, history)

    target = ctx.gear_objective
    ordered: list[MetaGoal] = [
        # A throwaway RootWalk: this is a conversion, not a visit, so it must
        # not append to the trail.
        _which_piece.piece_step(piece.slot, _which_piece.piece_target(piece, objective, state),
                                RootWalk(step_decline=step_decline, now=walk.now),
                                state, game_data, ctx, history)
        for piece in (target.missing if target is not None else ())
        # A piece a sibling crafts for this character has no step until it is
        # banked (§2.5, `GearPiece.awaits_delivery`): offering its `ObtainItem`
        # would hand the rotation the very climb the sibling route spares.
        if not piece.awaits_delivery(state)
    ]
    fleet = ctx.fleet_pieces if target is not None else ()
    ordered.extend(_which_piece.fleet_piece_root(piece, state, game_data, ctx, walk, history)
                   for piece in fleet)
    trunk = _which_piece.next_level(state, game_data)
    if target is not None and target.held and not fleet and trunk is not None:
        ordered.append(trunk)
    # THE RESTORED SEAM: the orphan skill roots, after the gear siblings and
    # after the trunk. Produced here, beside the trunk, and for the same reason
    # the trunk is produced here — neither is a question the piece walk asks,
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
    # `root` can be `None` (the wall case: no gear objective, `WhichPieceIsNext`),
    # which `Sequence[MetaGoal]` cannot type — filtered rather than left in,
    # since `gather_demand._seed` would skip it anyway (neither an `ObtainItem`
    # nor a `ReachSkillLevel`).
    # THE TASK OBJECTIVE (Phase 5-2c-iii-c), after the trunk and before the
    # orphan skill roots: the held monsters task as a root of its own, so the
    # turn order gives it turns. Its position matters little under `rotate` —
    # every plannable alternative gets a turn — but behind the trunk it does not
    # displace the objective's own provisioning, for the reason given above.
    task = _task_root(state, game_data, ctx, history)
    if task is not None:
        ordered.append(task)
    # THE FLEET OBJECTIVE (Phase 5-2c-iv), beside the task objective: work the
    # coordination tables name for this character, offered only while they do,
    # served on its rotation turn (was the SUPPLY_BANK / CURRENCY_TURNIN
    # collect rungs, above every root).
    ordered.extend(_fleet_roots(ctx))
    offered = [g for g in (root, *ordered) if g is not None]
    ordered.extend(_orphan_skill_roots(state, game_data, offered, ctx))

    alternatives: list[MetaGoal] = []
    for alt in ordered:
        if alt != root and alt not in alternatives:
            alternatives.append(alt)
    return RootResolution(root=root, alternatives=tuple(alternatives),
                          trail=tuple(walk.trail),
                          blocked_target=walk.blocked_target,
                          declined=tuple(walk.declined.items()))
