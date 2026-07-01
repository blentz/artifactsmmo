"""Shared item-table builder tests (no Textual app needed)."""

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_bank_items, build_inventory_items


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=0, y=0, level=5, xp=50, max_xp=500, hp=100, max_hp=100, gold=10,
        selected_goal="g", action="a", outcome="ok",
        inventory={"iron_ore": 5, "ash_wood": 2}, inventory_max=20,
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _text(renderable) -> str:
    console = Console(no_color=True, width=100)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


class TestBuildInventoryItems:
    def test_header_shows_counts(self):
        assert "7/20" in _text(build_inventory_items(_snap()))  # 5 + 2 = 7

    def test_items_listed(self):
        out = _text(build_inventory_items(_snap()))
        assert "iron_ore" in out and "ash_wood" in out

    def test_items_sorted_qty_desc(self):
        out = _text(build_inventory_items(_snap(inventory={"gem": 1, "iron": 10, "wood": 5})))
        assert out.find("iron") < out.find("wood") < out.find("gem")

    def test_no_equipment_section(self):
        assert "Equipment" not in _text(build_inventory_items(_snap()))

    def test_zero_max_no_error(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=0)))

    def test_empty_inventory(self):
        _text(build_inventory_items(_snap(inventory={}, inventory_max=20)))


class TestBuildBankItems:
    def test_none_shows_waiting(self):
        out = _text(build_bank_items(_snap(bank_items=None)))
        assert "waiting" in out.lower() and "Bank" in out

    def test_populated_lists_items_and_count(self):
        out = _text(build_bank_items(_snap(bank_items={"gold_ore": 3, "topaz": 1})))
        assert "gold_ore" in out and "topaz" in out
        assert "2 items" in out

    def test_sorted_qty_desc(self):
        out = _text(build_bank_items(_snap(bank_items={"a": 1, "b": 9, "c": 5})))
        assert out.find(" b") < out.find(" c") < out.find(" a")

    def test_empty_dict_zero_items(self):
        out = _text(build_bank_items(_snap(bank_items={})))
        assert "0 items" in out
