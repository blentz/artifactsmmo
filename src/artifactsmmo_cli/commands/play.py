"""Play command: run the GOAP AI player."""

import contextlib
import sys
import threading
import traceback
from datetime import datetime

import httpx
import typer

from artifactsmmo_cli.ai.file_tracer import FileTracer
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.coordination_store import CoordinationStore
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.null_tracer import NullTracer
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.recovery import StuckExit
from artifactsmmo_cli.ai.tracer import Tracer
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.learning_db_path import default_learn_db_path
from artifactsmmo_cli.multi.event_emitter import JsonlEventEmitter
from artifactsmmo_cli.multi.multi_run import MultiRun
from artifactsmmo_cli.server_unavailable_error import ServerUnavailableError
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.tui.observer import ThreadSafeBridge
from artifactsmmo_cli.utils.mutation_lock import check_mutation_lock, default_lock_path
from artifactsmmo_cli.utils.rate_budget import BucketBudgets
from artifactsmmo_cli.utils.rate_governor import RateGovernor

# `default_learn_db_path` now lives in `learning_db_path.py` so
# `multi/multi_run.py` can reuse the SAME default without importing
# `commands/play.py` (which already imports `MultiRun` — a cycle). The
# `import` above binds it into this module's namespace, so existing callers
# reading it as `play_module.default_learn_db_path()` (e.g. tests predicting
# the exact path `play` constructs a store against) are unaffected.


def emit_reason_for(exc: BaseException) -> str:
    """The exit reason reported to the supervisor. An httpx transport failure is
    transient and worth restarting; every other crash is a bug that a restart
    loop would only hide. The learning store still records plain "crash"."""
    if isinstance(exc, httpx.HTTPError):
        return "crash:network"
    return "crash"


def play(
    character: str | None = typer.Argument(None, help="Character name to play"),
    all_characters: bool = typer.Option(
        False, "--all",
        help="Supervise every account character, one subprocess each"),
    emit_events: bool = typer.Option(
        False, "--emit-events",
        help="Emit JSONL cycle events on stdout; human output moves to stderr"),
    rate_budget: str | None = typer.Option(
        None, "--rate-budget",
        help="This child's share of the account rate budget, as JSON"),
    coordination_db: str | None = typer.Option(
        None, "--coordination-db",
        help="Cross-character coordination DB path (set by `play --all`'s "
             "supervisor for every child; not meant to be passed by hand)"),
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
    refresh_game_data: bool = typer.Option(
        False, "--refresh-game-data",
        help="Ignore the cached static game data and re-fetch from the API"),
) -> None:
    """Run the autonomous GOAP AI player for one character."""
    if all_characters and character is not None:
        print("--all supervises every character; do not also name one")
        raise typer.Exit(code=2)
    if all_characters and trace_file is not None:
        print("--all writes one trace per character; --trace-file names only one")
        raise typer.Exit(code=2)
    if not all_characters and character is None:
        print("name a character to play, or pass --all")
        raise typer.Exit(code=2)
    if all_characters:
        MultiRun(verbose=verbose, dry_run=dry_run, trace=trace, learn=learn,
                 learn_db=learn_db, tui=tui,
                 refresh_game_data=refresh_game_data).run()
        return
    # The three checks above raise for every case where `character` could
    # still be None; mypy's flow analysis does not connect the two
    # independent conditions, so state the resulting invariant explicitly
    # rather than reaching for a `# type: ignore`.
    assert character is not None

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

    config = Config.from_token_file()

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
        persisted_db_path = learn_db or default_learn_db_path()
        store = LearningStore(db_path=persisted_db_path, character=character)
        print(f"Learning enabled - DB at {persisted_db_path}")
    else:
        store = LearningStore(db_path=":memory:", character=character)
    store.start_session()

    player = GamePlayer(
        character=character, verbose=verbose, dry_run=dry_run,
        tracer=tracer, history=store,
        game_data_ttl_minutes=config.game_data_ttl_minutes,
        refresh_game_data=refresh_game_data,
    )
    if rate_budget is not None:
        budgets = BucketBudgets.from_json(rate_budget)
        player.set_rate_governors(
            data=RateGovernor(budgets.data), action=RateGovernor(budgets.action),
            account=RateGovernor(budgets.account),
        )

    # Cross-character role coordination (emergent-specialization spec, Task
    # 11). Gated purely on `--coordination-db` being set. `--learn` no
    # longer gates coordination at all — it means only "persist learned
    # stats" now (human ruling, round 3 of review). The ONLY caller that
    # ever passes `--coordination-db` is `MultiRun._child_argv`, which
    # ALWAYS supplies a real, shared, on-disk path to every child of one
    # supervisor: the learning DB path when `--learn` is on (children
    # already share that file), else a supervisor-scoped temp file
    # `MultiRun` creates and cleans up itself (`:memory:` would be private
    # per-connection and could never coordinate with a sibling). A lone
    # `play <character>` never passes this flag, so it stays bit-identical.
    coordination: CoordinationStore | None = None
    if coordination_db is not None:
        coordination = CoordinationStore(db_path=coordination_db, character=character)
        player.set_coordination_store(coordination)

    emitter: JsonlEventEmitter | None = None
    if emit_events:
        # Capture the REAL stdout before the redirect below rebinds sys.stdout,
        # so the protocol keeps writing to the pipe the parent reads.
        emitter = JsonlEventEmitter(character=character, stream=sys.stdout)
        player.set_cycle_observer(emitter.snapshot)
        player.set_planning_observer(emitter.planning)

    exit_reason = "crash"
    emit_reason = "crash"
    try:
        with contextlib.redirect_stdout(sys.stderr) if emit_events else contextlib.nullcontext():
            if tui:
                _run_with_tui(player, character, config.game_data_ttl_minutes, refresh_game_data)
            else:
                player.run()
        exit_reason = "normal"
        emit_reason = "normal"
    except ServerUnavailableError:
        # Server returned a maintenance page. run() (the console entrypoint)
        # renders it and exits 3; here we only record the honest exit reason.
        exit_reason = emit_reason = "server_unavailable"
        raise
    except StuckExit as exc:
        # Honest terminal path: stuck recovery exhausted its escalation
        # ladder. This is a deliberate, clean stop — NOT a crash — so the
        # session records exit_reason="stuck_exit" (trace 2026-06-10: the
        # old SystemExit(2) here was recorded as "crash").
        exit_reason = emit_reason = "stuck_exit"
        print(f"Bot for {character!r} stopped: {exc} — manual intervention needed")
        raise typer.Exit(code=2) from exc
    except KeyboardInterrupt:
        exit_reason = emit_reason = "keyboard_interrupt"
        raise
    except httpx.HTTPError as exc:
        # A transport failure is transient and worth the supervisor
        # restarting; the learning store still records plain "crash" so its
        # existing vocabulary does not change.
        exit_reason = "crash"
        emit_reason = emit_reason_for(exc)
        raise
    finally:
        if emitter is not None:
            # A supervisor that has already killed this child leaves us with a
            # closed pipe. Nobody is listening for the exit event, so a failed
            # write is expected and not actionable — but letting it out of a
            # `finally` would REPLACE the exception we are propagating and
            # destroy the real exit diagnosis.
            with contextlib.suppress(OSError):
                emitter.emit_exit(emit_reason)
        store.end_session(exit_reason=exit_reason)
        store.close()
        if coordination is not None:
            coordination.close()


