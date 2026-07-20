"""The action factory must emit a Fight at an ACTIVE raid's tile (epic P4b).

Raid bosses have no monster-type map tile, so `all_monster_locations` never
contains them and the normal fight loop in `factory.build_actions` never
enumerates them. That is the mechanical reason a raid was unplannable: the gates
in raid_participation decide WHETHER to engage, but nothing produced an action to
engage WITH.

Participation is the ordinary fight action at a tile whose content type is `raid`,
while the raid is active (upstream concept docs) -- so the emission is a plain
FightAction, not a new action type.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.factory import build_actions
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.raid_info import RaidInfo
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_RAID = "enchanted_fairy"
_BOSS = "pixie"
_TILE = (-4, 10)


def _raid(status: str = "active") -> RaidInfo:
    return RaidInfo(code=_RAID, name="Enchanted Fairy", monster=_BOSS, status=status,
                    next_start_at=None, remaining_hp=5000, total_hp=10000,
                    window_ends_at=None)


def _gd() -> GameData:
    """A raid boss with a RAID tile and deliberately NO monster tile -- the real
    bundle shape (14 of 58 monsters have no monster tile; two are raid bosses)."""
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource")}
    gd._monster_level = {_BOSS: 40}
    gd._monster_hp = {_BOSS: 100000}
    gd._monster_attack = {_BOSS: {"air": 30}}
    gd._monster_resistance = {_BOSS: {}}
    gd.world.raid_locations = {_RAID: [_TILE]}
    gd._bank_location = (4, 0)          # build_actions requires one
    gd._taskmaster_location = (5, 0)
    fill_monster_stat_defaults(gd)
    return gd


def _fights_for(actions, code):
    return [a for a in actions
            if isinstance(a, FightAction) and a.monster_code == code]


def _build(state, gd):
    return build_actions(gd, state, None, bank_accessible=True,
                         task_exchange_min_coins=1)


def test_active_raid_emits_a_fight_at_the_raid_tile():
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid()])
    fights = _fights_for(_build(state, _gd()), _BOSS)
    assert fights, "an active raid must produce a fight the planner can select"
    assert _TILE in fights[0].locations


def test_inactive_raid_emits_nothing():
    """The tile exists statically; only the WINDOW makes the boss fightable."""
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid(status="closed")])
    assert not _fights_for(_build(state, _gd()), _BOSS)


def test_no_raids_emits_nothing():
    state = make_state(level=48, hp=1000, max_hp=1000, attack={"air": 50})
    assert not _fights_for(_build(state, _gd()), _BOSS)


def test_raid_without_a_known_tile_emits_nothing():
    """Nothing to route to -- emitting a location-less fight would produce an
    action that can never be applicable."""
    gd = _gd()
    gd.world.raid_locations = {}
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid()])
    assert not _fights_for(_build(state, gd), _BOSS)


def test_emitted_raid_fight_is_applicable_within_the_level_cap():
    """The whole point: the emitted action must actually be selectable.

    pixie is L40, so a L48 character clears the level+2 suicide cap. An
    over-cap boss (sonnengott, L55) stays blocked by that guard -- bypassing it
    for raids needs a Lean lockstep change and is a separate follow-up."""
    gd = _gd()
    state = make_state(level=48, hp=1000, max_hp=1000,
                       attack={"air": 50}, raids=[_raid()])
    fight = _fights_for(_build(state, gd), _BOSS)[0]
    assert fight._structurally_applicable(state, gd) is True
