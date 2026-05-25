"""Inventory pane: sorted item counts + equipped slots."""

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text
from textual.reactive import reactive
from textual.widgets import Static

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


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
        used = sum(s.inventory.values())
        max_ = s.inventory_max
        fill = used / max_ if max_ else 0.0
        header_color = "red" if fill > 0.9 else ("yellow" if fill > 0.7 else "white")
        header = Text(f"Inventory  {used}/{max_}", style=f"bold {header_color}")

        # Items sorted by qty desc
        items = Table(box=None, padding=(0, 1), show_header=False)
        items.add_column("qty", justify="right", style="cyan")
        items.add_column("code")
        for code, qty in sorted(s.inventory.items(), key=lambda kv: -kv[1]):
            items.add_row(str(qty), code)

        # Equipped slots
        equip_section = Text("\nEquipment", style="bold")
        equip = Table(box=None, padding=(0, 1), show_header=False)
        equip.add_column("slot", style="dim")
        equip.add_column("item")
        for slot, equipped in s.equipment.items():
            if equipped:
                equip.add_row(slot.replace("_slot", ""), equipped)

        return Group(header, items, equip_section, equip)
