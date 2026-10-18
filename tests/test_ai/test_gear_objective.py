"""The global gear objective `(L*, m*)` on the real bundle world (spec
2026-10-18 §2.2-§2.4, §5).

`L*` is the best loadout of ACHIEVABLE level-legal gear for the monster `m*` it
farms best. Achievable is a fixed point over a projected fighter, never the
worn gear; the missing pieces come in the core's order (layer, then gain per
price).
"""

from collections import Counter
from dataclasses import replace
from fractions import Fraction
from pathlib import Path

import pytest

import artifactsmmo_cli.ai.gear_objective as mod
from artifactsmmo_cli.ai.actions.combat import FIGHT_LEVEL_GAP_CEILING
from artifactsmmo_cli.ai.combat import fight_loadout, win_probability
from artifactsmmo_cli.ai.equipment.loadout_picker import _ordered_slots
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.gear_objective import achievable, fighter_owning, gear_objective
from artifactsmmo_cli.ai.gear_objective_core import piece_order_key
from artifactsmmo_cli.ai.gear_objective_result import GearObjective
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.learning.yield_reprs import grind_xp_repr
from artifactsmmo_cli.ai.loop_rate import food_menu
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_fight_winnable
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, load_bundle_game_data, scenario_state
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state

BUNDLE = Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json"
CTX = SelectionContext(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                       initial_xp=0, task_exchange_min_coins=0, combat_monster=None)
COPPER = {"weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
          "boots_slot": "copper_boots", "ring1_slot": "copper_ring"}
"""A level-12 character's worn copper set."""

ROBBY_WORN = {"weapon_slot": "death_knight_sword", "shield_slot": "slime_shield",
              "helmet_slot": "hard_leather_helmet", "body_armor_slot": "bandit_armor",
              "leg_armor_slot": "hard_leather_pants", "boots_slot": "snakeskin_boots",
              "ring1_slot": "ring_of_chance", "ring2_slot": "ring_of_chance",
              "amulet_slot": "skull_amulet", "artifact1_slot": "novice_guide",
              "rune_slot": "lifesteal_rune"}
"""Robby's live loadout (2026-10-18), less `lich_race_medal`, which the
committed bundle predates."""


def _robby(equipment: dict[str, str] = ROBBY_WORN) -> WorldState:
    """Robby's live shape (spec §1.2, his sheet on 2026-10-18): level 41, the
    server's own stat totals for the worn gear less the `lich_race_medal`'s
    (dmg 5, prospecting 25; its initiative 100 is not here because the
    fixture's initiative is 0), since `_bare` cannot strip an item the bundle
    does not know; gearcrafting 23,
    jewelrycrafting 22, weaponcrafting 22, and the alchemy 32 and cooking 34
    that make his potion loadouts stockable (no fight that pays him XP is won
    on bare gear alone)."""
    worn: dict[str, str | None] = {slot: None for slot in make_state().equipment}
    worn.update(equipment)
    return make_state(level=41, hp=845, max_hp=845, gold=0, bank_items={},
                      skills={"gearcrafting": 23, "jewelrycrafting": 22, "weaponcrafting": 22,
                              "alchemy": 32, "cooking": 34, "mining": 25, "woodcutting": 27,
                              "fishing": 29},
                      equipment=worn, attack={"fire": 37, "earth": 37, "water": 0, "air": 0},
                      dmg=24, dmg_elements={"fire": 30, "earth": 30, "water": 0, "air": 20},
                      resistance={"fire": 7, "earth": 13, "water": 21, "air": 21},
                      critical_strike=40, wisdom=25, prospecting=135)


def _novice(gd: GameData, equipment: dict[str, str] = COPPER,
            inventory: dict[str, int] | None = None, level: int = 12) -> WorldState:
    """A low-level character whose stat totals are its worn gear's."""
    return scenario_state(ScenarioCharacter(name="novice", level=level, derive_combat_stats=True,
                                            equipment=equipment, inventory=inventory or {}), gd)


def _objective(state: WorldState, gd: GameData,
               history: LearningStore | None = None) -> GearObjective:
    objective = gear_objective(state, gd, CTX, history)
    assert objective is not None
    return objective


