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

`_orphan_skill_roots` restores the seam, as a rule about DAG DEMAND rather
than about cooking (USER 2026-10-08: "Only when demanded" — a skill climbs when
the goal-action DAG asks for it), and `resolve_root` offers its roots one rank BELOW the
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

from collections.abc import Sequence
from dataclasses import dataclass, field, replace

# MODULE import, same idiom as `_skill_grindable` and `_route` below, and for the
# same reason but the OTHER direction: `gather_demand` imports
# `tiers.meta_goal` and `tiers.skill_grind_target`, both of which run
# `ai/tiers/__init__` -> `strategy` -> `progression_tree` -> THIS module. So an
# entry that imports `gather_demand` FIRST (e.g. `import
# artifactsmmo_cli.ai.gather_demand` on its own) reaches this line while
# `gather_demand` is only half built, and a NAME import of `gather_demand`/
# `craft_demand` raises ImportError. Binding the module object defers both
# attribute lookups to CALL time, by which point it is complete.
from artifactsmmo_cli.ai import craft_demand as _craft_demand
from artifactsmmo_cli.ai import gather_demand as _gather_demand

# `skill_grindable` is imported as a MODULE, not as `from ... import
# skill_is_grindable`, and that is load-bearing rather than stylistic. It
# imports `ai.tiers.skill_grind_target`, which runs `ai/tiers/__init__.py` ->
# `strategy` -> `progression_tree` -> THIS module: so whenever it is the first
# of the two to be imported, root.py executes while it is only half built and a
# NAME import raises ImportError. Binding the module object defers the
# attribute lookup to CALL time, by which point both halves are complete.
# Exactly the idiom `tiers/strategy.py:13` and `tiers/progression_tree.py:37`
# already use on each other, for this reason. (It used to be `level_skill`,
# whose `LevelSkill.is_applicable` wrapped this same predicate.)
from artifactsmmo_cli.ai import skill_grindable as _skill_grindable
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.combat_deficit import deficit_upgrade_target
from artifactsmmo_cli.ai.decision import Decision, resolve_node

# MODULE import, same idiom as `_skill_grindable` above and for the same reason:
# `route` imports `tiers.meta_goal`, which runs `tiers/__init__` ->
# `strategy` -> `progression_tree` -> THIS module, so whichever of the two
# is reached first executes while the other is half built. A NAME import
# of `route_price` raises ImportError when `decisions.route` is the entry.
from artifactsmmo_cli.ai.decisions import route as _route
from artifactsmmo_cli.ai.drop_evidence import drop_evidence
from artifactsmmo_cli.ai.fleet_work import (
    FLEET_SUPPLY,
    FLEET_TURN_IN,
    fleet_work_code,
    supply_due,
    turn_in_due,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_accept import accept_due
from artifactsmmo_cli.ai.task_coins import tasks_coin_total
from artifactsmmo_cli.ai.task_horizon import HORIZON_GEAR, resolve_task_horizon
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachFleetOutcome,
    ReachSkillLevel,
    ReachTaskOutcome,
    StepDecline,
    no_decline,
)
from artifactsmmo_cli.ai.tiers.objective import (
    CharacterObjective,
    GearTarget,
)
from artifactsmmo_cli.ai.tiers.progression_tree_core import milestone_pure
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
    items-task defer) and the arbiter walks it when the chosen step does not
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
    onto `StrategyDecision.blocked_target`, and the player publishes it as
    demand so a sibling holding the skill can make it."""

    declined: tuple[tuple[str, str], ...] = ()
    """`(root repr, reason)` for every gear target the walk passed over because
    its step cannot be served this cycle — see `RootWalk.declined`. The named
    blocker the plan pane shows instead of a bare demotion."""


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
      target is recorded with its reason and stays an alternative, after the
      served ones (`declined_targets`), so it is visible and re-asked every
      cycle: it heads the walk again exactly when its blocker clears.
    """

    trail: list[str] = field(default_factory=list)
    sibling_targets: list[tuple[str, GearTarget]] = field(default_factory=list)
    blocked_target: str | None = None
    step_decline: StepDecline = no_decline
    declined: dict[str, str] = field(default_factory=dict)
    declined_targets: list[tuple[str, GearTarget]] = field(default_factory=list)

    def serves(self, slot: str, target: GearTarget, state: WorldState,
               game_data: GameData, ctx: SelectionContext,
               history: LearningStore | None) -> bool:
        """Can this target's step be served this cycle? Records the reason when
        it cannot. The root is converted on a throwaway walk, as everywhere a
        target is converted outside the main visit."""
        root = IsThisTargetBlocked(slot, target, RootWalk()).resolve(
            state, game_data, ctx, history)
        reason = self.step_decline(root)
        if reason is None:
            return True
        self.declined[repr(root)] = reason
        return False


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


