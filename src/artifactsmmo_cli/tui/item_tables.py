"""Shared item-table renderers used by the inventory pane and character modal."""

from rich.console import Group, RenderableType
from rich.table import Table
from rich.text import Text

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot


def _item_table(items: dict[str, int]) -> Table:
    table = Table(box=None, padding=(0, 1), show_header=False)
    table.add_column("qty", justify="right", style="cyan")
    table.add_column("code")
    for code, qty in sorted(items.items(), key=lambda kv: -kv[1]):
        table.add_row(str(qty), code)
    return table


def build_inventory_items(snap: CycleSnapshot) -> RenderableType:
    """Colored inventory header + qty/code table (qty-desc). Items only."""
    used = sum(snap.inventory.values())
    max_ = snap.inventory_max
    fill = used / max_ if max_ else 0.0
    color = "red" if fill > 0.9 else ("yellow" if fill > 0.7 else "white")
    header = Text(f"Inventory  {used}/{max_}", style=f"bold {color}")
    return Group(header, _item_table(snap.inventory))


def build_bank_items(snap: CycleSnapshot) -> RenderableType:
    """Bank header + qty/code table (qty-desc), or a waiting placeholder when
    the bank has not been synced yet (bank_items is None)."""
    if snap.bank_items is None:
        return Text("Bank — waiting for sync…")
    header = Text(f"Bank  {len(snap.bank_items)} items", style="bold")
    return Group(header, _item_table(snap.bank_items))
