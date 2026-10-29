"""The fight refused for want of bag room (spec 2026-10-18 §2.10, ruling T13c):
one verdict, carried by the cycle's loadout, read by the keep and by the fight."""

from dataclasses import replace
from unittest.mock import MagicMock, patch

import pytest

import artifactsmmo_cli.ai.craft_plan_gen as craft_plan_gen_mod
import artifactsmmo_cli.ai.player as player_mod
import artifactsmmo_cli.ai.strategy_driver as driver_mod
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.best_loadout import fight_ahead_loadout
from artifactsmmo_cli.ai.chosen_loadout import ChosenLoadout, food_carry
from artifactsmmo_cli.ai.craft_plan_gen import decompose
from artifactsmmo_cli.ai.fight_room_license import license_fights, refusal_line, refused_fight
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.gathering import GatherMaterialsGoal
from artifactsmmo_cli.ai.goals.reach_skill import ReachSkillGoal
from artifactsmmo_cli.ai.goals.task_kills import TaskKillsGoal
from artifactsmmo_cli.ai.inventory_keep import keep_in_bag
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.plan_cache import PlanCache
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter, objective_step_goal
from artifactsmmo_cli.ai.tiers.meta_goal import ReachTaskOutcome
from artifactsmmo_cli.ai.tiers.strategy import StrategyDecision
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults
from tests.test_ai.fixtures import TIMED_NO_PROFILE_CONTEXT, make_state

CTX = replace(TIMED_NO_PROFILE_CONTEXT, combat_monster="ogre")


def _gd() -> GameData:
    """An ogre (100 HP, 30 fire a round) the player kills in 3 rounds at 40 fire,
    ending at 40 of 100 HP; a bone on every win; apples of 30 HP; a bank."""
    gd = GameData()
    gd._monster_level = {"ogre": 5, "wolf": 5}
    gd._monster_hp = {"ogre": 100, "wolf": 100}
    gd._monster_attack = {"ogre": {"fire": 30}, "wolf": {"fire": 30}}
    gd._monster_resistance = {"ogre": {}, "wolf": {}}
    fill_monster_stat_defaults(gd)
    gd._monster_locations = {"ogre": [(3, 4)], "wolf": [(1, 1)]}
    gd._monster_drops = {"ogre": [("bone", 1, 1, 1)]}
    gd._bank_location = (5, 5)
    gd._item_stats = {
        "apple": ItemStats(code="apple", level=1, type_="consumable", hp_restore=30),
        "bone": ItemStats(code="bone", level=1, type_="resource"),
    }
    return gd


def _state(inventory_max: int) -> WorldState:
    """Ten apples in the bag: the recovery eats two a fight, a carry of 40."""
    return make_state(level=5, hp=100, max_hp=100, attack={"fire": 40}, initiative=1,
                      inventory={"apple": 10}, inventory_max=inventory_max)


def _fight(monster: str) -> FightAction:
    return FightAction(monster_code=monster, locations=frozenset({(3, 4)}),
                       learned_drops=LearnedDrops.empty())


def test_the_carry_past_the_bag_refuses_the_fight_and_keeps_the_carry() -> None:
    """A bag of 30 holding the 40-apple carry has no room for the bone: the
    fight's loop does not run. The cycle's loadout says so by name, the fight
    against the ogre is refused and named, and the keep still holds the apple
    carry: this path does not switch the consumables off."""
    gd = _gd()
    state = _state(inventory_max=30)
    loadout = fight_ahead_loadout(state, gd, CTX, None)
    assert loadout is not None
    assert loadout.monster == "ogre" and loadout.runnable is False
    [(food, eaten)] = loadout.food
    assert food == "apple" and food_carry(eaten) > 30
    ctx = replace(CTX, loadout=loadout)
    assert refused_fight(ctx) == "ogre"
    pool: list[Action] = [_fight("ogre"), _fight("wolf"), RestAction()]
    assert license_fights(pool, ctx) == pool[1:]
    assert refusal_line("ogre") == ("Fight ogre refused: no room in the bag for its drops "
                                    "(the keep and the consumable carry fill it)")
    assert keep_in_bag("apple", state, gd, ctx) == food_carry(eaten)


def test_room_for_the_drops_refuses_nothing() -> None:
    gd = _gd()
    loadout = fight_ahead_loadout(_state(inventory_max=200), gd, CTX, None)
    assert loadout is not None and loadout.runnable
    ctx = replace(CTX, loadout=loadout)
    assert refused_fight(ctx) is None
    assert license_fights([_fight("ogre")], ctx) == [_fight("ogre")]


