"""Browsable per-turn fight transcripts (toggled with 'f').

Two panes: the fight list on the left, the selected fight's verbatim transcript
on the right. Session fights arrive on CycleSnapshot and need no network; older
fights are pulled from GET /my/logs/{name} on demand and merged in, deduped on
the server-side `started_at` the two sources share.
"""

from collections.abc import Callable, Iterable
from typing import Any

from textual.app import ComposeResult
from textual.containers import Horizontal
from textual.screen import Screen
from textual.widgets import Label, ListItem, ListView, RichLog, Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.ai.fight_record import FightRecord
from artifactsmmo_cli.tui.fight_format import fight_detail_lines, fight_row_label


class FightScreen(Screen[None]):
    """Modal fight browser. Dismiss with 'f' or Escape."""

    DEFAULT_CSS = """
    #fight-modal #fight-cols { width: 1fr; height: 1fr; }
    #fight-modal #fight-list { width: 44; border: solid white; }
    #fight-modal #fight-detail { width: 1fr; border: solid white; }
    #fight-modal #fight-status { height: 1; }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("f", "dismiss", "Back"),
        ("m", "load_older", "Load older"),
    ]

    def __init__(self, records: Iterable[FightRecord], character: str,
                 fetch_older: Callable[[int], list[FightRecord]] | None = None,
                 **kwargs: Any) -> None:
        super().__init__(id="fight-modal", **kwargs)
        self._character = character
        self._fetch_older = fetch_older
        self._next_page = 1
        self.status_text = ""
        self.records: list[FightRecord] = []
        self.merge(records)
        # The newest record present at construction: the boundary between what
        # this session watched and what was pulled from the server log.
        self.session_started_at: str | None = (
            self.records[0].started_at if self.records else None)

    def merge(self, records: Iterable[FightRecord]) -> None:
        """Add records, dropping any whose `started_at` is already present, and
        re-sort newest first. Existing records win: a session capture carries
        `hp_before`, which the backfilled form of the same fight cannot."""
        seen = {r.started_at for r in self.records}
        for rec in records:
            if rec.started_at not in seen:
                self.records.append(rec)
                seen.add(rec.started_at)
        self.records.sort(key=lambda r: r.started_at, reverse=True)

    def detail_lines(self, index: int) -> list[str]:
        if not self.records:
            return ["No fights recorded yet."]
        return fight_detail_lines(self.records[index])

    def compose(self) -> ComposeResult:
        with Horizontal(id="fight-cols"):
            yield ListView(id="fight-list")
            yield RichLog(wrap=True, markup=True, id="fight-detail")
        yield Static("", id="fight-status")

    def on_mount(self) -> None:
        self._refresh_list()
        self._render_detail(0)
        # Focus the list, not the transcript pane, so up/down browse fights the
        # moment the modal opens instead of scrolling the detail RichLog.
        self.query_one("#fight-list", ListView).focus()

    def _refresh_list(self) -> None:
        listing = self.query_one("#fight-list", ListView)
        # ListView.clear() drops the highlight, so hold the caller's row and put
        # it back — otherwise a fight merging in mid-browse would yank the
        # selection to the top. A fresh list seeds row 0 so it matches the detail
        # pane; without it the highlight reads as absent and the first arrow
        # press is spent selecting rather than moving.
        previous = listing.index
        listing.clear()
        for rec in self.records:
            listing.append(ListItem(Label(fight_row_label(rec))))
        if self.records:
            listing.index = (
                previous if previous is not None and previous < len(self.records) else 0)

    def _render_detail(self, index: int) -> None:
        detail = self.query_one("#fight-detail", RichLog)
        detail.clear()
        for line in self.detail_lines(index):
            detail.write(line)

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.index is not None:
            self._render_detail(event.list_view.index)

    def sync_ui(self) -> None:
        """Push current state into the widgets. EVENT-LOOP THREAD ONLY.

        Textual resolves widgets through the `active_app` ContextVar, which is
        unset on a worker thread — touching a widget there raises LookupError.
        Everything that mutates the UI funnels through here so the thread body
        can marshal one call back onto the loop.
        """
        if not self.is_mounted:
            return
        self.query_one("#fight-status", Static).update(self.status_text)
        self._refresh_list()

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        """A fight landed while the modal was open."""
        if snap.fight is None:
            return
        self.merge([snap.fight])
        self.session_started_at = self.records[0].started_at
        self.sync_ui()

    def action_load_older(self) -> None:
        """Fetch the next page of server history off the event loop.

        The generated client call is synchronous; running it inline would freeze
        the UI for the duration of the request.
        """
        self.run_worker(self._load_older_worker, thread=True)

    def _load_older_worker(self) -> None:
        """Worker-thread body: fetch, then hand the UI touch back to the loop."""
        self.load_older_sync()
        self.app.call_from_thread(self.sync_ui)

    def load_older_sync(self) -> None:
        """Fetch, convert, merge, and record status. Touches NO widgets, so it is
        safe both on a worker thread and when called directly in tests.

        The `except RuntimeError` is the SINGLE error-handling level for the
        backfill: the failure is surfaced in the status bar and the page counter
        is deliberately NOT advanced, so pressing 'm' again retries the same
        page. There is no fallback path — an empty page and a failed request
        report differently rather than both showing an empty list.
        """
        if self._fetch_older is None:
            return
        page = self._next_page
        try:
            fetched = self._fetch_older(page)
        except RuntimeError as exc:
            self.status_text = f"backfill failed: {exc}"
            return
        self._next_page = page + 1
        if not fetched:
            self.status_text = f"no older fights on page {page}"
            return
        before = len(self.records)
        self.merge(fetched)
        self.status_text = f"loaded {len(self.records) - before} older fights"
