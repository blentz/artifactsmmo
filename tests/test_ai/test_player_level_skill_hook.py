"""When plan[0] is a LevelSkill, the player runs ONE grind-cycle leg instead of
calling LevelSkill.execute (which raises). Uses a fake client + patched planner
so no live API and a deterministic sub-plan leg.

The last two tests use the REAL planner (no planner.plan mock): a grind rung's
material closure can need a cross-skill under-level intermediate, so sub_plan[0]
is itself a LevelSkill for another skill — the player must recurse through
_execute_level_skill (threading a cycle guard), not loop forever."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.planner import PlanStats
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.scenario import ScenarioCharacter, scenario_state
from artifactsmmo_cli.ai.world_state import WorldState


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "trinket": ItemStats(code="trinket", level=1, type_="resource",
                             subtype="craft", crafting_skill="gearcrafting",
                             crafting_level=1),
        "gear_ore": ItemStats(code="gear_ore", level=1, type_="resource",
                              subtype="mob"),
    }
    gd._crafting_recipes = {"trinket": {"gear_ore": 1}}
    gd._resource_drops = {"gear_rocks": "gear_ore"}
    gd._resource_skill = {"gear_rocks": ("mining", 1)}
    gd._resource_locations = {"gear_rocks": [(3, 3)]}
    gd._workshop_locations = {"gearcrafting": (2, 2)}
    return gd


def _under_skill_player() -> GamePlayer:
    gd = _gd()
    player = GamePlayer(character="hero")
    player.game_data = gd
    player.state = scenario_state(
        ScenarioCharacter(name="hero", level=5, skills={"gearcrafting": 1}), gd)
    return player


def test_level_skill_step_runs_grind_leg_not_execute() -> None:
    """_execute(LevelSkill) plans the skill_grind goal and executes its FIRST
    leg (a GatherAction) — never LevelSkill.execute (which raises)."""
    player = _under_skill_player()
    leg = GatherAction(resource_code="gear_rocks",
                       locations=frozenset({(3, 3)}))
    advanced = replace(player.state, x=3, y=3)
    client = MagicMock()

    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan",
                         return_value=[leg]) as plan_spy, \
            patch.object(GatherAction, "execute",
                         return_value=advanced) as gather_exec, \
            patch.object(LevelSkill, "execute") as level_exec:
        new_state, outcome = player._execute(
            LevelSkill("gearcrafting", 5), client)

    assert outcome == "ok"
    assert new_state is advanced
    gather_exec.assert_called_once()
    level_exec.assert_not_called()
    # The planner was asked to satisfy the skill_grind GatherMaterials goal.
    planned_goal = plan_spy.call_args.args[1]
    assert isinstance(planned_goal, GatherMaterialsGoal)
    assert planned_goal.skill_grind is True


def test_level_skill_step_raises_when_no_rung() -> None:
    """The guard itself still raises (asserted at `_execute_level_skill`, where
    the raise originates): no grind rung -> RuntimeError rather than a silent
    no-op. `_execute` wraps this into an error cycle instead of crashing (see
    test_level_skill_step_degrades_not_crash_*)."""
    player = _under_skill_player()
    client = MagicMock()
    with patch("artifactsmmo_cli.ai.player.next_grind_goal", return_value=None):
        with pytest.raises(RuntimeError, match="no grind rung"):
            player._execute_level_skill(LevelSkill("gearcrafting", 5), client)


def test_level_skill_step_raises_when_grind_produces_no_leg() -> None:
    """The guard itself still raises (asserted at `_execute_level_skill`): a rung
    exists but the grind goal yields no plan -> RuntimeError. `_execute` degrades
    this to an error cycle (see test_level_skill_step_degrades_not_crash_*)."""
    player = _under_skill_player()
    client = MagicMock()
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]):
        with pytest.raises(RuntimeError, match="no leg"):
            player._execute_level_skill(LevelSkill("gearcrafting", 5), client)


def test_no_leg_raise_names_a_TIMEOUT_as_a_blow_up_not_a_dead_end() -> None:
    """A budget timeout and a genuine dead end both surface as an empty
    sub-plan, and the raise used to word BOTH as "grind produced no leg" — which
    reads as unreachability. Live C3P0 2026-08-01: all 109 failing cycles were
    timeouts (`planner.timed_out` True on every one, `node_capped` on none), yet
    the message sent the diagnosis hunting for a dead end. The timeout arm must
    say so, and carry the goal + search stats the trace otherwise never records
    (`_last_grind_expansion` is cleared before this raise, so a failed grind
    cycle shows no chain at all)."""
    player = _under_skill_player()
    client = MagicMock()
    stats = PlanStats(nodes_explored=63944, max_depth_reached=84, timed_out=True)
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]), \
            patch.object(player.planner, "last_stats", stats):
        with pytest.raises(RuntimeError) as excinfo:
            player._execute_level_skill(LevelSkill("gearcrafting", 5), client)

    message = str(excinfo.value)
    assert "EXHAUSTED" in message
    assert "not a dead end" in message
    # The goal and the search size are what an offline bisect had to recover.
    assert "63944" in message and "84" in message
    assert "GatherMaterials" in message


def test_no_leg_raise_still_names_a_genuine_DEAD_END() -> None:
    """The other arm: search space exhausted without a timeout is a real dead
    end, and keeps the original wording so existing trace tooling still matches."""
    player = _under_skill_player()
    client = MagicMock()
    stats = PlanStats(nodes_explored=12, max_depth_reached=3, timed_out=False)
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]), \
            patch.object(player.planner, "last_stats", stats):
        with pytest.raises(RuntimeError, match="grind produced no leg") as excinfo:
            player._execute_level_skill(LevelSkill("gearcrafting", 5), client)

    assert "genuine dead end" in str(excinfo.value)
    assert "EXHAUSTED" not in str(excinfo.value)


def test_level_skill_step_degrades_not_crash_when_no_leg() -> None:
    """Fix B (crash-SAFETY): an EMPTY grind sub-plan is reachable by an ordinary
    planner timeout / node-cap (`GOAPPlanner.plan` returns [] under the 10s
    CHEAP_BUDGET_SECONDS), not only by logic errors. Dispatched INSIDE
    `_execute`'s try, the guard's RuntimeError is caught and converted to an
    `error:other` cycle — the session must NOT crash (`run()` has no `except`).
    Before Fix B the dispatch was BEFORE the try, so this propagated out of
    `run()` and ended the session with exit_reason="crash"."""
    player = _under_skill_player()
    client = MagicMock()
    refreshed = replace(player.state, x=9, y=9)
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]), \
            patch.object(player, "_fetch_world_state",
                         return_value=refreshed) as fetch:
        new_state, outcome = player._execute(
            LevelSkill("gearcrafting", 5), client)

    assert outcome == "error:other"
    assert new_state is refreshed
    fetch.assert_called_once()


# --- The failing grind must DAMPEN the goal that ordered it -------------------
#
# A grind expansion that produces no leg leaves the world untouched, so the next
# replan re-derives the same decision and the bot repeats the same failing
# action forever (live Robby 2026-08-03: 8 of 16 consecutive cycles; live C3P0
# 2026-08-01: 9.5h). The doomed memo never saw it, because the OUTER goal plans
# fine — it is the plan's LevelSkill STEP that cannot be expanded.


def _cached_goal_player(goal_repr: str) -> GamePlayer:
    """An under-skill player mid-plan, as the run loop leaves it: `_plan_cache`
    names the goal whose plan holds the LevelSkill step about to fail."""
    player = _under_skill_player()
    goal = GatherMaterialsGoal(target_item="trinket", needed={"trinket": 1})
    player._plan_cache = PlanCache(
        selected_goal=goal, plan=[LevelSkill("gearcrafting", 5)],
        crafting_target=None, latch_active=False, goal_repr=goal_repr)
    return player


def _raise_no_leg(player: GamePlayer, stats: PlanStats) -> None:
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[]), \
            patch.object(player.planner, "last_stats", stats):
        with pytest.raises(RuntimeError):
            player._execute_level_skill(LevelSkill("gearcrafting", 5), MagicMock())


def test_dead_end_grind_marks_the_ordering_goal_doomed() -> None:
    """The missing backoff edge: a dead-end expansion marks the cached goal in
    the arbiter's doomed memo, so the next cycle's arbiter skips it instead of
    re-picking the identical failing LevelSkill."""
    player = _cached_goal_player("UpgradeEquipment(life_ring->ring2_slot)")
    assert player.state is not None
    _raise_no_leg(player, PlanStats(nodes_explored=4, max_depth_reached=2,
                                    timed_out=False))
    assert player._arbiter._memo.is_doomed(
        "UpgradeEquipment(life_ring->ring2_slot)", player.state,
        player._cycle_counter) is True


def test_timed_out_grind_marks_the_ordering_goal_doomed() -> None:
    """The other arm marks too. Unlike the arbiter's two-pass planning, the
    grind expansion has no full-budget escalation for a cheap timeout to stay
    available for — one shot per cycle is all it gets, so a timeout here is as
    conclusive as a dead end (C3P0's 109 failures were ALL timeouts)."""
    player = _cached_goal_player("UpgradeEquipment(life_ring->ring1_slot)")
    assert player.state is not None
    _raise_no_leg(player, PlanStats(nodes_explored=63944, max_depth_reached=84,
                                    timed_out=True))
    assert player._arbiter._memo.is_doomed(
        "UpgradeEquipment(life_ring->ring1_slot)", player.state,
        player._cycle_counter) is True


def test_grind_failure_with_no_plan_cache_marks_nothing() -> None:
    """No cached plan means no goal to attribute the failure to (a `plan_once`
    diagnostic run executes nothing). The raise still reports the fault; the
    memo stays empty rather than doom an arbitrary goal."""
    player = _under_skill_player()
    assert player._plan_cache is None
    _raise_no_leg(player, PlanStats(nodes_explored=4, max_depth_reached=2,
                                    timed_out=False))
    assert player._arbiter._memo._entries == {}


def test_successful_grind_leaves_the_memo_alone() -> None:
    """Only a FAILED expansion dooms: a grind that yields a leg must not
    suppress the goal that ordered it."""
    player = _cached_goal_player("UpgradeEquipment(life_ring->ring2_slot)")
    leg = GatherAction(resource_code="gear_rocks", locations=frozenset({(3, 3)}))
    advanced = replace(player.state, x=3, y=3)
    with patch.object(player, "_build_actions", return_value=[]), \
            patch.object(player.planner, "plan", return_value=[leg]), \
            patch.object(GatherAction, "execute", return_value=advanced):
        player._execute_level_skill(LevelSkill("gearcrafting", 5), MagicMock())

    assert player._arbiter._memo._entries == {}


# --- Cross-skill nested grind (REAL planner, no planner.plan mock) ------------
#
# Rung R (gear_rung, gearcrafting-5, craftable at the char's current gearcrafting
# level) needs intermediate I (gem_widget) whose ONLY source is crafting at
# jewelrycrafting-8 (> the char's current jewelrycrafting-2, not gatherable /
# buyable / dropped). jewelrycrafting has its own in-level grind rung S
# (jewel_rung, jewelrycrafting-2). So the real planner's cheapest way to reach
# gear_rung is [LevelSkill(jewelrycrafting), Craft(gem_widget), Craft(gear_rung)]
# — sub_plan[0] is a LevelSkill for ANOTHER skill.


def _cross_skill_gd() -> GameData:
    """gearcrafting rung whose recipe needs a jewelrycrafting under-level
    intermediate; jewelrycrafting has its own in-level rung."""
    gd = GameData()
    gd._item_stats = {
        # A-skill rung, craftable at current gearcrafting 5.
        "gear_rung": ItemStats(code="gear_rung", level=5, type_="resource",
                               subtype="craft", crafting_skill="gearcrafting",
                               crafting_level=5),
        # Cross-skill intermediate, UNDER-level (jewelrycrafting 8 > current 2);
        # only obtainable by crafting (its input gem_ore is a resource drop).
        "gem_widget": ItemStats(code="gem_widget", level=8, type_="resource",
                                subtype="craft", crafting_skill="jewelrycrafting",
                                crafting_level=8),
        # B-skill rung, craftable at current jewelrycrafting 2.
        "jewel_rung": ItemStats(code="jewel_rung", level=2, type_="resource",
                                subtype="craft", crafting_skill="jewelrycrafting",
                                crafting_level=2),
        "gem_ore": ItemStats(code="gem_ore", level=1, type_="resource",
                             subtype="mob"),
        "jewel_ore": ItemStats(code="jewel_ore", level=1, type_="resource",
                               subtype="mob"),
    }
    gd._crafting_recipes = {
        "gear_rung": {"gem_widget": 1},
        "gem_widget": {"gem_ore": 1},
        "jewel_rung": {"jewel_ore": 1},
    }
    gd._resource_drops = {"gem_rocks": "gem_ore", "jewel_rocks": "jewel_ore"}
    gd._resource_skill = {"gem_rocks": ("mining", 1), "jewel_rocks": ("mining", 1)}
    gd._resource_locations = {"gem_rocks": [(3, 3)], "jewel_rocks": [(4, 4)]}
    gd._workshop_locations = {"gearcrafting": (2, 2), "jewelrycrafting": (5, 5)}
    # build_actions resolves bank/taskmaster tiles for its always-on actions.
    gd._bank_location = (0, 0)
    gd._taskmaster_location = (0, 0)
    return gd


def _cross_skill_player() -> GamePlayer:
    gd = _cross_skill_gd()
    player = GamePlayer(character="hero")
    player.game_data = gd
    # gem_ore + jewel_ore on hand so the ONLY blocking gap on either rung is the
    # skill level — the plans reduce to [LevelSkill, Craft, Craft] and [Craft].
    player.state = scenario_state(
        ScenarioCharacter(name="hero", level=20,
                          skills={"gearcrafting": 5, "jewelrycrafting": 2},
                          inventory={"gem_ore": 5, "jewel_ore": 5}),
        gd)
    return player


def test_cross_skill_nested_grind_terminates_and_runs_real_leg() -> None:
    """REAL planner: grinding gearcrafting plans a cross-skill jewelrycrafting
    LevelSkill as sub_plan[0]; the player recurses into _execute_level_skill for
    it (cycle-guard threaded) and bottoms out on a CONCRETE jewelrycrafting-grind
    leg (Craft(jewel_rung)). It must terminate — never RecursionError — and never
    call LevelSkill.execute."""
    player = _cross_skill_player()
    client = MagicMock()
    advanced = replace(player.state, x=5, y=5)

    executed: list[Action] = []
    real_execute = player._execute

    def spy_execute(action: Action,
                    _client: object) -> tuple[WorldState, str]:
        executed.append(action)
        return real_execute(action, _client)

    with patch.object(player, "_execute", side_effect=spy_execute), \
            patch.object(CraftAction, "execute", return_value=advanced), \
            patch.object(GatherAction, "execute", return_value=advanced), \
            patch.object(LevelSkill, "execute") as level_exec:
        new_state, outcome = player._execute_level_skill(
            LevelSkill("gearcrafting", 6), client)

    assert outcome == "ok"
    assert new_state is advanced
    level_exec.assert_not_called()
    # Exactly ONE concrete leg reached _execute, and it is the jewelrycrafting
    # grind rung's craft — proof the recursion bottomed out on a real B-grind
    # action rather than looping on LevelSkill.
    assert len(executed) == 1
    leaf = executed[0]
    assert isinstance(leaf, CraftAction)
    assert leaf.code == "jewel_rung"


def test_cyclic_skill_dependency_raises() -> None:
    """The cycle guard: re-entering _execute_level_skill for a skill already in
    the current recursion chain raises rather than looping forever. Driven
    deterministically by seeding `_grinding` with the skill under grind."""
    player = _cross_skill_player()
    client = MagicMock()
    with pytest.raises(RuntimeError, match="cyclic skill-grind dependency"):
        player._execute_level_skill(
            LevelSkill("gearcrafting", 6), client,
            _grinding=frozenset({"gearcrafting"}))
