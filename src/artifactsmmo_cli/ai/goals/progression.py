"""Progression goal: equipment upgrades."""

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS, EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.upgrade_selection import (
    UpgradeCandidate,
    best_by_key,
    best_by_value,
    craftable_key,
    inventory_key,
)
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.min_gathers import min_gathers
from artifactsmmo_cli.ai.recipe_closure import recipe_closure
from artifactsmmo_cli.ai.shopping_list import fully_covered_materials
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
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
        # Committed to a specific (item, slot): satisfied when item OCCUPIES
        # that slot. The earlier inventory-suffices rule (3a2dbc8) was the
        # wrong half of the equip-thrash fix — it stopped the goal from
        # firing the EquipAction at all, so chosen_root=ObtainItem(tool)
        # locked the arbiter into a step that short-circuited every cycle
        # and discretionary PursueTask ran forever (trace 2026-06-06 cycles
        # 9-278, 0 fights). The real thrash root was ObtainItem(tool)
        # demanding a slot occupied by a per-fight combat weapon — fixed
        # at the META layer by treating tools as satisfied when owned (see
        # meta_goal.ObtainItem.is_satisfied subtype=='tool' branch). Tools
        # never recommit here because their parent root drops. Real gear
        # (wooden_shield etc.) still requires slot occupancy and equips
        # exactly once.
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

    def is_plannable(self, state: WorldState, game_data: GameData,
                     history: LearningStore | None = None) -> bool:
        """Skip when the target needs more gather actions than max_depth.

        is_satisfied requires the target item EQUIPPED, which means crafting it
        first; a gather mints +1, so obtaining the target from raw materials
        needs ≥ `min_gathers` gather steps. The planner never returns a plan
        longer than `max_depth` (formal/Formal/PlannerDepthBound.lean:
        plan_length_le_max_depth), so when `min_gathers > max_depth` no plan can
        exist — running the 90s A* is pure waste. copper_boots from scratch =
        80 gathers ≫ base max_depth 15: the Robby first-cycle stall. When the
        target (or its materials) is already in hand/bank the count drops and the
        short craft+equip plan IS reachable, so the goal stays plannable and
        GatherMaterials does the accumulating across cycles."""
        if self.is_satisfied(state):
            return True
        target = self.find_upgrade_target(state, game_data)
        if target is None:
            return True
        item, _slot = target
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        if owned.get(item, 0) > 0:
            return True
        return min_gathers(item, 1, game_data._crafting_recipes, owned) <= self.max_depth

    def relevant_actions(self, actions: list[Action], state: WorldState,
                         game_data: GameData) -> list[Action]:
        """Lock planning to the upgrade target's recipe CLOSURE + SLOT.

        is_satisfied (when committed) requires the target item in its slot, but
        the planner still needs a narrow action set or it finds cheaper detours.
        Two bugs this prevents:

        1. SLOT LOCK: while gathering ash_plank for a wooden_shield (shield_slot),
           the planner crafted a fishing_net (a weapon tool sharing the ash_plank
           recipe) and equipped it via OptimizeLoadout. Keep only the EquipAction
           for the exact target item into the target slot; drop UnequipActions and
           every other equip-tagged action (OptimizeLoadout etc.).

        2. CLOSURE LOCK + BANK-AWARE GATHER PRUNING (fixes the live Robby
           timeout): the prior version kept EVERY non-equippable craft, every
           gather, and (via a catch-all) every Fight/Recycle/NpcBuy/NpcSell — so
           UpgradeEquipment(copper gear) gave the planner ~1000 actions and the
           A* search exploded (~20k-57k nodes, timeout, plan_len 0) even though
           the bank held 485 copper_ore. Restrict crafts/gathers/withdraws to the
           target's recipe closure (copper_dagger -> copper_bar -> copper_ore),
           and within that, PRUNE the gather for any material the bank+inventory
           fully cover (net deficit 0 per the bank-aware shopping_list) — that
           material is withdrawn, not re-gathered. A material with ANY net deficit
           keeps its gather (never prune the only path to a real deficit), so a
           reachable plan is never pruned (PlannerAdmissibility preserved). The
           result is a short withdraw->craft->equip plan in << budget.
        """
        target = self.find_upgrade_target(state, game_data)
        if target is None:
            return actions
        target_item, target_slot = target
        # Recipe closure of the target: the resources to gather and the craftable
        # intermediates (copper_bar, copper_dagger). Restrict the action set to
        # this so the planner cannot wander into unrelated crafts/fights/gathers.
        needed_resources, craftable_mats = recipe_closure(game_data, (target_item,))
        in_closure_crafts = set(craftable_mats) | {target_item}
        # Withdraw-eligible item codes: the craftable intermediates + the target
        # + the leaf raw-material drops of needed resources.
        withdrawable: set[str] = set(in_closure_crafts)
        for res in needed_resources:
            drop = game_data.resource_drop_item(res)
            if drop is not None:
                withdrawable.add(drop)
        # Materials the bank+inventory fully cover — withdraw them, don't gather.
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        covered = fully_covered_materials(target_item, 1, game_data._crafting_recipes, owned)
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif isinstance(action, UnequipAction):
                continue
            elif isinstance(action, GatherAction):
                # Keep only closure gathers, and only when their drop is NOT fully
                # bank/inventory-covered (else the WithdrawItemAction supplies it).
                if action.resource_code not in needed_resources:
                    continue
                drop = game_data.resource_drop_item(action.resource_code)
                if drop is not None and drop in covered:
                    continue
                result.append(action)
            elif isinstance(action, CraftAction):
                # Keep only closure crafts (the chain intermediates + target).
                if action.code in in_closure_crafts:
                    result.append(action)
            elif isinstance(action, WithdrawItemAction):
                # Keep only withdraws of closure items (chain materials/target).
                if action.code in withdrawable:
                    result.append(action)
            elif "equip" in action.tags:
                # Only the exact target item into the target slot. Drops
                # OptimizeLoadout and any other-item/other-slot equip.
                if isinstance(action, EquipAction) and action.code == target_item and action.slot == target_slot:
                    result.append(action)
            # Everything else (Fight, Recycle, NpcBuy/Sell, OptimizeLoadout, task
            # actions, gold/bank-expansion, map transitions) is irrelevant to
            # building+equipping the target — drop it to bound the search.
        return result

    def find_upgrade_target(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Find the best upgrade (inventory or craftable) ignoring material availability.

        Used to identify what to craft even when materials haven't been gathered yet.
        """
        if self._committed_target is not None:
            # Committed: return exactly the target. The commitment guarantee
            # (never substitute another equippable) is enforced by
            # relevant_actions slot-locking and is_satisfied, not here.
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
        since equipping it is cheaper than crafting. Delegates to the proved pure
        core `upgrade_selection.best_by_value` (tie -> inventory)."""
        inv_cand = self._value_candidate(inv, game_data)
        craft_cand = self._value_candidate(craft, game_data)
        chosen = best_by_value(inv_cand, craft_cand)
        if chosen is None:
            return None
        return inv if chosen is inv_cand else craft

    def _value_candidate(self, target: tuple[str, str] | None,
                         game_data: GameData) -> UpgradeCandidate | None:
        """Wrap a (item, slot) pick as a value-only UpgradeCandidate for
        `best_by_value`. The non-value fields are unused by `best_by_value`."""
        if target is None:
            return None
        return UpgradeCandidate(
            item_code=target[0], value=self._value_of(target, game_data),
            level=0, craft_level=0, relevant=False, fills_empty=False)

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

    def _find_inventory_upgrade(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        """Best-VALUE upgrade in inventory or bank (bank items need Withdraw first).

        Ranks by the proved `upgrade_selection.inventory_key`
        (relevant, value, level, item_code) via the deterministic argmax.
        Determinism is FIRST-WINS over the candidate list: distinct item_codes
        give a unique max-key ITEM, while the same item mapped to multiple slots
        emits same-code candidates that tie on the key (slot is not in the key) —
        the first slot in ITEM_TYPE_TO_SLOTS order wins."""
        active = frozenset(game_data.active_gathering_skills(state.task_code, state.crafting_target))
        bank = state.bank_items or {}
        picks: list[tuple[UpgradeCandidate, tuple[str, str]]] = []
        for item_code in set(state.inventory) | set(bank):
            if state.inventory.get(item_code, 0) + bank.get(item_code, 0) <= 0:
                continue
            stats = game_data.item_stats(item_code)
            if stats is None or state.level < stats.level:
                continue
            relevant = bool(active and any(s in active for s in stats.skill_effects))
            value = self._upgrade_value(stats)
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if not self._is_upgrade_over(item_code, stats, current, current_stats, game_data, active):
                    continue
                cand = UpgradeCandidate(item_code=item_code, value=value, level=stats.level,
                                        craft_level=0, relevant=relevant, fills_empty=False)
                picks.append((cand, (item_code, slot)))
        return self._argmax_pick(picks, inventory_key)

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
        # Sort key per (item, slot): (relevant_tool, fills_empty_slot, value,
        # -craft_level, item_code). Higher tuple wins. fills_empty ranks an
        # additive equip (empty slot) above a replacement; value ranks better
        # gear first. Determinism is FIRST-WINS over the candidate list: distinct
        # item_codes give a unique max-key ITEM (order-independent), while the
        # same item mapped to multiple slots emits same-code candidates that TIE
        # on the key (slot is not in the key) — the first slot in
        # ITEM_TYPE_TO_SLOTS order wins. Ranked via the proved
        # `upgrade_selection.craftable_key` argmax.
        picks: list[tuple[UpgradeCandidate, tuple[str, str]]] = []
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
            relevant_tool = bool(active and any(s in active for s in stats.skill_effects))
            value = self._upgrade_value(stats)
            for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
                current = state.equipment.get(slot)
                current_stats = game_data.item_stats(current) if current else None
                if not self._is_upgrade_over(item_code, stats, current, current_stats, game_data):
                    continue
                # Rank by VALUE before craft_level: the prior alphabetical
                # tiebreak made the bot prefer fishing_net (attack 5 + fishing
                # penalty) or wooden_staff over a wooden_shield purely by
                # item-code string order. value() puts genuinely better gear
                # first so the committed target is the best upgrade, not an
                # alphabetical accident.
                cand = UpgradeCandidate(item_code=item_code, value=value, level=stats.level,
                                        craft_level=craft_level, relevant=relevant_tool,
                                        fills_empty=current is None)
                picks.append((cand, (item_code, slot)))
        return self._argmax_pick(picks, craftable_key)

    @staticmethod
    def _argmax_pick(picks: list[tuple[UpgradeCandidate, tuple[str, str]]],
                     key: object) -> tuple[str, str] | None:
        """Run the proved deterministic argmax over candidates and return the
        winning (item, slot) pick. The candidate carries no slot, so we pair each
        with its (item, slot) and select by candidate identity (each pick holds a
        distinct candidate instance, so identity is the first-wins argmax)."""
        cands = [c for c, _ in picks]
        winner = best_by_key(cands, key)  # type: ignore[arg-type]
        if winner is None:
            return None
        return next(pick for cand, pick in picks if cand is winner)

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
