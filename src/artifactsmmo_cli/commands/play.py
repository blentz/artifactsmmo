"""Play command: run the GOAP AI player."""

import contextlib
import threading
import traceback
from datetime import datetime
from pathlib import Path

import typer

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tracer import Tracer
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.observer import ThreadSafeBridge
from artifactsmmo_cli.utils.mutation_lock import check_mutation_lock, default_lock_path


def default_learn_db_path() -> str:
    """Return ~/.cache/artifactsmmo/learning.db (parent dirs created on first use)."""
    return str(Path.home() / ".cache" / "artifactsmmo" / "learning.db")


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
    tui: bool = typer.Option(False, "--tui",
                              help="Run with a live TUI watcher (Textual). Bot runs in a worker thread."),
) -> None:
    """Run the autonomous GOAP AI player for one character."""
    # Mutate<->play interlock: formal/diff/mutate.py live-writes mutants into
    # src/ and holds a repo-root lockfile for the whole run. Starting the bot
    # mid-run imports poisoned code (2026-06-09: a mutated predicate crashed
    # play with SystemExit(2)), so refuse before any game data or threads.
    lock_path = default_lock_path()
    lock = check_mutation_lock(lock_path)
    if lock.state == "active":
        print(f"mutation run in progress (pid {lock.pid}, lock {lock_path}) — "
              "src/ contains live mutants; retry after it finishes")
        raise typer.Exit(code=2)
    if lock.state == "stale":
        print(f"Warning: stale mutation lockfile at {lock_path} ({lock.detail}); continuing")

    tracer: Tracer = NullTracer()
    if trace:
        path = trace_file or f"play-trace-{character}-{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
        tracer = FileTracer(path)
        print(f"Tracing to {path}")

    # An in-memory LearningStore is always constructed when --learn is absent so
    # that history-gated tier predicates (PURSUE_TASK, TASK_CANCEL,
    # LOW_YIELD_CANCEL) remain evaluable. With history=None they short-circuit
    # to False; an items task + no winnable monster then leaves the discretionary
    # tier empty and the bot stalls indefinitely on "No plan found — waiting 5s".
    # The ephemeral SQLite store has zero observations, so history-gated
    # predicates still behave conservatively, but tier dispatch can run.
    store: LearningStore
    if learn:
        db_path = learn_db or default_learn_db_path()
        store = LearningStore(db_path=db_path, character=character)
        print(f"Learning enabled - DB at {db_path}")
    else:
        store = LearningStore(db_path=":memory:", character=character)
    store.start_session()

    player = GamePlayer(
        character=character, verbose=verbose, dry_run=dry_run,
        tracer=tracer, history=store,
    )
    exit_reason = "crash"
    try:
        if tui:
            _run_with_tui(player, character)
        else:
            player.run()
        exit_reason = "normal"
    except KeyboardInterrupt:
        exit_reason = "keyboard_interrupt"
        raise
    finally:
        store.end_session(exit_reason=exit_reason)
        store.close()


def _run_with_tui(player: GamePlayer, character: str) -> None:
    """Spawn the bot in a worker thread; run the Textual app on main thread.

    Worker-thread failure is supervised via ``threading.excepthook``: a bare
    daemon thread dies SILENTLY, leaving the TUI ghosted (frozen panes, no
    error) and the session exit unrecorded — the 2026-06-10 Robby incident
    (worker died at 12:49Z, TUI sat ghosted until 18:29Z, exit_reason lied
    "normal"). The hook receives every uncaught worker exception without an
    ``except`` clause, records it, and tears the TUI down; the captured
    exception is re-raised on the main thread AFTER Textual has restored the
    real terminal, so the traceback is visible and play() records
    exit_reason="crash".
    """
    # Preload game_data on the main thread so the map can render the first
    # frame before the bot has done a cycle.
    client = ClientManager().client
    player.game_data = GameData.load(client)
    app = WatchApp(character=character, game_data=player.game_data)
    bridge = ThreadSafeBridge(app, app.update_snapshot)
    player.set_cycle_observer(bridge.notify)

    # Daemon thread so the process exits cleanly when the TUI quits.
    bot_thread = threading.Thread(target=player.run, daemon=True)

    crashes: list[BaseException] = []
    previous_hook = threading.excepthook

    def _bot_excepthook(hook_args: threading.ExceptHookArgs) -> None:
        if hook_args.thread is not bot_thread or hook_args.exc_value is None:
            previous_hook(hook_args)
            return
        crashes.append(hook_args.exc_value)
        # Fatal notification through the app's thread-safe channel: exit with
        # a message Textual prints after teardown. Best-effort — Textual's
        # call_from_thread raises RuntimeError when the app is not running
        # (already torn down / user quit first); the crash is still recorded
        # and re-raised below either way.
        with contextlib.suppress(RuntimeError):
            app.call_from_thread(
                app.exit,
                return_code=1,
                message=f"Bot worker thread crashed: {hook_args.exc_value!r}",
            )

    threading.excepthook = _bot_excepthook
    try:
        bot_thread.start()
        app.run()
    finally:
        threading.excepthook = previous_hook
    if crashes:
        # Print on the real terminal (after the alternate screen is gone),
        # then re-raise so play()'s finally records exit_reason="crash".
        print(f"Bot worker thread for {character!r} crashed; traceback:")
        traceback.print_exception(crashes[0])
        raise crashes[0]
