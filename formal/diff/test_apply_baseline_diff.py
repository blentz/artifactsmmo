"""Differential test for the **ApplyBaseline** contract (REAL BUG #5).

Property under test (Lean-proved): every `Action.apply` returns a `WorldState s'`
whose 8 stat-baseline fields are pointwise equal to `s`'s. The 8 fields are
the server-snapshot stats populated by `WorldState.from_character_schema`:

    attack, dmg, dmg_elements, resistance, critical_strike, initiative,
    wisdom, skill_xp

Pre-fix, 21+ of the 26 concrete Action.apply methods constructed a NEW
`WorldState(field=…, …)` listing only the fields they mutate, silently dropping
these 8 baseline fields. Probe-verified for Move and Equip. The refactor uses
`dataclasses.replace(state, <only-the-fields-this-action-mutates>)` which is
structurally guaranteed to preserve the rest.

This test:
* Hypothesis-generates a `WorldState` with NON-ZERO baseline fields.
* For every concrete Action subclass under `src/artifactsmmo_cli/ai/actions/`,
  asserts `preserves_baseline(state, action.apply(state, gd))` on real Python.
* Pins the probe-verified regression cases for Move and Equip (the user's
  explicit witnesses).
"""
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from typing import Any

from hypothesis import given, settings
from hypothesis import strategies as st

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.deposit_gold import DepositGoldAction
from artifactsmmo_cli.ai.actions.equip import EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.movement import MoveAction
from artifactsmmo_cli.ai.actions.movement_semantic import MoveTo
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.world_state import WorldState

BASELINE_FIELDS: tuple[str, ...] = (
    "attack", "dmg", "dmg_elements", "resistance",
    "critical_strike", "initiative", "wisdom", "skill_xp",
)


def _baseline(s: WorldState) -> dict[str, Any]:
    return {f: getattr(s, f) for f in BASELINE_FIELDS}


def _assert_preserved(before: WorldState, after: WorldState) -> None:
    """Assert all 8 baseline fields preserved (pointwise equality)."""
    for f in BASELINE_FIELDS:
        assert getattr(before, f) == getattr(after, f), (
            f"baseline field {f!r} silently dropped: "
            f"before={getattr(before, f)!r} after={getattr(after, f)!r}"
        )


def _make_state(
    *, x: int = 0, y: int = 0, hp: int = 100, max_hp: int = 100,
    gold: int = 100, inventory: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
    task_code: str | None = None, task_type: str | None = None,
    task_progress: int = 0, task_total: int = 0,
    bank_items: dict[str, int] | None = None, bank_gold: int | None = None,
    pending_items: tuple[tuple[str, str], ...] | None = None,
    # baseline fields — defaults to NON-ZERO to make preservation non-vacuous
    attack: dict[str, int] | None = None,
    dmg: int = 15,
    dmg_elements: dict[str, int] | None = None,
    resistance: dict[str, int] | None = None,
    critical_strike: int = 10,
    initiative: int = 5,
    wisdom: int = 12,
    skill_xp: dict[str, int] | None = None,
) -> WorldState:
    slots = ["weapon_slot", "rune_slot", "shield_slot", "helmet_slot",
             "body_armor_slot", "leg_armor_slot", "boots_slot",
             "ring1_slot", "ring2_slot", "amulet_slot",
             "artifact1_slot", "artifact2_slot", "artifact3_slot",
             "utility1_slot", "utility2_slot", "bag_slot"]
    eq = {s: None for s in slots}
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="probe", level=5, xp=0, max_xp=500,
        hp=hp, max_hp=max_hp, gold=gold,
        skills={"mining": 3, "woodcutting": 2, "fishing": 1,
                "weaponcrafting": 1, "gearcrafting": 1,
                "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=x, y=y,
        inventory=inventory or {},
        inventory_max=20,
        equipment=eq,
        cooldown_expires=None,
        task_code=task_code, task_type=task_type,
        task_progress=task_progress, task_total=task_total,
        bank_items=bank_items, bank_gold=bank_gold,
        pending_items=pending_items,
        attack=attack if attack is not None else {"fire": 30},
        dmg=dmg,
        dmg_elements=dmg_elements if dmg_elements is not None else {"fire": 10},
        resistance=resistance if resistance is not None else {"fire": 5},
        critical_strike=critical_strike,
        initiative=initiative,
        wisdom=wisdom,
        skill_xp=skill_xp if skill_xp is not None else {"alchemy": 4500},
    )


