"""Action-list factory: constructs the full GOAP action set for a cycle.

Extracted verbatim from ``GamePlayer._build_actions`` so player.py stays
focused on the sense→plan→act→learn loop. ``GamePlayer._build_actions``
delegates here, passing its state explicitly.
"""

from artifactsmmo_cli.ai.actions.accept_task import AcceptTaskAction
from artifactsmmo_cli.ai.actions.bank_expansion import BuyBankExpansionAction
from artifactsmmo_cli.ai.actions.base import Action
from artifactsmmo_cli.ai.actions.claim import ClaimPendingItemAction
from artifactsmmo_cli.ai.actions.combat import FightAction
from artifactsmmo_cli.ai.actions.complete_task import CompleteTaskAction
from artifactsmmo_cli.ai.actions.consumable import UseConsumableAction
from artifactsmmo_cli.ai.actions.crafting import CraftAction
from artifactsmmo_cli.ai.actions.delete import DeleteItemAction
from artifactsmmo_cli.ai.actions.deposit_all import DepositAllAction
from artifactsmmo_cli.ai.actions.deposit_gold import DepositGoldAction
from artifactsmmo_cli.ai.actions.equip import ITEM_TYPE_TO_SLOTS, EquipAction
from artifactsmmo_cli.ai.actions.gathering import GatherAction
from artifactsmmo_cli.ai.actions.level_skill import LevelSkill
from artifactsmmo_cli.ai.actions.npc import NpcBuyAction
from artifactsmmo_cli.ai.actions.npc_sell import NpcSellAction
from artifactsmmo_cli.ai.actions.optimize_loadout import OptimizeLoadoutAction
from artifactsmmo_cli.ai.actions.recycle import RecycleAction
from artifactsmmo_cli.ai.actions.rest import RestAction
from artifactsmmo_cli.ai.actions.task_cancel import TaskCancelAction
from artifactsmmo_cli.ai.actions.task_exchange import TaskExchangeAction
from artifactsmmo_cli.ai.actions.task_trade import TaskTradeAction
from artifactsmmo_cli.ai.actions.teleport import TeleportAction
from artifactsmmo_cli.ai.actions.transition import MapTransitionAction
from artifactsmmo_cli.ai.actions.unequip import UnequipAction
from artifactsmmo_cli.ai.actions.use_gold_bag import UseGoldBagAction
from artifactsmmo_cli.ai.actions.withdraw_gold import WithdrawGoldAction
from artifactsmmo_cli.ai.actions.withdraw_item import WithdrawItemAction
from artifactsmmo_cli.ai.game_data import GameData
from artifactsmmo_cli.ai.item_catalog import _GATHERING_SKILLS
from artifactsmmo_cli.ai.player_helpers import delete_cost
from artifactsmmo_cli.ai.task_batch import task_batch_size
from artifactsmmo_cli.ai.tiers.objective import CharacterObjective
from artifactsmmo_cli.ai.world_state import TASKS_COIN_CODE, WorldState


