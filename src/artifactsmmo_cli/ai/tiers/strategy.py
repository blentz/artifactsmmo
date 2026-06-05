"""Tier-3 strategy engine: rank Tier-1 roots and descend to the nearest
actionable subgoal. Pure; P3a runs it in shadow (traced, not enacted)."""

from dataclasses import asdict, dataclass, field

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import expected_yield_per_cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.decide_key import decide_key
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.tiers.personality import Personality
from artifactsmmo_cli.ai.tiers.prerequisite_graph import objective_roots, prerequisites
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    balancing as _balancing_pure,
)
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    blend_weight,
)
from artifactsmmo_cli.ai.tiers.strategy_blend import (
    learned_blend as _learned_blend_pure,
)
from artifactsmmo_cli.ai.world_state import WorldState

# Mirrors RestoreHPGoal.CRITICAL_HP_FRACTION. Kept local so the tiers layer does
# not depend on goals/ (which P3c retires); P3c unifies the source.
CRITICAL_HP_FRACTION = 0.25

PRIOR_CHAR_LEVEL = 1.0
PRIOR_COMBAT_GEAR = 1.0
PRIOR_UTILITY_GEAR = 0.4
PRIOR_COMBAT_CRAFT_SKILL = 0.6
PRIOR_GATHER_SKILL = 0.4
PRIOR_CONSUMABLE_SKILL = 0.3
SKILL_MARGINAL = 0.2
CHAR_MARGINAL = 1.0
GEAR_EQUIP_SCALE = 20.0
"""Normalizes gear equip-value gain to ~[0,1]; tune so a first-tier upgrade ~0.7-0.9."""
BALANCE_K = 0.25
BALANCE_THRESHOLD = 2
BALANCE_MIN = 0.5
BALANCE_MAX = 2.0
STICKY_DOMINANCE_RATIO = 1.5
PRIOR_RELEVANT_TOOL = 1.1
"""Active-task tool boost: a target_tools item whose skill_effects match
the bot's currently-active gathering skill (state.task_code resolved via
`game_data.active_gathering_skills`) gets this prior, BEATING
PRIOR_CHAR_LEVEL=1.0 so the bot crafts the tool before continuing the
grind. Without this boost, target_tools items scored at static
PRIOR_UTILITY_GEAR=0.4 * marginal=0=0 (or PRIOR_UTILITY_GEAR*0.25
fallback=0.1) and the bot never crafted any tool despite hours of
gathering. Fix shipped after trace cycle 760 evidence of static
0.1 tool scoring."""
"""Tier-2 sticky-commitment threshold. The previous cycle's chosen_root is
kept unless a new top candidate's score strictly exceeds
`STICKY_DOMINANCE_RATIO * sticky_score`. Matches Tier-3 means-tier
commitment: only switch when the new winner dominates by 50%+. Prevents
single-cycle objective flap from transient predicate flips (e.g.
combat_capable=False momentarily because pick_loadout's inventory
projection changes when inventory composition shifts)."""
_COMBAT_GEAR_SLOTS = frozenset({"weapon_slot", "shield_slot", "helmet_slot", "body_armor_slot",
                                "leg_armor_slot", "boots_slot", "ring1_slot", "ring2_slot", "amulet_slot"})
_COMBAT_CRAFT_SKILLS = frozenset({"weaponcrafting", "gearcrafting", "jewelrycrafting"})
_GATHER_SKILLS = frozenset({"mining", "woodcutting", "fishing"})
_CONSUMABLE_CRAFT_SKILLS = frozenset({"alchemy", "cooking"})

LEARN_W_MAX = 0.5
LEARN_SAMPLE_FULL = 20
XP_RATE_REFERENCE = 10.0
"""Observed char-XP/cycle that normalizes to 1.0; tune to a strong grind rate."""


def root_category(node: MetaGoal) -> str:
    if isinstance(node, ReachCharLevel):
        return "char_level"
    if isinstance(node, ReachSkillLevel):
        return "skills"
    return "gear"  # ObtainItem


def desired_state_of(node: MetaGoal | None) -> dict[str, object]:
    if isinstance(node, ObtainItem):
        return {"have": {node.code: node.quantity}}
    if isinstance(node, ReachSkillLevel):
        return {"skill": {node.skill: node.level}}
    if isinstance(node, ReachCharLevel):
        return {"level": node.level}
    return {}


def actionable_step(root: MetaGoal, state: WorldState, game_data: GameData) -> MetaGoal | None:
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
        unmet = [p for p in prerequisites(node, state, game_data)
                 if not p.is_satisfied(state, game_data)]
        if not unmet:
            if isinstance(node, ObtainItem) and not _producible(node.code, game_data):
                return None
            return node
        sub_path = path | {node}
        for prereq in sorted(unmet, key=repr):
            step = _step(prereq, sub_path)
            if step is not None:
                return step
        return None

    return _step(root, frozenset())


