"""The persisted intention (Phase 4-1b): the arbiter's commitment survives a
restart. One row per character; what began, and when."""

import tempfile

from sqlmodel import create_engine

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import _ctx, _FakeDecision, _make_planner_gd


def _store(tmp_path, character: str = "hero") -> LearningStore:
    return LearningStore(db_path=str(tmp_path / "intention.db"), character=character)


def test_no_intention_until_one_is_saved(tmp_path):
    store = _store(tmp_path)
    assert store.load_intention() is None
    store.close()


def test_a_saved_intention_reads_back(tmp_path):
    store = _store(tmp_path)
    store.save_intention("GrindCharacterXP(vampire)")
    row = store.load_intention()
    assert row is not None
    assert row.committed_repr == "GrindCharacterXP(vampire)"
    assert row.began_ts
    store.close()


def test_the_same_intention_keeps_when_it_began(tmp_path):
    """Re-saving the commitment it already holds is not a new intention: the
    start time is what a budget will be measured from (4-2b)."""
    store = _store(tmp_path)
    store.save_intention("ReachSkill(weaponcrafting->20)")
    began = store.load_intention().began_ts
    store.save_intention("ReachSkill(weaponcrafting->20)")
    assert store.load_intention().began_ts == began
    store.save_intention("ReachSkill(fishing->30)")
    row = store.load_intention()
    assert row.committed_repr == "ReachSkill(fishing->30)"
    assert row.began_ts >= began
    store.close()


def test_clearing_the_commitment_ends_the_intention(tmp_path):
    store = _store(tmp_path)
    store.save_intention("GrindCharacterXP(vampire)")
    store.save_intention(None)
    assert store.load_intention() is None
    store.close()


def test_intentions_are_per_character(tmp_path):
    a = _store(tmp_path, "Robby")
    b = _store(tmp_path, "Lor")
    a.save_intention("GrindCharacterXP(vampire)")
    assert b.load_intention() is None
    assert a.load_intention().committed_repr == "GrindCharacterXP(vampire)"
    a.close()
    b.close()


def _break_engine(store: LearningStore) -> None:
    store._engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}")


def test_a_db_error_on_save_is_reported_not_raised(tmp_path, capsys):
    store = _store(tmp_path)
    _break_engine(store)
    store.save_intention("GrindCharacterXP(vampire)")
    assert "save_intention failed" in capsys.readouterr().out


def test_a_db_error_on_load_reads_as_no_intention(tmp_path):
    store = _store(tmp_path)
    store.save_intention("GrindCharacterXP(vampire)")
    _break_engine(store)
    assert store.load_intention() is None


def test_the_arbiter_persists_its_commitment_and_a_new_one_resumes_it(tmp_path):
    """Phase 4-1b: a commitment made in one process is the commitment of the
    next — the arbiter writes it when it changes, and `resume_intention` reads
    it back on start (it used to be memory-only and lost on every restart)."""
    store = _store(tmp_path)
    arbiter = StrategyArbiter(GOAPPlanner(), history=store)
    state = make_state(hp=150, max_hp=150, task_code=None, task_total=0)
    actions = [AcceptTaskAction(taskmaster_location=(2, 1))]
    goal, _, _ = arbiter.select(_FakeDecision(chosen_step=None), state,
                                _make_planner_gd(), actions, _ctx())
    assert isinstance(goal, AcceptTaskGoal)
    assert store.load_intention().committed_repr == repr(goal)

    restarted = StrategyArbiter(GOAPPlanner(), history=store)
    assert restarted._committed_repr is None
    restarted.resume_intention()
    assert restarted._committed_repr == repr(goal)


def test_resume_without_a_store_or_an_intention_commits_to_nothing(tmp_path):
    bare = StrategyArbiter(GOAPPlanner(), history=None)
    bare.resume_intention()
    assert bare._committed_repr is None
    empty = StrategyArbiter(GOAPPlanner(), history=_store(tmp_path))
    empty.resume_intention()
    assert empty._committed_repr is None


def test_a_yield_round_trips_and_clears(tmp_path):
    store = _store(tmp_path)
    assert store.load_yield() is None
    store.save_yield("ObtainItem(code='life_ring')", None)
    store.save_yield("ObtainItem(code='life_ring')", "GrindCharacterXP(spider)")
    row = store.load_yield()
    assert (row.yielded_root, row.holder) == ("ObtainItem(code='life_ring')",
                                              "GrindCharacterXP(spider)")
    store.save_yield(None, None)
    assert store.load_yield() is None
    store.save_yield(None, None)  # clearing nothing is a no-op
    assert store.load_yield() is None


def test_a_db_error_on_yield_is_reported_or_reads_as_none(tmp_path, capsys):
    store = _store(tmp_path)
    _break_engine(store)
    store.save_yield("ObtainItem(code='life_ring')", None)
    assert "save_yield failed" in capsys.readouterr().out
    assert store.load_yield() is None
