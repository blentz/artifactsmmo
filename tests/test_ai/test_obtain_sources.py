"""Tests for `obtain_sources` — THE model of how an item can be obtained.

Mirrors the fixture style of `tests/ai/test_recoverable_materials.py` (a fake
`GameData` with `_item_stats` / `_crafting_recipes` / `_workshop_locations`,
plus a `with_workshops` toggle for the "no workshop known" gate) — do NOT
invent a new fixture idiom.

INERT — no consumers yet. The parity census's oracle will BE this function,
so it must be pinned by unit tests BEFORE anything depends on it (an oracle
and its consumer written together are wrong together). See
`docs/superpowers/specs/2026-07-14-one-obtain-model-design.md`.
"""

import pytest

from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.obtain_sources import (
    SourceKind,
    obtain_source_map,
    obtain_sources,
)
from artifactsmmo_cli.ai.selection_context import SelectionContext
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState
from tests.test_ai._monster_fixture import fill_monster_stat_defaults

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
        # Raw resource: no recipe, no crafting_skill -> the CRAFT gate's
        # "recipe is None" branch, and the sole GATHER source (ash_tree).
        "ash_wood": ItemStats(code="ash_wood", level=1, type_="resource"),
        # Craftable intermediate (from ash_wood); also RECYCLE-able out of
        # fishing_net surplus -- the priority-order test's centerpiece.
        "ash_plank": ItemStats(code="ash_plank", level=1, type_="resource",
                               crafting_skill="woodcutting", crafting_level=1),
        # Equippable + craftable, gearcrafting-gated: the RECYCLE SOURCE for
        # ash_plank (recipe {ash_plank: 6}).
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="amulet",
                                 crafting_skill="gearcrafting", crafting_level=1),
        # Equippable TOOL (skill_effects makes it the best owned woodcutting
        # tool -> KeepReason.WORKING_KIT protects the last copy).
        "copper_axe": ItemStats(code="copper_axe", level=1, type_="weapon",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10},
                                crafting_skill="weaponcrafting", crafting_level=1),
        # Craftable but NON-equippable: `type_="consumable"` has no slot in
        # `ITEM_TYPE_TO_SLOTS`, so `actions/factory` never builds a
        # RecycleAction for it -- the equippable gate.
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    crafting_skill="cooking", crafting_level=1),
        # Under-skill: recipe crafting_level (5) exceeds the fixed character
        # weaponcrafting level (1) set explicitly in its dedicated test.
        "fire_staff": ItemStats(code="fire_staff", level=5, type_="weapon",
                                attack={"fire": 20}, crafting_skill="weaponcrafting",
                                crafting_level=5),
        # No recipe at all; sold ONLY by an event NPC -> never a BUY source.
        "event_only_item": ItemStats(code="event_only_item", level=1, type_="ring"),
        # No recipe; sold by a PERMANENT, reachable vendor -> a live BUY source.
        "iron_ore": ItemStats(code="iron_ore", level=1, type_="resource"),
        # No recipe; sold by a vendor whose location is unknown (not an event
        # NPC either) -> the "npc_location is None" BUY gate.
        "ghost_item": ItemStats(code="ghost_item", level=1, type_="resource"),
        # No recipe; dropped only by an unwinnable monster.
        "boss_scale": ItemStats(code="boss_scale", level=1, type_="resource"),
        # No recipe; dropped by an easily-winnable monster -> a live DROP source.
        "slime_ball": ItemStats(code="slime_ball", level=1, type_="resource"),
    }
    gd._crafting_recipes = {
        "ash_plank": {"ash_wood": 5},
        "fishing_net": {"ash_plank": 6},
        "copper_axe": {"copper_bar": 6},
        "cooked_chicken": {"chicken": 2},
        "fire_staff": {"ash_wood": 10},
        # A recipe with NO matching `ItemStats` entry (malformed/dropped gear
        # data) -- the RECYCLE eligibility check must refuse it via
        # `stats is None` before ever asking `destroyable`.
        "mystery_part": {"ash_plank": 4},
        # Same shape for the CRAFT gate's own "stats is None" branch.
        "phantom_part": {"copper_bar": 4},
    }
    gd._resource_drops = {"ash_tree": "ash_wood"}
    gd._workshop_locations = ({"woodcutting": (1, 1), "gearcrafting": (2, 1),
                               "weaponcrafting": (3, 1), "cooking": (4, 1)}
                              if with_workshops else {})
    gd._npc_stock = {
        "general_store": {"iron_ore": 10},
        "hidden_vendor": {"ghost_item": 5},
        "event_vendor": {"event_only_item": 100},
    }
    gd._npc_locations = {"general_store": (5, 5)}
    # Event-vendor registration: is_event_npc True, but npc_location still
    # resolves (via the event-spawn fallback) -- this must be gated on the
    # event-ness, not merely on a missing location.
    gd._npc_event_code["event_vendor"] = "gemstone_week"
    gd._event_npc_spawns["event_vendor"] = (2, 2)
    gd._monster_level = {"boss": 10, "slime": 1}
    gd._monster_hp = {"boss": 50, "slime": 10}
    gd._monster_attack = {"boss": {"fire": 20}, "slime": {"earth": 1}}
    gd._monster_drops = {
        "boss": [("boss_scale", 20, 1, 1)],
        "slime": [("slime_ball", 2, 1, 1)],
    }
    fill_monster_stat_defaults(gd)
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
               skills: dict[str, int] | None = None, level: int = 5,
               gold: int = 0, attack: dict[str, int] | None = None,
               dmg: int = 0, hp: int = 100, max_hp: int = 100) -> WorldState:
    return WorldState(
        character="c", level=level, xp=0, max_xp=100, hp=hp, max_hp=max_hp, gold=gold,
        skills=skills or {}, x=0, y=0, inventory=inventory or {}, inventory_max=200,
        inventory_slots_max=max(len(inventory or {}), 1),
        equipment=dict(_ALL_SLOTS), cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=bank_items, bank_gold=None, bank_capacity=None, pending_items=None,
        attack=attack or {}, dmg=dmg,
    )


