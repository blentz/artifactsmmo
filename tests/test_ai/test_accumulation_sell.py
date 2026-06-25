from artifactsmmo_cli.ai.accumulation_sell import (
    ACCUM_MULT, SEVERE_STEPS, accumulation_excess, accumulation_steps,
    sellable_accumulation, worst_accumulation_steps,
)
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from tests.test_ai.fixtures import make_state


def _gd_with_buyer() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_shield": ItemStats(code="wooden_shield", level=1, type_="shield",
                                   crafting_skill="gearcrafting", crafting_level=1,
                                   tradeable=True),
        "gold_coin": ItemStats(code="gold_coin", level=1, type_="currency"),
    }
    gd._crafting_recipes = {}
    gd._npc_sell_prices = {"vendor": {"wooden_shield": 2}}
    gd._npc_locations = {"vendor": (1, 1)}
    return gd


def test_sellable_accumulation_targets_over_ratio_sellable_gear():
    gd = _gd_with_buyer()
    # 14 shields, cap 1 (equippable keep, not dominated) -> r=14 -> excess 13.
    state = make_state(level=1, inventory={"wooden_shield": 14})
    assert sellable_accumulation(state, gd) == {"wooden_shield": 13}


def test_sellable_accumulation_skips_unsellable_and_below_gate():
    gd = _gd_with_buyer()
    # gold_coin has no buyer -> skipped even if accumulated.
    state = make_state(level=1, inventory={"wooden_shield": 4, "gold_coin": 999})
    assert sellable_accumulation(state, gd) == {}  # 4 < 5*1; coin not sellable


def test_worst_accumulation_steps_is_max_over_items():
    gd = _gd_with_buyer()
    state = make_state(level=1, inventory={"wooden_shield": 40})  # steps 5
    assert worst_accumulation_steps(state, gd) == 5
    assert worst_accumulation_steps(make_state(level=1), gd) == 0


def test_steps_is_floor_log2_ratio():
    assert accumulation_steps(14, 1) == 3   # 2^3=8<=14<16
    assert accumulation_steps(11, 2) == 2   # 11/2=5.5 -> 2^2=4*2=8<=11<16
    assert accumulation_steps(32, 1) == 5   # exactly SEVERE
    assert accumulation_steps(1000, 1) == 9


def test_steps_zero_below_eff_cap_and_cap_zero_uses_one():
    assert accumulation_steps(0, 5) == 0
    assert accumulation_steps(3, 0) == 1    # eff_cap 1: 2^1=2<=3<4


def test_excess_sells_down_to_true_cap_past_gate():
    assert accumulation_excess(14, 1) == 13   # keep 1
    assert accumulation_excess(14, 0) == 14   # dominated -> sell all
    assert accumulation_excess(11, 2) == 9    # keep 2


def test_excess_zero_below_ratio_gate():
    assert accumulation_excess(4, 1) == 0     # 4 < 5*1
    assert accumulation_excess(9, 2) == 0     # 9 < 5*2=10
    assert accumulation_excess(10, 2) == 8    # 10 >= 10 -> keep 2


def test_constants():
    assert ACCUM_MULT == 5
    assert SEVERE_STEPS == 5
