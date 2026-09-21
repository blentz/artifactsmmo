"""The cycles table gains root attribution, and an old database gains it in place."""

from pathlib import Path

from sqlalchemy import create_engine
from sqlmodel import Session, select

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from tests.test_ai.fixtures import make_state


def test_store_migrates_root_group_columns(tmp_path: Path) -> None:
    db = tmp_path / "learning.db"
    # A pre-existing cycles table with neither new column.
    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        conn.exec_driver_sql(
            "CREATE TABLE cycles (id INTEGER PRIMARY KEY, ts TEXT, session_id TEXT, "
            "cycle_index INTEGER, character TEXT, outcome TEXT)"
        )
    engine.dispose()

    LearningStore(str(db), character="C3P0")

    engine = create_engine(f"sqlite:///{db}")
    with engine.begin() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(cycles)")}
    engine.dispose()
    assert "root_group" in cols
    assert "root_repr" in cols


def test_recent_cycles_returns_the_raw_stream_newest_first(tmp_path: Path) -> None:
    store = LearningStore(str(tmp_path / "learning.db"), character="C3P0")
    store.start_session()
    for index, group in enumerate(["trunk", "gear"]):
        store.record_cycle(Cycle(
            ts=f"2026-09-21T00:00:0{index}+00:00", session_id="placeholder",
            cycle_index=index, character="C3P0", outcome="ok",
            selected_goal="GrindCharacterXP(green_slime)", root_group=group,
            root_repr=f"Root{index}",
        ))
    rows = store.recent_cycles(window=10)
    # Newest first: the LAST recorded row leads.
    assert [r.root_group for r in rows] == ["gear", "trunk"]


def _record(store: LearningStore, decision: StrategyDecision) -> list[Cycle]:
    """Drive the REAL write site: `GamePlayer._record_learning_cycle` at
    player.py:4123, the same seam `test_cycle_error_text.py` uses for
    `error_text`. `_last_decision` is the StrategyDecision already in scope at
    that call site — there is no local variable named `decision` there, and the
    task-2 brief's binding ruling is that this seam, not a hand-built `Cycle`,
    is what proves the write site is actually populated in production."""
    player = GamePlayer(character="hero", dry_run=False, history=store)
    player._last_decision = decision
    prev = make_state(level=5)
    player._record_learning_cycle(
        prev_state=prev, new_state=make_state(level=5, xp=prev.xp + 10),
        action_repr="Fight(green_slime)", action_class="FightAction",
        outcome="ok", selected_goal="GrindCharacterXP(green_slime)",
        predicted_cost=0.0, actual_cooldown_seconds=0.0,
        planner_nodes=1, planner_depth=1, planner_timed_out=False,
        plan_len=1,
    )
    with Session(store._engine) as s:
        return list(s.exec(select(Cycle).where(
            Cycle.action_repr == "Fight(green_slime)")))


def test_write_site_records_guard_when_interrupt_set(tmp_path: Path) -> None:
    store = LearningStore(str(tmp_path / "guard.db"), character="hero")
    try:
        store.start_session()
        decision = StrategyDecision(
            interrupt="RestoreHP", chosen_root=ReachCharLevel(level=10), chosen_step=None)
        rows = _record(store, decision)
        assert len(rows) == 1
        assert rows[0].root_group == "guard"
        # chosen_root is still recorded even though the guard preempted it.
        assert rows[0].root_repr == repr(ReachCharLevel(level=10))
    finally:
        store.close()


def test_write_site_records_the_chosen_roots_group(tmp_path: Path) -> None:
    store = LearningStore(str(tmp_path / "trunk.db"), character="hero")
    try:
        store.start_session()
        decision = StrategyDecision(
            interrupt=None, chosen_root=ReachCharLevel(level=10), chosen_step=None)
        rows = _record(store, decision)
        assert len(rows) == 1
        assert rows[0].root_group == "trunk"
        assert rows[0].root_repr == repr(ReachCharLevel(level=10))
    finally:
        store.close()
