"""Tests for active loadout-profile resolution (Task 3).

Fixture layout:
  - "combat:chicken" profile  (activated by current combat_monster parameter)
  - "gather:mining"  profile  (activated by recent LevelSkill(mining->…) cycle)
  - "combat:wolf"    profile  (not current, not recent → excluded)
"""

import pytest
from datetime import datetime, timezone

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.learning.models import Cycle
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.loadout_profiles import (
    active_bank_space_cost,
    active_loadouts,
    active_profile_gear,
    active_task_keys,
    combat_key,
    gather_key,
)
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import WorldState

_ALL_SLOTS: dict[str, str | None] = {
    "weapon_slot": None, "shield_slot": None, "helmet_slot": None,
    "body_armor_slot": None, "leg_armor_slot": None, "boots_slot": None,
    "ring1_slot": None, "ring2_slot": None, "amulet_slot": None,
    "artifact1_slot": None, "artifact2_slot": None, "artifact3_slot": None,
    "utility1_slot": None, "utility2_slot": None, "bag_slot": None, "rune_slot": None,
}


def _make_state(**kwargs: object) -> WorldState:
    eq = dict(_ALL_SLOTS)
    eq.update(kwargs.pop("equipment", {}))  # type: ignore[arg-type]
    return WorldState(
        character="Robby", level=5, xp=100, max_xp=500,
        hp=100, max_hp=100, gold=0, skills={}, x=0, y=0,
        inventory={}, inventory_max=20, equipment=eq,
        cooldown_expires=None, task_code=None, task_type=None,
        task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _record_goal_cycle(history: LearningStore, selected_goal: str) -> None:
    """Insert a minimal Cycle row to seed the recent-goal window."""
    history.record_cycle(Cycle(
        ts=datetime.now(tz=timezone.utc).isoformat(),
        session_id="test-session",
        cycle_index=0,
        character=history._character,
        selected_goal=selected_goal,
        action_repr="<none>",
        action_class="NoPlan",
        outcome="ok",
    ))


@pytest.fixture
def profiles_fixture(tmp_path):
    """LearningStore with three profiles; only two should be active in the tests."""
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="Robby")
    # chicken: weapon=wooden_stick, ring1=copper_dagger (shared with mining for dedup test)
    history.record_loadout_profile(
        "combat:chicken",
        {"weapon_slot": "wooden_stick", "ring1_slot": "copper_dagger"},
    )
    # mining: weapon=copper_dagger (shared slot/code → dedup to 1)
    history.record_loadout_profile(
        "gather:mining",
        {"weapon_slot": "copper_dagger"},
    )
    # wolf: should NOT appear — no matching current objective or recent cycle
    history.record_loadout_profile(
        "combat:wolf",
        {"weapon_slot": "wolf_only_gear"},
    )
    # Seed a recent cycle so "gather:mining" appears in the recent window.
    # _recent_task_keys parses "LevelSkill(<skill>->...)" → "gather:<skill>".
    history.start_session()
    _record_goal_cycle(history, "LevelSkill(mining->5)")
    yield _make_state(), GameData(), history
    history.close()


# ── key helpers ────────────────────────────────────────────────────────────────

def test_combat_key():
    assert combat_key("chicken") == "combat:chicken"


def test_gather_key():
    assert gather_key("mining") == "gather:mining"


# ── active_task_keys ───────────────────────────────────────────────────────────

def test_active_task_keys_current_combat(tmp_path):
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    keys = active_task_keys(history, combat_monster="chicken", gather_skills=frozenset())
    assert "combat:chicken" in keys
    history.close()


def test_active_task_keys_current_gather(tmp_path):
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    keys = active_task_keys(history, combat_monster=None,
                            gather_skills=frozenset({"mining", "woodcutting"}))
    assert "gather:mining" in keys
    assert "gather:woodcutting" in keys
    history.close()


def test_active_task_keys_picks_up_recent_level_skill(tmp_path):
    """A recent LevelSkill(<skill>-><n>) cycle contributes gather:<skill>."""
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    history.start_session()
    _record_goal_cycle(history, "LevelSkill(woodcutting->3)")
    keys = active_task_keys(history, combat_monster=None, gather_skills=frozenset())
    assert "gather:woodcutting" in keys
    history.close()


