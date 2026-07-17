from artifactsmmo_cli.ai.cycle_snapshot import (
    CycleSnapshot,
    GoalAttempt,
    GoalRankEntry,
    PlanTreeNode,
)
from artifactsmmo_cli.tui.screens.log_screen import build_debug_log_line


def _snap(**overrides) -> CycleSnapshot:
    base = dict(
        cycle_index=7, timestamp="2026-05-21T12:34:56Z", character="hero",
        x=3, y=4, level=5, xp=0, max_xp=100, hp=80, max_hp=150, gold=0,
        selected_goal="FarmItems", action="Craft(potion)", outcome="ok",
        task_code="potion", task_type="items", task_progress=2, task_total=29,
        cooldown_remaining=4.5, path_next_action="green_slime",
        projected_cycles_to_max=1234.0,
        planner_nodes=842, planner_depth=7, plan_len=3, planner_timed_out=False,
        path_blocked=False,
        goals_tried=[
            GoalAttempt(goal="FarmItems", nodes=842, depth=7, plan_len=3),
            GoalAttempt(goal="FightMonster", nodes=120, depth=4, plan_len=0, timed_out=True),
        ],
        goal_rank=[GoalRankEntry(goal="FarmItems", priority=75.0),
                   GoalRankEntry(goal="TaskCancel", priority=0.0)],
    )
    base.update(overrides)
    return CycleSnapshot(**base)


def test_debug_line_shows_grind_chain():
    legs = (PlanTreeNode(key="l0", label="GatherAsh()", kind="obtain", status="current"),
            PlanTreeNode(key="l1", label="CraftPlank()", kind="obtain", status="unmet"))
    line = build_debug_log_line(_snap(action="LevelSkill(woodcutting)", grind_expansion=legs))
    assert "GatherAsh()" in line and "CraftPlank()" in line


def test_debug_line_no_grind_chain_when_empty():
    line = build_debug_log_line(_snap())
    assert "↳" not in line


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
    # full ranking (priority > 0): FarmItems shown; zero-priority omitted from rank
    assert "rank" in line and "75" in line
    rank_line = next(ln for ln in line.split("\n") if "rank" in ln)
    assert "TaskCancel" not in rank_line    # priority 0 filtered from the ranking


def test_debug_line_shows_planner_internals():
    line = build_debug_log_line(_snap())
    assert "nodes=842" in line
    assert "depth=7" in line
    assert "plan_len=3" in line
    assert "timeout=no" in line
    assert "blocked=no" in line


def test_debug_line_shows_goals_tried_with_timeout_flag():
    line = build_debug_log_line(_snap())
    assert "FarmItems(n=842 d=7 len=3)" in line
    assert "FightMonster(n=120 d=4 len=0 TIMEOUT)" in line


def test_debug_line_shows_suppressed_only_when_present():
    assert "suppressed" not in build_debug_log_line(_snap(suppressed_goals=[]))
    line = build_debug_log_line(_snap(suppressed_goals=["NpcSell", "ExpandBank"]))
    assert "suppressed" in line and "NpcSell" in line and "ExpandBank" in line


def test_debug_line_is_multiline_block():
    line = build_debug_log_line(_snap())
    assert "\n" in line  # trace renders as a multi-line block, not one clipped line
