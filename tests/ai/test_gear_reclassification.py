"""Approved behavior changes: rune/artifact join combat gear; ring/amulet/rune/artifact
use per-monster scoring in the dominance gate.
Spec: docs/superpowers/plans/2026-06-28-gear-taxonomy.md
(The PRIOR_COMBAT_GEAR consumer tests died with the flat ranking —
progression-tree Phase 4b Task 2.)
"""

import artifactsmmo_cli.ai.combat_targets as ct
from artifactsmmo_cli.ai.combat_targets import _clear_cache
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.inventory_caps import _is_equippable_dominated
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState


def _make_state(**overrides) -> WorldState:
    """Minimal WorldState for reclassification tests."""
    defaults: dict = dict(
        character="testchar",
        level=5,
        xp=100,
        max_xp=500,
        hp=100,
        max_hp=150,
        gold=50,
        skills={"mining": 3, "woodcutting": 2, "fishing": 1, "weaponcrafting": 1,
                "gearcrafting": 1, "jewelrycrafting": 1, "cooking": 1, "alchemy": 1},
        x=0,
        y=0,
        inventory={},
        inventory_max=20,
        inventory_slots_max=20,
        equipment={slot: None for slot in EQUIPMENT_SLOTS},
        cooldown_expires=None,
        task_code=None,
        task_type=None,
        task_progress=0,
        task_total=0,
        bank_items=None,
        bank_gold=None,
        bank_capacity=None,
        pending_items=None,
    )
    defaults.update(overrides)
    defaults.setdefault(
        "task_lifecycle_phase",
        derive_task_lifecycle_phase(
            defaults["task_code"], defaults["task_progress"], defaults["task_total"]
        ),
    )
    return WorldState(**defaults)


def _gd(items, consumable_codes=None):
    gd = GameData()
    for s in items:
        gd._item_stats[s.code] = s
    gd._consumable_effect_codes = consumable_codes or {}
    return gd


# --- GameData property tests (GREEN from Task 3; regression guard) ---


def test_rune_and_artifact_are_combat_gear():
    rune = ItemStats(code="vampiric_rune", level=1, type_="rune", lifesteal=10)
    artifact = ItemStats(code="novice_guide", level=1, type_="artifact", hp_bonus=25)
    gd = _gd([rune, artifact])
    assert "rune" in gd.combat_gear_types
    assert "artifact" in gd.combat_gear_types


def test_ring_amulet_are_defensive_for_dominance_gate():
    ring = ItemStats(code="r", level=1, type_="ring", hp_bonus=5)
    amulet = ItemStats(code="a", level=1, type_="amulet", resistance={"fire": 10})
    gd = _gd([ring, amulet])
    assert {"ring", "amulet"} <= gd.defensive_gear_types


# --- Consumer test: inventory_caps.py per-monster for rings ---
# RED before Step 2 implementation: ring not in _ARMOR_TYPES → scalar equip_value →
# attack_ring (equip_value=10) dominates resist_ring (equip_value=5).
# GREEN after: per-monster → attack_ring armor_score=0, does NOT dominate resist_ring.


def test_ring_per_monster_not_dominated_by_attack_ring(monkeypatch):
    """After reclassification, rings use per-monster scoring when monsters exist.
    Two attack_rings (filling both ring slots by count) would dominate the resist_ring
    under old scalar equip_value (attack 10 > resist 5). Under new per-monster scoring,
    the attack_ring scores armor_score=0 defensively and does NOT pareto-dominate the
    resist_ring (armor_score=5*20=100). Ring has 2 slots so peer_count=2 is used.
    Spec: docs/superpowers/plans/2026-06-28-gear-taxonomy.md
    """
    _clear_cache()
    gd = GameData()
    gd._item_stats = {
        "attack_ring": ItemStats(code="attack_ring", level=1, type_="ring",
                                  attack={"fire": 10}),
        "resist_ring": ItemStats(code="resist_ring", level=1, type_="ring",
                                  resistance={"fire": 5}),
    }
    gd._monster_level = {"fire_slime": 1}
    gd._monster_attack = {"fire_slime": {"fire": 20}}
    # A tile, so the monster survives combat_target_monsters' spawn gate. The gate
    # drops catalog monsters that spawn nowhere (raid bosses, dormant event
    # content); without a tile this fixture's monster vanishes and the per-monster
    # comparison below has nothing to compare against.
    gd._monster_locations = {"fire_slime": [(0, 0)]}
    monkeypatch.setattr(ct, "is_winnable", lambda s, g, c, h=None: True)
    # 2 attack_rings fills both ring slots by count — enough to scalar-dominate in old code.
    state = _make_state(inventory={"attack_ring": 2, "resist_ring": 1})
    # Per-monster: resist_ring armor_score = 5*20=100; attack_ring armor_score = 0.
    # attack_ring does NOT pareto-dominate resist_ring → resist_ring is NOT dominated.
    assert _is_equippable_dominated("resist_ring", state, gd) is False