def test_no_fight_ahead_refuses_nothing() -> None:
    assert refused_fight(TIMED_NO_PROFILE_CONTEXT) is None


def test_the_arbiter_plans_without_the_refused_fight(monkeypatch: pytest.MonkeyPatch) -> None:
    """The arbiter licenses the pool on its own ctx and names the refusal in
    the trace's fired kinds."""
    seen: list[list[Action]] = []

    def spy(actions: list[Action], ctx: SelectionContext) -> list[Action]:
        licensed = license_fights(actions, ctx)
        seen.append(licensed)
        return licensed
    monkeypatch.setattr(driver_mod, "license_fights", spy)
    ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (("apple", 2),), (), runnable=False))
    arbiter = StrategyArbiter(GOAPPlanner(), history=None)
    decision = StrategyDecision(interrupt=None, chosen_root=None, chosen_step=None)
    arbiter.select(decision, _state(inventory_max=30), _gd(), [_fight("ogre"), _fight("wolf")], ctx)
    assert seen == [[_fight("wolf")]]
    assert arbiter.last_fires["fight_no_room"] == "ogre"


def test_a_cached_fight_the_last_cycle_refused_is_a_replan() -> None:
    player = player_mod.GamePlayer(character="hero")
    player._last_ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), (), runnable=False))
    assert player._fight_refused(_fight("ogre")) is True
    assert player._fight_refused(_fight("wolf")) is False
    assert player._fight_refused(RestAction()) is False
    player._last_ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), ()))
    assert player._fight_refused(_fight("ogre")) is False


def test_a_party_fight_is_not_refused_on_the_solo_verdict() -> None:
    """T13e re-review minor (3): the refusal is the SOLO loop's (its bag has
    no room for the drops); a party fight's loop counts no trips and always
    runs (`party_loop`), so a party fight against the same monster stays in
    the pool and a cached one is not a replan."""
    party = FightAction(monster_code="ogre", locations=frozenset({(3, 4)}),
                        learned_drops=LearnedDrops.empty(), participants=("Lor",))
    ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), (), runnable=False))
    pool: list[Action] = [_fight("ogre"), party, _fight("wolf")]
    assert license_fights(pool, ctx) == [party, _fight("wolf")]
    player = player_mod.GamePlayer(character="hero")
    player._last_ctx = ctx
    assert player._fight_refused(party) is False
    assert player._fight_refused(_fight("ogre")) is True


def test_a_cached_fight_before_the_first_decision_is_a_replan() -> None:
    """T13e re-review minor (2): a plan cache restored from the store after a
    restart holds no decision's context yet (`NO_PROFILE_CONTEXT`), so no
    refusal verdict. Its fight step does not run on that context: it is a
    replan, whose decision binds the real one."""
    player = player_mod.GamePlayer(character="hero")
    assert player._last_ctx is player_mod.NO_PROFILE_CONTEXT
    assert player._fight_refused(_fight("ogre")) is True
    assert player._fight_refused(RestAction()) is False
    player._last_ctx = CTX
    assert player._fight_refused(_fight("ogre")) is False


def test_a_refused_fight_is_named_in_the_log(capsys: pytest.CaptureFixture[str]) -> None:
    """The decision band prints the refusal beside the gear objective line."""
    player = player_mod.GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    player._strategy = MagicMock()
    player._strategy.decide.return_value = MagicMock(chosen_root=None, chosen_step=None,
                                                     declined=())
    ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), (), runnable=False))
    with (patch.object(player._arbiter, "select", return_value=(None, [], [])),
          patch.object(player, "_record_decision_targets", return_value=None),
          patch.object(player, "_selection_context", return_value=ctx)):
        player._decide_band(make_state(), GameData(), [])
    assert refusal_line("ogre") in capsys.readouterr().out


