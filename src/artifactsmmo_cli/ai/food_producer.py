"""Who makes the fleet's food (spec 2026-10-13 §4, USER "the fleet needs a
food maker role so that others can focus elsewhere").

A food's OWNER is the catalogue role that owns its crafting skill (`fisher`
owns cooking). The owner makes it; a sibling fetches what is banked or rests.
When no live character holds the owning role, anyone makes it — the fleet must
not starve while the role is unheld — and a food no role crafts (an apple
gathered off a tree) is anyone's."""

# Module import, attributes read at call time: `role_catalog` -> `tiers` ->
# `decisions.root` -> this module is an import cycle, and a `from ... import
# ROLE_CATALOG` here would read the partially initialised module.
from artifactsmmo_cli.ai import role_catalog as _role_catalog
from artifactsmmo_cli.ai.game_data import GameData


def food_owner(code: str, game_data: GameData) -> str | None:
    """The role owning `code`'s crafting skill, or None when no role crafts it."""
    stats = game_data.item_stats(code)
    skill = stats.crafting_skill if stats is not None else None
    if not skill:
        return None
    return next((role.name for role in _role_catalog.ROLE_CATALOG
                 if skill in _role_catalog.role_skills(role)), None)


def may_make_food(code: str, role: str | None, fleet_roles: frozenset[str],
                  game_data: GameData) -> bool:
    """Whether a character holding `role` makes `code`, given the roles any
    live character holds (`fleet_roles`, empty on a single-character run)."""
    owner = food_owner(code, game_data)
    return owner is None or role == owner or owner not in fleet_roles
