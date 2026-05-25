"""Resource lookup and discovery commands."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.maps import get_all_maps_maps_get
from artifactsmmo_api_client.api.resources import (
    get_all_resources_resources_get,
    get_resource_resources_code_get,
)
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.gathering_skill import GatheringSkill
from artifactsmmo_api_client.types import UNSET, Unset

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


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
            _pkg.console.print(format_error_message("--radius requires --location to be specified"))
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
                _pkg.console.print(format_error_message("Invalid location format. Use 'X Y' coordinates"))
                raise typer.Exit(1)

        # Get character position if character specified
        char_x, char_y = None, None
        if character:
            try:
                char_x, char_y = _pkg.get_character_position(character)
            except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
                _pkg.console.print(format_error_message(f"Could not get character position: {e}"))
                raise typer.Exit(1)

        client = _pkg.ClientManager().client

        if resource_code:
            # Get specific resource
            response: Any = get_resource_resources_code_get.sync(client=client, code=resource_code)
            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                resource = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", str(display_field(resource, "code"))],
                    ["Name", str(display_field(resource, "name"))],
                    ["Skill", str(display_field(resource, "skill"))],
                    ["Level", str(display_field(resource, "level"))],
                ]

                # Add drops if available
                if hasattr(resource, "drops") and resource.drops:
                    drops = []
                    for drop in resource.drops:
                        drops.append(f"{display_field(drop, 'code')} ({display_field(drop, 'rate')}%)")
                    rows.append(["Drops", ", ".join(drops)])

                # Add location information if available
                if char_x is not None and char_y is not None:
                    try:
                        locations = _pkg._find_resource_locations(resource_code, character_x=char_x, character_y=char_y)
                        if locations:
                            nearest = min(locations, key=lambda r: r["distance"])
                            rows.append(
                                [
                                    "Nearest Location",
                                    f"({nearest['x']}, {nearest['y']}) - Distance: {nearest['distance']}",
                                ]
                            )
                    except (UnexpectedStatus, httpx.HTTPError):
                        pass  # Don't fail if location lookup fails

                output = format_table(headers, rows, title=f"Resource: {resource_code}")
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message(cli_response.error or f"Resource '{resource_code}' not found"))
        else:
            # Determine API parameters for level filtering
            api_min_level = level
            api_max_level = max_level

            # List resources - only pass non-None parameters to avoid API client bugs
            kwargs: dict[str, Any] = {"client": client, "page": page, "size": size}

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

            cli_response = _pkg.handle_api_response(response)
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
                                    locations = _pkg._find_resource_locations(
                                        resource_code_val, character_x=char_x, character_y=char_y
                                    )

                                    # Filter by location/radius if specified
                                    if center_x is not None and center_y is not None:
                                        if radius is not None:
                                            locations = [
                                                loc
                                                for loc in locations
                                                if abs(int(loc["x"]) - center_x) + abs(int(loc["y"]) - center_y)
                                                <= radius
                                            ]
                                        else:
                                            # Just sort by distance from center
                                            for loc in locations:
                                                loc["center_distance"] = abs(int(loc["x"]) - center_x) + abs(
                                                    int(loc["y"]) - center_y
                                                )
                                            locations.sort(key=lambda r: r["center_distance"])

                                    if locations:
                                        resource_locations[resource_code_val] = locations
                        except (UnexpectedStatus, httpx.HTTPError):
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
                                    drops.append(str(display_field(drop, "code")))

                            row = [
                                resource_code_val,
                                str(display_field(resource, "name")),
                                str(display_field(resource, "skill")),
                                str(display_field(resource, "level")),
                            ]

                            # Add location information if available
                            if resource_code_val in resource_locations:
                                nearest = resource_locations[resource_code_val][0]
                                row.append(f"({nearest['x']}, {nearest['y']})")

                                if char_x is not None and char_y is not None:
                                    row.append(str(nearest["distance"]))

                            elif char_x is not None and char_y is not None:
                                row.extend(["Not found", "N/A"])
                            # Center-only mode pre-filters resources to those WITH a
                            # location (see filter above), so the "not found" case
                            # cannot occur here — no branch needed.

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
                        _pkg.console.print(output)
                    else:
                        _pkg.console.print(format_error_message("No resources found matching criteria"))
                else:
                    _pkg.console.print(format_error_message("No resources found"))
            else:
                _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve resources"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


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
                char_x, char_y = _pkg.get_character_position(character)
            except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
                _pkg.console.print(format_error_message(f"Could not get character position: {e}"))
                raise typer.Exit(1)

        # Find resource locations
        resource_locations = _pkg._find_resource_locations(
            resource_name=resource_name,
            resource_type=resource_type,
            character_x=char_x,
            character_y=char_y,
            max_distance=max_distance,
        )

        if not resource_locations:
            _pkg.console.print(format_error_message(f"No resources found matching '{resource_name}'"))
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
                        str(resource["name"]),
                        str(resource["type"]),
                        f"({resource['x']}, {resource['y']})",
                        str(resource["distance"]),
                        str(resource["level"]),
                        str(resource["skill"]),
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
                        str(resource["name"]),
                        str(resource["type"]),
                        f"({resource['x']}, {resource['y']})",
                        str(resource["level"]),
                        str(resource["skill"]),
                    ]
                )
            title = f"{resource_name.title()} Resource Locations"

        output = format_table(headers, rows, title=title)
        _pkg.console.print(output)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
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
    client = _pkg.ClientManager().client

    # First, get resource data to understand what we're looking for
    resource_data = _pkg._get_resource_data(resource_name, resource_type)

    # Search map for resource locations
    resource_locations = []
    current_page = 1
    max_pages = 20  # Limit search to prevent infinite loops

    while current_page <= max_pages:
        response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
        cli_response = _pkg.handle_api_response(response)

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
    client = _pkg.ClientManager().client

    resources = []
    current_page = 1
    max_pages = 10

    # Convert string resource_type to GatheringSkill enum if provided
    skill_enum: GatheringSkill | Unset = UNSET
    if resource_type:
        try:
            skill_enum = GatheringSkill(resource_type.lower())
        except ValueError:
            # Invalid skill type, continue without filter
            skill_enum = UNSET

    while current_page <= max_pages:
        response = get_all_resources_resources_get.sync(client=client, skill=skill_enum, page=current_page, size=100)

        cli_response = _pkg.handle_api_response(response)
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
        if str(resource["code"]).lower() == content_code:
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
        if str(resource["code"]).lower() == content_code:
            return resource

    # If no exact match, create a default entry
    return {
        "name": content_code.replace("_", " ").title(),
        "skill": "Unknown",
        "level": 0,
    }
