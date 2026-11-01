"""P0 no-combat deadlock regression (2026-06-09 live repro).

At level 4 the stat-winnable monsters were chicken (L1) and yellow_slime
(L2) — both below the old picker/FightAction hard window
[max(1, 4-1), 4+2] = [3, 6] — while the only in-window monster (sheep L5:
hp 120, hit 14 vs char hp 165, hit ~5.9) was a guaranteed loss. The old
window-only `_pick_winnable_monster` returned None forever, so
`objective_step_goal(ReachCharLevel)` never produced a combat goal and the
bot never fought.

These tests lock the fixed chain against the trace state:

  1. FightAction for a below-window winnable target is applicable (the xp>0
     lower gate admits below-window monsters);
  2. objective_step_goal yields a combat goal (GrindCharacterXPGoal).

The player's windowed pick (`_pick_winnable_monster`) is gone since plan C
Task 4: the grind target is `farm_target`'s, and its picker core
(`pick_winnable_monster_pure`) went with ruling C4-b.

No mocking of the units under test: real GameData catalog stats, the real
predict_win-backed `_is_winnable`, action, and dispatch.
"""

from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.learned_drops import LearnedDrops
from artifactsmmo_cli.ai.learning.fight_seconds_model import committed_timing
from artifactsmmo_cli.ai.player import GamePlayer
from artifactsmmo_cli.ai.progression.guards import SelectionContext
from artifactsmmo_cli.ai.progression.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
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
    player._offline_timing = committed_timing()
    player._learned_drops = LearnedDrops.empty()
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

    def test_fight_action_applicable_for_fallback_target(self) -> None:
        """Picker→action consistency: the fallback target passes
        FightAction.is_applicable (xp>0 lower gate, level+2 suicide guard,
        gear pre-filter)."""
        gd = _trace_game_data()
        state = _trace_state()
        fight = FightAction(monster_code="yellow_slime",
                            locations=frozenset({(0, 2)}), learned_drops=LearnedDrops.empty())
        assert gd.xp_per_kill("yellow_slime", state.level) > 0
        assert fight.is_applicable(state, gd) is True

    def test_objective_step_goal_yields_combat_goal(self) -> None:
        """The full dead chain revived: ReachCharLevel + a below-window
        winnable target dispatches to GrindCharacterXPGoal instead of the
        old `combat_monster is None → return None` dead end. (The target is
        the grind target `farm_target` names; the player's windowed pick that
        found it here was deleted in plan C Task 4.)"""
        gd = _trace_game_data()
        state = _trace_state()
        target = "yellow_slime"
        assert _player(gd, state)._is_winnable(target) is True
        ctx = SelectionContext(
            bank_accessible=False, bank_required_level=10,
            bank_unlock_monster=None, initial_xp=state.xp,
            task_exchange_min_coins=0, combat_monster=target,
        )
        goal = objective_step_goal(ReachCharLevel(level=6), state, gd, ctx)
        assert isinstance(goal, GrindCharacterXPGoal)
        assert goal._target_monster == "yellow_slime"

    def test_zero_xp_fight_is_not_applicable(self) -> None:
        """A winnable monster whose kill grants zero XP (char out-levels it
        by 11+) is no XP fight — fighting it serves no leveling objective and
        FightAction's xp gate rejects it.

        The fixture was level 11 against a level-1 chicken — diff exactly 10,
        which the store replay shows pays in full (372 observed fights). It
        was asserting the off-by-one, not the exclusion; level 12 puts it back
        inside the zero band."""
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
            level=12, hp=165, max_hp=165,
            attack={"air": 5}, dmg=18, initiative=10,
            inventory={}, inventory_max=100,
            equipment=dict(base.equipment),
        )
        player = _player(gd, state)
        assert player._is_winnable("chicken") is True
        assert gd.xp_per_kill("chicken", 11) > 0
        assert gd.xp_per_kill("chicken", 12) == 0
        # Action-level: a DEFAULT fight (no drop_farm) keeps the xp gate — the
        # drop-farm bypass must never leak into plain xp-grind fights.
        fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}), learned_drops=LearnedDrops.empty())
        assert fight.is_applicable(state, gd) is False

    def test_fight_applicable_when_winnable_despite_low_gear_level(self) -> None:
        """Regression: a level-3 char in all level-1 gear must be able to fight a
        winnable level-4 monster (green_slime). The old `best_eq >= monster_level-1`
        gate rejected it, deadlocking GrindCharacterXP -> plan_len=0."""
        gd = GameData()
        gd._monster_level = {"green_slime": 4}
        gd._monster_hp = {"green_slime": 100}
        gd._monster_attack = {"green_slime": {"water": 5}}
        gd._monster_resistance = {"green_slime": {}}
        gd._monster_critical_strike = {"green_slime": 0}
        gd._monster_initiative = {"green_slime": 0}
        gd._monster_locations = {"green_slime": [(0, -1)]}
        gd._item_stats = {
            "copper_dagger": ItemStats(
                code="copper_dagger", level=1, type_="weapon", attack={"air": 3},
            ),
        }
        base = make_state()
        equipment = dict(base.equipment)
        equipment["weapon_slot"] = "copper_dagger"
        state = make_state(
            level=3, hp=160, max_hp=160,
            inventory={}, inventory_max=100,
            equipment=equipment,
        )
        fight = FightAction(monster_code="green_slime", locations=frozenset({(0, -1)}),
                            learned_drops=LearnedDrops.empty())
        # Preconditions: xp gate passes, only the gear-level gate can block.
        assert gd.xp_per_kill("green_slime", state.level) > 0
        assert fight.is_applicable(state, gd) is True
