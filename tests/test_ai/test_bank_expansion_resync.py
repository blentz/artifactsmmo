"""A bank expansion must refresh the bank state it just changed.

Live 2026-09-13, 15 minutes after the BANK_EXPAND promotion went live:

    13:28:26  C3P0  BuyBankExpansion  ok  -7000   gold 15167
    13:28:29  C3P0  BuyBankExpansion  ok  -14000  gold  1167

Two purchases three seconds apart, 21,000 gold, bank 70 -> 110 slots. After the
first buy the fill was ~55% against a 75% trigger and the rung should have gone
quiet; it fired again because `state.bank_capacity` still said 70. `_sync_bank`
re-reads capacity, but `player._execute` only calls it for the deposit and
withdraw actions — `BuyBankExpansionAction` was never added to that tuple.

The same staleness hit the SIBLINGS through a different field. Lor spent ten
consecutive cycles on `error:HTTP_492` holding 26,698 gold against a real price
of 28,000: `expansion_fires` refuses on `pocket >= cost`, but Lor's
`game_data.next_expansion_cost` was the value cached at ITS session start,
before C3P0 moved the price twice. `_sync_bank` fetches `/my/bank`, whose
`BankSchema` carries `next_expansion_cost`, and threw that field away.

Latent until 68585b6c: the rung had never once been selected, so nothing
exercised the path.
"""

from unittest.mock import MagicMock, patch

from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.player import GamePlayer
from tests.test_ai.fixtures import make_state


def _bank_reads(slots: int, cost: int, gold: int = 500):
    items = MagicMock()
    items.data = []
    details = MagicMock()
    details.data = MagicMock()
    details.data.gold = gold
    details.data.slots = slots
    details.data.next_expansion_cost = cost
    return items, details


class TestSyncBankCarriesTheExpansionPrice:
    def test_sync_refreshes_the_next_expansion_cost(self):
        """The price moves whenever ANY character buys, so the number a
        sibling's gate reads has to come from the same read that already
        refreshes capacity — not from its own session-start snapshot."""
        player = GamePlayer(character="hero")
        player.game_data = GameData()
        player.game_data._next_expansion_cost = 7000
        items, details = _bank_reads(slots=110, cost=28000)

        with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=items):
            with patch("artifactsmmo_cli.ai.player.get_bank_details", return_value=details):
                new_state = player._sync_bank(MagicMock(), make_state())

        assert player.game_data.next_expansion_cost == 28000
        assert new_state.bank_capacity == 110


class TestBuyingAnExpansionResyncsTheBank:
    def test_the_buy_triggers_a_bank_resync(self):
        """Without this the buyer re-fires on its own stale fill ratio — the
        21,000-gold double purchase."""
        player = GamePlayer(character="hero")
        player.game_data = GameData()
        player.state = make_state(bank_items={}, bank_capacity=70, gold=22167)
        player.game_data._next_expansion_cost = 7000
        action = BuyBankExpansionAction(bank_location=(0, 0), accessible=True)
        items, details = _bank_reads(slots=90, cost=14000)

        bought = make_state(bank_items={}, bank_capacity=70, gold=15167)
        with patch.object(BuyBankExpansionAction, "execute", return_value=bought):
            with patch("artifactsmmo_cli.ai.player.get_bank_items", return_value=items):
                with patch("artifactsmmo_cli.ai.player.get_bank_details",
                           return_value=details):
                    new_state, outcome = player._execute(action, MagicMock())

        assert outcome == "ok"
        assert new_state.bank_capacity == 90, (
            "capacity must come from the post-buy read, not the pre-buy state")
        assert player.game_data.next_expansion_cost == 14000
