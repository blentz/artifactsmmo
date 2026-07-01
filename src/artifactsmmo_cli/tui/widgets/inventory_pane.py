"""Inventory pane: sorted item counts + equipped slots."""

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.item_tables import build_inventory_items


class InventoryPane(Static):
    snapshot: reactive[CycleSnapshot | None] = reactive(None)

    def update_snapshot(self, snap: CycleSnapshot) -> None:
        self.snapshot = snap

    def render(self) -> RenderableType:
        snap = self.snapshot
        if snap is None:
            return Text("Waiting...")
        return self._render_inventory(snap)

    def _render_inventory(self, s: CycleSnapshot) -> Group:
        items = build_inventory_items(s)

        equip_section = Text("\nEquipment", style="bold")
        equip = Table(box=None, padding=(0, 1), show_header=False)
        equip.add_column("slot", style="dim")
        equip.add_column("item")
        for slot, equipped in s.equipment.items():
            if equipped:
                equip.add_row(slot.replace("_slot", ""), equipped)

        return Group(items, equip_section, equip)
