"""P0 no-combat deadlock regression (2026-06-09 live repro).

At level 4 the stat-winnable monsters were chicken (L1) and yellow_slime
(L2) — both below the old picker/FightAction hard window
[max(1, 4-1), 4+2] = [3, 6] — while the only in-window monster (sheep L5:
hp 120, hit 14 vs char hp 165, hit ~5.9) was a guaranteed loss. The old
window-only `_pick_winnable_monster` returned None forever, so
`objective_step_goal(ReachCharLevel)` never produced a combat goal and the
bot never fought.

These tests lock the fixed chain end-to-end against the trace state:

  1. picker returns yellow_slime (highest-level winnable, via the xp>0
     liveness fallback);
  2. FightAction for that target is applicable (the xp>0 lower gate
     admits below-window monsters);
  3. objective_step_goal yields a combat goal (GrindCharacterXPGoal).

No mocking of the units under test: real GameData catalog stats, the real
predict_win-backed `_is_winnable`, the real picker, action, and dispatch.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state


def _trace_game_data() -> GameData:
    """The level-4 trace catalog: chicken/yellow_slime winnable below the
    window, sheep (L5, in window) a stat-certain loss."""
    gd = GameData()
    gd._monster_level = {"chicken": 1, "yellow_slime": 2, "sheep": 5}
    gd._monster_hp = {"chicken": 60, "yellow_slime": 70, "sheep": 120}
    gd._monster_attack = {
        "chicken": {"air": 4},
        "yellow_slime": {"air": 5},
        "sheep": {"air": 14},
    }
    gd._monster_resistance = {"chicken": {}, "yellow_slime": {}, "sheep": {}}
    gd._monster_critical_strike = {"chicken": 0, "yellow_slime": 0, "sheep": 0}
    gd._monster_initiative = {"chicken": 0, "yellow_slime": 0, "sheep": 0}
    gd._monster_locations = {
        "chicken": [(0, 1)], "yellow_slime": [(0, 2)], "sheep": [(0, 3)],
    }
    gd._item_stats = {
        "wooden_stick": ItemStats(
            code="wooden_stick", level=1, type_="weapon", attack={"air": 5},
        ),
    }
    return gd


def _trace_state() -> WorldState:
    """Robby at level 4: hp 165, hit ~5.9 (attack 5 + small dmg bonus)."""
    base = make_state()
    equipment = dict(base.equipment)
    equipment["weapon_slot"] = "wooden_stick"
    return make_state(
        level=4, hp=165, max_hp=165,
        attack={"air": 5}, dmg=18, initiative=10,
        inventory={}, inventory_max=100,
        equipment=equipment,
    )


def _player(gd: GameData, state: WorldState) -> GamePlayer:
    player = GamePlayer(character="Robby")
    player.game_data = gd
    player.state = state
    return player


class TestNoCombatDeadlock:
    def test_trace_winnability_assumptions_hold(self) -> None:
        """Sanity-pin the fixture against the investigation: chicken and
        yellow_slime are stat-winnable, sheep is not."""
        gd = _trace_game_data()
        player = _player(gd, _trace_state())
        assert player._is_winnable("chicken") is True
        assert player._is_winnable("yellow_slime") is True
        assert player._is_winnable("sheep") is False

    def test_picker_falls_back_to_highest_winnable(self) -> None:
        """The window [3,6] holds no winnable monster (sheep loses); the
        liveness fallback returns yellow_slime — the highest-level winnable
        XP-positive monster. The old picker returned None forever here."""
        gd = _trace_game_data()
        player = _player(gd, _trace_state())
        assert player._pick_winnable_monster() == "yellow_slime"

    def test_fight_action_applicable_for_fallback_target(self) -> None:
        """Picker→action consistency: the fallback target passes
        FightAction.is_applicable (xp>0 lower gate, level+2 suicide guard,
        gear pre-filter)."""
        gd = _trace_game_data()
        state = _trace_state()
        fight = FightAction(monster_code="yellow_slime",
                            locations=frozenset({(0, 2)}))
        assert gd.xp_per_kill("yellow_slime", state.level) > 0
        assert fight.is_applicable(state, gd) is True

    def test_objective_step_goal_yields_combat_goal(self) -> None:
        """The full dead chain revived: ReachCharLevel + the picker's
        fallback target dispatches to GrindCharacterXPGoal instead of the
        old `combat_monster is None → return None` dead end."""
        gd = _trace_game_data()
        state = _trace_state()
        player = _player(gd, state)
        target = player._pick_winnable_monster()
        assert target is not None
        ctx = SelectionContext(
            bank_accessible=False, bank_required_level=10,
            bank_unlock_monster=None, initial_xp=state.xp,
            task_exchange_min_coins=0, combat_monster=target,
        )
        goal = objective_step_goal(ReachCharLevel(level=6), state, gd, ctx)
        assert isinstance(goal, GrindCharacterXPGoal)
        assert goal._target_monster == "yellow_slime"

    def test_fallback_skips_overleveled_monster(self) -> None:
        """Picker→action consistency: a winnable monster ABOVE level+2 is
        never a fallback target (FightAction's suicide guard would reject
        it and re-create the dead-target → empty-plan cascade)."""
        gd = _trace_game_data()
        gd._monster_level = {"chicken": 1, "weak_giant": 9}
        gd._monster_hp = {"chicken": 60, "weak_giant": 10}
        gd._monster_attack = {"chicken": {"air": 4}, "weak_giant": {"air": 1}}
        gd._monster_resistance = {"chicken": {}, "weak_giant": {}}
        gd._monster_critical_strike = {"chicken": 0, "weak_giant": 0}
        gd._monster_initiative = {"chicken": 0, "weak_giant": 0}
        gd._monster_locations = {"chicken": [(0, 1)], "weak_giant": [(0, 9)]}
        player = _player(gd, _trace_state())
        assert player._is_winnable("weak_giant") is True  # stats say beatable
        assert player._pick_winnable_monster() == "chicken"

    def test_fallback_requires_positive_xp(self) -> None:
        """A winnable monster whose kill grants zero XP (char out-levels it
        by 10+) is not a fallback target — fighting it serves no leveling
        objective and FightAction's xp gate would reject it."""
        gd = GameData()
        gd._monster_level = {"chicken": 1}
        gd._monster_hp = {"chicken": 60}
        gd._monster_attack = {"chicken": {"air": 4}}
        gd._monster_resistance = {"chicken": {}}
        gd._monster_critical_strike = {"chicken": 0}
        gd._monster_initiative = {"chicken": 0}
        gd._monster_locations = {"chicken": [(0, 1)]}
        base = _trace_state()
        state = make_state(
            level=11, hp=165, max_hp=165,
            attack={"air": 5}, dmg=18, initiative=10,
            inventory={}, inventory_max=100,
            equipment=dict(base.equipment),
        )
        player = _player(gd, state)
        assert player._is_winnable("chicken") is True
        assert gd.xp_per_kill("chicken", 11) == 0
        assert player._pick_winnable_monster() is None

    def test_true_deadlock_still_returns_none(self) -> None:
        """When nothing winnable grants XP the picker honestly returns None
        (gear progression is the only path). Sheep-only catalog: in-window
        but a stat-certain loss."""
        gd = GameData()
        gd._monster_level = {"sheep": 5}
        gd._monster_hp = {"sheep": 120}
        gd._monster_attack = {"sheep": {"air": 14}}
        gd._monster_resistance = {"sheep": {}}
        gd._monster_critical_strike = {"sheep": 0}
        gd._monster_initiative = {"sheep": 0}
        gd._monster_locations = {"sheep": [(0, 3)]}
        player = _player(gd, _trace_state())
        assert player._pick_winnable_monster() is None
