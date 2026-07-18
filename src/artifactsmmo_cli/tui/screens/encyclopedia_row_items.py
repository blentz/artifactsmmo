"""Trivial ListItem row adapters for the encyclopaedia's three panes."""

from textual.widgets import Label, ListItem

from artifactsmmo_cli.tui.encyclopedia_detail import Ref
from artifactsmmo_cli.tui.encyclopedia_index import IndexEntry


class CategoryItem(ListItem):
    def __init__(self, kind: str, label: str) -> None:
        super().__init__(Label(label))
        self.enc_kind = kind


class EntityItem(ListItem):
    def __init__(self, entry: IndexEntry) -> None:
        super().__init__(Label(entry.display))
        self.enc_kind = entry.kind
        self.enc_code = entry.code


class LinkItem(ListItem):
    def __init__(self, ref: Ref) -> None:
        super().__init__(Label(f"{ref.code}  ({ref.label})" if ref.label else ref.code))
        self.enc_ref = ref
