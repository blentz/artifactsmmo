"""The price of one consumable read from the world
(`docs/PLAN_consumable_utility.md` increment 2)."""

from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.consumable_price as price_mod
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.consumable_price import (
    buy_gold,
    consumable_price_of,
    gold_per_second,
    held_count,
    make_seconds,
    replacement_price_of,
)
from artifactsmmo_cli.ai.fight_walk import walk_seconds
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective_result import GearObjective, GearPiece
from artifactsmmo_cli.ai.obtain_sources import UNBOUNDED_CAPACITY, Source, SourceKind
from artifactsmmo_cli.ai.scenario import SCENARIOS, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.task_worth import fight_gold_rate
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

_BUNDLE = (Path(__file__).resolve().parent / "scenarios" / "fixtures" / "gamedata_bundle.json")
_CTX = TIMED_NO_PROFILE_CONTEXT


@pytest.fixture(scope="module")
def game_data() -> GameData:
    return load_bundle_game_data(_BUNDLE)


def _objective(monster: str, fighter: WorldState | None = None) -> GearObjective:
    """A gear objective on `monster` with one piece missing: `farm_target`
    names no grind target for it. `fighter` is the one wearing its `L*`."""
    piece = GearPiece("shield_slot", "wooden_shield", 0, Fraction(1), Fraction(10))
    return GearObjective(monster, {"shield_slot": "wooden_shield"}, Fraction(1), (piece,),
                         fighter=fighter)


def _gold_per_second(fighter: WorldState, game_data: GameData, monster: str) -> Fraction:
    """Fight gold per second in `fighter`'s gear: the gold per fight-equivalent
    over that fight's learned seconds (spec 2026-10-18 §2.9)."""
    seconds = walk_seconds(fighter, game_data, monster, (), _CTX.timing())
    return fight_gold_rate(fighter, game_data, monster, seconds) / seconds


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
    def test_the_walk_in_learned_action_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Four actions at the committed capture's mean action (spec §2.9,
        ruling CA): 35.77 s each."""
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)
        seconds = make_seconds("x", make_state(), GameData(), _CTX, None)
        assert seconds == 4 * _CTX.action_seconds_of()
        assert round(seconds, 2) == Fraction(14307, 100)

    def test_an_unlearned_action_has_no_seconds(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)
        with pytest.raises(ValueError, match="no learned action seconds"):
            make_seconds("x", make_state(), GameData(), NO_PROFILE_CONTEXT, None)

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
        rate = _gold_per_second(state, game_data, "wolf")
        assert rate > 0
        assert gold_per_second(state, game_data, ctx) == rate

    def test_no_grind_target_reads_the_objectives_monster(self, game_data: GameData) -> None:
        """Ruling AL (final review F5): while a piece of `L*` is missing
        `farm_target` names no grind target, but buying is still priced at
        the objective's `m*` gold rate — a pricing input, not a fight choice."""
        state = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        fighter = replace(state, attack={**state.attack, "fire": state.attack.get("fire", 0) + 40})
        ctx = replace(_CTX, combat_monster=None, gear_objective=_objective("wolf", fighter))
        assert gold_per_second(state, game_data, ctx) == _gold_per_second(fighter, game_data, "wolf")
        assert _gold_per_second(fighter, game_data, "wolf") != _gold_per_second(
            state, game_data, "wolf")

    def test_an_objective_without_its_fighter_raises(self, game_data: GameData) -> None:
        state = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        ctx = replace(_CTX, combat_monster=None, gear_objective=_objective("wolf"))
        with pytest.raises(ValueError, match="carries no fighter"):
            gold_per_second(state, game_data, ctx)

    def test_an_unlearned_fight_has_no_seconds(self, game_data: GameData) -> None:
        """Spec 2026-10-18 §2.9: a fight's seconds are learned; a context that
        carries none prices no fight, rather than stand a constant in."""
        state = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        ctx = replace(NO_PROFILE_CONTEXT, combat_monster="wolf")
        with pytest.raises(ValueError, match="no learned fight seconds"):
            gold_per_second(state, game_data, ctx)

    def test_the_grind_target_outranks_the_objectives_monster(
            self, game_data: GameData) -> None:
        state = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        ctx = replace(_CTX, combat_monster="wolf", gear_objective=_objective("chicken", state))
        assert gold_per_second(state, game_data, ctx) == _gold_per_second(state, game_data, "wolf")


class TestBuyOnlyWhileGearing:
    def test_a_buy_only_consumable_keeps_its_price(self) -> None:
        """Ruling AL on the committed bundle's order book: `lava_fish` is
        sold on the Grand Exchange and has no make route for l20_boost_stock
        (no bundle POTION is buy-only, so the buy-only consumable is a food).
        With no grind target and no objective it is unpriced; with the
        objective's `m*` it has a price."""
        world = load_bundle_game_data(_BUNDLE, with_ge_orders=True)
        state = scenario_state(SCENARIOS["l20_boost_stock"], world)
        assert make_seconds("lava_fish", replace(state, inventory={}, bank_items={}),
                            world, _CTX, None) is None
        assert buy_gold("lava_fish", state, world, _CTX) is not None
        assert consumable_price_of("lava_fish", state, world, _CTX) is None
        gearing = replace(_CTX, combat_monster=None, gear_objective=_objective("wolf", state))
        price = consumable_price_of("lava_fish", state, world, gearing)
        assert price is not None and price > 0


class TestPrice:
    def test_the_cheaper_of_make_and_buy(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)   # 143.07 s
        monkeypatch.setattr(price_mod, "buy_gold", lambda *a: 40)
        monkeypatch.setattr(price_mod, "gold_per_second", lambda *a: Fraction(1, 2))  # 80 s
        assert consumable_price_of("x", make_state(), GameData(), _CTX) == 80
        monkeypatch.setattr(price_mod, "gold_per_second", lambda *a: Fraction(0))
        assert consumable_price_of("x", make_state(), GameData(), _CTX) == 4 * _CTX.action_seconds_of()

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
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: 4)   # 143.07 s
        monkeypatch.setattr(price_mod, "buy_gold", lambda *a: None)
        state = make_state(bank_items={"x": 3})
        assert consumable_price_of("x", state, GameData(), _CTX) == 0
        assert replacement_price_of("x", state, GameData(), _CTX) == 4 * _CTX.action_seconds_of()
        monkeypatch.setattr(price_mod, "acquisition_actions", lambda *a, **k: UNOBTAINABLE_PER_UNIT)
        assert replacement_price_of("x", state, GameData(), _CTX) is None


class TestReplacementIgnoresHoldings:
    """The make side of a replacement price walks from EMPTY holdings: the
    real walk credits a bag unit at 0 actions and a banked one at a withdraw,
    so a held food priced its own replacement at nothing and the stock made
    itself forever (live 2026-10-14: cooked_trout, 38 in C3P0's bag, priced 0 s
    where making one takes 4 actions)."""

    def test_a_held_food_and_its_input_price_the_full_walk(self, game_data: GameData) -> None:
        bare = scenario_state(SCENARIOS["l20_boost_stock"], game_data)
        bare = replace(bare, inventory={}, bank_items={})
        ctx = replace(_CTX, combat_monster="wolf")
        walk = make_seconds("cooked_chicken", bare, game_data, ctx, None)
        assert walk is not None and walk > 0
        held = replace(bare, inventory={"cooked_chicken": 5, "raw_chicken": 5},
                       bank_items={"cooked_chicken": 5, "raw_chicken": 5})
        assert make_seconds("cooked_chicken", held, game_data, ctx, None) < walk
        assert replacement_price_of("cooked_chicken", held, game_data, ctx) == walk
