"""Progression goal: equipment upgrades."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equipment import ITEM_TYPE_TO_SLOTS, EquipAction, UnequipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.tiers.equip_value import equip_value
from artifactsmmo_cli.ai.world_state import WorldState

# Value constants (inlined from retired priorities.py).
# Relevant-tool upgrade: above FarmItems(35) so the loop interrupts to equip.
_UPGRADE_EQUIPMENT_RELEVANT_TOOL = 51.0
# Base upgrade value when no relevant-tool match.
_UPGRADE_EQUIPMENT_BASE = 35.0


class UpgradeEquipmentGoal(Goal):
    """Craft and equip better gear when an upgrade is available or craftable."""

    def __init__(self, initial_equipment: dict[str, str | None] | None = None,
                 committed_target: tuple[str, str] | None = None) -> None:
        self._initial_equipment: dict[str, str | None] = dict(initial_equipment) if initial_equipment else {}
        # When set, the goal commits to crafting exactly this (item, slot)
        # upgrade and ignores all other craftable candidates. The player
        # persists the target across cycles so a transient inventory change
        # can't make UpgradeEquipment craft a different equippable than the
        # one GatherMaterials is actively gathering for (e.g. a fishing_net
        # built from ash_planks meant for a wooden_shield).
        self._committed_target = committed_target

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
            return _UPGRADE_EQUIPMENT_RELEVANT_TOOL
        return _UPGRADE_EQUIPMENT_BASE

    def _upgrade_is_relevant_tool(self, upgrade: tuple[str, str],
                                   state: WorldState, game_data: GameData) -> bool:
        """True if the upgrade improves a tool for a skill the current task needs."""
        item_code, _slot = upgrade
        stats = game_data.item_stats(item_code)
        if stats is None or not stats.skill_effects:
            return False
        active = game_data.active_gathering_skills(state.task_code, state.crafting_target)
        if not active:
            return False
        return any(skill in active for skill in stats.skill_effects)

    def is_satisfied(self, state: WorldState) -> bool:
        # Committed to a specific (item, slot): satisfied only when THAT item sits
        # in THAT slot. The old "any slot differs from the initial snapshot" rule
        # let the planner satisfy the goal by equipping any freshly-crafted item
        # (e.g. a fishing_net built from the shield's ash_planks), defeating the
        # commitment. Without a commitment, keep the snapshot rule so an
        # inventory-ready equip into any slot still counts.
        if self._committed_target is not None:
            item, slot = self._committed_target
            return state.equipment.get(slot) == item
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

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Lock planning to the upgrade target's SLOT.

        is_satisfied (when committed) requires the target item in its slot, but
        the planner still needs a narrow action set or it finds cheaper detours.
        The bug this prevents: while gathering ash_plank for a wooden_shield
        (shield_slot), the planner crafted a fishing_net (a weapon tool sharing
        the ash_plank recipe) and equipped it via OptimizeLoadout. Lock to the
        slot — keep only:
          - the EquipAction for the exact target item into the target slot,
          - CraftActions for the target item, items equippable in the target
            slot, and non-equippable recipe-chain materials (ash_plank, bars),
          - gather/withdraw and recovery/deposit support.
        Drop UnequipActions and every other equip-tagged action (including
        OptimizeLoadout, which equips arbitrary slots) and crafts of equippables
        belonging to a different slot.
        """
        target = self.find_upgrade_target(state, game_data)
        if target is None:
            return actions
        target_item, target_slot = target
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif isinstance(action, UnequipAction):
                continue
            elif isinstance(action, CraftAction):
                stats = game_data.item_stats(action.code)
                slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, []) if stats is not None else []
                # Keep target-slot equippables and non-equippable materials
                # (recipe chain); drop equippables for other slots.
                if not slots or target_slot in slots:
                    result.append(action)
            elif "equip" in action.tags:
                # Only the exact target item into the target slot. Drops
                # OptimizeLoadout and any other-item/other-slot equip.
                if isinstance(action, EquipAction) and action.code == target_item and action.slot == target_slot:
                    result.append(action)
            else:
                result.append(action)
        return result

    def find_upgrade_target(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the best upgrade (inventory or craftable) ignoring material availability.

        Used to identify what to craft even when materials haven't been gathered yet.
        """
        if self._committed_target is not None:
            return self._committed_target
        return self._best_by_value(
            self._find_inventory_upgrade(state, game_data),
            self._find_craftable_upgrade_target(state, game_data),
            game_data,
        )

    def _find_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find a better item in inventory or craftable with materials already available."""
        if self._committed_target is not None:
            # Locked to the player's persisted target: craft it only when its
            # materials are in hand, never substitute a different equippable.
            return self._committed_upgrade_if_ready(state, game_data)
        return self._best_by_value(
            self._find_inventory_upgrade(state, game_data),
            self._find_craftable_upgrade(state, game_data),
            game_data,
        )

    def _best_by_value(self, inv: tuple[str, str] | None, craft: tuple[str, str] | None,
                       game_data: GameData) -> tuple[str, str] | None:
        """Pick the higher-VALUE of an inventory pick and a craftable pick.

        Inventory-first precedence let a junk owned weapon (wooden_stick) beat
        a far better craftable shield just because it was already in the bag.
        Compare by stat value; prefer the owned (inventory) item only on a tie,
        since equipping it is cheaper than crafting.
        """
        if inv is None:
            return craft
        if craft is None:
            return inv
        return inv if self._value_of(inv, game_data) >= self._value_of(craft, game_data) else craft

    def _committed_upgrade_if_ready(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        assert self._committed_target is not None
        item_code, _slot = self._committed_target
        recipe = game_data._crafting_recipes.get(item_code) or {}
        bank = state.bank_items or {}
        if recipe and all(
            state.inventory.get(mat, 0) + bank.get(mat, 0) >= qty
            for mat, qty in recipe.items()
        ):
            return self._committed_target
        # Already crafted and sitting in inventory? Then it's equip-ready.
        if state.inventory.get(item_code, 0) > 0:
            return self._committed_target
        return None

    def _value_of(self, target: tuple[str, str] | None, game_data: GameData) -> float:
        """Stat value of a (item, slot) pick, or -inf for None."""
        if target is None:
            return -float("inf")
        stats = game_data.item_stats(target[0])
        return self._upgrade_value(stats) if stats is not None else -float("inf")

    def _find_inventory_only_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Best-VALUE upgrade already in inventory — equippable in one action.

        Ranked by (relevant_tool, value, level, item_code), not by level alone:
        a junk weapon (wooden_stick) sitting in the bag used to win an empty
        slot over far better gear purely because the picker maximized level
        with an arbitrary tiebreak.
        """
        active = frozenset(game_data.active_gathering_skills(state.task_code, state.crafting_target))
        best: tuple[str, str] | None = None
        best_key: tuple[int, float, int, str] = (-1, -float("inf"), -1, "")
        for item_code in state.inventory:
            if state.inventory.get(item_code, 0) <= 0:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            relevant = 1 if active and any(s in active for s in stats.skill_effects) else 0
            value = self._upgrade_value(stats)
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if not self._is_upgrade_over(item_code, stats, current, current_stats, game_data, active):
                    continue
                key = (relevant, value, stats.level, item_code)
                if key > best_key:
                    best, best_key = (item_code, slot), key
        return best

    def _find_inventory_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Best-VALUE upgrade in inventory or bank (bank items need Withdraw first)."""
        active = frozenset(game_data.active_gathering_skills(state.task_code, state.crafting_target))
        bank = state.bank_items or {}
        best: tuple[str, str] | None = None
        best_key: tuple[int, float, int, str] = (-1, -float("inf"), -1, "")
        for item_code in set(state.inventory) | set(bank):
            if state.inventory.get(item_code, 0) + bank.get(item_code, 0) <= 0:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            relevant = 1 if active and any(s in active for s in stats.skill_effects) else 0
            value = self._upgrade_value(stats)
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if not self._is_upgrade_over(item_code, stats, current, current_stats, game_data, active):
                    continue
                key = (relevant, value, stats.level, item_code)
                if key > best_key:
                    best, best_key = (item_code, slot), key
        return best

    def _find_craftable_upgrade_target(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the best craftable upgrade ignoring material availability.

        Ranking: (relevant_tool_first, lowest_crafting_level). Relevant-tool means
        the item has a positive skill_effect for a skill the current task needs
        (e.g. a better axe while the active task chains through woodcutting).
        Within each tier, lowest crafting_level first so skill progression is
        linear: craft basic items to level the skill, unlocking higher recipes.
        """
        active = game_data.active_gathering_skills(state.task_code, state.crafting_target)
        equipped = set(state.equipment.values()) - {None}
        best: tuple[str, str] | None = None
        # Sort key per (item, slot): (relevant_tool, fills_empty_slot, value,
        # -craft_level, item_code). Higher tuple wins. fills_empty ranks an
        # additive equip (empty slot) above a replacement; value ranks better
        # gear first; item_code is the final deterministic tiebreak so equal
        # candidates never depend on dict iteration order.
        best_key: tuple[int, int, float, int, str] = (-1, -1, -float("inf"), -10**9, "")
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
            value = self._upgrade_value(stats)
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if not self._is_upgrade_over(item_code, stats, current, current_stats, game_data):
                    continue
                fills_empty = 1 if current is None else 0
                # Rank by VALUE before craft_level: the prior alphabetical
                # tiebreak made the bot prefer fishing_net (attack 5 + fishing
                # penalty) or wooden_staff over a wooden_shield purely by
                # item-code string order. value() puts genuinely better gear
                # first so the committed target is the best upgrade, not an
                # alphabetical accident.
                key = (relevant_tool, fills_empty, value, -craft_level, item_code)
                if key > best_key:
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
        active_skills: frozenset[str] = frozenset(),
    ) -> bool:
        """Return True if item_code is an upgrade over current_code for an equipment slot."""
        return self._is_upgrade_over_impl(
            item_code, stats, current_code, current_stats, game_data, active_skills)

    def _upgrade_value(self, stats: ItemStats) -> float:
        """Crude combat/utility value of an equippable: total attack +
        resistance + hp restore. Delegates to the shared tiers.equip_value."""
        return equip_value(stats)

    def _is_upgrade_over_impl(
        self,
        item_code: str,
        stats: ItemStats,
        current_code: str | None,
        current_stats: ItemStats | None,
        game_data: GameData,
        active_skills: frozenset[str],
    ) -> bool:
        if current_code is None:
            return True
        # Stats missing for an equipped item: refuse the upgrade. Treating
        # missing-stats as "no current item" caused infinite recrafts when
        # the game_data DB lacked entries for starter gear (fishing_net).
        if current_stats is None:
            return False
        if stats.level > current_stats.level:
            return True
        # Same-level rules.
        if stats.level == current_stats.level:
            # Active-task tool match: candidate boosts a skill the current
            # task needs, current does not. Bot was gathering ash with the
            # fishing_net equipped because the same-level check below
            # rejected copper_axe (both craftable) without considering the
            # task-skill mismatch.
            if active_skills:
                cand_boosts = bool(active_skills & set(stats.skill_effects))
                curr_boosts = bool(active_skills & set(current_stats.skill_effects))
                if cand_boosts and not curr_boosts:
                    return True
            # Craftable items beat non-craftable starter gear.
            return (
                item_code in game_data._crafting_recipes
                and current_code not in game_data._crafting_recipes
            )
        return False

    def __repr__(self) -> str:
        return "UpgradeEquipment"