@pytest.fixture(scope="module")
def gd() -> GameData:
    return load_bundle_game_data(BUNDLE)


@pytest.fixture(scope="module")
def robby(gd: GameData) -> GearObjective:
    return _objective(_robby(), gd)


@pytest.fixture(scope="module")
def novice(gd: GameData) -> GearObjective:
    return _objective(_novice(gd), gd)


def test_robbys_shape_names_level_40_gear_not_level_20(gd: GameData, robby: GearObjective) -> None:
    """The target is the best ACHIEVABLE gear at level 41, not a level-20 cap:
    every slot Robby fills with level-20-or-lower gear that `L*` replaces gets
    gear above level 20, and some piece needs a crafting skill above Robby's own
    (the climb is a cost, never a veto). In the committed bundle the achievable
    set tops out at level 30: the level-40 recipes need drops of monsters no
    achievable loadout beats, or of event monsters that are not up."""
    state = _robby()
    assert robby.missing
    for piece in robby.missing:
        stats = gd.item_stats(piece.code)
        assert stats is not None and stats.level <= state.level
        worn = state.equipment.get(piece.slot)
        worn_stats = gd.item_stats(worn) if worn else None
        if worn_stats is not None and worn_stats.level <= 20:
            assert stats.level > 20, piece
    assert {"helmet_slot", "leg_armor_slot"} <= {piece.slot for piece in robby.missing}
    assert any((stats := gd.item_stats(piece.code)) is not None and stats.crafting_skill
               and stats.crafting_level > state.skills.get(stats.crafting_skill, 1)
               for piece in robby.missing)


def test_an_item_worn_one_slot_over_is_held(gd: GameData, robby: GearObjective,
                                            novice: GearObjective) -> None:
    """Slots of one type are interchangeable. `L*` puts `novice_guide` in the
    second artifact slot; Robby wears it in the first: held, and the missing
    artifact goes to a slot that displaces nothing held. A level-12 character
    wearing one of its two target rings in the SECOND ring slot misses one
    ring, not two."""
    assert "novice_guide" in robby.loadout.values()
    assert all(piece.code != "novice_guide" for piece in robby.missing)
    assert all(piece.slot != "artifact1_slot" for piece in robby.missing)
    ring = novice.loadout["ring1_slot"]
    worn = {slot: code for slot, code in COPPER.items() if slot != "ring1_slot"}
    objective = _objective(_novice(gd, equipment={**worn, "ring2_slot": ring}), gd)
    assert objective.loadout["ring1_slot"] == objective.loadout["ring2_slot"] == ring
    assert [piece.slot for piece in objective.missing if piece.code == ring] == ["ring1_slot"]


def test_an_unbeatable_event_monster_changes_nothing(monkeypatch: pytest.MonkeyPatch,
                                                    robby: GearObjective) -> None:
    """Spec §5.3. `echoless_bat` stands only on its event's maps, its event is
    not live, and Robby loses to it; its wing is a material of level-legal
    gear (`mithril_platebody`). The objective is the same as in a world without
    the monster's drops at all."""
    gd = load_bundle_game_data(BUNDLE)
    state = _robby()
    assert not gd.monster_spawn_known("echoless_bat")
    assert win_probability(state, gd, "echoless_bat") == 0
    recipe = gd.crafting_recipe("mithril_platebody")
    stats = gd.item_stats("mithril_platebody")
    assert recipe is not None and "echoless_bat_wing" in recipe
    assert stats is not None and stats.level <= state.level
    dropping = gd.monsters_dropping

    def without_the_bat(item: str) -> list[tuple[str, int, int, int]]:
        return [row for row in dropping(item) if row[0] != "echoless_bat"]

    monkeypatch.setattr(gd, "monsters_dropping", without_the_bat)
    assert _objective(state, gd) == robby


LEATHER = {"weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
           "shield_slot": "wooden_shield", "ring1_slot": "iron_ring",
           "boots_slot": "leather_boots", "leg_armor_slot": "iron_legs_armor",
           "body_armor_slot": "leather_armor", "amulet_slot": "fire_and_earth_amulet"}
