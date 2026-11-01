"""Capture the committed action-seconds fixture from the LIVE API, once (review
I2/I3 of the ticket-farm fix, 2026-10-31).

Writes tests/test_ai/fixtures/action_logs.json: every entry of the account's
`GET /my/logs` (every page) as `[type, cooldown, item, quantity]`. `item` and
`quantity` are the craft's or the recycle's own (`content.item`,
`content.quantity`: a craft's units made, a recycle's units recycled), None
and 1 for every other entry; and `craft_yields`, the API craft quantity
(`GET /items/{code}`, `craft.quantity`) of every item crafted in it. The offline per-kind seconds
(`fight_seconds_model.offline_kind_seconds`) read this file; the fight fit
keeps reading `fight_logs.json`. Production reads the same fields from its own
`/my/logs` bootstrap (`fetch_fleet_bootstrap`).

Each request is spaced by `SPACING_SECONDS`: the fleet shares the account's
rate budget while this runs.

    ARTIFACTSMMO_TOKEN="$(cat TOKEN)" uv run python scripts/capture_action_logs.py
"""

import json
import time
from datetime import UTC, datetime
from pathlib import Path

from artifactsmmo_api_client.api.items import get_item_items_code_get
from artifactsmmo_api_client.models.log_type import LogType

from artifactsmmo_cli.ai.learning.fight_seconds_model import log_kind
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

OUT = Path(__file__).resolve().parent.parent / "tests" / "test_ai" / "fixtures" / "action_logs.json"
SPACING_SECONDS = 1.0
PAGE_SIZE = 100


def main() -> None:
    manager = ClientManager()
    manager.initialize(Config.from_token_file())
    api = manager.api
    entries: list[list[object]] = []
    page, pages = 1, 1
    while page <= pages:
        time.sleep(SPACING_SECONDS)
        result = api.get_all_characters_logs(page=page, size=PAGE_SIZE)
        pages = result.pages
        entries.extend(list(log_kind(entry)) for entry in result.data)
        page += 1
    yields: dict[str, int] = {}
    for code in sorted({str(item) for kind, _cooldown, item, _quantity in entries
                        if kind == LogType.CRAFTING.value}):
        time.sleep(SPACING_SECONDS)
        item = get_item_items_code_get.sync(client=manager.client, code=code).data
        yields[code] = item.craft.quantity
    OUT.write_text(json.dumps({
        "source": "GET /my/logs (every page) and GET /items/{code}, live API",
        "captured_at": datetime.now(UTC).isoformat(),
        "craft_yields": yields,
        "entries": entries,
    }) + "\n")


if __name__ == "__main__":
    main()