def _make_game_data_basic() -> GameData:
    gd = GameData()
    gd._item_stats = {}
    gd._crafting_recipes = {}
    gd._resource_drops = {}
    gd._resource_skill = {}
    gd._resource_locations = {}
    gd._workshop_locations = {}
    gd._monster_locations = {"chicken": [(0, 0)]}
    gd._monster_level = {"chicken": 1}
    gd._bank_location = (4, 0)
    gd._next_expansion_cost = 1000
    return gd


# ----------------------------------------------------------------------------
# Explicit regression-pins: the probe-verified state from the user spec
# ----------------------------------------------------------------------------

PROBE_BASELINE = dict(
    attack={"fire": 30},
    skill_xp={"alchemy": 4500},
    resistance={"fire": 5},
    dmg=15,
    wisdom=12,
    critical_strike=10,
    initiative=5,
    dmg_elements={"fire": 10},
)


def test_move_preserves_baseline_probe() -> None:
    """Pre-fix regression: MoveAction dropped all 8 baseline fields."""
    state = _make_state(x=0, y=0, **PROBE_BASELINE)
    gd = _make_game_data_basic()
    after = MoveAction(x=1, y=0).apply(state, gd)
    _assert_preserved(state, after)
    # And the move actually moved (non-vacuous):
    assert (after.x, after.y) == (1, 0)


def test_equip_preserves_baseline_probe() -> None:
    """Pre-fix regression: EquipAction dropped all 8 baseline fields."""
    state = _make_state(inventory={"sword": 1}, **PROBE_BASELINE)
    gd = _make_game_data_basic()
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon")}
    after = EquipAction(code="sword", slot="weapon_slot").apply(state, gd)
    _assert_preserved(state, after)
    # And the equip actually equipped:
    assert after.equipment["weapon_slot"] == "sword"


# ----------------------------------------------------------------------------
# Per-action preservation: one test per concrete Action subclass
# ----------------------------------------------------------------------------

def _gd_with_recipe() -> GameData:
    gd = _make_game_data_basic()
    gd._item_stats = {
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
    }
    gd._crafting_recipes = {"copper_dagger": {"copper_ore": 6}}
    gd._workshop_locations = {"weaponcrafting": (3, 0)}
    return gd


def test_move() -> None:
    state = _make_state(x=0, y=0)
    _assert_preserved(state, MoveAction(x=1, y=0).apply(state, _make_game_data_basic()))


def test_move_semantic() -> None:
    state = _make_state(x=0, y=0)
    _assert_preserved(
        state,
        MoveTo(name="bank", destinations=frozenset({(4, 0)})).apply(state, _make_game_data_basic()),
    )


def test_equip() -> None:
    state = _make_state(inventory={"sword": 1})
    gd = _make_game_data_basic()
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon")}
    _assert_preserved(state, EquipAction(code="sword", slot="weapon_slot").apply(state, gd))


def test_unequip() -> None:
    state = _make_state(equipment={"weapon_slot": "sword"})
    _assert_preserved(state, UnequipAction(slot="weapon_slot").apply(state, _make_game_data_basic()))


def test_claim() -> None:
    state = _make_state(pending_items=(("id1", "gold_ring"),))
    _assert_preserved(state, ClaimPendingItemAction().apply(state, _make_game_data_basic()))


def test_rest() -> None:
    state = _make_state(hp=10, max_hp=100)
    _assert_preserved(state, RestAction().apply(state, _make_game_data_basic()))


def test_transition() -> None:
    # Identity apply — trivially preserves.
    state = _make_state()
    _assert_preserved(state, MapTransitionAction().apply(state, _make_game_data_basic()))


def test_accept_task() -> None:
    state = _make_state()
    _assert_preserved(state, AcceptTaskAction(taskmaster_location=(1, 0)).apply(state, _make_game_data_basic()))


def test_complete_task() -> None:
    state = _make_state(task_code="x", task_type="monsters", task_progress=5, task_total=5)
    _assert_preserved(state, CompleteTaskAction(taskmaster_location=(1, 0)).apply(state, _make_game_data_basic()))


def test_task_cancel() -> None:
    # Post-fix (REAL BUG #11): TaskCancel requires holding a tasks_coin.
    state = _make_state(task_code="x", task_type="monsters", task_total=5,
                        inventory={"tasks_coin": 1})
    _assert_preserved(state, TaskCancelAction(taskmaster_location=(1, 0)).apply(state, _make_game_data_basic()))


def test_task_exchange() -> None:
    state = _make_state(inventory={"tasks_coin": 10})
    _assert_preserved(
        state,
        TaskExchangeAction(taskmaster_location=(1, 0), min_coins=3).apply(state, _make_game_data_basic()),
    )


