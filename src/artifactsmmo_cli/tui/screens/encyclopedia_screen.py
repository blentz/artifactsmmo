"""Browseable, searchable game-data encyclopaedia modal (toggled with 'e')."""

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import Screen
from textual.widgets import Input, ListView, Static

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.encyclopedia_detail import DetailView, Ref, build_detail
from artifactsmmo_cli.tui.encyclopedia_index import (
    EncyclopediaIndex,
    build_index,
    rank_entries,
)
from artifactsmmo_cli.tui.screens.encyclopedia_row_items import (
    CategoryItem,
    EntityItem,
    LinkItem,
)


class EncyclopediaScreen(Screen[None]):
    """Three-pane catalog browser: categories | search+entities | detail+links."""

    DEFAULT_CSS = """
    #encyclopedia-modal #enc-cols { width: 1fr; height: 1fr; }
    #encyclopedia-modal #enc-cats { width: 24; border: solid white; }
    #encyclopedia-modal #enc-mid { width: 1fr; }
    #encyclopedia-modal #enc-search { border: solid white; }
    #encyclopedia-modal #enc-entities { border: solid white; height: 1fr; }
    #encyclopedia-modal #enc-right { width: 2fr; border: solid white; }
    #encyclopedia-modal #enc-links { height: auto; max-height: 40%; }
    """

    BINDINGS = [
        ("escape", "dismiss", "Back"),
        ("e", "dismiss", "Back"),
        ("backspace", "back", "Back"),
    ]

    def __init__(self, game_data: GameData) -> None:
        super().__init__(id="encyclopedia-modal")
        self._game_data = game_data
        self._index: EncyclopediaIndex = build_index(game_data)
        self._active_kind: str = ""
        self._nav: list[Ref] = []

    def compose(self) -> ComposeResult:
        with Horizontal(id="enc-cols"):
            with ListView(id="enc-cats"):
                for kind, count in self._index.categories():
                    yield CategoryItem(kind, f"{kind} ({count})")
            with Vertical(id="enc-mid"):
                yield Input(placeholder="search", id="enc-search")
                yield ListView(id="enc-entities")
            with Vertical(id="enc-right"):
                yield VerticalScroll(Static("", id="enc-detail"))
                yield ListView(id="enc-links")

    def on_mount(self) -> None:
        cats = self._index.categories()
        if cats:
            self._active_kind = cats[0][0]
            self._refill_entities("")

    def _refill_entities(self, query: str) -> None:
        entities = self.query_one("#enc-entities", ListView)
        entities.clear()
        for entry in rank_entries(self._index.entries(self._active_kind), query):
            entities.append(EntityItem(entry))

    def _render_detail(self, ref: Ref) -> None:
        view: DetailView = build_detail(self._game_data, ref.kind, ref.code)
        self.query_one("#enc-detail", Static).update(view.renderable)
        links = self.query_one("#enc-links", ListView)
        links.clear()
        for link in view.links:
            links.append(LinkItem(link))

    def _navigate(self, ref: Ref) -> None:
        self._nav.append(ref)
        self._render_detail(ref)

    def action_back(self) -> None:
        if not self._nav:
            return
        self._nav.pop()
        if self._nav:
            self._render_detail(self._nav[-1])
        else:
            self.query_one("#enc-detail", Static).update("")
            self.query_one("#enc-links", ListView).clear()

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.list_view.id == "enc-cats" and isinstance(event.item, CategoryItem):
            self._active_kind = event.item.enc_kind
            self._nav.clear()
            self.query_one("#enc-search", Input).value = ""
            self.query_one("#enc-detail", Static).update("")
            self.query_one("#enc-links", ListView).clear()
            self._refill_entities("")

    def on_list_view_selected(self, event: ListView.Selected) -> None:
        item = event.item
        if isinstance(item, EntityItem):
            self._navigate(Ref(item.enc_kind, item.enc_code, ""))
        elif isinstance(item, LinkItem):
            self._navigate(item.enc_ref)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id == "enc-search":
            self._refill_entities(event.value)
