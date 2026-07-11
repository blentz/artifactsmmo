"""Hoard-scaled recycle urgency: every 5 surplus copies of the piling item add
1x urgency (40-ish hoard = 8x), and past the hoist threshold RecycleSurplus is
materialized in the COLLECT band so it actually outranks the grind instead of
waiting in the starved discretionary tier.
"""

from artifactsmmo_cli.ai.arbiter_select import BAND_COLLECT, BAND_STEP
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.recycle_surplus import (
    RECYCLE_SURPLUS_VALUE,
    RecycleSurplusGoal,
)
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.recycle_surplus import recycle_urgency, recycle_urgency_pure
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.tiers.means import MeansKind
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


# ── pure core ────────────────────────────────────────────────────────────────

def test_urgency_baseline_below_five() -> None:
    assert recycle_urgency_pure(0) == 1
    assert recycle_urgency_pure(1) == 1
    assert recycle_urgency_pure(4) == 1
    assert recycle_urgency_pure(5) == 1


def test_urgency_steps_every_five() -> None:
    assert recycle_urgency_pure(6) == 2
    assert recycle_urgency_pure(10) == 2
    assert recycle_urgency_pure(11) == 3


def test_urgency_forty_hoard_is_eight_x() -> None:
    """The spec example: a ~40-copy hoard is 8x more urgent than <5."""
    assert recycle_urgency_pure(40) == 8
    assert recycle_urgency_pure(39) == 8
    assert recycle_urgency_pure(41) == 9


def test_urgency_of_surplus_map_uses_largest_pile() -> None:
    assert recycle_urgency({}) == 1
    assert recycle_urgency({"copper_helmet": 39, "copper_ring": 1}) == 8


# ── goal value scales with urgency ───────────────────────────────────────────

def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {"copper_helmet": {"copper_bar": 6}}
    gd._workshop_locations = {"gearcrafting": (2, 1)}
    return gd


