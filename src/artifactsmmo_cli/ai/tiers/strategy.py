"""Tier-3 strategy engine: descend the progression tree to the nearest
actionable subgoal. `decide` delegates to `progression_tree.decide_tree`
(Phase 4b THE FLIP); the flat scalar ranking pipeline is deleted."""

from collections.abc import Callable, Mapping
from dataclasses import asdict, dataclass, field
from fractions import Fraction
from types import MappingProxyType

from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT, SelectionContext
from artifactsmmo_cli.ai.tiers import progression_tree
from artifactsmmo_cli.ai.tiers.leaf_attainable_core import leaf_attainable_pure
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
)
from artifactsmmo_cli.ai.tiers.objective import GOLD, CharacterObjective, _permanent_vendor_purchases
from artifactsmmo_cli.ai.tiers.prerequisite_graph import prerequisites
from artifactsmmo_cli.ai.world_state import WorldState

_NO_FOCUS: Mapping[tuple[str, str], int] = MappingProxyType({})
"""Immutable empty-focus default, sibling of `progression_tree._NO_FOCUS` (not
imported directly: `progression_tree` imports this module at its top, so a
reverse name-import here would race the circular load order). Avoids a
mutable `{}` default (ruff B006); read-only, forwarded straight through to
`decide_tree`."""

_NO_SEATS: Mapping[str, int] = MappingProxyType({})
"""Immutable empty-seats default, sibling of `_NO_FOCUS` and
`progression_tree._NO_SEATS` (same circular-load reason it is redeclared here
rather than imported). The d'Hondt seat accumulator for the focus-aging
interleave; read-only, forwarded straight through to `decide_tree` (Task 12
perf: O(candidates) incremental seats replace the unbounded global cycle
index)."""


def root_category(node: MetaGoal) -> str:
    if isinstance(node, ReachCharLevel):
        return "char_level"
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
                    ctx: SelectionContext = NO_PROFILE_CONTEXT,
                    exclude_recycle_leaf: bool = False) -> MetaGoal | None:
    """Deepest unmet node reachable from root whose DIRECT prerequisites are all
    satisfied (the 'singular loop' step). None when cyclically blocked.

    Per-path cycle tracking mirrors is_reachable + matches the proved Lean model
    `Formal.StrategyTraversal.actStep` — bridge between Python and Lean is now
    byte-equivalent at the algorithm level. A node on the CURRENT DFS path is
    rejected (cycle guard); a node reached via a sibling branch is NOT pruned
    (the path frozenset backtracks on return).

    `exclude_recycle_leaf` (a SKILL GRIND sets it): a RECYCLE source does not
    leaf a material, so the grind descends past a recyclable-only intermediate
    to its gatherable raw — see `prerequisites`."""
    def _step(node: MetaGoal, path: frozenset[MetaGoal]) -> MetaGoal | None:
        if node in path:
            return None
        unmet = [p for p in prerequisites(node, state, game_data, ctx,
                                          exclude_recycle_leaf)
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


def _producible(code: str, state: WorldState, game_data: GameData) -> bool:
    """True when the item can be made by known means: craftable (has a recipe),
    gatherable (some resource drops it), task-earnable (awarded by the task loop),
    currency-buyable from a permanent vendor for gold or a directly task-earnable
    currency, or obtainable by FIGHTING — some monster that drops it is WINNABLE
    with the best on-hand loadout.

    The winnability gate is load-bearing: a drop from an unwinnable monster must
    NOT read as producible, else the planner would emit an unreachable FightAction
    plan. The SPAWN-LOCATION gate is equally load-bearing: a winnable dropper with
    no known `monster_locations` entry yields NO FightAction (the fight-is-None
    guard in GatherMaterialsGoal.relevant_actions), so the item would read
    producible yet generate an empty/stuck plan. Requiring a non-empty spawn list
    makes producible ⇒ a FightAction can actually be emitted (genuinely obtainable).

    The currency-buy check here is FLAT (non-recursive): currency is gold or is
    directly task-earnable. This is sufficient because tasks_coin (the real
    use-case) is directly task-earnable. Cross-prerequisite recursion lives in
    is_reachable, not here. The `known_spawn_drop` flag uses the WINNABLE+spawned
    drop (state-aware), preserving the winnability gate.

    Routes the leaf decision through leaf_attainable_pure so the Lean proof
    governs the live behavior (Finding B fix). Craftable short-circuits before
    the core call to avoid instantiating the four flags when unneeded."""
    if game_data.crafting_recipe(code) is not None:
        return True
    # Already IN HAND (inventory or bank): nothing left to produce — the
    # obtain step is served by withdraw/equip. Without this arm a HELD
    # recipe-less vendor item (sandwhisper_bag bought a cycle ago) still
    # read not-producible and actionable_step went dead (2026-07-06).
    bank = state.bank_items or {}
    if state.inventory.get(code, 0) > 0 or bank.get(code, 0) > 0:
        return True
    # Currency-buy, one level deep: gold, task-earnable (tasks_coin), or a
    # currency the character can PRODUCE now — gatherable (hides come from
    # fights but wool/dusts also gather-adjacent items count via the full
    # drop tables) or dropped by a currently-winnable spawned monster
    # (P3, docs/PLAN_engagement_expansion.md: tailor leathers @ hides,
    # archaeologist @ shards, cultist @ corrupted_gem). Currencies are base
    # items, so one level suffices; is_reachable recurses for the rest.
    def _currency_producible(currency: str) -> bool:
        if currency == GOLD or game_data.is_task_earnable(currency):
            return True
        if currency in game_data.gatherable_drop_items():
            return True
        return any(
            is_winnable(state, game_data, monster_code)
            and game_data.monster_spawn_known(monster_code)
            for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(currency))
    # A purchase is producible when the currency can be PRODUCED — or is
    # ALREADY EARNED: currency on hand (inventory + bank) covering the price
    # counts even when its droppers are currently unwinnable (the incremental
    # accumulation route banks coins across cycles; 2026-07-06).
    buyable = any(
        state.inventory.get(currency, 0) + bank.get(currency, 0) >= price
        or _currency_producible(currency)
        for price, currency in _permanent_vendor_purchases(code, game_data))
    # Winnable drop: state-aware (preserves the winnability gate).
    winnable_drop = any(
        is_winnable(state, game_data, monster_code)
        and game_data.monster_spawn_known(monster_code)
        for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))
    return leaf_attainable_pure(
        code in game_data.gatherable_drop_items(),
        winnable_drop,
        game_data.is_task_earnable(code),
        buyable)


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
    contribution: Fraction
    cost: int
    score: Fraction
    step_repr: str
    instrumental: bool = False

    def to_dict(self) -> dict[str, object]:
        # P4a float boundary: scores are exact Fractions internally; the trace
        # record stays JSON-numeric by converting ONCE here (trace-only seam,
        # never read back into decisions).
        d = asdict(self)
        d["contribution"] = float(self.contribution)
        d["score"] = float(self.score)
        return d


