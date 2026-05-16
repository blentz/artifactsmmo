"""Play command: run the GOAP AI player."""

from datetime import datetime

import typer

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tracing import FileTracer, NullTracer, Tracer

app = typer.Typer(help="Run the autonomous AI player")


@app.command("play")
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full plan each cycle"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute actions"),
    trace: bool = typer.Option(False, "--trace", help="Emit per-cycle JSONL to --trace-file"),
    trace_file: str | None = typer.Option(None, "--trace-file",
                                          help="Trace output path (default: play-trace-{character}-{ts}.jsonl)"),
) -> None:
    """Run the autonomous GOAP AI player for one character."""
    tracer: Tracer = NullTracer()
    if trace:
        path = trace_file or f"play-trace-{character}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
        tracer = FileTracer(path)
        print(f"Tracing to {path}")

    player = GamePlayer(character=character, verbose=verbose, dry_run=dry_run, tracer=tracer)
    player.run()
