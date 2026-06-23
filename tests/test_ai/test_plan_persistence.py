import tempfile

from sqlmodel import create_engine

from artifactsmmo_cli.ai.learning.store import LearningStore


def _store(tmp_path):
    s = LearningStore(db_path=str(tmp_path / "learn.db"), character="hero")
    s.start_session()
    return s


def _break_engine(store: LearningStore) -> None:
    bad_dir = tempfile.mkdtemp()
    store._engine = create_engine(f"sqlite:///{bad_dir}")


def test_plan_body_round_trips(tmp_path):
    s = _store(tmp_path)
    s.record_plan_body("Goal(copper_ring)", "Gather(copper_ore)",
                        ["Gather(copper_ore)", "Craft(copper_bar)", "Craft(copper_ring)"])
    rows = s.plan_bodies_for_goal("Goal(copper_ring)")
    assert len(rows) == 1
    assert rows[0].head_action_repr == "Gather(copper_ore)"


def test_commitment_upserts_single_row(tmp_path):
    s = _store(tmp_path)
    s.save_plan_commitment("Goal(g)", "{}", ["A", "B"], 0, "copper_ring", False)
    s.save_plan_commitment("Goal(g)", '{"type":"X"}', ["A", "B", "C"], 1, None, True)
    loaded = s.load_plan_commitment()
    assert loaded is not None
    assert loaded.cursor == 1
    assert loaded.latch_active is True
    assert loaded.crafting_target is None
    assert loaded.goal_json == '{"type":"X"}'


def test_load_commitment_absent_returns_none(tmp_path):
    s = _store(tmp_path)
    assert s.load_plan_commitment() is None


def test_record_plan_body_swallows_error(tmp_path, capsys):
    s = _store(tmp_path)
    _break_engine(s)
    s.record_plan_body("Goal(g)", "Act(x)", ["Act(x)"])
    assert "record_plan_body failed" in capsys.readouterr().out


def test_plan_bodies_for_goal_returns_empty_on_error(tmp_path):
    s = _store(tmp_path)
    _break_engine(s)
    assert s.plan_bodies_for_goal("Goal(g)") == []


def test_save_plan_commitment_swallows_error(tmp_path, capsys):
    s = _store(tmp_path)
    _break_engine(s)
    s.save_plan_commitment("Goal(g)", "{}", ["A"], 0, None, False)
    assert "save_plan_commitment failed" in capsys.readouterr().out


def test_load_plan_commitment_returns_none_on_error(tmp_path):
    s = _store(tmp_path)
    _break_engine(s)
    assert s.load_plan_commitment() is None
