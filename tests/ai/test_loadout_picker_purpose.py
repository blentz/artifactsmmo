"""pick_loadout(Combat(m)) reproduces the old per-monster pick exactly; Gather equips a tool.

These are the regression-lock + new-behavior tests for Task 2 (generalize pick_loadout to purpose).
The combat assertions are hardcoded against the ACTUAL old per-slot picks (computed from
weapon_score / armor_score directly), not tautologies.
"""

from artifactsmmo_cli.ai.equipment.loadout_picker import pick_loadout
from artifactsmmo_cli.ai.equipment.scoring import armor_score, weapon_score
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.gear_value_core import Combat, Gather
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
    level: int = 1,
    inventory: dict[str, int] | None = None,
    equipment: dict[str, str | None] | None = None,
) -> WorldState:
    """Minimal WorldState for pick_loadout tests. `equipment` is merged with all-None defaults."""
    eq = dict(_ALL_SLOTS)
    if equipment:
        eq.update(equipment)
    return WorldState(
        character="testchar", level=level, xp=0, max_xp=100,
        hp=100, max_hp=100, gold=0, skills={}, x=0, y=0,
        inventory=inventory or {}, inventory_max=20,
        equipment=eq, cooldown_expires=None,
        task_code=None, task_type=None, task_progress=0, task_total=0,
        task_lifecycle_phase=derive_task_lifecycle_phase(None, 0, 0),
        bank_items=None, bank_gold=None, bank_capacity=None, pending_items=None,
    )


def _gd_combat() -> GameData:
    """GameData fixture for combat regression tests (yellow_slime vs owned gear)."""
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        "fishing_net": ItemStats(code="fishing_net", level=1, type_="weapon", subtype="tool",
                                 attack={"water": 5}, skill_effects={"fishing": -10}),
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
        "water_robe": ItemStats(code="water_robe", level=1, type_="body_armor",
                                resistance={"water": 20}),
    }
    gd._monster_attack = {
        "yellow_slime": {"earth": 8, "fire": 0, "water": 0, "air": 0},
    }
    gd._monster_resistance = {
        "yellow_slime": {"earth": 25, "fire": 0, "water": 0, "air": 0},
    }
    return gd


def _gd_gather() -> GameData:
    """GameData fixture for gather-purpose tests (woodcutting tools)."""
    gd = GameData()
    gd._item_stats = {
        "wooden_stick": ItemStats(code="wooden_stick", level=1, type_="weapon",
                                  attack={"earth": 4}),
        "weak_axe": ItemStats(code="weak_axe", level=1, type_="weapon", subtype="tool",
                              attack={"earth": 2}, skill_effects={"woodcutting": -3}),
        "strong_axe": ItemStats(code="strong_axe", level=1, type_="weapon", subtype="tool",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10}),
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
    }
    # No monster data needed for gather tests.
    return gd


# ---------------------------------------------------------------------------
# Combat regression: pick_loadout(Combat(m)) == old pick_loadout(m)
# ---------------------------------------------------------------------------


def test_combat_purpose_weapon_slot_picks_same_as_legacy() -> None:
    """Regression lock: pick_loadout(Combat) picks fishing_net over wooden_stick vs
    yellow_slime — the same choice the old per-monster scorer made.

    Old weapon_score values (hardcoded, not re-derived from the function-under-test):
      fishing_net: water atk=5 vs water_res=0 → raw=5*100*200=100000 → score=2*100000=200000 (tool)
      wooden_stick: earth atk=4 vs earth_res=25 → raw=4*75*200=60000 → score=2*60000+1=120001 (non-tool)
    Legacy pick = fishing_net.  Generalized picker must agree.
    """
    gd = _gd_combat()
    m_atk = gd.monster_attack("yellow_slime")
    m_res = gd.monster_resistance("yellow_slime")

    # Verify the hardcoded expected values against the scorers (regression-lock sanity).
    stats = gd._item_stats
    assert weapon_score(stats["fishing_net"], m_res) == 200000
    assert weapon_score(stats["wooden_stick"], m_res) == 120001
    assert weapon_score(stats["fishing_net"], m_res) > weapon_score(stats["wooden_stick"], m_res)

    state = _make_state(
        level=1,
        inventory={"fishing_net": 1},
        equipment={"weapon_slot": "wooden_stick"},
    )
    purpose = Combat(m_atk, m_res)
    result = pick_loadout(purpose, state, gd)
    assert result["weapon_slot"] == "fishing_net"


