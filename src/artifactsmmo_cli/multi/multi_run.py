"""MultiRun: build and run the `play --all` supervisor, with or without the TUI."""

import asyncio
import sys
import tempfile
import uuid
from functools import partial
from pathlib import Path
from typing import Any

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.learning_db_path import default_learn_db_path
from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_event import ChildEvent, PlanningEvent, SnapshotEvent
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.utils.rate_budget import (
    BucketBudgets,
    parse_rate_limits,
)
from artifactsmmo_cli.utils.rate_governor import RateGovernor
from artifactsmmo_cli.utils.request_log import RequestLog


class MultiRun:
    """Owns the `play --all` lifecycle: discover the roster, read and divide the
    rate budget, spawn a supervised child per character, and present them.

    The supervisor and Textual share one asyncio loop, so events go straight
    from a child's pipe to the app -- the single-character path's thread
    bridge is not needed here.
    """

    def __init__(self, verbose: bool, dry_run: bool, trace: bool, learn: bool,
                 learn_db: str | None, tui: bool, refresh_game_data: bool) -> None:
        self._verbose = verbose
        self._dry_run = dry_run
        self._trace = trace
        self._learn = learn
        self._learn_db = learn_db
        self._tui = tui
        self._refresh_game_data = refresh_game_data
        self._app: WatchApp | None = None
        # The ONE on-disk path every child's CoordinationStore opens, computed
        # lazily and memoized for the life of this MultiRun — see
        # `_coordination_db_path`. `_owns_coordination_db` is True only when
        # THIS MultiRun generated a fresh temp path (as opposed to reusing the
        # persisted `--learn` DB path), which is what `_cleanup_coordination_db`
        # checks before ever deleting anything: the persisted learning DB must
        # never be removed, only a temp file this instance itself created.
        self._coordination_db: str | None = None
        self._owns_coordination_db = False

    def _coordination_db_path(self) -> str:
        """The shared coordination DB path every child receives via
        `--coordination-db`, computed once and memoized.

        Coordination is cross-PROCESS by construction (children are separate
        subprocesses), so it needs a real file on disk -- a `:memory:` SQLite
        DB is private to the connection that opened it and could never
        coordinate with a sibling (the same reasoning `commands/play.py`
        applies to the single-character path). When `--learn` is on, every
        child already opens the SAME learning DB file, so coordination just
        reuses it. When `--learn` is off, this generates a fresh, unique path
        in the OS temp directory -- WITHOUT creating the file: the first
        child's own `CoordinationStore.__init__` creates it lazily
        (`SQLModel.metadata.create_all`), exactly like any other SQLite path
        in this codebase. Pure path computation with no filesystem I/O here
        keeps this method safe to call from tests that build argv/pools
        directly without ever spawning a real child or calling `run()`."""
        if self._coordination_db is not None:
            return self._coordination_db
        if self._learn:
            self._coordination_db = self._learn_db or default_learn_db_path()
            self._owns_coordination_db = False
        else:
            temp_path = Path(tempfile.gettempdir()) / f"artifactsmmo-coordination-{uuid.uuid4().hex}.db"
            self._coordination_db = str(temp_path)
            self._owns_coordination_db = True
        return self._coordination_db

    def _cleanup_coordination_db(self) -> None:
        """Remove the temp coordination DB (and its WAL/SHM sidecars) this
        MultiRun generated, if any. A no-op when coordination reused the
        persisted `--learn` DB path (`_owns_coordination_db` is False) --
        that file must survive for the next session -- or when
        `_coordination_db_path` was never called at all."""
        if not self._owns_coordination_db or self._coordination_db is None:
            return
        for suffix in ("", "-wal", "-shm"):
            Path(f"{self._coordination_db}{suffix}").unlink(missing_ok=True)

    def child_argv(self, character: str, budget: BucketBudgets, fleet_size: int) -> list[str]:
        """The command line for one child. Never `--all` (that would fork-bomb
        the account) and never `--tui` (only the parent owns the terminal)."""
        argv = [sys.executable, "-m", "artifactsmmo_cli.main", "play", character,
                "--emit-events", "--rate-budget", budget.to_json(),
                "--fleet-size", str(fleet_size),
                "--coordination-db", self._coordination_db_path()]
        if self._verbose:
            argv.append("--verbose")
        if self._dry_run:
            argv.append("--dry-run")
        if self._trace:
            argv.append("--trace")
        if self._learn:
            argv.append("--learn")
            if self._learn_db is not None:
                argv += ["--learn-db", self._learn_db]
        if self._refresh_game_data:
            argv.append("--refresh-game-data")
        return argv

    def build_pool(self, characters: list[str], rates: dict[str, Any]) -> SupervisorPool:
        if not characters:
            raise ValueError("account has no characters to play")
        # The WHOLE budget goes to every child: the children police it together
        # through the request log in the shared coordination DB, so an idle
        # child's share is spendable by a busy one. A static even split left
        # each child 60 account requests/hour; one GE-order poll per cycle
        # spent most of that and parked three children for 18 minutes
        # (2026-09-25).
        limits = parse_rate_limits(rates)
        return SupervisorPool(
            [
                CharacterSupervisor(
                    character=name,
                    argv=self.child_argv(name, limits, len(characters)),
                    on_event=self._on_event,
                    # `partial` binds `name` by VALUE right now, unlike a lambda
                    # closing over the loop variable `name` (which would report
                    # every child under whichever name the loop variable held
                    # last by the time a callback actually fired).
                    on_stderr=partial(self._on_stderr, name),
                )
                for name in characters
            ],
            # The children are spaced by the ACCOUNT bucket's own sustainable
            # pace, read from /my/rates -- never a guessed constant. That bucket
            # is the tightest the API declares, and pacing the one bucket every
            # child shares is what keeps a simultaneous launch from turning the
            # unmetered startup game-data load into boot-time 429s. (Its
            # `load_ge_orders` leg is live-only, so even a warm-cache child pages
            # it -- 17 requests when measured 2026-09-21 -- but that leg bills
            # DATA, not account: see supervisor_pool's stagger note.) The UNDIVIDED
            # limits are the right input: the stagger paces children against
            # each other in the one bucket they all share.
            stagger_seconds=limits.account.sustainable_interval(),
            on_stagger=self._on_stagger,
        )

    def _on_event(self, event: ChildEvent) -> None:
        if self._app is None:
            return
        if isinstance(event, SnapshotEvent):
            self._app.update_snapshot(event.payload)
        elif isinstance(event, PlanningEvent) and event.character == self._app.focused_character:
            # `set_planning` drives ONE overlay, not a per-character one, so
            # only the focused child's planning state should reach it -- a
            # background child's planning flicker must not fight the overlay
            # for whichever character the operator is actually watching.
            self._app.set_planning(event.active)

    def _on_stderr(self, character: str, line: str) -> None:
        """Headless mode has no TUI to show a dead child's log in, so per the
        design doc it streams each child's stderr live, prefixed with the
        character name. In TUI mode this would corrupt the alternate screen,
        so it stays quiet there -- the roster/status pane surfaces the same
        information instead."""
        if not self._tui:
            print(f"[{character}] {line}", file=sys.stderr)

    def _on_stagger(self, character: str, wait_seconds: float) -> None:
        """Announce a child's rate-stagger hold, mirroring `_on_stderr`'s
        convention: printed with the same `[Name]` prefix to the real stderr
        in headless mode, quiet in TUI mode for the same alternate-screen
        reason. This is the parent's own line -- the child process behind
        `character` does not exist yet, so nothing else could emit it."""
        if not self._tui:
            print(f"[{character}] holding {wait_seconds:g}s before start "
                  f"(rate stagger)", file=sys.stderr)

    def run(self) -> None:
        # The whole body is wrapped so `_cleanup_coordination_db` runs on
        # EVERY exit path -- normal return (either branch below), a raised
        # RuntimeError from the two API guards, a supervisor pool failure
        # propagating out of `_run_headless`, or a WatchApp crash. It does
        # NOT run on a hard kill (SIGKILL) or a crash of the interpreter
        # itself -- no user-space Python code can react to either; see
        # `_cleanup_coordination_db`'s docstring and the Task 11 report for
        # the honest residual gap.
        try:
            config = Config.from_token_file()
            client = ClientManager().client
            api = APIWrapper(client)

            characters_response = api.get_my_characters()
            if characters_response is None:
                raise RuntimeError(
                    "GET /my/characters returned no data -- cannot discover the "
                    "account's characters")
            characters = [c.name for c in characters_response.data]

            rates_response = api.get_rate_limits()
            if rates_response is None:
                raise RuntimeError(
                    "GET /my/rates returned no data -- cannot divide the account's "
                    "rate budget across children")
            rates = rates_response.to_dict()

            pool = self.build_pool(characters, rates)
            if not self._tui:
                asyncio.run(self._run_headless(pool))
                return

            # The TUI's map preload bills the same per-IP budget the children
            # share, so it goes through the same request log as they do.
            limits = parse_rate_limits(rates)
            request_log = RequestLog(self._coordination_db_path())
            try:
                game_data = GameData.load(
                    client, ttl_minutes=config.game_data_ttl_minutes,
                    force_refresh=self._refresh_game_data,
                    acquire_data=RateGovernor(limits.data, 1, request_log, "data").acquire,
                    acquire_account=RateGovernor(limits.account, 1, request_log, "account").acquire)
            finally:
                request_log.close()
            self._app = WatchApp(characters=characters, game_data=game_data, api=api)
            self._app.attach_pool(pool)
            self._app.run()
        finally:
            self._cleanup_coordination_db()

    async def _run_headless(self, pool: SupervisorPool) -> None:
        await pool.run()
