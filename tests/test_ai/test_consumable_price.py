"""The price of one consumable read from the world
(`docs/PLAN_consumable_utility.md` increment 2)."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.consumable_price as price_mod
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.consumable_price import (
    FIGHT_SECONDS,
    buy_gold,
    consumable_price_of,
    gold_per_second,
    held_count,
    make_seconds,
    replacement_price_of,
)
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY, Source, SourceKind
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import fight_gold_rate
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json")
_CTX = NO_PROFILE_CONTEXT


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(_BUNDLE)


def _source(kind: SourceKind, code: str) -> Source:
    return Source(kind=kind, code=code, yield_per=1, capacity=UNBOUNDED_CAPACITY)


class TestHeld:
    def test_bag_bank_and_the_slots_that_wear_it(self) -> None:
        state = make_state(inventory={"potion": 2}, bank_items={"potion": 3},
                           utility1_slot_quantity=4, utility2_slot_quantity=7)
        state = replace(state, equipment={**state.equipment, "utility1_slot": "potion",
                                          "utility2_slot": "other"})
        assert held_count("potion", state) == 2 + 3 + 4
        assert held_count("other", state) == 7
        assert held_count("absent", state) == 0

    def test_held_reads_nothing_else(self, monkeypatch: pytest.MonkeyPatch) -> None:
        def boom(*_: object, **__: object) -> None:
            raise AssertionError("a held item must not be priced")
        monkeypatch.setattr(price_mod, "acquisition_actions", boom)
        monkeypatch.setattr(price_mod, "obtain_sources", boom)
        state = make_state(bank_items={"potion": 1})
        assert consumable_price_of("potion", state, GameData(), _CTX) == 0


class TestMake:
    def test_the_walk_in_fight_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)
        assert make_seconds("x", make_state(), GameData(), _CTX, None) == 4 * FIGHT_SECONDS == 120

    def test_an_unobtainable_walk_is_no_make_side(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: UNOBTAINABLE_PER_UNIT)
        assert make_seconds("x", make_state(), GameData(), _CTX, None) is None


class TestBuy:
    def _patch(self, monkeypatch: pytest.MonkeyPatch, sources: list[Source]) -> None:
        monkeypatch.setattr(price_mod, "obtain_sources", lambda *a, **k: sources)
        npc = {"cheap_npc": (30, "gold"), "dear_npc": (90, "gold"), "coin_npc": (1, "tasks_coin")}
        monkeypatch.setattr(price_mod, "npc_price_of", lambda item, code, gd: npc[code])
        monkeypatch.setattr(price_mod, "ge_price_of", lambda item, order, gd: {"o1": 45}[order])

    def test_the_cheapest_gold_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, [_source(SourceKind.BUY, "dear_npc"),
                                  _source(SourceKind.GE_FILL, "o1"),
                                  _source(SourceKind.BUY, "cheap_npc"),
                                  _source(SourceKind.CRAFT, "x")])
        assert buy_gold("x", make_state(), GameData(), _CTX) == 30

    def test_a_ge_order_counts(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, [_source(SourceKind.BUY, "dear_npc"),
                                  _source(SourceKind.GE_FILL, "o1")])
        assert buy_gold("x", make_state(), GameData(), _CTX) == 45

    def test_another_currency_is_not_a_gold_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, [_source(SourceKind.BUY, "coin_npc")])
        assert buy_gold("x", make_state(), GameData(), _CTX) is None

    def test_nobody_sells(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._patch(monkeypatch, [])
        assert buy_gold("x", make_state(), GameData(), _CTX) is None


class TestGoldRate:
    def test_no_grind_target_earns_nothing(self) -> None:
        assert gold_per_second(make_state(), GameData(), _CTX) == 0

    def test_the_grind_targets_rate_per_second(self, game_data: GameData) -> None:
        state = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        ctx = replace(_CTX, combat_monster="wolf")
        rate = fight_gold_rate(state, game_data, "wolf")
        assert rate > 0
        assert gold_per_second(state, game_data, ctx) == rate / 30


class TestPrice:
    def test_the_cheaper_of_make_and_buy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)   # 120 s
        monkeypatch.setattr(price_mod, "buy_gold", lambda *a: 40)
        monkeypatch.setattr(price_mod, "gold_per_second", lambda *a: Fraction(1, 2))  # 80 s
        assert consumable_price_of("x", make_state(), GameData(), _CTX) == 80
        monkeypatch.setattr(price_mod, "gold_per_second", lambda *a: Fraction(0))
        assert consumable_price_of("x", make_state(), GameData(), _CTX) == 120

    def test_end_to_end_on_the_committed_bundle(self, game_data: GameData) -> None:
        state: WorldState = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        ctx = replace(_CTX, combat_monster="wolf")
        # Worn in utility1: free.
        assert state.equipment.get("utility1_slot") == "small_health_potion"
        assert consumable_price_of("small_health_potion", state, game_data, ctx) == 0
        # Not held: the walk (no gold seller for it in this world) in fight seconds.
        walk = make_seconds("cooked_chicken", state, game_data, ctx, None)
        assert walk is not None and walk > 0
        assert buy_gold("cooked_chicken", state, game_data, ctx) is None
        assert consumable_price_of("cooked_chicken", state, game_data, ctx) == walk

    def test_a_held_unit_has_a_replacement_price(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # Held units are free; a unit past them costs its replacement, as if
        # none were held (USER 2026-10-09, "free until used up").
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)   # 120 s
        monkeypatch.setattr(price_mod, "buy_gold", lambda *a: None)
        state = make_state(bank_items={"x": 3})
        assert consumable_price_of("x", state, GameData(), _CTX) == 0
        assert replacement_price_of("x", state, GameData(), _CTX) == 120
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: UNOBTAINABLE_PER_UNIT)
        assert replacement_price_of("x", state, GameData(), _CTX) is None
