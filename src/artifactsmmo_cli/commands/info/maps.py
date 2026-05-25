"""Map information command."""

import httpx
import typer
from artifactsmmo_api_client.api.maps import get_all_maps_maps_get, get_map_by_position_maps_layer_x_y_get
from artifactsmmo_api_client.errors import UnexpectedStatus
from artifactsmmo_api_client.models.map_layer import MapLayer

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def map_info(
    x: int = typer.Option(None, help="X coordinate"),
    y: int = typer.Option(None, help="Y coordinate"),
    content_code: str = typer.Option(None, help="Content code to search for"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """Get map information for locations."""
    try:
        client = _pkg.ClientManager().client

        if x is not None and y is not None:
            # Get specific map location
            response = get_map_by_position_maps_layer_x_y_get.sync(client=client, layer=MapLayer.OVERWORLD, x=x, y=y)
            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                map_data = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Coordinates", f"({display_field(map_data, 'x')}, {display_field(map_data, 'y')})"],
                    ["Name", str(display_field(map_data, "name"))],
                    ["Skin", str(display_field(map_data, "skin"))],
                ]

                # Add content info if available
                if hasattr(map_data, "content") and map_data.content:
                    content = map_data.content
                    rows.extend(
                        [
                            ["Content Type", str(display_field(content, "type"))],
                            ["Content Code", str(display_field(content, "code"))],
                        ]
                    )

                output = format_table(headers, rows, title=f"Map Location ({x}, {y})")
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message(cli_response.error or f"Map location ({x}, {y}) not found"))
        else:
            # List maps with optional filtering
            response = get_all_maps_maps_get.sync(client=client, content_code=content_code, page=page, size=size)

            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                maps = cli_response.data
                if hasattr(maps, "data") and maps.data:
                    headers = ["Coordinates", "Name", "Skin", "Content Type", "Content Code"]
                    rows = []
                    for map_item in maps.data:
                        content_type = ""
                        content_code_val = ""
                        if hasattr(map_item, "content") and map_item.content:
                            content_type = str(display_field(map_item.content, "type"))
                            content_code_val = str(display_field(map_item.content, "code"))

                        rows.append(
                            [
                                f"({display_field(map_item, 'x')}, {display_field(map_item, 'y')})",
                                str(display_field(map_item, "name")),
                                str(display_field(map_item, "skin")),
                                content_type,
                                content_code_val,
                            ]
                        )

                    title = "Map Locations"
                    if content_code:
                        title += f" (Content: {content_code})"
                    output = format_table(headers, rows, title=title)
                    _pkg.console.print(output)
                else:
                    _pkg.console.print(format_error_message("No map locations found"))
            else:
                _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve map information"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
