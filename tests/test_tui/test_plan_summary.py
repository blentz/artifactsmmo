from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.plan_summary import build_plan_header


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def _snap(**ov) -> CycleSnapshot:
    base = dict(cycle_index=1, timestamp="t", character="hero", x=0, y=0, level=1,
                xp=0, max_xp=100, hp=10, max_hp=10, gold=0, selected_goal="g",
                action="a", outcome="ok", max_level=40)
    base.update(ov)
    return CycleSnapshot(**base)


def test_header_shows_objective_and_eta():
    out = _text(build_plan_header(_snap(
        chosen_root="ObtainItem(code='life_amulet', quantity=1)",
        projected_cycles_to_max=18.0)))
    assert "OBJECTIVE" in out and "40" in out
    assert "ETA" in out and "18" in out


def test_header_none_objective_message():
    out = _text(build_plan_header(_snap(chosen_root=None)))
    assert "No committed objective" in out


def test_header_lists_suppressed():
    out = _text(build_plan_header(_snap(
        chosen_root="ReachCharLevel(level=3)",
        suppressed_goals=["PursueTask", "GatherMaterials"])))
    assert "suppressed" in out and "PursueTask" in out and "GatherMaterials" in out


def test_header_omits_eta_when_absent():
    out = _text(build_plan_header(_snap(chosen_root="ReachCharLevel(level=3)")))
    assert "ETA" not in out
