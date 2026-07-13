"""Keep-economy consumer migration (Task 5, spec 2026-06-28-gear-loadout-profiles).

The GEAR portion of every keep/recycle/deposit/sell protection is rerouted from
the `target_gear`/`target_tools` recipe-closure to the ACTIVE-PROFILE gear-demand
set (`gear_keep` = deduped per-code loadout demand ∪ the in-flight upgrade, +1
spare). NON-gear protection (tasks_coin, task_code, HP consumables, crafting/task
recipe materials) is UNCHANGED — `test_nongear_protection_unchanged` is the
regression lock.

The migration is threaded as an optional `gear_keep` map: `None` keeps the
legacy blanket equippable keep (so every pre-migration test is untouched); a
populated map switches to the profile-aware economy.
"""

from dataclasses import replace
from datetime import datetime, timezone

import pytest

from artifactsmmo_cli.ai.accumulation_sell import sellable_accumulation
from artifactsmmo_cli.ai.bank_selection import select_bank_deposits
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import useful_quantity_cap
from artifactsmmo_cli.ai.inventory_keep import destroyable, keep_in_bag
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles import active_profile_gear
from artifactsmmo_cli.ai.recycle_surplus import recyclable_surplus
from artifactsmmo_cli.ai.strategy_driver import _gear_protected
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.tiers.guards import SelectionContext, active_profile
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def make_state(**overrides: object) -> WorldState:
    """Self-contained WorldState builder (tests/ai has no shared fixtures pkg)."""
    eq = dict(_ALL_SLOTS)
    eq.update(overrides.pop("equipment", {}))  # type: ignore[arg-type]
    defaults: dict[str, object] = dict(
        character="Robby", level=5, xp=100, max_xp=500, hp=100, max_hp=150,
        gold=50, skills={}, x=0, y=0, inventory={}, inventory_max=20,
        inventory_slots_max=20,
        cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0, bank_items=None, bank_gold=None,
        bank_capacity=None, pending_items=None,
    )
    defaults.update(overrides)
    defaults["equipment"] = eq
    defaults["task_lifecycle_phase"] = derive_task_lifecycle_phase(
        defaults["task_code"], defaults["task_progress"], defaults["task_total"])  # type: ignore[arg-type]
    return WorldState(**defaults)  # type: ignore[arg-type]


def _gd() -> GameData:
    gd = GameData()
    gd._item_stats = {
        # Equippable, craftable gear (recyclable when surplus).
        "copper_dagger": ItemStats(code="copper_dagger", level=1, type_="weapon",
                                   crafting_skill="weaponcrafting", crafting_level=1),
        "copper_helmet": ItemStats(code="copper_helmet", level=1, type_="helmet",
                                   crafting_skill="gearcrafting", crafting_level=1),
        "copper_boots": ItemStats(code="copper_boots", level=1, type_="boots",
                                  crafting_skill="gearcrafting", crafting_level=1),
        "copper_ring": ItemStats(code="copper_ring", level=1, type_="ring",
                                 crafting_skill="jewelrycrafting", crafting_level=1),
        # NON-gear protected items.
        "copper_ore": ItemStats(code="copper_ore", level=1, type_="resource"),
        "copper_bar": ItemStats(code="copper_bar", level=1, type_="resource"),
        "cooked_chicken": ItemStats(code="cooked_chicken", level=1, type_="consumable",
                                    hp_restore=40),
        TASKS_COIN_CODE: ItemStats(code=TASKS_COIN_CODE, level=1, type_="currency"),
        "wooden_staff": ItemStats(code="wooden_staff", level=1, type_="weapon"),
    }
    gd._crafting_recipes = {
        "copper_dagger": {"copper_bar": 6},
        "copper_helmet": {"copper_bar": 6},
        "copper_boots": {"copper_bar": 8},
        "copper_ring": {"copper_bar": 4},
        "copper_bar": {"copper_ore": 10},
    }
    gd._workshop_locations = {"weaponcrafting": (1, 1), "gearcrafting": (2, 1),
                             "jewelrycrafting": (5, 1)}
    return gd


