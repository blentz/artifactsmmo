"""Monster lookup commands."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.monsters import (
    get_all_monsters_monsters_get,
    get_monster_monsters_code_get,
)
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def list_monsters(
    monster_code: str = typer.Option(None, help="Specific monster code to lookup"),
    level: int = typer.Option(None, help="Filter by exact level (for backward compatibility)"),
    min_level: int = typer.Option(None, "--min-level", help="Filter by minimum level"),
    max_level: int = typer.Option(None, "--max-level", help="Filter by maximum level"),
    compare: str = typer.Option(None, "--compare", help="Character name to compare combat difficulty"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List or search monsters with optional combat assessment.

    Level filtering options:
    - Use --level for exact level match (backward compatibility)
    - Use --min-level and/or --max-level for range filtering
    - Cannot combine --level with --min-level or --max-level

    Combat assessment:
    - Use --compare CHARACTER to show difficulty ratings and success probabilities
    """
    try:
        # Validate parameter combinations
        if level is not None and (min_level is not None or max_level is not None):
            _pkg.console.print(format_error_message("Cannot combine --level with --min-level or --max-level"))
            raise typer.Exit(1)

        if min_level is not None and max_level is not None and min_level > max_level:
            _pkg.console.print(format_error_message("Minimum level cannot be greater than maximum level"))
            raise typer.Exit(1)

        # Determine API parameters
        api_min_level = None
        api_max_level = None

        if level is not None:
            # Exact level match (backward compatibility)
            api_min_level = level
            api_max_level = level
        else:
            # Range filtering
            api_min_level = min_level
            api_max_level = max_level

        # Get character data for comparison if specified
        character_data = None
        if compare:
            character_data = _pkg._get_character_data(compare)
            if not character_data:
                _pkg.console.print(format_error_message(f"Character '{compare}' not found"))
                raise typer.Exit(1)

        client = _pkg.ClientManager().client

        if monster_code:
            # Get specific monster
            response: Any = get_monster_monsters_code_get.sync(client=client, code=monster_code)
            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                monster = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", str(display_field(monster, "code"))],
                    ["Name", str(display_field(monster, "name"))],
                    ["Level", str(display_field(monster, "level"))],
                    ["HP", str(display_field(monster, "hp"))],
                    ["Attack Fire", str(display_field(monster, "attack_fire"))],
                    ["Attack Earth", str(display_field(monster, "attack_earth"))],
                    ["Attack Water", str(display_field(monster, "attack_water"))],
                    ["Attack Air", str(display_field(monster, "attack_air"))],
                    ["Res Fire", str(display_field(monster, "res_fire"))],
                    ["Res Earth", str(display_field(monster, "res_earth"))],
                    ["Res Water", str(display_field(monster, "res_water"))],
                    ["Res Air", str(display_field(monster, "res_air"))],
                ]

                # Add drops information
                drops = _pkg._get_monster_drops(monster)
                if drops:
                    rows.append(["Drops", ", ".join(drops)])
                else:
                    rows.append(["Drops", "None"])

                output = format_table(headers, rows, title=f"Monster: {monster_code}")
                _pkg.console.print(output)

                # Show combat analysis if character comparison requested
                if character_data:
                    monster_data = {
                        "level": getattr(monster, "level", 0),
                        "hp": getattr(monster, "hp", 0),
                        "attack_fire": getattr(monster, "attack_fire", 0),
                        "attack_earth": getattr(monster, "attack_earth", 0),
                        "attack_water": getattr(monster, "attack_water", 0),
                        "attack_air": getattr(monster, "attack_air", 0),
                    }

                    combat_rows = _pkg._format_combat_analysis(character_data, monster_data)
                    combat_output = format_table(
                        ["Property", "Value"],
                        combat_rows,
                        title=f"Combat Analysis: {character_data['name']} vs {display_field(monster, 'name')}",
                    )
                    _pkg.console.print()
                    _pkg.console.print(combat_output)
            else:
                _pkg.console.print(format_error_message(cli_response.error or f"Monster '{monster_code}' not found"))
        else:
            # List monsters
            response = get_all_monsters_monsters_get.sync(
                client=client, min_level=api_min_level, max_level=api_max_level, page=page, size=size
            )

            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                monsters = cli_response.data
                # Handle both old and new API response formats
                monsters_list = monsters.data if hasattr(monsters, "data") else monsters
                if monsters_list:
                    # Determine headers based on whether we're comparing
                    if character_data:
                        headers = [
                            "Code",
                            "Name",
                            "Level",
                            "HP",
                            "Difficulty",
                            "Success %",
                            "Fire",
                            "Earth",
                            "Water",
                            "Air",
                        ]
                    else:
                        headers = ["Code", "Name", "Level", "HP", "Fire", "Earth", "Water", "Air"]

                    rows = []
                    for monster in monsters_list:
                        row = [
                            str(display_field(monster, "code")),
                            str(display_field(monster, "name")),
                            str(display_field(monster, "level")),
                            str(display_field(monster, "hp")),
                        ]

                        # Add combat assessment columns if comparing
                        if character_data:
                            monster_data = {
                                "level": getattr(monster, "level", 0),
                                "hp": getattr(monster, "hp", 0),
                                "attack_fire": getattr(monster, "attack_fire", 0),
                                "attack_earth": getattr(monster, "attack_earth", 0),
                                "attack_water": getattr(monster, "attack_water", 0),
                                "attack_air": getattr(monster, "attack_air", 0),
                            }

                            difficulty = _pkg._calculate_difficulty_rating(
                                int(character_data["level"]), int(monster_data["level"])
                            )
                            success_prob = _pkg._calculate_success_probability(character_data, monster_data)

                            row.extend(
                                [
                                    f"{difficulty['emoji']} {difficulty['rating']}",
                                    f"{success_prob}%",
                                ]
                            )

                        # Add attack stats
                        row.extend(
                            [
                                str(display_field(monster, "attack_fire")),
                                str(display_field(monster, "attack_earth")),
                                str(display_field(monster, "attack_water")),
                                str(display_field(monster, "attack_air")),
                            ]
                        )

                        rows.append(row)

                    title = "Monsters"
                    if character_data:
                        title += f" (Combat Assessment for {character_data['name']})"

                    output = format_table(headers, rows, title=title)
                    _pkg.console.print(output)
                else:
                    _pkg.console.print(format_error_message("No monsters found"))
            else:
                _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve monsters"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def get_monster(
    name: str = typer.Argument(help="Monster name or code to lookup"),
    compare: str = typer.Option(None, "--compare", help="Character name to compare combat difficulty"),
) -> None:
    """Get detailed information about a specific monster with optional combat analysis."""
    try:
        # Get character data for comparison if specified
        character_data = None
        if compare:
            character_data = _pkg._get_character_data(compare)
            if not character_data:
                _pkg.console.print(format_error_message(f"Character '{compare}' not found"))
                raise typer.Exit(1)

        client = _pkg.ClientManager().client

        # Try to get monster by exact code first
        try:
            response: Any = get_monster_monsters_code_get.sync(client=client, code=name)
            cli_response = _pkg.handle_api_response(response)

            if cli_response.success and cli_response.data:
                monster = cli_response.data
                _display_monster_details(monster, character_data)
                return
        except (UnexpectedStatus, httpx.HTTPError):
            pass  # Try searching by name instead

        # If exact code lookup failed, search by name

        # Search through monsters to find name match
        found_monster = None
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages and not found_monster:
            response = get_all_monsters_monsters_get.sync(client=client, page=current_page, size=100)
            cli_response = _pkg.handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            monsters = cli_response.data
            if not hasattr(monsters, "data") or not monsters.data:
                break

            # Look for monster with matching name
            for monster in monsters.data:
                monster_name = getattr(monster, "name", "").lower()
                monster_code = getattr(monster, "code", "").lower()
                search_name = name.lower()

                if search_name in monster_name or search_name in monster_code:
                    found_monster = monster
                    break

            # Check if we have more pages
            if hasattr(monsters, "pages") and current_page >= monsters.pages:
                break
            current_page += 1

        if found_monster:
            _display_monster_details(found_monster, character_data)
        else:
            _pkg.console.print(format_error_message(f"Monster '{name}' not found"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def _display_monster_details(monster: Any, character_data: dict[str, str | int] | None = None) -> None:
    """Display detailed monster information with optional combat analysis.

    Args:
        monster: Monster object from API
        character_data: Optional character data for combat analysis
    """
    # Basic monster information
    headers = ["Property", "Value"]
    rows = [
        ["Code", str(display_field(monster, "code"))],
        ["Name", str(display_field(monster, "name"))],
        ["Level", str(display_field(monster, "level"))],
        ["HP", str(display_field(monster, "hp"))],
    ]

    # Attack stats
    rows.extend(
        [
            ["Attack Fire", str(display_field(monster, "attack_fire"))],
            ["Attack Earth", str(display_field(monster, "attack_earth"))],
            ["Attack Water", str(display_field(monster, "attack_water"))],
            ["Attack Air", str(display_field(monster, "attack_air"))],
        ]
    )

    # Resistance stats
    rows.extend(
        [
            ["Res Fire", str(display_field(monster, "res_fire"))],
            ["Res Earth", str(display_field(monster, "res_earth"))],
            ["Res Water", str(display_field(monster, "res_water"))],
            ["Res Air", str(display_field(monster, "res_air"))],
        ]
    )

    # Total attack power
    total_attack = (
        getattr(monster, "attack_fire", 0)
        + getattr(monster, "attack_earth", 0)
        + getattr(monster, "attack_water", 0)
        + getattr(monster, "attack_air", 0)
    )
    rows.append(["Total Attack", str(total_attack)])

    # Drops information
    drops = _pkg._get_monster_drops(monster)
    if drops:
        rows.append(["Drops", ", ".join(drops)])
    else:
        rows.append(["Drops", "None"])

    # Display basic monster info
    monster_name = display_field(monster, "name")
    output = format_table(headers, rows, title=f"Monster: {monster_name}")
    _pkg.console.print(output)

    # Show combat analysis if character comparison requested
    if character_data:
        monster_data = {
            "level": getattr(monster, "level", 0),
            "hp": getattr(monster, "hp", 0),
            "attack_fire": getattr(monster, "attack_fire", 0),
            "attack_earth": getattr(monster, "attack_earth", 0),
            "attack_water": getattr(monster, "attack_water", 0),
            "attack_air": getattr(monster, "attack_air", 0),
        }

        combat_rows = _pkg._format_combat_analysis(character_data, monster_data)
        combat_output = format_table(
            ["Property", "Value"], combat_rows, title=f"Combat Analysis: {character_data['name']} vs {monster_name}"
        )
        _pkg.console.print()
        _pkg.console.print(combat_output)
