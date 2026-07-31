"""MultiRun: build and run the `play --all` supervisor, with or without the TUI."""

import asyncio
import sys
from typing import Any

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.multi.character_supervisor import CharacterSupervisor
from artifactsmmo_cli.multi.child_event import ChildEvent, SnapshotEvent
from artifactsmmo_cli.multi.supervisor_pool import SupervisorPool
from artifactsmmo_cli.tui.app import WatchApp
from artifactsmmo_cli.utils.rate_budget import (
    BucketBudgets,
    parse_rate_limits,
    split_budget,
)


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

    def child_argv(self, character: str, budget: BucketBudgets) -> list[str]:
        """The command line for one child. Never `--all` (that would fork-bomb
        the account) and never `--tui` (only the parent owns the terminal)."""
        argv = [sys.executable, "-m", "artifactsmmo_cli.main", "play", character,
                "--emit-events", "--rate-budget", budget.to_json()]
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
        budget = split_budget(parse_rate_limits(rates), children=len(characters))
        return SupervisorPool([
            CharacterSupervisor(
                character=name,
                argv=self.child_argv(name, budget),
                on_event=self._on_event,
            )
            for name in characters
        ])

    def _on_event(self, event: ChildEvent) -> None:
        if self._app is not None and isinstance(event, SnapshotEvent):
            self._app.update_snapshot(event.payload)

    def run(self) -> None:
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

        game_data = GameData.load(
            client, ttl_minutes=config.game_data_ttl_minutes,
            force_refresh=self._refresh_game_data)
        self._app = WatchApp(characters=characters, game_data=game_data, api=api)
        self._app.attach_pool(pool)
        self._app.run()

    async def _run_headless(self, pool: SupervisorPool) -> None:
        await pool.run()
