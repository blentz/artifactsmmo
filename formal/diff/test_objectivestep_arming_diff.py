"""Task 5 — SELECT-side differential for the `perceptionRefresh` arming.

`Formal/Liveness/PerceptionRefresh.lean` arms the two objective-step Bools below
the level cap: `objectiveStepFires := true`, `objectiveStepIsFight := true`. That
arming is the in-model image of production committing the `ReachCharLevel`
meta-goal whose plan LEADS WITH A FIGHT. This differential PINS that image to the
real `objective_step_goal` (`src/artifactsmmo_cli/ai/strategy_driver.py:583-617`,
the `ReachCharLevel` branch), so the Lean `objectiveStepIsFight = true` arming is
backed by production, not asserted.

## The production branch (strategy_driver.py:583-617)

For `step = ReachCharLevel(target)`:
  * `combat_monster is None`            → return `None`         (NO fight).
  * `bootstrap_gap = target - level`; if `bootstrap_gap > 4` AND an items task is
    active (`task_type == "items" and task_code and task_total > 0 and
    task_progress < task_total`)        → return `None`         (long-haul defer).
  * else                                → `GrindCharacterXPGoal` (a FIGHT).

So production yields a fight IFF a combat target is set AND we are NOT in the
long-haul items-task defer case. The Lean kernel half
(`WinnableGrounded.winnableAcrossBand_grounded` →
`GearTierLeveling.combatObjective_live_below_fifty`) PROVES that below 50 a
winnable XP-positive combat target EXISTS. So the faithful binding is:

    produced_fight  ==  (combat_target_exists AND level < 50 AND NOT defer_case)

The Lean arming is `objectiveStepIsFight = true` exactly on that condition's
in-model image (target existence below 50). The `defer_case` is modelled here so
the binding is FAITHFUL, not flattering — the test includes scenarios hitting
BOTH the fire path and the defer path and asserts production matches in each.

## Residual (honest framing)

This differential pins PRODUCTION's `ReachCharLevel` → fight behaviour (the
arming's production half). The kernel half (a winnable combat target exists below
50) is `WinnableGrounded.winnableAcrossBand_grounded`. Neither is rigged: the
production side reads the real `objective_step_goal`, and the defer branch is
encoded into the expected value, so a scenario where production defers (no fight)
must see `lean_armed == False` too.

Template: `formal/diff/test_ladder_fires_diff.py`
(`_production_answers`/`_lean_answers`, per-row agreement).
"""
from __future__ import annotations

import dataclasses

from hypothesis import given, settings, strategies as st

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.goals.grind_character_xp import GrindCharacterXPGoal
from artifactsmmo_cli.ai.strategy_driver import objective_step_goal
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.meta_goal import ReachCharLevel
from artifactsmmo_cli.ai.world_state import WorldState

COMBAT_MONSTER = "chicken"


@dataclasses.dataclass(frozen=True)
class Scenario:
    level: int
    target_level: int           # ReachCharLevel(target_level)
    combat_target_exists: bool   # ctx.combat_monster set (winnable target found)
    # Items-task lifecycle (the long-haul defer condition's inputs).
    task_type: str | None        # "items" | "monsters" | None
    task_code: str | None
    task_progress: int
    task_total: int

    @property
    def bootstrap_gap(self) -> int:
        return self.target_level - self.level

    @property
    def items_task_active(self) -> bool:
        return (self.task_type == "items" and bool(self.task_code)
                and self.task_total > 0 and self.task_progress < self.task_total)

    @property
    def defer_case(self) -> bool:
        """The long-haul items-task stand-down (strategy_driver.py:611-614)."""
        return self.bootstrap_gap > 4 and self.items_task_active

    @property
    def lean_armed(self) -> bool:
        """The Lean `objectiveStepIsFight = true` arming condition (faithful):
        below 50 a winnable target exists AND production does not defer."""
        return (self.level < 50 and self.combat_target_exists
                and not self.defer_case)


def _make_game_data() -> GameData:
    gd = GameData()
    gd._monster_locations = {}
    gd._monster_level = {COMBAT_MONSTER: 1}
    gd._monster_hp = {}
    gd._monster_attack = {}
    gd._monster_resistance = {}
    gd._monster_critical_strike = {}
    gd._monster_initiative = {}
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_locations = {}
    gd._resource_skill = {}
    gd._resource_drops = {}
    gd._workshop_locations = {}
    gd._npc_stock = {}
    gd._npc_sell_prices = {}
    gd._npc_locations = {}
    gd._bank_capacity = 0
    gd._next_expansion_cost = 0
    return gd


def _make_world(scn: Scenario) -> WorldState:
    return WorldState(
        character="diff", level=scn.level, xp=0, max_xp=999999,
        hp=100, max_hp=100, gold=0, skills={}, x=0, y=0,
        inventory={}, inventory_max=40, inventory_slots_max=40,
        equipment={}, cooldown_expires=None,
        bank_items=None, bank_gold=None, pending_items=None,
        task_code=scn.task_code, task_type=scn.task_type,
        task_progress=scn.task_progress, task_total=scn.task_total,
    )


def _make_ctx(scn: Scenario) -> SelectionContext:
    return SelectionContext(
        bank_accessible=False, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=5,
        combat_monster=COMBAT_MONSTER if scn.combat_target_exists else None,
        target_gear=frozenset(), target_tools=frozenset(),
        gear_review_active=False,
    )