def test_combat_purpose_armor_slot_picks_same_as_legacy() -> None:
    """Regression lock: armor slot picks leather_armor (earth resist 10) over water_robe
    (water resist 20) vs an earth-attacking yellow_slime.

    Old armor_score values (hardcoded):
      leather_armor: earth_atk=8 * earth_res=10 = 80
      water_robe: water_atk=0 * water_res=20 = 0
    Legacy pick = leather_armor.  Generalized picker must agree.
    """
    gd = _gd_combat()
    m_atk = gd.monster_attack("yellow_slime")
    m_res = gd.monster_resistance("yellow_slime")

    stats = gd._item_stats
    assert armor_score(stats["leather_armor"], m_atk) == 80
    assert armor_score(stats["water_robe"], m_atk) == 0

    state = _make_state(
        level=1,
        inventory={"leather_armor": 1, "water_robe": 1},
        equipment={"body_armor_slot": None},
    )
    purpose = Combat(m_atk, m_res)
    result = pick_loadout(purpose, state, gd)
    assert result["body_armor_slot"] == "leather_armor"


def test_combat_purpose_no_improvement_keeps_current() -> None:
    """pick_loadout(Combat) keeps the current item when nothing better is owned."""
    gd = _gd_combat()
    m_atk = gd.monster_attack("yellow_slime")
    m_res = gd.monster_resistance("yellow_slime")
    state = _make_state(
        level=1,
        inventory={},
        equipment={"weapon_slot": "wooden_stick"},
    )
    result = pick_loadout(Combat(m_atk, m_res), state, gd)
    assert result["weapon_slot"] == "wooden_stick"


# ---------------------------------------------------------------------------
# Gather purpose: pick_loadout(Gather(skill)) equips best tool
# ---------------------------------------------------------------------------


def test_gather_purpose_equips_best_tool_over_combat_weapon() -> None:
    """pick_loadout(Gather("woodcutting")) swaps a combat weapon for a gather tool."""
    gd = _gd_gather()
    state = _make_state(
        level=1,
        inventory={"strong_axe": 1},
        equipment={"weapon_slot": "wooden_stick"},
    )
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["weapon_slot"] == "strong_axe"


def test_gather_purpose_picks_most_negative_skill_effect() -> None:
    """pick_loadout(Gather) prefers the axe with the stronger (more-negative) skill_effect."""
    gd = _gd_gather()
    state = _make_state(
        level=1,
        inventory={"weak_axe": 1, "strong_axe": 1},
        equipment={"weapon_slot": None},
    )
    result = pick_loadout(Gather("woodcutting"), state, gd)
    # strong_axe: -10 → benefit 10 > weak_axe: -3 → benefit 3
    assert result["weapon_slot"] == "strong_axe"


def test_gather_purpose_no_tool_keeps_current_weapon() -> None:
    """If no gather tool is owned for the skill, the current combat weapon stays."""
    gd = _gd_gather()
    state = _make_state(
        level=1,
        inventory={},
        equipment={"weapon_slot": "wooden_stick"},
    )
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["weapon_slot"] == "wooden_stick"


def test_gather_purpose_armor_slots_unchanged() -> None:
    """For a Gather purpose, armor slots keep their current item.

    Armor items have no skill_effects so their gather benefit is 0.
    An occupied slot needs a strictly better candidate (> 0) to swap — none exist.
    An empty slot has best_score <= 0 so the empty-slot gate fires — stays empty.
    """
    gd = _gd_gather()
    state = _make_state(
        level=1,
        inventory={"strong_axe": 1},
        equipment={"weapon_slot": "wooden_stick", "body_armor_slot": "leather_armor"},
    )
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["weapon_slot"] == "strong_axe"
    assert result["body_armor_slot"] == "leather_armor"