@dataclass(frozen=True)
class StrategyDecision:
    interrupt: str | None
    chosen_root: MetaGoal | None
    chosen_step: MetaGoal | None
    desired_state: dict[str, object]
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
    # Whether the committed gear pick went through the focus-aging INTERLEAVE
    # this decision (Task 12): True iff a gear candidate was chosen AND at least
    # one candidate had aged past FOCUS_FLAT (the negation of `focus_aging_pick`'s
    # fast-path condition, over the SAME candidates). The player gates its
    # d'Hondt SEAT bump on this — a seat is consumed only on an interleaved
    # decision, so a stale ledger entry for a root that has LEFT the candidate
    # set (e.g. its slot got filled by equipping owned gear, no reset) can no
    # longer pollute the schedule. Defaulted False: fast-path / non-gear / XP
    # decisions consume no seat, and every non-tree constructor is unaffected.
    aged_pick: bool = False

    def to_trace(self) -> dict[str, object]:
        return {
            "interrupt": self.interrupt,
            "chosen_root": repr(self.chosen_root) if self.chosen_root is not None else None,
            "chosen_step": repr(self.chosen_step) if self.chosen_step is not None else None,
            "desired_state": self.desired_state,
            "ranking": [rs.to_dict() for rs in self.ranking],
            "fallback_steps": [repr(s) for s in self.fallback_steps],
            "fallback_roots": [repr(r) for r in self.fallback_roots],
        }


@dataclass(frozen=True)
class StrategyEngine:
    objective: CharacterObjective

    def decide(self, state: WorldState, game_data: GameData,
               step_servable: Callable[[MetaGoal, MetaGoal], bool] | None = None,
               band_adequate: bool = False,
               ctx: SelectionContext = NO_PROFILE_CONTEXT,
               focus: Mapping[tuple[str, str], int] = _NO_FOCUS,
               seats: Mapping[str, int] = _NO_SEATS,
               ) -> StrategyDecision:
        """THE FLIP (Phase 4b): thin delegate to the progression tree — the
        flat scalar ranking pipeline is deleted (Task 2). The tree is
        deterministic, so decide-level sticky scoring and the learned blend
        are gone with it; arbiter-level commitment (objective-committed
        arbitration, zombie release) is unaffected.

        `band_adequate` is the caller's progression-band verdict (see
        `GamePlayer._tree_band_adequate`); `step_servable` keeps the
        plannability demotion alive across the cutover (see
        `progression_tree._servable_promotion`). `ctx` is the caller's
        per-cycle `SelectionContext` (see `GamePlayer._decide_band` /
        `plan_from_state`), forwarded to every `actionable_step` call so the
        descent stops at a node with any ready `ai/obtain_sources` route
        instead of falling into its recipe (one-obtain-model epic, Task 5;
        originally the recycle-as-acquisition epic's bespoke `recoverable`
        map). Defaults to `NO_PROFILE_CONTEXT` for every caller that doesn't
        wire it in.

        `focus`/`seats` (arbiter anti-starvation epic, Task 4; Task 12 perf)
        are forwarded straight through to `decide_tree`'s aging pick/order —
        see that docstring. `seats` is the incremental d'Hondt seat accumulator
        (O(candidates) per decision, replacing the unbounded global cycle
        index). Both default to the empty-focus / empty-seats case, reproducing
        today's plain argmax for every caller that doesn't wire the ledger
        in."""
        return progression_tree.decide_tree(
            state, game_data, self.objective,
            band_adequate=band_adequate, step_servable=step_servable,
            ctx=ctx, focus=focus, seats=seats)