"""A level-10 set whose `leather_boots` the picker ranks equal to `iron_boots`
against `m*`: a pick that starts in the worn gear keeps them, one that starts
bare takes the other."""


@pytest.mark.parametrize(("worn", "level"), [(COPPER, 12), (LEATHER, 10)])
def test_the_target_ignores_what_is_worn(gd: GameData, worn: dict[str, str], level: int) -> None:
    """The same holdings, worn or carried: the same `L*` and `m*`, and over one
    achievable set the same `L*(m)` for every candidate `m`. (The achievable
    set itself is the same too: `test_the_same_holdings_worn_or_carried_give_the_same_layers`.)"""
    wearing = _novice(gd, equipment=worn, level=level)
    carried = _novice(gd, equipment={}, inventory=Counter(worn.values()), level=level)
    objectives = [_objective(state, gd) for state in (wearing, carried)]
    assert len({(o.monster, tuple(sorted(o.loadout.items()))) for o in objectives}) == 1
    achieved = frozenset().union(*achievable(wearing, gd, CTX))
    targets = [{code: loadout for code, (_, loadout) in mod._targets(state, gd, achieved).items()}
               for state in (wearing, carried)]
    assert targets[0] == targets[1]


def test_a_fixed_supply_item_with_no_free_copy_is_never_a_piece(gd: GameData) -> None:
    """Review Focus 2. `novice_guide` has no supplier; one copy exists. Worn by
    Robby it is held, so it is achievable for him; worn by a sibling it is in
    neither this character's bag nor the bank, so it is never a piece."""
    assert "novice_guide" in frozenset().union(*achievable(_robby(), gd, CTX))
    sibling = _robby({slot: code for slot, code in ROBBY_WORN.items() if code != "novice_guide"})
    assert "novice_guide" not in frozenset().union(*achievable(sibling, gd, CTX))
    objective = _objective(sibling, gd)
    assert "novice_guide" not in objective.loadout.values()
    assert all(piece.code != "novice_guide" for piece in objective.missing)


def test_one_ring_code_fills_both_slots_only_with_two_copies(gd: GameData,
                                                            novice: GearObjective) -> None:
    """Review Focus 4. A fighter owns two of a ring, one of anything else, a
    held copy counted; `L*` names one ring for both slots only because two
    copies are owned, and one copy fills one slot."""
    state = _novice(gd)
    fighter = fighter_owning(state, frozenset({"copper_ring", "iron_ring", "iron_sword"}), gd)
    assert fighter.inventory == {"copper_ring": 1, "iron_ring": 2, "iron_sword": 1}
    ring = novice.loadout["ring1_slot"]
    assert novice.loadout["ring2_slot"] == ring
    one = replace(state, inventory={**fighter.inventory, ring: 1})
    picked = fight_loadout(one, gd, novice.monster)
    assert [picked.get("ring1_slot"), picked.get("ring2_slot")].count(ring) == 1


def test_an_item_with_no_stats_is_refused(gd: GameData) -> None:
    with pytest.raises(KeyError, match="no item stats for not_an_item"):
        fighter_owning(_novice(gd), frozenset({"not_an_item"}), gd)


def test_pieces_come_in_core_order(robby: GearObjective, novice: GearObjective) -> None:
    rank = _ordered_slots()
    for objective in (robby, novice):
        keys = [piece_order_key(piece.layer, max(piece.gain, Fraction(0)), piece.price,
                                rank.index(piece.slot)) for piece in objective.missing]
        assert keys == sorted(keys)
    assert len({piece.layer for piece in novice.missing}) > 1


def test_held_when_every_slot_wears_its_target(gd: GameData, novice: GearObjective) -> None:
    """Wearing `L*` (the rest of the holdings carried) holds the objective; the
    same character in copper does not."""
    assert not novice.held
    carried = Counter(COPPER.values())
    carried.subtract(Counter(novice.loadout.values()))
    wearing = _novice(gd, equipment=novice.loadout, inventory=+carried)
    objective = _objective(wearing, gd)
    assert objective.monster == novice.monster
    assert objective.missing == ()
    assert objective.held


