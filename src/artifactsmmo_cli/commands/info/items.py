"""Item lookup command."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.items import get_all_items_items_get, get_item_items_code_get
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


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
        client = _pkg.ClientManager().client

        if item_code:
            # Get specific item
            response: Any = get_item_items_code_get.sync(client=client, code=item_code)
            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                item = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", str(display_field(item, "code"))],
                    ["Name", str(display_field(item, "name"))],
                    ["Type", str(display_field(item, "type_"))],
                    ["Subtype", str(display_field(item, "subtype"))],
                    ["Level", str(display_field(item, "level"))],
                    ["Description", str(display_field(item, "description"))],
                ]

                # Add craft info if available
                if hasattr(item, "craft") and item.craft:
                    craft = item.craft
                    rows.extend(
                        [
                            ["Craft Skill", str(display_field(craft, "skill"))],
                            ["Craft Level", str(display_field(craft, "level"))],
                        ]
                    )

                output = format_table(headers, rows, title=f"Item: {item_code}")
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message(cli_response.error or f"Item '{item_code}' not found"))
        else:
            # List items - only pass non-None parameters to avoid API client bugs
            kwargs: dict[str, Any] = {"client": client, "page": page, "size": size}
            if item_type is not None:
                kwargs["type_"] = item_type
            if craft_skill is not None:
                kwargs["craft_skill"] = craft_skill
            if craft_level is not None:
                kwargs["min_level"] = craft_level

            response = get_all_items_items_get.sync(**kwargs)

            cli_response = _pkg.handle_api_response(response)
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
                                str(display_field(item, "code")),
                                str(display_field(item, "name")),
                                str(display_field(item, "type_")),
                                str(display_field(item, "level")),
                                description,
                            ]
                        )

                    output = format_table(headers, rows, title="Items")
                    _pkg.console.print(output)
                else:
                    _pkg.console.print(format_error_message("No items found"))
            else:
                _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve items"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
