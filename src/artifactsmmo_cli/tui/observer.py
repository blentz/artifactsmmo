"""Thread-safe bridge: bot worker thread → Textual main thread."""

from collections.abc import Callable

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


class ThreadSafeBridge:
    """Wrap an Textual App's call_from_thread for the bot's cycle_observer.

    The bot calls `bridge.notify(snap)` from its worker thread; the bridge
    forwards to the TUI app on the main thread (Textual's threading rule:
    every widget mutation must go through call_from_thread).
    """

    def __init__(self, app, handler: Callable[[CycleSnapshot], None]) -> None:
        self._app = app
        self._handler = handler

    def notify(self, snap: CycleSnapshot) -> None:
        # Textual's App.call_from_thread is the documented escape hatch.
        # Falls back to direct invocation if call_from_thread isn't
        # available (e.g. tests using a stub app).
        call_from_thread = getattr(self._app, "call_from_thread", None)
        if call_from_thread is None:
            self._handler(snap)
        else:
            call_from_thread(self._handler, snap)
