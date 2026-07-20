"""plan_fits_event_window: reject a plan whose event-only content expires first.

The P2 gap: the planner would commit a long chain to content that expires in
ninety seconds, because nothing outside event_availability read
WorldState.active_events' expirations.

Two judgements this makes, both of which have a concrete witness in the bundle:

* EVENT-GATED means event tiles AND NO static tile. A monster that spawns both
  ways (solar_desert_scorpion is the bundle's one such case) is NOT window-gated:
  the plan can be finished after the event closes.
* The ETA is the summed action costs, converted at 10 seconds per cost unit. It
  is an APPROXIMATION -- costs are evaluated against the starting state, and some
  are history-dependent -- so this is a guard against the obviously-impossible,
  not a scheduler.
"""

from datetime import datetime, timedelta, timezone

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.event_plan_window import plan_fits_event_window
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import make_state

_EVENT = "fairy_ring"
_EVENT_ONLY = "pixie_swarm"      # event tiles, NO static tile
_BOTH = "desert_scorpion"        # event tiles AND a static tile
_NOW = datetime(2026, 7, 20, 12, 0, tzinfo=timezone.utc)


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {"x": ItemStats(code="x", level=1, type_="resource")}
    gd._monster_level = {_EVENT_ONLY: 5, _BOTH: 5}
    gd._monster_hp = {_EVENT_ONLY: 10, _BOTH: 10}
    gd._monster_attack = {_EVENT_ONLY: {}, _BOTH: {}}
    gd._monster_resistance = {_EVENT_ONLY: {}, _BOTH: {}}
    gd._monster_locations = {_BOTH: [(1, 0)]}          # STATIC tile for _BOTH only
    gd.world.event_monster_locations = {_EVENT_ONLY: [(3, 0)], _BOTH: [(4, 0)]}
    gd.world.event_code_of_content = {_EVENT_ONLY: _EVENT, _BOTH: _EVENT}
    gd.world.active_event_codes = {_EVENT}
    fill_monster_stat_defaults(gd)
    return gd


def _state(seconds_left: float):
    return make_state(x=0, y=0, level=10, attack={"fire": 50},
                      active_events={_EVENT: _NOW + timedelta(seconds=seconds_left)})


def _fight(code):
    gd = _gd()
    return FightAction(monster_code=code,
                       locations=frozenset(gd.monster_locations(code)))


def test_plan_without_event_content_always_fits():
    plan = [MoveAction(x=1, y=1)]
    assert plan_fits_event_window(plan, _state(30), _gd(), _NOW) is True


def test_ample_window_fits():
    assert plan_fits_event_window([_fight(_EVENT_ONLY)], _state(3600), _gd(), _NOW) is True


def test_window_too_short_for_the_plan_does_not_fit():
    """THE P2 CASE: the window outlasts the walk but not the work."""
    plan = [_fight(_EVENT_ONLY)] * 12
    assert plan_fits_event_window(plan, _state(90), _gd(), _NOW) is False


def test_content_with_a_static_tile_is_not_window_gated():
    """solar_desert_scorpion's shape: reachable after the event closes, so a
    short window must NOT suppress the plan."""
    assert plan_fits_event_window([_fight(_BOTH)] * 12, _state(5), _gd(), _NOW) is True


def test_inactive_event_does_not_fit():
    """Event-only content with no active window cannot be planned against."""
    state = make_state(x=0, y=0, level=10, attack={"fire": 50}, active_events={})
    assert plan_fits_event_window([_fight(_EVENT_ONLY)], state, _gd(), _NOW) is False


def test_gathers_are_gated_too():
    """Not just fights -- an event-only RESOURCE is the same question."""
    gd = _gd()
    gd._resource_drops = {"fairy_dust_node": "fairy_dust"}
    gd.world.event_resource_locations = {"fairy_dust_node": [(3, 0)]}
    gd.world.event_code_of_content["fairy_dust_node"] = _EVENT
    plan = [GatherAction(resource_code="fairy_dust_node",
                         locations=frozenset({(3, 0)}))] * 12
    assert plan_fits_event_window(plan, _state(90), gd, _NOW) is False
    assert plan_fits_event_window(plan, _state(3600), gd, _NOW) is True


def test_naive_now_is_rejected_loudly():
    """Mirrors event_npc_tradeable: a naive datetime would raise an opaque
    TypeError deep in the planner instead."""
    import pytest
    with pytest.raises(ValueError, match="timezone-aware"):
        plan_fits_event_window([_fight(_EVENT_ONLY)], _state(90), _gd(),
                               datetime(2026, 7, 20, 12, 0))


# ─── the WIRING, not just the helper ─────────────────────────────────────────
# A gate that is never CALLED is worse than no gate: it reads as coverage while
# enforcing nothing. This drives the real driver seam (_plan_and_record).
#
# An earlier attempt here drove the whole planner and was VACUOUS -- the fixture
# character sat at 100/150 HP, so HP_CRITICAL fired and the plan was ['Rest'];
# the event fight was never planned, so "it was suppressed" proved nothing. The
# non-vacuity check caught it. This version stubs the PLANNER (a collaborator,
# not the unit under test) so an event-only plan definitely reaches the seam.

