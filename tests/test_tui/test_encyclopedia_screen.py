"""Pilot tests for the encyclopaedia modal shell."""

from textual.app import App, ComposeResult
from textual.widgets import Input, ListView, Static

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_detail import Ref
from artifactsmmo_cli.tui.screens.encyclopedia_screen import EncyclopediaScreen


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon", subtype="dagger"
    )
    gd.items.stats["copper"] = ItemStats(code="copper", level=1, type_="resource")
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    return gd


class _Host(App[None]):
    def __init__(self, gd: GameData) -> None:
        super().__init__()
        self._gd = gd

    def compose(self) -> ComposeResult:  # pragma: no cover - Textual harness
        yield from ()

    async def on_mount(self) -> None:
        await self.push_screen(EncyclopediaScreen(self._gd))


async def test_search_filters_entities() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen.query_one("#enc-search", Input).value = "dagger"
        await pilot.pause()
        entities = screen.query_one("#enc-entities", ListView)
        codes = [item.enc_code for item in entities.children]
        assert codes == ["copper_dagger"]


async def test_follow_link_pushes_nav() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper_dagger", ""))
        await pilot.pause()
        assert screen._nav[-1] == Ref("item", "copper_dagger", "")
        # detail lists a 'recipe' link for the craftable dagger
        links = screen.query_one("#enc-links", ListView)
        refs = [item.enc_ref for item in links.children]
        assert Ref("recipe", "copper_dagger", "recipe") in refs


async def test_back_pops_nav() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper", ""))
        screen._navigate(Ref("item", "copper_dagger", ""))
        await pilot.pause()
        screen.action_back()
        await pilot.pause()
        assert screen._nav[-1] == Ref("item", "copper", "")


async def test_back_is_noop_when_nav_empty() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        assert screen._nav == []
        screen.action_back()
        await pilot.pause()
        assert screen._nav == []


async def test_back_clears_detail_when_nav_becomes_empty() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper", ""))
        await pilot.pause()
        screen.action_back()
        await pilot.pause()
        assert screen._nav == []
        detail = screen.query_one("#enc-detail", Static)
        assert str(detail.content) == ""
        links = screen.query_one("#enc-links", ListView)
        assert list(links.children) == []


async def test_select_entity_pushes_nav_via_list_view() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        entities = screen.query_one("#enc-entities", ListView)
        await pilot.pause()
        item = next(i for i in entities.children if i.enc_code == "copper_dagger")
        index = list(entities.children).index(item)
        entities.post_message(ListView.Selected(entities, item, index))
        await pilot.pause()
        assert screen._nav[-1] == Ref("item", "copper_dagger", "")


async def test_select_link_pushes_nav_via_list_view() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper_dagger", ""))
        await pilot.pause()
        links = screen.query_one("#enc-links", ListView)
        item = next(i for i in links.children if i.enc_ref.kind == "recipe")
        index = list(links.children).index(item)
        links.post_message(ListView.Selected(links, item, index))
        await pilot.pause()
        assert screen._nav[-1] == item.enc_ref


async def test_category_switch_clears_populated_nav_search_detail() -> None:
    app = _Host(_seed())
    async with app.run_test() as pilot:
        screen = app.screen
        screen._navigate(Ref("item", "copper_dagger", ""))
        screen.query_one("#enc-search", Input).value = "cop"
        await pilot.pause()
        # precondition: state is actually populated before the switch
        assert screen._nav != []
        assert screen.query_one("#enc-search", Input).value != ""

        cats = screen.query_one("#enc-cats", ListView)
        target = next(i for i in cats.children if i.enc_kind == "recipe")
        index = list(cats.children).index(target)
        cats.index = index
        await pilot.pause()

        assert screen._active_kind == "recipe"
        assert screen._nav == []
        assert screen.query_one("#enc-search", Input).value == ""
        assert list(screen.query_one("#enc-links", ListView).children) == []
