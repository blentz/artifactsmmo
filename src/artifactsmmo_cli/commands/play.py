"""Play command: run the GOAP AI player."""

from datetime import datetime
from pathlib import Path

import typer

from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tracing import FileTracer, NullTracer, Tracer

app = typer.Typer(help="Run the autonomous AI player")


def default_learn_db_path() -> str:
    """Return ~/.cache/artifactsmmo/learning.db (parent dirs created on first use)."""
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


@app.command("play")
def play(
    character: str = typer.Argument(..., help="Character name to play"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show full plan each cycle"),
    dry_run: bool = typer.Option(False, "--dry-run", help="Plan only, do not execute actions"),
    trace: bool = typer.Option(False, "--trace", help="Emit per-cycle JSONL to --trace-file"),
    trace_file: str | None = typer.Option(None, "--trace-file",
                                          help="Trace output path (default: play-trace-{character}-{ts}.jsonl)"),
    learn: bool = typer.Option(False, "--learn",
                                help="Read/write learned stats to SQLite for autoregressive planning"),
    learn_db: str | None = typer.Option(None, "--learn-db",
                                         help="Learning DB path (default: ~/.cache/artifactsmmo/learning.db)"),
) -> None:
    """Run the autonomous GOAP AI player for one character."""
    tracer: Tracer = NullTracer()
    if trace:
        path = trace_file or f"play-trace-{character}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
        tracer = FileTracer(path)
        print(f"Tracing to {path}")

    store: LearningStore | None = None
    if learn:
        db_path = learn_db or default_learn_db_path()
        store = LearningStore(db_path=db_path, character=character)
        store.start_session()
        print(f"Learning enabled - DB at {db_path}")

    player = GamePlayer(
        character=character, verbose=verbose, dry_run=dry_run,
        tracer=tracer, history=store,
    )
    exit_reason = "crash"
    try:
        player.run()
        exit_reason = "normal"
    except KeyboardInterrupt:
        exit_reason = "keyboard_interrupt"
        raise
    finally:
        if store is not None:
            store.end_session(exit_reason=exit_reason)
            store.close()
