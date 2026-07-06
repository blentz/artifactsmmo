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
from artifactsmmo_cli.ai.combat_picker import pick_winnable_monster_pure
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
        # Action-level: a DEFAULT fight (no drop_farm) keeps the xp gate — the
        # drop-farm bypass must never leak into plain xp-grind fights.
        fight = FightAction(monster_code="chicken", locations=frozenset({(0, 1)}))
        assert fight.is_applicable(state, gd) is False

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

    def test_every_picker_target_is_applicable(self) -> None:
        """Picker ⟷ applicability consistency: every monster that
        pick_winnable_monster_pure can return passes FightAction.is_applicable
        when transient gates are held true (full HP, 1+ free inventory slot,
        spawn location present for every monster in the catalog).

        This locks the P0-revision alignment: the picker's gates (xp>0 lower
        bound and level+2 suicide guard) are exactly the structural gates in
        is_applicable. A regression that adds a gear-level check to either
        one but not the other would be caught here."""
        # Catalog: one monster per level 1..12, spanning all levels relevant
        # to char_levels 1..10.  Winnability is held True so the picker's
        # only active filters are xp>0 and the level+2 suicide guard.
        catalog: list[tuple[str, int]] = [(f"m{lvl}", lvl) for lvl in range(1, 13)]

        checked = 0
        for char_level in range(1, 11):
            gd = GameData()
            gd._monster_level = {code: lvl for code, lvl in catalog}
            gd._monster_hp = {code: 50 for code, _ in catalog}
            gd._monster_attack = {code: {} for code, _ in catalog}
            gd._monster_resistance = {code: {} for code, _ in catalog}
            gd._monster_critical_strike = {code: 0 for code, _ in catalog}
            gd._monster_initiative = {code: 0 for code, _ in catalog}
            gd._monster_locations = {code: [(0, lvl)] for code, lvl in catalog}
            # Full HP (150/150 = 100% >> 50% threshold), empty inventory
            # (100 free slots >> MIN_FREE_SLOTS=1), correct char level.
            state = make_state(
                level=char_level, hp=150, max_hp=150,
                inventory={}, inventory_max=100,
            )
            # cl=char_level default-arg captures the loop variable per iteration.
            target = pick_winnable_monster_pure(
                char_level,
                catalog,
                is_winnable=lambda _code: True,
                xp_positive=lambda code, cl=char_level, gd=gd: gd.xp_per_kill(code, cl) > 0,
            )
            if target is None:
                continue
            locations = frozenset({(0, gd._monster_level[target])})
            fight = FightAction(monster_code=target, locations=locations)
            checked += 1
            assert fight.is_applicable(state, gd), (
                f"Picker-applicability divergence at char_level={char_level}: "
                f"picker returned {target!r} (monster_level="
                f"{gd._monster_level[target]}) but FightAction.is_applicable "
                f"returned False. Picker and is_applicable gates must stay aligned."
            )
        assert checked >= 1, (
            "property test exercised no targets — picker returned None for every level"
        )

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
        fight = FightAction(monster_code="green_slime", locations=frozenset({(0, -1)}))
        # Preconditions: xp gate passes, only the gear-level gate can block.
        assert gd.xp_per_kill("green_slime", state.level) > 0
        assert fight.is_applicable(state, gd) is True
