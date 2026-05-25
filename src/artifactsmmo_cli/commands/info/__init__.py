"""Information and lookup commands.

This package was split out of a single ``info.py`` module. The public surface
is preserved: ``app`` plus every command and helper that callers import from
``artifactsmmo_cli.commands.info`` remain importable from here, and the shared
dependencies below stay patchable at ``artifactsmmo_cli.commands.info.<name>``.

Submodules reference the shared dependencies and cross-domain helpers through
this package object (``from artifactsmmo_cli.commands import info as _pkg``)
so that test patches applied here affect the running command code.
"""

import typer
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.commands.info.achievements import list_achievements
from artifactsmmo_cli.commands.info.combat import (
    _calculate_difficulty_rating,
    _calculate_success_probability,
    _format_combat_analysis,
    _get_character_data,
    _get_monster_drops,
)
from artifactsmmo_cli.commands.info.events import list_events
from artifactsmmo_cli.commands.info.items import list_items
from artifactsmmo_cli.commands.info.leaderboard import show_leaderboard
from artifactsmmo_cli.commands.info.maps import map_info
from artifactsmmo_cli.commands.info.monsters import (
    _display_monster_details,
    get_monster,
    list_monsters,
)
from artifactsmmo_cli.commands.info.npcs import _classify_npc, get_npc, list_npcs
from artifactsmmo_cli.commands.info.resources import (
    _find_resource_locations,
    _get_resource_data,
    _get_resource_info_for_content,
    _matches_resource_criteria,
    find_nearest_resource,
    list_resources,
)
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.pathfinding import get_character_position

# Shared, patchable module-level object (kept here so the historical patch
# target ``artifactsmmo_cli.commands.info.console`` keeps resolving).
console = Console()

app = typer.Typer(help="Information and lookup commands")

app.command("items")(list_items)
app.command("monsters")(list_monsters)
app.command("monster")(get_monster)
app.command("resources")(list_resources)
app.command("achievements")(list_achievements)
app.command("leaderboard")(show_leaderboard)
app.command("events")(list_events)
app.command("map")(map_info)
app.command("npcs")(list_npcs)
app.command("npc")(get_npc)
app.command("nearest")(find_nearest_resource)

__all__ = [
    "app",
    "console",
    "ClientManager",
    "display_field",
    "format_error_message",
    "format_table",
    "handle_api_error",
    "handle_api_response",
    "get_character_position",
    "list_items",
    "list_monsters",
    "get_monster",
    "_display_monster_details",
    "list_resources",
    "find_nearest_resource",
    "list_achievements",
    "show_leaderboard",
    "list_events",
    "map_info",
    "list_npcs",
    "get_npc",
    "_classify_npc",
    "_find_resource_locations",
    "_get_resource_data",
    "_get_resource_info_for_content",
    "_matches_resource_criteria",
    "_get_character_data",
    "_calculate_difficulty_rating",
    "_calculate_success_probability",
    "_format_combat_analysis",
    "_get_monster_drops",
]
