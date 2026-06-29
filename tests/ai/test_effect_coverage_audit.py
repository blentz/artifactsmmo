"""Live-data regression: every item effect in the API is modeled or deliberately carved.

This is a token-gated integration test (mirrors test_gear_taxonomy_live_audit.py).
The load itself succeeding proves that _build_items raised on NONE of the live items —
i.e., every live item effect code is either modeled in ItemStats or in one of the
carve sets (_ITEM_EFFECT_CARVEOUTS / _RUNE_ABILITY_CARVEOUTS / "threat").

Skipped when no TOKEN file is present (token-less CI). The offline unit tests in
test_game_data_item_effect_guard.py give 100%-coverage of the guard branches;
this test verifies the live API hasn't added a new unmodeled code.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData, _ITEM_EFFECT_CARVEOUTS
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config


@pytest.mark.integration
@pytest.mark.skipif(not Path("TOKEN").exists(),
                    reason="live-data audit needs a TOKEN file + API access")
def test_live_item_effect_coverage():
    """The live full-catalog load succeeds (guard raised on nothing) and
    bag_of_gold carries the expected gold_value."""
    cm = ClientManager()
    cm.initialize(Config.from_token_file())
    try:
        # force_refresh so we hit the real API, not a stale cache
        gd = GameData.load(cm.client, force_refresh=True)
        # bag_of_gold is the canonical gold-bag: effect `gold` value 2500
        stats = gd.item_stats("bag_of_gold")
        assert stats is not None, "bag_of_gold must be present in the API"
        assert stats.gold_value == 2500
        # Carve sets must contain the documented entries
        assert "gems" in _ITEM_EFFECT_CARVEOUTS
        assert "christmas_magic" in _ITEM_EFFECT_CARVEOUTS
    finally:
        cm.client.get_httpx_client().close()
        ClientManager._instance = None
        ClientManager._client = None
        ClientManager._api = None
        ClientManager._config = None
