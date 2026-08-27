"""Wave 4: the taskmaster choice (`choose_taskmaster`, spec §4).

Picks the tasks master whose pool best serves the pursued gear. The lever is
binary — combat tasks (char_xp) vs craft/gather tasks (materials + skills) — and
is scored against the live GEAR demand, not the trunk, so a monsters master does
not trivially win. These tests pin the lever both ways, the nearer-tile
tie-break, and the two "no choice" edges that fall back to today's behaviour.
"""

import json
from pathlib import Path

import pytest

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.accept_task_goal import AcceptTaskGoal
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import map_means
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.tiers.objective_needs import NeedSet
from artifactsmmo_cli.ai.tiers.taskmaster_choice import choose_taskmaster
from tests.test_ai.fixtures import make_state

_BUNDLE = Path("tests/test_ai/scenarios/fixtures/gamedata_bundle.json")


@pytest.fixture(scope="module")
def bundle_game_data() -> GameData:
    return GameData.from_cache_bundle(json.loads(_BUNDLE.read_text()))


class _FakeTask:
    def __init__(self, code: str, type_: str) -> None:
        self.code = code
        self.type_ = type_          # plain str: getattr(str,'value',str) == str


class _FakeMemo:
    def __init__(self, demands: dict[str, dict[str, int]]) -> None:
        self._demands = demands

    def requirement_multiset_for(self, code: str) -> dict[str, int]:
        return self._demands.get(code, {})


class _FakeGameData:
    def __init__(self, tiles, tasks_by_type, demands) -> None:
        self.taskmaster_tiles = tiles
        self._tasks = tasks_by_type
        self.requirement_graph = _FakeMemo(demands)

    def tasks_for(self, task_type, max_level):
        return self._tasks.get(task_type, [])


_TILES = {"monsters": (1, 1), "items": (5, 5)}


def test_one_master_no_choice():
    """Only one master discovered — no distribution to pick, fall back (None).
    This is exactly the pre-Phase-0 world, so Phase 4 was provably inert then."""
    gd = _FakeGameData({"monsters": (1, 1)}, {"monsters": [_FakeTask("w", "monsters")]}, {})
    assert choose_taskmaster(make_state(), gd, frozenset()) is None


def test_both_pools_empty_no_choice():
    """Two masters, but neither has a level-appropriate task — no basis to
    choose, fall back to the nearest/default tile (None)."""
    gd = _FakeGameData(_TILES, {"monsters": [], "items": []}, {})
    assert choose_taskmaster(make_state(), gd, frozenset({"gear"})) is None


def test_monsters_preferred_when_gear_routes_through_drops():
    """Gear whose closure needs monster drops (a char_xp token) aligns with the
    combat master; the unrelated craft task stays at the floor."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"drop_gear": {"char_xp": 3}, "copper_bar": {"copper_ore": 2}},
    )
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, frozenset({"drop_gear"}))
    assert chosen == ("monsters", (1, 1))


def test_items_preferred_when_gear_needs_materials_and_skills():
    """Gear routed through crafting (shared materials + a skill token) aligns with
    the items master; the combat task does not (the gear needs no char_xp)."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"craft_gear": {"skill:mining": 2, "copper_ore": 5},
         "copper_bar": {"copper_ore": 3, "skill:mining": 1}},
    )
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, frozenset({"craft_gear"}))
    assert chosen == ("items", (5, 5))


