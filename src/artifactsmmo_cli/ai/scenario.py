"""Synthetic planner scenarios: a mock character + the real game catalog.

Phase 1 of the progression-tree spec (docs/superpowers/specs/
2026-07-06-progression-tree-design.md): golden scenario tests and the
`plan --scenario` CLI share these fixtures, so a planner change can be
exercised offline against realistic data before it ever runs live."""

import json
from dataclasses import dataclass, field
from pathlib import Path

from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.task_lifecycle import derive_task_lifecycle_phase
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, SKILL_NAMES, WorldState


@dataclass(frozen=True)
class ScenarioCharacter:
    """A synthetic character for offline planning. Only game-legal values:
    item codes are validated against the catalog by the scenario tests."""
    name: str
    level: int = 1
    hp: int | None = None          # None -> max_hp
    max_hp: int = 120
    gold: int = 0
    skills: dict[str, int] = field(default_factory=dict)
    equipment: dict[str, str] = field(default_factory=dict)  # slot -> code
    inventory: dict[str, int] = field(default_factory=dict)
    inventory_max: int = 100
    bank: dict[str, int] | None = field(default_factory=dict)  # None = unknown
    task: tuple[str, str, int, int] | None = None  # code, type, progress, total
    description: str = ""


def scenario_state(sc: ScenarioCharacter) -> WorldState:
    equipment: dict[str, str | None] = {slot: None for slot in EQUIPMENT_SLOTS}
    equipment.update(sc.equipment)
    # Every real character carries all 8 craft/gathering skills starting at
    # level 1 (world_state._fetch_world_state loops SKILL_NAMES with no
    # omissions) — a scenario that only sets the skills it cares about must
    # still produce a state with every key present, or planner code that
    # indexes state.skills[skill] unconditionally (a sound assumption against
    # live data) raises KeyError.
    skills: dict[str, int] = {name: 1 for name in SKILL_NAMES}
    skills.update(sc.skills)
    task_code, task_type, progress, total = sc.task or (None, None, 0, 0)
    return WorldState(
        character=sc.name, level=sc.level, xp=0, max_xp=100,
        hp=sc.hp if sc.hp is not None else sc.max_hp, max_hp=sc.max_hp,
        gold=sc.gold, skills=skills, x=0, y=0,
        inventory=dict(sc.inventory), inventory_max=sc.inventory_max,
        equipment=equipment, cooldown_expires=None,
        task_code=task_code, task_type=task_type,
        task_progress=progress, task_total=total,
        task_lifecycle_phase=derive_task_lifecycle_phase(task_code, progress, total),
        bank_items=dict(sc.bank) if sc.bank is not None else None,
        bank_gold=0 if sc.bank is not None else None,
        bank_capacity=200 if sc.bank is not None else None,
        pending_items=None,
    )


def load_bundle_game_data(path: Path) -> GameData:
    return GameData.from_cache_bundle(json.loads(path.read_text()))


_COPPER_SET = {
    "weapon_slot": "copper_dagger", "helmet_slot": "copper_helmet",
    "body_armor_slot": "copper_armor", "leg_armor_slot": "copper_legs_armor",
    "boots_slot": "copper_boots", "ring1_slot": "copper_ring",
    "ring2_slot": "copper_ring",
}

