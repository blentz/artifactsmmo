"""pick_loadout_cached memoizes the GOAP-hot loadout solve.

Live profile 2026-07-06: 86% of planner CPU was redundant pick_loadout runs —
OptimizeLoadoutAction called it fresh from is_applicable, cost AND apply on
every node expansion, and GatherAction.cost re-ran it per node too. The cache
is keyed by the exact determinants of pick_loadout (purpose, level, equipment,
inventory counts) and scoped per-GameData, so a hit is bit-identical to a
recompute against unchanged inputs.

Cache-hit proofs work by POISONING the underlying GameData between calls: a
recompute would see the poisoned catalog and change its answer, so an
unchanged answer proves the memo served.
"""

import gc

import pytest

from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.equipment.loadout_cache import (
    CACHE_MAX_ENTRIES,
    _caches,
    pick_loadout_cached,
)
from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather, Rank
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(
    level: int = 5,
    inventory: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
) -> WorldState:
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="testchar", level=level, xp=0, max_xp=100,
        hp=100, max_hp=100, gold=0,
        skills={"woodcutting": 5},
        x=0, y=0,
        inventory=inventory or {}, inventory_max=20,
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        "iron_axe": ItemStats(code="iron_axe", level=1, type_="weapon", subtype="tool",
                              attack={"earth": 3}, skill_effects={"woodcutting": -10}),
    }
    gd._resource_skill = {"ash_tree": ("woodcutting", 1)}
    gd._monster_attack = {"yellow_slime": {"earth": 5, "fire": 0, "water": 0, "air": 0}}
    gd._monster_resistance = {"yellow_slime": {"earth": 0, "fire": 0, "water": 0, "air": 0}}
    return gd


def _poison(gd: GameData) -> None:
    """Remove the gather tool from the catalog: any RECOMPUTE now picks
    differently, so an unchanged answer proves a cache hit."""
    del gd._item_stats["iron_axe"]


