"""NPC lookup commands."""

import httpx
import typer
from artifactsmmo_api_client.api.maps import get_all_maps_maps_get
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def list_npcs(
    npc_type: str = typer.Option(None, help="Filter by NPC type (task_master, bank, grand_exchange, workshop)"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List all NPCs and their locations."""
    try:
        client = _pkg.ClientManager().client

        # Search through map data to find NPCs
        all_npcs = []
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = _pkg.handle_api_response(response)

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
                        if npc_type and npc_type.lower() not in str(npc_info["type"]).lower():
                            continue

                        all_npcs.append(
                            {
                                "name": npc_info["name"],
                                "type": npc_info["type"],
                                "x": str(display_field(map_item, "x")),
                                "y": str(display_field(map_item, "y")),
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
                            str(npc["name"]),
                            str(npc["type"]),
                            f"({npc['x']}, {npc['y']})",
                            services_str,
                        ]
                    )

                title = "NPCs"
                if npc_type:
                    title += f" (Type: {npc_type})"
                title += f" - Page {page} of {(len(all_npcs) + size - 1) // size}"

                output = format_table(headers, rows, title=title)
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message(f"No NPCs found on page {page}"))
        else:
            # No NPC content in the map API — report it. Never fabricate a
            # "known locations" table (CLAUDE.md: use only API data or fail).
            _pkg.console.print(format_error_message("No NPC content data found in map API"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


def get_npc(
    name: str = typer.Argument(help="NPC name to search for"),
) -> None:
    """Get specific NPC details by name."""
    try:
        client = _pkg.ClientManager().client

        # Search through map data to find the specific NPC
        found_npc = None
        current_page = 1
        max_pages = 10  # Limit search to prevent infinite loops

        while current_page <= max_pages and not found_npc:
            response = get_all_maps_maps_get.sync(client=client, page=current_page, size=100)
            cli_response = _pkg.handle_api_response(response)

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
                    if npc_info and name.lower() in str(npc_info["name"]).lower():
                        found_npc = {
                            "name": npc_info["name"],
                            "type": npc_info["type"],
                            "x": str(display_field(map_item, "x")),
                            "y": str(display_field(map_item, "y")),
                            "services": npc_info["services"],
                            "content_code": content_code,
                            "content_type": content_type,
                            "location_name": str(display_field(map_item, "name")),
                        }
                        break

            # Check if we have more pages
            if hasattr(maps, "pages") and current_page >= maps.pages:
                break
            current_page += 1

        if found_npc:
            headers = ["Property", "Value"]
            rows = [
                ["Name", str(found_npc["name"])],
                ["Type", str(found_npc["type"])],
                ["Location", f"({found_npc['x']}, {found_npc['y']})"],
                ["Area", str(found_npc["location_name"])],
                ["Content Type", str(found_npc["content_type"])],
                ["Content Code", str(found_npc["content_code"])],
                ["Services", ", ".join(found_npc["services"])],
            ]

            output = format_table(headers, rows, title=f"NPC: {found_npc['name']}")
            _pkg.console.print(output)
        else:
            # No NPC content for this name in the map API. Report it — never
            # fabricate coordinates (CLAUDE.md: use only API data or fail).
            _pkg.console.print(format_error_message(f"NPC '{name}' not found"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
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
