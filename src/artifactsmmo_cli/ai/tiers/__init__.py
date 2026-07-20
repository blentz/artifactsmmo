"""Tiered goal architecture.

P1: Tier-1 objective.
P2: Tier-2 meta-goal nodes + prerequisite graph (search substrate)."""

from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.tiers.meta_goal import (
    MetaGoal,
    ObtainItem,
    ReachCharLevel,
    owned_count,
)
from artifactsmmo_cli.ai.tiers.objective import (
    CharacterObjective,
    is_attainable,
)
from artifactsmmo_cli.ai.tiers.prerequisite_graph import (
    best_attainable_weapon,
    combat_capable,
    prerequisites,
)
from artifactsmmo_cli.ai.tiers.strategy import (
    RootScore,
    StrategyDecision,
    StrategyEngine,
    actionable_step,
    desired_state_of,
    root_category,
    unmet_closure_size,
)

__all__ = [
    "CharacterObjective",
    "MetaGoal",
    "ObtainItem",
    "ReachCharLevel",
    "RootScore",
    "StrategyDecision",
    "StrategyEngine",
    "actionable_step",
    "best_attainable_weapon",
    "combat_capable",
    "desired_state_of",
    "equip_value",
    "is_attainable",
    "owned_count",
    "prerequisites",
    "root_category",
    "unmet_closure_size",
]