class TestPickLoadoutCached:
    def test_matches_uncached_pick_loadout(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"iron_axe": 1, "wooden_stick": 1})
        purpose = Gather("woodcutting")
        assert pick_loadout_cached(purpose, state, gd) == pick_loadout(purpose, state, gd)

    def test_second_identical_call_is_served_from_cache(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"iron_axe": 1})
        first = pick_loadout_cached(Gather("woodcutting"), state, gd)
        assert first["weapon_slot"] == "iron_axe"
        _poison(gd)
        assert pick_loadout_cached(Gather("woodcutting"), state, gd) == first

    def test_inventory_change_recomputes(self) -> None:
        gd = _gd()
        pick_loadout_cached(Gather("woodcutting"), _make_state(inventory={"iron_axe": 1}), gd)
        _poison(gd)
        # New inventory = new key = recompute against the poisoned catalog.
        fresh = pick_loadout_cached(
            Gather("woodcutting"), _make_state(inventory={"wooden_stick": 1}), gd)
        assert fresh["weapon_slot"] != "iron_axe"

    def test_equipment_change_recomputes(self) -> None:
        gd = _gd()
        base = _make_state(inventory={"iron_axe": 1})
        cached = pick_loadout_cached(Gather("woodcutting"), base, gd)
        assert cached["weapon_slot"] == "iron_axe"
        _poison(gd)
        equipped = _make_state(inventory={"iron_axe": 1},
                               equipment={"weapon_slot": "wooden_stick"})
        fresh = pick_loadout_cached(Gather("woodcutting"), equipped, gd)
        # Poisoned catalog has no iron_axe: a recompute cannot pick it.
        assert fresh["weapon_slot"] != "iron_axe"

    def test_non_equippable_inventory_churn_still_hits(self) -> None:
        """GOAP `apply` churns gathered materials every node; none of them can
        ever appear in a loadout, so the memo key must ignore them (live
        profile 2026-07-06: whole-inventory keys left 68% of planner CPU as
        cache misses)."""
        gd = _gd()
        gd._item_stats["copper_ore"] = ItemStats(code="copper_ore", level=1,
                                                 type_="resource")
        first = pick_loadout_cached(
            Gather("woodcutting"), _make_state(inventory={"iron_axe": 1}), gd)
        assert first["weapon_slot"] == "iron_axe"
        _poison(gd)
        churned = _make_state(
            inventory={"iron_axe": 1, "copper_ore": 7, "uncatalogued_drop": 2})
        assert pick_loadout_cached(Gather("woodcutting"), churned, gd) == first

    def test_equippable_count_change_recomputes(self) -> None:
        gd = _gd()
        pick_loadout_cached(
            Gather("woodcutting"), _make_state(inventory={"iron_axe": 1}), gd)
        _poison(gd)
        fresh = pick_loadout_cached(
            Gather("woodcutting"), _make_state(inventory={"iron_axe": 2}), gd)
        # Two copies = new key = recompute against the poisoned catalog.
        assert fresh["weapon_slot"] != "iron_axe"

    def test_purpose_distinguishes_entries(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"iron_axe": 1, "wooden_stick": 1})
        gather = pick_loadout_cached(Gather("woodcutting"), state, gd)
        combat = pick_loadout_cached(
            Combat(gd.monster_attack("yellow_slime"),
                   gd.monster_resistance("yellow_slime")),
            state, gd)
        assert gather["weapon_slot"] == "iron_axe"
        assert combat["weapon_slot"] == "wooden_stick"

    def test_rank_purpose_is_cacheable(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"wooden_stick": 1})
        first = pick_loadout_cached(Rank(), state, gd)
        _poison(gd)
        assert pick_loadout_cached(Rank(), state, gd) == first

    def test_unknown_purpose_raises(self) -> None:
        gd = _gd()
        with pytest.raises(TypeError, match="purpose"):
            pick_loadout_cached(object(), _make_state(), gd)

    def test_mutating_returned_dict_does_not_poison_cache(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"iron_axe": 1})
        first = pick_loadout_cached(Gather("woodcutting"), state, gd)
        first["weapon_slot"] = "corrupted"
        again = pick_loadout_cached(Gather("woodcutting"), state, gd)
        assert again["weapon_slot"] == "iron_axe"

    def test_lru_bound_holds(self) -> None:
        gd = _gd()
        # Distinct EQUIPPABLE codes: only the equippable projection of the
        # inventory enters the key, so uncatalogued junk would collapse to one
        # entry instead of exercising the bound.
        for i in range(CACHE_MAX_ENTRIES + 1):
            code = f"axe_{i}"
            gd._item_stats[code] = ItemStats(code=code, level=1, type_="weapon",
                                             attack={"earth": 1})
            pick_loadout_cached(Gather("woodcutting"),
                                _make_state(inventory={"iron_axe": 1, code: 1}), gd)
        assert len(_caches[id(gd)]) == CACHE_MAX_ENTRIES

    def test_cache_is_dropped_with_its_gamedata(self) -> None:
        gd = _gd()
        pick_loadout_cached(Gather("woodcutting"), _make_state(inventory={"iron_axe": 1}), gd)
        key = id(gd)
        assert key in _caches
        del gd
        gc.collect()
        assert key not in _caches

    def test_distinct_gamedata_instances_do_not_collide(self) -> None:
        state = _make_state(inventory={"iron_axe": 1})
        gd_a = _gd()
        assert pick_loadout_cached(
            Gather("woodcutting"), state, gd_a)["weapon_slot"] == "iron_axe"
        gd_b = _gd()
        _poison(gd_b)
        fresh = pick_loadout_cached(Gather("woodcutting"), state, gd_b)
        assert fresh["weapon_slot"] != "iron_axe"


class TestHotCallersUseCache:
    """The two profiled hot paths must ride the memo: a poisoned catalog no
    longer changes their answer for an already-seen (purpose, state)."""

    def test_optimize_loadout_swap_plan_is_memoized(self) -> None:
        gd = _gd()
        state = _make_state(inventory={"iron_axe": 1})
        action = OptimizeLoadoutAction(target_skill="woodcutting")
        first_cost = action.cost(state, gd)
        assert first_cost > 0  # a swap is planned: iron_axe into weapon_slot
        _poison(gd)
        assert action.cost(state, gd) == first_cost
        assert action.is_applicable(state, gd)

    def test_gather_cost_is_memoized(self) -> None:
        gd = _gd()
        # Wrong tool equipped: pick_loadout(Gather) differs → penalty fires.
        state = _make_state(inventory={"iron_axe": 1},
                            equipment={"weapon_slot": "wooden_stick"})
        action = GatherAction(resource_code="ash_tree", locations=frozenset({(0, 0)}))
        first = action.cost(state, gd)
        _poison(gd)
        assert action.cost(state, gd) == first
