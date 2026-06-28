"""Locks the effect-derived gear classification against real v8 data.

This is a live-data regression test: it loads the REAL game catalog from the
API and asserts the ground-truth combat/defensive type sets. It is skipped when
no TOKEN file is present (token-less CI), so the default suite stays green; the
classified `src` lines are covered by the offline unit tests regardless, so the
100%-coverage gate holds in both modes. Run it locally (TOKEN present) to verify
the live taxonomy still matches the proved core's expectation.
"""

from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config

EXPECTED_COMBAT = frozenset({
    "amulet", "artifact", "body_armor", "boots", "helmet", "leg_armor",
    "ring", "rune", "shield", "weapon"})


@pytest.mark.integration
@pytest.mark.skipif(not Path("TOKEN").exists(),
                    reason="live-data audit needs a TOKEN file + API access")
def test_live_combat_gear_classification():
    cm = ClientManager()
    cm.initialize(Config.from_token_file())
    try:
        gd = GameData.load(cm.client, force_refresh=True)
        assert gd.combat_gear_types == EXPECTED_COMBAT
        assert "utility" not in gd.combat_gear_types   # consumable carve
        assert "bag" not in gd.combat_gear_types        # not combat-bearing
        assert gd.defensive_gear_types == EXPECTED_COMBAT - frozenset({"weapon"})
    finally:
        # Close the real httpx connection pool (else a leaked SSL socket is
        # promoted to an error at a later test under -W error) and reset the
        # ClientManager singleton so no live client/config leaks across tests.
        cm.client.get_httpx_client().close()
        ClientManager._instance = None
        ClientManager._client = None
        ClientManager._api = None
        ClientManager._config = None
