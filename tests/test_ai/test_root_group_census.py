"""The cycles table gains root attribution, and an old database gains it in place."""

from pathlib import Path

import pytest
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


# ===== NEW TESTS FOR TASK 4: root_group_counts =====


def _grouped(character: str, group: str | None) -> Cycle:
    return Cycle(
        ts="2026-09-21T00:00:00+00:00", session_id="s", cycle_index=0,
        character=character, outcome="ok", root_group=group,
    )


def test_counts_by_group_per_character() -> None:
    from artifactsmmo_cli.audit.root_group_census import GroupCounts, root_group_counts

    rows = root_group_counts([
        _grouped("C3P0", "trunk"), _grouped("C3P0", "trunk"), _grouped("C3P0", "gear"),
        _grouped("R2D2", "orphan_skill"),
    ])
    by_char = {r.character: r for r in rows}
    assert by_char["C3P0"].counts == {"trunk": 2, "gear": 1}
    assert by_char["R2D2"].counts == {"orphan_skill": 1}


def test_pre_migration_rows_are_reported_as_unattributed_not_counted() -> None:
    from artifactsmmo_cli.audit.root_group_census import root_group_counts

    rows = root_group_counts([_grouped("C3P0", "trunk"), _grouped("C3P0", None)])
    assert rows[0].attributed == 1
    assert rows[0].unattributed == 1
    assert rows[0].counts == {"trunk": 1}


def test_an_unknown_group_label_raises() -> None:
    from artifactsmmo_cli.audit.root_group_census import root_group_counts

    # A label outside ROOT_GROUPS means the classifier and the census have
    # drifted. Counting it nowhere would hide that silently.
    with pytest.raises(ValueError, match="unknown root group"):
        root_group_counts([_grouped("C3P0", "made_up")])


def test_characters_are_ordered_by_name() -> None:
    from artifactsmmo_cli.audit.root_group_census import root_group_counts

    rows = root_group_counts([_grouped("R2D2", "gear"), _grouped("C3P0", "gear")])
    assert [r.character for r in rows] == ["C3P0", "R2D2"]


def test_share_is_denominated_on_attributed_rows_only() -> None:
    from artifactsmmo_cli.audit.root_group_census import GroupCounts

    counts = GroupCounts(character="C3P0", counts={"trunk": 1}, attributed=1, unattributed=9)
    assert counts.share("trunk") == 1.0
    assert counts.share("gear") == 0.0


def test_all_pre_migration_character_returns_none_share() -> None:
    from artifactsmmo_cli.audit.root_group_census import root_group_counts

    # A character whose entire window is pre-migration NULLs (today IS the migration date).
    rows = root_group_counts([_grouped("C3P0", None), _grouped("C3P0", None)])
    assert len(rows) == 1
    assert rows[0].character == "C3P0"
    assert rows[0].counts == {}
    assert rows[0].attributed == 0
    assert rows[0].unattributed == 2
    # share() returns None when nothing was attributed, not 0.0.
    assert rows[0].share("trunk") is None
    assert rows[0].share("gear") is None
