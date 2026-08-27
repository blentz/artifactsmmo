"""`ai/decisions/route.py` — the ONE pricing funnel for the resolution graph.

Wave 4 increment 4.1b. This module ships INERT: nothing under `ai/decisions/`
calls it yet, and that is deliberate. Wave 4's `WhichSlotClosesTheFight` (4.2)
is its first caller, and wave 6 completes the dispatch for the two `MetaGoal`
variants left unpriced here.

It lands now, ahead of its caller, because wave 6's obligation O6 forbids any
module under `ai/decisions/` importing `acquisition_cost` except this one. If
4.2 shipped the import inside `decisions/root.py` instead, O6 would be red the
day it was written.
"""

import dataclasses
import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.acquisition_cost import acquisition_actions
from artifactsmmo_cli.ai.acquisition_cost_core import UNOBTAINABLE_PER_UNIT
from artifactsmmo_cli.ai.decisions import route as route_mod
from artifactsmmo_cli.ai.decisions.route import route_exists, route_price
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.projections import cheapest_path_to_level
from artifactsmmo_cli.ai.learning.store import Cycle, LearningStore
from artifactsmmo_cli.ai.obtain_sources import obtain_sources
from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
from artifactsmmo_cli.ai.selection_context import NO_PROFILE_CONTEXT
from artifactsmmo_cli.ai.skill_grind_cost_core import skill_grind_cycles
from artifactsmmo_cli.ai.tiers.meta_goal import (
    META_GOAL_KINDS,
    ObtainItem,
    ReachCharLevel,
    ReachSkillLevel,
)

BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures" / "gamedata_bundle.json")
CELL = "l32_held_task_closable"


@pytest.fixture(scope="module")
def gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(BUNDLE.read_text()))


def _state(game_data: GameData):
    return scenario_state(SCENARIOS[CELL], game_data)


def test_obtain_item_prices_through_acquisition_actions(gd: GameData) -> None:
    """The funnel FORWARDS, it does not re-implement. Asserted against the
    function it forwards to, so a divergence in either is a failure here."""
    state = _state(gd)
    goal = ObtainItem("iron_sword", 1)
    assert route_price(goal, state, gd, NO_PROFILE_CONTEXT, None) == \
        acquisition_actions("iron_sword", 1, state, gd, NO_PROFILE_CONTEXT,
                            equip=False, store=None)


def test_equip_is_derived_from_slot_and_nothing_else(gd: GameData) -> None:
    """`equip` is `slot is not None` — the C11 rule. A slotted goal prices the
    equip action, an unslotted one does not, and the caller never passes it.

    This is the assertion that would fail if someone re-introduced an `equip=`
    parameter and let it disagree with the slot."""
    state = _state(gd)
    slotted = route_price(ObtainItem("iron_sword", 1, slot="weapon_slot"),
                          state, gd, NO_PROFILE_CONTEXT, None)
    bare = route_price(ObtainItem("iron_sword", 1), state, gd,
                       NO_PROFILE_CONTEXT, None)
    assert slotted == acquisition_actions(
        "iron_sword", 1, state, gd, NO_PROFILE_CONTEXT, equip=True, store=None)
    assert bare == acquisition_actions(
        "iron_sword", 1, state, gd, NO_PROFILE_CONTEXT, equip=False, store=None)
    # NOT VACUOUS: the two arms genuinely differ, by exactly the equip action.
    # Measured 10 vs 9 here. Without this line the test above would pass even
    # if `equip` made no difference to the price, which is the shape that makes
    # an assertion decorative.
    assert slotted == bare + 1


def test_quantity_is_forwarded(gd: GameData) -> None:
    """Not pinned by the two tests above, both of which use quantity=1."""
    state = _state(gd)
    assert route_price(ObtainItem("iron_ore", 5), state, gd,
                       NO_PROFILE_CONTEXT, None) == \
        acquisition_actions("iron_ore", 5, state, gd, NO_PROFILE_CONTEXT,
                            equip=False, store=None)


