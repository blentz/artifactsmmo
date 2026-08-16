"""Task 7: a recalled currency is not re-equipped while its turn-in is live.

Five characters wear `lich_race_medal` artifacts that double as the currency
for `lich_race_trophy`. When a fleet turn-in is live, siblings unequip and
deposit their medals so the elected buyer can spend them. Without this
reservation, the character that just banked a medal immediately re-equips it
into its empty artifact slot — a withdraw/re-equip livelock, this repo's known
failure shape.

The general rule is unchanged: wearing a dual-role item like `lich_race_medal`
IS the fleet's storage, and stays allowed. This reservation is narrow and
temporary — it excludes ONLY the live turn-in's currency code, and ONLY while
`ctx.turn_in` is set, mirroring the existing `task_reserved_demand` exclusion
this same call site already applies for items-task materials.

Seam: `StrategyArbiter._build_candidates`, the sole caller of
`empty_slot_rank_fills` — same seam `test_equip_owned_arbiter.py` exercises.
"""

from artifactsmmo_cli.ai.currency_turnin import TurnIn
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.equip_owned_gear import EquipOwnedGoal
from artifactsmmo_cli.ai.planner import GOAPPlanner
from artifactsmmo_cli.ai.strategy_driver import StrategyArbiter
from artifactsmmo_cli.ai.tiers.guards import SelectionContext
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai.fixtures import make_state
from tests.test_ai.test_dual_role_fixtures import medal_game_data


def _wearable_medal_game_data() -> GameData:
    """`medal_game_data()` gives `lich_race_medal` an all-zero-stat ItemStats —
    fine for the currency-side tests it exists for, but the empty-slot picker's
    zero-benefit gate (see `medal_game_data`'s own docstring) would then reject
    the medal as a fill for a reason unrelated to this feature. Give it the
    same minimal `hp_bonus=1` `lich_race_trophy` uses so it is a genuine
    positive-Rank fill candidate here."""
    gd = medal_game_data()
    stats = gd._item_stats["lich_race_medal"]
    gd._item_stats["lich_race_medal"] = ItemStats(
        code=stats.code, level=stats.level, type_=stats.type_, hp_bonus=1)
    return gd

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}

_LIVE_TURN_IN = TurnIn(item_code="lich_race_trophy", npc_code="archaeologist",
                        price=10, currency="lich_race_medal",
                        buyer="Robby", fleet_total=10)


def _ctx(**kw: object) -> SelectionContext:
    base = dict(bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
                initial_xp=0, task_exchange_min_coins=1, combat_monster=None,
                gear_review_active=False)
    base.update(kw)
    return SelectionContext(**base)


def _medal_state(**overrides: object) -> WorldState:
    # level=10: matches lich_race_medal's ItemStats.level (medal_game_data) —
    # a lower character level would make the medal unequippable regardless of
    # reservation, and this fixture must isolate the turn-in exclusion alone.
    base = dict(level=10, inventory={"lich_race_medal": 1}, equipment=dict(_ALL_SLOTS))
    base.update(overrides)
    return make_state(**base)


def _build(state: WorldState, gd: GameData, ctx: SelectionContext) -> list:
    arbiter = StrategyArbiter(GOAPPlanner(), None)
    return arbiter._build_candidates(
        guard_kinds=[], collect_kinds=[], discretionary_kinds=[],
        step_goal=None, fallback_steps=[], fallback_roots=[],
        state=state, game_data=gd, ctx=ctx,
    )


def test_a_recalled_currency_is_not_re_equipped_while_the_turn_in_is_live() -> None:
    cands = _build(_medal_state(), _wearable_medal_game_data(), _ctx(turn_in=_LIVE_TURN_IN))
    equips = [c for c in cands if isinstance(c.goal, EquipOwnedGoal)]
    assert not equips, [c.repr_ for c in cands]


def test_the_same_medal_is_equippable_when_no_turn_in_is_live() -> None:
    """The general rule is unchanged: wearing dual-role items IS the storage."""
    cands = _build(_medal_state(), _wearable_medal_game_data(), _ctx())
    equips = [c for c in cands if isinstance(c.goal, EquipOwnedGoal)]
    assert len(equips) == 1, [c.repr_ for c in cands]
    assert equips[0].goal.fills == {"artifact1_slot": "lich_race_medal"}


def test_task_material_reservation_still_excludes_its_fill() -> None:
    """Pre-existing behaviour (`task_reserved_demand`) is untouched: an owned
    item still owed to an active items task is excluded regardless of
    `ctx.turn_in`."""
    gd = GameData()
    gd._item_stats = {
        "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                  hp_bonus=30, wisdom=10, prospecting=5),
    }
    state = make_state(
        inventory={"novice_guide": 1}, equipment=dict(_ALL_SLOTS),
        task_code="novice_guide", task_type="items", task_progress=0, task_total=1,
    )
    cands = _build(state, gd, _ctx())
    equips = [c for c in cands if isinstance(c.goal, EquipOwnedGoal)]
    assert not equips, [c.repr_ for c in cands]
