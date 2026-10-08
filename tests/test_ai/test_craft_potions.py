"""Tests for Task 6 (spec 2026-06-30-potion-supply): CraftPotionsGoal.

Covers target-potion selection, the baseline `is_satisfied`, the `value` deficit,
and the three-tier action ladder (craft-from-held > buy-mix > gather-5) that tops
the equipped utility-slot potion stack toward its target.

Since 2026-07-19 that target is COMBAT-JUSTIFIED: it is projected in-combat
consumption against a real winnable-but-damaging monster, capped (never floored)
by the level ramp. Fixtures therefore have to supply combat context — a monster
with a known spawn tile and a character with an attack — or the goal correctly
projects zero need and plans nothing.
"""

import dataclasses

from sqlmodel import Session as SqlSession

import artifactsmmo_cli.ai.potion_supply as potion_supply
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.craft_potions import CraftPotionsGoal
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.models import Session as SessionModel
from artifactsmmo_cli.ai.learning.store import LearningStore
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_POTION = "small_health_potion"
_INGREDIENT = "sunflower"
_INGREDIENT2 = "herb"
_RESOURCE = "sunflower_field"
_HURTS = "biting_slime"   # winnable-but-damaging: makes potion stocking justified


def _gd_potion(*, hp_restore: int = 30, craft_level: int = 1) -> GameData:
    """GameData where `small_health_potion` is the one alchemy-craftable,
    utility-slot-equippable heal (its ingredient `sunflower` drops from
    `sunflower_field`)."""
    gd = GameData()
    gd._item_stats = {
        _POTION: ItemStats(code=_POTION, level=1, type_="utility", hp_restore=hp_restore,
                           crafting_skill="alchemy", crafting_level=craft_level),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1}}
    gd._resource_drops = {_RESOURCE: _INGREDIENT}
    gd._resource_locations = {_RESOURCE: [(2, 0)]}
    gd._workshop_locations = {"alchemy": (3, 0)}
    # Combat pressure. Potion stocking is combat-justified (2026-07-19): the target
    # is projected IN-COMBAT consumption, so a catalog with no hurting monster
    # projects zero need and the goal correctly plans nothing. This monster is
    # given a static tile so it also survives the combat_targets spawn gate.
    gd._monster_level = {_HURTS: 3}
    gd._monster_hp = {_HURTS: 60}
    gd._monster_attack = {_HURTS: {"fire": 40}}
    gd._monster_resistance = {_HURTS: {}}
    gd._monster_locations = {_HURTS: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def _gd_no_alchemy_heal() -> GameData:
    """GameData with NO alchemy utility heal — only a cooking food (the wrong
    type/skill for a utility slot), so `_target_potion` is None."""
    gd = GameData()
    gd._item_stats = {
        "cooked_fish": ItemStats(code="cooked_fish", level=1, type_="consumable",
                                 hp_restore=50, crafting_skill="cooking", crafting_level=1),
    }
    gd._crafting_recipes = {"cooked_fish": {"raw_fish": 1}}
    return gd


def _craft_action() -> CraftAction:
    return CraftAction(code=_POTION, quantity=1, workshop_location=(3, 0))


# ── target-potion selection ──────────────────────────────────────────────────

def test_target_potion_picks_alchemy_utility_heal():
    gd = _gd_potion()
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == _POTION


def test_target_potion_none_without_craftable_utility_heal():
    gd = _gd_no_alchemy_heal()
    assert CraftPotionsGoal()._target_potion(make_state(), gd) is None


def test_target_potion_none_when_skill_gate_unmet():
    gd = _gd_potion(craft_level=10)
    state = make_state(skills={"alchemy": 1})
    assert CraftPotionsGoal()._target_potion(state, gd) is None


def test_target_potion_picks_higher_restore_regardless_of_craft_skill():
    """Any utility-slot heal counts, not just alchemy-crafted ones — the skill
    that makes it is not a game fact the selector may assume. A cooking-crafted
    utility heal with higher hp_restore (99) must win over the alchemy potion
    (30) when its own skill gate is met."""
    gd = _gd_potion()
    gd._item_stats["cook_potion"] = ItemStats(code="cook_potion", level=1, type_="utility",
                                              hp_restore=99, crafting_skill="cooking", crafting_level=1)
    gd._crafting_recipes["cook_potion"] = {_INGREDIENT: 1}
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == "cook_potion"


def test_target_potion_skips_utility_heal_when_its_own_skill_gate_unmet():
    """The skill gate reads the item's OWN crafting skill/level (API data), not a
    hardcoded 'alchemy'. A higher-restore utility heal crafted by a skill the
    character hasn't leveled is correctly skipped in favour of the craftable one."""
    gd = _gd_potion()
    gd._item_stats["cook_potion"] = ItemStats(code="cook_potion", level=1, type_="utility",
                                              hp_restore=99, crafting_skill="cooking", crafting_level=10)
    gd._crafting_recipes["cook_potion"] = {_INGREDIENT: 1}
    state = make_state(skills={"cooking": 1, "alchemy": 1})
    assert CraftPotionsGoal()._target_potion(state, gd) == _POTION


def test_target_potion_skips_utility_heal_without_a_crafting_skill():
    """A utility heal whose stats carry no crafting_skill (None) can't be skill-
    gated, so it is skipped in favour of a properly-skilled potion — never
    crashing on a None skill lookup."""
    gd = _gd_potion()
    gd._item_stats["skilless_potion"] = ItemStats(code="skilless_potion", level=1,
                                                  type_="utility", hp_restore=99,
                                                  crafting_skill=None, crafting_level=1)
    gd._crafting_recipes["skilless_potion"] = {_INGREDIENT: 1}
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == _POTION


def test_target_potion_highest_restore_then_smallest_code():
    gd = _gd_potion()
    gd._item_stats["aaa_potion"] = ItemStats(code="aaa_potion", level=1, type_="utility",
                                             hp_restore=30, crafting_skill="alchemy", crafting_level=1)
    gd._item_stats["big_potion"] = ItemStats(code="big_potion", level=1, type_="utility",
                                             hp_restore=80, crafting_skill="alchemy", crafting_level=1)
    gd._crafting_recipes["aaa_potion"] = {_INGREDIENT: 1}
    gd._crafting_recipes["big_potion"] = {_INGREDIENT: 1}
    # big_potion (80) beats the two 30s; among equal restore the lexically first wins.
    assert CraftPotionsGoal()._target_potion(make_state(), gd) == "big_potion"


# ── is_satisfied (state-only baseline check) ─────────────────────────────────

def test_satisfied_when_slot_meets_baseline():
    # A utility slot stocked to this level's combat-projected target (capped by
    # the level ramp at 5 for level 1) leaves nothing to craft.
    gd = _gd_potion()
    state = make_state(level=1, attack={"fire": 20}, equipment={"utility1_slot": _POTION})
    state = dataclasses.replace(state, utility1_slot_quantity=5)
    assert CraftPotionsGoal(game_data=gd, combat_monster=_HURTS).is_satisfied(state) is True


def test_unsatisfied_when_understocked():
    gd = _gd_potion()
    state = make_state(level=1, attack={"fire": 20})
    assert CraftPotionsGoal(game_data=gd, combat_monster=_HURTS).is_satisfied(state) is False


# ── value ────────────────────────────────────────────────────────────────────

def test_value_is_baseline_deficit_when_understocked():
    gd = _gd_potion()
    # _HURTS projects real in-combat consumption; the ramp caps it at 5 for
    # level 1, and nothing is equipped -> deficit 5.
    state = make_state(level=1, attack={"fire": 20})
    assert CraftPotionsGoal(combat_monster=_HURTS).value(state, gd) == 5.0
    # No fight ahead: nothing to stock for (2026-10-06).
    assert CraftPotionsGoal().value(state, gd) == 0.0


def test_value_zero_when_satisfied():
    gd = _gd_potion()
    state = make_state(level=1, attack={"fire": 20}, equipment={"utility1_slot": _POTION})
    state = dataclasses.replace(state, utility1_slot_quantity=5)
    assert CraftPotionsGoal().value(state, gd) == 0.0


def test_preemptive_flag():
    assert CraftPotionsGoal.preemptive is True


def test_desired_state_empty():
    gd = _gd_potion()
    assert CraftPotionsGoal().desired_state(make_state(), gd) == {}


def test_repr():
    assert repr(CraftPotionsGoal()) == "CraftPotionsGoal"


# ── _baseline monster-demand scaling ─────────────────────────────────────────

def _mk_store_with_fights(tmp_path, monster: str, consumables_json: str,
                          n: int = 5) -> LearningStore:
    """LearningStore with `n` won Fight(monster) cycles each expending consumables_json."""
    store = LearningStore(db_path=str(tmp_path / "test.db"), character="testchar")
    store.start_session()
    with SqlSession(store._engine) as s:
        if not s.get(SessionModel, store._session_id):
            s.add(SessionModel(session_id=store._session_id,
                               started_at="2026-05-18T00:00:00Z", character="testchar"))
        for i in range(n):
            s.add(Cycle(
                ts=f"2026-05-18T00:{i:02d}:00Z",
                session_id=store._session_id,
                cycle_index=i,
                character="testchar",
                action_repr=f"Fight({monster})",
                outcome="ok",
                consumables_expended_json=consumables_json,
            ))
        s.commit()
    return store


def _marginal(monkeypatch, state) -> None:  # type: ignore[no-untyped-def]
    """The boss's expected damage is the character's whole max HP: a marginal
    fight, the only kind learned consumption may size (2026-10-08)."""
    monkeypatch.setattr(potion_supply, "expected_damage_per_fight", lambda s, g, m: state.max_hp)


def test_a_comfortable_fight_needs_no_stock_whatever_was_drunk(tmp_path, monkeypatch):
    """Live 2026-10-08: C3P0 drank potions in 19 of 36 cow fights it won
    comfortably; a potion in the slot is drunk whenever HP dips, so drinking is
    not need. A comfortable fight's learned drinking stocks nothing."""
    gd = _gd_potion(hp_restore=30)
    state = make_state(level=45)
    monkeypatch.setattr(potion_supply, "expected_damage_per_fight", lambda s, g, m: 1)
    store = _mk_store_with_fights(tmp_path, "cow", '{"small_health_potion": 3}')
    goal = CraftPotionsGoal(combat_monster="cow", game_data=gd, history=store)
    result = goal._baseline(state.level, state, gd, store)
    store.close()
    assert result == 0


def test_a_marginal_fight_without_history_is_sized_by_its_damage(monkeypatch):
    gd = _gd_potion(hp_restore=30)
    state = make_state(level=45)
    _marginal(monkeypatch, state)
    assert potion_supply.projected_heal_need_per_fight(state, gd, "hard_boss", None) == state.max_hp


def test_baseline_follows_learned_combat_demand(tmp_path, monkeypatch):
    """Learned in-combat consumption DRIVES the target; the level ramp only caps it.

    level=45 → level_baseline=100 (the cap). 5 fight rows each expend 1 potion ×
    30 HP, so hp_healed_per_fight returns 30.0. Projected over the
    POTION_LEAD_FIGHTS=10 fight lead-time window that is 300 HP, i.e.
    ceil(300/30) = 10 potions — well under the cap, so the learned demand is what
    comes out.
    """
    _MONSTER = "hard_boss"
    gd = _gd_potion(hp_restore=30)
    state = make_state(level=45)
    _marginal(monkeypatch, state)
    store = _mk_store_with_fights(tmp_path, _MONSTER, '{"small_health_potion": 1}')
    goal = CraftPotionsGoal(combat_monster=_MONSTER, game_data=gd, history=store)
    result = goal._baseline(state.level, state, gd, store)
    store.close()
    assert result == 10


def test_baseline_capped_by_level_ramp(tmp_path, monkeypatch):
    """The level ramp is a CAP on speculation, never a floor.

    level=1 → level_baseline=5. 5 fight rows each expend 10 potions × 30 HP, so
    hp_healed_per_fight returns 300.0 and the 10-fight projection wants
    ceil(3000/30) = 100 potions. The ramp clamps that to 5 — a level-1 character
    is not sent gather-crafting a hundred potions on the strength of a projection.
    """
    _MONSTER = "hard_boss"
    gd = _gd_potion(hp_restore=30)
    state = make_state(level=1)
    _marginal(monkeypatch, state)
    store = _mk_store_with_fights(tmp_path, _MONSTER, '{"small_health_potion": 10}')
    goal = CraftPotionsGoal(combat_monster=_MONSTER, game_data=gd, history=store)
    result = goal._baseline(state.level, state, gd, store)
    store.close()
    assert result == 5


def test_baseline_zero_when_no_target_monster():
    """NEW CONTRACT (combat-justified stocking): no combat target → target 0.

    The goal was built for no fight (`ctx.fight_monster` is None). There is no
    fight to be consumed in, so
    there is nothing to stock for — the level ramp does NOT apply as a floor.
    Previously this returned the bare level_baseline (5) regardless of combat.
    """
    gd = _gd_potion()
    state = make_state(level=1)  # no attack → no winnable monster
    goal = CraftPotionsGoal()  # no injected combat_monster either
    assert goal._baseline(state.level, state, gd) == 0


def test_baseline_zero_when_no_target_potion():
    """combat_monster set but game_data has no craftable utility heal →
    _target_potion returns None → target 0.

    NEW CONTRACT: the fallback is 0, not the level ramp — a potion that cannot be
    made is not a thing to stock toward.
    """
    gd = _gd_no_alchemy_heal()
    state = make_state(level=1)
    goal = CraftPotionsGoal(combat_monster="some_boss")
    assert goal._baseline(state.level, state, gd) == 0


def test_baseline_zero_when_potion_restore_zero():
    """A utility item selected by effect='wisdom' has hp_restore=0, so no amount
    of it covers the projected in-combat HP need → target 0.

    NEW CONTRACT: the fallback is 0, not the level ramp. Non-vacuous: the monster
    is a real, winnable, damaging one (so hp_need > 0) and the item passes the
    skill gate — only its zero hp_restore makes it useless as stock.
    """
    gd = GameData()
    gd._item_stats = {
        "wisdom_token": ItemStats(code="wisdom_token", level=1, type_="utility",
                                  wisdom=5, hp_restore=0,
                                  crafting_skill="alchemy", crafting_level=1),
    }
    gd._crafting_recipes = {"wisdom_token": {_INGREDIENT: 1}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._monster_level = {_HURTS: 3}
    gd._monster_hp = {_HURTS: 60}
    gd._monster_attack = {_HURTS: {"fire": 40}}
    gd._monster_resistance = {_HURTS: {}}
    gd._monster_locations = {_HURTS: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    state = make_state(level=1, attack={"fire": 20})  # alchemy=1 passes skill gate
    goal = CraftPotionsGoal(combat_monster=_HURTS, effect="wisdom")
    assert goal._baseline(state.level, state, gd) == 0


def test_baseline_zero_when_hp_need_zero():
    """Monster code not in game_data.monster_levels → expected_damage_per_fight
    returns 0 → hp_need == 0 → target 0.

    NEW CONTRACT: the fallback is 0, not the level ramp — a fight that costs no
    HP needs no potions.
    """
    gd = _gd_potion()  # small_health_potion with hp_restore=30
    state = make_state(level=1)
    # "unknown_monster" absent from monster_levels → expected_damage_per_fight → 0
    goal = CraftPotionsGoal(combat_monster="unknown_monster")
    assert goal._baseline(state.level, state, gd) == 0


# ── heal-then-boost in _active_craft (Task 4) ────────────────────────────────

_BOOST_CODE = "fire_boost"
_MONSTER_CODE = "slime"


def _gd_heal_and_boost() -> GameData:
    """GameData with a heal (small_health_potion) and a beneficial boost (fire_boost).

    Monster slime (level=5, hp=1000, attack={"fire": 5}): winnable by a character
    with attack={"fire": 50} (predict_win True, margin=1). With fire_boost equipped
    (dmg_elements={"fire": 10}) raw_player=55, rounds_to_kill drops 20→19, margin
    rises to 2 → gain=1 > 0 → best_boost_potion returns fire_boost.
    """
    gd = GameData()
    gd._item_stats = {
        _POTION: ItemStats(code=_POTION, level=1, type_="utility", hp_restore=30,
                           crafting_skill="alchemy", crafting_level=1),
        _BOOST_CODE: ItemStats(code=_BOOST_CODE, level=1, type_="utility",
                               dmg_elements={"fire": 10},
                               crafting_skill="alchemy", crafting_level=1),
        _INGREDIENT: ItemStats(code=_INGREDIENT, level=1, type_="resource"),
    }
    gd._crafting_recipes = {_POTION: {_INGREDIENT: 1}, _BOOST_CODE: {_INGREDIENT: 3}}
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {"alchemy": (3, 0)}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._monster_level = {_MONSTER_CODE: 5}
    gd._monster_hp = {_MONSTER_CODE: 1000}
    gd._monster_attack = {_MONSTER_CODE: {"fire": 5}}
    gd._monster_resistance = {_MONSTER_CODE: {}}
    # Static tile: combat_target_monsters only sees monsters with a known spawn,
    # and both the boost selector and the combat-justified heal target route
    # through it — without a location the goal projects no combat at all.
    gd._monster_locations = {_MONSTER_CODE: [(1, 0)]}
    fill_monster_stat_defaults(gd)
    return gd


def test_goal_crafts_boost_after_heal_satisfied():
    """_active_craft returns the boost code when heals are stocked and a beneficial
    boost is understocked.

    level=5 → baseline=5; utility1_slot has small_health_potion at qty=5 (stocked,
    deficit=0). combat_monster="slime" → best_boost_potion returns fire_boost
    (gain=1 > 0). boost_equipped=0 < boost_baseline=5 → boost path fires.
    Non-vacuous: both the heal and the boost exist and are craftable; only the
    heal deficit distinguishes this from the heal path test.
    """
    gd = _gd_heal_and_boost()
    state = make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 10},
        equipment={**make_state().equipment, "utility1_slot": _POTION},
        utility1_slot_quantity=5,
        inventory={_INGREDIENT: 3},
    )
    goal = CraftPotionsGoal(combat_monster=_MONSTER_CODE, game_data=gd)
    result = goal._active_craft(state, gd)
    assert result is not None, "_active_craft must return a boost plan when heals are stocked"
    code, _runs, _qty = result
    assert code == _BOOST_CODE


def test_goal_prioritizes_heal_over_boost():
    """_active_craft returns the heal code when heals are under-baseline, even when
    a beneficial boost also exists.

    level=5 → baseline=5; utility1_slot is empty (qty=0, deficit=5 > 0). Both the
    heal and boost are in game_data and the boost is beneficial, but the heal deficit
    takes precedence → _active_craft targets small_health_potion.
    Non-vacuous: the boost exists and is craftable (alchemy gate met); only the
    heal-equipped count differs from test_goal_crafts_boost_after_heal_satisfied.
    """
    gd = _gd_heal_and_boost()
    state = make_state(
        level=5,
        hp=100, max_hp=100,
        attack={"fire": 50},
        skills={**make_state().skills, "alchemy": 10},
        equipment={**make_state().equipment, "utility1_slot": None},
        utility1_slot_quantity=0,
        inventory={_INGREDIENT: 10},
    )
    goal = CraftPotionsGoal(combat_monster=_MONSTER_CODE, game_data=gd)
    result = goal._active_craft(state, gd)
    assert result is not None, "_active_craft must return a heal plan when heals are understocked"
    code, _runs, _qty = result
    assert code == _POTION


# ─── uncovered defensive branches (added 2026-07-20) ─────────────────────────
# Found by the 100% coverage gate after the merge, not by the fast --no-cov loop
# I had switched to. Each is a real path the goal can be constructed into.

def test_baseline_zero_without_game_data_or_state():
    """`_baseline` is called with optional context; without it there is no
    monster and no target, so there is nothing to size a stock against."""
    goal = CraftPotionsGoal(combat_monster=_HURTS)
    assert goal._baseline(10, None, None, None) == 0
    assert goal._baseline(10, make_state(level=10), None, None) == 0


def test_is_satisfied_without_game_data_reads_satisfied():
    """The state-only arm, and it is DEGENERATE by construction.

    `Goal.is_satisfied(state)` has no GameData, so a goal built without one
    compares utility-slot quantities against `_baseline(...)` -- which itself
    returns 0 when game_data is None. `qty >= 0` always holds, so the goal reads
    satisfied whatever the stock.

    That is the right outcome (no catalog means no target means nothing to do)
    but it is easy to misread as a stocking check, so it is pinned rather than
    left implicit. The REAL gating lives in `craft_potions_fires`, which does
    have GameData; the guard not firing is what makes this arm unreachable in
    production."""
    goal = CraftPotionsGoal()          # no game_data injected
    assert goal.is_satisfied(make_state(level=3, utility1_slot_quantity=99)) is True
    assert goal.is_satisfied(
        make_state(level=3, utility1_slot_quantity=0, utility2_slot_quantity=0)) is True
