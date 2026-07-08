# tests/test_ai/test_progression_reserve.py
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.progression_reserve import (
    _MIN_SAFETY_FLOOR,
    boss_targets,
    buy_price,
    crafting_unlock_targets,
    gear_targets,
    progression_reserve,
    reserve_floor,
    reserve_floor_multi,
    reserved_targets,
)
from tests.test_ai.fixtures import make_state


def _gd_buyable_armor() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # a body-armor upgrade usable at level<=7, sold by an npc, not craftable
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
        # currently equipped (worse)
        "rags": ItemStats(code="rags", level=1, type_="body_armor", hp_bonus=5),
    }
    # _npc_stock is what NPCs sell TO the player (feeds npcs_selling_item)
    gd._npc_stock = {"merchant": {"iron_armor": 120}}
    gd._monster_level = {"chicken": 1}
    return gd


def test_buy_price_is_cheapest_seller():
    gd = _gd_buyable_armor()
    assert buy_price("iron_armor", gd) == 120
    assert buy_price("nonexistent", gd) is None


def test_gear_targets_reserves_unmet_buyable_upgrade():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    targets = gear_targets(state, gd)
    assert targets == {"iron_armor": 120}


def test_gear_targets_skips_already_equipped_best():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "iron_armor"})
    assert gear_targets(state, gd) == {}


def test_gear_targets_skips_out_of_horizon():
    gd = _gd_buyable_armor()
    gd._item_stats["iron_armor"].level = 99  # far above level+2
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert gear_targets(state, gd) == {}


def test_gear_targets_skips_craftable_upgrade():
    """A better in-horizon gear upgrade that HAS a crafting recipe is not a gold
    need (it can be crafted) → excluded from gear_targets."""
    gd = _gd_buyable_armor()
    gd._crafting_recipes = {"iron_armor": {"iron_bar": 3}}  # craftable, not a BUY
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert gear_targets(state, gd) == {}


def test_gear_targets_skips_upgrade_with_no_seller():
    """A better in-horizon, non-craftable gear upgrade that NO NPC/GE sells has no
    buy price → cannot be a gold need → excluded from gear_targets."""
    gd = _gd_buyable_armor()
    gd._npc_stock = {}  # nobody sells iron_armor; not craftable either
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert gear_targets(state, gd) == {}


def test_buy_price_prefers_ge_when_cheaper():
    """GE sell order cheaper than NPC → buy_price returns the GE price."""
    gd = GameData()
    gd._item_stats = {
        "iron_armor": ItemStats(code="iron_armor", level=5, type_="body_armor", hp_bonus=40),
    }
    gd._npc_stock = {"merchant": {"iron_armor": 200}}
    # GE sell order: (order_id, price, quantity); price 80 < NPC 200
    gd._ge_sell_orders = {"iron_armor": ("order-1", 80, 10)}
    assert buy_price("iron_armor", gd) == 80


def test_buy_price_uses_ge_when_no_npc():
    """Item only available via a GE sell order → buy_price returns the GE price."""
    gd = GameData()
    gd._item_stats = {
        "silver_ring": ItemStats(code="silver_ring", level=3, type_="ring", hp_bonus=5),
    }
    gd._npc_stock = {}
    gd._ge_sell_orders = {"silver_ring": ("order-99", 150, 5)}
    assert buy_price("silver_ring", gd) == 150


def test_crafting_unlock_reserves_buyable_recipe_input():
    """Recipe input that is not gatherable and has no recipe of its own → reserved at qty * price."""
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=6, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"steel_bar": 3}}
    # steel_bar is sold by NPC (buyable), not gatherable, no recipe of its own
    gd._npc_stock = {"smith": {"steel_bar": 25}}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    targets = crafting_unlock_targets(state, gd)
    assert targets == {"steel_bar": 75}


def test_crafting_unlock_skips_gatherable_inputs():
    """Recipe input that is gatherable → not a gold need, skipped."""
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "iron_ore": ItemStats(code="iron_ore", level=6, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"iron_ore": 3}}
    gd._resource_drops = {"iron_rocks": "iron_ore"}  # gatherable → not a gold need
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    assert crafting_unlock_targets(state, gd) == {}


def test_crafting_unlock_skips_craftable_inputs():
    """Recipe input that has its own crafting recipe → not a gold need, skipped."""
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=6, type_="resource"),
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
    }
    # steel_bar has its own recipe (craftable from iron_ore) → should NOT be reserved
    gd._crafting_recipes = {
        "steel_sword": {"steel_bar": 3},
        "steel_bar": {"iron_ore": 2},
    }
    gd._npc_stock = {"smith": {"steel_bar": 25}}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    assert crafting_unlock_targets(state, gd) == {}


