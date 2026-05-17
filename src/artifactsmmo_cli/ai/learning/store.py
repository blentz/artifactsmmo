"""SQLModel-backed learning store for autoregressive GOAP planning."""

from pathlib import Path

from sqlalchemy import text
from sqlmodel import SQLModel, create_engine

from artifactsmmo_cli.ai.learning.models import Cycle, Session


class LearningStore:
    """Event log + queryable learned stats. Best-effort: errors degrade to defaults."""

    def __init__(self, db_path: str, character: str) -> None:
        Path(db_path).parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_engine(f"sqlite:///{db_path}")
        SQLModel.metadata.create_all(self._engine)

        with self._engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.commit()

        self._character = character
        self._session_id: str | None = None

    def close(self) -> None:
        self._engine.dispose()
