"""`credit_demanded_skills`: the acquisition routes with every action that
trains a demanded skill made free
(docs/superpowers/specs/2026-10-13-fleet-food-role-design.md §2).

USER 2026-10-13, "useful XP only": seconds spent on a skill the goal-action DAG
still demands (`SelectionContext.skill_demand`) are spent levelling it anyway,
so they are not a cost of what they produce. A GATHER route trains its
resource's skill; a CRAFT route trains the item's crafting skill. Every other
route (withdraw, buy, drop, ...) trains none and keeps its price. Travel hops
are charged by the walk, not by a route, and always cost."""

from collections.abc import Mapping
from dataclasses import replace

from artifactsmmo_cli.ai.acquisition_cost_core import RouteOption
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.source_kind import SourceKind


def route_skill(item: str, route: RouteOption, game_data: GameData) -> str | None:
    """The skill one application of `route` (listed under `item`) trains, or None."""
    if route.kind == SourceKind.GATHER.value:
        requirement = game_data.resource_skill_level(route.venue)
        return requirement[0] if requirement is not None else None
    if route.kind == SourceKind.CRAFT.value:
        stats = game_data.item_stats(item)
        return stats.crafting_skill if stats is not None else None
    return None


def credit_demanded_skills(options: Mapping[str, list[RouteOption]], skills: frozenset[str],
                           game_data: GameData) -> dict[str, list[RouteOption]]:
    """`options` with every route that trains a skill in `skills` costing no actions."""
    return {item: [replace(route, actions_per_application=0)
                   if route_skill(item, route, game_data) in skills else route
                   for route in routes]
            for item, routes in options.items()}
