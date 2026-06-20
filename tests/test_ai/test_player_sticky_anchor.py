"""Player progress-gated sticky anchor (the zombie-livelock fix, 2026-06-20).

`GamePlayer._update_sticky_anchor` re-feeds the Tier-2 sticky anchor
(`_last_strategy_root`) only when the committed root yielded a goal this cycle AND
advanced on its own progress axis. A frozen root (the weaponcrafting zombie: skill xp
stuck while the bot gathers a different skill) is released so the higher-value plannable
root wins next cycle. See Formal/Liveness/StickySelect.lean.
"""

from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.tiers.meta_goal import ObtainItem, ReachSkillLevel
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_strategy_driver import (
    _ctx,
    _gd,
    _make_planner_gd,
    objective_step_goal,
)


def _player() -> GamePlayer:
    return GamePlayer(character="hero")


def test_fresh_commit_arms_the_anchor():
    p = _player()
    root = ReachSkillLevel(skill="weaponcrafting", level=5)
    st = make_state(skill_xp={"weaponcrafting": 75})
    p._update_sticky_anchor(root, st, _make_planner_gd(), chosen_step_alive=True)
    assert p._last_strategy_root == repr(root)
    assert p._sticky_progress_value == 75


def test_frozen_skill_zombie_is_released():
    # The 1028-cycle weaponcrafting hold: committed to weaponcrafting, but its xp is
    # frozen across cycles (the bot gathers mining). Second cycle -> no progress ->
    # anchor released so a higher-value root wins next cycle.
    p = _player()
    root = ReachSkillLevel(skill="weaponcrafting", level=5)
    gd = _make_planner_gd()
    # Cycle 1: fresh commit, armed.
    p._update_sticky_anchor(root, make_state(skill_xp={"weaponcrafting": 75}), gd, True)
    assert p._last_strategy_root == repr(root)
    # Cycle 2: same root, weaponcrafting xp UNCHANGED (mining rose, irrelevant) -> release.
    p._update_sticky_anchor(
        root, make_state(skill_xp={"weaponcrafting": 75, "mining": 999}), gd, True)
    assert p._last_strategy_root is None


def test_progressing_skill_keeps_the_anchor():
    p = _player()
    root = ReachSkillLevel(skill="weaponcrafting", level=5)
    gd = _make_planner_gd()
    p._update_sticky_anchor(root, make_state(skill_xp={"weaponcrafting": 75}), gd, True)
    # Cycle 2: weaponcrafting xp rose -> progress -> anchor kept.
    p._update_sticky_anchor(root, make_state(skill_xp={"weaponcrafting": 90}), gd, True)
    assert p._last_strategy_root == repr(root)
    assert p._sticky_progress_value == 90


def test_progressing_gear_keeps_anchor_as_materials_accumulate():
    p = _player()
    # Use the target's own owned count (recipe-input path covered in the core test).
    root = ObtainItem(code="copper_ore", quantity=10, slot=None)
    gd = _make_planner_gd()
    p._update_sticky_anchor(root, make_state(inventory={"copper_ore": 1}), gd, True)
    # Owned grows -> obtain progress rises -> kept.
    p._update_sticky_anchor(root, make_state(inventory={"copper_ore": 4}), gd, True)
    assert p._last_strategy_root == repr(root)


def test_chosen_step_alive_false_releases_even_if_progressing():
    # The 2026-06-19 condition is retained: a root whose step yields no goal is
    # released regardless of progress.
    p = _player()
    root = ReachSkillLevel(skill="weaponcrafting", level=5)
    gd = _make_planner_gd()
    p._update_sticky_anchor(root, make_state(skill_xp={"weaponcrafting": 75}), gd, True)
    p._update_sticky_anchor(
        root, make_state(skill_xp={"weaponcrafting": 90}), gd, chosen_step_alive=False)
    assert p._last_strategy_root is None


def test_none_root_clears_anchor():
    p = _player()
    p._last_strategy_root = "stale"
    p._sticky_progress_value = 5
    p._update_sticky_anchor(None, make_state(), _make_planner_gd(), True)
    assert p._last_strategy_root is None
    assert p._sticky_progress_value is None


def test_step_servable_demotes_doomed_goal():
    # is_plannable is optimistic (feather_coat passed it yet planned to plan_len=0).
    # The doomed memo carries the REAL plan-failure signal: a goal that actually
    # failed to plan is demoted by the servable predicate so chosen_root stops
    # committing to an unbuildable objective while the bot char-grinds.
    p = GamePlayer(character="hero")
    gd = _gd()
    st = make_state()
    ctx = _ctx()
    step = ObtainItem("ash_plank", 6)
    goal = objective_step_goal(step, st, gd, ctx, root=step, committed_root=step)
    assert goal is not None and goal.is_plannable(st, gd)
    pred = p._step_servable(st, gd, ctx)
    # Not doomed -> servable.
    assert pred(step, step) is True
    # Mark the goal doomed in the arbiter memo -> predicate demotes it.
    p._arbiter.set_cycle(3)
    p._arbiter._memo.mark(repr(goal), st, 3)
    assert pred(step, step) is False


def test_arbiter_goal_doomed_reflects_memo():
    p = GamePlayer(character="hero")
    st = make_state()
    p._arbiter.set_cycle(0)
    assert p._arbiter.goal_doomed("SomeGoal()", st) is False
    p._arbiter._memo.mark("SomeGoal()", st, 0)
    assert p._arbiter.goal_doomed("SomeGoal()", st) is True


def test_switching_root_rearms_for_new_root():
    p = _player()
    gd = _make_planner_gd()
    skill = ReachSkillLevel(skill="weaponcrafting", level=5)
    gear = ObtainItem(code="copper_ore", quantity=10, slot=None)
    p._update_sticky_anchor(skill, make_state(skill_xp={"weaponcrafting": 75}), gd, True)
    # Different root chosen this cycle -> treated as fresh commit (armed), new baseline.
    p._update_sticky_anchor(gear, make_state(inventory={"copper_ore": 2}), gd, True)
    assert p._last_strategy_root == repr(gear)
    assert p._sticky_progress_value == 2
