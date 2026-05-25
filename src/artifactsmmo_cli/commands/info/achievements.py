"""Achievement (badge) lookup command."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.badges import get_all_badges_badges_get, get_badge_badges_code_get
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def list_achievements(
    achievement_code: str = typer.Option(None, help="Specific achievement code to lookup"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """List or search achievements (badges)."""
    try:
        client = _pkg.ClientManager().client

        if achievement_code:
            # Get specific achievement
            response: Any = get_badge_badges_code_get.sync(client=client, code=achievement_code)
            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                badge = cli_response.data
                headers = ["Property", "Value"]
                rows = [
                    ["Code", str(display_field(badge, "code"))],
                    ["Name", str(display_field(badge, "name"))],
                    ["Description", str(display_field(badge, "description"))],
                ]

                output = format_table(headers, rows, title=f"Achievement: {achievement_code}")
                _pkg.console.print(output)
            else:
                _pkg.console.print(
                    format_error_message(cli_response.error or f"Achievement '{achievement_code}' not found")
                )
        else:
            # List achievements
            response = get_all_badges_badges_get.sync(client=client, page=page, size=size)

            cli_response = _pkg.handle_api_response(response)
            if cli_response.success and cli_response.data:
                badges = cli_response.data
                if hasattr(badges, "data") and badges.data:
                    headers = ["Code", "Name", "Description"]
                    rows = []
                    for badge in badges.data:
                        description = getattr(badge, "description", "")
                        if len(description) > 60:
                            description = description[:57] + "..."

                        rows.append([str(display_field(badge, "code")), str(display_field(badge, "name")), description])

                    output = format_table(headers, rows, title="Achievements")
                    _pkg.console.print(output)
                else:
                    _pkg.console.print(format_error_message("No achievements found"))
            else:
                _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve achievements"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
