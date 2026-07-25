"""ReachCurrencyGoal search-branching regression.

The in-model accepted task is the `__pending__` placeholder AcceptTaskAction.apply
installs, and it is monsters-typed with task_total=1 — so ANY admitted FightAction
progresses it. Admitting every fight in the catalog therefore hands A* a set of
interchangeable actions that differ only in cost, and with h=0 the search
enumerates which monster to kill on each funding cycle.

Live (Robby, level 20, 44 fights in the catalog): the goal timed out on the 10s
cheap pass at ~10.5K nodes and returned no plan, which blocks the satchel chain
(jasper_crystal is sold only by tasks_trader for tasks_coin). Restricted to the
monsters the bot's own combat-target selector will actually fight, the same
funding plan is found in 55 nodes instead of 5444.

This mirrors the reduction the goal's docstring already documents for crafts
("keeping the ~320 crafts only flooded the h=0 search ... milliseconds without").
"""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.combat_targets import combat_target_monsters
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.reach_currency import ReachCurrencyGoal
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_IN_BAND = "wolf"
_OUT_OF_BAND = [f"trash_mob_{i}" for i in range(12)]


def _gd() -> GameData:
    """One in-band beatable monster plus a dozen far-below-band ones. Only the
    in-band monster is a real farm target; the rest are pure search fan-out."""
    gd = GameData()
    gd._item_stats = {
        "wpn": ItemStats(code="wpn", level=1, type_="weapon", attack={"fire": 150}),
    }
    gd._crafting_recipes = {}
    gd._monster_level = {_IN_BAND: 18, **{m: 1 for m in _OUT_OF_BAND}}
    gd._monster_hp = {_IN_BAND: 200, **{m: 20 for m in _OUT_OF_BAND}}
    gd._monster_attack = {_IN_BAND: {"fire": 40}, **{m: {"fire": 5} for m in _OUT_OF_BAND}}
    gd._monster_resistance = {m: {} for m in [_IN_BAND, *_OUT_OF_BAND]}
    gd._monster_locations = {_IN_BAND: [(1, 0)],
                             **{m: [(2 + i, 0)] for i, m in enumerate(_OUT_OF_BAND)}}
    fill_monster_stat_defaults(gd)
    gd._resource_drops = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    return gd


def _state(**overrides):
    base = dict(
        level=20, hp=480, max_hp=480,
        attack={"fire": 150},
        equipment={**make_state().equipment, "weapon_slot": "wpn"},
        inventory={},
        inventory_max=138, inventory_slots_max=138,
    )
    base.update(overrides)
    return make_state(**base)


def _actions(gd: GameData) -> list:
    out: list = [AcceptTaskAction(taskmaster_location=(0, 0)),
                 CompleteTaskAction(taskmaster_location=(0, 0))]
    for monster in gd.monster_levels:
        out.append(FightAction(monster_code=monster,
                               locations=frozenset(gd._monster_locations[monster])))
    return out


def test_relevant_actions_admits_only_real_combat_targets():
    """Fights are restricted to what combat_target_monsters selects, not the
    whole catalog — the rest are interchangeable for a `__pending__` task and
    only fan the search out."""
    gd = _gd()
    state = _state()
    goal = ReachCurrencyGoal(currency="tasks_coin", target=8)

    rel = goal.relevant_actions(_actions(gd), state, gd)

    admitted = {a.monster_code for a in rel if isinstance(a, FightAction)}
    assert admitted == set(combat_target_monsters(state, gd))
    assert _IN_BAND in admitted, "the real farm target must survive"
    assert not admitted & set(_OUT_OF_BAND), "out-of-band fan-out must be dropped"


def test_accept_and_complete_survive_the_narrowing():
    """The funding loop's own two actions must not be filtered out."""
    gd = _gd()
    state = _state()
    goal = ReachCurrencyGoal(currency="tasks_coin", target=8)

    rel = goal.relevant_actions(_actions(gd), state, gd)

    assert any(isinstance(a, AcceptTaskAction) for a in rel)
    assert any(isinstance(a, CompleteTaskAction) for a in rel)


def test_all_fights_kept_when_no_combat_target_is_selectable():
    """Soundness guard: when the selector names nothing (e.g. the character
    cannot currently beat anything in band), narrowing to the empty set would
    make the goal spuriously unplannable. Fall back to the full fight set and
    let the planner decide."""
    gd = _gd()
    # Too weak to beat anything: combat_target_monsters goes empty.
    state = _state(attack={"fire": 0}, equipment=make_state().equipment)
    assert combat_target_monsters(state, gd) == []

    rel = ReachCurrencyGoal(currency="tasks_coin", target=8).relevant_actions(
        _actions(gd), state, gd)

    admitted = {a.monster_code for a in rel if isinstance(a, FightAction)}
    assert admitted == set(gd.monster_levels), "must not narrow to nothing"
