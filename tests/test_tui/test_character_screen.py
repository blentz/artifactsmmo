from rich.console import Console

from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot
from artifactsmmo_cli.tui.screens.character_screen import build_character_detail


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=1, timestamp="2026-05-21T12:00:00Z", character="hero",
        x=3, y=4, level=5, xp=120, max_xp=500, hp=80, max_hp=150, gold=42,
        selected_goal="g", action="a", outcome="ok",
        skills={"mining": 10, "alchemy": 1}, skill_xp={"mining": 50, "alchemy": 5},
        equipment={"weapon_slot": "copper_axe", "shield_slot": None},
        task_code="small_health_potion", task_type="items",
        task_progress=2, task_total=29,
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def _text(renderable) -> str:
    console = Console(no_color=True, width=120)
    with console.capture() as cap:
        console.print(renderable)
    return cap.get()


def test_detail_includes_vitals_and_task():
    out = _text(build_character_detail(_snap()))
    assert "hero" in out and "L5" in out
    assert "80/150" in out          # hp
    assert "42" in out              # gold
    assert "(3,4)" in out
    assert "small_health_potion" in out and "2/29" in out


def test_detail_lists_all_skills_with_level_and_xp():
    out = _text(build_character_detail(_snap()))
    assert "mining" in out and "10" in out and "50" in out
    assert "alchemy" in out


def test_detail_lists_equipment_slots():
    out = _text(build_character_detail(_snap()))
    assert "weapon_slot" in out and "copper_axe" in out
    assert "shield_slot" in out and "—" in out   # empty slot


def test_detail_no_task():
    out = _text(build_character_detail(_snap(task_code=None)))
    assert "none" in out.lower()