def unmet_closure_size(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
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
            stack.extend(prerequisites(node, state, game_data))
    return max(count, 1)


def root_cost(root: MetaGoal, state: WorldState, game_data: GameData) -> int:
    """Effort proxy in 'steps remaining': levels for leaf progression goals,
    craft/gather chain size for gear. Floored at 1."""
    if isinstance(root, ReachCharLevel):
        return max(1, root.level - state.level)
    if isinstance(root, ReachSkillLevel):
        return max(1, root.level - state.skills.get(root.skill, 1))
    return unmet_closure_size(root, state, game_data)


def _producible(code: str, game_data: GameData) -> bool:
    """True when the item can be made by known means: craftable (has a recipe)
    or gatherable (some resource drops it). Buying / monster-drops are not
    modelled yet, so such items read as not-producible."""
    return (game_data.crafting_recipe(code) is not None
            or code in game_data._resource_drops.values())


def is_reachable(root: MetaGoal, state: WorldState, game_data: GameData,
                 path: frozenset[MetaGoal] = frozenset()) -> bool:
    """True when `root`'s entire prerequisite chain bottoms out in obtainable
    leaves. Cycle-safe (a node on the current path can't bottom out)."""
    if root.is_satisfied(state, game_data):
        return True
    if root in path:
        return False
    if isinstance(root, ReachSkillLevel):
        return True  # grinding the skill is always an available action
    prereqs = prerequisites(root, state, game_data)
    if isinstance(root, ObtainItem) and not prereqs:
        return _producible(root.code, game_data)
    sub_path = path | {root}
    return all(is_reachable(p, state, game_data, sub_path) for p in prereqs)


@dataclass(frozen=True)
class RootScore:
    root_repr: str
    category: str
    contribution: float
    cost: int
    score: float
    step_repr: str
    instrumental: bool = False

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class StrategyDecision:
    interrupt: str | None
    chosen_root: MetaGoal | None
    chosen_step: MetaGoal | None
    desired_state: dict[str, object]
    ranking: list[RootScore] = field(default_factory=list)

    def to_trace(self) -> dict[str, object]:
        return {
            "interrupt": self.interrupt,
            "chosen_root": repr(self.chosen_root) if self.chosen_root is not None else None,
            "chosen_step": repr(self.chosen_step) if self.chosen_step is not None else None,
            "desired_state": self.desired_state,
            "ranking": [rs.to_dict() for rs in self.ranking],
        }


@dataclass(frozen=True)
class StrategyEngine:
    objective: CharacterObjective
    personality: Personality

    def _base_prior(self, root: MetaGoal) -> float:
        category = root_category(root)
        weight = self.personality.category_weight(category)
        if isinstance(root, ReachCharLevel):
            tier = PRIOR_CHAR_LEVEL
        elif isinstance(root, ReachSkillLevel):
            if root.skill in _COMBAT_CRAFT_SKILLS:
                tier = PRIOR_COMBAT_CRAFT_SKILL
            elif root.skill in _GATHER_SKILLS:
                tier = PRIOR_GATHER_SKILL
            elif root.skill in _CONSUMABLE_CRAFT_SKILLS:
                tier = PRIOR_CONSUMABLE_SKILL
            else:
                tier = 0.0   # unknown skill — no prior, scores zero
        elif isinstance(root, ObtainItem):
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            tier = PRIOR_COMBAT_GEAR if slot in _COMBAT_GEAR_SLOTS else PRIOR_UTILITY_GEAR
        else:
            tier = 0.0
        return tier * weight

    def _marginal(self, root: MetaGoal, state: WorldState, game_data: GameData) -> float:
        if isinstance(root, ReachCharLevel):
            return CHAR_MARGINAL
        if isinstance(root, ReachSkillLevel):
            return SKILL_MARGINAL
        if isinstance(root, ObtainItem):
            stats = game_data.item_stats(root.code)
            if stats is None:
                return 0.0
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            current_code = state.equipment.get(slot) if slot is not None else None
            current_stats = game_data.item_stats(current_code) if current_code else None
            current_value = equip_value(current_stats) if current_stats is not None else 0.0
            gain = max(0.0, equip_value(stats) - current_value)
            return min(1.0, gain / GEAR_EQUIP_SCALE)
        return 0.0

    def _balancing(self, root: MetaGoal, state: WorldState) -> float:
        if not isinstance(root, ReachSkillLevel):
            return 1.0
        levels = list(state.skills.values())
        leader = max(levels) if levels else 0
        current = state.skills.get(root.skill, 0)
        return _balancing_pure(leader, current)

    def _relevant_tool_value(self, root: MetaGoal, state: WorldState,
                             game_data: GameData) -> float:
        """Active-task tool boost. Returns PRIOR_RELEVANT_TOOL when the
        root is a target_tools item whose skill matches the current
        task's active gathering skill; else 0. Combined with `_value`
        via max so the boost can't accidentally suppress a higher-scored
        baseline."""
        if not isinstance(root, ObtainItem):
            return 0.0
        # Find the gathering skill this tool would boost (the target_tools
        # entry maps skill → code; reverse the lookup).
        skill_for_tool = next(
            (s for s, c in self.objective.target_tools.items() if c == root.code),
            None,
        )
        if skill_for_tool is None:
            return 0.0
        active = game_data.active_gathering_skills(
            state.task_code, state.crafting_target,
        )
        if skill_for_tool not in active:
            return 0.0
        category = root_category(root)
        weight = self.personality.category_weight(category)
        return PRIOR_RELEVANT_TOOL * weight

    def _value(self, root: MetaGoal, state: WorldState, game_data: GameData) -> float:
        base = self._base_prior(root) * self._marginal(root, state, game_data) * self._balancing(root, state)
        return max(base, self._relevant_tool_value(root, state, game_data))

    def _learned_blend(self, root: MetaGoal, value: float,
                       history: LearningStore | None, combat_monster: str | None) -> float:
        if not (isinstance(root, ReachCharLevel) and history is not None and combat_monster):
            return value
        y = expected_yield_per_cycle(f"FarmMonster({combat_monster})", history)
        if y.sample_count <= 0:
            return value
        normalized = min(1.0, max(0.0, y.char_xp / XP_RATE_REFERENCE))
        w = blend_weight(y.sample_count)
        return _learned_blend_pure(value, normalized, w)

    def decide(self, state: WorldState, game_data: GameData,
               history: LearningStore | None = None,
               combat_monster: str | None = None,
               last_chosen_root: str | None = None) -> StrategyDecision:
        """Pick the top-ranked objective root with Tier-2 sticky commitment.

        `last_chosen_root` is the previous cycle's chosen_root repr (None on
        first cycle). When supplied AND the matching candidate survives this
        cycle's is_satisfied + is_reachable filters AND its score is at least
        `STICKY_RATIO` (2/3) of the winner's score, prefer it. Eliminates
        single-cycle objective flap (e.g. transient combat_capable=False
        flips that would otherwise demote ReachCharLevel for one cycle while
        an inferior gear objective momentarily wins).
        """
        interrupt = "restore_hp" if state.hp_percent < CRITICAL_HP_FRACTION else None
        candidates: list[tuple[MetaGoal, MetaGoal, float, int, float]] = []   # root, step, final, effort, pre
        for root in objective_roots(self.objective, state):
            if root.is_satisfied(state, game_data):
                continue
            if not is_reachable(root, state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            assert step is not None
            value = self._value(root, state, game_data)
            final = self._learned_blend(root, value, history, combat_monster)
            effort = root_cost(root, state, game_data)
            candidates.append((root, step, final, effort, value))
        candidates.sort(key=lambda c: decide_key(-c[2], c[3], repr(c[0])))   # final desc, effort asc, repr last
        ranking = [
            RootScore(repr(r), root_category(r), pre, effort, final, repr(s), False)
            for (r, s, final, effort, pre) in candidates
        ]
        if candidates:
            top_root, top_step, top_final, _top_effort, _top_pre = candidates[0]
            chosen_root: MetaGoal | None = top_root
            chosen_step: MetaGoal | None = top_step
            # Tier-2 sticky commitment: keep the previous cycle's chosen root
            # when it survives this cycle's filters AND its score is within
            # the dominance threshold of the new winner. Prevents single-cycle
            # objective flap from transient combat_capable flips.
            if last_chosen_root is not None and last_chosen_root != repr(top_root):
                sticky_candidate = next(
                    (c for c in candidates if repr(c[0]) == last_chosen_root),
                    None,
                )
                if sticky_candidate is not None:
                    sticky_final = sticky_candidate[2]
                    # Sticky wins unless top is strictly dominant
                    # (top_final > STICKY_DOMINANCE_RATIO * sticky_final).
                    if top_final <= STICKY_DOMINANCE_RATIO * sticky_final:
                        chosen_root = sticky_candidate[0]
                        chosen_step = sticky_candidate[1]
        else:
            chosen_root = chosen_step = None
        return StrategyDecision(
            interrupt=interrupt,
            chosen_root=chosen_root,
            chosen_step=chosen_step,
            desired_state=desired_state_of(chosen_step),
            ranking=ranking,
        )
