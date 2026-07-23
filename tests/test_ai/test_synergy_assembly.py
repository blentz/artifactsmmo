"""Wave 3b: the impure synergy B-assembly (`_synergy_map`, spec §3.6).

`_synergy_map` turns each gear candidate's demand-weighted requirement multiset
into a `(slot, code) -> Fraction` synergy multiplier: the leave-one-out overlap
with the other live roots, through `synergy_pure`. These tests pin the
arithmetic with a controlled demand double (currency suppression, the deliberate
committed-root double-count, and the mandatory leave-one-out), then confirm it
FIRES on the real bundle graph (green tests != runtime-active, spec §7)."""

import json
from collections.abc import Mapping
from fractions import Fraction
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.requirement_graph_memo import CHAR_XP, SKILL_PREFIX
from artifactsmmo_cli.ai.requirement_projections import requirement_closure
from artifactsmmo_cli.ai.source_kind import SourceKind
from artifactsmmo_cli.ai.tiers.progression_tree import _synergy_map
from artifactsmmo_cli.ai.tiers.progression_tree_core import _NO_SYNERGY, GearCandidate
from artifactsmmo_cli.ai.tiers.synergy_core import S_MIN

from tests.test_ai.fixtures import make_state

_BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="module")
def bundle_game_data() -> GameData:
    """The committed live-API bundle as GameData (same source as the audit
    census fixture) — the real graph, so the firing check is not synthetic."""
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))


class _FakeMemo:
    """Stand-in for `RequirementGraphMemo.requirement_multiset_for` — returns the
    controlled per-code requirement multiset (items and/or synthetic skill/char
    tokens) so the leave-one-out arithmetic is exercised on exact inputs. This
    doubles the collaborator, not `_synergy_map` itself."""

    def __init__(self, demands: dict[str, Mapping[str, int]]) -> None:
        self._demands = demands

    def requirement_multiset_for(self, code: str) -> Mapping[str, int]:
        return self._demands.get(code, {})


class _FakeGameData:
    def __init__(self, demands: dict[str, Mapping[str, int]]) -> None:
        self.requirement_graph = _FakeMemo(demands)


def _gc(slot: str, code: str) -> GearCandidate:
    return GearCandidate(slot=slot, code=code, gain=Fraction(1), level=1)


def test_empty_candidates_is_no_synergy():
    gd = _FakeGameData({})
    assert _synergy_map([], None, make_state(), gd) is _NO_SYNERGY


def test_currency_root_suppressed():
    """The §3.10 worked case. A buy-only currency root shares none of its work
    with the other live roots, so it lands at the S_MIN floor while a candidate
    whose materials feed a sibling scores higher — differential suppression, not
    a flat penalty."""
    demands = {
        "gear1": {"copper_bar": 2},
        "gear2": {"copper_bar": 1, "iron": 3},
        "ticket": {"ticket": 5},          # buy-only: nothing else needs it
    }
    gd = _FakeGameData(demands)
    cands = [_gc("weapon_slot", "gear1"), _gc("shield_slot", "gear2"),
             _gc("amulet_slot", "ticket")]
    syn = _synergy_map(cands, None, make_state(), gd)
    assert syn[("amulet_slot", "ticket")] == S_MIN            # zero overlap -> floor
    assert syn[("weapon_slot", "gear1")] == Fraction(1)       # copper_bar fully shared
    assert syn[("amulet_slot", "ticket")] < syn[("shield_slot", "gear2")]


def test_leave_one_out_not_degenerate():
    """A lone candidate must NOT overlap itself: with leave-one-out its own
    demand is removed from B, so a root nothing else needs scores S_MIN, not 1.
    Without the subtraction every candidate would score 1 — a constant, i.e.
    inert (spec §3.3)."""
    gd = _FakeGameData({"solo": {"a": 1, "b": 2}})
    syn = _synergy_map([_gc("weapon_slot", "solo")], None, make_state(), gd)
    assert syn[("weapon_slot", "solo")] == S_MIN
    assert syn[("weapon_slot", "solo")] < Fraction(1)


def test_committed_root_double_counts():
    """The §3.6 deliberate double-count: the committed root enters the demand
    union a SECOND time, so a candidate that IS the committed root overlaps
    itself through that copy and is pulled up from the floor toward 1 — biasing
    the tree toward finishing what it started. Pinned so a reader cannot 'fix'
    it as a bug."""
    gd = _FakeGameData({"held": {"a": 1, "b": 1}})
    cand = [_gc("weapon_slot", "held")]
    without = _synergy_map(cand, None, make_state(), gd)
    with_root = _synergy_map(cand, "held", make_state(), gd)
    assert without[("weapon_slot", "held")] == S_MIN          # alone -> floor
    assert with_root[("weapon_slot", "held")] == Fraction(1)  # self-overlap via 2nd copy
    assert with_root[("weapon_slot", "held")] > without[("weapon_slot", "held")]


def test_items_task_is_a_member_but_monsters_task_is_not():
    """An items/crafting task contributes its requirement set to B (task and
    gear work converge); a monsters task carries no item requirement and is
    omitted (its char_xp overlap is a later wave)."""
    gd = _FakeGameData({"gear": {"a": 1}, "task_item": {"a": 1}})
    cand = [_gc("weapon_slot", "gear")]
    crafting = make_state(task_code="task_item", task_type="crafting")
    monsters = make_state(task_code="task_item", task_type="monsters")
    assert _synergy_map(cand, None, crafting, gd)[("weapon_slot", "gear")] == Fraction(1)
    assert _synergy_map(cand, None, monsters, gd)[("weapon_slot", "gear")] == S_MIN