class _DummyGoal:
    """A minimal real-shaped Goal: not WaitGoal (which the seam short-circuits)
    and never satisfied, so the stubbed planner's plan is what reaches the gate."""

    def is_plannable(self, state, game_data, history=None):
        return True

    def is_satisfied(self, state):
        return False

    def relevant_actions(self, actions, state, game_data):
        return list(actions)

    def max_depth(self):
        return 20

    def __repr__(self):
        return "DummyGoal"


def _driver_with_plan(plan, gd, state):
    from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter

    class _StubPlanner:
        """Returns a fixed plan; the seam's job is to gate it, not to find it."""
        def __init__(self):
            self.last_stats = type("S", (), {
                "nodes_explored": 1, "max_depth_reached": 1,
                "timed_out": False, "node_capped": False})()

        def plan(self, *a, **kw):
            return list(plan)

    driver = StrategyArbiter.__new__(StrategyArbiter)
    driver._planner = _StubPlanner()
    driver._history = None
    driver.goals_tried = []
    driver._last_timed_out = False
    return driver


def test_wiring_calls_the_gate_and_drops_an_unfinishable_event_plan():
    """The seam must DROP a plan whose event window cannot fit it."""
    gd = _gd()
    now = datetime.now(timezone.utc)
    state = make_state(x=0, y=0, level=10, attack={"fire": 50},
                       active_events={_EVENT: now + timedelta(seconds=30)})
    plan = [_fight(_EVENT_ONLY)] * 12
    driver = _driver_with_plan(plan, gd, state)
    out = driver._plans(_DummyGoal(), state, gd, [], None, budget_seconds=1.0)
    assert out == [], [repr(a) for a in out]
    assert driver.goals_tried[-1]["plan_len"] == 0


def test_wiring_passes_the_same_plan_through_an_ample_window():
    """Non-vacuity: identical plan, longer window -> NOT dropped. Without this
    the test above would pass even if the seam dropped every plan."""
    gd = _gd()
    now = datetime.now(timezone.utc)
    state = make_state(x=0, y=0, level=10, attack={"fire": 50},
                       active_events={_EVENT: now + timedelta(days=1)})
    plan = [_fight(_EVENT_ONLY)] * 12
    driver = _driver_with_plan(plan, gd, state)
    out = driver._plans(_DummyGoal(), state, gd, [], None, budget_seconds=1.0)
    assert len(out) == 12
    assert driver.goals_tried[-1]["plan_len"] == 12


# ─── _event_only_target: the load-bearing classification ─────────────────────
# Tested directly (not just through plan_fits_event_window) because this is where
# the "event tiles AND no static tile" judgement lives. Using is_event_monster
# alone here would wrongly gate solar_desert_scorpion, whose shape _BOTH mirrors.

def test_classifier_flags_event_only_content():
    from artifactsmmo_cli.ai.event_plan_window import _event_only_target
    assert _event_only_target(_fight(_EVENT_ONLY), _gd()) == _EVENT_ONLY


def test_classifier_ignores_content_with_a_static_tile():
    """The solar_desert_scorpion shape: in the event registry AND permanently
    spawned, so a plan against it survives the window closing."""
    from artifactsmmo_cli.ai.event_plan_window import _event_only_target
    assert _event_only_target(_fight(_BOTH), _gd()) is None


def test_classifier_ignores_plain_content():
    from artifactsmmo_cli.ai.event_plan_window import _event_only_target
    gd = _gd()
    gd._monster_locations = {"chicken": [(1, 1)], _BOTH: [(1, 0)]}
    fight = FightAction(monster_code="chicken", locations=frozenset({(1, 1)}))
    assert _event_only_target(fight, gd) is None


def test_classifier_ignores_non_targeting_actions():
    """Move/Rest carry no target, so they can never be window-gated."""
    from artifactsmmo_cli.ai.event_plan_window import _event_only_target
    assert _event_only_target(MoveAction(x=1, y=1), _gd()) is None


def test_classifier_flags_event_only_resources():
    from artifactsmmo_cli.ai.event_plan_window import _event_only_target
    gd = _gd()
    gd._resource_drops = {"fairy_dust_node": "fairy_dust"}
    gd.world.event_resource_locations = {"fairy_dust_node": [(3, 0)]}
    gather = GatherAction(resource_code="fairy_dust_node",
                          locations=frozenset({(3, 0)}))
    assert _event_only_target(gather, gd) == "fairy_dust_node"


def test_state_says_active_but_gamedata_overlay_disagrees_does_not_fit():
    """The DESYNC guard. `state.active_events` and
    `game_data.world.active_event_codes` are separate sources, synced per cycle
    by the player. If the state believes the window is open but the overlay has
    not been refreshed, the content resolves to NO reachable tiles -- there is
    nothing to route to, so the plan cannot be honoured.

    Reaching this needs the two sources to disagree; an empty tile list instead
    makes the content read as non-event and skips the gate entirely."""
    gd = _gd()
    gd.world.active_event_codes = set()          # overlay says the event is SHUT
    fight = FightAction(monster_code=_EVENT_ONLY, locations=frozenset({(3, 0)}))
    # ...while the STATE still carries an un-expired window for it.
    assert plan_fits_event_window([fight], _state(3600), gd, _NOW) is False
