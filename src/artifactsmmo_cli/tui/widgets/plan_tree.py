"""Interactive collapsible tree of the chosen objective's prerequisite plan.

Renders tuple[PlanTreeNode, ...] onto a Textual Tree, styling each label by
status/kind, and preserves the operator's expand/collapse choices by node key
across live snapshot rebuilds."""

from typing import Any

from rich.text import Text
from textual.widgets import Tree
from textual.widgets.tree import TreeNode

from artifactsmmo_cli.ai.cycle_snapshot import PlanTreeNode

_STYLE = {
    "met": "green",
    "unmet": "",
    "current": "bold yellow",
    "step": "cyan",
    "root_stub": "dim",
}


def _glyph(node: PlanTreeNode, chosen: bool) -> str:
    if chosen:
        return "●"                 # ● chosen root
    if node.kind in ("root_stub", "step"):
        return "•"                 # •
    if node.status == "current":
        return "▸"                 # ▸
    if node.status == "met":
        return "✔"                 # ✔
    return "○"                     # ○ unmet


def _node_text(node: PlanTreeNode, chosen: bool) -> Text:
    body = f"{_glyph(node, chosen)} {node.label}"
    if chosen:
        body += "   ◄ CHOSEN"
    elif node.status == "current" and node.kind != "step":
        body += "   ◄ now"
    if node.detail:
        body += f"   {node.detail}"
    style = "bold" if chosen else _STYLE.get(node.kind if node.kind in _STYLE else node.status,
                                             _STYLE.get(node.status, ""))
    return Text(body, style=style)


def default_expanded(roots: tuple[PlanTreeNode, ...]) -> set[str]:
    """Keys to open on first render: the chosen root plus every node on the path
    down to the `current` node."""
    keys: set[str] = set()

    def walk(node: PlanTreeNode, chain: list[str]) -> None:
        chain = [*chain, node.key]
        if node.status == "current":
            keys.update(chain)
        for child in node.children:
            walk(child, chain)

    if roots and roots[0].kind != "root_stub":
        keys.add(roots[0].key)
        walk(roots[0], [])
    return keys


class PlanTree(Tree[PlanTreeNode]):
    """Prerequisite plan tree with key-based expansion memory."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__("PLAN", **kwargs)
        self.show_root = False
        self._expanded_keys: set[str] = set()
        self._seeded = False

    def set_nodes(self, roots: tuple[PlanTreeNode, ...]) -> None:
        if not self._seeded:
            self._expanded_keys = default_expanded(roots)
            self._seeded = True
        self.root.remove_children()
        for i, node in enumerate(roots):
            self._add(self.root, node, chosen=(i == 0 and node.kind != "root_stub"))

    def _add(self, parent: TreeNode[PlanTreeNode], node: PlanTreeNode, chosen: bool = False) -> None:
        tn = parent.add(_node_text(node, chosen), data=node,
                        allow_expand=bool(node.children))
        for child in node.children:
            self._add(tn, child)
        if node.children and node.key in self._expanded_keys:
            tn.expand()

    def on_tree_node_expanded(self, event: Tree.NodeExpanded[PlanTreeNode]) -> None:
        node = event.node.data
        if isinstance(node, PlanTreeNode):
            self._expanded_keys.add(node.key)

    def on_tree_node_collapsed(self, event: Tree.NodeCollapsed[PlanTreeNode]) -> None:
        node = event.node.data
        if isinstance(node, PlanTreeNode):
            self._expanded_keys.discard(node.key)