def _is_dead_target(target: GearTarget, state: WorldState,
                    game_data: GameData) -> bool:
    """Is this target's blocker a wall NOTHING IN THE CATALOGUE OPENS?

    Exactly the drop-wall census's `WALL_DROPPER_OUT_OF_REACH` arm, whose own
    docstring calls it "An honest terminal wall, and the arm a future pricing
    change must decline rather than charge". Three conjuncts, and the middle one
    is the whole reason this is not just "the blocker is unreachable":

      * MATERIAL-GATED. `blocker is None` is an attainable target and
        `blocker == code` is a leaf with no recipe (`GearTarget`'s docstring
        names both shapes). Neither is a claim about a monster.
      * IT HAS LIVE DROPPERS. `on_live_tiles` non-empty. Live 2026-09-12, HAL:
        `hard_leather_helmet` is blocked on `astralyte_crystal`, which NO
        monster drops at all — a SPAWN wall, a resource node the character has
        not unlocked, not a fight it cannot win. Dropping that conjunct would
        demote every gather-gated target in the catalogue on evidence that says
        nothing about them.
      * NONE OF THEM CLOSES. `combat_deficit` finds no gear chain that lifts the
        margin over any live dropper, so the target is not merely expensive —
        there is no sequence of acquisitions in the catalogue that makes it
        servable at this level. HAL's `slime_shield` sits here: `king_slimeball`
        drops from `king_slime` alone, a static 1000-hp spawn, and his best
        reachable chain gets the margin from -17 to -8.

    DEMOTION, NEVER EXCLUSION — see `_slot_order`. The verdict is a fact about
    THIS cycle's state (a level-30 HAL closes it), so a target that leaves the
    sheet here could never come back on its own.
    """
    if target.blocker is None or target.blocker == target.code:
        return False
    evidence = drop_evidence(target.blocker, state, game_data)
    return bool(evidence.on_live_tiles) and not evidence.closes


def dead_target_slots(targets: dict[str, GearTarget], state: WorldState,
                      game_data: GameData) -> frozenset[str]:
    """The slots of `targets` whose target is `_is_dead_target`, computed ONCE.

    THE REASON THIS IS NOT A `_slot_order` CONJUNCT COMPUTED IN PLACE:
    `_slot_order` is a SORT KEY, and `drop_evidence` walks every dropper of the
    blocker through `combat_deficit`, which costs tens of milliseconds. A key
    function runs O(n log n) times per cycle and `sorted` gives no memo, so
    asking there turns a 74 ms resolution into seconds. `resolve` asks once, for
    exactly the `len(targets)` distinct targets, and hands the answer down.
    """
    return frozenset(slot for slot, target in targets.items()
                     if _is_dead_target(target, state, game_data))