SCENARIOS: dict[str, ScenarioCharacter] = {
    "l1_fresh": ScenarioCharacter(
        name="l1_fresh", level=1, max_hp=120,
        description="Fresh start: nothing owned — trunk begins, xp branch, starter monster."),
    "l8_overstocked": ScenarioCharacter(
        name="l8_overstocked", level=8, max_hp=200,
        skills={"mining": 5, "woodcutting": 5},
        equipment=dict(_COPPER_SET),
        inventory={"feather": 90, "raw_chicken": 6}, inventory_max=100,
        description="96/100 bag of loot — the deposit guard must preempt."),
    "l10_copper_adequate": ScenarioCharacter(
        name="l10_copper_adequate", level=10, max_hp=240,
        skills={"mining": 10, "woodcutting": 10, "weaponcrafting": 10,
                "gearcrafting": 10, "alchemy": 5},
        equipment=dict(_COPPER_SET),
        bank={"sunflower": 20},
        description="Band-adequate copper set, empty utility slots, potion mats banked."),
    "l10_weapon_upgrade": ScenarioCharacter(
        name="l10_weapon_upgrade", level=10, max_hp=240,
        skills={"mining": 10, "weaponcrafting": 10},
        equipment={**_COPPER_SET, "weapon_slot": "wooden_stick"},
        bank={"iron_ore": 60, "copper_ore": 20},
        description="Weapon slot lags a tier; upgrade mats banked — gear branch."),
    "l3_low_hp": ScenarioCharacter(
        name="l3_low_hp", level=3, hp=20, max_hp=80,
        description="Critical HP — the survival guard preempts every branch."),
    "l12_taskgated_bag": ScenarioCharacter(
        name="l12_taskgated_bag", level=12, max_hp=260,
        skills={"gearcrafting": 10},
        equipment=dict(_COPPER_SET),
        bank={"cowhide": 5, "feather": 2},
        description="Satchel mats banked, 0 tasks_coin — the task-funding chain."),

    # --- Per-band trunk liveness net (docs/superpowers/specs/
    # 2026-07-06-progression-tree-design.md Phase 1, deferred to this pass):
    # one scenario per trunk band, each a plausible character ENTERING that
    # band slightly under-tier — the gear branch always has a reachable
    # target (so band_adequate is False: has_structural_upgrade is true in
    # every one of these), while the xp/trunk branch survives as a
    # decide_tree fallback. See tests/test_ai/scenarios/test_band_liveness.py.
    "l15_midband": ScenarioCharacter(
        name="l15_midband", level=15, max_hp=300, gold=50,
        skills={"mining": 12, "woodcutting": 12, "weaponcrafting": 10,
                "gearcrafting": 10, "fishing": 10, "cooking": 10,
                "alchemy": 6, "jewelrycrafting": 6},
        equipment={
            "weapon_slot": "iron_dagger", "helmet_slot": "iron_helm",
            "body_armor_slot": "iron_armor", "leg_armor_slot": "iron_legs_armor",
            "boots_slot": "iron_boots", "ring1_slot": "iron_ring",
            "shield_slot": "iron_shield",
        },
        bank={"iron_ore": 15, "spruce_wood": 10, "feather": 5, "wolf_bone": 3},
        inventory_max=120,
        description="Mid L10-20 band: full iron (L10) set, L15 upgrades on offer."),
    "l20_band_entry": ScenarioCharacter(
        name="l20_band_entry", level=20, max_hp=360, gold=100,
        skills={"mining": 18, "woodcutting": 18, "weaponcrafting": 15,
                "gearcrafting": 15, "fishing": 15, "cooking": 15,
                "alchemy": 10, "jewelrycrafting": 10},
        equipment={
            "weapon_slot": "highwayman_dagger", "helmet_slot": "lucky_wizard_hat",
            "body_armor_slot": "mushmush_jacket", "leg_armor_slot": "adventurer_pants",
            "boots_slot": "adventurer_boots", "ring1_slot": "air_ring",
            "amulet_slot": "wisdom_amulet",
        },
        bank={"coal": 10, "wolf_bone": 5, "wolf_hair": 5, "green_cloth": 5},
        inventory_max=130,
        description="Entering L20-30 band: L15 gear, L20 upgrades on offer."),
    "l30_band_entry": ScenarioCharacter(
        name="l30_band_entry", level=30, max_hp=480, gold=200,
        skills={"mining": 28, "woodcutting": 28, "weaponcrafting": 25,
                "gearcrafting": 25, "fishing": 25, "cooking": 25,
                "alchemy": 18, "jewelrycrafting": 18},
        equipment={
            "weapon_slot": "dreadful_staff", "helmet_slot": "piggy_helmet",
            "body_armor_slot": "bandit_armor", "leg_armor_slot": "piggy_pants",
            "boots_slot": "hard_leather_boots", "ring1_slot": "ring_of_the_adept",
            "amulet_slot": "emerald_amulet",
        },
        bank={"gold_ore": 15, "sap": 5, "red_cloth": 5},
        inventory_max=140,
        description="Entering L30-40 band: L25 gear (L20 boots — no L25 boots "
                     "exist in the catalog), L30 upgrades on offer."),
    "l40_band_entry": ScenarioCharacter(
        name="l40_band_entry", level=40, max_hp=600, gold=400,
        skills={"mining": 38, "woodcutting": 38, "weaponcrafting": 35,
                "gearcrafting": 35, "fishing": 35, "cooking": 35,
                "alchemy": 25, "jewelrycrafting": 25},
        equipment={
            "weapon_slot": "cursed_sceptre", "helmet_slot": "strangold_helmet",
            "body_armor_slot": "strangold_armor", "leg_armor_slot": "strangold_legs_armor",
            "boots_slot": "enchanter_boots", "ring1_slot": "malefic_ring",
            "amulet_slot": "corrupted_stone_amulet",
        },
        bank={"mithril_ore": 10, "magic_wood": 5},
        inventory_max=150,
        description="Entering L40-50 band: L35 gear, L40 upgrades on offer."),
    "l48_capstone_approach": ScenarioCharacter(
        name="l48_capstone_approach", level=48, max_hp=690, gold=800,
        skills={"mining": 46, "woodcutting": 46, "weaponcrafting": 42,
                "gearcrafting": 42, "fishing": 42, "cooking": 42,
                "alchemy": 35, "jewelrycrafting": 35},
        equipment={
            "weapon_slot": "mithril_sword", "helmet_slot": "mithril_helm",
            "body_armor_slot": "mithril_platebody", "leg_armor_slot": "mithril_platelegs",
            "boots_slot": "mithril_boots", "ring1_slot": "mithril_ring",
            "amulet_slot": "greater_sapphire_amulet",
        },
        bank={"adamantite_ore": 5, "mithril_ore": 10},
        inventory_max=150,
        description="Approaching the L50 capstone: L40 gear, L45 upgrades on "
                     "offer — empirical capstone-reachability evidence."),
}
