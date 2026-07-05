"""Arbiter wiring: `_build_candidates` materializes a `WithdrawToolsGoal` in the
COLLECT band when the bank holds a gathering tool strictly better than anything
owned, so the tool is ferried into the bag where the proven gather re-arm
(GATHER_LOADOUT_PENALTY + OptimizeLoadout(Gather)) can equip it.

Regression: trace 2026-07-05 cycles ~600-902 — Robby mined copper_rocks 261/300
actions with copper_dagger equipped while copper_pickaxe sat in the bank;
pick_loadout scans only inventory+equipped, so no path ever withdrew the tool.
"""

from artifactsmmo_cli.ai.arbiter_select import BAND_COLLECT, BAND_STEP
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.withdraw_tools import WithdrawToolsGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


class _StubStep(Goal):
    """Minimal step-tier goal with a stable repr (a tagged candidate id)."""

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


def _state(bank_items=None, equipment=None) -> WorldState:
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="c", level=10, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory={}, inventory_max=20,
        equipment=eq, cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=bank_items, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "copper_pickaxe": ItemStats(code="copper_pickaxe", level=1, type_="weapon",
                                    attack={"earth": 5}, skill_effects={"mining": -10}),
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   attack={"air": 6}, critical_strike=35),
    }
    gd.world.bank_tile = (4, 1)
    return gd


def _build(state: WorldState, gd: GameData, ctx=None) -> list:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    return arbiter._build_candidates(
        guard_kinds=[], collect_kinds=[], discretionary_kinds=[],
        step_goal=_StubStep(), fallback_steps=[], fallback_roots=[],
        state=state, game_data=gd, ctx=ctx or _ctx(),
    )


def test_withdraw_tools_candidate_in_collect_band() -> None:
    state = _state(bank_items={"copper_pickaxe": 1},
                   equipment={"weapon_slot": "copper_dagger"})
    cands = _build(state, _gd())
    withdraws = [c for c in cands if isinstance(c.goal, WithdrawToolsGoal)]
    assert len(withdraws) == 1, [c.repr_ for c in cands]
    wt = withdraws[0]
    assert wt.goal.fills == {"mining": "copper_pickaxe"}
    assert wt.goal.bank_location == (4, 1)
    assert wt.band == BAND_COLLECT
    assert BAND_COLLECT < BAND_STEP


def test_withdraw_tools_precedes_step_goal() -> None:
    state = _state(bank_items={"copper_pickaxe": 1})
    cands = _build(state, _gd())
    wt_idx = next(i for i, c in enumerate(cands) if isinstance(c.goal, WithdrawToolsGoal))
    step_idx = [c.repr_ for c in cands].index("GrindCharacterXP(green_slime)")
    assert wt_idx < step_idx


def test_no_candidate_when_bank_unknown() -> None:
    cands = _build(_state(bank_items=None), _gd())
    assert not any(isinstance(c.goal, WithdrawToolsGoal) for c in cands)


def test_no_candidate_when_tool_already_owned() -> None:
    state = _state(bank_items={"copper_pickaxe": 1},
                   equipment={"weapon_slot": "copper_pickaxe"})
    cands = _build(state, _gd())
    assert not any(isinstance(c.goal, WithdrawToolsGoal) for c in cands)


def test_no_candidate_when_bank_inaccessible() -> None:
    state = _state(bank_items={"copper_pickaxe": 1})
    cands = _build(state, _gd(), ctx=_ctx(bank_accessible=False))
    assert not any(isinstance(c.goal, WithdrawToolsGoal) for c in cands)


def test_no_candidate_when_map_has_no_bank() -> None:
    gd = _gd()
    gd.world.bank_tile = None
    cands = _build(_state(bank_items={"copper_pickaxe": 1}), gd)
    assert not any(isinstance(c.goal, WithdrawToolsGoal) for c in cands)
