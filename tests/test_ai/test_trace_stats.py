"""Tests for the trace-stats analyzer."""

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.trace_stats import analyze


def _cycle(**kw) -> Cycle:
    """Construct a Cycle with sensible defaults for the analyzer."""
    base = dict(
        ts="2026-06-05T00:00:00+00:00",
        session_id="s",
        cycle_index=0,
        character="hero",
        outcome="ok",
    )
    base.update(kw)
    return Cycle(**base)


def test_empty_input_returns_zero_state():
    s = analyze([])
    assert s.cycles == 0
    assert s.outcomes == {}
    assert s.planner == []
    assert s.task_completions == []


def test_outcomes_and_errors_counted():
    cycles = [
        _cycle(action_repr="Gather(copper_rocks)", outcome="ok"),
        _cycle(cycle_index=1, action_repr="Fight(chicken)", outcome="error:fight_lost", hp=1, max_hp=130),
        _cycle(cycle_index=2, action_repr="Gather(copper_rocks)", outcome="ok"),
    ]
    s = analyze(cycles)
    assert s.cycles == 3
    assert s.outcomes["ok"] == 2
    assert s.outcomes["error:fight_lost"] == 1
    assert s.errors_by_action[("Fight(chicken)", "error:fight_lost")] == 1


def test_fight_losses_capture_hp_and_monster():
    cycles = [
        _cycle(action_repr="Fight(chicken)", outcome="error:fight_lost",
               hp=1, max_hp=130),
    ]
    s = analyze(cycles)
    assert len(s.fight_losses) == 1
    fl = s.fight_losses[0]
    assert fl.hp == 1 and fl.max_hp == 130
    assert fl.monster == "chicken"


def test_goal_run_counting():
    """Three cycles of goal A, two of B → 2 runs, 1 change, 0 single-cycle."""
    cycles = [
        _cycle(selected_goal="A"),
        _cycle(cycle_index=1, selected_goal="A"),
        _cycle(cycle_index=2, selected_goal="A"),
        _cycle(cycle_index=3, selected_goal="B"),
        _cycle(cycle_index=4, selected_goal="B"),
    ]
    s = analyze(cycles)
    assert s.goal_runs == 2
    assert s.goal_changes == 1
    assert s.single_cycle_goals == {}


def test_single_cycle_goal_detection():
    """A run of length 1 lands in single_cycle_goals."""
    cycles = [
        _cycle(selected_goal="A"),
        _cycle(cycle_index=1, selected_goal="A"),
        _cycle(cycle_index=2, selected_goal="DETOUR"),  # 1-cycle blip
        _cycle(cycle_index=3, selected_goal="A"),
        _cycle(cycle_index=4, selected_goal="A"),
    ]
    s = analyze(cycles)
    assert s.single_cycle_goals["DETOUR"] == 1
    assert "A" not in s.single_cycle_goals


def test_planner_load_aggregated_per_goal():
    cycles = [
        _cycle(selected_goal="A", planner_nodes=100, plan_len=5),
        _cycle(cycle_index=1, selected_goal="A", planner_nodes=200, plan_len=8,
               planner_timed_out=True),
        _cycle(cycle_index=2, selected_goal="B", planner_nodes=50, plan_len=2),
    ]
    s = analyze(cycles)
    by_goal = {p.goal: p for p in s.planner}
    assert by_goal["A"].max_nodes == 200
    assert by_goal["A"].avg_nodes == 150
    assert by_goal["A"].timeouts == 1
    assert by_goal["A"].samples == 2
    assert by_goal["B"].max_nodes == 50
    # planner list ordered by -max_nodes
    assert s.planner[0].goal == "A"


def test_inventory_event_parsing():
    cycles = [
        _cycle(action_repr="Craft(ash_plank×3)"),
        _cycle(cycle_index=1, action_repr="Craft(copper_bar×1)"),
        _cycle(cycle_index=2, action_repr="Equip(copper_pickaxe->weapon_slot)"),
        _cycle(cycle_index=3, action_repr="DepositAll"),
        _cycle(cycle_index=4, action_repr="Withdraw(ash_wood×5)"),
        _cycle(cycle_index=5, action_repr="Delete(apple×5)"),
    ]
    s = analyze(cycles)
    assert s.craft_events == {"ash_plank": 1, "copper_bar": 1}
    assert s.equip_events == 1
    assert s.deposit_events == 1
    assert s.withdraw_events == {"ash_wood": 1}
    assert s.delete_events == {"apple": 1}


def test_task_completion_duration():
    cycles = [
        _cycle(ts="2026-06-05T00:00:00+00:00", task_code="copper_ore",
               task_type="items", task_progress=0, task_total=10),
        _cycle(ts="2026-06-05T00:05:00+00:00", cycle_index=1,
               task_code="copper_ore", task_type="items",
               task_progress=10, task_total=10),
    ]
    s = analyze(cycles)
    assert len(s.task_completions) == 1
    assert s.task_completions[0].task_code == "copper_ore"
    assert s.task_completions[0].duration_minutes == 5.0


def test_stuck_window_detection():
    """8+ consecutive cycles with identical (task, progress, inv) flag
    a stuck window."""
    cycles = [
        _cycle(ts=f"2026-06-05T00:{i:02d}:00+00:00", cycle_index=i,
               task_code="x", task_progress=0, inventory_used=50)
        for i in range(10)
    ]
    s = analyze(cycles)
    assert len(s.stuck_windows) == 1
    assert s.stuck_windows[0].cycles == 10


def test_useless_repeat_detection():
    """Same action + same inventory + same task_progress = useless."""
    cycles = [
        _cycle(action_repr="Wait", task_progress=5, inventory_used=10),
        _cycle(cycle_index=1, action_repr="Wait",
               task_progress=5, inventory_used=10),
        _cycle(cycle_index=2, action_repr="Wait",
               task_progress=5, inventory_used=10),
    ]
    s = analyze(cycles)
    # 2 repeats (cycles 1, 2 each match prior).
    assert s.useless_repeats == 2


def test_duration_uses_ts_span():
    cycles = [
        _cycle(ts="2026-06-05T00:00:00+00:00"),
        _cycle(ts="2026-06-05T01:30:00+00:00", cycle_index=1),
    ]
    s = analyze(cycles)
    assert s.duration_minutes == 90.0
