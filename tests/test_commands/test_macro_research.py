from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.commands.macro_research import macro_research


def _seed_progression(store, char):
    store.start_session()
    for ci, (lvl, goal) in enumerate([
        (1, "GrindCharacterXP(chicken)"), (1, "GrindCharacterXP(chicken)"),
        (2, "PursueTask(t)"),
    ]):
        store.record_cycle(Cycle(
            ts=f"2026-06-23T00:00:0{ci}", session_id="s", cycle_index=ci,
            character=char, outcome="ok", level=lvl, selected_goal=goal,
            action_class="FightAction", planner_nodes=100, planner_timed_out=False))


def test_macro_research_writes_report(tmp_path):
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    _seed_progression(store, "hero")
    out = tmp_path / "macro-report.md"
    macro_research(db=db, out=str(out), top_n=10)
    text = out.read_text()
    assert "# Macro-candidate research" in text
    assert "GrindCharacterXP" in text


def test_macro_research_prints_when_no_out(tmp_path, capsys):
    db = str(tmp_path / "l.db")
    store = LearningStore(db_path=db, character="hero")
    _seed_progression(store, "hero")
    macro_research(db=db, out=None, top_n=5)
    assert "# Macro-candidate research" in capsys.readouterr().out
