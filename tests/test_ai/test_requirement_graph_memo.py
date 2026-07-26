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


def _gd_with_self_price() -> GameData:
    """x is sold by a vendor priced in ITSELF — a degenerate listing with no
    external currency at all (the 1-hop degenerate case of a cycle)."""
    gd = GameData()
    gd.world.npc_stock["vendor_x"] = {"x": 5}
    gd.world.npc_buy_currency["vendor_x"] = {"x": "x"}
    gd.world.npc_tiles["vendor_x"] = (0, 0)
    return gd


def test_buy_only_currency_expands_transitively():
    """lich_race_trophy costs 10 lich_race_medal; each medal costs 100
    event_ticket. The multiset must show the 1000 tickets, not stop at 10
    medals — un-expanded, the most expensive candidate reads as the cheapest."""
    gd = _gd_with_chain()          # trophy <- 10 medal <- 100 event_ticket each
    ms = gd.requirement_graph.requirement_multiset_for("trophy")
    assert ms.get("event_ticket") == 1000
    assert "medal" not in ms, "the intermediate currency must be expanded, not listed"


def test_currency_cycle_terminates_at_the_last_resolvable_hop():
    """A priced in B priced in A must not recurse forever, AND must not
    attribute A's cost to A ITSELF (the item the deepest frame re-encounters
    when the loop closes). The last RESOLVABLE hop is "a costs 1 b" — the
    walk must stop there, not drill into b's own (cyclic) currency and
    report 'a' as its own price. Asserting full CONTENT here, not merely
    `is not None`, is the point: a version that self-inflated `a` (reporting
    `{"a": 2, ...}` instead of `{"a": 1, "b": 1}`) would still be non-None
    and would have passed a weaker check."""
    gd = _gd_with_cycle()          # a <- 1 b, b <- 1 a
    ms = gd.requirement_graph.requirement_multiset_for("a")
    assert ms == {"a": 1, "b": 1}


def test_self_priced_item_does_not_self_inflate():
    """An item priced in itself has no external currency to expand into.
    `_currency_cost` must refuse that hop (return None) rather than
    reporting the item's own code as its currency — which would silently
    double its own multiset entry via `out[currency] += units`."""
    gd = _gd_with_self_price()     # x <- 1 x (degenerate: no real currency)
    ms = gd.requirement_graph.requirement_multiset_for("x")
    assert ms == {"x": 1}
