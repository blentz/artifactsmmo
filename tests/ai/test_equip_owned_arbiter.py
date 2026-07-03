"""Arbiter wiring: `_build_candidates` materializes an `EquipOwnedGoal` in the
COLLECT band (outranking the step/grind tier) when owned positive-Rank gear can
fill an empty slot.

Locks the band placement the mutation gate perturbs (mutant (c): flipping the
`band=BAND_COLLECT` literal is killed by `test_equip_owned_candidate_in_collect_band`).
"""

from artifactsmmo_cli.ai.arbiter_select import BAND_COLLECT, BAND_STEP
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.equip_owned_gear import EquipOwnedGoal
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


def _state() -> WorldState:
    return WorldState(
        character="c", level=10, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills={}, x=0, y=0, inventory={"novice_guide": 1}, inventory_max=20,
        equipment=dict(_ALL_SLOTS), cooldown_expires=None, task_code=None,
        task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                  hp_bonus=30, wisdom=10, prospecting=5),
    }
    return gd


def _build(state: WorldState, gd: GameData) -> list:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    return arbiter._build_candidates(
        guard_kinds=[], collect_kinds=[], discretionary_kinds=[],
        step_goal=_StubStep(), fallback_steps=[], fallback_roots=[],
        state=state, game_data=gd, ctx=_ctx(),
    )


def test_equip_owned_candidate_in_collect_band() -> None:
    cands = _build(_state(), _gd())
    equips = [c for c in cands if isinstance(c.goal, EquipOwnedGoal)]
    assert len(equips) == 1, [c.repr_ for c in cands]
    equip = equips[0]
    assert equip.goal.fills == {"artifact1_slot": "novice_guide"}
    # Band placement (mutant (c)): must be COLLECT, strictly above the step tier.
    assert equip.band == BAND_COLLECT
    assert BAND_COLLECT < BAND_STEP


def test_equip_owned_precedes_step_goal() -> None:
    cands = _build(_state(), _gd())
    reprs = [c.repr_ for c in cands]
    equip_idx = next(i for i, c in enumerate(cands) if isinstance(c.goal, EquipOwnedGoal))
    step_idx = reprs.index("GrindCharacterXP(green_slime)")
    assert equip_idx < step_idx


def test_no_candidate_when_no_ownable_fill() -> None:
    # Empty inventory → no owned gear to equip → no EquipOwnedGoal candidate,
    # so the wiring is inert for the overwhelming majority of states.
    state = _state()
    empty = WorldState(**{**state.__dict__, "inventory": {}})
    cands = _build(empty, _gd())
    assert not any(isinstance(c.goal, EquipOwnedGoal) for c in cands)
