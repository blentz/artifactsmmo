"""Tests for the trace-stats analyzer."""

from datetime import datetime, timezone

from sqlmodel import Session as SqlSession
from sqlmodel import SQLModel, create_engine

from artifactsmmo_cli.ai.learning.models import Cycle, Session
from artifactsmmo_cli.ai.trace_stats import (
    analyze,
    analyze_tree_divergence,
    list_sessions,
    load_cycles_from_db,
    load_trace_records,
)


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


def test_unparseable_ts_yields_zero_duration():
    """An ISO ts the parser rejects leaves duration at its zero default
    rather than raising."""
    cycles = [
        _cycle(ts="not-a-timestamp"),
        _cycle(ts="still-not-a-timestamp", cycle_index=1),
    ]
    s = analyze(cycles)
    assert s.duration_minutes == 0.0


def test_stuck_window_flushed_when_state_changes_midstream():
    """A stuck window (>=8 identical cycles) followed by a state change is
    recorded mid-stream, not only at end of input."""
    stuck = [
        _cycle(ts=f"2026-06-05T00:{i:02d}:00+00:00", cycle_index=i,
               task_code="x", task_progress=0, inventory_used=50)
        for i in range(9)
    ]
    moved = [
        _cycle(ts="2026-06-05T01:00:00+00:00", cycle_index=9,
               task_code="x", task_progress=1, inventory_used=51),
        _cycle(ts="2026-06-05T01:01:00+00:00", cycle_index=10,
               task_code="x", task_progress=2, inventory_used=52),
    ]
    s = analyze(stuck + moved)
    assert len(s.stuck_windows) == 1
    w = s.stuck_windows[0]
    assert w.cycles == 9
    assert w.progress == 0 and w.inventory == 50


def _seed_db(db_path: str) -> None:
    """Two sessions for two characters, each with cycles at known timestamps."""
    engine = create_engine(f"sqlite:///{db_path}")
    SQLModel.metadata.create_all(engine)
    early = datetime(2026, 6, 5, 10, 0, 0, tzinfo=timezone.utc).isoformat()
    late = datetime(2026, 6, 5, 12, 0, 0, tzinfo=timezone.utc).isoformat()
    with SqlSession(engine) as s:
        s.add(Session(session_id="old", character="Robby", started_at=early,
                      ended_at=None, cycle_count=2, exit_reason=None))
        s.add(Session(session_id="new", character="Robby", started_at=late,
                      ended_at=late, cycle_count=1, exit_reason="normal"))
        s.add(Session(session_id="other", character="Alice", started_at=late,
                      ended_at=late, cycle_count=1, exit_reason="normal"))
        s.add(Cycle(ts="2026-06-05T10:00:00+00:00", session_id="old",
                    cycle_index=0, character="Robby", outcome="ok"))
        s.add(Cycle(ts="2026-06-05T10:05:00+00:00", session_id="old",
                    cycle_index=1, character="Robby", outcome="ok"))
        s.add(Cycle(ts="2026-06-05T12:00:00+00:00", session_id="new",
                    cycle_index=0, character="Robby", outcome="ok"))
        s.add(Cycle(ts="2026-06-05T12:00:00+00:00", session_id="other",
                    cycle_index=0, character="Alice", outcome="ok"))
        s.commit()
    engine.dispose()


