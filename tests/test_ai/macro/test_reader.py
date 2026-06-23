from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.macro.reader import load_cycle_rows


def _seed(store, **kw):
    base = dict(ts=kw.pop("ts"), session_id="s1", cycle_index=kw.pop("ci"),
                character="hero", outcome="ok")
    store.record_cycle(Cycle(**{**base, **kw}))


def test_load_cycle_rows_projects_and_orders(tmp_path):
    store = LearningStore(db_path=str(tmp_path / "l.db"), character="hero")
    store.start_session()
    _seed(store, ts="2026-06-23T00:00:02", ci=1, level=2,
          selected_goal="GrindCharacterXP(chicken)", action_class="FightAction",
          planner_nodes=12, planner_timed_out=False)
    _seed(store, ts="2026-06-23T00:00:01", ci=0, level=1,
          selected_goal="GrindCharacterXP(chicken)", action_class="FightAction",
          planner_nodes=8, planner_timed_out=False)
    rows = load_cycle_rows(str(tmp_path / "l.db"))
    assert [r.cycle_index for r in rows] == [0, 1]      # ts asc order preserved
    assert rows[0].level == 1 and rows[1].planner_nodes == 12
    assert rows[0].selected_goal == "GrindCharacterXP(chicken)"
