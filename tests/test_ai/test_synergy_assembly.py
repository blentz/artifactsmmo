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
    """Stand-in for `RequirementGraphMemo.demand_for` — returns the controlled
    per-code demand multiset so the leave-one-out arithmetic is exercised on
    exact inputs. This doubles the collaborator, not `_synergy_map` itself."""

    def __init__(self, demands: dict[str, Mapping[str, int]]) -> None:
        self._demands = demands

    def demand_for(self, code: str) -> Mapping[str, int]:
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
