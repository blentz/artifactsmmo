"""Leaderboard command."""

from typing import Any

import httpx
import typer
from artifactsmmo_api_client.api.leaderboard import (
    get_accounts_leaderboard_leaderboard_accounts_get,
    get_characters_leaderboard_leaderboard_characters_get,
)
from artifactsmmo_api_client.errors import UnexpectedStatus

from artifactsmmo_cli.commands import info as _pkg
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import format_error_message, format_table


def show_leaderboard(
    board_type: str = typer.Argument("characters", help="Leaderboard type: 'characters' or 'accounts'"),
    sort: str = typer.Option("level", help="Sort by: level, xp, gold, etc."),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """Display leaderboards."""
    try:
        if board_type.lower() not in ("characters", "accounts"):
            _pkg.console.print(format_error_message("Invalid leaderboard type. Use 'characters' or 'accounts'"))
            raise typer.Exit(1)

        client = _pkg.ClientManager().client

        lb_kwargs: dict[str, Any] = {"client": client, "sort": sort, "page": page, "size": size}
        if board_type.lower() == "characters":
            response: Any = get_characters_leaderboard_leaderboard_characters_get.sync(**lb_kwargs)
        elif board_type.lower() == "accounts":
            response = get_accounts_leaderboard_leaderboard_accounts_get.sync(**lb_kwargs)
        cli_response = _pkg.handle_api_response(response)
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
                                str(display_field(entry, "name")),
                                str(display_field(entry, "level")),
                                str(display_field(entry, "xp")),
                                str(display_field(entry, "gold")),
                            ]
                        )
                else:  # accounts
                    headers = ["Rank", "Username", "Characters", "Achievements"]
                    rows = []
                    for i, entry in enumerate(leaderboard.data, 1):
                        rows.append(
                            [
                                str(i + (page - 1) * size),
                                str(display_field(entry, "username")),
                                str(display_field(entry, "characters_count")),
                                str(display_field(entry, "achievements_points")),
                            ]
                        )

                output = format_table(headers, rows, title=f"{board_type.title()} Leaderboard")
                _pkg.console.print(output)
            else:
                _pkg.console.print(format_error_message("No leaderboard data found"))
        else:
            _pkg.console.print(format_error_message(cli_response.error or "Could not retrieve leaderboard"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = _pkg.handle_api_error(e)
        _pkg.console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
