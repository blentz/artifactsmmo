"""`LearningStore.fight_cost_rows`: the loss-cost evidence a fight's win
threshold reads (spec 2026-10-15 fight-gates-odds §2)."""

import tempfile

from sqlmodel import create_engine

from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore


def _cycle(store: LearningStore, ts: str, action_class: str, action_repr: str,
           outcome: str, seconds: float | None) -> None:
    store.record_cycle(Cycle(
        ts=ts, session_id="x", cycle_index=0, character="x", outcome=outcome,
        action_class=action_class, action_repr=action_repr,
        actual_cooldown_seconds=seconds,
    ))


def test_interleaved_characters(tmp_path) -> None:
    db = tmp_path / "t.db"
    a = LearningStore(db_path=db, character="A")
    b = LearningStore(db_path=db, character="B")
    a.start_session()
    b.start_session()
    _cycle(a, "2026-10-01T00:00:00+00:00", "FightAction", "Fight(imp)", "ok", 10.0)
    _cycle(a, "2026-10-15T00:00:00+00:00", "FightAction", "Fight(imp)", "ok", 10.0)
    _cycle(b, "2026-10-15T00:00:01+00:00", "RestAction", "Rest", "ok", 99.0)
    _cycle(a, "2026-10-15T00:00:02+00:00", "CraftAction", "Craft(x)", "ok", 5.0)
    _cycle(a, "2026-10-15T00:00:03+00:00", "RestAction", "Rest", "ok", 40.6)
    _cycle(a, "2026-10-15T00:00:04+00:00", "MoveAction", "Move(0,0)", "ok", None)
    _cycle(a, "2026-10-15T00:00:05+00:00", "FightAction", "Fight(imp)", "error:fight_lost", 12.0)
    assert a.fight_cost_rows("2026-10-10T00:00:00+00:00") == [
        ("FightAction", "Fight(imp)", "ok", 10),
        ("RestAction", "Rest", "ok", 41),
        ("MoveAction", "Move(0,0)", "ok", 0),
        ("FightAction", "Fight(imp)", "error:fight_lost", 12),
    ]
    a.close()
    b.close()


def test_fight_cost_rows_empty_on_error(tmp_path) -> None:
    store = LearningStore(db_path=str(tmp_path / "t.db"), character="hero")
    store._engine = create_engine(f"sqlite:///{tempfile.mkdtemp()}")
    assert store.fight_cost_rows("2026-10-01T00:00:00+00:00") == []
