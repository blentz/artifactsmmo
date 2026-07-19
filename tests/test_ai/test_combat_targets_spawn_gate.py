"""combat_target_monsters must only return monsters the planner can actually reach.

`monster_levels` is the FULL catalog. Without a spawn gate this helper returned
event-only monsters whose event is not running and raid bosses that have no
monster-type map tile at all -- 14 of the 58 monsters in the committed bundle have
no static tile, including the raid bosses `pixie` and `sonnengott`.

That is not cosmetic: `potion_supply.primary_combat_target` delegates here, so
combat-justified potion stocking could size itself against a raid boss the bot can
never fight. `inventory_caps` consumes it too.

The gate keys on REACHABILITY (does it spawn somewhere right now), NOT on being
event content -- event monsters are legitimately fightable while their event runs,
and filtering them out would undo the event-visibility work.
"""

from artifactsmmo_cli.ai.combat_targets import _clear_cache, combat_target_monsters
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_PERMANENT = "chicken"
_EVENT_ONLY = "corrupted_ogre"
_RAID_BOSS = "pixie"


def _gd() -> GameData:
    """Three monsters, all trivially winnable and in band, differing ONLY in where
    they spawn: one permanent tile, one event-only tile, one no tile at all."""
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource")}
    gd._monster_level = {_PERMANENT: 1, _EVENT_ONLY: 1, _RAID_BOSS: 1}
    gd._monster_hp = {_PERMANENT: 1, _EVENT_ONLY: 1, _RAID_BOSS: 1}
    gd._monster_attack = {_PERMANENT: {}, _EVENT_ONLY: {}, _RAID_BOSS: {}}
    gd._monster_resistance = {_PERMANENT: {}, _EVENT_ONLY: {}, _RAID_BOSS: {}}
    # Only the permanent monster gets a static tile.
    gd._monster_locations = {_PERMANENT: [(1, 0)]}
    # The event monster has an event-tile entry, inert until its event is active.
    gd.world.event_monster_locations = {_EVENT_ONLY: [(2, 0)]}
    gd.world.event_code_of_content = {_EVENT_ONLY: _EVENT_ONLY}
    fill_monster_stat_defaults(gd)
    return gd


def _state():
    return make_state(level=5, hp=100, max_hp=150, attack={"fire": 50})


def test_unreachable_monsters_are_excluded():
    """The raid boss has no tile on any layer, so it is not a combat target."""
    _clear_cache()
    out = combat_target_monsters(_state(), _gd())
    assert _PERMANENT in out
    assert _RAID_BOSS not in out, (
        "a raid boss with no monster tile is unreachable; returning it lets "
        "potion stocking size itself against a fight that can never happen"
    )


def test_event_monster_excluded_while_its_event_is_inactive():
    _clear_cache()
    out = combat_target_monsters(_state(), _gd())
    assert _EVENT_ONLY not in out


def test_event_monster_included_while_its_event_is_active():
    """Reachability, not event-ness, is the gate -- an active event monster IS
    fightable, and excluding it would undo the event-visibility work."""
    _clear_cache()
    gd = _gd()
    gd.active_event_codes = {_EVENT_ONLY}
    assert _EVENT_ONLY in combat_target_monsters(_state(), gd)


def test_memo_key_tracks_active_events():
    """The memo must not serve a stale answer across an event boundary.

    The result now depends on `active_event_codes`, which the player mutates on
    the SAME GameData object every cycle (player.py:1275). A key of
    (id(game_data), level, equipment) would return the pre-event answer for the
    rest of the run -- the read-set/memo-key rule.
    """
    _clear_cache()
    gd = _gd()
    state = _state()
    before = combat_target_monsters(state, gd)
    assert _EVENT_ONLY not in before
    gd.active_event_codes = {_EVENT_ONLY}          # same object, mutated in place
    after = combat_target_monsters(state, gd)
    assert _EVENT_ONLY in after, (
        "memo served a stale pre-event result; active_event_codes is part of "
        "this function's read-set and must be part of its key"
    )
