"""Capture the committed store-cooldowns fixture from a learning DB, once (the
user's I2 ruling, 2026-10-31: "learning DB, then raise").

Writes tests/test_ai/fixtures/store_cooldowns.json: the rows
`LearningStore.fleet_action_cooldowns` reads for every priced action class
(`fight_seconds_model.STORE_KINDS`), `[action_class, action_repr, total
cooldown seconds, cycles]`. The offline per-kind seconds
(`fight_seconds_model.offline_kind_seconds`) read this file. Point it at a
READ-ONLY BACKUP of the live DB, never the live file:

    sqlite3 -readonly ~/.cache/artifactsmmo/learning.db ".backup /tmp/copy.db"
    uv run python scripts/capture_store_cooldowns.py /tmp/copy.db
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from artifactsmmo_cli.ai.learning.fight_seconds_model import STORE_KINDS
from artifactsmmo_cli.ai.learning.store import LearningStore

OUT = (Path(__file__).resolve().parent.parent / "tests" / "test_ai" / "fixtures"
       / "store_cooldowns.json")


def main(db_path: str) -> None:
    store = LearningStore(db_path=db_path, character="capture")
    try:
        rows = sorted(store.fleet_action_cooldowns(frozenset(STORE_KINDS), 0,
                                                   store.last_cycle_id()))
    finally:
        store.close()
    OUT.write_text(json.dumps({
        "source": "LearningStore.fleet_action_cooldowns over a backup of the live learning DB",
        "captured_at": datetime.now(UTC).isoformat(),
        "rows": [list(row) for row in rows],
    }, indent=0) + "\n")


if __name__ == "__main__":
    main(sys.argv[1])