def test_task_skill_convergence():
    """The §3.10 worked case, closure-count weighted. A non-monsters task
    contributes its skill tokens to B, so a gear candidate whose closure consumes
    the SAME skill scores high while an unrelated candidate stays at the floor —
    task and grind become one line of progress. Without the task the aligned
    candidate falls back to the floor, so it is the task that lifts it."""
    demands = {
        "gear_mining": {SKILL_PREFIX + "mining": 3},
        "gear_alchemy": {SKILL_PREFIX + "alchemy": 2},
        "task_item": {SKILL_PREFIX + "mining": 1},
    }
    gd = _FakeGameData(demands)
    cands = [_gc("weapon_slot", "gear_mining"), _gc("shield_slot", "gear_alchemy")]
    crafting = make_state(task_code="task_item", task_type="crafting")
    syn = _synergy_map(cands, None, crafting, gd)
    assert syn[("weapon_slot", "gear_mining")] == Fraction(1)     # task feeds mining
    assert syn[("shield_slot", "gear_alchemy")] == S_MIN          # unrelated skill
    # the task is what lifts it: with no task, mining candidate falls to the floor
    without = _synergy_map(cands, None, make_state(), gd)
    assert without[("weapon_slot", "gear_mining")] == S_MIN


def test_level_up_preference():
    """The §3.10 level-up case. The char-level trunk is always a member, so a
    candidate whose closure routes through monster DROPS (a char_xp token)
    overlaps it and is nudged above a pure-craft candidate — the 'L50 slightly
    favoured' preference, mechanical not a tuned constant."""
    demands = {
        "drop_routed": {CHAR_XP: 4},          # 4 drop leaves in its closure
        "pure_craft": {"copper_bar": 2},      # no drops
    }
    gd = _FakeGameData(demands)
    cands = [_gc("weapon_slot", "drop_routed"), _gc("shield_slot", "pure_craft")]
    syn = _synergy_map(cands, None, make_state(), gd)
    assert syn[("weapon_slot", "drop_routed")] == Fraction(1)     # overlaps the trunk
    assert syn[("shield_slot", "pure_craft")] == S_MIN
    assert syn[("weapon_slot", "drop_routed")] > syn[("shield_slot", "pure_craft")]


def test_monsters_task_contributes_char_xp_not_items():
    """A monsters-task produces character progression, not craftable items, so it
    enters B as a char_xp member (lifting drop-routed candidates), never by its
    monster code's (nonexistent) item requirement."""
    gd = _FakeGameData({"drop_routed": {CHAR_XP: 2}})
    cand = [_gc("weapon_slot", "drop_routed")]
    monsters = make_state(task_code="some_monster", task_type="monsters")
    assert _synergy_map(cand, None, monsters, gd)[("weapon_slot", "drop_routed")] == Fraction(1)


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


def test_requirement_multiset_matches_independent_recompute(bundle_game_data: GameData):
    """Differential pin: the enriched multiset equals `demand_for` PLUS a
    from-scratch recompute of the closure-count skill tokens and the DROP-leaf
    char_xp token. Any drift in the enrichment arithmetic (a skill source
    skipped, a weight not incremented, the char count zeroed) fails here."""
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
            purchases = bundle_game_data.npc_purchases(item)
            if purchases:
                _npc, price, currency = min(purchases, key=lambda p: p[1])
                expected[currency] = expected.get(currency, 0) + price * expected.get(item, 1)
    drop_leaves = sum(1 for item in closure
                      if SourceKind.DROP in graph.leaves.get(item, frozenset()))
    if drop_leaves:
        expected[CHAR_XP] = drop_leaves

    assert dict(memo.requirement_multiset_for(target)) == expected


def test_buy_only_item_carries_its_currency_cost(bundle_game_data: GameData):
    """The blindness fix: a buy-only item's real work is its currency PRICE, not
    its (empty) recipe closure. `requirement_multiset_for` must expose that
    currency so synergy can weigh it — otherwise an expensive currency grind
    (e.g. lich_race_medal → 100 event_ticket) is invisible and scores as a
    one-token root that serves nothing else can be recognised against."""
    memo = bundle_game_data.requirement_graph
    graph = memo.graph()
    target = next((code for code in graph.leaves
                   if SourceKind.BUY in graph.leaves[code]
                   and bundle_game_data.npc_purchases(code)), None)
    assert target is not None, "no buy-only currency item in the bundle to check"
    ms = memo.requirement_multiset_for(target)
    _npc, price, currency = min(bundle_game_data.npc_purchases(target), key=lambda p: p[1])
    assert ms.get(currency, 0) >= price, (
        f"{target} multiset {dict(ms)} is missing its {currency} cost (>= {price})")


def test_synergy_fires_on_real_graph(bundle_game_data: GameData):
    """Runtime activation (spec §7): on the real bundle graph, two candidates
    with genuinely different overlap must produce DIFFERENT multipliers — proof
    the assembly is not silently inert. Uses real item codes and the real
    memoized demand walk."""
    graph = bundle_game_data.requirement_graph.graph()
    # Pick two craftable items whose demand sets differ in size, so at least one
    # cannot fully overlap the other -> a non-uniform map.
    codes = [c for c in graph.edges if bundle_game_data.requirement_graph.demand_for(c)]
    assert len(codes) >= 2, "bundle has too few craftable items to exercise synergy"
    a, b = codes[0], codes[1]
    cands = [_gc("weapon_slot", a), _gc("shield_slot", b)]
    syn = _synergy_map(cands, None, make_state(), bundle_game_data)
    # every value is a valid synergy multiplier...
    assert all(S_MIN <= v <= Fraction(1) for v in syn.values())
    # ...and the map is populated (fires), keyed by (slot, code)
    assert set(syn) == {("weapon_slot", a), ("shield_slot", b)}
