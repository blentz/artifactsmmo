"""Tier-3 strategy engine: rank Tier-1 roots and descend to the nearest
actionable subgoal. Pure; P3a runs it in shadow (traced, not enacted)."""

from dataclasses import asdict, dataclass, field

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective, ObjectiveGap
from artifactsmmo_cli.ai.tiers.personality import Personality
from artifactsmmo_cli.ai.tiers.prerequisite_graph import objective_roots, prerequisites
from artifactsmmo_cli.ai.world_state import WorldState

# Mirrors RestoreHPGoal.CRITICAL_HP_FRACTION. Kept local so the tiers layer does
# not depend on goals/ (which P3c retires); P3c unifies the source.
CRITICAL_HP_FRACTION = 0.25


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
    satisfied (the 'singular loop' step). None when cyclically blocked."""
    def _step(node: MetaGoal, visited: set[MetaGoal]) -> MetaGoal | None:
        if node in visited:
            return None
        visited.add(node)
        unmet = [p for p in prerequisites(node, state, game_data)
                 if not p.is_satisfied(state, game_data)]
        if not unmet:
            if isinstance(node, ObtainItem) and not _producible(node.code, game_data):
                return None
            return node
        for prereq in sorted(unmet, key=repr):
            step = _step(prereq, visited)
            if step is not None:
                return step
        return None

    return _step(root, set())


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


def instrumental_skills(objective: CharacterObjective, game_data: GameData) -> set[str]:
    """Crafting skills that gate target gear — leveling these unlocks gear the
    objective wants, so they win skill ties."""
    skills: set[str] = set()
    for code in objective.target_gear.values():
        stats = game_data.item_stats(code)
        if stats is not None and stats.crafting_skill:
            skills.add(stats.crafting_skill)
    return skills


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

    def _contribution(self, root: MetaGoal, gap: ObjectiveGap, game_data: GameData) -> float:
        category = root_category(root)
        weight = self.personality.category_weight(category)
        if isinstance(root, ReachCharLevel):
            share = gap.char_level_fraction
        elif isinstance(root, ReachSkillLevel):
            share = gap.skill_gaps.get(root.skill, 0) / game_data.max_skill_level
        elif isinstance(root, ObtainItem):  # gear
            slot = next((s for s, c in self.objective.target_gear.items() if c == root.code), None)
            total = sum(
                equip_value(stats)
                for c in self.objective.target_gear.values()
                if (stats := game_data.item_stats(c)) is not None
            )
            share = (gap.gear_gaps.get(slot, 0.0) / total) if (slot is not None and total > 0) else 0.0
        else:
            share = 0.0
        return weight * share

    def decide(self, state: WorldState, game_data: GameData) -> StrategyDecision:
        interrupt = "restore_hp" if state.hp_percent < CRITICAL_HP_FRACTION else None
        gap = self.objective.gap(state)
        instrumental = instrumental_skills(self.objective, game_data)

        def is_instrumental(root: MetaGoal) -> bool:
            return isinstance(root, ReachSkillLevel) and root.skill in instrumental

        candidates: list[tuple[MetaGoal, MetaGoal, float, int, float]] = []
        for root in objective_roots(self.objective):
            if root.is_satisfied(state, game_data):
                continue
            if not is_reachable(root, state, game_data):
                continue
            step = actionable_step(root, state, game_data)
            # is_reachable guarantees the chain bottoms out in a producible step.
            assert step is not None
            contribution = self._contribution(root, gap, game_data)
            cost = root_cost(root, state, game_data)
            score = contribution / max(cost, 1)
            candidates.append((root, step, contribution, cost, score))
        candidates.sort(key=lambda c: (-c[4], 0 if is_instrumental(c[0]) else 1, repr(c[0])))
        ranking = [
            RootScore(repr(r), root_category(r), contribution, cost, score, repr(s),
                      is_instrumental(r))
            for (r, s, contribution, cost, score) in candidates
        ]
        if candidates:
            chosen_root: MetaGoal | None = candidates[0][0]
            chosen_step: MetaGoal | None = candidates[0][1]
        else:
            chosen_root = chosen_step = None
        return StrategyDecision(
            interrupt=interrupt,
            chosen_root=chosen_root,
            chosen_step=chosen_step,
            desired_state=desired_state_of(chosen_step),
            ranking=ranking,
        )