def _record_goal_cycle(history: LearningStore, selected_goal: str) -> None:
    history.record_cycle(Cycle(
        ts=datetime.now(tz=timezone.utc).isoformat(),
        session_id="t", cycle_index=0, character=history._character,
        selected_goal=selected_goal, action_repr="<none>",
        action_class="NoPlan", outcome="ok",
    ))


@pytest.fixture
def store(tmp_path) -> LearningStore:
    return LearningStore(db_path=str(tmp_path / "t.db"), character="Robby")


def _ctx(**kw: object):
    base: dict[str, object] = dict(
        bank_accessible=True, bank_required_level=0, bank_unlock_monster=None,
        initial_xp=0, task_exchange_min_coins=1, combat_monster=None)
    base.update(kw)
    return SelectionContext(**base)  # type: ignore[arg-type]


# --------------------------------------------------------------------------- #
# 1. Reclaim: un-profiled, not-in-flight gear becomes reclaimable.
# --------------------------------------------------------------------------- #
def test_unprofiled_gear_becomes_reclaimable():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 1})
    # gear_keep protects only copper_boots — copper_helmet is in NO profile and
    # not in-flight, so its keep drops to 0 → the held unit is reclaimable.
    gear_keep = {"copper_boots": 1}
    assert recyclable_surplus(state, gd, _ctx(gear_keep=gear_keep)) == {"copper_helmet": 1}
    # No profile info at all (legacy fallback): EQUIPPABLE_KEEP=1 → keep 1 → not
    # surplus. The keep authority reads BOTH modes off the ctx.
    assert recyclable_surplus(state, gd, _ctx()) == {}


# --------------------------------------------------------------------------- #
# 2. Profiled gear is kept up to demand: not recycled / banked / sold.
# --------------------------------------------------------------------------- #
def test_profiled_gear_protected():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1, "weaponcrafting": 1},
                       inventory={"copper_dagger": 2})
    gear_keep = {"copper_dagger": 2}  # a profile that wants 2 copper_dagger
    # Kept up to demand: cap == 2 (held 2 → no surplus).
    assert useful_quantity_cap("copper_dagger", state, gd, gear_keep=gear_keep) == 2
    assert recyclable_surplus(state, gd, _ctx(gear_keep=gear_keep)) == {}
    # Not DESTROYED: gear demand is an OWNERSHIP demand (GEAR_DEMAND feeds
    # keep_owned), so both copies must remain owned.
    ctx = SelectionContext(bank_accessible=True, bank_required_level=0,
                           bank_unlock_monster=None, initial_xp=0,
                           task_exchange_min_coins=0, combat_monster=None,
                           gear_keep=gear_keep)
    # Not SOLD either — the keep authority licenses nothing (Task 8).
    assert sellable_accumulation(state, gd, ctx) == {}
    assert destroyable("copper_dagger", state, gd, ctx) == 0
    # BANKING, though, is reversible — and deliberately NOT blanket-blocked (the
    # in-bag ladder has no GEAR_DEMAND arm, spec Task 1). The copy the character
    # actually fights with stays in the bag (COMBAT_WEAPON = 1); the profile's
    # SECOND copy is banked, still owned, and withdrawn when the loadout needs it.
    # Pinning it in the bag is what ate the slots this epic exists to free.
    assert keep_in_bag("copper_dagger", state, gd, ctx) == 1
    assert dict(select_bank_deposits(state, gd, ctx))["copper_dagger"] == 1


# --------------------------------------------------------------------------- #
# 3. In-flight upgrade (the pursued gear craft, +1 spare) is not recycled.
# --------------------------------------------------------------------------- #
def test_inflight_upgrade_not_recycled():
    gd = _gd()
    state = make_state(level=5, skills={"gearcrafting": 1},
                       inventory={"copper_helmet": 1})
    # copper_helmet is the in-flight upgrade (in no profile, keep=1 spare).
    gear_keep = {"copper_helmet": 1}
    assert useful_quantity_cap("copper_helmet", state, gd, gear_keep=gear_keep) == 1
    assert recyclable_surplus(state, gd, _ctx(gear_keep=gear_keep)) == {}


