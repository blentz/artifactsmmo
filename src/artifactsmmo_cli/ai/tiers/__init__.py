"""Tiered goal architecture.

P1: Tier-1 objective + gap + personality seam.
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
    ObjectiveGap,
    is_attainable,
)
from artifactsmmo_cli.ai.tiers.personality import (
    BalancedPersonality,
    Personality,
    weighted_remaining,
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
    "BalancedPersonality",
    "CharacterObjective",
    "MetaGoal",
    "ObjectiveGap",
    "ObtainItem",
    "Personality",
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
    "weighted_remaining",
]