def test_crafting_unlock_skips_input_with_no_seller():
    """Recipe input that is neither gatherable nor craftable but has NO seller →
    no buy price → it cannot be a reserved gold need, so it is skipped."""
    gd = GameData()
    gd._item_stats = {
        "steel_sword": ItemStats(code="steel_sword", level=6, type_="weapon",
                                 attack={"fire": 30}, crafting_skill="weaponcrafting",
                                 crafting_level=1),
        "steel_bar": ItemStats(code="steel_bar", level=6, type_="resource"),
    }
    gd._crafting_recipes = {"steel_sword": {"steel_bar": 3}}
    # steel_bar: not gatherable, no recipe of its own, and NO NPC/GE sells it.
    gd._npc_stock = {}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5, skills={"weaponcrafting": 1})
    assert crafting_unlock_targets(state, gd) == {}


def test_boss_targets_is_stub_empty():
    gd = _gd_buyable_armor()
    assert boss_targets(make_state(level=5), gd) == {}


def test_reserved_targets_unions_sources():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert reserved_targets(state, gd) == {"iron_armor": 120}
    assert progression_reserve(state, gd) == 120


def test_reserve_floor_deducts_when_buying_a_reserved_item():
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    # buying the reserved iron_armor -> its 120 is credited -> raw floor 0,
    # but clamped up to _MIN_SAFETY_FLOOR (100) so the bot never spends to zero.
    assert reserve_floor(state, gd, "iron_armor") == 100
    # buying something else -> full floor 120 (already above the 100 min)
    assert reserve_floor(state, gd, "copper_ore") == 120
    assert reserve_floor(state, gd, None) == 120


def test_minimum_safety_floor_when_nothing_reserved():
    gd = GameData()
    gd._item_stats = {}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5)
    assert progression_reserve(state, gd) == 100   # _MIN_SAFETY_FLOOR


# --- reserve_floor_multi (follow-up wave Task 4: joint gold affordability) ---


def test_reserve_floor_multi_matches_single_leaf_for_singleton():
    """`reserve_floor_multi(s, gd, frozenset({x}))` must equal
    `reserve_floor(s, gd, x)` — the joint check must reduce EXACTLY to Task
    3's single-leaf gate when only one leaf is in play, never a silent
    behavior fork."""
    gd = _gd_buyable_armor()
    state = make_state(level=5, equipment={"body_armor_slot": "rags"})
    assert (reserve_floor_multi(state, gd, frozenset({"iron_armor"}))
            == reserve_floor(state, gd, "iron_armor") == 100)
    assert (reserve_floor_multi(state, gd, frozenset({"copper_ore"}))
            == reserve_floor(state, gd, "copper_ore") == 120)


def test_reserve_floor_multi_dedups_every_leaf_in_the_set():
    """Two DISTINCT reserved targets (iron_armor 250, a second gear upgrade
    200 — priced well above `_MIN_SAFETY_FLOOR` so the floor clamp doesn't
    mask the dedup arithmetic) bought TOGETHER dedup BOTH from the floor —
    checking either alone would only dedup itself, silently crediting the
    other's price as still-protected room (the exact joint-overspend gap
    Task 4 closes)."""
    gd = _gd_buyable_armor()
    gd._npc_stock["merchant"]["iron_armor"] = 250
    gd._item_stats["shiny_ring"] = ItemStats(
        code="shiny_ring", level=5, type_="ring", hp_bonus=1)
    gd._npc_stock["jeweler"] = {"shiny_ring": 200}
    state = make_state(level=5, equipment={"body_armor_slot": "rags", "ring1_slot": None})
    assert reserved_targets(state, gd) == {"iron_armor": 250, "shiny_ring": 200}
    # Buying iron_armor alone: only its own 250 dedups -> floor 200 (shiny_ring protected).
    assert reserve_floor_multi(state, gd, frozenset({"iron_armor"})) == 200
    # Buying BOTH together: both dedup -> raw floor 0, clamped to _MIN_SAFETY_FLOOR.
    assert reserve_floor_multi(state, gd, frozenset({"iron_armor", "shiny_ring"})) == 100
    assert reserve_floor_multi(state, gd, frozenset()) == 450  # nothing bought -> full total


def test_reserve_floor_multi_floors_at_min_safety():
    gd = GameData()
    gd._item_stats = {}
    gd._monster_level = {"chicken": 1}
    state = make_state(level=5)
    assert reserve_floor_multi(state, gd, frozenset({"anything"})) == _MIN_SAFETY_FLOOR
