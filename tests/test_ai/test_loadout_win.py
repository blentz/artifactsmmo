"""The drop route's WINNABLE gate wears a utility-potion loadout (USER
2026-10-10, "judge drop fights with the chosen loadout";
docs/PLAN_drop_fight_loadout.md)."""

from unittest.mock import patch

import artifactsmmo_cli.ai.loadout_win as win_mod
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.loadout_win import stockable_potions, winning_loadout, wins_with_a_loadout
from artifactsmmo_cli.ai.obtain_model.drop_routes import drop_routes
from artifactsmmo_cli.ai.obtain_model.gate import GateKind
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_UTILITY = dict(level=1, type_="utility")


def _gd() -> GameData:
    """One ogre (100 HP, 30 fire a round) dropping ogre_eye. The player (20
    fire, 100 HP) kills it in 5 rounds and dies in 4 without help; a 40-HP
    heal potion carries it through."""
    gd = GameData()
    gd._monster_level = {"ogre": 5}
    gd._monster_hp = {"ogre": 100}
    gd._monster_attack = {"ogre": {"fire": 30}}
    gd._monster_resistance = {"ogre": {}}
    gd._monster_locations = {"ogre": (1, 0)}
    gd._monster_drops = {"ogre": [("ogre_eye", 1, 1, 1)]}
    fill_monster_stat_defaults(gd)
    gd._consumable_effect_codes = {
        "heal_potion": ["restore"], "brewed_potion": ["restore"], "sold_potion": ["restore"],
        "event_potion": ["restore"], "ghost_potion": ["restore"],
        "splash_potion": ["splash_restore"],
        "high_potion": ["restore"]}
    gd._item_stats = {
        "heal_potion": ItemStats(code="heal_potion", hp_restore=40, **_UTILITY),
        "brewed_potion": ItemStats(code="brewed_potion", hp_restore=40, crafting_skill="alchemy",
                                   crafting_level=5, **_UTILITY),
        "sold_potion": ItemStats(code="sold_potion", hp_restore=40, **_UTILITY),
        "event_potion": ItemStats(code="event_potion", hp_restore=40, **_UTILITY),
        "ghost_potion": ItemStats(code="ghost_potion", hp_restore=40, **_UTILITY),
        "splash_potion": ItemStats(code="splash_potion", hp_restore=150, **_UTILITY),
        "high_potion": ItemStats(code="high_potion", level=9, type_="utility", hp_restore=900),
        "ogre_eye": ItemStats(code="ogre_eye", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"brewed_potion": {"herb": 1}}
    # the fair's tile is known (an event vendor), the ghost's is not
    gd._npc_stock = {"grocer": {"sold_potion": 5}, "fair": {"event_potion": 5},
                     "ghost": {"ghost_potion": 5}}
    gd._npc_locations = {"grocer": (2, 2), "fair": (3, 3)}
    gd.world.npc_event_codes = {"fair": "fair_event"}
    return gd


def _state(**kw: object) -> WorldState:
    base: dict[str, object] = dict(level=5, hp=100, max_hp=100, attack={"fire": 20},
                                   initiative=1)
    base.update(kw)
    return make_state(**base)


def test_stockable_potions_are_held_brewable_or_sold_for_gold() -> None:
    gd = _gd()
    # nothing held, alchemy 1: only the located gold vendor's potion
    assert stockable_potions(_state(), gd) == ["sold_potion"]
    # held (bag), brewable at alchemy 5; never the event vendor's, the splash,
    # or a potion above the level, even held
    state = _state(inventory={"heal_potion": 1, "splash_potion": 3, "high_potion": 2},
                   skills={"alchemy": 5})
    assert stockable_potions(state, gd) == ["heal_potion", "brewed_potion", "sold_potion"]


def test_a_potion_wins_what_the_bare_stats_lose() -> None:
    gd = _gd()
    gd._npc_stock = {}
    assert not wins_with_a_loadout(_state(), gd, "ogre")
    assert wins_with_a_loadout(_state(bank_items={"heal_potion": 1}), gd, "ogre")


def test_the_verdict_is_memoized_on_what_the_walk_reads() -> None:
    gd = _gd()
    state = _state()
    with patch.object(win_mod, "fight_walk", wraps=win_mod.fight_walk) as walk:
        assert wins_with_a_loadout(state, gd, "ogre")
        calls = walk.call_count
        assert wins_with_a_loadout(_state(inventory={"ogre_eye": 3}), gd, "ogre")
        assert walk.call_count == calls  # a non-equippable bag change: a hit
        wins_with_a_loadout(_state(max_hp=120), gd, "ogre")
        assert walk.call_count > calls   # a fight field: a miss


def test_the_drop_route_is_winnable_with_a_loadout() -> None:
    gd = _gd()
    gd._npc_stock = {}

    def winnable(state: WorldState) -> bool:
        (route,) = drop_routes("ogre_eye", state, gd)
        return next(g.satisfied for g in route.gates if g.kind is GateKind.WINNABLE)

    assert not winnable(_state())
    assert winnable(_state(inventory={"heal_potion": 2}))


def test_the_winning_loadout_is_named() -> None:
    gd = _gd()
    gd._npc_stock = {}
    assert winning_loadout(_state(), gd, "ogre") is None
    assert winning_loadout(_state(bank_items={"heal_potion": 1}), gd, "ogre") == ("heal_potion",)
