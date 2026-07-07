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
from artifactsmmo_cli.ai.world_state import EQUIPMENT_SLOTS, WorldState


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
    task_code, task_type, progress, total = sc.task or (None, None, 0, 0)
    return WorldState(
        character=sc.name, level=sc.level, xp=0, max_xp=100,
        hp=sc.hp if sc.hp is not None else sc.max_hp, max_hp=sc.max_hp,
        gold=sc.gold, skills=dict(sc.skills), x=0, y=0,
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
}