# --------------------------------------------------------------------------- #
# 4. Shared gear across two active profiles is kept ONCE (MAX-fold dedup).
# --------------------------------------------------------------------------- #
def test_shared_gear_kept_once(store: LearningStore):
    # Two active profiles both wear ONE copper_dagger → demand 1 (not 2).
    store.record_loadout_profile("combat:chicken",
                                 {"weapon_slot": "copper_dagger"})
    store.record_loadout_profile("gather:mining",
                                 {"ring1_slot": "copper_dagger"})
    _record_goal_cycle(store, "LevelSkill(mining->6)")
    gear = active_profile_gear(make_state(), _gd(), store,
                               combat_monster="chicken",
                               gather_skills=frozenset())
    assert gear["copper_dagger"] == 1


# --------------------------------------------------------------------------- #
# 5. REGRESSION LOCK: non-gear protection is byte-identical to pre-migration.
# --------------------------------------------------------------------------- #
def test_nongear_protection_unchanged():
    gd = _gd()
    state = make_state(
        level=5, skills={"gearcrafting": 1, "weaponcrafting": 1},
        inventory={TASKS_COIN_CODE: 12, "cooked_chicken": 8,
                   "copper_ore": 50, "copper_bar": 30, "iron_pick": 1},
        task_type="items", task_code="copper_helmet",
        task_total=10, task_progress=2,
        crafting_target="copper_dagger",
    )
    # A populated gear_keep must NOT change any NON-gear cap (gear_keep only
    # reroutes the EQUIPPABLE component).
    gear_keep = {"copper_dagger": 1, "copper_helmet": 1}
    nongear = [TASKS_COIN_CODE, "cooked_chicken", "copper_ore", "copper_bar"]
    for code in nongear:
        assert (useful_quantity_cap(code, state, gd, gear_keep=gear_keep)
                == useful_quantity_cap(code, state, gd)), code

    # The bank keep CAPS of the NON-gear members are identical with vs without a
    # gear profile, and every one of them is strictly protected: task item, task
    # coins, HP consumables, and the crafting-target + task recipe materials.
    # (`gear_keep` only reroutes the EQUIPPABLE component, which the in-bag ladder
    # does not read at all.)
    base_ctx = SelectionContext(bank_accessible=True, bank_required_level=0,
                                bank_unlock_monster=None, initial_xp=0,
                                task_exchange_min_coins=0, combat_monster=None)
    profile_ctx = replace(base_ctx, gear_keep=gear_keep)
    for code in (TASKS_COIN_CODE, "copper_helmet", "cooked_chicken",
                 "copper_ore", "copper_bar"):
        legacy = keep_in_bag(code, state, gd, base_ctx)
        profiled = keep_in_bag(code, state, gd, profile_ctx)
        assert legacy == profiled, code
        assert legacy > 0, code


# --------------------------------------------------------------------------- #
# Wiring: protected-set source + finished-gear deposit/discard floor.
# --------------------------------------------------------------------------- #
def test_gear_protected_source_switches_with_profile_presence():
    # Profiles present → the protected set is the active-profile gear set.
    ctx = _ctx(gear_keep={"copper_dagger": 1},
               target_gear=frozenset({"copper_boots"}))
    assert _gear_protected(ctx) == frozenset({"copper_dagger"})
    # No profile info → legacy target_gear|target_tools fallback.
    legacy = _ctx(target_gear=frozenset({"copper_boots"}),
                  target_tools=frozenset({"iron_pick"}))
    assert _gear_protected(legacy) == frozenset({"copper_boots", "iron_pick"})


def test_active_profile_protects_finished_profile_gear():
    gd = _gd()
    state = make_state(skills={"weaponcrafting": 1}, inventory={"copper_dagger": 1})
    # A profile that wants 2 copper_dagger → the finished gear is floored at 2 in
    # the active profile so deposit/discard never bank/delete it below 2.
    profile = active_profile(state, gd, _ctx(gear_keep={"copper_dagger": 2}))
    assert profile["copper_dagger"] == 2
