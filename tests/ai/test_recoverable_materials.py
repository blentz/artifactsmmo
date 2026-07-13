"""Tests for `recoverable_materials` — materials recoverable by recycling
LICENSED surplus (bag+bank), the ACQUISITION face of recycle.

Mirrors the fixture style of `tests/test_ai/test_recycle_surplus.py` (the
DISPOSAL-face sibling): a fake `GameData` with `_item_stats` /
`_crafting_recipes` / `_workshop_locations`.

This suite PINS the oracle before any consumer exists (a later behavioral
census will use `recoverable_materials` as its oracle) — see
`docs/superpowers/specs/2026-07-13-recycle-as-acquisition-design.md`.
"""

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.recoverable_materials import recoverable_materials
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _build_game_data(with_workshops: bool) -> GameData:
    gd = GameData()
    gd._item_stats = {
        # Equippable + craftable, gearcrafting-gated: the ACQUISITION sibling
        # of copper_helmet in test_recycle_surplus.py's fixture.
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="amulet",
                                 crafting_skill="gearcrafting", crafting_level=1),
        # Equippable TOOL (skill_effects makes it the best owned woodcutting
        # tool -> KeepReason.WORKING_KIT protects the last copy, same fixture
        # shape as test_recycle_surplus.py's live-hoard axe).
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        # 1-qty ingredient recipe: the ONLY way to distinguish repeated-UNIT
        # yield (n * max(1, qty // 2)) from batch yield (max(1, (qty*n) // 2)).
        "sticky_thing": ItemStats(code="sticky_thing", level=1, type_="ring",
                                  crafting_skill="jewelrycrafting", crafting_level=1),
        # Under-skill: recipe crafting_level (5) exceeds the fixed character
        # weaponcrafting level (1) set explicitly in its dedicated test.
        "fire_staff": ItemStats(code="fire_staff", level=5, type_="weapon",
                                attack={"fire": 20}, crafting_skill="weaponcrafting",
                                crafting_level=5),
        # A SECOND copper_bar source — so two eligible items collide on ONE
        # material key and the accumulation itself is pinned (see
        # test_two_sources_of_one_material_accumulate).
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
    }
    gd._crafting_recipes = {
        "fishing_net": {"ash_plank": 6},
        "copper_axe": {"copper_bar": 6},
        "copper_boots": {"copper_bar": 8},
        "sticky_thing": {"glue": 1},
        "fire_staff": {"ash_wood": 10},
        # A recipe with NO matching `ItemStats` entry (malformed/dropped gear
        # data) — the eligibility check must refuse it via `stats is None`
        # before ever asking `destroyable`.
        "mystery_part": {"copper_bar": 4},
    }
    gd._workshop_locations = ({"gearcrafting": (2, 1), "weaponcrafting": (3, 1),
                               "jewelrycrafting": (5, 1)} if with_workshops else {})
    return gd


@pytest.fixture
def game_data() -> GameData:
    """Every gate satisfiable: recipes known, workshops known."""
    return _build_game_data(with_workshops=True)


@pytest.fixture
def game_data_no_workshop() -> GameData:
    """Same items/recipes, but NO workshop is known for any crafting skill."""
    return _build_game_data(with_workshops=False)


@pytest.fixture
def ctx() -> SelectionContext:
    return SelectionContext(bank_accessible=True, bank_required_level=0,
                            bank_unlock_monster=None, initial_xp=0,
                            task_exchange_min_coins=1, combat_monster=None)


