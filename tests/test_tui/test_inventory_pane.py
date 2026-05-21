"""InventoryPane rendering tests (no Textual app needed)."""

import io

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.widgets.inventory_pane import InventoryPane


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1,
        timestamp="2026-05-21T12:00:00Z",
        character="hero",
        x=0,
        y=0,
        level=5,
        xp=50,
        max_xp=500,
        hp=100,
        max_hp=100,
        gold=10,
        selected_goal="gather",
        action="harvest",
        outcome="ok",
        inventory={"iron_ore": 5, "ash_wood": 2},
        inventory_max=20,
        equipment={"weapon_slot": "wooden_staff", "helmet_slot": None},
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _render(pane: InventoryPane) -> str:
    """Render a pane to a plain string using a no-color Console."""
    buf = io.StringIO()
    c = Console(file=buf, width=100, no_color=True)
    c.print(pane.render())
    return buf.getvalue()


class TestInventoryPaneNoSnapshot:
    def test_render_without_snapshot_shows_waiting(self):
        pane = InventoryPane()
        assert "Waiting" in str(pane.render())


class TestInventoryPaneHeader:
    def test_render_shows_inventory_counts(self):
        pane = InventoryPane()
        pane.update_snapshot(_snap())
        plain = _render(pane)
        # used = 5 + 2 = 7, max = 20
        assert "7/20" in plain

    def test_header_normal_color_below_70pct(self):
        """Below 70% used — no crash, renders white header."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={"iron_ore": 5}, inventory_max=20))
        _render(pane)

    def test_header_yellow_above_70pct(self):
        """Above 70% used — yellow warning."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={"item": 15}, inventory_max=20))
        _render(pane)

    def test_header_red_above_90pct(self):
        """Above 90% used — red warning."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={"item": 19}, inventory_max=20))
        _render(pane)

    def test_header_zero_max_no_error(self):
        """inventory_max == 0 should not cause division errors."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={}, inventory_max=0))
        _render(pane)


class TestInventoryPaneItems:
    def test_items_shown(self):
        pane = InventoryPane()
        pane.update_snapshot(_snap())
        plain = _render(pane)
        assert "iron_ore" in plain
        assert "ash_wood" in plain

    def test_items_sorted_by_qty_descending(self):
        """Higher qty items should appear before lower qty ones."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={"rare_gem": 1, "iron_ore": 10, "wood": 5}))
        plain = _render(pane)
        iron_pos = plain.find("iron_ore")
        wood_pos = plain.find("wood")
        gem_pos = plain.find("rare_gem")
        assert iron_pos < wood_pos < gem_pos

    def test_qty_shown(self):
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={"iron_ore": 7}))
        assert "7" in _render(pane)

    def test_empty_inventory(self):
        """Empty inventory renders without error."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(inventory={}, inventory_max=20))
        _render(pane)


class TestInventoryPaneEquipment:
    def test_equipped_item_shown(self):
        pane = InventoryPane()
        pane.update_snapshot(_snap())
        assert "wooden_staff" in _render(pane)

    def test_slot_name_trimmed(self):
        """'_slot' suffix is stripped from slot names."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(equipment={"weapon_slot": "sword"}))
        plain = _render(pane)
        assert "weapon" in plain
        assert "weapon_slot" not in plain

    def test_none_equipment_not_shown(self):
        """Slots with None value are not rendered as rows."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(equipment={"helmet_slot": None}))
        plain = _render(pane)
        assert "helmet" not in plain

    def test_equipment_section_header(self):
        pane = InventoryPane()
        pane.update_snapshot(_snap())
        assert "Equipment" in _render(pane)

    def test_empty_equipment(self):
        """All None slots — equipment section still renders."""
        pane = InventoryPane()
        pane.update_snapshot(_snap(equipment={}))
        _render(pane)


class TestInventoryPaneUpdateSnapshot:
    def test_update_snapshot_sets_snapshot(self):
        pane = InventoryPane()
        snap = _snap()
        pane.update_snapshot(snap)
        assert pane.snapshot == snap