def build_actions(
    game_data: GameData,
    state: WorldState | None,
    objective: CharacterObjective | None,
    bank_accessible: bool,
    task_exchange_min_coins: int,
) -> list[Action]:
    """Build the action list. Each action handles its own movement in execute() and cost().

    The DESTRUCTIVE emissions (Recycle / NpcSell / Delete) are the raw MENU, not a
    decision: the keep authority licenses them per-cycle in `StrategyArbiter.select`
    (`ai/destructive_license`). The old `protected_gear` code-set parameter is gone —
    see the recycle block below.
    """
    bank = game_data.bank_location()
    taskmaster = game_data.taskmaster_location()

    actions: list[Action] = [
        RestAction(),
        UseConsumableAction(_item_stats=game_data.all_item_stats),
        UseGoldBagAction(_item_stats=game_data.all_item_stats),
        DepositAllAction(bank_location=bank, accessible=bank_accessible, game_data=game_data),
        AcceptTaskAction(taskmaster_location=taskmaster),
        CompleteTaskAction(taskmaster_location=taskmaster),
        TaskExchangeAction(taskmaster_location=taskmaster, min_coins=task_exchange_min_coins),
        TaskCancelAction(taskmaster_location=taskmaster),
        ClaimPendingItemAction(),
    ]

    # Fight and gather actions carry their own locations — no separate move actions needed
    for monster_code, locs in game_data.all_monster_locations.items():
        actions.append(FightAction(monster_code=monster_code, locations=frozenset(locs)))
        actions.append(OptimizeLoadoutAction(target_monster_code=monster_code, game_data=game_data))

    # Raid bosses have NO monster-type map tile, so the loop above never sees
    # them — that is the mechanical reason a raid was unplannable. Participation
    # is the ordinary fight action at a tile whose content type is `raid`, while
    # the raid is active (upstream concept docs), so the emission is a plain
    # FightAction rather than a new action type. Gated on `active_raids` because
    # the tile exists statically but the boss is only fightable inside the
    # window; whether to ENGAGE is decided separately by ai/raid_participation.
    for raid in (state.active_raids if state is not None else []):
        raid_tiles = game_data.raid_location_tiles(raid.code)
        if raid_tiles:
            actions.append(FightAction(monster_code=raid.monster,
                                       locations=frozenset(raid_tiles)))
            actions.append(OptimizeLoadoutAction(target_monster_code=raid.monster,
                                                 game_data=game_data))

    for resource_code, locs in game_data.all_resource_locations.items():
        actions.append(GatherAction(resource_code=resource_code, locations=frozenset(locs)))
        # P1: one targeted gather per NON-primary drop (rare multi-drops —
        # gems from rocks, pearls from fishing). The planner simulates the
        # secondary yield directly (see GatherAction.drop_item_override), so
        # gem-ingredient recipe chains are plannable at last.
        primary = game_data.resource_drop_item(resource_code)
        seen: set[str] = set()
        for drop_item, _rate, _mn, _mx in game_data.resource_drop_table(resource_code):
            if drop_item != primary and drop_item not in seen:
                seen.add(drop_item)
                actions.append(GatherAction(
                    resource_code=resource_code, locations=frozenset(locs),
                    drop_item_override=drop_item))

    # One gather-loadout optimizer per gathering skill — lets the planner re-arm
    # with the best tool before a gather session (mirrors the per-monster combat
    # optimizers above).
    for skill in sorted(_GATHERING_SKILLS):
        actions.append(OptimizeLoadoutAction(target_skill=skill, game_data=game_data))

    # Craft, equip, and withdraw actions carry workshop/bank locations
    materials_to_withdraw: dict[str, int] = {}
    unit_withdraw_codes: set[str] = set()
    _level_skill_seen: set[tuple[str, int]] = set()
    for item_code, recipe in game_data.crafting_recipes.items():
        stats = game_data.item_stats(item_code)
        if stats is None:
            continue
        workshop_loc = game_data.workshop_location(stats.crafting_skill) if stats.crafting_skill else None
        actions.append(CraftAction(code=item_code, quantity=1, workshop_location=workshop_loc))
        if stats.crafting_skill and stats.crafting_level:
            _level_skill_seen.add((stats.crafting_skill, stats.crafting_level))
        for slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):
            actions.append(EquipAction(code=item_code, slot=slot))
        if ITEM_TYPE_TO_SLOTS.get(stats.type_):
            # Allow withdrawing the crafted item from bank to equip it
            actions.append(WithdrawItemAction(
                code=item_code, quantity=1, bank_location=bank, accessible=bank_accessible))
            unit_withdraw_codes.add(item_code)
            for mat_code, mat_qty in recipe.items():
                if mat_qty > materials_to_withdraw.get(mat_code, 0):
                    materials_to_withdraw[mat_code] = mat_qty
    # Gather-skill gates: a resource whose gather is skill-locked (iron_rocks,
    # mining 10) needs a LevelSkill(skill->level) to open it inside a
    # GatherMaterials search, exactly as an under-skill craft does. Craft gates
    # above cover a level only when some item is CRAFTED at it; a pure gather
    # gate (ore/wood/fish source with no coinciding craft) would otherwise have
    # no LevelSkill and its ore closure would be unplannable (the P3b
    # gather-gate livelock — l12_taskgated_bag iron_ore).
    for _res in game_data.resource_drops:
        _req = game_data.resource_skill_level(_res)
        if _req is not None:
            _level_skill_seen.add(_req)
    for _skill, _lvl in _level_skill_seen:
        actions.append(LevelSkill(skill=_skill, target_level=_lvl))

    # OWNED recipe-less equippables (NPC-bought bags/runes/artifacts, task
    # rewards): the loop above enumerates equips only for CRAFTABLE items, so
    # a held sandwhisper_bag had NO EquipAction and UpgradeEquipment's
    # closure-locked search died at 0 plans even at full capability (probe
    # 2026-07-06 @L50). Bounded to owned items so the action set stays small;
    # the acquisition legs (Fight xN -> NpcBuy) are GatherMaterials' job, and
    # ownership is exactly when the equip leg becomes real.
    if state is not None:
        owned_codes = set(state.inventory) | set(state.bank_items or {})
        for item_code in sorted(owned_codes):
            if item_code in game_data.crafting_recipes:
                continue  # already enumerated above
            stats = game_data.item_stats(item_code)
            if stats is None:
                continue
            slots = ITEM_TYPE_TO_SLOTS.get(stats.type_, [])
            for slot in slots:
                actions.append(EquipAction(code=item_code, slot=slot))
            if slots and item_code not in unit_withdraw_codes:
                actions.append(WithdrawItemAction(
                    code=item_code, quantity=1, bank_location=bank,
                    accessible=bank_accessible))
                unit_withdraw_codes.add(item_code)

    # Walk recipe closure transitively. The first pass above only adds
    # withdraws for DIRECT recipe inputs of equippables (e.g. copper_bar
    # for copper_dagger). Trace 2026-06-06 15:21: bot looped gather →
    # deposit copper_ore for 80 cycles because WithdrawItemAction
    # (copper_ore, ...) was never in the action set — copper_ore is the
    # recipe input of copper_bar (non-equippable), so the inner block
    # skipped it. Bank had 414 copper_ore unused while bot regathered.
    # Expand recipe chains so EVERY material the bot may need can be
    # withdrawn instead of regathered.
    pending = list(materials_to_withdraw.keys())
    while pending:
        code = pending.pop()
        sub_recipe = game_data.crafting_recipe(code)
        if not sub_recipe:
            continue
        for sub_mat, sub_qty in sub_recipe.items():
            # Quantity = parent withdraw qty x per-craft sub recipe qty,
            # capped to a reasonable batch (we never need more than one
            # full equippable's worth of raw materials in one withdraw).
            parent_qty = materials_to_withdraw.get(code, 1)
            desired = sub_qty * parent_qty
            if desired > materials_to_withdraw.get(sub_mat, 0):
                materials_to_withdraw[sub_mat] = desired
                pending.append(sub_mat)

    # Also add SMALLER-QUANTITY withdraws (one craft unit's worth) so
    # the action is applicable even when inventory_free is below the
    # full-chain quantity. Trace 2026-06-06 15:21: WithdrawItemAction
    # (copper_ore, 80) was added but state.inventory_free=56 — planner
    # fell back to gather. Adding Withdraw(copper_ore, 10) (one
    # copper_bar craft's worth) lets the planner chain
    # Withdraw → Craft → Withdraw → Craft instead.
    per_craft_withdraws: dict[str, int] = {}
    for item_code, recipe in game_data.crafting_recipes.items():
        if item_code in materials_to_withdraw:
            for sub_mat, sub_qty in recipe.items():
                if sub_qty > per_craft_withdraws.get(sub_mat, 0):
                    per_craft_withdraws[sub_mat] = sub_qty
    for mat_code, mat_qty in per_craft_withdraws.items():
        if mat_qty != materials_to_withdraw.get(mat_code, 0):
            actions.append(WithdrawItemAction(
                code=mat_code, quantity=mat_qty,
                bank_location=bank, accessible=bank_accessible))

    for mat_code, mat_qty in materials_to_withdraw.items():
        actions.append(WithdrawItemAction(
            code=mat_code, quantity=mat_qty, bank_location=bank, accessible=bank_accessible))

    # Residual-extraction withdraws: one x1 WithdrawItemAction per material.
    # The batched quantities above (full-chain xN, per-craft xn) strand bank
    # stock below the smallest batch: bank 28 copper_ore with only
    # Withdraw(copper_ore x10/x80) available leaves 8 ore unreachable, and
    # bank 1 copper_bar with only Withdraw(copper_bar x6) leaves the bar
    # unreachable. The goal layer's bank-aware gather pruning
    # (shopping_list.fully_covered_materials, used by GatherMaterialsGoal /
    # UpgradeEquipmentGoal.relevant_actions) credits bank stock at UNIT
    # granularity when it prunes the gather, so "net deficit 0" must imply
    # "every credited unit is withdrawable" or the pruning removes the sole
    # path to a needed item and breaks planner admissibility (trace
    # 2026-06-09 cycle-64: inv 22 ore + bank {ore: 28, bar: 1} → net 0 →
    # gather pruned → reachable ore 42 < 60 → 9-node plan failure). A x1
    # withdraw makes every banked unit extractable while keeping the action
    # count bounded (at most one extra action per material — no per-quantity
    # ladders); planner cost still prefers the batched withdraws, so x1
    # chains appear in plans only when residues are actually needed.
    for mat_code, mat_qty in materials_to_withdraw.items():
        unit_exists = (
            mat_qty == 1                              # full-chain withdraw is already x1
            or per_craft_withdraws.get(mat_code) == 1  # per-craft withdraw is already x1
            or mat_code in unit_withdraw_codes         # equippable input: equip-withdraw x1 above
        )
        if not unit_exists:
            actions.append(WithdrawItemAction(
                code=mat_code, quantity=1, bank_location=bank, accessible=bank_accessible))

    # Allow withdrawing task coins from bank for exchange
    actions.append(WithdrawItemAction(
        code=TASKS_COIN_CODE, quantity=1, bank_location=bank, accessible=bank_accessible))

    # Unequip actions: one per equipment slot
    all_slots = {slot for slots in ITEM_TYPE_TO_SLOTS.values() for slot in slots}
    for slot in all_slots:
        actions.append(UnequipAction(slot=slot))

    # Recycle actions: one per craftable equippable item.
    #
    # NO CODE-SET EXCLUSION (item-protection-authority epic). This loop used to skip
    # `protected_codes = protected_gear or (target_gear | target_tools)` — a
    # `frozenset[str]`, i.e. keep-ALL-copies, the exact type this epic exists to kill.
    # It was also the WRONG shape of defence: it shielded BiS codes (all 18 copies of
    # the axe, because the axe is a `target_tools` member) while leaving the heal
    # stock, the active task's own item and any non-BiS last tool wide open. WHAT may
    # be destroyed, and HOW MANY copies, is now the keep authority's single answer:
    # `ai/destructive_license.license_destructive_actions` filters this pool (and the
    # NpcSell / Delete emissions below) in `StrategyArbiter.select`, where the ctx the
    # authority reads is fully bound. Emitting the menu here and licensing it there is
    # deliberate: the factory runs BEFORE the strategy decision exists, so a gate
    # applied at this line would ask the authority with an empty `step_profile` and no
    # `crafting_target` — and would still licence destroying an active step's own
    # materials.
    for item_code in game_data.crafting_recipes:
        stats = game_data.item_stats(item_code)
        if stats is None or not ITEM_TYPE_TO_SLOTS.get(stats.type_):
            continue
        workshop_loc = game_data.workshop_location(stats.crafting_skill) if stats.crafting_skill else None
        actions.append(RecycleAction(code=item_code, quantity=1, workshop_location=workshop_loc))

    # Delete actions: built from current inventory when bank is locked (with the bank
    # open, banking is always the better slot-relief route). Cost weights:
    # ingredient=50 (harsher), sellable=25, worthless=5 (cheaper to delete) — a RANKING
    # among LICENSED victims only: `license_destructive_actions` removes the ones the
    # keep authority protects before the planner ever ranks them.
    if not bank_accessible and state is not None:
        equipped = set(state.equipment.values()) - {None}
        for item_code, qty in state.inventory.items():
            if qty <= 0 or item_code in equipped:
                continue
            actions.append(DeleteItemAction(
                code=item_code, quantity=1,
                cost_weight=delete_cost(item_code, game_data),
            ))

    # NPC buy actions: one per (npc, item) pair. Prior version filtered to
    # hp_restore>0 (consumables only), which made every non-potion vendor
    # item unreachable — the planner could never spend gold on weapons,
    # gear, tools, or ammo even when the merchant carried them. Drop the
    # filter so the action set covers the full vendor surface; the
    # planner / goal layer decides whether to actually buy.
    for npc_code, stock in game_data.npc_stock.items():
        npc_loc = game_data.npc_location(npc_code)
        for item_code in stock:
            if game_data.item_stats(item_code) is None:
                continue  # unknown item -> can't reason about it; skip safely
            actions.append(NpcBuyAction(
                npc_code=npc_code,
                item_code=item_code,
                quantity=1,
                npc_location=npc_loc,
            ))

    # NPC sell actions: one per (npc, item) pair where the NPC buys the item. Sales
    # DESTROY the copies they sell, so this menu is licensed by the keep authority in
    # `StrategyArbiter.select` (`ai/destructive_license`) — the unlicensed pool is what
    # let a bank-locked full bag sell the task's own item or the last tool for slots.
    for npc_code, sell_prices in game_data.npc_sell_prices.items():
        npc_loc = game_data.npc_location(npc_code)
        for item_code in sell_prices:
            actions.append(NpcSellAction(
                npc_code=npc_code,
                item_code=item_code,
                quantity=1,
                npc_location=npc_loc,
            ))

    # P5b: region-crossing transition edges + off-region content. Fights and
    # gathers for tiles OUTSIDE the overworld open region become plannable —
    # the planner chains Transition edges to reach them (movement folds only
    # within a region). Monster/resource codes already indexed by the legacy
    # (overworld) maps are NOT re-emitted for their overworld tiles.
    for (px, py, playr), (dx, dy, dlayer, conds) in sorted(
            game_data.world.transition_edges.items()):
        actions.append(MapTransitionAction(
            portal_x=px, portal_y=py, dest_x=dx, dest_y=dy, dest_layer=dlayer,
            conditions=conds,
            travel_region=game_data.region_of(px, py, playr)))
    layered_extra: dict[tuple[str, str], list[tuple[int, int]]] = {}
    for code, layered_tiles in game_data.world.layered_content.items():
        for (tx, ty, tlayer) in layered_tiles:
            region = game_data.region_of(tx, ty, tlayer)
            if region == "overworld":
                continue
            layered_extra.setdefault((code, region), []).append((tx, ty))
    for (code, region), region_tiles in sorted(layered_extra.items()):
        if code in game_data.monsters.levels:
            actions.append(FightAction(
                monster_code=code, locations=frozenset(region_tiles),
                travel_region=region))
            actions.append(OptimizeLoadoutAction(
                target_monster_code=code, game_data=game_data))
        elif game_data.resource_skill_level(code) is not None:
            actions.append(GatherAction(
                resource_code=code, locations=frozenset(region_tiles),
                travel_region=region))

    # Phase B: bank expansion, transitions, gold management
    actions.append(BuyBankExpansionAction(bank_location=bank, accessible=bank_accessible))
    # Teleport consumables (PLAN #6b): one TeleportAction per teleport item whose
    # destination map resolves to a known tile. The planner's cost search prefers a
    # warp over a long walk when cheaper; is_applicable gates on actually holding it.
    for item_code, stats in game_data.all_item_stats.items():
        if stats.teleport_map_id <= 0:
            continue
        dest = game_data.teleport_destination(item_code)
        if dest is not None:
            actions.append(TeleportAction(item_code=item_code, dest_x=dest[0], dest_y=dest[1]))
    # Gold deposit/withdraw with typical small quantities; let planner decide
    for q in (50, 100, 500, 1000):
        actions.append(DepositGoldAction(quantity=q, bank_location=bank, accessible=bank_accessible))
        actions.append(WithdrawGoldAction(quantity=q, bank_location=bank, accessible=bank_accessible))
    # Task trade is built only when current task is items-type
    if state is not None and state.task_type == "items" and state.task_code:
        task_code = state.task_code
        k = task_batch_size(state, game_data)
        stats = game_data.item_stats(task_code)
        workshop = (game_data.workshop_location(stats.crafting_skill)
                    if stats is not None and stats.crafting_skill else None)
        if workshop is not None and k > 1:
            actions.append(CraftAction(code=task_code, quantity=k, workshop_location=workshop))
        actions.append(TaskTradeAction(code=task_code, quantity=k, taskmaster_location=taskmaster))
        if k > 1:
            actions.append(TaskTradeAction(code=task_code, quantity=1, taskmaster_location=taskmaster))

    return actions