def _run_with_tui(
    player: GamePlayer, character: str,
    game_data_ttl_minutes: int = 30, refresh_game_data: bool = False,
) -> None:
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
    player.game_data = GameData.load(
        client, ttl_minutes=game_data_ttl_minutes, force_refresh=refresh_game_data)
    app = WatchApp(characters=[character], game_data=player.game_data,
                   api=APIWrapper(client))
    bridge = ThreadSafeBridge(app, app.update_snapshot, planning_handler=app.set_planning)
    player.set_cycle_observer(bridge.notify)
    player.set_planning_observer(bridge.notify_planning)

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
        # and re-raised below either way. A StuckExit is a deliberate stop,
        # not a crash — say so honestly.
        if isinstance(hook_args.exc_value, StuckExit):
            message = f"Bot stopped: {hook_args.exc_value}"
        elif isinstance(hook_args.exc_value, ServerUnavailableError):
            message = "Server unavailable — stopping bot."
        else:
            message = f"Bot worker thread crashed: {hook_args.exc_value!r}"
        with contextlib.suppress(RuntimeError):
            app.call_from_thread(app.exit, return_code=1, message=message)

    threading.excepthook = _bot_excepthook
    try:
        bot_thread.start()
        app.run()
    finally:
        threading.excepthook = previous_hook
    if crashes:
        # Print on the real terminal (after the alternate screen is gone),
        # then re-raise so play() records the honest exit_reason: "stuck_exit"
        # for a deliberate StuckExit stop, "server_unavailable" for a
        # maintenance page (run() renders it), "crash" for everything else.
        if isinstance(crashes[0], StuckExit):
            print(f"Bot for {character!r} stopped: {crashes[0]}")
        elif isinstance(crashes[0], ServerUnavailableError):
            # Clean stop: run() renders the maintenance page and exits 3.
            pass
        else:
            print(f"Bot worker thread for {character!r} crashed; traceback:")
            traceback.print_exception(crashes[0])
        raise crashes[0]