def _fighter_state(**overrides) -> WorldState:
    """A state whose combat stats beat the harmless slime (mirrors the
    winnability fixture shape in test_craft_plan_gen.py's `_fighter_state`)."""
    base = dict(hp=165, max_hp=165, attack={"air": 5}, dmg=18)
    base.update(overrides)
    return make_state(**base)


def test_priority_prefers_stock_already_owned(game_data, ctx):
    """WITHDRAW and RECYCLE outrank CRAFT/GATHER: they consume stock we already
    hold. This generalises the rule _next already hard-codes (bank before descend)."""
    # ash_plank: craftable (from ash_wood), banked x3, AND recoverable from
    # 7 surplus fishing_net (recipe {ash_plank: 6})
    state = make_state(inventory={"fishing_net": 7}, bank_items={"ash_plank": 3})
    kinds = [s.kind for s in obtain_sources("ash_plank", state, game_data, ctx)]
    assert kinds[0] is SourceKind.WITHDRAW
    assert kinds[1] is SourceKind.RECYCLE
    assert SourceKind.CRAFT in kinds


def test_recycle_source_names_the_SOURCE_item_not_the_target(game_data, ctx):
    """Source.code for a RECYCLE is the item to DESTROY, not the material gained —
    the mapper needs it to pick RecycleAction(fishing_net)."""
    state = make_state(inventory={"fishing_net": 7})
    rec = [s for s in obtain_sources("ash_plank", state, game_data, ctx)
           if s.kind is SourceKind.RECYCLE]
    assert [s.code for s in rec] == ["fishing_net"]
    assert rec[0].yield_per == max(1, 6 // 2)   # 3 — the UNIT-recycle yield, not batch


def test_protected_item_is_not_a_recycle_source(game_data, ctx):
    """The last copper_axe is WORKING_KIT: destroyable == 0. Never a source.
    This is the anti-tool-melting property."""
    state = make_state(inventory={"copper_axe": 1})
    assert not [s for s in obtain_sources("copper_bar", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_non_equippable_is_not_a_recycle_source(game_data, ctx):
    """RecycleActions are only CONSTRUCTED for equippables (factory.py). A
    consumable/resource source has NO action in existence -> leaf with no plan."""
    state = make_state(inventory={"cooked_chicken": 9})   # craftable, NOT equippable
    assert not [s for s in obtain_sources("chicken", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_under_skill_craft_is_not_a_source(game_data, ctx):
    """A craft whose skill gate is unmet cannot be served now."""
    state = make_state(skills={"weaponcrafting": 1})   # fire_staff needs 5
    assert not [s for s in obtain_sources("fire_staff", state, game_data, ctx)
                if s.kind is SourceKind.CRAFT]


def test_event_vendor_is_not_a_buy_source(game_data, ctx):
    """Event NPCs are not permanent; a BUY source must be reliably reachable."""
    state = make_state(gold=10_000)
    assert not [s for s in obtain_sources("event_only_item", state, game_data, ctx)
                if s.kind is SourceKind.BUY]


def test_unwinnable_dropper_is_not_a_drop_source(game_data, ctx):
    state = make_state(level=1)
    assert not [s for s in obtain_sources("boss_scale", state, game_data, ctx)
                if s.kind is SourceKind.DROP]


def test_raw_resource_has_exactly_one_gather_source(game_data, ctx):
    state = make_state()
    srcs = obtain_sources("ash_wood", state, game_data, ctx)
    assert [s.kind for s in srcs] == [SourceKind.GATHER]
    assert srcs[0].code == "ash_tree"


def test_source_map_covers_a_whole_closure(game_data, ctx):
    state = make_state()
    m = obtain_source_map(["ash_plank", "ash_wood"], state, game_data, ctx)
    assert set(m) == {"ash_plank", "ash_wood"}


# ---------------------------------------------------------------------------
# Additional coverage: branches the priority/eligibility tests above don't
# reach on their own (statement coverage, not just the pinned properties).
# ---------------------------------------------------------------------------

def test_recycle_source_stats_none_is_refused(game_data, ctx):
    """`mystery_part` has a recipe consuming ash_plank but NO matching
    ItemStats (malformed/dropped gear data) -- refused via `stats is None`
    before `destroyable` is ever asked, exactly like `recoverable_materials`."""
    state = make_state(inventory={"mystery_part": 5})
    assert not [s for s in obtain_sources("ash_plank", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_craft_source_stats_none_is_refused(game_data, ctx):
    """`phantom_part` has a recipe but NO matching ItemStats -- the CRAFT gate
    must refuse the same way the RECYCLE gate does."""
    state = make_state()
    assert not [s for s in obtain_sources("phantom_part", state, game_data, ctx)
                if s.kind is SourceKind.CRAFT]


def test_recycle_source_under_skill_is_refused(game_data, ctx):
    """A source item's OWN crafting_level (not the target's) gates its
    recycle -- fire_staff needs weaponcrafting 5, character is 1."""
    state = make_state(inventory={"fire_staff": 5}, skills={"weaponcrafting": 1})
    assert not [s for s in obtain_sources("ash_wood", state, game_data, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_recycle_source_unknown_workshop_is_refused(game_data_no_workshop, ctx):
    """Every other RECYCLE gate for fishing_net passes, but no workshop is on
    file for gearcrafting -- `RecycleAction.is_applicable` would refuse too."""
    state = make_state(inventory={"fishing_net": 7})
    assert not [s for s in obtain_sources("ash_plank", state, game_data_no_workshop, ctx)
                if s.kind is SourceKind.RECYCLE]


def test_unknown_workshop_is_not_a_craft_source(game_data_no_workshop, ctx):
    """A recipe + skill gate met, but no workshop on file -> not servable now."""
    state = make_state()
    assert not [s for s in obtain_sources("ash_plank", state, game_data_no_workshop, ctx)
                if s.kind is SourceKind.CRAFT]


def test_permanent_reachable_vendor_is_a_buy_source(game_data, ctx):
    """A non-event vendor with a known location IS a live BUY source."""
    state = make_state(gold=1_000)
    buy = [s for s in obtain_sources("iron_ore", state, game_data, ctx)
           if s.kind is SourceKind.BUY]
    assert [s.code for s in buy] == ["general_store"]
    assert buy[0].yield_per == 1


def test_vendor_with_unknown_location_is_not_a_buy_source(game_data, ctx):
    """A non-event vendor whose location is unknown cannot anchor a plan --
    distinct from the event-vendor gate (this vendor is permanent, just
    unreachable-on-file)."""
    state = make_state(gold=1_000)
    assert not [s for s in obtain_sources("ghost_item", state, game_data, ctx)
                if s.kind is SourceKind.BUY]


def test_winnable_dropper_is_a_drop_source(game_data, ctx):
    """A winnable monster's drop IS a live DROP source."""
    state = _fighter_state()
    drop = [s for s in obtain_sources("slime_ball", state, game_data, ctx)
            if s.kind is SourceKind.DROP]
    assert [s.code for s in drop] == ["slime"]
    assert drop[0].yield_per == 1


def test_craft_source_yield_per_reflects_craft_yield(game_data, ctx):
    """CRAFT's yield_per is the batch yield of ONE craft run, defaulting to 1
    when the recipe schema doesn't declare a multi-unit output."""
    state = make_state()
    craft = [s for s in obtain_sources("ash_plank", state, game_data, ctx)
             if s.kind is SourceKind.CRAFT]
    assert [s.code for s in craft] == ["ash_plank"]
    assert craft[0].yield_per == 1
