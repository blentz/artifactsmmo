"""Tests for `RequirementGraphMemo._currency_cost` / the buy-only currency
enrichment arm of `requirement_multiset_for` (Task 1, achievability-factor).

The multiset priced a BUY leaf in its DIRECT currency and stopped:
`lich_race_trophy` costs 10 `lich_race_medal`, and each medal itself costs 100
`event_ticket`, but the un-expanded multiset showed only 10 medals (11 tokens
total) — the most expensive item in the catalog read as the CHEAPEST. Fixed by
walking the currency chain to the currency actually earned, cycle-safe.
"""

from artifactsmmo_cli.ai.game_data import GameData


def _gd_with_chain() -> GameData:
    """trophy <- 10 medal <- 100 event_ticket each.

    Neither hop is a craft recipe: both are NPC purchases priced in a
    non-gold currency, which is exactly the shape `lich_race_trophy` /
    `lich_race_medal` / `event_ticket` has in live data (Step 5 below). Real
    backing fields: `npc_purchases` reads `world.npc_stock` (price) and
    `world.npc_buy_currency` (currency); `npc_location` reads `world.npc_tiles`
    (there is no `npc_locations` field)."""
    gd = GameData()
    gd.world.npc_stock["trophy_vendor"] = {"trophy": 10}
    gd.world.npc_buy_currency["trophy_vendor"] = {"trophy": "medal"}
    gd.world.npc_tiles["trophy_vendor"] = (0, 0)
    gd.world.npc_stock["medal_vendor"] = {"medal": 100}
    gd.world.npc_buy_currency["medal_vendor"] = {"medal": "event_ticket"}
    gd.world.npc_tiles["medal_vendor"] = (1, 1)
    return gd


def _gd_with_cycle() -> GameData:
    """a is bought for 1 b; b is bought for 1 a — a currency cycle. Pricing
    either in terms of the other must terminate via the `seen` guard, not
    recurse forever."""
    gd = GameData()
    gd.world.npc_stock["vendor_a"] = {"a": 1}
    gd.world.npc_buy_currency["vendor_a"] = {"a": "b"}
    gd.world.npc_tiles["vendor_a"] = (0, 0)
    gd.world.npc_stock["vendor_b"] = {"b": 1}
    gd.world.npc_buy_currency["vendor_b"] = {"b": "a"}
    gd.world.npc_tiles["vendor_b"] = (1, 1)
    return gd


def test_buy_only_currency_expands_transitively():
    """lich_race_trophy costs 10 lich_race_medal; each medal costs 100
    event_ticket. The multiset must show the 1000 tickets, not stop at 10
    medals — un-expanded, the most expensive candidate reads as the cheapest."""
    gd = _gd_with_chain()          # trophy <- 10 medal <- 100 event_ticket each
    ms = gd.requirement_graph.requirement_multiset_for("trophy")
    assert ms.get("event_ticket") == 1000
    assert "medal" not in ms, "the intermediate currency must be expanded, not listed"


def test_currency_cycle_terminates():
    """A priced in B priced in A must not recurse forever."""
    gd = _gd_with_cycle()          # a <- 1 b, b <- 1 a
    assert gd.requirement_graph.requirement_multiset_for("a") is not None
