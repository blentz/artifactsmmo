"""Events command."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.events import (
    get_all_active_events_events_active_get,
    get_all_events_events_get,
)
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def list_events(
    active_only: bool = typer.Option(True, help="Show only active events"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List game events."""
    try:
        client = _pkg.ClientManager().client

        if active_only:
            response: Any = get_all_active_events_events_active_get.sync(client=client, page=page, size=size)
        else:
            response = get_all_events_events_get.sync(client=client, page=page, size=size)

        cli_response = _pkg.handle_api_response(response)
        if cli_response.success and cli_response.data:
            events = cli_response.data
            if hasattr(events, "data") and events.data:
                headers = ["Name", "Map", "Duration", "Rate", "Expiration"]
                rows = []
                for event in events.data:
                    rows.append(
                        [
                            str(display_field(event, "name")),
                            getattr(event, "map", {}).get("name", "N/A") if hasattr(event, "map") else "N/A",
                            str(display_field(event, "duration")),
                            str(display_field(event, "rate")),
                            str(display_field(event, "expiration")),
                        ]
                    )

                title = "Active Events" if active_only else "All Events"
                output = format_table(headers, rows, title=title)
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message("No events found"))
        else:
            _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve events"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