@pytest.mark.parametrize("goal", [
    ReachCharLevel(level=33),
    ReachSkillLevel(skill="weaponcrafting", level=16),
])
def test_the_climbs_are_walled_without_a_learning_store(gd: GameData, goal) -> None:
    """No store means no measured rate, and an unpriceable climb is WALLED, not
    free.

    `UNOBTAINABLE_PER_UNIT`, never 0 and never `inf`. Zero would make a level
    root outrank every gear root; infinity would break the total order the walk
    needs. This is the "free-looking grind" that captured R2D2 for 4.5 hours,
    refused at the funnel."""
    assert route_price(goal, _state(gd), gd, NO_PROFILE_CONTEXT, None) \
        == UNOBTAINABLE_PER_UNIT


def test_the_dispatch_is_total_over_meta_goal_kinds() -> None:
    """DRIFT GUARD. A new `MetaGoal` kind must fail loudly here rather than
    price as 0 — the failure mode `objective_needs` suffered when
    `ReachSkillLevel` became reachable at the flip.

    Asserted over `META_GOAL_KINDS` itself, so adding a kind without an arm
    fails this test rather than silently ranking on an unpriced zero."""
    import inspect

    from artifactsmmo_cli.ai.decisions import route as route_mod
    src = inspect.getsource(route_mod.route_price)
    for kind in META_GOAL_KINDS:
        assert f"isinstance(goal, {kind.__name__})" in src, kind.__name__


def test_route_exists_forwards_to_obtain_sources(gd: GameData) -> None:
    """A pure forward, and CHEAP by contract: a node asking "is this reachable"
    must not pay a full closure walk to learn a boolean.

    Pinned against the producer rather than against a hand-written expectation,
    so the two cannot drift."""
    state = _state(gd)
    for code in ("iron_sword", "iron_ore"):
        assert route_exists(code, state, gd, NO_PROFILE_CONTEXT) \
            is bool(obtain_sources(code, state, gd, NO_PROFILE_CONTEXT))


def test_route_exists_is_not_vacuous(gd: GameData) -> None:
    """The two arms of `route_exists` are both reachable on real bundle data —
    without this the test above passes on an all-True or all-False oracle."""
    state = _state(gd)
    answers = {c: route_exists(c, state, gd, NO_PROFILE_CONTEXT)
               for c in ("iron_sword", "iron_ore", "no_such_item_xyzzy")}
    assert answers["no_such_item_xyzzy"] is False
    assert any(answers[c] for c in ("iron_sword", "iron_ore"))


# ---------------------------------------------------------------------------
# The two climbs, PRICED. The tests above only reach their walled arms; these
# reach the arms that produce a number, which is where a unit error would live.
# ---------------------------------------------------------------------------

def _store(tmp_path, skill: str | None = None, rate: float = 10.0):
    """A store with a measured grind rate for `skill`, or an empty one."""
    st = LearningStore(db_path=str(tmp_path / "route.db"), character="r")
    if skill is not None:
        session = st.start_session()
        for i in range(12):
            st.record_cycle(Cycle(
                ts=f"2026-01-01T00:{i:02d}:00+00:00",
                session_id=session, cycle_index=i, character="r",
                action_repr=f"LevelSkill({skill}->9)", outcome="ok",
                delta_skill_xp_json=json.dumps({skill: rate}),
            ))
    return st


def test_reach_skill_level_prices_the_climb_in_cycles(gd: GameData, tmp_path) -> None:
    """The UNIT IS PLANNER ACTIONS, and cycles ARE actions — this arm forwards to
    `skill_grind_cycles`, the same term `acquisition_cost` charges as
    `unlock_actions`. Asserted against that producer so a skill-gated
    `ObtainItem` and a bare `ReachSkillLevel` cannot price the same climb
    differently."""
    # `skill_max_xp` is EMPTY on every scenario cell, so it is set explicitly
    # here. Without it this test skipped — and a skipped test is a decorative
    # one: it never reached the arm it claims to price.
    state = dataclasses.replace(_state(gd), skill_max_xp={"weaponcrafting": 600})
    store = _store(tmp_path, "weaponcrafting", rate=10.0)
    try:
        rate = store.skill_grind_rate("weaponcrafting") \
            or store.fleet_skill_grind_rate("weaponcrafting")
        max_xp = state.skill_max_xp["weaponcrafting"]
        assert rate and rate > 0, "fixture must yield a measurable rate"
        goal = ReachSkillLevel(skill="weaponcrafting",
                               level=state.skills.get("weaponcrafting", 1) + 2)
        priced = route_price(goal, state, gd, NO_PROFILE_CONTEXT, store)
        assert priced == skill_grind_cycles(
            state.skills.get("weaponcrafting", 1),
            state.skill_xp.get("weaponcrafting", 0), max_xp, goal.level, rate)
        # NOT the wall — this arm produced a real number.
        assert priced < UNOBTAINABLE_PER_UNIT
    finally:
        store.close()