def test_tie_breaks_to_the_nearer_tile():
    """A demand NEITHER pool serves → both score S_MIN → the masters tie → the
    nearer tile wins (travel is a legitimate tie-break, never part of the score).

    THE DEMAND IS NON-EMPTY ON PURPOSE. This test used to pass `frozenset()`,
    and wave 6 increment 5.5 made that its own arm: an empty demand now returns
    None rather than falling through to a pure distance decision. The tie-break
    itself is unchanged and still reachable — two POPULATED pools can score
    equally — so the fixture asks for something neither master can supply
    instead of asking for nothing."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")],
         "items": [_FakeTask("copper_bar", "items")]},
        {"copper_bar": {"copper_ore": 1}, "iron_bar": {"iron_ore": 1}},
    )
    # Expands to REAL tokens (iron_bar -> iron_ore) that neither pool supplies,
    # so the demand is non-empty and both masters still score S_MIN. An item
    # absent from the catalogue would expand to nothing and take the
    # empty-demand arm instead, which is a different case.
    unserved = frozenset({"iron_bar"})
    # character at (0,0): monsters tile (1,1) dist 2 < items (5,5) dist 10
    chosen = choose_taskmaster(make_state(x=0, y=0), gd, unserved)
    assert chosen == ("monsters", (1, 1))
    # move the character next to the items tile: now items is nearer and wins
    chosen2 = choose_taskmaster(make_state(x=5, y=4), gd, unserved)
    assert chosen2 == ("items", (5, 5))


def test_choice_fires_on_real_bundle(bundle_game_data: GameData):
    """Runtime activation (spec §7): on the real bundle, with its two discovered
    masters and a level that has tasks, the choice returns one of the real
    taskmaster tiles — proof it is not silently inert."""
    tiles = bundle_game_data.taskmaster_tiles
    assert len(tiles) == 2, "bundle should carry both keyed masters (Phase 0)"
    # A REAL demand, not `frozenset()`. Wave 6 increment 5.5 gave the empty case
    # its own arm — it returns None now — so passing nothing here would assert
    # that a fallback fires, not that the choice does.
    chosen = choose_taskmaster(make_state(level=40, x=0, y=0), bundle_game_data,
                               frozenset({"iron_sword"}))
    assert chosen is not None, "no task at level 40 in either pool — choice inert"
    code, tile = chosen
    assert code in tiles and tile == tiles[code]

def test_map_means_parameterises_the_goal_with_the_chosen_master(
        bundle_game_data: GameData):
    """The choice reaches the GOAL, not just the helper. A parameterised
    `AcceptTaskGoal` carries the chosen tile and emits its own action rather than
    filtering the prebuilt pool, which is what steers the task DISTRIBUTION."""
    state = make_state(level=40, x=0, y=0)
    ctx = SelectionContext(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
        draw_owed=True)
    # `needs` carries the ACTIVE LINK's demand since wave 6 increment 5.5.
    # Without it the demand is empty, `choose_taskmaster` declines, and the goal
    # is correctly UNPARAMETERISED — which is the sibling test below, not this
    # one. This test is about the choice reaching the goal, so it must supply a
    # link that actually wants something.
    needs = NeedSet(materials=frozenset({"iron_ore"}), skill_xp=frozenset(),
                    buy_only=frozenset(), char_xp=False)
    goal = map_means(MeansKind.ACCEPT_TASK, bundle_game_data, ctx, state,
                     needs=needs)
    assert isinstance(goal, AcceptTaskGoal)
    emitted = goal.relevant_actions([], state, bundle_game_data)
    assert len(emitted) == 1, "a parameterised goal emits its own accept"
    assert emitted[0].taskmaster_location in bundle_game_data.taskmaster_tiles.values()


def test_an_unparameterised_goal_filters_the_prebuilt_pool():
    """The fallback arm: no second master, so the goal keeps today's behaviour
    and narrows whatever the factory built."""
    goal = AcceptTaskGoal()
    pool = [AcceptTaskAction(taskmaster_location=(2, 1)), MoveAction(x=0, y=0)]
    assert goal.relevant_actions(pool, make_state(), GameData()) == [pool[0]]


_O9_BUNDLE = (Path(__file__).parent / "scenarios" / "fixtures"
              / "gamedata_bundle.json")


def _bundle_gd() -> GameData:
    return GameData.from_cache_bundle(json.loads(_O9_BUNDLE.read_text()))


def _bundle_state():
    from artifactsmmo_cli.ai.scenario import SCENARIOS, scenario_state
    return scenario_state(SCENARIOS["l32_held_task_closable"], _bundle_gd())


# ---------------------------------------------------------------------------
# NO DEMAND, NO PREFERENCE (wave 6, increment 5.5 / obligation O9a)
# ---------------------------------------------------------------------------

def test_empty_demand_declines_to_choose() -> None:
    """An empty demand set returns None — fall back to the default master.

    THIS ARM IS REACHABLE ONLY BECAUSE OF THE RE-POINT. Scored against the gear
    SHEET the demand was never empty (the sheet always wants something), so the
    case could not arise. Scored against the ACTIVE LINK it arises exactly when
    the link is a `ReachCharLevel` — level up, which no items task serves.

    Without it the scorer falls through with every pool at 0 and hands the whole
    decision to the DISTANCE tie-break, making travel the decision rather than
    the tie-break its own docstring says it is. Measured on the committed bundle
    before this arm existed: the choice was identical in 44/44 cells because the
    nearer tile always won."""
    gd = _bundle_gd()
    state = _bundle_state()
    assert len(gd.taskmaster_tiles) >= 2, "fixture must offer a real choice"
    assert choose_taskmaster(state, gd, frozenset()) is None


def test_a_real_demand_still_scores_a_choice() -> None:
    """NOT VACUOUS. The empty arm must not have turned the function off: a
    populated demand still returns a master, so `None` means "nothing
    distinguishes them" rather than "this never chooses"."""
    gd = _bundle_gd()
    state = _bundle_state()
    chosen = choose_taskmaster(state, gd, frozenset({"iron_sword"}))
    assert chosen is not None
    assert chosen[0] in gd.taskmaster_tiles


def test_a_master_with_no_pool_at_this_level_is_skipped() -> None:
    """A master offering nothing at the character's level is passed over, and
    the other one still wins.

    REACHED WITH A REAL DEMAND. This path used to be exercised by tests passing
    `frozenset()`, which now short-circuits at the empty-demand arm — so the
    empty-pool skip and the no-pool-anywhere case below both needed their own
    non-empty-demand fixtures to stay covered."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [_FakeTask("wolf", "monsters")], "items": []},
        {"copper_bar": {"copper_ore": 1}, "iron_bar": {"iron_ore": 1}},
    )
    chosen = choose_taskmaster(make_state(x=5, y=4), gd, frozenset({"iron_bar"}))
    # items is NEARER from (5,4), so picking monsters proves the empty pool was
    # skipped rather than merely out-scored.
    assert chosen == ("monsters", (1, 1))


def test_no_master_with_a_pool_returns_none() -> None:
    """Both pools empty at this level: nothing to score, so no choice to make.

    Distinct from the empty-DEMAND arm above — here the demand is real and it is
    the SUPPLY that is missing. Both return None, and conflating them would hide
    a bundle with no tasks behind a fallback that looks deliberate."""
    gd = _FakeGameData(
        _TILES,
        {"monsters": [], "items": []},
        {"iron_bar": {"iron_ore": 1}},
    )
    assert choose_taskmaster(make_state(x=0, y=0), gd,
                             frozenset({"iron_bar"})) is None