def test_an_owned_item_the_picker_ranks_equal_is_held(monkeypatch: pytest.MonkeyPatch,
                                                     gd: GameData) -> None:
    """Held is the picker's measure, not a code: with every item ranked equal,
    every worn slot is held, and only the empty slots are missing."""
    monkeypatch.setattr(mod, "_benefit", lambda _stats, _purpose: 0)
    objective = _objective(_novice(gd), gd)
    assert objective.missing
    assert {piece.slot for piece in objective.missing}.isdisjoint(COPPER)


def test_a_drop_opens_through_the_projected_fighter(novice: GearObjective) -> None:
    """A piece the worn copper cannot reach (its drop's monster beats copper)
    becomes achievable through the fighter owning the first layer."""
    assert any(piece.layer > 0 for piece in novice.missing)


def test_achievable_gear_is_level_legal(gd: GameData) -> None:
    state = _novice(gd)
    layers = achievable(state, gd, CTX)
    assert len(layers) > 1
    for layer in layers:
        for code in layer:
            stats = gd.item_stats(code)
            assert stats is not None and stats.level <= state.level, code


def test_m_star_is_the_max_rate_monster(gd: GameData, novice: GearObjective) -> None:
    """`R` of every candidate, each on the fighter wearing its own `L*`."""
    state = _novice(gd)
    achieved = frozenset().union(*achievable(state, gd, CTX))
    food = food_menu(state, gd, CTX)
    rates = {code: mod._rate(fighter, gd, code, food)
             for code, (fighter, _) in mod._targets(state, gd, achieved).items()}
    assert len(set(rates.values())) > 1
    assert novice.rate == rates[novice.monster] == max(rates.values())


def _record_grind(store: LearningStore, monster: str, every: int, rows: int) -> None:
    """`rows` cycles of grinding `monster`, one kill in each `every`."""
    for i in range(rows):
        action = f"Fight({monster})" if i % every == 0 else "Rest"
        store.record_cycle(Cycle(ts=f"2026-10-18T00:{i // 60:02d}:{i % 60:02d}+00:00",
                                 session_id="s", cycle_index=i, character="novice",
                                 outcome="ok", selected_goal=grind_xp_repr(monster),
                                 action_repr=action, consumables_expended_json="{}"))


def test_the_rate_is_modelled_not_measured(tmp_path: Path, gd: GameData,
                                           novice: GearObjective) -> None:
    """A measured upkeep belongs to the worn gear: `m*`'s grind on the record
    (twenty cycles a kill) does not move the projected loadout's rate."""
    store = LearningStore(db_path=str(tmp_path / "gear.db"), character="novice")
    store.start_session()
    _record_grind(store, novice.monster, every=20, rows=100)
    assert store.fight_upkeep(novice.monster) is not None
    objective = _objective(_novice(gd), gd, store)
    store.close()
    assert (objective.monster, objective.rate) == (novice.monster, novice.rate)


def test_none_when_no_monster_pays_even_on_the_achievable_fighter(gd: GameData) -> None:
    """Level 41 with nothing worn and the stats of nothing: no achievable
    loadout beats any monster that pays XP at 41."""
    state = _novice(gd, equipment={}, level=41)
    assert gear_objective(state, gd, CTX, None) is None


def test_an_equal_rate_goes_to_the_higher_monster(monkeypatch: pytest.MonkeyPatch,
                                                  gd: GameData) -> None:
    state = _novice(gd)
    monkeypatch.setattr(mod, "_rate", lambda *_args: Fraction(1))
    objective = _objective(state, gd)
    levels = [gd.monster_levels[code] for code in mod._candidates(state, gd)]
    assert len(set(levels)) > 1
    assert gd.monster_levels[objective.monster] == max(levels)


