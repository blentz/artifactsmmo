"""Tier-3 strategy engine: descend the progression tree to the nearest
actionable subgoal. `decide` delegates to `progression_tree.decide_tree`
(Phase 4b THE FLIP); the flat scalar ranking pipeline is deleted."""

from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from fractions import Fraction

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.obtain_model.obtain_model import ObtainModel
from artifactsmmo_cli.ai.obtain_model.policy import Policy
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import progression_tree
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import (
    ATTAINABILITY_ALLOWS_GREY,
    CharacterObjective,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.world_state import WorldState


def root_category(node: MetaGoal) -> str:
    if isinstance(node, ReachCharLevel):
        return "char_level"
    if isinstance(node, ReachSkillLevel):
        return "skill"
    return "gear"  # ObtainItem


def desired_state_of(node: MetaGoal | None) -> dict[str, object]:
    if isinstance(node, ObtainItem):
        return {"have": {node.code: node.quantity}}
    if isinstance(node, ReachCharLevel):
        return {"level": node.level}
    return {}


_PREREQ_KIND_RANK: dict[type, int] = {ObtainItem: 0, ReachCharLevel: 1}
"""Sibling-descent priority for `actionable_step`'s DFS (retires the
`sorted(unmet, key=repr)` alphabetical tiebreak — feedback_no_alphabetical_
tiebreak). Materials (ObtainItem) rank before char-level gates
(ReachCharLevel): the mats are the concrete, immediate thing the character
can act on right now (gather/craft), while a char-level gate is the
broadest/slowest kind. This matches the OLD repr order too (`ObtainItem(...)`
always sorted before `ReachCharLevel(...)` — the class name is the first repr
token — so no production behavior changes) but the rank is now an intentional,
named decision instead of an accident of Python's default repr."""


def _prereq_order(node: MetaGoal) -> tuple[int, str, int]:
    """Semantic descent-priority key for `sorted(unmet, ...)`: (kind rank,
    semantic name, semantic level). The secondary/tertiary fields are the
    node's OWN identifying data (item code, or char level) — never a repr
    string — so a tie only breaks on the same semantic field the node already
    exposes."""
    if isinstance(node, ObtainItem):
        return (_PREREQ_KIND_RANK[ObtainItem], node.code, node.quantity)
    assert isinstance(node, ReachCharLevel), f"unhandled MetaGoal kind: {node!r}"
    return (_PREREQ_KIND_RANK[ReachCharLevel], "", node.level)


def actionable_step(root: MetaGoal, state: WorldState, game_data: GameData,
                    ctx: SelectionContext = NO_PROFILE_CONTEXT) -> MetaGoal | None:
    """Deepest unmet node reachable from root whose DIRECT prerequisites are all
    satisfied (the 'singular loop' step). None when cyclically blocked.

    Per-path cycle tracking mirrors is_reachable + matches the proved Lean model
    `Formal.StrategyTraversal.actStep` — bridge between Python and Lean is now
    byte-equivalent at the algorithm level. A node on the CURRENT DFS path is
    rejected (cycle guard); a node reached via a sibling branch is NOT pruned
    (the path frozenset backtracks on return)."""
    def _step(node: MetaGoal, path: frozenset[MetaGoal]) -> MetaGoal | None:
        if node in path:
            return None
        unmet = [p for p in prerequisites(node, state, game_data, ctx)
                 if not p.is_satisfied(state, game_data)]
        if not unmet:
            if isinstance(node, ObtainItem) and not _producible(node.code, state, game_data):
                return None
            return node
        sub_path = path | {node}
        for prereq in sorted(unmet, key=_prereq_order):
            step = _step(prereq, sub_path)
            if step is not None:
                return step
        return None

    return _step(root, frozenset())


def unmet_closure_size(root: MetaGoal, state: WorldState, game_data: GameData,
                       ctx: SelectionContext = NO_PROFILE_CONTEXT) -> int:
    """Structural cost proxy: count of unmet nodes in root's prereq closure (min 1)."""
    seen: set[MetaGoal] = set()
    stack: list[MetaGoal] = [root]
    count = 0
    while stack:
        node = stack.pop()
        if node in seen:
            continue
        seen.add(node)
        if not node.is_satisfied(state, game_data):
            count += 1
            stack.extend(prerequisites(node, state, game_data, ctx))
    return max(count, 1)


def root_cost(root: MetaGoal, state: WorldState, game_data: GameData,
             ctx: SelectionContext = NO_PROFILE_CONTEXT) -> int:
    """Effort proxy in 'steps remaining': levels for leaf progression goals,
    craft/gather chain size for gear. Floored at 1."""
    if isinstance(root, ReachCharLevel):
        return max(1, root.level - state.level)
    return unmet_closure_size(root, state, game_data, ctx)


STEP_POLICY = Policy(all_gather_routes=True, gather_skill_gate=False, craft_skill_gate=False,
                     event_vendors=False, spawn_known=True,
                     allow_grey=ATTAINABILITY_ALLOWS_GREY, vendor_routes=True, ge_routes=False,
                     task_rewards=True, fight_gold=True, drop_routes=True)
"""What the step graph counts as a way to produce a leaf, as an obtain-model
policy (step 4 of docs/PLAN_decision_architecture_redesign.md): every
gatherer, a routable spawn, a winnable dropper (grey allowed:
`ATTAINABILITY_ALLOWS_GREY`), a permanent vendor, the task board, and gold
earned by fighting. Gold is RENEWABLE here, as it always was for this test
("gold is producible"): a vendor leaf is a step the character can work toward
however far the pocket falls short, which is exactly what near-term
attainability (pocket gold only) must not say. No GE fill: goal emission fills
an order only as the cheaper venue for an item an NPC also sells (D-E). No
skill gate: an under-skill craft's gate is a sub-task the walk opens by a grind."""


def _producible(code: str, state: WorldState, game_data: GameData) -> bool:
    """Can the step graph treat `code` as a leaf it can produce? A craftable
    item always can: `prerequisites` decomposes its recipe, so its inputs are
    the step graph's own business, not this test's. Anything else is
    `ObtainModel.feasible(code, 1, STEP_POLICY)`: in hand (bag or bank), or a
    ready route whose inputs can be had.

    The winnability gate is load-bearing: a drop from an unwinnable monster must
    NOT read as producible, else the planner would emit an unreachable FightAction
    plan. The SPAWN gate is equally load-bearing: a winnable dropper with no
    routable spawn yields NO FightAction, so the item would read producible yet
    generate an empty plan. Both are the shared fight gates
    (`obtain_model/drop_routes.py`), judged at restorable hp.

    A purchase's currency is asked in the amount the price needs, recursively:
    currency on hand covering the price counts even when its droppers are
    currently unwinnable (the incremental accumulation route banks coins across
    cycles; 2026-07-06), and gold is earned by any winnable fight that pays it."""
    if game_data.crafting_recipe(code) is not None:
        return True
    model = ObtainModel(state, game_data, NO_PROFILE_CONTEXT, datetime.now(UTC))
    return model.feasible(code, 1, STEP_POLICY)


def is_reachable(root: MetaGoal, state: WorldState, game_data: GameData,
                 path: frozenset[MetaGoal] = frozenset(),
                 ctx: SelectionContext = NO_PROFILE_CONTEXT) -> bool:
    """True when `root`'s entire prerequisite chain bottoms out in obtainable
    leaves. Cycle-safe (a node on the current path can't bottom out)."""
    if root.is_satisfied(state, game_data):
        return True
    if root in path:
        return False
    prereqs = prerequisites(root, state, game_data, ctx)
    if isinstance(root, ObtainItem) and not prereqs:
        return _producible(root.code, state, game_data)
    sub_path = path | {root}
    return all(is_reachable(p, state, game_data, sub_path, ctx) for p in prereqs)


@dataclass(frozen=True)
class RootScore:
    root_repr: str
    category: str
    score: Fraction
    step_repr: str
    j: int | None = None
    """The unified objective's value for this root — LOWER IS BETTER, the
    opposite of `score`, which is why it is a separate field and not folded in.

    `score` is `pursuit_value` for gear and the constant `Fraction(1)` for the xp
    trunk. Those are two unrelated scales sharing a column, and printed together
    they read as a landslide that never happened: live 2026-08-08, gear showed
    `2.6e8` against the trunk's `1.0` while `J` had the two within 0.006% of each
    other and the trunk winning. Reporting a root's `J` beside its score is what
    lets a reader see the decision that was actually taken.

    None when `J` was not consulted (no learning store) — and None for any root
    outside the finite band, since the objective was void there. Wave 3b deleted
    `J` and every module that computed it, so nothing in `src/` writes this any
    more; roots carry `reachable_level` instead."""

    reachable_level: int | None = None
    """How far this root's projection actually gets, for a root `J` cannot price.

    A character can hold BOTH kinds at once and R2D2 did on 2026-08-08: its xp
    trunk stalled at level 17 (unreachable, so `j` is None) while a gear candidate
    reached 50 (`j=6490`). With only `j` to show, the trunk fell back to the
    legacy `score` — the constant `1.0` — so one pane listed `1.0` beside `6490`
    and reproduced the very cross-scale comparison this field exists to end.

    In the unreachable band the ordering key IS the reachable level (furthest
    progress first, then acquisition cost — S-006), so this is not a consolation
    figure: it is the number that actually decided those rows."""

    def to_dict(self) -> dict[str, object]:
        # P4a float boundary: scores are exact Fractions internally; the trace
        # record stays JSON-numeric by converting ONCE here (trace-only seam,
        # never read back into decisions).
        d = asdict(self)
        d["score"] = float(self.score)
        return d


@dataclass(frozen=True)
class StrategyDecision:
    interrupt: str | None
    chosen_root: MetaGoal | None
    chosen_step: MetaGoal | None
    ranking: list[RootScore] = field(default_factory=list)
    # Ranked alternative steps below the chosen one. Used by the arbiter
    # to fall back when the top step's goal is None (e.g. ReachCharLevel
    # with no winnable monster) instead of dropping straight into
    # discretionary. Closes the 2026-06-06 09:59 gap where 50+ cycles of
    # PursueTask ran because bootstrap step yielded None and the gear
    # roots (copper_boots, copper_helmet) at score 1.0 were never tried.
    fallback_steps: list[MetaGoal] = field(default_factory=list)
    # The ROOT paired with each fallback step (same index). The arbiter
    # uses this to map an intermediate ObtainItem step back to its
    # equippable root: a step like ObtainItem(copper_bar, 8) emerged from
    # ObtainItem(copper_boots) → UpgradeEquipmentGoal(copper_boots) should
    # be used (planner crafts bars + boots in one chain) rather than
    # GatherMaterials(copper_bar) which only crafts bars and stops.
    fallback_roots: list[MetaGoal] = field(default_factory=list)
    # The gear code whose CRAFTING-SKILL GATE produced a `ReachSkillLevel` root
    # (`decisions/root.RootWalk.blocked_target`). Carried so the player can
    # PUBLISH it as fleet demand: a blocked character's root is a skill climb,
    # not an `ObtainItem`, so without this it publishes nothing at all and the
    # one item a sibling could make for it is the one never asked for.
    blocked_target: str | None = None
    # Whether the committed gear pick went through the focus-aging INTERLEAVE
    # this decision (Task 12): True iff a gear candidate was chosen AND at least
    # one candidate had aged past FOCUS_FLAT. Produced by the ONE node that
    # makes that choice — `WhichSlotIsFurthestBehind._aged_head`
    # (`ai/decisions/root.py:348-365`) sets `RootResolution.aged`, and
    # `decide_tree` copies it straight across. It used to be re-derived here as
    # the negation of `focus_aging_pick`'s fast-path condition over the same
    # candidates; wave 3a made the node the single producer and wave 3b deleted
    # `focus_aging_pick`, so there is no second derivation left to drift from.
    # The player gates its
    # d'Hondt SEAT bump on this — a seat is consumed only on an interleaved
    # decision, so a stale ledger entry for a root that has LEFT the candidate
    # set (e.g. its slot got filled by equipping owned gear, no reset) can no
    # longer pollute the schedule. Defaulted False: fast-path / non-gear / XP
    # decisions consume no seat, and every non-tree constructor is unaffected.
    aged_pick: bool = False
    # The root the TREE picked, when servability promotion then displaced it;
    # None when the tree's own pick survived. Diagnostic only — no decision
    # reads it — but the distinction is not recoverable afterwards: the
    # servability diagnostic is computed on the FINAL decision, so a promoted
    # root logs as servable and the promotion is invisible. Live 2026-07-27:
    # 9 of 15 cycles logged `chosen_root: ReachCharLevel, servable: true` and
    # read as the tree choosing XP, when the tree had chosen GEAR every time
    # and promotion walked to the trunk sitting at fallback index 0.
    promoted_from: MetaGoal | None = None

    def to_trace(self) -> dict[str, object]:
        return {
            "interrupt": self.interrupt,
            "chosen_root": repr(self.chosen_root) if self.chosen_root is not None else None,
            "chosen_step": repr(self.chosen_step) if self.chosen_step is not None else None,
            "ranking": [rs.to_dict() for rs in self.ranking],
            "fallback_steps": [repr(s) for s in self.fallback_steps],
            "fallback_roots": [repr(r) for r in self.fallback_roots],
        }


@dataclass(frozen=True)
class StrategyEngine:
    objective: CharacterObjective

    def decide(self, state: WorldState, game_data: GameData,
               step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
               ctx: SelectionContext = NO_PROFILE_CONTEXT,
               history: LearningStore | None = None,
               ) -> StrategyDecision:
        """Thin delegate to the progression tree, which since wave 3a RESOLVES
        the root through `ai/decisions/root.py` instead of ranking candidates.

        Six parameters went with the ranking — `band_adequate`, `focus`,
        `seats`, `committed_root_code`, `enable_synergy` and `store` (renamed
        `history`). See `progression_tree.decide_tree` for why each one has no
        reader left.

        `step_servable` keeps the plannability demotion alive (see
        `progression_tree._servable_promotion`). `ctx` is the caller's
        per-cycle `SelectionContext` (see `GamePlayer._decide_band` /
        `plan_from_state`), forwarded to every `actionable_step` call so the
        descent stops at a node with any ready `ai/obtain_sources` route
        instead of falling into its recipe (one-obtain-model epic, Task 5;
        originally the recycle-as-acquisition epic's bespoke `recoverable`
        map). Defaults to `NO_PROFILE_CONTEXT` for every caller that doesn't
        wire it in.

        `history` is the learning store the root walk's own nodes read —
        `IsMyGearBehindMyTier` passes it to `gear_targets_with_blockers` and
        `CanIClearMyTier` to `next_uncleared_tier`. None is a legitimate
        answer, not a disabled mode: both fall back to the state-only verdict
        the same way every other `Decision` in the codebase does."""
        return progression_tree.decide_tree(
            state, game_data, self.objective,
            step_servable=step_servable, ctx=ctx, history=history)