def test_load_cycles_since_until_window(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    rows = load_cycles_from_db(
        db_path=db, character="Robby", session_id=None,
        since="2026-06-05T10:01:00+00:00", until="2026-06-05T11:00:00+00:00",
    )
    # The 10:00 cycle is excluded by `since`; the 12:00 cycle by `until`;
    # only the 10:05 cycle survives the window.
    assert [r.ts for r in rows] == ["2026-06-05T10:05:00+00:00"]


def test_load_cycles_limit_caps_rows(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    rows = load_cycles_from_db(
        db_path=db, character="Robby", session_id=None, limit=1,
    )
    assert len(rows) == 1


def test_load_cycles_last_session_resolves_most_recent(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    rows = load_cycles_from_db(db_path=db, character="Robby", session_id="last")
    # "new" started later than "old", so only its single cycle is returned.
    assert [r.session_id for r in rows] == ["new"]


def test_load_cycles_last_no_session_returns_empty(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    rows = load_cycles_from_db(db_path=db, character="Ghost", session_id="last")
    assert rows == []


def test_list_sessions_filters_by_character(tmp_path):
    db = str(tmp_path / "learning.db")
    _seed_db(db)
    sess = list_sessions(db, character="Alice")
    assert [s.session_id for s in sess] == ["other"]


def _trace(chosen_root: str, tree_root: str) -> dict:
    """A minimal Phase-3 shadow trace record: only the `chosen_root` keys
    `analyze_tree_divergence` reads are populated (real records carry the
    full `StrategyDecision.to_trace()` payload; the analyzer only touches
    `chosen_root`)."""
    return {
        "strategy": {"chosen_root": chosen_root},
        "tree": {"chosen_root": tree_root},
    }


def test_tree_divergence_empty_input_is_zero_state():
    s = analyze_tree_divergence([])
    assert s.tree_dual_cycles == 0
    assert s.tree_agree == 0
    assert s.tree_branch_counts == {}
    assert s.tree_divergent_pairs == {}


def test_tree_divergence_binding_scenario():
    """Brief's binding fixture: 2 agreeing + 1 divergent dual record + 1
    legacy-only old-format record (no "tree" key) -> 3 dual cycles, 2 agree,
    old-format record skipped outright (never counted, never guessed)."""
    records = [
        _trace("ReachCharLevel()", "ReachCharLevel()"),
        _trace("ObtainItem(copper_boots)", "ObtainItem(copper_boots)"),
        _trace("PursueTask(copper_ore)", "ObtainItem(iron_sword)"),
        {"strategy": {"chosen_root": "GatherMaterials(sunflower)"}},  # no "tree"
    ]
    s = analyze_tree_divergence(records)
    assert s.tree_dual_cycles == 3
    assert s.tree_agree == 2
    assert s.tree_divergent_pairs[("PursueTask(copper_ore)", "ObtainItem(iron_sword)")] == 1


def test_tree_divergence_branch_counts_gear_vs_xp():
    records = [
        _trace("ReachCharLevel()", "ReachCharLevel()"),
        _trace("X", "ObtainItem(copper_boots)"),
        _trace("X", "ObtainItem(iron_sword)"),
    ]
    s = analyze_tree_divergence(records)
    assert s.tree_branch_counts["xp"] == 1
    assert s.tree_branch_counts["gear"] == 2


def test_tree_divergence_unrecognized_root_buckets_as_other():
    """A `chosen_root` that is neither ObtainItem- nor ReachCharLevel-rooted
    (or is None/absent) buckets as "other" rather than being dropped or
    guessed into one of the two known branches."""
    records = [
        _trace("X", "SomethingElse()"),
        {"strategy": {"chosen_root": None}, "tree": {"chosen_root": None}},
    ]
    s = analyze_tree_divergence(records)
    assert s.tree_dual_cycles == 2
    assert s.tree_branch_counts["other"] == 2


def test_tree_divergence_skips_record_missing_strategy_key():
    """Defensive: a record with a "tree" key but no "strategy" key (should
    not occur from `_emit_trace`, but the analyzer must not guess a
    comparison) is skipped, same as the missing-"tree" case."""
    records = [{"tree": {"chosen_root": "ReachCharLevel()"}}]
    s = analyze_tree_divergence(records)
    assert s.tree_dual_cycles == 0


def test_load_trace_records_reads_jsonl(tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text(
        '{"cycle": 0, "strategy": {"chosen_root": "A"}}\n'
        "\n"
        '{"cycle": 1, "tree": {"chosen_root": "B"}}\n'
    )
    records = load_trace_records(str(path))
    assert len(records) == 2
    assert records[0]["cycle"] == 0
    assert records[1]["tree"] == {"chosen_root": "B"}


def test_load_trace_records_skips_malformed_and_non_object_lines(tmp_path):
    path = tmp_path / "trace.jsonl"
    path.write_text(
        '{"cycle": 0}\n'
        "not-json\n"
        "5\n"
        '["also", "not", "a", "record"]\n'
        '{"cycle": 1}\n'
    )
    records = load_trace_records(str(path))
    assert len(records) == 2
    assert [r["cycle"] for r in records] == [0, 1]
