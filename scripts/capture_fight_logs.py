"""Capture the committed fight-seconds fixture from the LIVE API, once (spec
2026-10-18 §2.9, ruling CC).

Writes tests/test_ai/fixtures/fight_logs.json: for every character on the
account, its sheet `haste` at capture time and every entry of
`GET /my/logs/{name}` as `[type, cooldown, turns]` (`turns` is the fight's
`fight.turns`, None for any other entry). The offline fit (tests, scenarios,
censuses) reads this file; production fits from the learning store and its own
`/my/logs` bootstrap instead.

Each request is spaced by `SPACING_SECONDS`: the fleet shares the account's
rate budget while this runs.

    ARTIFACTSMMO_TOKEN="$(cat TOKEN)" uv run python scripts/capture_fight_logs.py
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

OUT = Path(__file__).resolve().parent.parent / "tests" / "test_ai" / "fixtures" / "fight_logs.json"
SPACING_SECONDS = 1.0
PAGE_SIZE = 100


def main() -> None:
    manager = ClientManager()
    manager.initialize(Config.from_token_file())
    api = manager.api
    characters: dict[str, dict[str, object]] = {}
    for character in api.get_my_characters().data:
        time.sleep(SPACING_SECONDS)
        entries: list[list[object]] = []
        page, pages = 1, 1
        while page <= pages:
            time.sleep(SPACING_SECONDS)
            result = api.get_character_logs(character.name, page=page, size=PAGE_SIZE)
            pages = result.pages
            for entry in result.data:
                turns = entry.content["fight"]["turns"] if entry.type_ == LogType.FIGHT else None
                entries.append([str(entry.type_), entry.cooldown, turns])
            page += 1
        characters[character.name] = {"haste": character.haste, "entries": entries}
    OUT.write_text(json.dumps({
        "source": "GET /my/logs/{name} (every page) and GET /my/characters, live API",
        "captured_at": datetime.now(UTC).isoformat(),
        "characters": characters,
    }, indent=1) + "\n")


if __name__ == "__main__":
    main()
