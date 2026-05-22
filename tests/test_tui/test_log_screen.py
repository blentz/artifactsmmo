from artifactsmmo_cli.ai.cycle_snapshot import CycleSnapshot, GoalRankEntry
from artifactsmmo_cli.tui.screens.log_screen import build_debug_log_line


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=7, timestamp="2026-05-21T12:34:56Z", character="hero",
        x=3, y=4, level=5, xp=0, max_xp=100, hp=80, max_hp=150, gold=0,
        selected_goal="FarmItems", action="Craft(potion)", outcome="ok",
        task_code="potion", task_type="items", task_progress=2, task_total=29,
        cooldown_remaining=4.5, path_next_action="green_slime",
        projected_cycles_to_max=1234.0,
        goal_rank=[GoalRankEntry(goal="FarmItems", priority=75.0),
                   GoalRankEntry(goal="TaskCancel", priority=0.0)],
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def test_debug_line_has_core_fields():
    line = build_debug_log_line(_snap())
    assert "12:34:56" in line
    assert "7" in line  # cycle index present
    assert "FarmItems" in line and "Craft(potion)" in line and "ok" in line


def test_debug_line_has_debug_detail():
    line = build_debug_log_line(_snap())
    assert "2/29" in line              # task progress
    assert "80/150" in line            # hp
    assert "4.5" in line               # cooldown
    assert "(3,4)" in line             # position
    assert "green_slime" in line       # path next
    assert "1234" in line              # projected cycles


def test_debug_line_includes_full_goal_rank():
    line = build_debug_log_line(_snap())
    # full ranking (priority > 0): FarmItems shown; zero-priority omitted
    assert "FarmItems" in line and "75" in line
    assert "TaskCancel" not in line    # priority 0 filtered
