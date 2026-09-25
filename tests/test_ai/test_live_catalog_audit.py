"""Live-data regressions over ONE load of the real game catalog.

Two audits run against the live API:
- The effect-derived gear classification matches the proved core's expected
  combat/defensive type sets.
- Every live item effect is modelled or deliberately carved. The load itself
  succeeding proves `_build_items` raised on none of them.

Both are token-gated: skipped when no TOKEN file is present (token-less CI).
The offline unit tests cover every classified `src` line, so the
100%-coverage gate holds either way.

ONE LOAD, PACED. These were two modules, each forcing its own full catalog
refresh. Under xdist they ran in parallel beside a `play --all` fleet that
spends the same per-IP budget, collided into HTTP 429, and restarted their
whole loads into each other again. That happened on most gate runs of
2026-09-25. The module now loads once. The load is charged to a private
governor holding the fair share of the budget for the account's characters
plus this test, so it stays inside its slice while the fleet runs. The
governor's log is in memory: a test never writes to the fleet's real
learning DB (see `tests/conftest.py`'s `artifactsmmo_test_home`).
"""

from collections.abc import Iterator
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import _ITEM_EFFECT_CARVEOUTS, GameData
from artifactsmmo_cli.api_wrapper import APIWrapper
from artifactsmmo_cli.client_manager import ClientManager
from artifactsmmo_cli.config import Config
from artifactsmmo_cli.utils.rate_budget import parse_rate_limits
from artifactsmmo_cli.utils.rate_governor import RateGovernor
from artifactsmmo_cli.utils.request_log import RequestLog

EXPECTED_COMBAT = frozenset({
    "amulet", "artifact", "body_armor", "boots", "helmet", "leg_armor",
    "ring", "rune", "shield", "weapon"})

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not Path("TOKEN").exists(),
                       reason="live-data audit needs a TOKEN file + API access"),
]


@pytest.fixture(scope="module")
def live_game_data() -> Iterator[GameData]:
    """The real catalog, force-refreshed once and paced at a fair share of
    the per-IP budget."""
    cm = ClientManager()
    cm.initialize(Config.from_token_file())
    log = RequestLog(":memory:")
    try:
        api = APIWrapper(cm.client)
        characters = api.get_my_characters()
        rates = api.get_rate_limits()
        assert characters is not None and rates is not None, "roster/rates returned no data"
        sharers = len(characters.data) + 1
        limits = parse_rate_limits(rates.to_dict())
        yield GameData.load(
            cm.client, force_refresh=True,
            acquire_data=RateGovernor(
                limits.data.divided_by(sharers), 1, log, "data").acquire,
            acquire_account=RateGovernor(
                limits.account.divided_by(sharers), 1, log, "account").acquire)
    finally:
        log.close()
        # Close the real httpx pool (a leaked SSL socket is promoted to an error
        # under -W error) and reset the singleton so no live client leaks.
        cm.client.get_httpx_client().close()
        ClientManager._instance = None
        ClientManager._client = None
        ClientManager._api = None
        ClientManager._config = None


def test_live_combat_gear_classification(live_game_data: GameData) -> None:
    gd = live_game_data
    assert gd.combat_gear_types == EXPECTED_COMBAT
    assert "utility" not in gd.combat_gear_types   # consumable carve
    assert "bag" not in gd.combat_gear_types        # not combat-bearing
    assert gd.defensive_gear_types == EXPECTED_COMBAT - frozenset({"weapon"})


def test_live_item_effect_coverage(live_game_data: GameData) -> None:
    """The full live load succeeded (the guard raised on nothing), and
    bag_of_gold carries the expected gold_value."""
    stats = live_game_data.item_stats("bag_of_gold")
    assert stats is not None, "bag_of_gold must be present in the API"
    assert stats.gold_value == 2500
    assert "gems" in _ITEM_EFFECT_CARVEOUTS
    assert "christmas_magic" in _ITEM_EFFECT_CARVEOUTS