def test_reach_skill_level_is_walled_without_a_measured_rate(
        gd: GameData, tmp_path) -> None:
    """An empty store has no rate for this character AND none for the fleet, so
    the climb is unpriceable — walled, not free. This is the arm that keeps a
    zero-cost grind from outranking everything."""
    store = _store(tmp_path)
    try:
        goal = ReachSkillLevel(skill="weaponcrafting", level=40)
        assert route_price(goal, _state(gd), gd, NO_PROFILE_CONTEXT, store) \
            == UNOBTAINABLE_PER_UNIT
    finally:
        store.close()


def test_reach_char_level_prices_or_walls_by_the_path_plan(
        gd: GameData, tmp_path) -> None:
    """`PathPlan.total_cycles` is already "CYCLES — planner actions", so this arm
    forwards it; a BLOCKED path walls instead.

    Both outcomes are asserted against `cheapest_path_to_level` itself rather
    than a literal, because the fixture's beatable-monster set decides which one
    this cell takes and a hard-coded expectation would rot with the bundle."""
    state = _state(gd)
    store = _store(tmp_path)
    try:
        goal = ReachCharLevel(level=state.level + 1)
        plan = cheapest_path_to_level(goal.level, state, store, gd)
        priced = route_price(goal, state, gd, NO_PROFILE_CONTEXT, store)
        if plan.blocked:
            assert priced == UNOBTAINABLE_PER_UNIT
        else:
            assert priced == int(plan.total_cycles)
    finally:
        store.close()


@dataclasses.dataclass(frozen=True)
class _UnknownMetaGoal:
    """A `MetaGoal`-shaped node that is NOT in `META_GOAL_KINDS`."""


def test_route_price_raises_on_an_unhandled_metagoal_kind(gd: GameData) -> None:
    """A foreign node must FAIL, not price as 0.

    Same convention as `prerequisite_graph.prerequisites` and for the same
    reason: a dispatch that silently reports a number for a kind it does not
    know is the `objective_needs` failure — an unpriced root that outranks
    everything. "API data or fail" applied to a dispatch."""
    with pytest.raises(AssertionError, match="unhandled MetaGoal kind"):
        route_price(_UnknownMetaGoal(), _state(gd), gd, NO_PROFILE_CONTEXT, None)


def test_reach_char_level_forwards_total_cycles_when_the_path_is_open(
        gd: GameData, tmp_path, monkeypatch) -> None:
    """The OPEN arm forwards `PathPlan.total_cycles` unchanged — the unit is
    already "CYCLES — planner actions", so any arithmetic here would be a unit
    error, which is exactly what a structural diff cannot catch.

    The plan is stubbed rather than fixture-derived because which arm the real
    bundle takes is a property of its monster table, not of this function."""
    from artifactsmmo_cli.ai.learning.projections import PathPlan
    monkeypatch.setattr(
        route_mod, "cheapest_path_to_level",
        lambda target, state, store, game_data: PathPlan(
            target_level=target, total_cycles=41.0, blocked=False))
    store = _store(tmp_path)
    try:
        assert route_price(ReachCharLevel(level=33), _state(gd), gd,
                           NO_PROFILE_CONTEXT, store) == 41
    finally:
        store.close()


def test_reach_char_level_walls_a_blocked_path(
        gd: GameData, tmp_path, monkeypatch) -> None:
    """The BLOCKED arm walls. A blocked climb means every beatable monster is
    grey — the character needs GEAR, not monsters — and pricing that at
    `total_cycles` would send it to grind monsters it cannot beat."""
    from artifactsmmo_cli.ai.learning.projections import PathPlan
    monkeypatch.setattr(
        route_mod, "cheapest_path_to_level",
        lambda target, state, store, game_data: PathPlan(
            target_level=target, total_cycles=41.0, blocked=True))
    store = _store(tmp_path)
    try:
        assert route_price(ReachCharLevel(level=33), _state(gd), gd,
                           NO_PROFILE_CONTEXT, store) == UNOBTAINABLE_PER_UNIT
    finally:
        store.close()
