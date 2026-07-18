"""Unit tests for the pure encyclopaedia index."""

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import ItemStats
from artifactsmmo_cli.tui.encyclopedia_index import (
    CATEGORY_ORDER,
    IndexEntry,
    build_index,
    rank_entries,
)


def _seed() -> GameData:
    gd = GameData()
    gd.items.stats["copper_dagger"] = ItemStats(
        code="copper_dagger", level=1, type_="weapon", subtype="dagger"
    )
    gd.items.stats["copper_ore"] = ItemStats(code="copper_ore", level=1, type_="resource")
    gd.monsters.levels["chicken"] = 1
    gd.monsters.hp["chicken"] = 60
    gd.recipes_catalog.resource_skill["copper_rocks"] = ("mining", 1)
    gd.recipes_catalog.crafting_recipes["copper_dagger"] = {"copper": 6}
    gd.recipes_catalog.craft_yields["copper_dagger"] = 1
    gd.world.npc_tiles["ge_trader"] = (5, 1)
    gd.world.workshop_locations["mining"] = (1, 2)
    gd._task_coin_rewards["kill_chickens"] = 25
    return gd


def test_categories_fixed_order_with_counts() -> None:
    idx = build_index(_seed())
    cats = idx.categories()
    assert [c for c, _ in cats] == list(CATEGORY_ORDER)
    counts = dict(cats)
    assert counts["item"] == 2
    assert counts["monster"] == 1
    assert counts["resource"] == 1
    assert counts["recipe"] == 1
    assert counts["npc"] == 1
    assert counts["location"] == 1  # mining workshop
    assert counts["task"] == 1


def test_entries_sorted_by_code() -> None:
    idx = build_index(_seed())
    items = idx.entries("item")
    assert [e.code for e in items] == ["copper_dagger", "copper_ore"]
    assert all(isinstance(e, IndexEntry) for e in items)


def test_lookup_hit_and_miss() -> None:
    idx = build_index(_seed())
    dagger = idx.lookup("item", "copper_dagger")
    assert dagger is not None
    assert dagger.kind == "item"
    assert idx.lookup("item", "no_such") is None
    chicken = idx.lookup("monster", "chicken")
    assert chicken is not None
    assert chicken.code == "chicken"


def test_rank_prefix_before_contains_case_insensitive() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "COPPER_O")
    assert [e.code for e in ranked] == ["copper_ore"]
    ranked2 = rank_entries(idx.entries("item"), "dagger")  # contains-only match
    assert [e.code for e in ranked2] == ["copper_dagger"]


def test_rank_empty_query_returns_all_in_order() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "   ")
    assert [e.code for e in ranked] == ["copper_dagger", "copper_ore"]


def test_search_text_covers_subtype() -> None:
    idx = build_index(_seed())
    ranked = rank_entries(idx.entries("item"), "dagger")
    assert ranked and ranked[0].code == "copper_dagger"
