"""Progression goal: equipment upgrades."""

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.world_state import WorldState


class UpgradeEquipmentGoal(Goal):
    """Craft and equip better gear when an upgrade is available or craftable."""

    def __init__(self, initial_equipment: dict[str, str | None] | None = None) -> None:
        self._initial_equipment: dict[str, str | None] = dict(initial_equipment) if initial_equipment else {}

    def value(self, state: WorldState, game_data: GameData) -> float:
        if self._find_upgrade(state, game_data):
            return 35.0
        return 0.0

    def priority(self, state: WorldState, game_data: GameData) -> float:
        # Upgrade already in inventory → equip immediately, ahead of gathering (50.0).
        # Upgrade in bank or needs crafting → normal priority.
        if self._find_inventory_only_upgrade(state, game_data):
            return 60.0
        return self.value(state, game_data)

    def is_satisfied(self, state: WorldState) -> bool:
        for slot, current in state.equipment.items():
            if current is not None and current != self._initial_equipment.get(slot):
                return True
        return False

    def desired_state(self, state: WorldState, game_data: GameData) -> dict[str, object]:
        upgrade = self._find_upgrade(state, game_data)
        if upgrade is None:
            return {}
        code, slot = upgrade
        return {"equipment": {slot: code}}

    def find_upgrade_target(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the best upgrade (inventory or craftable) ignoring material availability.

        Used to identify what to craft even when materials haven't been gathered yet.
        """
        return self._find_inventory_upgrade(state, game_data) or self._find_craftable_upgrade_target(state, game_data)

    def _find_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find a better item in inventory or craftable with materials already available."""
        return self._find_inventory_upgrade(state, game_data) or self._find_craftable_upgrade(state, game_data)

    def _find_inventory_only_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find a highest-level upgrade in inventory only — can be equipped in one action."""
        best: tuple[str, str] | None = None
        best_level = -1
        for item_code in state.inventory:
            if state.inventory.get(item_code, 0) <= 0:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if self._is_upgrade_over(item_code, stats, current, current_stats, game_data) and stats.level >= best_level:
                    best, best_level = (item_code, slot), stats.level
        return best

    def _find_inventory_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find highest-level upgrade in inventory or bank (bank items need Withdraw first)."""
        bank = state.bank_items or {}
        best: tuple[str, str] | None = None
        best_level = -1
        for item_code in set(state.inventory) | set(bank):
            if state.inventory.get(item_code, 0) + bank.get(item_code, 0) <= 0:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if self._is_upgrade_over(item_code, stats, current, current_stats, game_data) and stats.level >= best_level:
                    best, best_level = (item_code, slot), stats.level
        return best

    def _find_craftable_upgrade_target(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the lowest-crafting-level upgrade we can make, ignoring material availability.

        Lowest crafting_level first so skill progression is linear: craft basic items to
        level the skill, unlocking higher recipes over time.
        """
        equipped = set(state.equipment.values()) - {None}
        best: tuple[str, str] | None = None
        best_craft_level = float("inf")
        for item_code in game_data._crafting_recipes:
            if item_code in state.inventory or item_code in equipped:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            if stats.crafting_skill and state.skills.get(stats.crafting_skill, 0) < stats.crafting_level:
                continue
            craft_level = stats.crafting_level or 0
            if craft_level >= best_craft_level:
                continue
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if self._is_upgrade_over(item_code, stats, current, current_stats, game_data):
                    best, best_craft_level = (item_code, slot), craft_level
        return best

    def _find_craftable_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the lowest-crafting-level upgrade whose materials are already available."""
        equipped = set(state.equipment.values()) - {None}
        bank = state.bank_items or {}
        best: tuple[str, str] | None = None
        best_craft_level = float("inf")
        for item_code, recipe in game_data._crafting_recipes.items():
            if item_code in state.inventory or item_code in equipped:
                continue  # already handled by _find_inventory_upgrade or already equipped
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            if stats.crafting_skill and state.skills.get(stats.crafting_skill, 0) < stats.crafting_level:
                continue
            # Only propose craft if materials are already available (inventory + bank).
            # This keeps the planner chain short: Withdraw → Craft → Equip.
            if not all(
                state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
                for mat, qty in recipe.items()
            ):
                continue
            craft_level = stats.crafting_level or 0
            if craft_level >= best_craft_level:
                continue
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if self._is_upgrade_over(item_code, stats, current, current_stats, game_data):
                    best, best_craft_level = (item_code, slot), craft_level
        return best

    def _is_upgrade_over(
        self,
        item_code: str,
        stats: ItemStats,
        current_code: str | None,
        current_stats: ItemStats | None,
        game_data: GameData,
    ) -> bool:
        """Return True if item_code is an upgrade over current_code for an equipment slot."""
        if current_code is None or current_stats is None:
            return True
        if stats.level > current_stats.level:
            return True
        # Same level: craftable items beat non-craftable starter gear.
        return (
            stats.level == current_stats.level
            and item_code in game_data._crafting_recipes
            and current_code not in game_data._crafting_recipes
        )

    def __repr__(self) -> str:
        return "UpgradeEquipment"
