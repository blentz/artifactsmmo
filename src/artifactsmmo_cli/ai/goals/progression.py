"""Progression goal: equipment upgrades."""

import dataclasses

from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.equip import DUPLICATE_SLOT_TYPES, ITEM_TYPE_TO_SLOTS, EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.combat import is_winnable
from artifactsmmo_cli.ai.forced_craft_grind import forced_craft_grind
from artifactsmmo_cli.ai.game_data import GameData, ItemStats
from artifactsmmo_cli.ai.goals.base import Goal
from artifactsmmo_cli.ai.goals.upgrade_selection import (
    UpgradeCandidate,
    best_by_key,
    best_by_value,
    craftable_key,
    inventory_key,
)
from artifactsmmo_cli.ai.intermediate_batch import size_intermediate_craft
from artifactsmmo_cli.ai.learning.store import LearningStore
from artifactsmmo_cli.ai.min_plan_length import min_plan_length
from artifactsmmo_cli.ai.monster_drop_selection import (
    MonsterDropCandidate,
    select_monster_for_drop,
)
from artifactsmmo_cli.ai.nearest_tile import nearest_or_error
from artifactsmmo_cli.ai.recipe_closure import (
    closure_demand,
    gather_serves_closure,
    recipe_closure,
)
from artifactsmmo_cli.ai.shopping_list import fully_covered_materials
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

    @property
    def max_depth(self) -> int:
        """Deeper than the base 15 so a craft+equip plan whose lower bound sits
        just under the base bound is actually FOUND by the A*, not falsely
        admitted then abandoned. is_plannable gates on min_plan_length (a PROVED
        lower bound, Formal.PlanModel.min_plan_length_le_plan): for a 2nd
        copper_ring with bar×4/ore×8 in hand the bound is 15 == base max_depth, so
        the goal was admitted, yet the real plan (gather ×12 → craft bar ×2 →
        craft ring → equip) is 16 actions > 15 — the planner returned plan_len 0
        and the bot fell to a discretionary skill-grind (wooden_shield) instead of
        crafting the ring it could plainly make. 32 covers single-tier gear
        craft+equip from materials-in-hand while still routing genuinely deep
        from-scratch chains (copper_boots ≈ 80 gathers, steel_boots ≈ 480) to
        GatherMaterials accumulation via the unchanged depth-reachability split."""
        return 32

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

    def heuristic(self, state: WorldState, game_data: GameData) -> float:
        """Admissible+consistent: the cost of the FORCED craft-skill grind the
        target requires. `forced_craft_grind` counts it only when crafting is
        unavoidable, so h never over-estimates; `LevelSkill.cost` is the exact
        edge cost the plan pays, so taking the grind drops h by exactly that
        (consistency). 0 when satisfied, owned, skill-met, or the target has a
        non-craft route — see the design's admissibility guard.

        NOTE (latent footgun): `LevelSkill` below is built with no `xp_curve`,
        so `cost` takes the no-curve fallback, matching the factory's edge
        cost today — if a future change populates observed curves on the
        factory's LevelSkill but not here, admissibility could break."""
        if self.is_satisfied(state):
            return 0.0
        target = self.find_upgrade_target(state, game_data)
        if target is None:
            return 0.0
        target_item, _slot = target
        grind = forced_craft_grind(target_item, 1, state, game_data)
        if grind is None:
            return 0.0
        skill, level = grind
        return LevelSkill(skill=skill, target_level=level).cost(state, game_data)

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
        80 gathers ≫ max_depth 32: the Robby first-cycle stall. When the
        target (or its materials) is already in hand/bank the count drops and the
        short craft+equip plan IS reachable, so the goal stays plannable and
        GatherMaterials does the accumulating across cycles.

        Under-skill craft targets are NOT pruned here (LevelSkill epic P3a): the
        former crafting-skill fast-fail (which returned False while the character
        was below the recipe's crafting_level — the pre-LevelSkill CPU guard
        against the arbiter planning a gated final craft to exhaustion) is
        retired. `relevant_actions` now admits a SCOPED LevelSkill for the
        target's own gated (skill, level), so an under-skill equippable is
        reachable via a grind->craft->equip sequence — the same fix P2 applied to
        GatherMaterialsGoal. Only the depth-reachability bound remains."""
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
        return min_plan_length(
            item, 1, game_data.crafting_recipes, owned,
            game_data.max_gather_yield, equip=True,
        ) <= self.max_depth

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
        _needed_resources, craftable_mats = recipe_closure(game_data, (target_item,))
        in_closure_crafts = set(craftable_mats) | {target_item}
        # Withdraw-eligible item codes: the craftable intermediates + the
        # target; every leaf material arrives via the closure-demand union
        # below (GAP-7: the per-resource primary-drop loop was redundant and,
        # with the widened needed_resources, would admit junk withdraws).
        withdrawable: set[str] = set(in_closure_crafts)
        # Run-18 trace 2026-06-12 20:23: UpgradeEquipment(feather_coat) was
        # unplannable every cycle (111 nodes, plan_len 0) with the deficit
        # feather IN THE BANK — feather is a MONSTER drop (neither craftable
        # nor a resource drop), so the sets above missed it and
        # Withdraw(feather) never entered a plan. Every material in the full
        # recipe closure must be withdrawable (same defect fixed in
        # GatherMaterialsGoal for run-17 c94).
        chain: dict[str, int] = {}
        closure_demand(target_item, 1, game_data, chain, frozenset())
        withdrawable |= set(chain)
        # Materials the bank+inventory fully cover — withdraw them, don't gather.
        owned: dict[str, int] = dict(state.inventory)
        for code, qty in (state.bank_items or {}).items():
            owned[code] = owned.get(code, 0) + qty
        covered = fully_covered_materials(target_item, 1, game_data.crafting_recipes, owned)
        # LevelSkill admission scope (P3a): a skill-grind action only serves THIS
        # goal when a closure craftable (the target or a craftable intermediate)
        # is gated behind that exact (skill, level) and the character is under it
        # — the gear-unlock grind. Mirrors GatherMaterialsGoal.gated_skill_levels:
        # an UNCONDITIONAL skill_grind admission fans EVERY emitted LevelSkill
        # (one per craft level in the whole recipe table) into every search,
        # timing out under load (the P2 ff4401ac regression), and would also
        # break the slot-lock by admitting grinds unrelated to the target.
        gated_skill_levels: set[tuple[str, int]] = set()
        for code in in_closure_crafts:
            stats = game_data.item_stats(code)
            if (stats is not None and stats.crafting_skill
                    and game_data.crafting_recipe(code) is not None
                    and state.skills.get(stats.crafting_skill, 1)
                    < stats.crafting_level):
                gated_skill_levels.add((stats.crafting_skill, stats.crafting_level))
        result: list[Action] = []
        for action in actions:
            if "recovery" in action.tags or "deposit" in action.tags:
                result.append(action)
            elif ("skill_grind" in action.tags
                    and (getattr(action, "skill", ""),
                         getattr(action, "target_level", 0)) in gated_skill_levels):
                # Gear-unlock grind (P3a): admit a LevelSkill only for the
                # target's own gated (skill, level) — duck-typed so the goal need
                # not import LevelSkill. Scoped to keep the slot-lock intact.
                result.append(action)
            elif isinstance(action, UnequipAction):
                continue
            elif isinstance(action, GatherAction):
                # Keep only closure gathers — GAP-7 admission precision: the
                # gather's EFFECTIVE drop (override or primary) must be a
                # closure material — and only when that drop is NOT fully
                # bank/inventory-covered (else the WithdrawItemAction
                # supplies it).
                if not gather_serves_closure(action.resource_code,
                                             action.drop_item_override,
                                             game_data.resource_drops, chain):
                    continue
                drop = (action.drop_item_override
                        or game_data.resource_drop_item(action.resource_code))
                if drop is not None and drop in covered:
                    continue
                result.append(action)
            elif isinstance(action, CraftAction):
                # Keep only closure crafts (the chain intermediates + target).
                # The target passes through unchanged; intermediates are sized to
                # their inventory-bounded closure demand via size_intermediate_craft.
                if action.code == target_item:
                    result.append(action)
                elif action.code in in_closure_crafts:
                    result.append(size_intermediate_craft(action, chain, state, game_data))
            elif isinstance(action, WithdrawItemAction):
                # Keep only withdraws of closure items (chain materials/target).
                if action.code in withdrawable:
                    result.append(action)
            elif ("equip" in action.tags and isinstance(action, EquipAction)
                    and action.code == target_item and action.slot == target_slot):
                # Only the exact target item into the target slot. Drops
                # OptimizeLoadout and any other-item/other-slot equip.
                result.append(action)
            # Everything else (Fight, Recycle, NpcBuy/Sell, OptimizeLoadout, task
            # actions, gold/bank-expansion, map transitions) is irrelevant to
            # building+equipping the target — drop it to bound the search,
            # EXCEPT the target's own dropper fight re-emitted below.
        # GAP-6 (2026-07-08): the loop above drops every FightAction, so a
        # target that is itself a MONSTER DROP (old_boots: recipe=None, no
        # buyable vendor, sole dropper spider) had NO acquisition edge at all —
        # UpgradeEquipment(old_boots) died at 1 node and the cycle Waited with
        # a healthy character (l35_artifact_fill tripwire). Mirror
        # GatherMaterialsGoal's proven dropper wiring for the goal's OWN
        # target: emit the expected-kills-optimal winnable dropper's fight,
        # and synthesize the Equip leg the factory cannot enumerate for an
        # unowned recipe-less item (its equip loop covers craftable + OWNED
        # codes only). Skipped when the target is already held/banked — the
        # withdraw+equip edges above already serve it.
        if owned.get(target_item, 0) <= 0:
            fight = self._target_drop_fight(actions, state, game_data, target_item)
            if fight is not None:
                result.append(fight)
                # Task 6c: the GAP-6 re-emission above bypasses the factory's
                # normal Fight+OptimizeLoadout pairing (that loop drops every
                # FightAction at line 268-271), so this re-emitted dropper
                # fight needs its own companion swap. Self-guarding: inapplicable
                # when the loadout is already optimal for this monster (mirrors
                # GatherMaterialsGoal's Task 6b fix).
                result.append(OptimizeLoadoutAction(
                    target_monster_code=fight.monster_code, game_data=game_data))
                if not any(isinstance(a, EquipAction) and a.code == target_item
                           and a.slot == target_slot for a in result):
                    result.append(EquipAction(code=target_item, slot=target_slot))
        return result

    def _target_drop_fight(self, actions: list[Action], state: WorldState,
                           game_data: GameData,
                           target_item: str) -> FightAction | None:
        """Expected-kills-optimal WINNABLE dropper fight for the goal's own
        target item, or None when no winnable dropper exists.

        Mirrors GatherMaterialsGoal.relevant_actions' monster-drop narrowing
        (the live caller of the proved select_monster_for_drop core,
        formal/Formal/MonsterDropSelection.lean): never plan a losing fight
        (is_winnable gate), keep exactly one dropper (the lex-argmin of the
        expected-kills metric), and route a GREY dropper (zero xp at this
        level) through the drop_farm variant — the proven xp-gate bypass
        (formal/Formal/ActionApplicability.lean, dropFarm arm: every
        structural gate still applies).

        grey_farm_allowed is deliberately NOT consulted here. That policy
        gates RECIPE-material farming, where next-tier suppression is safe
        because the consuming recipe's own family carries the substitute
        (skill rises, the demand shifts to the next-tier recipe). An equip
        TARGET is its own consumer: the progression tree's attainable-argmax
        already arbitrated it against every craftable same-family alternative
        on equip_value, and nothing arms a grind toward a not-yet-attainable
        alternative — suppression would re-create the Wait livelock this
        emission exists to fix (l35 witness: enchanter_boots, equip_value 485
        > old_boots 371, crafts at gearcrafting 35 vs skill 30, within
        GREY_FARM_NEXT_TIER_MARGIN — the margin rule would suppress the only
        live route while no goal grinds gearcrafting). The demand gate holds
        structurally: the drop IS the goal's target, so a grey fight emitted
        here can never serve an xp-grind plan."""
        droppers = game_data.monsters_dropping(target_item)
        if not droppers:
            return None
        fights_by_code: dict[str, FightAction] = {
            a.monster_code: a for a in actions if isinstance(a, FightAction)
        }
        drop_candidates: list[MonsterDropCandidate] = []
        winner_fights: dict[str, FightAction] = {}
        for monster_code, rate, mn, mx in droppers:
            fight = fights_by_code.get(monster_code)
            if fight is None:
                continue
            if not is_winnable(state, game_data, monster_code):
                continue
            if fight.locations:
                loc = nearest_or_error(state.x, state.y, fight.locations, "gather")
                dist = abs(loc[0] - state.x) + abs(loc[1] - state.y)
            else:
                dist = 0
            drop_candidates.append(MonsterDropCandidate(
                monster_code=monster_code, rate=rate,
                min_quantity=mn, max_quantity=mx, distance=dist))
            winner_fights[monster_code] = fight
        chosen = select_monster_for_drop(target_item, drop_candidates)
        if chosen is None:
            return None
        fight = winner_fights[chosen]
        if game_data.xp_per_kill(chosen, state.level) > 0:
            return fight
        return dataclasses.replace(fight, drop_farm=True)

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
        `best_by_value`. The non-value fields are unused by `best_by_value`.

        P4a (exact arithmetic): the old `_value_of` scored a missing-stats
        pick as float ``-inf`` so it lost every comparison. With `value: int`
        the sentinel is gone — a pick whose stats are missing simply yields NO
        candidate (`None`), which `best_by_value` already treats as the
        always-loses case. Unreachable in production: both finders only emit
        picks whose `item_stats` resolved (same `game_data`, deterministic).
        """
        if target is None:
            return None
        stats = game_data.item_stats(target[0])
        if stats is None:
            return None
        return UpgradeCandidate(
            item_code=target[0], value=self._upgrade_value(stats),
            level=0, craft_level=0, relevant=False, fills_empty=False)

    def _committed_upgrade_if_ready(self, state: WorldState, game_data: GameData) -> tuple[str, str] | None:
        assert self._committed_target is not None
        item_code, _slot = self._committed_target
        recipe = game_data.crafting_recipe(item_code) or {}
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

    @staticmethod
    def _worn_in_other_slot(item_code: str, slot: str, state: WorldState,
                            game_data: GameData) -> bool:
        """One slot per code (server HTTP 485): a code worn in ANY other slot can
        never be equipped into `slot` — EXCEPT duplicate-allowed types (rings,
        artifacts).

        For rings the server permits the SAME code in multiple slots up to
        physical ownership (HTTP 200, live probe 2026-06-14; see
        `equip.py:DUPLICATE_SLOT_TYPES`, `EquipAction.is_applicable`, and
        `RealizableLoadout`). So copper_ring worn in ring1_slot does NOT block
        crafting/equipping a SECOND copper_ring for the empty ring2_slot — the
        whole point of the dual-ring carve-out. Without this carve the upgrade
        selector dropped the ring2 target and the bot never pursued the 2nd ring
        (it ground throwaway skill items instead). A NON-dup code worn elsewhere
        is still a dead target (its final EquipAction would 485 forever)."""
        stats = game_data.item_stats(item_code)
        if stats is not None and stats.type_ in DUPLICATE_SLOT_TYPES:
            return False
        return any(worn == item_code for s, worn in state.equipment.items() if s != slot)

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
                if self._worn_in_other_slot(item_code, slot, state, game_data):
                    continue
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
        for item_code in game_data.crafting_recipes:
            # Skip only if a copy is already in inventory/bank waiting to equip —
            # otherwise the bot re-crafts duplicates of an item it already holds
            # (the inventory-upgrade path equips that copy). A code WORN in a
            # slot is handled per-slot below by `_worn_in_other_slot`: for a
            # NON-duplicate type the server's one-slot-per-code rule (HTTP 485)
            # means it can never fill a sibling slot, so those targets are
            # dropped; but for DUPLICATE_SLOT_TYPES (rings, artifacts) the server allows the
            # SAME code in multiple slots up to ownership (HTTP 200), so a 2nd
            # copper_ring IS a valid craft target for the empty ring2 — the
            # dual-ring case. `_is_upgrade_over` still rejects a code for its own
            # already-filled slot.
            if (
                state.inventory.get(item_code, 0) > 0
                or bank.get(item_code, 0) > 0
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
                if self._worn_in_other_slot(item_code, slot, state, game_data):
                    continue
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
        recipe = game_data.crafting_recipe(item_code) or {}
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

    def _upgrade_value(self, stats: ItemStats) -> int:
        """Unified combat/utility value of an equippable: ranks on
        ``2*(combat_raw + wisdom + prospecting + inventory_space + haste) +
        nonToolBonus``, where ``combat_raw`` sums the 8 genuine-combat stats
        (attack + resistance + hp_restore + hp_bonus + dmg + critical_strike +
        lifesteal + combat_buff). Delegates to the shared tiers.equip_value
        (exact int since P4a)."""
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
                item_code in game_data.crafting_recipes
                and current_code not in game_data.crafting_recipes
            )
        return False

    def serialize(self) -> dict[str, object]:
        committed = list(self._committed_target) if self._committed_target is not None else None
        return {"type": "UpgradeEquipmentGoal",
                "initial_equipment": dict(self._initial_equipment),
                "committed_target": committed}

    def __repr__(self) -> str:
        # The committed target is part of the goal's identity. Run-18 trace
        # 2026-06-12 (cycles 27-98): the bare "UpgradeEquipment" repr made the
        # arbiter's fallback dedup collapse the rank-#1 root's ONE-ACTION
        # equip goal (copper_legs_armor, owned and unequipped) into the sticky
        # root's UNPLANNABLE one (feather_coat, drop-gated) — the crafted legs
        # sat in inventory for 73 cycles of unarmored fights. Repr collisions
        # also poisoned sticky commitment, DoomedMemo, and learned-cost keys
        # across targets. The probe form (no committed target) keeps the bare
        # repr.
        if self._committed_target is not None:
            item, slot = self._committed_target
            return f"UpgradeEquipment({item}->{slot})"
        return "UpgradeEquipment"
