"""Browsable per-turn fight transcripts (toggled with 'f').

Two panes: the fight list on the left, the selected fight's verbatim transcript
on the right. Session fights arrive on CycleSnapshot and need no network; older
fights are pulled from GET /my/logs/{name} on demand.

The two sources CANNOT be matched against each other: they stamp the same fight
from different moments (measured ~66 ms apart, one offset-aware and one naive),
so no key dedupes a session capture against its server-log twin. Overlap is
therefore prevented structurally — backfill is clamped to strictly before
`session_floor`, the oldest fight this session watched — rather than matched
heuristically after the fact.
"""

import datetime
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
        # OLDEST fight this session watched — the point below which every row
        # came from the server log. Backfill is clamped to strictly before it,
        # which is why the two sources can never present the same fight twice.
        self.session_floor: datetime.datetime | None = None
        self.merge(records)
        self._lower_floor(records)

    def _lower_floor(self, records: Iterable[FightRecord]) -> None:
        """Extend the session boundary down to cover `records`."""
        for rec in records:
            if self.session_floor is None or rec.instant < self.session_floor:
                self.session_floor = rec.instant

    def merge(self, records: Iterable[FightRecord]) -> None:
        """Add records, dropping same-source repeats, and re-sort newest first.

        Dedup is on the raw `started_at`, which is only meaningful WITHIN one
        source (re-fetching a page). It cannot match a session capture against
        its /my/logs twin — those differ by tens of milliseconds — so overlap is
        prevented by `session_floor` in `load_older_sync` instead of matched
        here. Ordering goes through `instant`: the sources mix offset-aware and
        naive stamps, which sort wrongly as raw strings.
        """
        seen = {r.started_at for r in self.records}
        for rec in records:
            if rec.started_at not in seen:
                self.records.append(rec)
                seen.add(rec.started_at)
        self.records.sort(key=lambda r: r.instant, reverse=True)

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
        self._lower_floor([snap.fight])
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
        # Clamp to strictly before the session boundary. A fight this session
        # already captured also sits in the server log under a DIFFERENT stamp
        # (~66 ms off, and offset-aware where the log is naive), so letting it
        # through would show that fight twice — no key can match the two.
        older = [r for r in fetched
                 if self.session_floor is None or r.instant < self.session_floor]
        skipped = len(fetched) - len(older)
        before = len(self.records)
        self.merge(older)
        added = len(self.records) - before
        # Never silently truncate: say what the clamp dropped.
        note = f", {skipped} skipped (already seen this session)" if skipped else ""
        self.status_text = f"loaded {added} older fights{note}"