def test_task_trade() -> None:
    state = _make_state(inventory={"gudgeon": 5})
    _assert_preserved(
        state,
        TaskTradeAction(code="gudgeon", quantity=2, taskmaster_location=(1, 0)).apply(
            state, _make_game_data_basic()
        ),
    )


def test_delete() -> None:
    state = _make_state(inventory={"trash": 3})
    _assert_preserved(state, DeleteItemAction(code="trash", quantity=1).apply(state, _make_game_data_basic()))


def test_deposit_gold() -> None:
    state = _make_state(gold=200, bank_gold=0)
    _assert_preserved(
        state,
        DepositGoldAction(quantity=50, bank_location=(4, 0)).apply(state, _make_game_data_basic()),
    )


def test_withdraw_gold() -> None:
    state = _make_state(gold=0, bank_gold=200)
    _assert_preserved(
        state,
        WithdrawGoldAction(quantity=50, bank_location=(4, 0)).apply(state, _make_game_data_basic()),
    )


def test_withdraw_item() -> None:
    state = _make_state(bank_items={"sword": 3})
    _assert_preserved(
        state,
        WithdrawItemAction(code="sword", quantity=1, bank_location=(4, 0)).apply(
            state, _make_game_data_basic()
        ),
    )


def test_deposit_all() -> None:
    gd = _make_game_data_basic()
    state = _make_state(inventory={"trash": 5}, bank_items={})
    action = DepositAllAction(bank_location=(4, 0), game_data=gd)
    _assert_preserved(state, action.apply(state, gd))


def test_bank_expansion() -> None:
    state = _make_state(gold=5000)
    gd = _make_game_data_basic()
    _assert_preserved(state, BuyBankExpansionAction(bank_location=(4, 0)).apply(state, gd))


def test_npc_buy() -> None:
    gd = _make_game_data_basic()
    gd._npc_sells = {("merchant", "potion"): 10}
    gd.npc_sells_item = lambda npc, item: gd._npc_sells.get((npc, item))  # type: ignore[method-assign]
    state = _make_state(gold=200)
    _assert_preserved(
        state,
        NpcBuyAction(npc_code="merchant", item_code="potion", quantity=1,
                     npc_location=(2, 0)).apply(state, gd),
    )


def test_npc_sell() -> None:
    gd = _make_game_data_basic()
    gd._npc_buys = {("merchant", "trash"): 5}
    gd.npc_buys_item = lambda npc, item: gd._npc_buys.get((npc, item))  # type: ignore[method-assign]
    state = _make_state(inventory={"trash": 3})
    _assert_preserved(
        state,
        NpcSellAction(npc_code="merchant", item_code="trash", quantity=1,
                      npc_location=(2, 0)).apply(state, gd),
    )


def test_use_consumable() -> None:
    gd = _make_game_data_basic()
    stats = {"potion": ItemStats(code="potion", level=1, type_="consumable", hp_restore=50)}
    state = _make_state(hp=50, max_hp=100, inventory={"potion": 2})
    action = UseConsumableAction(_item_stats=stats)
    _assert_preserved(state, action.apply(state, gd))


def test_craft() -> None:
    gd = _gd_with_recipe()
    state = _make_state(inventory={"copper_ore": 12}, skill_xp={"weaponcrafting": 10, "alchemy": 4500})
    _assert_preserved(
        state,
        CraftAction(code="copper_dagger", quantity=1, workshop_location=(3, 0)).apply(state, gd),
    )


def test_recycle() -> None:
    gd = _gd_with_recipe()
    state = _make_state(inventory={"copper_dagger": 2})
    _assert_preserved(
        state,
        RecycleAction(code="copper_dagger", quantity=1, workshop_location=(3, 0)).apply(state, gd),
    )


def test_gather() -> None:
    gd = _make_game_data_basic()
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    state = _make_state(skill_xp={"mining": 5, "alchemy": 4500})
    _assert_preserved(
        state,
        GatherAction(resource_code="copper_rocks", locations=frozenset([(2, 0)])).apply(state, gd),
    )


# ----------------------------------------------------------------------------
# Projected skill XP delta — NEW field outside the 8-field baseline contract.
# Gather/Craft.apply MUST add to it; the contract over `skill_xp` is unaffected.
# ----------------------------------------------------------------------------

