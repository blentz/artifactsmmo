"""PlanScreen tests — build_plan_detail adapter rendering from a snapshot."""

from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, RootScoreView
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.tui.screens.plan_screen import PlanScreen, build_plan_detail


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _gd() -> GameData:
    gd = GameData()
    gd._crafting_recipes = {"copper_boots": {"copper_bar": 6}, "copper_bar": {"copper_ore": 10}}
    gd._item_stats = {"copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                                crafting_skill="gearcrafting", crafting_level=1)}
    return gd


def _snap(**ov) -> CycleSnapshot:
    base = dict(cycle_index=1, timestamp="2026-06-13T00:00:00Z", character="hero",
                x=0, y=0, level=1, xp=0, max_xp=100, hp=10, max_hp=10, gold=0,
                selected_goal="g", action="a", outcome="ok",
                chosen_root="ObtainItem(code='copper_boots', quantity=1)",
                strategy_ranking=[RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                                                category="gear", score=2.5)],
                inventory={"copper_ore": 42}, projected_cycles_to_max=18.0)
    base.update(ov)
    return CycleSnapshot(**base)


def test_build_plan_detail_from_snapshot():
    out = _text(build_plan_detail(_snap(), _gd()))
    assert "CHOSEN" in out and "copper_boots" in out
    assert "42/60" in out and "ETA" in out


def test_plan_screen_page_actions_clamp():
    snap = _snap(strategy_ranking=[
        RootScoreView(root_repr="ObtainItem(code='copper_boots', quantity=1)",
                      category="gear", score=2.5, step_repr="UpgradeEquipment(copper_boots)"),
    ])
    screen = PlanScreen(snap, _gd())
    assert screen._alt_page == 0
    screen.action_alt_prev()
    assert screen._alt_page == 0          # clamped at 0
    screen.action_alt_next()
    assert screen._alt_page == 0          # only one page → no advance
