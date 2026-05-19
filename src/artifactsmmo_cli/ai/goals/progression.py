"""Progression goal: equipment upgrades."""

from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.world_state import WorldState


class UpgradeEquipmentGoal(Goal):
    """Craft and equip better gear when an upgrade is available or craftable."""

    def __init__(self, initial_equipment: dict[str, str | None] | None = None) -> None:
        self._initial_equipment: dict[str, str | None] = dict(initial_equipment) if initial_equipment else {}

    def value(self, state: WorldState, game_data: GameData,
              history: LearningStore | None = None) -> float:
        upgrade = self._find_upgrade(state, game_data)
        if upgrade is None:
            return 0.0
        # Tool upgrade that boosts an active gather skill (e.g. better axe while
        # woodcutting for an ash_plank task) is far more valuable than generic
        # gear because it cuts the per-gather cooldown directly. Bump above
        # FarmItems (35) so the loop interrupts to craft+equip the tool.
        if self._upgrade_is_relevant_tool(upgrade, state, game_data):
            return 50.0
        return 35.0

    def priority(self, state: WorldState, game_data: GameData,
                 history: LearningStore | None = None) -> float:
        # Upgrade already in inventory → equip immediately, ahead of gathering (50.0).
        # Upgrade in bank or needs crafting → normal priority (possibly boosted
        # by value() above for active-skill tool upgrades).
        if self._find_inventory_only_upgrade(state, game_data):
            return 60.0
        return self.value(state, game_data)

    def _upgrade_is_relevant_tool(self, upgrade: tuple[str, str],
                                   state: WorldState, game_data: GameData) -> bool:
        """True if the upgrade improves a tool for a skill the current task needs."""
        item_code, _slot = upgrade
        stats = game_data.item_stats(item_code)
        if stats is None or not stats.skill_effects:
            return False
        active = game_data.active_gathering_skills(state.task_code)
        if not active:
            return False
        return any(skill in active for skill in stats.skill_effects)

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
        """Find the best craftable upgrade ignoring material availability.

        Ranking: (relevant_tool_first, lowest_crafting_level). Relevant-tool means
        the item has a positive skill_effect for a skill the current task needs
        (e.g. a better axe while the active task chains through woodcutting).
        Within each tier, lowest crafting_level first so skill progression is
        linear: craft basic items to level the skill, unlocking higher recipes.
        """
        active = game_data.active_gathering_skills(state.task_code)
        equipped = set(state.equipment.values()) - {None}
        best: tuple[str, str] | None = None
        # Sort key: (relevant_tool 0|1, -craft_level). Higher tuple wins.
        # Init to (-1, -inf) so any real candidate beats it.
        best_key: tuple[int, float] = (-1, -float("inf"))
        bank = state.bank_items or {}
        for item_code in game_data._crafting_recipes:
            # Skip if already owned (inventory, bank, or equipped) — otherwise
            # the bot re-crafts copies of items it already has waiting to equip.
            if (
                state.inventory.get(item_code, 0) > 0
                or bank.get(item_code, 0) > 0
                or item_code in equipped
            ):
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            if not ITEM_TYPE_TO_SLOTS.get(stats.type_):
                continue
            if stats.crafting_skill and state.skills.get(stats.crafting_skill, 0) < stats.crafting_level:
                continue
            craft_level = stats.crafting_level or 0
            relevant_tool = 1 if active and any(s in active for s in stats.skill_effects) else 0
            # Sort key: relevant tools come first (higher rank), then lower craft level.
            key = (relevant_tool, -craft_level)
            if key < best_key:
                continue
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if self._is_upgrade_over(item_code, stats, current, current_stats, game_data):
                    best, best_key = (item_code, slot), key
        return best

    def _find_craftable_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Return the IDEAL craftable upgrade target only if its materials are in hand.

        Must agree with `_find_craftable_upgrade_target` on which item to
        build. Otherwise the bot races itself: GatherMaterials gathers for
        the ideal target (ring), this goal sees enough materials for a
        cheaper item (dagger), and crafts the wrong thing with the bars
        meant for the ring. Returning None when the ideal target lacks
        materials lets GatherMaterials keep working until the target
        chain is genuinely buildable.
        """
        target = self._find_craftable_upgrade_target(state, game_data)
        if target is None:
            return None
        item_code, _slot = target
        recipe = game_data._crafting_recipes.get(item_code) or {}
        bank = state.bank_items or {}
        if not all(
            state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
            for mat, qty in recipe.items()
        ):
            return None
        return target

    def _is_upgrade_over(
        self,
        item_code: str,
        stats: ItemStats,
        current_code: str | None,
        current_stats: ItemStats | None,
        game_data: GameData,
    ) -> bool:
        """Return True if item_code is an upgrade over current_code for an equipment slot."""
        if current_code is None:
            return True
        # Stats missing for an equipped item: refuse the upgrade. Treating
        # missing-stats as "no current item" caused infinite recrafts when
        # the game_data DB lacked entries for starter gear (fishing_net).
        if current_stats is None:
            return False
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
