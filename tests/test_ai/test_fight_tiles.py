"""The tiles a monster is fought on are exactly the action factory's FightAction
tiles, on every layer (fight-odds final review C1: `rat` spawns only on
`interior`, `bat` and `lich` only `underground`, and the legacy
`monster_locations` index alone said they spawn nowhere)."""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.fight_tiles import by_region, fight_tiles, layered_extra
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.raid_info import RaidInfo
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state


def _raid(code: str, monster: str) -> RaidInfo:
    return RaidInfo(code=code, name=code, monster=monster, status="active", next_start_at=None,
                    remaining_hp=5000, total_hp=10000, window_ends_at=None)


def _gd() -> GameData:
    """crab: a mainland tile and an island tile (a second overworld-layer
    region); rat: one interior tile only; lich: two underground tiles; pixie: a
    raid boss with a raid tile only; chicken: an overworld layered tile only."""
    gd = GameData()
    gd.world.walkable_tiles = {(0, 0, "overworld"), (1, 0, "overworld"),
                               (5, 5, "overworld"), (5, 6, "overworld")}
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (1, 0)
    gd._monster_level = {"crab": 5, "rat": 1, "lich": 30, "pixie": 40, "chicken": 1}
    gd._monster_hp = {code: 100 for code in gd._monster_level}
    gd._monster_attack = {code: {"fire": 10} for code in gd._monster_level}
    gd._monster_resistance = {code: {} for code in gd._monster_level}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"crab": [(1, 0), (5, 5)]}
    gd.world.raid_locations = {"fairy_raid": [(-4, 10)]}
    gd.world.layered_content = {
        # (5, 6) is on the island the legacy index fights on, but not one of
        # its tiles: the factory does not fight there
        "crab": [(5, 5, "overworld"), (5, 6, "overworld"), (2, 2, "interior")],
        "rat": [(-3, 12, "interior")],
        "lich": [(9, 8, "underground"), (9, 9, "underground")],
        "chicken": [(0, 1, "overworld")],
    }
    return gd


def _state() -> WorldState:
    return make_state(raids=[_raid("fairy_raid", "pixie")])


def test_every_source_on_every_layer() -> None:
    gd = _gd()
    state = _state()
    assert fight_tiles(state, gd, "crab") == [(1, 0), (5, 5), (2, 2)]
    assert fight_tiles(state, gd, "rat") == [(-3, 12)]
    assert fight_tiles(state, gd, "lich") == [(9, 8), (9, 9)]
    assert fight_tiles(state, gd, "pixie") == [(-4, 10)]


def test_no_tile_on_any_layer_is_no_tile() -> None:
    gd = _gd()
    assert fight_tiles(_state(), gd, "chicken") == []  # overworld layered: the legacy index's
    assert fight_tiles(_state(), gd, "ghost") == []
    assert fight_tiles(make_state(), gd, "pixie") == []  # the raid is not active


def test_a_raid_fights_only_its_own_boss() -> None:
    gd = _gd()
    state = make_state(raids=[_raid("fairy_raid", "crab")])
    assert fight_tiles(state, gd, "crab") == [(1, 0), (5, 5), (-4, 10), (2, 2)]
    assert fight_tiles(state, gd, "pixie") == []


def test_a_tile_is_listed_once() -> None:
    gd = _gd()
    gd.world.raid_locations = {"fairy_raid": [(1, 0)]}
    state = make_state(raids=[_raid("fairy_raid", "crab")])
    assert fight_tiles(state, gd, "crab") == [(1, 0), (5, 5), (2, 2)]


def test_the_layered_tiles_skip_the_overworld_and_the_named_regions() -> None:
    gd = _gd()
    assert layered_extra(gd, "crab", set()) == {"overworld:5,5": [(5, 5), (5, 6)],
                                                "interior": [(2, 2)]}
    assert layered_extra(gd, "crab", {"overworld:5,5"}) == {"interior": [(2, 2)]}
    assert layered_extra(gd, "chicken", set()) == {}
    assert by_region([(1, 0), (5, 5), (0, 0)], gd) == {"overworld": [(1, 0), (0, 0)],
                                                       "overworld:5,5": [(5, 5)]}


def test_the_tiles_are_the_factorys_fight_tiles() -> None:
    """Parity: for every monster, the union of the factory's FightAction tiles."""
    gd = _gd()
    state = _state()
    actions = build_actions(gd, state, None, bank_accessible=True, task_exchange_min_coins=1,
                            learned_drops=LearnedDrops.empty())
    for monster in ("crab", "rat", "lich", "pixie", "chicken", "ghost"):
        built = {tile for a in actions if isinstance(a, FightAction) and a.monster_code == monster
                 for tile in a.locations}
        assert set(fight_tiles(state, gd, monster)) == built, monster