def test_gather_increments_projected_skill_xp_delta() -> None:
    """Regression pin: GatherAction.apply must add +1 to the projected XP
    accumulator for the resource's gathering skill (the LevelSkillGoal
    plannability fix)."""
    gd = _make_game_data_basic()
    gd._resource_skill = {"copper_rocks": ("mining", 1)}
    gd._resource_drops = {"copper_rocks": "copper_ore"}
    gd._resource_locations = {"copper_rocks": [(2, 0)]}
    state = _make_state()
    after = GatherAction(
        resource_code="copper_rocks", locations=frozenset([(2, 0)])
    ).apply(state, gd)
    _assert_preserved(state, after)  # 8-field contract still holds
    assert after.projected_skill_xp_delta.get("mining", 0) == 1
    # state's own delta untouched (frozen dataclass).
    assert state.projected_skill_xp_delta == {}


def test_craft_increments_projected_skill_xp_delta_by_quantity() -> None:
    """Regression pin: CraftAction.apply must add +quantity to the projected
    XP accumulator for the recipe's crafting skill."""
    gd = _gd_with_recipe()
    state = _make_state(inventory={"copper_ore": 12})
    after = CraftAction(
        code="copper_dagger", quantity=2, workshop_location=(3, 0)
    ).apply(state, gd)
    _assert_preserved(state, after)  # 8-field contract still holds
    assert after.projected_skill_xp_delta.get("weaponcrafting", 0) == 2


def test_fight() -> None:
    gd = _make_game_data_basic()
    state = _make_state(hp=100, max_hp=100,
                        equipment={"weapon_slot": "sword"})
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon")}
    _assert_preserved(
        state,
        FightAction(monster_code="chicken", locations=frozenset({(0, 0)})).apply(state, gd),
    )


def test_optimize_loadout() -> None:
    """OptimizeLoadout returns identity when no swap is beneficial (or no
    target). The contract still holds — preservation is trivial on identity
    and structural on the active branch (dataclasses.replace)."""
    gd = _make_game_data_basic()
    state = _make_state()
    # Empty target with empty inventory ⇒ no swap ⇒ identity.
    after = OptimizeLoadoutAction(target_monster_code="", game_data=gd).apply(state, gd)
    _assert_preserved(state, after)


# ----------------------------------------------------------------------------
# Hypothesis property: every action preserves baseline over generated states
# ----------------------------------------------------------------------------

@st.composite
def _baseline_kwargs(draw) -> dict[str, Any]:
    """Generate non-trivial baseline kwargs to feed to _make_state."""
    elems = st.sampled_from(["fire", "earth", "water", "air"])
    dict_strat = st.dictionaries(elems, st.integers(min_value=0, max_value=200), max_size=4)
    skill_dict = st.dictionaries(
        st.sampled_from(["mining", "woodcutting", "fishing", "weaponcrafting",
                         "gearcrafting", "jewelrycrafting", "cooking", "alchemy"]),
        st.integers(min_value=0, max_value=10_000), max_size=8,
    )
    return dict(
        attack=draw(dict_strat),
        dmg=draw(st.integers(min_value=0, max_value=500)),
        dmg_elements=draw(dict_strat),
        resistance=draw(dict_strat),
        critical_strike=draw(st.integers(min_value=0, max_value=100)),
        initiative=draw(st.integers(min_value=0, max_value=100)),
        wisdom=draw(st.integers(min_value=0, max_value=100)),
        skill_xp=draw(skill_dict),
    )


@given(bkw=_baseline_kwargs())
@settings(max_examples=200)
def test_move_preserves_baseline_property(bkw) -> None:
    state = _make_state(x=0, y=0, **bkw)
    after = MoveAction(x=1, y=0).apply(state, _make_game_data_basic())
    _assert_preserved(state, after)


@given(bkw=_baseline_kwargs())
@settings(max_examples=200)
def test_equip_preserves_baseline_property(bkw) -> None:
    state = _make_state(inventory={"sword": 1}, **bkw)
    gd = _make_game_data_basic()
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon")}
    after = EquipAction(code="sword", slot="weapon_slot").apply(state, gd)
    _assert_preserved(state, after)


@given(bkw=_baseline_kwargs())
@settings(max_examples=200)
def test_claim_preserves_baseline_property(bkw) -> None:
    state = _make_state(pending_items=(("id1", "gold_ring"),), **bkw)
    after = ClaimPendingItemAction().apply(state, _make_game_data_basic())
    _assert_preserved(state, after)


@given(bkw=_baseline_kwargs())
@settings(max_examples=200)
def test_fight_preserves_baseline_property(bkw) -> None:
    state = _make_state(hp=100, max_hp=100,
                        equipment={"weapon_slot": "sword"}, **bkw)
    gd = _make_game_data_basic()
    gd._item_stats = {"sword": ItemStats(code="sword", level=1, type_="weapon")}
    after = FightAction(monster_code="chicken", locations=frozenset({(0, 0)})).apply(state, gd)
    _assert_preserved(state, after)