def test_the_cached_plan_replans_a_refused_fight() -> None:
    """A cached plan whose next step fights the refused monster is not reused:
    its step reads as not applicable, so `should_replan` re-decides."""
    player = player_mod.GamePlayer(character="hero")
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
    goal = MagicMock()
    goal.is_satisfied.return_value = False
    player._plan_cache = PlanCache(selected_goal=goal, plan=[_fight("ogre")],
                                   crafting_target=None, plan_level=5, goal_repr="G")
    seen: list[bool] = []

    def spy(cache: object, outcome: object, level: int, satisfied: bool, applicable: bool,
            *rest: object) -> bool:
        seen.append(applicable)
        return False
    with (patch.object(player_mod, "should_replan", side_effect=spy),
          patch.object(FightAction, "is_applicable", return_value=True),
          patch.object(player_mod.GamePlayer, "_fight_ready", return_value=True)):
        player._last_ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), (), runnable=False))
        player._plan_or_reuse(make_state(), GameData(), [])
        player._last_ctx = replace(CTX, loadout=ChosenLoadout("ogre", (), (), ()))
        player._plan_or_reuse(make_state(), GameData(), [])
    assert seen == [False, True]


_WOLF_AHEAD = ChosenLoadout("wolf", (), (), ())
"""The cycle's loadout is chosen against another monster, so the ogre's fight
is priced by `loadout_for` alone (ruling T14d-2)."""


def _grind_fighting_ogre(monkeypatch: pytest.MonkeyPatch, inventory_max: int) -> tuple[object, list[str]]:
    rung = GatherMaterialsGoal("bone", {"bone": 1})
    monkeypatch.setattr(craft_plan_gen_mod, "grind_rung_goal", lambda *a, **k: rung)
    monkeypatch.setattr(craft_plan_gen_mod, "_walk_plan", lambda *a, **k: [_fight("ogre")])
    monkeypatch.setattr(craft_plan_gen_mod, "heal_prep_goal", lambda *a, **k: None)
    declined: list[str] = []
    plan = decompose(ReachSkillGoal(skill_name="mining", target_level=5),
                     _state(inventory_max=inventory_max), _gd(), [_fight("ogre")],
                     replace(CTX, loadout=_WOLF_AHEAD), declined)
    return plan, declined


def test_a_grinds_fight_with_no_room_for_its_drops_is_refused_at_the_grind(
        monkeypatch: pytest.MonkeyPatch) -> None:
    """T13e re-review minor (1): the grind's fight against the ogre is priced
    by `loadout_for` (the cycle's loadout is the wolf's). Its loop has no room
    for the drops in a bag of 30, so the grind declines it by name; in a bag of
    200 the grind's legs stand."""
    plan, declined = _grind_fighting_ogre(monkeypatch, 30)
    assert plan is None and declined == ["fight_no_room:ogre"]
    plan, declined = _grind_fighting_ogre(monkeypatch, 200)
    assert plan == [_fight("ogre")] and declined == []


def test_a_task_fight_with_no_room_for_its_drops_is_refused_at_its_step() -> None:
    """T13e re-review minor (1): the held task's fight against the ogre is
    priced by `loadout_for`, as its prep is. With no room for the drops the
    task step maps to no goal; with room it is one more kill."""
    gd = _gd()
    ctx = replace(CTX, loadout=_WOLF_AHEAD)
    held = {"task_code": "ogre", "task_type": "monsters", "task_total": 5, "task_progress": 0}
    full = replace(_state(inventory_max=30), **held)
    roomy = replace(_state(inventory_max=200), **held)
    assert objective_step_goal(ReachTaskOutcome("ogre"), full, gd, ctx) is None
    goal = objective_step_goal(ReachTaskOutcome("ogre"), roomy, gd, ctx)
    assert isinstance(goal, TaskKillsGoal) and repr(goal) == "TaskKills(ogre)"


def test_the_task_steps_prep_and_refusal_share_one_guard(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ruling T14d-R m5: the task step's bag-room refusal and its prep are
    guarded by one predicate (`_prices_step_fight`). Where it says the step
    prices no fight, neither is asked: the refusing pick is never read and the
    step is one more kill."""
    asked: list[str] = []
    monkeypatch.setattr(driver_mod, "_prices_step_fight",
                        lambda *a: asked.append(a[3]) or False)
    monkeypatch.setattr(driver_mod, "refuses_fight_against",
                        lambda *a: pytest.fail("the refusal was asked"))
    held = {"task_code": "ogre", "task_type": "monsters", "task_total": 5, "task_progress": 0}
    full = replace(_state(inventory_max=30), **held)
    goal = objective_step_goal(ReachTaskOutcome("ogre"), full, _gd(), replace(CTX, loadout=_WOLF_AHEAD))
    assert isinstance(goal, TaskKillsGoal) and asked == ["ogre", "ogre"]