def make_state(inventory: dict[str, int] | None = None,
               bank_items: dict[str, int] | None = None,
               skills: dict[str, int] | None = None, level: int = 5) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=100, max_hp=100, gold=0,
        skills=skills or {}, x=0, y=0, inventory=inventory or {}, inventory_max=200,
        inventory_slots_max=max(len(inventory or {}), 1),
        equipment=dict(_ALL_SLOTS), cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=bank_items, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def test_recoverable_sums_two_live_contributors_at_depth(game_data, ctx):
    """TWO disjoint contributors, both live. A single contributor cannot
    distinguish `sum` from `max` — the keep epic was bitten by exactly this."""
    # fishing_net {ash_plank: 6}; copper_axe {copper_bar: 6}
    # bag: 7 fishing_net (keep_owned 1 -> destroyable 6)
    #      17 copper_axe (keep_owned 1 -> destroyable 16)
    state = make_state(inventory={"fishing_net": 7, "copper_axe": 17})
    out = recoverable_materials(state, game_data, ctx)
    assert out["ash_plank"] == 6 * max(1, 6 // 2)    # 18
    assert out["copper_bar"] == 16 * max(1, 6 // 2)  # 48


def test_two_sources_of_one_material_accumulate(game_data, ctx):
    """The contributions of two DIFFERENT recyclable items to the SAME material
    must ADD.

    The two-contributor test above uses DISJOINT materials (ash_plank vs
    copper_bar), so it pins that both items are seen — but it cannot see the
    accumulator: with no key collision, `out[mat] = x` (overwrite) and
    `out[mat] += x` agree, and so does `max`. Only a COLLIDING key separates
    them, and a colliding key is the normal case (copper_bar is an ingredient of
    most copper gear).

    copper_axe {copper_bar: 6}: 17 held, keep_owned 1 -> 16 destroyable -> 16*3 = 48
    copper_boots {copper_bar: 8}:  9 held, keep_owned 1 ->  8 destroyable ->  8*4 = 32
    """
    state = make_state(inventory={"copper_axe": 17, "copper_boots": 9})
    out = recoverable_materials(state, game_data, ctx)
    assert out["copper_bar"] == 48 + 32     # sum of BOTH sources
    assert out["copper_bar"] != max(48, 32)  # not `max`, not last-writer-wins


def test_recoverable_counts_bank_copies(game_data, ctx):
    """destroyable counts bag+bank, so a banked hoard is recoverable —
    DEPOSIT_FULL banks the surplus, so this is the MAIN path, not an edge."""
    state = make_state(inventory={}, bank_items={"fishing_net": 7})
    out = recoverable_materials(state, game_data, ctx)
    assert out["ash_plank"] == 6 * max(1, 6 // 2)


def test_recoverable_unit_yield_not_batch_yield(game_data, ctx):
    """A 1-qty ingredient distinguishes repeated-unit from batch recycling.
    4 unit recycles of {glue: 1} recover 4; the batch formula predicts 2."""
    # sticky_thing {glue: 1}; bag 5, keep_owned 1 -> destroyable 4
    state = make_state(inventory={"sticky_thing": 5})
    out = recoverable_materials(state, game_data, ctx)
    assert out["glue"] == 4 * max(1, 1 // 2)   # 4 * 1 == 4
    assert out["glue"] != max(1, (1 * 4) // 2)  # NOT 2


def test_protected_item_contributes_nothing(game_data, ctx):
    """The last copper_axe is the WORKING_KIT tool: destroyable == 0.
    This is the anti-tool-melting property."""
    state = make_state(inventory={"copper_axe": 1})
    assert recoverable_materials(state, game_data, ctx) == {}


def test_under_skill_item_is_not_recoverable(game_data, ctx):
    """RecycleAction.is_applicable refuses when the char is under the recipe's
    crafting_level, so recoverable must refuse too or the descent stalls."""
    state = make_state(inventory={"fire_staff": 5},
                       skills={"weaponcrafting": 1})  # fire_staff needs 5
    assert recoverable_materials(state, game_data, ctx) == {}


def test_unknown_workshop_is_not_recoverable(game_data_no_workshop, ctx):
    """RecycleAction.is_applicable requires workshop_location."""
    state = make_state(inventory={"fishing_net": 7})
    assert recoverable_materials(state, game_data_no_workshop, ctx) == {}


def test_raw_material_without_recipe_is_not_recoverable(game_data, ctx):
    """A raw/gathered code has no crafting recipe at all — gate 1 refuses it
    before any keep-authority lookup, exactly like `RecycleAction.is_applicable`
    (`copper_ore` in test_recycle_surplus.py)."""
    state = make_state(inventory={"copper_ore": 50})
    assert recoverable_materials(state, game_data, ctx) == {}


def test_recipe_without_item_stats_is_not_recoverable(game_data, ctx):
    """A recipe with no matching `ItemStats` (malformed/dropped gear data) must
    be refused, not crash — `RecycleAction.is_applicable` refuses it the same
    way (`stats is None`)."""
    state = make_state(inventory={"mystery_part": 5})
    assert recoverable_materials(state, game_data, ctx) == {}