def test_active_task_keys_picks_up_recent_grind(tmp_path):
    """A recent GrindCharacterXP(<m>) cycle contributes combat:<m>."""
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    history.start_session()
    _record_goal_cycle(history, "GrindCharacterXP(yellow_slime)")
    keys = active_task_keys(history, combat_monster=None, gather_skills=frozenset())
    assert "combat:yellow_slime" in keys
    history.close()


def test_active_task_keys_excludes_old_grind(tmp_path):
    """GrindCharacterXP cycles beyond RECENT_PROFILE_WINDOW are not active."""
    from artifactsmmo_cli.ai.loadout_profiles import RECENT_PROFILE_WINDOW
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    history.start_session()
    # Insert RECENT_PROFILE_WINDOW + 1 other cycles to push wolf out of the window
    for _ in range(RECENT_PROFILE_WINDOW + 1):
        _record_goal_cycle(history, "SomeOtherGoal()")
    _record_goal_cycle(history, "GrindCharacterXP(wolf)")
    # wolf cycle is beyond the window when ordering by id desc (oldest)
    history.start_session()
    for _ in range(RECENT_PROFILE_WINDOW):
        _record_goal_cycle(history, "GrindCharacterXP(chicken)")
    keys = active_task_keys(history, combat_monster=None, gather_skills=frozenset())
    assert "combat:wolf" not in keys
    history.close()


# ── active_loadouts ────────────────────────────────────────────────────────────

def test_active_includes_current_objective_and_recent(profiles_fixture):
    """combat:chicken (current) + gather:mining (recent) active; wolf excluded."""
    state, game_data, history = profiles_fixture
    loadouts = active_loadouts(state, game_data, history,
                               combat_monster="chicken", gather_skills=frozenset())
    assert any("wooden_stick" in lout.values() for lout in loadouts)   # chicken
    assert any("copper_dagger" in lout.values() for lout in loadouts)  # mining (recent)
    assert all("wolf_only_gear" not in lout.values() for lout in loadouts)


def test_active_loadouts_no_match_returns_empty(tmp_path):
    """If no stored profiles match active keys, active_loadouts is empty."""
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    result = active_loadouts(_make_state(), GameData(), history,
                             combat_monster="dragon", gather_skills=frozenset())
    assert result == []
    history.close()


# ── active_profile_gear ────────────────────────────────────────────────────────

def test_active_profile_gear_dedups(profiles_fixture):
    """copper_dagger in both chicken + mining profiles → demand 1, not 2."""
    state, game_data, history = profiles_fixture
    gear = active_profile_gear(state, game_data, history,
                               combat_monster="chicken",
                               gather_skills=frozenset({"mining"}))
    assert gear.get("copper_dagger", 0) == 1   # shared across profiles -> 1


def test_active_profile_gear_empty_when_no_profiles(tmp_path):
    history = LearningStore(db_path=str(tmp_path / "t.db"), character="X")
    gear = active_profile_gear(_make_state(), GameData(), history,
                               combat_monster=None, gather_skills=frozenset())
    assert gear == {}
    history.close()


# ── active_bank_space_cost ─────────────────────────────────────────────────────

def test_active_bank_space_cost_excludes_equipped(profiles_fixture):
    """Items already equipped do not count toward bank space cost."""
    state, game_data, history = profiles_fixture
    # Equip wooden_stick so it's not a bank cost
    eq = dict(_ALL_SLOTS)
    eq["weapon_slot"] = "wooden_stick"
    state_with_eq = _make_state(equipment={"weapon_slot": "wooden_stick"})
    # Active profiles (chicken+mining) hold: wooden_stick, copper_dagger
    # Equipped: wooden_stick → only copper_dagger needs bank space = 1
    cost = active_bank_space_cost(state_with_eq, game_data, history,
                                  combat_monster="chicken",
                                  gather_skills=frozenset({"mining"}))
    assert cost == 1
