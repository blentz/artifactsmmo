"""Pure per-entity detail views for the encyclopaedia, with navigable links.

Each `build_detail` branch reads only static `GameData` catalogs and returns a
Rich renderable plus the cross-reference `Ref`s the shell turns into a
navigable list. No Textual import; no fabricated data.
"""

from dataclasses import dataclass

from rich.console import RenderableType
from rich.table import Table

from artifactsmmo_cli.ai.game_data import GameData


class EncyclopediaDetailError(Exception):
    """Raised when asked to render a detail for an unknown category kind."""


@dataclass(frozen=True)
class Ref:
    """A navigable cross-reference to another encyclopaedia entity."""

    kind: str
    code: str
    label: str


@dataclass(frozen=True)
class DetailView:
    """A rendered detail plus its outbound navigable links."""

    renderable: RenderableType
    links: tuple[Ref, ...]


def _kv_table(title: str) -> Table:
    t = Table(box=None, padding=(0, 2), show_header=False, title=title)
    t.add_column("k", style="dim")
    t.add_column("v")
    return t


def _item_detail(game_data: GameData, code: str) -> DetailView:
    stats = game_data.items.stats.get(code)
    if stats is None:
        raise EncyclopediaDetailError(f"unknown item: {code}")
    t = _kv_table(code)
    t.add_row("level", str(stats.level))
    t.add_row("type", f"{stats.type_} / {stats.subtype}" if stats.subtype else stats.type_)
    if stats.attack:
        t.add_row("attack", ", ".join(f"{el} {v}" for el, v in sorted(stats.attack.items())))
    if stats.resistance:
        t.add_row("resist", ", ".join(f"{el} {v}" for el, v in sorted(stats.resistance.items())))
    if stats.hp_restore:
        t.add_row("heals", str(stats.hp_restore))
    if stats.hp_bonus:
        t.add_row("hp", f"+{stats.hp_bonus}")

    links: list[Ref] = []
    if code in game_data.recipes_catalog.crafting_recipes:
        links.append(Ref("recipe", code, "recipe"))
    for out, inputs in sorted(game_data.recipes_catalog.crafting_recipes.items()):
        if code in inputs:
            links.append(Ref("recipe", out, "used in"))
    return DetailView(renderable=t, links=tuple(links))


def build_detail(game_data: GameData, kind: str, code: str) -> DetailView:
    if kind == "item":
        return _item_detail(game_data, code)
    raise EncyclopediaDetailError(f"unknown kind: {kind}")