def _state(helmets: int, inventory_max: int = 118) -> WorldState:
    eq = dict(_ALL_SLOTS)
    eq["helmet_slot"] = "copper_helmet"
    return WorldState(
        character="c", level=10, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={"gearcrafting": 8}, x=0, y=0,
        inventory={"copper_helmet": helmets}, inventory_max=inventory_max,
        # A realistic 20-slot bag: the single copper_helmet stack is NOT
        # slot-full, so these quantity-driven recycle-urgency cases exercise
        # QUANTITY pressure (the slot-aware _used_fraction split, 2026-07-11,
        # would otherwise read a 1-slot bag as 100% full and suppress the hoist).
        inventory_slots_max=20,
        equipment=eq, cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def test_goal_value_scales_with_hoard() -> None:
    gd = _gd()
    goal = RecycleSurplusGoal(game_data=gd, protected_codes=frozenset())
    # 40 held, cap 1 -> surplus 39 -> urgency 8.
    assert goal.value(_state(40), gd) == 8 * RECYCLE_SURPLUS_VALUE
    # 4 held -> surplus 3 -> baseline.
    assert goal.value(_state(4), gd) == RECYCLE_SURPLUS_VALUE
    # No surplus -> satisfied -> 0.
    assert goal.value(_state(1), gd) == 0.0


# ── arbiter hoist ────────────────────────────────────────────────────────────

class _StubStep(Goal):
    def __repr__(self) -> str:
        return "GrindCharacterXP(green_slime)"

    def is_satisfied(self, state: WorldState) -> bool:  # pragma: no cover
        return False

    def value(self, *args: object, **kwargs: object) -> float:  # pragma: no cover
        return 0.0

    def desired_state(self, *args: object, **kwargs: object) -> dict[str, object]:  # pragma: no cover
        return {}


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _build(state: WorldState, gd: GameData, discretionary=()) -> list:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    return arbiter._build_candidates(
        guard_kinds=[], collect_kinds=[], discretionary_kinds=list(discretionary),
        step_goal=_StubStep(), fallback_steps=[], fallback_roots=[],
        state=state, game_data=gd, ctx=_ctx(),
    )


def test_urgent_hoard_hoists_recycle_into_collect_band() -> None:
    cands = _build(_state(40), _gd())
    recycles = [c for c in cands if isinstance(c.goal, RecycleSurplusGoal)]
    assert len(recycles) == 1, [c.repr_ for c in cands]
    assert recycles[0].band == BAND_COLLECT
    assert BAND_COLLECT < BAND_STEP
    step_idx = [c.repr_ for c in cands].index("GrindCharacterXP(green_slime)")
    assert cands.index(recycles[0]) < step_idx


def test_small_surplus_is_not_hoisted() -> None:
    # 6 held -> surplus 5 -> urgency 1 -> stays discretionary-only.
    cands = _build(_state(6), _gd())
    assert not any(isinstance(c.goal, RecycleSurplusGoal) for c in cands)


def test_hoist_fires_at_urgency_two_exactly() -> None:
    # 7 held -> surplus 6 -> urgency 2 (the threshold).
    cands = _build(_state(7), _gd())
    recycles = [c for c in cands if isinstance(c.goal, RecycleSurplusGoal)]
    assert len(recycles) == 1 and recycles[0].band == BAND_COLLECT


def test_hoist_suppressed_under_inventory_pressure() -> None:
    # Recycling mints materials into the bag; under pressure the deposit /
    # discard guards own the bag, so the hoist must stand down.
    state = _state(40, inventory_max=45)  # 40/45 > SELL_PRESSURE_FRACTION
    cands = _build(state, _gd())
    assert not any(isinstance(c.goal, RecycleSurplusGoal) for c in cands)


def test_hoisted_recycle_is_deduped_from_discretionary() -> None:
    # When hoisted, the discretionary RECYCLE_SURPLUS means must not add a
    # second "RecycleSurplus" candidate (duplicate reprs confuse stickiness).
    cands = _build(_state(40), _gd(), discretionary=[MeansKind.RECYCLE_SURPLUS])
    recycles = [c for c in cands if isinstance(c.goal, RecycleSurplusGoal)]
    assert len(recycles) == 1
    assert recycles[0].band == BAND_COLLECT


def test_small_surplus_keeps_discretionary_recycle() -> None:
    # Not hoisted -> the normal discretionary means candidate stays.
    cands = _build(_state(6), _gd(), discretionary=[MeansKind.RECYCLE_SURPLUS])
    recycles = [c for c in cands if isinstance(c.goal, RecycleSurplusGoal)]
    assert len(recycles) == 1
    assert recycles[0].band != BAND_COLLECT


def test_goal_with_snapshot_satisfied_by_partial_progress() -> None:
    """All-or-nothing satisfaction dead-ends the planner when the hoard cannot
    fit one bag-limited recycle (live 2026-07-05: 39 surplus, space-capped
    Recycle x14, plan_len=0). With the initial-total snapshot, ANY reduction
    satisfies — one batch per cycle, converging across cycles."""
    gd = _gd()
    goal = RecycleSurplusGoal(game_data=gd, protected_codes=frozenset(),
                              initial_total=39)
    assert not goal.is_satisfied(_state(40))       # 39 surplus: no progress yet
    assert goal.is_satisfied(_state(26))           # 25 surplus < 39: progress
    assert goal.is_satisfied(_state(1))            # cleared entirely


def test_hoisted_goal_carries_snapshot_and_is_plannable_one_batch() -> None:
    from artifactsmmo_cli.ai.actions.recycle import RecycleAction
    cands = _build(_state(40, inventory_max=50), _gd())
    rs = next(c.goal for c in cands if isinstance(c.goal, RecycleSurplusGoal))
    actions = rs.relevant_actions([], _state(40, inventory_max=50), _gd())
    assert actions and isinstance(actions[0], RecycleAction)
    post = actions[0].apply(_state(40, inventory_max=50), _gd())
    assert rs.is_satisfied(post)  # one space-capped batch already satisfies
