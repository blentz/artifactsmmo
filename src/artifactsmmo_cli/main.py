"""Main CLI entry point for ArtifactsMMO CLI."""

from pathlib import Path

import typer
from rich.console import Console

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.commands import account, action, bank, character, craft, info, task, trade
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.utils.formatters import format_error_message

# Create the main Typer app
app = typer.Typer(
    name="artifactsmmo", help="CLI interface for ArtifactsMMO game", add_completion=True, rich_markup_mode="rich"
)

console = Console()

# Register command groups
app.add_typer(character.app, name="character", help="Character management commands")
app.add_typer(action.app, name="action", help="Character action commands")
app.add_typer(bank.app, name="bank", help="Bank operation commands")
app.add_typer(trade.app, name="trade", help="Grand Exchange trading commands")
app.add_typer(craft.app, name="craft", help="Crafting and recycling commands")
app.add_typer(task.app, name="task", help="Task management commands")
app.add_typer(info.app, name="info", help="Information and lookup commands")
app.add_typer(account.app, name="account", help="Account management commands")


@app.callback()
def main(
    ctx: typer.Context,
    token_file: Path | None = typer.Option(
        None, "--token-file", "-t", help="Path to token file (default: TOKEN in current directory)"
    ),
    debug: bool = typer.Option(False, "--debug", help="Enable debug output"),
) -> None:
    """
    ArtifactsMMO CLI - Command line interface for the ArtifactsMMO game.

    This CLI provides access to all game features including character management,
    actions, banking, trading, and more through a convenient command-line interface.

    Authentication is handled via a TOKEN file or ARTIFACTSMMO_TOKEN environment variable.
    """
    # Skip initialization for help and completion commands
    if ctx.invoked_subcommand in ["--help", "--install-completion", "--show-completion"]:
        return

    try:
        # Load configuration
        config = Config.from_token_file(token_file)
        config.debug = debug

        # Initialize the client manager
        ClientManager().initialize(config)

        if debug:
            console.print(f"[dim]Initialized with API base URL: {config.api_base_url}[/dim]")

    except ValueError as e:
        console.print(format_error_message(str(e)))
        raise typer.Exit(1)
    except Exception as e:
        console.print(format_error_message(f"Failed to initialize CLI: {str(e)}"))
        raise typer.Exit(1)


@app.command("version")
def version() -> None:
    """Show version information."""
    from artifactsmmo_cli import __version__

    console.print(f"ArtifactsMMO CLI version {__version__}")


@app.command("status")
def status() -> None:
    """Check API connection status."""
    try:
        client_manager = ClientManager()
        if not client_manager.is_initialized():
            console.print(format_error_message("Client not initialized"))
            raise typer.Exit(1)

        # Try to make a simple API call to check connectivity
        api = client_manager.api
        response = api.get_server_details()

        if response:
            console.print("[green]✓[/green] API connection successful")
            console.print(f"Version: {response.data.version}")
            console.print(f"Max Level: {response.data.max_level}")
            console.print(f"Characters Online: {response.data.characters_online}")
            console.print(f"Server Time: {response.data.server_time}")
        else:
            console.print(format_error_message("Failed to connect to API"))
            raise typer.Exit(1)

    except Exception as e:
        console.print(format_error_message(f"API connection failed: {str(e)}"))
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
