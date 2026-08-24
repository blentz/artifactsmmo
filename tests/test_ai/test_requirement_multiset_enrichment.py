"""The enriched requirement multiset — `RequirementGraphMemo.requirement_multiset_for`.

WAVE 3b: this file was `test_synergy_assembly.py` and its subject was
`progression_tree._synergy_map`, the impure B-assembly that turned each gear
candidate's multiset into a synergy multiplier. THE FLIP left `_synergy_map`
with zero callers and wave 3b deleted it (re-derived deletion list §3 row 16),
so every test that drove it went with it.

What is left is what those tests were BUILT ON and what survives: the enriched
multiset itself. `requirement_multiset_for` returns each item's demand
multiset augmented with synthetic `skill:<name>` tokens (one per craft/gather
gate in the closure), a `char_xp` token per DROP leaf, and the TRANSITIVELY
expanded buy-currency cost. These three tests pin that enrichment against an
independent recompute and prove it fires on the real bundle graph — none of
them mentions synergy. `tiers/synergy_core` is untouched and still live at
`tiers/taskmaster_choice` and `tiers/means_worth`.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_graph_memo import CHAR_XP, SKILL_PREFIX
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.source_kind import SourceKind

_BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="module")
def bundle_game_data() -> GameData:
    """The committed live-API bundle as GameData (same source as the audit
    census fixture) — the real graph, so the firing check is not synthetic."""
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))


def test_enriched_multiset_fires_on_real_graph(bundle_game_data: GameData):
    """Runtime activation of the enrichment (spec §7): on the real bundle graph
    the multiset must actually carry skill tokens (some craftable is skill-gated)
    and at least one closure a char_xp token (some route hits a monster drop) —
    proof the skill/char enrichment is not silently empty."""
    memo = bundle_game_data.requirement_graph
    graph = memo.graph()
    saw_skill = False
    saw_char = False
    for code in graph.edges:
        ms = memo.requirement_multiset_for(code)
        if any(k.startswith(SKILL_PREFIX) for k in ms):
            saw_skill = True
        if CHAR_XP in ms:
            saw_char = True
        if saw_skill and saw_char:
            break
    assert saw_skill, "no craftable in the bundle carries a skill token — enrichment inert"
    assert saw_char, "no closure in the bundle routes through a drop — char_xp inert"


def _expected_currency_cost(gd: GameData, item: str, qty: int,
                            seen: frozenset[str] = frozenset()) -> tuple[str, int] | None:
    """Independent recompute of `RequirementGraphMemo._currency_cost`'s
    CONTRACT (walk the NPC-purchase currency chain to the currency actually
    earned, refusing a hop that re-prices the item in itself or closes a
    cycle) — written as its OWN recursion here, not a call into the memo's
    private method, so a regression in that method's recursion would make
    this recompute DISAGREE with it rather than silently agreeing with
    whatever the code under test happens to do. Task 1 achievability-factor
    fix round 1 (review finding 2): the previous version of this recompute
    inlined the OLD one-hop pricing, so it only ever matched production
    because the committed bundle happens to contain no chained currency —
    never because it validated the recursion."""
    purchases = gd.npc_purchases(item)
    if not purchases:
        return None
    _npc, price, currency = min(purchases, key=lambda p: p[1])
    if currency == item or currency in seen:
        return None
    deeper = _expected_currency_cost(gd, currency, price * qty, seen | {item})
    return deeper if deeper is not None else (currency, price * qty)


def test_requirement_multiset_matches_independent_recompute(bundle_game_data: GameData):
    """Differential pin: the enriched multiset equals `demand_for` PLUS a
    from-scratch recompute of the closure-count skill tokens, the DROP-leaf
    char_xp token, and the TRANSITIVELY-expanded buy-currency cost (Task 1,
    achievability-factor). Any drift in the enrichment arithmetic (a skill
    source skipped, a weight not incremented, the char count zeroed, or the
    currency chain stopping one hop short) fails here."""
    memo = bundle_game_data.requirement_graph
    graph = memo.graph()
    target = next((code for code in graph.edges
                   if any(k.startswith(SKILL_PREFIX)
                          for k in memo.requirement_multiset_for(code))
                   or CHAR_XP in memo.requirement_multiset_for(code)), None)
    assert target is not None, "no enriched multiset in the bundle to differentiate against"

    expected: dict[str, int] = dict(memo.demand_for(target))
    closure = requirement_closure(graph, [target])
    for item in closure:
        craft = graph.craft_skill.get(item)
        if craft is not None:
            expected[SKILL_PREFIX + craft[0]] = expected.get(SKILL_PREFIX + craft[0], 0) + 1
        gather = graph.gather_skill.get(item)
        if gather is not None:
            expected[SKILL_PREFIX + gather[0]] = expected.get(SKILL_PREFIX + gather[0], 0) + 1
        if SourceKind.BUY in graph.leaves.get(item, frozenset()):
            priced = _expected_currency_cost(bundle_game_data, item, expected.get(item, 1))
            if priced is not None:
                currency, units = priced
                expected[currency] = expected.get(currency, 0) + units
    drop_leaves = sum(1 for item in closure
                      if SourceKind.DROP in graph.leaves.get(item, frozenset()))
    if drop_leaves:
        expected[CHAR_XP] = drop_leaves

    assert dict(memo.requirement_multiset_for(target)) == expected


def test_buy_only_item_carries_its_currency_cost(bundle_game_data: GameData):
    """The blindness fix: a buy-only item's real work is its currency PRICE,
    expanded TRANSITIVELY to the currency actually earned (Task 1,
    achievability-factor) — not its (empty) recipe closure, and not just the
    FIRST currency hop. `requirement_multiset_for` must expose that currency
    so synergy can weigh it — otherwise an expensive currency grind (e.g.
    lich_race_medal → 100 event_ticket) is invisible and scores as a
    one-token root that serves nothing else can be recognised against."""
    memo = bundle_game_data.requirement_graph
    graph = memo.graph()
    target = next((code for code in graph.leaves
                   if SourceKind.BUY in graph.leaves[code]
                   and bundle_game_data.npc_purchases(code)), None)
    assert target is not None, "no buy-only currency item in the bundle to check"
    ms = memo.requirement_multiset_for(target)
    demanded = memo.demand_for(target).get(target, 1)
    priced = _expected_currency_cost(bundle_game_data, target, demanded)
    assert priced is not None, f"{target} has NPC purchases but resolved to no currency"
    currency, units = priced
    assert ms.get(currency, 0) >= units, (
        f"{target} multiset {dict(ms)} is missing its {currency} cost (>= {units})")
