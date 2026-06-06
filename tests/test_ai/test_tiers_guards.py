"""Tests for the guard ladder (state-pressure interrupts + prerequisite gates)."""

from unittest.mock import patch

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.tiers.guards import (
    GUARD_ORDER,
    GuardKind,
    SelectionContext,
    _fires,
    active_guards,
)
from tests.test_ai.fixtures import make_state


def _ctx(**kw) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)


def test_hp_critical_fires_below_quarter_and_outranks_all():
    state = make_state(hp=10, max_hp=100)            # 10% < 0.25
    guards = active_guards(state, GameData(), None, _ctx())
    assert guards[0] is GuardKind.HP_CRITICAL


def test_no_guards_when_calm():
    state = make_state(hp=100, max_hp=100, inventory={}, inventory_max=20)
    assert active_guards(state, GameData(), None, _ctx(bank_accessible=True)) == []


def test_guard_order_is_ladder_order():
    state = make_state(hp=10, max_hp=100, inventory={"x": 20}, inventory_max=20, bank_items={})
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=True))
    assert guards == [g for g in GUARD_ORDER if g in guards]


def test_reach_unlock_level_fires_within_gap():
    state = make_state(level=3, hp=100, max_hp=100)
    guards = active_guards(state, GameData(), None, _ctx(bank_required_level=5))
    assert GuardKind.REACH_UNLOCK_LEVEL in guards


def test_reach_unlock_level_silent_beyond_gap():
    state = make_state(level=3, hp=100, max_hp=100)
    guards = active_guards(state, GameData(), None, _ctx(bank_required_level=20))
    assert GuardKind.REACH_UNLOCK_LEVEL not in guards


def test_deposit_full_fires_when_inventory_high_and_depositable_item():
    # inventory_max=10, inventory={"ore": 9} → 90% ≥ 80%
    # "ore" is not tasks_coin, not task item, not HP item, not a weapon
    # → select_bank_deposits returns [("ore", 9)]
    state = make_state(
        hp=100, max_hp=100,
        inventory={"ore": 9},
        inventory_max=10,
        bank_items={},
    )
    gd = GameData()
    guards = active_guards(state, gd, None, _ctx(bank_accessible=True))
    assert GuardKind.DEPOSIT_FULL in guards


def test_used_fraction_zero_when_inventory_max_zero():
    # Covers the inventory_max <= 0 branch in _used_fraction.
    # With inventory_max=0 no guard that checks fraction should fire.
    state = make_state(hp=100, max_hp=100, inventory={}, inventory_max=0)
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=True))
    assert guards == []


def test_bank_unlock_fires_when_monster_set_and_bank_not_accessible():
    # BANK_UNLOCK guard: bank_unlock_monster set, bank_accessible=False, xp == initial_xp,
    # monster_level unknown (returns 0) → fires (target_level == 0 branch).
    state = make_state(hp=100, max_hp=100, xp=0, level=1)
    guards = active_guards(
        state, GameData(), None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK in guards


def test_bank_unlock_silent_when_xp_earned():
    # BANK_UNLOCK guard: state.xp > initial_xp → does NOT fire.
    state = make_state(hp=100, max_hp=100, xp=50, level=1)
    guards = active_guards(
        state, GameData(), None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK not in guards


def test_bank_unlock_fires_when_level_meets_threshold():
    # BANK_UNLOCK: target_level returned as 5, player level=4 (>= 5-1=4) → fires.
    gd = GameData()
    gd._monster_level["goblin"] = 5
    state = make_state(hp=100, max_hp=100, xp=0, level=4)
    guards = active_guards(
        state, gd, None,
        _ctx(bank_accessible=False, bank_unlock_monster="goblin", initial_xp=0),
    )
    assert GuardKind.BANK_UNLOCK in guards


def test_deposit_full_silent_when_bank_inaccessible():
    state = make_state(hp=100, max_hp=100, inventory={"copper_ore": 9}, inventory_max=10, bank_items={})
    guards = active_guards(state, GameData(), None, _ctx(bank_accessible=False))
    assert GuardKind.DEPOSIT_FULL not in guards


def test_fires_returns_false_for_unknown_guard_kind():
    # Covers the defensive `return False` fallthrough at the end of _fires.
    # Patch GuardKind to inject a value not handled by any if-branch.
    state = make_state(hp=100, max_hp=100)
    ctx = _ctx()
    unknown = object()  # not a GuardKind member
    with patch("artifactsmmo_cli.ai.tiers.guards.GUARD_ORDER", (unknown,)):  # type: ignore[arg-type]
        result = _fires(unknown, state, GameData(), None, ctx)  # type: ignore[arg-type]
    assert result is False


def test_gear_review_in_guard_order_below_survival_above_none():
    # GEAR_REVIEW is the LAST guard (lowest-priority guard, still above all means).
    assert GUARD_ORDER[-1] is GuardKind.GEAR_REVIEW
    assert GuardKind.HP_CRITICAL in GUARD_ORDER[:GUARD_ORDER.index(GuardKind.GEAR_REVIEW)]


def test_gear_review_fires_only_when_ctx_active(make_planner_gd):
    from tests.test_ai.test_strategy_driver import _ctx as driver_ctx
    state = make_state(hp=150, max_hp=150)
    active_ctx = driver_ctx(gear_review_active=True)
    inactive_ctx = driver_ctx(gear_review_active=False)
    assert GuardKind.GEAR_REVIEW in active_guards(state, make_planner_gd, None, active_ctx)
    assert GuardKind.GEAR_REVIEW not in active_guards(state, make_planner_gd, None, inactive_ctx)