def test_an_equal_rate_and_level_goes_to_the_cheaper_pieces(monkeypatch: pytest.MonkeyPatch,
                                                           gd: GameData) -> None:
    """Two level-15 monsters at one rate: `m*` is the one whose missing pieces
    cost less in all, whichever the catalogue lists first. Every piece is
    priced 1 but one that only one monster's `L*` names, priced 2."""
    state = _novice(gd, level=15)
    tied = [code for code in mod._candidates(state, gd) if gd.monster_levels[code] == 15]
    assert len(tied) == 2
    monkeypatch.setattr(mod, "_rate", lambda *_args: Fraction(1))
    for dear, cheap in (tied, tied[::-1]):
        dear_only = set(_objective_for(monkeypatch, state, gd, [dear]).loadout.values())
        dear_only -= set(_objective_for(monkeypatch, state, gd, [cheap]).loadout.values())
        priced = dear_only.pop()

        def price(*args: object, item: str = priced) -> Fraction:
            return Fraction(2 if args[-1] == item else 1)

        monkeypatch.setattr(mod, "_price", price)
        for order in ([dear, cheap], [cheap, dear]):
            assert _objective_for(monkeypatch, state, gd, order).monster == cheap
        monkeypatch.undo()
        monkeypatch.setattr(mod, "_rate", lambda *_args: Fraction(1))


def _objective_for(monkeypatch: pytest.MonkeyPatch, state: WorldState, gd: GameData,
                   candidates: list[str]) -> GearObjective:
    monkeypatch.setattr(mod, "_candidates", lambda *_args: candidates)
    return _objective(state, gd)


def test_a_pick_that_never_settles_raises(monkeypatch: pytest.MonkeyPatch, gd: GameData) -> None:
    """A fight loadout that flips between two picks has no `L*`: the walk
    raises after its bound instead of returning a loadout no fight wears."""
    state = _novice(gd, equipment={}, inventory={"copper_dagger": 1, "iron_sword": 1})
    flips = iter(range(1_000))

    def flipping(_state: WorldState, _gd: GameData, _monster: str) -> dict[str, str]:
        return {"weapon_slot": ("copper_dagger", "iron_sword")[next(flips) % 2]}

    monkeypatch.setattr(mod, "fight_loadout", flipping)
    with pytest.raises(RuntimeError, match="has not converged in"):
        mod._target(state, gd, "chicken")
    assert next(flips) == mod.CONVERGE_PASSES


def test_potions_change_neither_the_monster_nor_the_target(gd: GameData,
                                                          novice: GearObjective) -> None:
    """Every gear decision judges bare gear: a character with health and boost
    potions worn and in the bag gets the `L*`, `m*` and `R` of one with none."""
    potions = {"utility1_slot": "small_health_potion", "utility2_slot": "air_boost_potion"}
    state = scenario_state(ScenarioCharacter(
        name="novice", level=12, derive_combat_stats=True, equipment={**COPPER, **potions},
        inventory={"small_health_potion": 50, "air_boost_potion": 50},
        utility_quantities={"utility1_slot": 50, "utility2_slot": 50}), gd)
    potioned = _objective(state, gd)
    assert (potioned.monster, potioned.loadout, potioned.rate) == (
        novice.monster, novice.loadout, novice.rate)


@pytest.mark.parametrize(("worn", "level"), [(COPPER, 12), (LEATHER, 10)])
def test_the_same_holdings_worn_or_carried_give_the_same_layers(
        gd: GameData, worn: dict[str, str], level: int) -> None:
    """Achievability never reads what is worn: the unlock fighter strips the
    worn gear and dresses from the holdings (the level-10 leather set once
    reached `forest_staff` worn and not carried)."""
    wearing = achievable(_novice(gd, equipment=worn, level=level), gd, CTX)
    carried = achievable(_novice(gd, equipment={}, inventory=Counter(worn.values()), level=level),
                         gd, CTX)
    assert wearing == carried


def test_a_static_monster_on_another_layer_is_a_candidate(gd: GameData) -> None:
    """`goblin_guard` stands only underground, in a reachable region, where the
    action factory builds its `FightAction`; the overworld index never lists
    it."""
    assert not gd.monster_locations("goblin_guard")
    assert "goblin_guard" in mod._candidates(_robby(), gd)


