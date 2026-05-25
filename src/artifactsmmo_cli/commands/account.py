"""Account management commands."""

import httpx
import typer
from artifactsmmo_api_client.api.my_account import get_account_details_my_details_get
from artifactsmmo_api_client.api.my_characters import (
    get_all_characters_logs_my_logs_get,
    get_character_logs_my_logs_name_get,
)
from artifactsmmo_api_client.errors import UnexpectedStatus
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.utils.api_display import display_field
from artifactsmmo_cli.utils.formatters import (
    format_error_message,
    format_table,
)
from artifactsmmo_cli.utils.helpers import handle_api_error, handle_api_response
from artifactsmmo_cli.utils.validators import validate_character_name

app = typer.Typer(help="Account management commands")
console = Console()


@app.command("details")
def show_account_details() -> None:
    """Show account details."""
    try:
        client = ClientManager().client

        response = get_account_details_my_details_get.sync(client=client)

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            account = cli_response.data
            headers = ["Property", "Value"]
            rows = [
                ["Username", str(display_field(account, "username"))],
                ["Email", str(display_field(account, "email"))],
                ["Subscribed", str(display_field(account, "subscribed"))],
                ["Status", str(display_field(account, "status"))],
                ["Badges", str(display_field(account, "badges"))],
            ]

            # Add subscription info if available
            if hasattr(account, "subscription") and account.subscription:
                sub = account.subscription
                rows.extend(
                    [
                        ["Sub Type", str(display_field(sub, "type"))],
                        ["Sub Status", str(display_field(sub, "status"))],
                        ["Sub Expires", str(display_field(sub, "expires_at"))],
                    ]
                )

            output = format_table(headers, rows, title="Account Details")
            console.print(output)
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve account details"))
            raise typer.Exit(1)

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)


@app.command("logs")
def show_logs(
    character: str = typer.Option(None, help="Character name (if not specified, shows all characters)"),
    page: int = typer.Option(1, help="Page number"),
    size: int = typer.Option(50, help="Items per page"),
) -> None:
    """Show account or character logs."""
    try:
        client = ClientManager().client

        if character:
            # Get logs for specific character
            character = validate_character_name(character)
            response = get_character_logs_my_logs_name_get.sync(client=client, name=character, page=page, size=size)
            title = f"Logs for {character}"
        else:
            # Get logs for all characters
            response = get_all_characters_logs_my_logs_get.sync(client=client, page=page, size=size)
            title = "All Character Logs"

        cli_response = handle_api_response(response)
        if cli_response.success and cli_response.data:
            logs = cli_response.data
            if hasattr(logs, "data") and logs.data:
                headers = ["Character", "Type", "Description", "Content", "Cooldown", "Created"]
                rows = []
                for log in logs.data:
                    # Truncate long descriptions and content
                    description = getattr(log, "description", "")
                    if len(description) > 30:
                        description = description[:27] + "..."

                    content = str(getattr(log, "content", ""))
                    if len(content) > 20:
                        content = content[:17] + "..."

                    rows.append(
                        [
                            str(display_field(log, "character")),
                            str(display_field(log, "type")),
                            description,
                            content,
                            str(display_field(log, "cooldown")),
                            str(display_field(log, "created_at")),
                        ]
                    )

                output = format_table(headers, rows, title=title)
                console.print(output)
            else:
                console.print(format_error_message("No logs found"))
        else:
            console.print(format_error_message(cli_response.error or "Could not retrieve logs"))

    except (ValueError, UnexpectedStatus, httpx.HTTPError) as e:
        cli_response = handle_api_error(e)
        console.print(format_error_message(cli_response.error or str(e)))
        raise typer.Exit(1)