def _production_answers(scn: Scenario) -> bool:
    """Run the REAL `objective_step_goal` on a `ReachCharLevel` step and return
    whether it yielded a FIGHT (GrindCharacterXPGoal)."""
    gd = _make_game_data()
    w = _make_world(scn)
    ctx = _make_ctx(scn)
    goal = objective_step_goal(ReachCharLevel(scn.target_level), w, gd, ctx)
    return isinstance(goal, GrindCharacterXPGoal)


@st.composite
def _scenario(draw) -> Scenario:
    level = draw(st.integers(min_value=1, max_value=49))
    # Targets that hit BOTH the small-gap fire path (gap <= 4) and the long-haul
    # defer path (gap > 4).
    target_level = draw(st.integers(min_value=level, max_value=50))
    task_type = draw(st.sampled_from(["items", "monsters", None]))
    has_code = draw(st.booleans())
    task_total = draw(st.integers(min_value=0, max_value=10))
    task_progress = draw(st.integers(min_value=0, max_value=task_total))
    return Scenario(
        level=level,
        target_level=target_level,
        combat_target_exists=draw(st.booleans()),
        task_type=task_type,
        task_code="t_items" if has_code else None,
        task_progress=task_progress,
        task_total=task_total,
    )


@settings(max_examples=400)
@given(scn=_scenario())
def test_objectivestep_arming_matches_production(scn: Scenario) -> None:
    """Production `objective_step_goal(ReachCharLevel)` yields a FIGHT exactly
    when the Lean arming condition holds (winnable target exists, below 50, not
    the long-haul items-task defer case)."""
    produced_fight = _production_answers(scn)
    assert produced_fight == scn.lean_armed, (
        f"ARMING DIVERGENCE: production_fight={produced_fight} "
        f"lean_armed={scn.lean_armed}\n  scenario={scn}"
    )


# ---------------------------------------------------------------------------
# Boundary witnesses — pin BOTH the fire path and the defer path explicitly, so
# the binding is non-vacuous on the defer branch (not just the random sweep).
# ---------------------------------------------------------------------------


def _base_scn(**overrides) -> Scenario:
    defaults: dict[str, object] = dict(
        level=5, target_level=7, combat_target_exists=True,
        task_type=None, task_code=None, task_progress=0, task_total=0,
    )
    defaults.update(overrides)
    return Scenario(**defaults)  # type: ignore[arg-type]


def _assert(scn: Scenario) -> None:
    assert _production_answers(scn) == scn.lean_armed, scn


def test_fire_small_gap_no_task() -> None:
    # gap 2 (<=4), target set, no task → production FIGHTS, lean armed.
    scn = _base_scn(level=5, target_level=7)
    assert _production_answers(scn) is True
    _assert(scn)


def test_fire_small_gap_items_task_active() -> None:
    # gap 2 (<=4) with an active items task → bootstrap path STILL fights
    # (defer only triggers at gap > 4).
    scn = _base_scn(level=5, target_level=7, task_type="items",
                    task_code="t_items", task_progress=1, task_total=5)
    assert scn.defer_case is False
    assert _production_answers(scn) is True
    _assert(scn)


def test_fire_large_gap_items_task_done() -> None:
    # gap 10 (>4) but the items task is COMPLETE (progress==total) → not active
    # → no defer → production FIGHTS.
    scn = _base_scn(level=5, target_level=15, task_type="items",
                    task_code="t_items", task_progress=5, task_total=5)
    assert scn.defer_case is False
    assert _production_answers(scn) is True
    _assert(scn)


def test_fire_large_gap_monsters_task() -> None:
    # gap 10 (>4) with an active MONSTERS task (not items) → no defer → FIGHTS.
    scn = _base_scn(level=5, target_level=15, task_type="monsters",
                    task_code="t_mon", task_progress=1, task_total=5)
    assert scn.defer_case is False
    assert _production_answers(scn) is True
    _assert(scn)


def test_defer_large_gap_items_task_active() -> None:
    # gap 10 (>4) AND an active items task → long-haul DEFER → production
    # returns None (no fight), lean NOT armed.
    scn = _base_scn(level=5, target_level=15, task_type="items",
                    task_code="t_items", task_progress=1, task_total=5)
    assert scn.defer_case is True
    assert _production_answers(scn) is False
    _assert(scn)


def test_defer_boundary_gap_five() -> None:
    # gap 5 is the first gap that DEFERS (> 4 is strict). gap 4 does not.
    defer = _base_scn(level=5, target_level=10, task_type="items",
                      task_code="t_items", task_progress=1, task_total=5)
    assert defer.bootstrap_gap == 5 and defer.defer_case is True
    assert _production_answers(defer) is False
    _assert(defer)
    fire = _base_scn(level=5, target_level=9, task_type="items",
                     task_code="t_items", task_progress=1, task_total=5)
    assert fire.bootstrap_gap == 4 and fire.defer_case is False
    assert _production_answers(fire) is True
    _assert(fire)


def test_no_combat_target() -> None:
    # combat_monster is None → production returns None regardless of gap/task.
    scn = _base_scn(level=5, target_level=7, combat_target_exists=False)
    assert _production_answers(scn) is False
    _assert(scn)