def _slot_order(item: tuple[str, GearTarget], state: WorldState,
                game_data: GameData, dead: frozenset[str]
                ) -> tuple[int, int, int, int]:
    """Descent key for `WhichSlotIsFurthestBehind`: reachable targets first,
    then furthest behind, then the higher-rung target, then the API schema's
    own slot order.

    The LEADING component is `dead_target_slots`' verdict as 0/1, so an
    ascending sort puts every target whose blocker something can open above
    every target whose blocker nothing can. It is a DEMOTION and the key is
    total either way: a dead target keeps its full place in
    `RootResolution.alternatives` and is still ranked against its dead peers by
    the same three components, it just cannot head the resolution while a
    servable sibling exists. Live 2026-09-12, HAL at level 20: `slime_shield`
    (blocked on `king_slimeball`, dropped only by `king_slime`, whose margin
    closes at no level he can reach) headed the walk, so the planner was handed
    `ObtainItem(king_slimeball, 6)` and returned `nodes=6 depth=2 plan_len=0 NO
    PLAN` every cycle. The fall-through cost no cycles; it cost the resolution
    its meaning.

    NOT A FILTER, and deliberately not. The verdict is state-dependent — HAL at
    level 30 beats `king_slime` — and `gear_targets_with_blockers` exists
    precisely to keep unattainable targets visible rather than dropping them on
    the floor (`near_term_gear` drops them; that is the defect `GearTarget` was
    introduced for). A removed target is invisible to `_servable_promotion`, to
    the plan pane and to every census that walks the alternatives.

    The last component is `EQUIPMENT_SLOTS.index`, the order the character
    schema declares its slots in — NOT `sorted(slot)`. An alphabetical
    tiebreak is the defect `feedback_no_alphabetical_tiebreak` names; the
    schema order is a declared vocabulary and is the only total order over
    slots this codebase actually publishes.
    """
    slot, target = item
    return (1 if slot in dead else 0,
            -_tier_gap(slot, target, state, game_data),
            -_target_rung(game_data, target.code),
            EQUIPMENT_SLOTS.index(slot))


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
    shortfall (`ctx.supply_shortfall`, the floor's tier food — the same roots
    `xp_demand.demand_roots` seeds), in two passes:

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
    with no destination. A skill a root on offer already climbs (the tier
    walk's skill-gated target, a supply-link climb) is left to that root.

    WHAT THIS REPLACED. The old gate admitted every skill no gear target could
    name (cooking and alchemy unconditionally) and a gear-nameable skill when
    nothing demanded it. Live 2026-10-08 the orphan `ReachSkillLevel(cooking,
    32)` pulled `fishing 30` in through its grind target and four characters
    spent ~100 cycles each on `Gather(trout_spot)` with nothing asking for a
    fish. An empty group is now legitimate: the trunk is always on offer
    ahead of it.

    "an open, XP-positive rung" is `skill_is_grindable(S, C+1)` — the SAME
    predicate `ReachSkillGoal`'s only action offers and the O1 census
    (`audit/open_rung_completeness`) verdicts a cell on, so no unplannable
    root is emitted.

    ORDER: ONE INTEGER, `state.level - skill level` — how far the skill trails
    the character, largest first — with ties broken by `SKILL_NAMES`, the
    schema vocabulary `world_state` derives from the API's own enums (never
    `sorted()` as a decision key; see `feedback_no_alphabetical_tiebreak`).
    DO NOT ADD A SECOND TERM: if the order is wrong, change WHICH integer it
    is, not how many.
    """
    roots = [*offered, *(ObtainItem(code, qty) for code, qty in ctx.supply_shortfall)]
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
        there is nothing to build for it. `task_worth.task_worth_for` reads
        this verdict as infeasible (a cancel); this node must not compete.
      * `HORIZON_LEVEL_UP` — one level would close it, and this node only fires
        when `ctx.combat_monster is None`, i.e. with NO monster worth fighting.
        A level goal here would have no beatable monster in its
        `relevant_actions`. That verdict is served from the EDGE instead — a
        real loss or level-up, where the cascade does find something — by
        `map_guard`'s surviving LEVEL_UP arm. Pinned by
        `test_an_out_of_horizon_task_leaves_the_character_doing_its_own_work`:
        letting the objective's own XP grind run IS the level-up being pursued.

    `ctx.combat_monster`, not a separate `winnable_alternative` parameter.
    `player.py` computes `_winnable_farm_target()` ONCE and hands it to
    `_selection_context`; the sibling node `IsThereACombatTarget` already reads
    `ctx`. One read.

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
    `map_guard`'s GEAR_REVIEW branch (that guard was deleted in Phase 4-3b), the
    only link the bot had between "I cannot
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
        gear = self.objective.classify_target(code, state)
        if not self.walk.serves(slot, gear, state, game_data, ctx, history):
            # The fight's best acquisition cannot be served this cycle (named
            # in `walk.declined`): the same fall-through as naming nothing.
            return IsMyGearBehindMyTier(self.objective, self.walk)
        return IsThisTargetBlocked(slot, gear, self.walk)


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
        served = {slot: target for slot, target in targets.items()
                  if self.walk.serves(slot, target, state, game_data, ctx, history)}
        declined = {slot: target for slot, target in targets.items() if slot not in served}
        dead = dead_target_slots(declined, state, game_data)
        self.walk.declined_targets = sorted(
            declined.items(), key=lambda item: _slot_order(item, state, game_data, dead))
        if not served:
            # Every target the sheet wants is blocked this cycle, each with its
            # named reason: the gear arm has nothing to offer, so the walk asks
            # the combat/tier arm, as it does when the sheet wants nothing.
            return IsThereACombatTarget(self.walk)
        return WhichSlotIsFurthestBehind(served, self.walk)


class WhichSlotIsFurthestBehind(Decision[MetaGoal]):
    """The largest tier gap among the served slots wins; the rest become
    `RootResolution.alternatives`, in `_slot_order`.

    `targets` is never empty: the only constructor call site is
    `IsMyGearBehindMyTier.resolve`, inside its `if not served` NEGATIVE arm.

    FAIRNESS IS NOT DECIDED HERE ANY MORE. `_slot_order` is a pure total order
    over a set that does not change while the character makes no progress, so
    on its own it would re-elect the same slot forever (the ring2 shape: a
    target whose only route is an unbeatable monster's drop, held once). That
    used to be answered here by focus aging and a d'Hondt interleave over the
    slots. Phase 4-2b replaced both with facts about the intention: a target
    that makes no progress ends as `stalled` (and a lost fight is learned, so
    the walk declines it), and one that spends its cycle budget goes to the back
    of the turn order (the arbiter tries the least recently served goal first,
    `intention_progress.rotate`), so every other candidate gets a turn.

    THE DEAD-TARGET DEMOTION IS A KEY, NOT A GATE. `dead_target_slots` is asked
    ONCE here and leads `_slot_order`, so a provably-dead target cannot head the
    walk while a servable sibling exists, and it stays on offer.
    """

    name = "WhichSlotIsFurthestBehind"

    def __init__(self, targets: dict[str, GearTarget], walk: RootWalk) -> None:
        self.targets = targets
        self.walk = walk

    def resolve(self, state: WorldState, game_data: GameData,
                ctx: SelectionContext, history: LearningStore | None
                ) -> "Decision[MetaGoal] | MetaGoal | None":
        self.walk.trail.append(self.name)
        # ONCE per cycle, NOT inside the key: see `dead_target_slots`.
        dead = dead_target_slots(self.targets, state, game_data)
        ranked = sorted(self.targets.items(),
                        key=lambda item: _slot_order(item, state, game_data, dead))
        (slot, target), *siblings = ranked
        self.walk.sibling_targets = siblings
        return IsThisTargetBlocked(slot, target, self.walk)


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
      acquisition that most improves the margin against the task monster
      (`combat_deficit.deficit_upgrade_target`, the question
      `WhichSlotClosesTheFight` asks), as an `ObtainItem` in its slot;
    * no gear closes the gap: None. The task waits, inert, for a coin to cancel
      it (S-052).

    * a WORTHLESS task (no XP, no GOLD, no DROPS reason — `task_worth_core`)
      with a pocket coin to cancel it: the task itself, whose step is the
      cancel (c-2 #5, USER 2026-10-07: this was the TASK_CANCEL rung and, before
      it, the LOW_YIELD_CANCEL rung). Without a coin it is worked to clear it.

    * a held, unmet items task: the task itself, worked (c-2 #4 was the
      PURSUE_TASK rung; #5 drops its PIVOT gate — a task is cancelled by its
      worth or worked).

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
        # the task objective's turn.
        return ReachTaskOutcome(state.task_code)
    if (state.task_type != "monsters" or not state.task_code
            or state.task_progress >= state.task_total):
        return None
    if is_winnable(replace(state, hp=state.max_hp), game_data, state.task_code, history):
        return ReachTaskOutcome(state.task_code)

    def actions_of(code: str, slot: str) -> int:
        return _route.route_price(ObtainItem(code, 1, slot=slot), state,
                                  game_data, ctx, history)

    target = deficit_upgrade_target(state, game_data, actions_of=actions_of)
    if target is None:
        return None
    code, slot = target
    return ObtainItem(code, 1, slot=slot)


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
                 step_decline: StepDecline = no_decline) -> RootResolution:
    """Walk the tier graph from `IsAFightBlockingMe` to a root MetaGoal.

    `step_decline` is the cycle's answer for a root's step (`StepDecline`); a
    gear target whose step it declines cannot head the walk and is offered
    after the served siblings, with its reason in `RootResolution.declined`."""
    walk = RootWalk(step_decline=step_decline)
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
        for slot, target in (*walk.sibling_targets, *walk.declined_targets)
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
    # `root` can be `None` (the wall case, `CanIClearMyTier`'s own docstring),
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
