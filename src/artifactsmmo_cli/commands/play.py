"""Play command: run the GOAP AI player."""

import typer

from artifactsmmo_cli.ai.player import GamePlayer

app = typer.Typer(help="Run the autonomous AI player")


@app.command()
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full plan each cycle"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute actions"),
) -> None:
    """Run the GOAP AI player for a character."""
    player = GamePlayer(character=character, verbose=verbose, dry_run=dry_run)
    player.run()
