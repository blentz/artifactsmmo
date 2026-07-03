"""PlanScreen tests — header renders and the tree receives snapshot nodes."""

import pytest
from textual.app import App

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, PlanTreeNode
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen
from artifactsmmo_cli.tui.widgets.plan_tree import PlanTree


def _snap(**ov) -> CycleSnapshot:
    node = PlanTreeNode(key="amulet", label="life_amulet", kind="obtain", status="unmet")
    base = dict(cycle_index=1, timestamp="t", character="hero", x=0, y=0, level=1,
                xp=0, max_xp=100, hp=10, max_hp=10, gold=0, selected_goal="g",
                action="a", outcome="ok", max_level=40,
                chosen_root="ObtainItem(code='life_amulet', quantity=1)",
                projected_cycles_to_max=18.0, plan_tree=(node,))
    base.update(ov)
    return CycleSnapshot(**base)


class _Harness(App):
    def __init__(self, snap):
        super().__init__()
        self._snap = snap

    def on_mount(self) -> None:
        self.push_screen(PlanScreen(self._snap, GameData()))


@pytest.mark.asyncio
async def test_screen_mounts_header_and_tree():
    app = _Harness(_snap())
    async with app.run_test():
        screen = app.screen
        assert isinstance(screen, PlanScreen)
        tree = screen.query_one("#plan-tree", PlanTree)
        assert [n.data.label for n in tree.root.children] == ["life_amulet"]


@pytest.mark.asyncio
async def test_update_snapshot_refreshes_tree():
    app = _Harness(_snap())
    async with app.run_test():
        screen = app.screen
        new = PlanTreeNode(key="ring", label="golden_ring", kind="obtain", status="unmet")
        screen.update_snapshot(_snap(plan_tree=(new,)))
        tree = screen.query_one("#plan-tree", PlanTree)
        assert [n.data.label for n in tree.root.children] == ["golden_ring"]


@pytest.mark.asyncio
async def test_update_snapshot_before_mount_is_noop_for_widgets():
    screen = PlanScreen(_snap(), GameData())
    new = PlanTreeNode(key="ring", label="golden_ring", kind="obtain", status="unmet")
    # Screen is not mounted yet: update_snapshot must only update internal state,
    # not attempt to query widgets that don't exist.
    screen.update_snapshot(_snap(plan_tree=(new,)))
    assert screen._snapshot.plan_tree == (new,)
