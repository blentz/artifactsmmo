"""Information and lookup commands."""

import typer
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.formatters import (
    format_error_message,
    format_table,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.pathfinding import get_character_position

app = typer.Typer(help="Information and lookup commands")
console = Console()


@app.command("items")
def list_items(
    item_code: str = typer.Option(None, help="Specific item code to lookup"),
    item_type: str = typer.Option(None, help="Filter by item type"),
    craft_skill: str = typer.Option(None, help="Filter by crafting skill"),
    craft_level: int = typer.Option(None, help="Filter by minimum craft level"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List or search items."""
    try:
        client = ClientManager().client

        if item_code:
            # Import the API function
            from artifactsmmo_api_client.api.items import get_item_items_code_get

            # Get specific item
            response = get_item_items_code_get.sync(client=client, code=item_code)
            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                item = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", getattr(item, "code", "N/A")],
                    ["Name", getattr(item, "name", "N/A")],
                    ["Type", getattr(item, "type_", "N/A")],
                    ["Subtype", getattr(item, "subtype", "N/A")],
                    ["Level", str(getattr(item, "level", 0))],
                    ["Description", getattr(item, "description", "N/A")],
                ]

                # Add craft info if available
                if hasattr(item, "craft") and item.craft:
                    craft = item.craft
                    rows.extend(
                        [
                            ["Craft Skill", getattr(craft, "skill", "N/A")],
                            ["Craft Level", str(getattr(craft, "level", 0))],
                        ]
                    )

                output = format_table(headers, rows, title=f"Item: {item_code}")
                console.print(output)
            else:
                console.print(format_error_message(cli_response.error or f"Item '{item_code}' not found"))
        else:
            # Import the API function
            from artifactsmmo_api_client.api.items import get_all_items_items_get

            # List items - only pass non-None parameters to avoid API client bugs
            kwargs = {"client": client, "page": page, "size": size}
            if item_type is not None:
                kwargs["type_"] = item_type
            if craft_skill is not None:
                kwargs["craft_skill"] = craft_skill
            if craft_level is not None:
                kwargs["min_level"] = craft_level

            response = get_all_items_items_get.sync(**kwargs)

            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                items = cli_response.data
                # Handle both old and new API response formats
                items_list = items.data if hasattr(items, "data") else items
                if items_list:
                    headers = ["Code", "Name", "Type", "Level", "Description"]
                    rows = []
                    for item in items_list:
                        description = getattr(item, "description", "")
                        if len(description) > 50:
                            description = description[:47] + "..."

                        rows.append(
                            [
                                getattr(item, "code", "N/A"),
                                getattr(item, "name", "N/A"),
                                getattr(item, "type_", "N/A"),
                                str(getattr(item, "level", 0)),
                                description,
                            ]
                        )

                    output = format_table(headers, rows, title="Items")
                    console.print(output)
                else:
                    console.print(format_error_message("No items found"))
            else:
                console.print(format_error_message(cli_response.error or "Could not retrieve items"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("monsters")
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
            console.print(format_error_message("Cannot combine --level with --min-level or --max-level"))
            raise typer.Exit(1)

        if min_level is not None and max_level is not None and min_level > max_level:
            console.print(format_error_message("Minimum level cannot be greater than maximum level"))
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
            character_data = _get_character_data(compare)
            if not character_data:
                console.print(format_error_message(f"Character '{compare}' not found"))
                raise typer.Exit(1)

        client = ClientManager().client

        if monster_code:
            # Import the API function
            from artifactsmmo_api_client.api.monsters import get_monster_monsters_code_get

            # Get specific monster
            response = get_monster_monsters_code_get.sync(client=client, code=monster_code)
            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                monster = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", getattr(monster, "code", "N/A")],
                    ["Name", getattr(monster, "name", "N/A")],
                    ["Level", str(getattr(monster, "level", 0))],
                    ["HP", str(getattr(monster, "hp", 0))],
                    ["Attack Fire", str(getattr(monster, "attack_fire", 0))],
                    ["Attack Earth", str(getattr(monster, "attack_earth", 0))],
                    ["Attack Water", str(getattr(monster, "attack_water", 0))],
                    ["Attack Air", str(getattr(monster, "attack_air", 0))],
                    ["Res Fire", str(getattr(monster, "res_fire", 0))],
                    ["Res Earth", str(getattr(monster, "res_earth", 0))],
                    ["Res Water", str(getattr(monster, "res_water", 0))],
                    ["Res Air", str(getattr(monster, "res_air", 0))],
                ]

                # Add drops information
                drops = _get_monster_drops(monster)
                if drops:
                    rows.append(["Drops", ", ".join(drops)])
                else:
                    rows.append(["Drops", "None"])

                output = format_table(headers, rows, title=f"Monster: {monster_code}")
                console.print(output)

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

                    combat_rows = _format_combat_analysis(character_data, monster_data)
                    combat_output = format_table(
                        ["Property", "Value"],
                        combat_rows,
                        title=f"Combat Analysis: {character_data['name']} vs {getattr(monster, 'name', 'Monster')}",
                    )
                    console.print()
                    console.print(combat_output)
            else:
                console.print(format_error_message(cli_response.error or f"Monster '{monster_code}' not found"))
        else:
            # Import the API function
            from artifactsmmo_api_client.api.monsters import get_all_monsters_monsters_get

            # List monsters
            response = get_all_monsters_monsters_get.sync(
                client=client, min_level=api_min_level, max_level=api_max_level, page=page, size=size
            )

            cli_response = handle_api_response(response)
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
                            getattr(monster, "code", "N/A"),
                            getattr(monster, "name", "N/A"),
                            str(getattr(monster, "level", 0)),
                            str(getattr(monster, "hp", 0)),
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

                            difficulty = _calculate_difficulty_rating(
                                int(character_data["level"]), int(monster_data["level"])
                            )
                            success_prob = _calculate_success_probability(character_data, monster_data)

                            row.extend(
                                [
                                    f"{difficulty['emoji']} {difficulty['rating']}",
                                    f"{success_prob}%",
                                ]
                            )

                        # Add attack stats
                        row.extend(
                            [
                                str(getattr(monster, "attack_fire", 0)),
                                str(getattr(monster, "attack_earth", 0)),
                                str(getattr(monster, "attack_water", 0)),
                                str(getattr(monster, "attack_air", 0)),
                            ]
                        )

                        rows.append(row)

                    title = "Monsters"
                    if character_data:
                        title += f" (Combat Assessment for {character_data['name']})"

                    output = format_table(headers, rows, title=title)
                    console.print(output)
                else:
                    console.print(format_error_message("No monsters found"))
            else:
                console.print(format_error_message(cli_response.error or "Could not retrieve monsters"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("monster")
def get_monster(
    name: str = typer.Argument(help="Monster name or code to lookup"),
    compare: str = typer.Option(None, "--compare", help="Character name to compare combat difficulty"),
) -> None:
    """Get detailed information about a specific monster with optional combat analysis."""
    try:
        # Get character data for comparison if specified
        character_data = None
        if compare:
            character_data = _get_character_data(compare)
            if not character_data:
                console.print(format_error_message(f"Character '{compare}' not found"))
                raise typer.Exit(1)

        client = ClientManager().client

        # Try to get monster by exact code first
        from artifactsmmo_api_client.api.monsters import get_monster_monsters_code_get

        try:
            response = get_monster_monsters_code_get.sync(client=client, code=name)
            cli_response = handle_api_response(response)

            if cli_response.success and cli_response.data:
                monster = cli_response.data
                _display_monster_details(monster, character_data)
                return
        except Exception:
            pass  # Try searching by name instead

        # If exact code lookup failed, search by name
        from artifactsmmo_api_client.api.monsters import get_all_monsters_monsters_get

        # Search through monsters to find name match
        found_monster = None
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages and not found_monster:
            response = get_all_monsters_monsters_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

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
            console.print(format_error_message(f"Monster '{name}' not found"))
            raise typer.Exit(1)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def _display_monster_details(monster, character_data: dict[str, str | int] | None = None) -> None:
    """Display detailed monster information with optional combat analysis.

    Args:
        monster: Monster object from API
        character_data: Optional character data for combat analysis
    """
    # Basic monster information
    headers = ["Property", "Value"]
    rows = [
        ["Code", getattr(monster, "code", "N/A")],
        ["Name", getattr(monster, "name", "N/A")],
        ["Level", str(getattr(monster, "level", 0))],
        ["HP", str(getattr(monster, "hp", 0))],
    ]

    # Attack stats
    rows.extend(
        [
            ["Attack Fire", str(getattr(monster, "attack_fire", 0))],
            ["Attack Earth", str(getattr(monster, "attack_earth", 0))],
            ["Attack Water", str(getattr(monster, "attack_water", 0))],
            ["Attack Air", str(getattr(monster, "attack_air", 0))],
        ]
    )

    # Resistance stats
    rows.extend(
        [
            ["Res Fire", str(getattr(monster, "res_fire", 0))],
            ["Res Earth", str(getattr(monster, "res_earth", 0))],
            ["Res Water", str(getattr(monster, "res_water", 0))],
            ["Res Air", str(getattr(monster, "res_air", 0))],
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
    drops = _get_monster_drops(monster)
    if drops:
        rows.append(["Drops", ", ".join(drops)])
    else:
        rows.append(["Drops", "None"])

    # Display basic monster info
    monster_name = getattr(monster, "name", "Monster")
    output = format_table(headers, rows, title=f"Monster: {monster_name}")
    console.print(output)

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

        combat_rows = _format_combat_analysis(character_data, monster_data)
        combat_output = format_table(
            ["Property", "Value"], combat_rows, title=f"Combat Analysis: {character_data['name']} vs {monster_name}"
        )
        console.print()
        console.print(combat_output)


@app.command("resources")
def list_resources(
    resource_code: str = typer.Option(None, help="Specific resource code to lookup"),
    skill: str = typer.Option(None, help="Filter by skill"),
    level: int = typer.Option(None, help="Filter by minimum level"),
    max_level: int = typer.Option(None, "--max-level", help="Filter by maximum level"),
    resource_type: str = typer.Option(None, "--type", help="Filter by resource type (mining, woodcutting, fishing)"),
    location: str = typer.Option(None, "--location", help="Center location as 'X Y' coordinates"),
    radius: int = typer.Option(None, "--radius", help="Search radius from location (requires --location)"),
    character: str = typer.Option(None, help="Character name to calculate distances from"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List or search resources with optional location filtering."""
    try:
        # Validate parameter combinations
        if radius is not None and location is None:
            console.print(format_error_message("--radius requires --location to be specified"))
            raise typer.Exit(1)

        # Parse location if provided
        center_x, center_y = None, None
        if location:
            try:
                parts = location.strip().split()
                if len(parts) != 2:
                    raise ValueError("Location must be in format 'X Y'")
                center_x, center_y = int(parts[0]), int(parts[1])
            except ValueError:
                console.print(format_error_message("Invalid location format. Use 'X Y' coordinates"))
                raise typer.Exit(1)

        # Get character position if character specified
        char_x, char_y = None, None
        if character:
            try:
                char_x, char_y = get_character_position(character)
            except Exception as e:
                console.print(format_error_message(f"Could not get character position: {e}"))
                raise typer.Exit(1)

        client = ClientManager().client

        if resource_code:
            # Import the API function
            from artifactsmmo_api_client.api.resources import get_resource_resources_code_get

            # Get specific resource
            response = get_resource_resources_code_get.sync(client=client, code=resource_code)
            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                resource = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", getattr(resource, "code", "N/A")],
                    ["Name", getattr(resource, "name", "N/A")],
                    ["Skill", getattr(resource, "skill", "N/A")],
                    ["Level", str(getattr(resource, "level", 0))],
                ]

                # Add drops if available
                if hasattr(resource, "drops") and resource.drops:
                    drops = []
                    for drop in resource.drops:
                        drops.append(f"{getattr(drop, 'code', 'Unknown')} ({getattr(drop, 'rate', 0)}%)")
                    rows.append(["Drops", ", ".join(drops)])

                # Add location information if available
                if char_x is not None and char_y is not None:
                    try:
                        locations = _find_resource_locations(resource_code, character_x=char_x, character_y=char_y)
                        if locations:
                            nearest = min(locations, key=lambda r: r["distance"])
                            rows.append(
                                [
                                    "Nearest Location",
                                    f"({nearest['x']}, {nearest['y']}) - Distance: {nearest['distance']}",
                                ]
                            )
                    except Exception:
                        pass  # Don't fail if location lookup fails

                output = format_table(headers, rows, title=f"Resource: {resource_code}")
                console.print(output)
            else:
                console.print(format_error_message(cli_response.error or f"Resource '{resource_code}' not found"))
        else:
            # Import the API function
            from artifactsmmo_api_client.api.resources import get_all_resources_resources_get

            # Determine API parameters for level filtering
            api_min_level = level
            api_max_level = max_level

            # List resources - only pass non-None parameters to avoid API client bugs
            from artifactsmmo_api_client.models.gathering_skill import GatheringSkill
            from artifactsmmo_api_client.types import UNSET

            kwargs = {"client": client, "page": page, "size": size}

            # Convert skill string to GatheringSkill enum if provided
            if skill is not None:
                try:
                    skill_enum = GatheringSkill(skill.lower())
                    kwargs["skill"] = skill_enum
                except ValueError:
                    # Invalid skill, don't pass skill parameter
                    pass

            if api_min_level is not None:
                kwargs["min_level"] = api_min_level
            if api_max_level is not None:
                kwargs["max_level"] = api_max_level

            response = get_all_resources_resources_get.sync(**kwargs)

            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                resources = cli_response.data
                # Handle both old and new API response formats
                resources_list = resources.data if hasattr(resources, "data") else resources
                if resources_list:
                    # Filter by resource type if specified
                    filtered_resources = []
                    for resource in resources_list:
                        resource_skill = getattr(resource, "skill", "").lower()

                        # Apply type filter
                        if resource_type and resource_type.lower() != resource_skill:
                            continue

                        filtered_resources.append(resource)

                    # Get location information if needed
                    resource_locations = {}
                    if char_x is not None and char_y is not None or center_x is not None:
                        try:
                            for resource in filtered_resources:
                                resource_code_val = getattr(resource, "code", "")
                                if resource_code_val:
                                    locations = _find_resource_locations(
                                        resource_code_val, character_x=char_x, character_y=char_y
                                    )

                                    # Filter by location/radius if specified
                                    if center_x is not None and center_y is not None:
                                        if radius is not None:
                                            locations = [
                                                loc
                                                for loc in locations
                                                if abs(loc["x"] - center_x) + abs(loc["y"] - center_y) <= radius
                                            ]
                                        else:
                                            # Just sort by distance from center
                                            for loc in locations:
                                                loc["center_distance"] = abs(loc["x"] - center_x) + abs(
                                                    loc["y"] - center_y
                                                )
                                            locations.sort(key=lambda r: r["center_distance"])

                                    if locations:
                                        resource_locations[resource_code_val] = locations
                        except Exception:
                            pass  # Don't fail if location lookup fails

                    # Filter resources that have locations if location filtering is active
                    if center_x is not None and center_y is not None:
                        filtered_resources = [
                            resource
                            for resource in filtered_resources
                            if getattr(resource, "code", "") in resource_locations
                        ]

                    if filtered_resources:
                        # Determine headers based on available information
                        if char_x is not None and char_y is not None:
                            headers = ["Code", "Name", "Skill", "Level", "Nearest Location", "Distance", "Drops"]
                        elif center_x is not None and center_y is not None:
                            headers = ["Code", "Name", "Skill", "Level", "Nearest Location", "Drops"]
                        else:
                            headers = ["Code", "Name", "Skill", "Level", "Drops"]

                        rows = []
                        for resource in filtered_resources:
                            resource_code_val = getattr(resource, "code", "N/A")
                            drops = []
                            if hasattr(resource, "drops") and resource.drops:
                                for drop in resource.drops[:3]:  # Show first 3 drops
                                    drops.append(getattr(drop, "code", "Unknown"))

                            row = [
                                resource_code_val,
                                getattr(resource, "name", "N/A"),
                                getattr(resource, "skill", "N/A"),
                                str(getattr(resource, "level", 0)),
                            ]

                            # Add location information if available
                            if resource_code_val in resource_locations:
                                nearest = resource_locations[resource_code_val][0]
                                row.append(f"({nearest['x']}, {nearest['y']})")

                                if char_x is not None and char_y is not None:
                                    row.append(str(nearest["distance"]))

                            elif char_x is not None and char_y is not None:
                                row.extend(["Not found", "N/A"])
                            elif center_x is not None and center_y is not None:
                                row.append("Not found")

                            row.append(", ".join(drops) if drops else "None")
                            rows.append(row)

                        title = "Resources"
                        if resource_type:
                            title += f" (Type: {resource_type})"
                        if character:
                            title += f" (Near {character})"
                        elif center_x is not None and center_y is not None:
                            title += f" (Near {center_x}, {center_y}"
                            if radius is not None:
                                title += f" within {radius})"
                            else:
                                title += ")"

                        output = format_table(headers, rows, title=title)
                        console.print(output)
                    else:
                        console.print(format_error_message("No resources found matching criteria"))
                else:
                    console.print(format_error_message("No resources found"))
            else:
                console.print(format_error_message(cli_response.error or "Could not retrieve resources"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("achievements")
def list_achievements(
    achievement_code: str = typer.Option(None, help="Specific achievement code to lookup"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List or search achievements (badges)."""
    try:
        client = ClientManager().client

        if achievement_code:
            # Import the API function
            from artifactsmmo_api_client.api.badges import get_badge_badges_code_get

            # Get specific achievement
            response = get_badge_badges_code_get.sync(client=client, code=achievement_code)
            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                badge = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", getattr(badge, "code", "N/A")],
                    ["Name", getattr(badge, "name", "N/A")],
                    ["Description", getattr(badge, "description", "N/A")],
                ]

                output = format_table(headers, rows, title=f"Achievement: {achievement_code}")
                console.print(output)
            else:
                console.print(format_error_message(cli_response.error or f"Achievement '{achievement_code}' not found"))
        else:
            # Import the API function
            from artifactsmmo_api_client.api.badges import get_all_badges_badges_get

            # List achievements
            response = get_all_badges_badges_get.sync(client=client, page=page, size=size)

            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                badges = cli_response.data
                if hasattr(badges, "data") and badges.data:
                    headers = ["Code", "Name", "Description"]
                    rows = []
                    for badge in badges.data:
                        description = getattr(badge, "description", "")
                        if len(description) > 60:
                            description = description[:57] + "..."

                        rows.append([getattr(badge, "code", "N/A"), getattr(badge, "name", "N/A"), description])

                    output = format_table(headers, rows, title="Achievements")
                    console.print(output)
                else:
                    console.print(format_error_message("No achievements found"))
            else:
                console.print(format_error_message(cli_response.error or "Could not retrieve achievements"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("leaderboard")
def show_leaderboard(
    board_type: str = typer.Argument("characters", help="Leaderboard type: 'characters' or 'accounts'"),
    sort: str = typer.Option("level", help="Sort by: level, xp, gold, etc."),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """Display leaderboards."""
    try:
        client = ClientManager().client

        if board_type.lower() == "characters":
            # Import the API function
            from artifactsmmo_api_client.api.leaderboard import get_characters_leaderboard_leaderboard_characters_get

            response = get_characters_leaderboard_leaderboard_characters_get.sync(
                client=client, sort=sort, page=page, size=size
            )
        elif board_type.lower() == "accounts":
            # Import the API function
            from artifactsmmo_api_client.api.leaderboard import get_accounts_leaderboard_leaderboard_accounts_get

            response = get_accounts_leaderboard_leaderboard_accounts_get.sync(
                client=client, sort=sort, page=page, size=size
            )
        else:
            console.print(format_error_message("Invalid leaderboard type. Use 'characters' or 'accounts'"))
            raise typer.Exit(1)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            leaderboard = cli_response.data
            if hasattr(leaderboard, "data") and leaderboard.data:
                if board_type.lower() == "characters":
                    headers = ["Rank", "Name", "Level", "XP", "Gold"]
                    rows = []
                    for i, entry in enumerate(leaderboard.data, 1):
                        rows.append(
                            [
                                str(i + (page - 1) * size),
                                getattr(entry, "name", "N/A"),
                                str(getattr(entry, "level", 0)),
                                str(getattr(entry, "xp", 0)),
                                str(getattr(entry, "gold", 0)),
                            ]
                        )
                else:  # accounts
                    headers = ["Rank", "Username", "Characters", "Achievements"]
                    rows = []
                    for i, entry in enumerate(leaderboard.data, 1):
                        rows.append(
                            [
                                str(i + (page - 1) * size),
                                getattr(entry, "username", "N/A"),
                                str(getattr(entry, "characters_count", 0)),
                                str(getattr(entry, "achievements_points", 0)),
                            ]
                        )

                output = format_table(headers, rows, title=f"{board_type.title()} Leaderboard")
                console.print(output)
            else:
                console.print(format_error_message("No leaderboard data found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve leaderboard"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("events")
def list_events(
    active_only: bool = typer.Option(True, help="Show only active events"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List game events."""
    try:
        client = ClientManager().client

        if active_only:
            # Import the API function
            from artifactsmmo_api_client.api.events import get_all_active_events_events_active_get

            response = get_all_active_events_events_active_get.sync(client=client, page=page, size=size)
        else:
            # Import the API function
            from artifactsmmo_api_client.api.events import get_all_events_events_get

            response = get_all_events_events_get.sync(client=client, page=page, size=size)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            events = cli_response.data
            if hasattr(events, "data") and events.data:
                headers = ["Name", "Map", "Duration", "Rate", "Expiration"]
                rows = []
                for event in events.data:
                    rows.append(
                        [
                            getattr(event, "name", "N/A"),
                            getattr(event, "map", {}).get("name", "N/A") if hasattr(event, "map") else "N/A",
                            str(getattr(event, "duration", 0)),
                            str(getattr(event, "rate", 0)),
                            getattr(event, "expiration", "N/A"),
                        ]
                    )

                title = "Active Events" if active_only else "All Events"
                output = format_table(headers, rows, title=title)
                console.print(output)
            else:
                console.print(format_error_message("No events found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve events"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("map")
def map_info(
    x: int = typer.Option(None, help="X coordinate"),
    y: int = typer.Option(None, help="Y coordinate"),
    content_code: str = typer.Option(None, help="Content code to search for"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """Get map information for locations."""
    try:
        client = ClientManager().client

        if x is not None and y is not None:
            # Import the API function for specific coordinates
            from artifactsmmo_api_client.api.maps import get_map_maps_x_y_get

            # Get specific map location
            response = get_map_maps_x_y_get.sync(client=client, x=x, y=y)
            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                map_data = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Coordinates", f"({getattr(map_data, 'x', 'N/A')}, {getattr(map_data, 'y', 'N/A')})"],
                    ["Name", getattr(map_data, "name", "N/A")],
                    ["Skin", getattr(map_data, "skin", "N/A")],
                ]

                # Add content info if available
                if hasattr(map_data, "content") and map_data.content:
                    content = map_data.content
                    rows.extend(
                        [
                            ["Content Type", getattr(content, "type", "N/A")],
                            ["Content Code", getattr(content, "code", "N/A")],
                        ]
                    )

                output = format_table(headers, rows, title=f"Map Location ({x}, {y})")
                console.print(output)
            else:
                console.print(format_error_message(cli_response.error or f"Map location ({x}, {y}) not found"))
        else:
            # Import the API function for searching maps
            from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

            # List maps with optional filtering
            response = get_all_maps_maps_get.sync(client=client, content_code=content_code, page=page, size=size)

            cli_response = handle_api_response(response)
            if cli_response.success and cli_response.data:
                maps = cli_response.data
                if hasattr(maps, "data") and maps.data:
                    headers = ["Coordinates", "Name", "Skin", "Content Type", "Content Code"]
                    rows = []
                    for map_item in maps.data:
                        content_type = ""
                        content_code_val = ""
                        if hasattr(map_item, "content") and map_item.content:
                            content_type = getattr(map_item.content, "type", "")
                            content_code_val = getattr(map_item.content, "code", "")

                        rows.append(
                            [
                                f"({getattr(map_item, 'x', 'N/A')}, {getattr(map_item, 'y', 'N/A')})",
                                getattr(map_item, "name", "N/A"),
                                getattr(map_item, "skin", "N/A"),
                                content_type,
                                content_code_val,
                            ]
                        )

                    title = "Map Locations"
                    if content_code:
                        title += f" (Content: {content_code})"
                    output = format_table(headers, rows, title=title)
                    console.print(output)
                else:
                    console.print(format_error_message("No map locations found"))
            else:
                console.print(format_error_message(cli_response.error or "Could not retrieve map information"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("npcs")
def list_npcs(
    npc_type: str = typer.Option(None, help="Filter by NPC type (task_master, bank, grand_exchange, workshop)"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List all NPCs and their locations."""
    try:
        client = ClientManager().client

        # Import the API function for searching maps
        from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

        # Search through map data to find NPCs
        all_npcs = []
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            maps = cli_response.data
            if not hasattr(maps, "data") or not maps.data:
                break

            # Look for NPCs in this page
            for map_item in maps.data:
                if hasattr(map_item, "content") and map_item.content:
                    content = map_item.content
                    content_type = getattr(content, "type", "")
                    content_code = getattr(content, "code", "")

                    # Determine if this is an NPC location
                    npc_info = _classify_npc(content_type, content_code)
                    if npc_info:
                        # Apply type filter if specified
                        if npc_type and npc_type.lower() not in npc_info["type"].lower():
                            continue

                        all_npcs.append(
                            {
                                "name": npc_info["name"],
                                "type": npc_info["type"],
                                "x": getattr(map_item, "x", "N/A"),
                                "y": getattr(map_item, "y", "N/A"),
                                "services": npc_info["services"],
                                "content_code": content_code,
                            }
                        )

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if all_npcs:
            # Sort NPCs by name for consistent output
            all_npcs.sort(key=lambda x: x["name"])

            # Apply pagination to results
            start_idx = (page - 1) * size
            end_idx = start_idx + size
            paginated_npcs = all_npcs[start_idx:end_idx]

            if paginated_npcs:
                headers = ["Name", "Type", "Location (X,Y)", "Services"]
                rows = []
                for npc in paginated_npcs:
                    services_str = ", ".join(npc["services"][:2])  # Show first 2 services
                    if len(npc["services"]) > 2:
                        services_str += "..."

                    rows.append(
                        [
                            npc["name"],
                            npc["type"],
                            f"({npc['x']}, {npc['y']})",
                            services_str,
                        ]
                    )

                title = "NPCs"
                if npc_type:
                    title += f" (Type: {npc_type})"
                title += f" - Page {page} of {(len(all_npcs) + size - 1) // size}"

                output = format_table(headers, rows, title=title)
                console.print(output)
            else:
                console.print(format_error_message(f"No NPCs found on page {page}"))
        else:
            # Fallback: show known NPC locations if no content data is available
            console.print("[yellow]Warning: No NPC content data found in map API. Showing known locations:[/yellow]")
            _show_fallback_npcs(npc_type, page, size)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("npc")
def get_npc(
    name: str = typer.Argument(help="NPC name to search for"),
) -> None:
    """Get specific NPC details by name."""
    try:
        client = ClientManager().client

        # Import the API function for searching maps
        from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

        # Search through map data to find the specific NPC
        found_npc = None
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages and not found_npc:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = handle_api_response(response)

            if not cli_response.success or not cli_response.data:
                break

            maps = cli_response.data
            if not hasattr(maps, "data") or not maps.data:
                break

            # Look for the specific NPC in this page
            for map_item in maps.data:
                if hasattr(map_item, "content") and map_item.content:
                    content = map_item.content
                    content_type = getattr(content, "type", "")
                    content_code = getattr(content, "code", "")

                    # Determine if this is an NPC location
                    npc_info = _classify_npc(content_type, content_code)
                    if npc_info and name.lower() in npc_info["name"].lower():
                        found_npc = {
                            "name": npc_info["name"],
                            "type": npc_info["type"],
                            "x": getattr(map_item, "x", "N/A"),
                            "y": getattr(map_item, "y", "N/A"),
                            "services": npc_info["services"],
                            "content_code": content_code,
                            "content_type": content_type,
                            "location_name": getattr(map_item, "name", "N/A"),
                        }
                        break

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if found_npc:
            headers = ["Property", "Value"]
            rows = [
                ["Name", found_npc["name"]],
                ["Type", found_npc["type"]],
                ["Location", f"({found_npc['x']}, {found_npc['y']})"],
                ["Area", found_npc["location_name"]],
                ["Content Type", found_npc["content_type"]],
                ["Content Code", found_npc["content_code"]],
                ["Services", ", ".join(found_npc["services"])],
            ]

            output = format_table(headers, rows, title=f"NPC: {found_npc['name']}")
            console.print(output)
        else:
            # Fallback: check known NPC locations
            fallback_npc = _get_fallback_npc(name)
            if fallback_npc:
                headers = ["Property", "Value"]
                rows = [
                    ["Name", fallback_npc["name"]],
                    ["Type", fallback_npc["type"]],
                    ["Location", f"({fallback_npc['x']}, {fallback_npc['y']})"],
                    ["Services", ", ".join(fallback_npc["services"])],
                    ["Note", "Location from known coordinates (API content data not available)"],
                ]

                output = format_table(headers, rows, title=f"NPC: {fallback_npc['name']}")
                console.print(output)
            else:
                console.print(format_error_message(f"NPC '{name}' not found"))

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def _classify_npc(content_type: str, content_code: str) -> dict[str, str | list[str]] | None:
    """Classify content as NPC and return NPC information."""
    if not content_type:
        return None

    content_type_lower = content_type.lower()
    content_code_lower = content_code.lower()

    # Task Master
    if "task" in content_type_lower:
        return {
            "name": "Task Master",
            "type": "task_master",
            "services": ["Task Assignment", "Task Completion", "Quest Management"],
        }

    # Bank
    if "bank" in content_type_lower:
        return {"name": "Bank", "type": "bank", "services": ["Item Storage", "Gold Storage", "Inventory Management"]}

    # Grand Exchange
    if "exchange" in content_type_lower or "market" in content_type_lower:
        return {
            "name": "Grand Exchange",
            "type": "grand_exchange",
            "services": ["Item Trading", "Market Access", "Price Discovery"],
        }

    # Workshops
    if "workshop" in content_type_lower or "craft" in content_type_lower:
        if "weapon" in content_code_lower:
            return {
                "name": "Weaponcrafting Workshop",
                "type": "workshop",
                "services": ["Weapon Crafting", "Weapon Upgrades"],
            }
        elif "gear" in content_code_lower or "armor" in content_code_lower:
            return {
                "name": "Gearcrafting Workshop",
                "type": "workshop",
                "services": ["Gear Crafting", "Armor Creation"],
            }
        elif "cooking" in content_code_lower or "food" in content_code_lower:
            return {"name": "Cooking Workshop", "type": "workshop", "services": ["Food Preparation", "Cooking"]}
        else:
            return {
                "name": f"{content_code.title()} Workshop",
                "type": "workshop",
                "services": ["Crafting", "Item Creation"],
            }

    return None


def _show_fallback_npcs(npc_type: str | None, page: int, size: int) -> None:
    """Show known NPC locations as fallback when API content data is not available."""
    known_npcs = [
        {
            "name": "Task Master",
            "type": "task_master",
            "x": 1,
            "y": 2,
            "services": ["Task Assignment", "Task Completion"],
        },
        {
            "name": "Task Master",
            "type": "task_master",
            "x": 5,
            "y": 1,
            "services": ["Task Assignment", "Task Completion"],
        },
        {"name": "Bank", "type": "bank", "x": 4, "y": 1, "services": ["Item Storage", "Gold Storage"]},
        {
            "name": "Grand Exchange",
            "type": "grand_exchange",
            "x": 5,
            "y": 1,
            "services": ["Item Trading", "Market Access"],
        },
        {
            "name": "Grand Exchange",
            "type": "grand_exchange",
            "x": 5,
            "y": 5,
            "services": ["Item Trading", "Market Access"],
        },
        {"name": "Weaponcrafting Workshop", "type": "workshop", "x": 1, "y": 3, "services": ["Weapon Crafting"]},
        {"name": "Gearcrafting Workshop", "type": "workshop", "x": 3, "y": 1, "services": ["Gear Crafting"]},
        {"name": "Cooking Workshop", "type": "workshop", "x": 1, "y": 5, "services": ["Food Preparation"]},
    ]

    # Apply type filter if specified
    if npc_type:
        known_npcs = [npc for npc in known_npcs if npc_type.lower() in npc["type"].lower()]

    # Apply pagination
    start_idx = (page - 1) * size
    end_idx = start_idx + size
    paginated_npcs = known_npcs[start_idx:end_idx]

    if paginated_npcs:
        headers = ["Name", "Type", "Location (X,Y)", "Services"]
        rows = []
        for npc in paginated_npcs:
            services_str = ", ".join(npc["services"][:2])
            if len(npc["services"]) > 2:
                services_str += "..."

            rows.append(
                [
                    npc["name"],
                    npc["type"],
                    f"({npc['x']}, {npc['y']})",
                    services_str,
                ]
            )

        title = "Known NPCs (Fallback Data)"
        if npc_type:
            title += f" (Type: {npc_type})"
        title += f" - Page {page} of {(len(known_npcs) + size - 1) // size}"

        output = format_table(headers, rows, title=title)
        console.print(output)
    else:
        console.print(format_error_message(f"No NPCs found on page {page}"))


def _get_fallback_npc(name: str) -> dict[str, str | int | list[str]] | None:
    """Get specific NPC from known locations as fallback."""
    known_npcs = [
        {
            "name": "Task Master",
            "type": "task_master",
            "x": 1,
            "y": 2,
            "services": ["Task Assignment", "Task Completion", "Quest Management"],
        },
        {
            "name": "Task Master",
            "type": "task_master",
            "x": 5,
            "y": 1,
            "services": ["Task Assignment", "Task Completion", "Quest Management"],
        },
        {
            "name": "Bank",
            "type": "bank",
            "x": 4,
            "y": 1,
            "services": ["Item Storage", "Gold Storage", "Inventory Management"],
        },
        {
            "name": "Grand Exchange",
            "type": "grand_exchange",
            "x": 5,
            "y": 1,
            "services": ["Item Trading", "Market Access", "Price Discovery"],
        },
        {
            "name": "Grand Exchange",
            "type": "grand_exchange",
            "x": 5,
            "y": 5,
            "services": ["Item Trading", "Market Access", "Price Discovery"],
        },
        {
            "name": "Weaponcrafting Workshop",
            "type": "workshop",
            "x": 1,
            "y": 3,
            "services": ["Weapon Crafting", "Weapon Upgrades"],
        },
        {
            "name": "Gearcrafting Workshop",
            "type": "workshop",
            "x": 3,
            "y": 1,
            "services": ["Gear Crafting", "Armor Creation"],
        },
        {"name": "Cooking Workshop", "type": "workshop", "x": 1, "y": 5, "services": ["Food Preparation", "Cooking"]},
    ]

    for npc in known_npcs:
        if name.lower() in npc["name"].lower():
            return npc

    return None


@app.command("nearest")
def find_nearest_resource(
    resource_name: str = typer.Argument(help="Resource name or type to find"),
    character: str = typer.Option(None, help="Character name to calculate distance from"),
    resource_type: str = typer.Option(None, "--type", help="Filter by resource type (mining, woodcutting, fishing)"),
    max_distance: int = typer.Option(None, "--max-distance", help="Maximum distance to search"),
    limit: int = typer.Option(5, help="Maximum number of results to show"),
) -> None:
    """Find nearest resources of a specific type."""
    try:
        # Get character position if character specified
        char_x, char_y = None, None
        if character:
            try:
                char_x, char_y = get_character_position(character)
            except Exception as e:
                console.print(format_error_message(f"Could not get character position: {e}"))
                raise typer.Exit(1)

        # Find resource locations
        resource_locations = _find_resource_locations(
            resource_name=resource_name,
            resource_type=resource_type,
            character_x=char_x,
            character_y=char_y,
            max_distance=max_distance,
        )

        if not resource_locations:
            console.print(format_error_message(f"No resources found matching '{resource_name}'"))
            raise typer.Exit(1)

        # Sort by distance if character position is available
        if char_x is not None and char_y is not None:
            resource_locations.sort(key=lambda r: r["distance"])

        # Limit results
        resource_locations = resource_locations[:limit]

        # Format output
        if char_x is not None and char_y is not None:
            headers = ["Resource", "Type", "Location", "Distance", "Level", "Skill"]
            rows = []
            for resource in resource_locations:
                rows.append(
                    [
                        resource["name"],
                        resource["type"],
                        f"({resource['x']}, {resource['y']})",
                        str(resource["distance"]),
                        str(resource["level"]),
                        resource["skill"],
                    ]
                )
            title = f"Nearest {resource_name.title()} Resources"
            if character:
                title += f" (from {character})"
        else:
            headers = ["Resource", "Type", "Location", "Level", "Skill"]
            rows = []
            for resource in resource_locations:
                rows.append(
                    [
                        resource["name"],
                        resource["type"],
                        f"({resource['x']}, {resource['y']})",
                        str(resource["level"]),
                        resource["skill"],
                    ]
                )
            title = f"{resource_name.title()} Resource Locations"

        output = format_table(headers, rows, title=title)
        console.print(output)

    except Exception as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def _find_resource_locations(
    resource_name: str,
    resource_type: str | None = None,
    character_x: int | None = None,
    character_y: int | None = None,
    max_distance: int | None = None,
) -> list[dict[str, str | int]]:
    """Find resource locations on the map.

    Args:
        resource_name: Name of resource to find
        resource_type: Optional resource type filter
        character_x: Character X position for distance calculation
        character_y: Character Y position for distance calculation
        max_distance: Maximum distance to search

    Returns:
        List of resource location dictionaries
    """
    client = ClientManager().client

    # First, get resource data to understand what we're looking for
    resource_data = _get_resource_data(resource_name, resource_type)

    # Search map for resource locations
    from artifactsmmo_api_client.api.maps import get_all_maps_maps_get

    resource_locations = []
    current_page = 1
    max_pages = 20  # Limit search to prevent infinite loops

    while current_page <= max_pages:
        response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
        cli_response = handle_api_response(response)

        if not cli_response.success or not cli_response.data:
            break

        maps = cli_response.data
        if not hasattr(maps, "data") or not maps.data:
            break

        # Look for resources in this page
        for map_item in maps.data:
            if hasattr(map_item, "content") and map_item.content:
                content = map_item.content
                content_code = getattr(content, "code", "").lower()
                content_type = getattr(content, "type", "").lower()

                # Check if this matches our search criteria
                if _matches_resource_criteria(content_code, content_type, resource_name, resource_type, resource_data):
                    x = getattr(map_item, "x", None)
                    y = getattr(map_item, "y", None)

                    if x is not None and y is not None:
                        x, y = int(x), int(y)

                        # Calculate distance if character position provided
                        distance = None
                        if character_x is not None and character_y is not None:
                            distance = abs(x - character_x) + abs(y - character_y)

                            # Skip if beyond max distance
                            if max_distance is not None and distance > max_distance:
                                continue

                        # Find matching resource data
                        resource_info = _get_resource_info_for_content(content_code, resource_data)

                        resource_locations.append(
                            {
                                "name": resource_info["name"],
                                "type": content_type,
                                "x": x,
                                "y": y,
                                "distance": distance or 0,
                                "level": resource_info["level"],
                                "skill": resource_info["skill"],
                                "content_code": content_code,
                            }
                        )

        # Check if we have more pages
        if hasattr(maps, "pages") and current_page >= maps.pages:
            break
        current_page += 1

    return resource_locations


def _get_resource_data(resource_name: str, resource_type: str | None = None) -> list[dict[str, str | int]]:
    """Get resource data from the API.

    Args:
        resource_name: Name of resource to find
        resource_type: Optional resource type filter

    Returns:
        List of resource data dictionaries
    """
    client = ClientManager().client
    from artifactsmmo_api_client.api.resources import get_all_resources_resources_get
    from artifactsmmo_api_client.models.gathering_skill import GatheringSkill
    from artifactsmmo_api_client.types import UNSET

    resources = []
    current_page = 1
    max_pages = 10

    # Convert string resource_type to GatheringSkill enum if provided
    skill_enum = UNSET
    if resource_type:
        try:
            skill_enum = GatheringSkill(resource_type.lower())
        except ValueError:
            # Invalid skill type, continue without filter
            skill_enum = UNSET

    while current_page <= max_pages:
        response = get_all_resources_resources_get.sync(client=client, skill=skill_enum, page=current_page, size=100)

        cli_response = handle_api_response(response)
        if not cli_response.success or not cli_response.data:
            break

        resource_list = cli_response.data
        if not hasattr(resource_list, "data") or not resource_list.data:
            break

        for resource in resource_list.data:
            resource_code = getattr(resource, "code", "").lower()
            resource_skill = getattr(resource, "skill", "").lower()

            # Check if this resource matches our search
            if (
                resource_name.lower() in resource_code
                or resource_name.lower() in getattr(resource, "name", "").lower()
                or (resource_type and resource_type.lower() == resource_skill)
            ):
                resources.append(
                    {
                        "code": getattr(resource, "code", ""),
                        "name": getattr(resource, "name", ""),
                        "skill": getattr(resource, "skill", ""),
                        "level": getattr(resource, "level", 0),
                    }
                )

        # Check if we have more pages
        if hasattr(resource_list, "pages") and current_page >= resource_list.pages:
            break
        current_page += 1

    return resources


def _matches_resource_criteria(
    content_code: str,
    content_type: str,
    resource_name: str,
    resource_type: str | None,
    resource_data: list[dict[str, str | int]],
) -> bool:
    """Check if map content matches resource search criteria.

    Args:
        content_code: Content code from map
        content_type: Content type from map
        resource_name: Resource name being searched
        resource_type: Optional resource type filter
        resource_data: List of resource data from API

    Returns:
        True if content matches criteria
    """
    # Check if content_code matches any known resource
    for resource in resource_data:
        if resource["code"].lower() == content_code:
            return True

    # Check for general resource type matching
    if "resource" in content_type:
        # Check if resource name appears in content code
        if resource_name.lower() in content_code:
            return True

        # Check for type-based matching
        if resource_type:
            type_keywords = {
                "mining": ["ore", "rock", "stone", "coal", "iron", "copper", "gold"],
                "woodcutting": ["tree", "wood", "log", "ash", "birch", "dead"],
                "fishing": ["fish", "gudgeon", "shrimp", "trout", "bass"],
            }

            if resource_type.lower() in type_keywords:
                for keyword in type_keywords[resource_type.lower()]:
                    if keyword in content_code:
                        return True

    return False


def _get_resource_info_for_content(
    content_code: str, resource_data: list[dict[str, str | int]]
) -> dict[str, str | int]:
    """Get resource info for a specific content code.

    Args:
        content_code: Content code from map
        resource_data: List of resource data from API

    Returns:
        Resource info dictionary
    """
    # Find exact match first
    for resource in resource_data:
        if resource["code"].lower() == content_code:
            return resource

    # If no exact match, create a default entry
    return {
        "name": content_code.replace("_", " ").title(),
        "skill": "Unknown",
        "level": 0,
    }


# Combat Assessment Helper Functions


def _get_character_data(character_name: str) -> dict[str, str | int] | None:
    """Get character data for combat assessment.

    Args:
        character_name: Name of the character to fetch

    Returns:
        Character data dictionary or None if not found
    """
    try:
        from artifactsmmo_api_client.api.characters import get_character_characters_name_get

        client = ClientManager().client
        response = get_character_characters_name_get.sync(client=client, name=character_name)
        cli_response = handle_api_response(response)

        if cli_response.success and cli_response.data:
            character = cli_response.data
            return {
                "name": getattr(character, "name", ""),
                "level": getattr(character, "level", 0),
                "hp": getattr(character, "hp", 0),
                "max_hp": getattr(character, "max_hp", 0),
                "attack_fire": getattr(character, "attack_fire", 0),
                "attack_earth": getattr(character, "attack_earth", 0),
                "attack_water": getattr(character, "attack_water", 0),
                "attack_air": getattr(character, "attack_air", 0),
                "res_fire": getattr(character, "res_fire", 0),
                "res_earth": getattr(character, "res_earth", 0),
                "res_water": getattr(character, "res_water", 0),
                "res_air": getattr(character, "res_air", 0),
                "dmg": getattr(character, "dmg", 0),
                "dmg_fire": getattr(character, "dmg_fire", 0),
                "dmg_earth": getattr(character, "dmg_earth", 0),
                "dmg_water": getattr(character, "dmg_water", 0),
                "dmg_air": getattr(character, "dmg_air", 0),
            }
    except Exception:
        pass

    return None


def _calculate_difficulty_rating(char_level: int, monster_level: int) -> dict[str, str]:
    """Calculate difficulty rating based on level difference.

    Args:
        char_level: Character level
        monster_level: Monster level

    Returns:
        Dictionary with difficulty info (rating, color, emoji)
    """
    level_diff = monster_level - char_level

    if level_diff <= -2:
        return {"rating": "Easy", "color": "green", "emoji": "🟢"}
    elif -1 <= level_diff <= 1:
        return {"rating": "Medium", "color": "yellow", "emoji": "🟡"}
    elif 2 <= level_diff <= 3:
        return {"rating": "Hard", "color": "red", "emoji": "🟠"}
    else:  # level_diff >= 4
        return {"rating": "Deadly", "color": "bright_red", "emoji": "🔴"}


def _calculate_success_probability(character: dict[str, str | int], monster: dict[str, str | int]) -> int:
    """Calculate estimated success probability for combat.

    Args:
        character: Character data dictionary
        monster: Monster data dictionary

    Returns:
        Success probability as percentage (0-100)
    """
    char_level = int(character.get("level", 0))
    monster_level = int(monster.get("level", 0))
    char_hp = int(character.get("max_hp", 0))
    monster_hp = int(monster.get("hp", 0))

    # Base probability from level difference
    level_diff = monster_level - char_level
    if level_diff <= -2:
        base_prob = 90
    elif -1 <= level_diff <= 1:
        base_prob = 75
    elif 2 <= level_diff <= 3:
        base_prob = 50
    else:
        base_prob = 25

    # Adjust for HP difference
    if char_hp > 0 and monster_hp > 0:
        hp_ratio = char_hp / monster_hp
        if hp_ratio > 2.0:
            base_prob += 10
        elif hp_ratio > 1.5:
            base_prob += 5
        elif hp_ratio < 0.5:
            base_prob -= 15
        elif hp_ratio < 0.75:
            base_prob -= 10

    # Calculate total damage potential vs monster HP
    char_total_attack = (
        int(character.get("attack_fire", 0))
        + int(character.get("attack_earth", 0))
        + int(character.get("attack_water", 0))
        + int(character.get("attack_air", 0))
    )

    if char_total_attack > 0 and monster_hp > 0:
        damage_ratio = char_total_attack / monster_hp
        if damage_ratio > 0.5:
            base_prob += 5
        elif damage_ratio < 0.1:
            base_prob -= 10

    # Clamp to reasonable range
    return max(5, min(95, base_prob))


def _format_combat_analysis(character: dict[str, str | int], monster: dict[str, str | int]) -> list[list[str]]:
    """Format combat analysis for display.

    Args:
        character: Character data dictionary
        monster: Monster data dictionary

    Returns:
        List of table rows for combat analysis
    """
    char_level = int(character.get("level", 0))
    monster_level = int(monster.get("level", 0))

    difficulty = _calculate_difficulty_rating(char_level, monster_level)
    success_prob = _calculate_success_probability(character, monster)

    rows = [
        ["Character Level", str(char_level)],
        ["Monster Level", str(monster_level)],
        ["Level Difference", f"{monster_level - char_level:+d}"],
        ["Difficulty", f"{difficulty['emoji']} {difficulty['rating']}"],
        ["Success Probability", f"{success_prob}%"],
    ]

    # HP comparison
    char_hp = int(character.get("max_hp", 0))
    monster_hp = int(monster.get("hp", 0))
    rows.extend(
        [
            ["Character HP", str(char_hp)],
            ["Monster HP", str(monster_hp)],
        ]
    )

    # Damage comparison
    char_total_attack = (
        int(character.get("attack_fire", 0))
        + int(character.get("attack_earth", 0))
        + int(character.get("attack_water", 0))
        + int(character.get("attack_air", 0))
    )
    monster_total_attack = (
        int(monster.get("attack_fire", 0))
        + int(monster.get("attack_earth", 0))
        + int(monster.get("attack_water", 0))
        + int(monster.get("attack_air", 0))
    )

    rows.extend(
        [
            ["Character Total Attack", str(char_total_attack)],
            ["Monster Total Attack", str(monster_total_attack)],
        ]
    )

    # Recommended level
    if difficulty["rating"] in ["Hard", "Deadly"]:
        recommended_level = monster_level - 1
        rows.append(["Recommended Level", f"{recommended_level}+"])

    return rows


def _get_monster_drops(monster) -> list[str]:
    """Extract monster drop information.

    Args:
        monster: Monster object from API

    Returns:
        List of drop descriptions
    """
    drops = []
    if hasattr(monster, "drops") and monster.drops:
        for drop in monster.drops:
            drop_code = getattr(drop, "code", "Unknown")
            drop_rate = getattr(drop, "rate", 0)
            min_quantity = getattr(drop, "min_quantity", 1)
            max_quantity = getattr(drop, "max_quantity", 1)

            if min_quantity == max_quantity:
                quantity_str = str(min_quantity)
            else:
                quantity_str = f"{min_quantity}-{max_quantity}"

            drops.append(f"{drop_code} x{quantity_str} ({drop_rate}%)")

    return drops