def test_a_fight_below_the_threshold_in_its_target_is_no_candidate(
        monkeypatch: pytest.MonkeyPatch, gd: GameData) -> None:
    """At level 13 `wolf` out-rates `flying_snake`, and in its `L*` it wins
    with P just under 1. With this character's threshold for wolf at 1 the
    fight gates refuse it, so `m*` is the slower fight they take."""
    monkeypatch.setattr(mod, "_candidates", lambda *_args: ["wolf", "flying_snake"])
    state = _novice(gd, level=13)
    assert _objective(state, gd).monster == "wolf"
    fighter, _ = mod._targets(state, gd, frozenset().union(*achievable(state, gd, CTX)))["wolf"]
    assert Fraction(0) < win_probability(fighter, gd, "wolf") < 1
    picky = replace(state, win_thresholds={"wolf": Fraction(1)})
    assert _objective(picky, gd).monster == "flying_snake"


def test_a_drop_monster_is_judged_on_its_own_target(gd: GameData) -> None:
    """§2.3: a drop is achievable when SOME achievable loadout beats its
    monster. `forest_ring` drops only from `mushmush`, which the level-12
    character's holdings beat only in mushmush's own `L*`, not undressed."""
    state = _novice(gd)
    assert [row[0] for row in gd.monsters_dropping("forest_ring")] == ["mushmush"]
    layers = achievable(state, gd, CTX)
    achieved = frozenset().union(*layers)
    assert "forest_ring" in achieved
    owned = frozenset().union(*layers[:-1])
    assert not drop_fight_winnable(mod._bare(state, owned, gd), gd, "mushmush")
    assert drop_fight_winnable(mod._fighters(state, owned, gd)("mushmush"), gd, "mushmush")


def test_a_party_only_monster_is_no_candidate(gd: GameData) -> None:
    """A boss pays Robby more per kill than any solo fight, spawns, and is in
    his level reach; the party path owns it, so it is never `m*`."""
    state = _robby()
    candidates = mod._candidates(state, gd)
    for boss in ("goblin_priestess", "rosenblood"):
        assert gd.monsters.types[boss] == "boss"
        assert gd.monster_levels[boss] <= state.level + FIGHT_LEVEL_GAP_CEILING
        assert gd.monster_spawn_known(boss)
        assert all(gd.xp_per_kill(boss, state.level) > gd.xp_per_kill(code, state.level)
                   for code in candidates)
        assert boss not in candidates


def test_a_monster_above_the_fight_ceiling_is_no_candidate(gd: GameData) -> None:
    """`wolf` (level 15, paying, spawned) is more than `FIGHT_LEVEL_GAP_CEILING`
    above a level-12 character, which `FightAction` refuses; at level 13 it is
    exactly the ceiling and a candidate."""
    assert gd.monster_levels["wolf"] == 12 + FIGHT_LEVEL_GAP_CEILING + 1
    assert gd.monster_spawn_known("wolf") and gd.xp_per_kill("wolf", 12) > 0
    assert "wolf" not in mod._candidates(_novice(gd), gd)
    assert "wolf" in mod._candidates(_novice(gd, level=13), gd)


def test_a_grey_monster_is_no_candidate(gd: GameData) -> None:
    """`chicken` pays a level-12 character no XP: no XP rate to farm."""
    assert gd.monster_spawn_known("chicken") and gd.xp_per_kill("chicken", 12) == 0
    candidates = mod._candidates(_novice(gd), gd)
    assert "chicken" not in candidates
    assert "yellow_slime" in candidates


def test_wearing_an_unowned_piece_raises(gd: GameData) -> None:
    with pytest.raises(RuntimeError, match="iron_sword is not owned to wear in weapon_slot"):
        mod._wearing(_novice(gd), {"weapon_slot": "iron_sword"}, gd)


def test_a_no_potion_loop_that_never_runs_raises(monkeypatch: pytest.MonkeyPatch,
                                                 gd: GameData) -> None:
    monkeypatch.setattr(mod, "loop_rate", lambda *_args: None)
    with pytest.raises(RuntimeError, match="the no-potion loop against chicken did not run"):
        mod._rate(_novice(gd), gd, "chicken", ())
