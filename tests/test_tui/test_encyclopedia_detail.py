"""Unit tests for pure encyclopaedia detail rendering + link soundness."""

import pytest
from rich.console import Console

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_detail import (
    DetailView,
    EncyclopediaDetailError,
    Ref,
    build_detail,
)


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger",
        level=1,
        type_="weapon",
        subtype="dagger",
        crafting_skill="weaponcrafting",
        crafting_level=1,
        attack={"fire": 6},
    )
    gd.items.stats["copper"] = ItemStats(code="copper", level=1, type_="resource")
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    return gd


def _render(view: DetailView) -> str:
    console = Console(width=80, record=True)
    console.print(view.renderable)
    return console.export_text()


def test_item_detail_shows_stats_and_links_to_recipe() -> None:
    view = build_detail(_seed(), "item", "copper_dagger")
    text = _render(view)
    assert "copper_dagger" in text
    assert "weapon" in text
    assert "fire" in text
    # craftable -> link to its recipe; input 'copper' surfaced via the recipe branch
    assert Ref("recipe", "copper_dagger", "recipe") in view.links


def test_item_used_in_links_back() -> None:
    view = build_detail(_seed(), "item", "copper")
    # 'copper' is an input of copper_dagger's recipe -> used-in link
    assert Ref("recipe", "copper_dagger", "used in") in view.links


def test_unknown_kind_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed(), "spaceship", "x")


def test_unknown_item_code_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed(), "item", "does_not_exist")


def test_item_detail_shows_resistance_and_hp_fields() -> None:
    gd = _seed()
    gd.items.stats["iron_shield"] = ItemStats(
        code="iron_shield",
        level=5,
        type_="shield",
        resistance={"water": 10},
        hp_restore=20,
        hp_bonus=15,
    )
    view = build_detail(gd, "item", "iron_shield")
    text = _render(view)
    assert "water" in text
    assert "20" in text
    assert "+15" in text


def _seed_world() -> GameData:
    gd = _seed()
    gd.monsters.levels["chicken"] = 1
    gd.monsters.hp["chicken"] = 60
    gd.monsters.attack["chicken"] = {"fire": 4}
    gd.monsters.resistance["chicken"] = {"water": 2}
    gd.monsters.critical_strike["chicken"] = 5
    gd.monsters.lifesteal["chicken"] = 0
    gd.monsters.drops["chicken"] = [("copper", 100, 1, 1)]
    gd.recipes_catalog.resource_skill["copper_rocks"] = ("mining", 1)
    gd.recipes_catalog.resource_drops_full["copper_rocks"] = [("copper", 80, 1, 1)]
    gd.recipes_catalog.locations["copper_rocks"] = [(2, 0)]
    return gd


def test_monster_detail_links_to_drops() -> None:
    view = build_detail(_seed_world(), "monster", "chicken")
    text = _render(view)
    assert "chicken" in text
    assert "60" in text  # hp
    assert Ref("item", "copper", "drops") in view.links


def test_resource_detail_links_to_drops() -> None:
    view = build_detail(_seed_world(), "resource", "copper_rocks")
    text = _render(view)
    assert "mining" in text
    assert Ref("item", "copper", "drops") in view.links


def test_recipe_detail_links_inputs_and_output() -> None:
    view = build_detail(_seed_world(), "recipe", "copper_dagger")
    text = _render(view)
    assert "weaponcrafting" in text
    assert Ref("item", "copper_dagger", "makes") in view.links
    assert Ref("item", "copper", "needs 6") in view.links


def test_unknown_monster_code_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed_world(), "monster", "does_not_exist")


def test_unknown_resource_code_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed_world(), "resource", "does_not_exist")


def test_unknown_recipe_code_raises() -> None:
    with pytest.raises(EncyclopediaDetailError):
        build_detail(_seed_world(), "recipe", "does_not_exist")


def test_monster_detail_shows_lifesteal_and_locations() -> None:
    gd = _seed_world()
    gd.monsters.lifesteal["chicken"] = 10
    gd.monsters.locations["chicken"] = [(3, 4)]
    view = build_detail(gd, "monster", "chicken")
    text = _render(view)
    assert "10%" in text
    assert "(3,4)" in text