def test_gather_purpose_empty_armor_slots_stay_empty() -> None:
    """Empty armor slots are not filled for a Gather purpose (benefit=0 → skip gate)."""
    gd = _gd_gather()
    state = _make_state(
        level=1,
        inventory={"strong_axe": 1, "leather_armor": 1},
        equipment={"weapon_slot": None, "body_armor_slot": None},
    )
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["weapon_slot"] == "strong_axe"
    assert result["body_armor_slot"] is None


# ---------------------------------------------------------------------------
# Gather purpose: artifact utility-fill branch
# ---------------------------------------------------------------------------


def _gd_gather_artifact() -> GameData:
    """Gather fixture with a tool, armor, and two utility artifacts."""
    gd = GameData()
    gd._item_stats = {
        "strong_axe": ItemStats(code="strong_axe", level=1, type_="weapon", subtype="tool",
                                attack={"earth": 3}, skill_effects={"woodcutting": -10}),
        "leather_armor": ItemStats(code="leather_armor", level=1, type_="body_armor",
                                   resistance={"earth": 10}),
        "novice_guide": ItemStats(code="novice_guide", level=1, type_="artifact",
                                  hp_bonus=25, wisdom=25, prospecting=25),
        "lucky_charm": ItemStats(code="lucky_charm", level=1, type_="artifact",
                                 wisdom=10, prospecting=10),
    }
    return gd


def test_gather_fills_empty_artifact_slot() -> None:
    """MUTATION KILLER: a gather re-arm fills an empty artifact slot with an owned
    utility artifact. novice_guide flat utility = hp_bonus 25 + wisdom 25 +
    prospecting 25 = 75 > 0, so the empty-slot gate passes. The mutant that
    reverts the artifact branch to -gather_score (0) leaves the slot empty."""
    gd = _gd_gather_artifact()
    assert armor_score(gd._item_stats["novice_guide"], {}) == 75
    state = _make_state(level=1, inventory={"novice_guide": 1},
                        equipment={"artifact1_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["artifact1_slot"] == "novice_guide"


def test_gather_picks_best_utility_artifact() -> None:
    """Under Gather, artifacts argmax on flat utility (not an arbitrary 0-0 tie):
    novice_guide (75) takes the first artifact slot, lucky_charm (20) the next."""
    gd = _gd_gather_artifact()
    state = _make_state(level=1, inventory={"novice_guide": 1, "lucky_charm": 1},
                        equipment={"artifact1_slot": None, "artifact2_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["artifact1_slot"] == "novice_guide"
    assert result["artifact2_slot"] == "lucky_charm"


def test_gather_artifact_branch_leaves_armor_empty() -> None:
    """The utility-fill branch is artifact-ONLY. Empty armor with owned hp-bonus
    armor (flat utility 30 > 0) still stays empty under Gather — armor is not a
    fill type, so it keeps the proven -gather_score (0) benefit."""
    gd = _gd_gather_artifact()
    gd._item_stats["padded_vest"] = ItemStats(code="padded_vest", level=1,
                                              type_="body_armor", hp_bonus=30)
    state = _make_state(level=1, inventory={"padded_vest": 1},
                        equipment={"body_armor_slot": None})
    result = pick_loadout(Gather("woodcutting"), state, gd)
    assert result["body_armor_slot"] is None


def test_combat_fills_empty_artifact_slot_unchanged() -> None:
    """Regression: Combat already fills artifacts (armor_score includes flat
    utility). The Gather-branch edit must not change the Combat path."""
    gd = _gd_gather_artifact()
    state = _make_state(level=1, inventory={"novice_guide": 1},
                        equipment={"artifact1_slot": None})
    result = pick_loadout(Combat({"earth": 0}, {"earth": 0}), state, gd)
    assert result["artifact1_slot"] == "novice_guide"
