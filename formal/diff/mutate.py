"""Mutation runner: each mutant the diff test fails to kill is a survivor -> gate fails."""
import argparse
import os
import queue
import shutil
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# Mutate<->play interlock: while this runner holds live mutants in src/, other
# consumers (artifactsmmo play) must not import the package. The reader side
# lives in src/artifactsmmo_cli/utils/mutation_lock.py — keep the filename
# string identical there (MUTATION_LOCKFILE_NAME).
MUTATION_LOCKFILE = ROOT / ".mutation-run.lock"
SRC = ROOT / "src" / "artifactsmmo_cli" / "utils" / "pathfinding.py"
TASK_BATCH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_batch.py"
INVENTORY_CAPS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "inventory_caps.py"
ACCUMULATION_SELL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "accumulation_sell.py"
DOMINANCE_PARETO_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "dominance_pareto.py"
COMBAT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "combat.py"
PROJECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "equipment" / "projection.py"
GATHERING_APPLY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "gathering.py"
LEVEL_SKILL_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "level_skill.py"
SCORING_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "equipment" / "scoring.py"
SKILL_XP_CURVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "skill_xp_curve.py"
SKILL_TARGET_CURVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "skill_target_curve.py"
SKILL_GRIND_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "skill_grind_selection.py"
SKILL_STEP_DISPATCH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "skill_step_dispatch.py"
ACTION_FACTORY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "factory.py"
RECIPE_CLOSURE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "recipe_closure.py"
TASK_FEASIBILITY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_feasibility.py"
PREREQUISITE_GRAPH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "prerequisite_graph.py"
OBJECTIVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "objective.py"
STRATEGY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "strategy.py"
BANK_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "bank_selection.py"
STUCK_DETECTOR_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "recovery.py"
PRIORITY_BAND_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "priority_band.py"
OWNED_COUNT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "owned_count.py"
ROOT_PROGRESS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "root_progress.py"
UPGRADE_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "upgrade_selection.py"
SCALAR_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "scalar_core.py"
PLANNER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "planner.py"
ARBITER_SELECT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "arbiter_select.py"
STICKY_SELECT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "sticky_select_core.py"
SERVABLE_FILTER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "servable_filter.py"
TASK_DECISION_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_decision_core.py"
OBJECTIVE_COMPLETION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "objective_completion.py"
LOW_YIELD_BOUNDARY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "low_yield_boundary.py"
STRATEGY_BLEND_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "strategy_blend.py"
DECIDE_KEY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "decide_key.py"
CYCLES_FOR_PROGRESS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "cycles_for_progress_core.py"
GATHER_APPLY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "gather_apply_core.py"
GATHER_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "gather_selection.py"
SHOPPING_LIST_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "shopping_list.py"
MIN_GATHERS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "min_gathers.py"
GATHER_STEP_TARGET_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "gather_step_target.py"
MONSTER_DROP_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "monster_drop_selection.py"
CRAFT_VS_BUY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "craft_vs_buy.py"
LIQUIDATION_VENUE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "liquidation_venue.py"
BUY_SOURCE_VENUE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "buy_source_venue.py"
NEAREST_TILE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "nearest_tile.py"
CONSUMABLE_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "consumable_selection.py"
BANK_EXPANSION_TIMING_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "bank_expansion_timing.py"
EVENT_WINDOW_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "event_availability.py"
COST_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "cost_core.py"
NPC_BUY_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "npc_buy_core.py"
TASK_TRADE_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "task_trade_core.py"
APPLY_MOVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "movement.py"
APPLY_EQUIP_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "equip.py"
APPLY_CLAIM_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "claim.py"
APPLY_REST_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "rest.py"
APPLY_FIGHT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "combat.py"
APPLY_BANK_EXPANSION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "bank_expansion.py"
APPLY_TELEPORT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "teleport.py"
CONSUMABLE_SUPPLY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "consumable_supply.py"
MEANS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "means.py"
GUARDS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "guards.py"
WITHDRAW_ITEM_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "withdraw_item.py"
UNEQUIP_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "unequip.py"
TASK_EXCHANGE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "task_exchange.py"
TASK_CANCEL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "task_cancel.py"
GATHERING_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "gathering.py"
PURSUE_TASK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "pursue_task.py"
SCALAR_PRIORITY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "scalar_priority.py"
EQUIP_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "equip.py"
STORE_WARMUP_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "store_warmup_core.py"
BANK_EXPANSION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "bank_expansion.py"
EXPAND_BANK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "expand_bank.py"
MONSTER_CATALOG_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "monster_catalog.py"
WINNABLE_CASCADE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "winnable_cascade.py"
COMBAT_PICKER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "combat_picker.py"
TASK_RESERVATION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_reservation.py"
PROJECTIONS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "projections.py"
# Phase-18 — additional Goal sources.
ACCEPT_TASK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "accept_task_goal.py"
CLAIM_PENDING_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "claim_pending.py"
TASK_EXCHANGE_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "task_exchange.py"
TASK_CANCEL_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "task_cancel.py"
COMPLETE_TASK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "complete_task_goal.py"
REACH_UNLOCK_LEVEL_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "reach_unlock_level.py"
LOW_YIELD_CANCEL_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "low_yield_cancel.py"
UNLOCK_BANK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "unlock_bank.py"
DISCARD_OVERSTOCK_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "discard_overstock.py"
PROGRESSION_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "progression.py"
RESTORE_HP_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "restore_hp.py"
DEPOSIT_INVENTORY_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "deposit_inventory.py"
SELL_INVENTORY_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "sell_inventory.py"
# Phase-19d — Tier-1 liveness measure (Python port of Formal.Liveness.Measure).
# Production sources reuse GATHERING_APPLY_SRC / APPLY_REST_SRC defined above.
MEASURE_SRC = ROOT / "formal" / "sim" / "measure.py"
# Phase-22b — cycle-loop mirror (Python port of Formal.Liveness.CycleStep).
CYCLE_STEP_SRC = ROOT / "formal" / "sim" / "cycle_step.py"

EQUIP_VALUE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "equip_value.py"
GAME_DATA_PARSE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "game_data.py"
LOCATION_CATALOG_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "location_catalog.py"
PROGRESSION_RESERVE_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "progression_reserve_core.py"
NEXT_CRAFT_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "next_craft_core.py"
CRAFT_PLAN_DRIVER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "craft_plan_driver_core.py"

# craft_plan_full / _apply_state mutations (B2 full-plan driver). The CONSUMING
# model is the soundness-critical part; killed by
# formal/diff/test_craft_plan_driver_diff.py (plan-agreement + reaches-target).
CRAFT_PLAN_DRIVER_MUTATIONS = [
    ("craft_plan_driver: drop craft input consumption",
     "                new_owned[inp] = new_owned.get(inp, 0) - per * na.qty",
     "                new_owned[inp] = new_owned.get(inp, 0)"),
    ("craft_plan_driver: craft consumption sign flip (- -> +)",
     "                new_owned[inp] = new_owned.get(inp, 0) - per * na.qty",
     "                new_owned[inp] = new_owned.get(inp, 0) + per * na.qty"),
    ("craft_plan_driver: withdraw skips bank debit",
     "        new_bank[na.item] = new_bank.get(na.item, 0) - na.qty",
     "        new_bank[na.item] = new_bank.get(na.item, 0)"),
]

# next_craft_target_pure mutations -- anchors for the deterministic craft-action
# generator (churn fix). Each breaks one of the four load-bearing decisions;
# killed by formal/diff/test_next_craft_diff.py (300-example property over random
# DAGs + spot-checks).
NEXT_CRAFT_MUTATIONS = [
    ("next_craft: drop per-scaling on required inputs",
     "        required = per * deficit",
     "        required = deficit"),
    ("next_craft: short-input off-by-one (< -> <=)",
     "        if owned.get(inp, 0) < required:",
     "        if owned.get(inp, 0) <= required:"),
    ("next_craft: None-boundary off-by-one (>= -> >)",
     "    if owned.get(target, 0) >= qty:",
     "    if owned.get(target, 0) > qty:"),
    ("next_craft: craft result emits gather kind",
     '    return NextAction(item, "craft", deficit)  # all inputs on hand → craft',
     '    return NextAction(item, "gather", deficit)  # all inputs on hand → craft'),
    # withdraw branch (banked-intermediate fix): banked short input → withdraw.
    ("next_craft: withdraw bank-check flip (== 0 -> != 0)",
     "            if bank.get(inp, 0) == 0:",
     "            if bank.get(inp, 0) != 0:"),
    ("next_craft: withdraw emits gather kind",
     '            return NextAction(inp, "withdraw", min(bank.get(inp, 0), required - owned.get(inp, 0)))',
     '            return NextAction(inp, "gather", min(bank.get(inp, 0), required - owned.get(inp, 0)))'),
    ("next_craft: withdraw qty min -> max (over-withdraw)",
     '            return NextAction(inp, "withdraw", min(bank.get(inp, 0), required - owned.get(inp, 0)))',
     '            return NextAction(inp, "withdraw", max(bank.get(inp, 0), required - owned.get(inp, 0)))'),
]

# Effect-parser coverage (stat-audit fixes).
RESTORE_FAMILY_MUTATIONS = [
    ("game_data: drop restore-family hp_restore mapping (restore/splash potions invisible)",
     '                    if effect.code in ("heal", "restore", "splash_restore"):',
     '                    if effect.code in ("heal",):'),
    ("game_data: drop inventory_space parse (bags' capacity stat invisible)",
     '                    elif effect.code == "inventory_space":',
     '                    elif effect.code == "inventory_space_disabled":'),
    ("game_data: drop haste parse (cooldown-reduction gear invisible)",
     '                    elif effect.code == "haste":',
     '                    elif effect.code == "haste_disabled":'),
    ("game_data: drop lifesteal parse (heal-on-crit gear invisible)",
     '                    elif effect.code == "lifesteal":',
     '                    elif effect.code == "lifesteal_disabled":'),
    ("game_data: invert monster-effect coverage guard (unmapped code silently dropped)",
     "                    elif code not in _MONSTER_EFFECT_CARVEOUTS:",
     "                    elif code in _MONSTER_EFFECT_CARVEOUTS:"),
]

# Event-content visibility gate (PLAN #4): event monster/resource spawns surface to
# the planner ONLY while their event is active. Killed by
# tests/test_ai/test_event_content_visibility.py.
EVENT_VISIBILITY_MUTATIONS = [
    ("location_catalog: drop active-event gate (event content always visible)",
     "        return ev is not None and ev in self.active_event_codes",
     "        return ev is not None"),
    ("location_catalog: invert active-event gate (event content visible only when dormant)",
     "        return ev is not None and ev in self.active_event_codes",
     "        return ev is not None and ev not in self.active_event_codes"),
]

# Skill-gate fast-fail + doomed-memo (2026-06-15 feather_coat CPU-peg fix).
GATHER_PLANNABLE_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "gather_plannable_core.py"
LEAF_ATTAINABLE_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "leaf_attainable_core.py"
COMPLETE_TASK_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "complete_task_core.py"
FUNDING_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "funding_core.py"
CURRENCY_AFFORD_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "currency_afford_core.py"
DOOMED_MEMO_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "doomed_memo.py"
STRATEGY_DRIVER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "strategy_driver.py"

# (description, old, new) -- old strings matched to the actual current pathfinding.py text.
MUTATIONS = [
    # step direction: invert the X step toward target
    ("step-dir: current_x < end_x -> +=1 becomes -=1",
     "        if current_x < end_x:\n            next_x += 1",
     "        if current_x < end_x:\n            next_x -= 1"),
    # step direction: invert the Y step toward target
    ("step-dir: current_y < end_y -> +=1 becomes -=1",
     "        if current_y < end_y:\n            next_y += 1",
     "        if current_y < end_y:\n            next_y -= 1"),
    # loop condition: or -> and (stops early on either axis aligned)
    ("loop-cond: while ... or ... -> and",
     "    while current_x != end_x or current_y != end_y:",
     "    while current_x != end_x and current_y != end_y:"),
    # total_distance: subtraction instead of addition of the two axis deltas
    ("total_distance: + -> - between axis deltas",
     "    total_distance = abs(end_x - start_x) + abs(end_y - start_y)",
     "    total_distance = abs(end_x - start_x) - abs(end_y - start_y)"),
    # total_distance: drop the Y term entirely
    ("total_distance: drop abs(end_y - start_y) term",
     "    total_distance = abs(end_x - start_x) + abs(end_y - start_y)",
     "    total_distance = abs(end_x - start_x)"),
    # estimated_time: change the per-step factor 5 -> 6
    ("estimated_time factor",
     "estimated_time = len(steps) * 5",
     "estimated_time = len(steps) * 6"),
]


# task_batch mutations -- old strings matched to the actual current task_batch.py text.
TASK_BATCH_MUTATIONS = [
    # invert the max(1, ...) floor: drop the floor so a 0-fit case yields 0, not 1.
    ("task_batch: drop max(1, ...) floor",
     "    return max(1, min(remaining, fit, BATCH_CAP))",
     "    return min(remaining, fit, BATCH_CAP)"),
    # drop the BATCH_CAP clamp entirely (allows results > 10).
    ("task_batch: drop BATCH_CAP clamp",
     "    return max(1, min(remaining, fit, BATCH_CAP))",
     "    return max(1, min(remaining, fit))"),
    # off-by-one on remaining (use task_total instead of task_total - progress).
    # P3a re-anchor: the read moved into the pure core (plain scalars).
    ("task_batch: off-by-one remaining (+1)",
     "    remaining = task_total - task_progress",
     "    remaining = task_total - task_progress + 1"),
]


# inventory_caps mutations -- old strings matched to current inventory_caps.py text.
INVENTORY_CAPS_MUTATIONS = [
    # drop the equipped floor: equipped items no longer guaranteed >= 1.
    # P3b re-anchor: the floor moved into the pure core (useful_quantity_cap_pure).
    ("inventory_caps: drop equipped max(1, ...) floor",
     "    if equipped:\n"
     "        return max(1, base)\n"
     "    return base",
     "    if equipped:\n"
     "        return base\n"
     "    return base"),
    # drop the safety-floor clamp: demanded items can fall below safety_floor.
    ("inventory_caps: drop safety-floor clamp",
     "        recipe_cap = max(recipe_cap, safety_floor)",
     "        recipe_cap = recipe_cap"),
    # overstock off-by-one: record over + 1 instead of over (the report
    # over-sheds every overstocked item by one unit).
    ("inventory_caps: overstock off-by-one (+1)",
     "            excess[code] = over",
     "            excess[code] = over + 1"),
    # drop the currency keep-floor: currencies (event_ticket, sandwhisper_coin,
    # …) fall to cap 0 and become delete/drain-eligible (the categorization bug).
    ("inventory_caps: drop currency keep-floor",
     '        if stats.type_ == "currency":\n'
     "            return CURRENCY_KEEP",
     '        if stats.type_ == "currency":\n'
     "            return 0"),
    # drop the consumable keep-floor: non-hp consumables (teleport / gold-bag
    # potions) fall to cap 0 and become delete/drain-eligible.
    ("inventory_caps: drop consumable keep-floor",
     '        if stats.type_ == "consumable":\n'
     "            return CONSUMABLE_KEEP",
     '        if stats.type_ == "consumable":\n'
     "            return 0"),
    # drop the level-distance ceiling clamp: far-out-of-band items keep their
    # full base cap (999 / full recipe demand) instead of <=10/<=5.
    ("inventory_caps: drop level-distance ceiling clamp",
     "    ceiling = level_distance_keep_ceiling(stats, state.level)\n"
     "    if ceiling is not None and base > ceiling:\n"
     "        return ceiling\n"
     "    return base",
     "    return base"),
    # drop the unique (non-tradeable) exemption: bound/unique items wrongly get
    # the level ceiling applied.
    ("inventory_caps: drop unique exemption in level ceiling",
     "    if stats is None or stats.tradeable is False:\n"
     "        return None",
     "    if stats is None:\n"
     "        return None"),
    # weaken the far ceiling (5 -> 6): keep one too many of a 10+-levels item.
    ("inventory_caps: KEEP_CEILING_FAR 5 -> 6",
     "KEEP_CEILING_FAR = 5",
     "KEEP_CEILING_FAR = 6"),
]


# accumulation_sell (ratio-driven sell-down) mutations. Killed by
# formal/diff/test_accumulation_sell_diff.py (real core vs the proved
# Formal.AccumulationSell defs through the `accumulation_sell` oracle).
ACCUMULATION_SELL_MUTATIONS = [
    # weaken the ratio gate (5 -> 3): items below 5x cap wrongly become excess.
    ("accumulation_sell: ACCUM_MULT 5 -> 3",
     "ACCUM_MULT = 5",
     "ACCUM_MULT = 3"),
    # drop the ratio gate entirely: every held quantity reports excess.
    ("accumulation_sell: drop ratio gate",
     "    if held < ACCUM_MULT * eff_cap:\n"
     "        return 0",
     "    if False:\n"
     "        return 0"),
    # steps off-by-one: geometric severity over-counts every doubling.
    ("accumulation_sell: steps k+1 -> k+2",
     "        k = k + 1",
     "        k = k + 2"),
    # steps loop boundary < instead of <=: under-counts at exact powers.
    ("accumulation_sell: steps loop <= -> <",
     "    while bound * 2 <= held:",
     "    while bound * 2 < held:"),
    # keep the eff_cap instead of the true cap: a dominated item (cap 0) keeps
    # 1 instead of selling to 0.
    ("accumulation_sell: keep eff_cap not true cap",
     "    keep = cap if cap > 0 else 0",
     "    keep = cap if cap > 0 else 1"),
]


# dominance_pareto (pareto_dominates) mutations. Killed by
# formal/diff/test_dominance_pareto_diff.py (real core vs the proved
# Formal.DominancePareto.paretoDominates through the `pareto_dominates` oracle).
DOMINANCE_PARETO_MUTATIONS = [
    # drop the strict-win requirement: an equal-everywhere peer wrongly dominates.
    ("dominance_pareto: drop gt_some (ties dominate)",
     "    return geq_all and gt_some",
     "    return geq_all"),
    # geq comparator >= -> > : a tie on one component wrongly un-dominates.
    ("dominance_pareto: geq_all >= -> >",
     "    geq_all = all(p >= i for p, i in zip(peer_scores, item_scores))",
     "    geq_all = all(p > i for p, i in zip(peer_scores, item_scores))"),
    # strict comparator > -> >= : equal vectors wrongly dominate.
    ("dominance_pareto: gt_some > -> >=",
     "    gt_some = any(p > i for p, i in zip(peer_scores, item_scores))",
     "    gt_some = any(p >= i for p, i in zip(peer_scores, item_scores))"),
]


# inventory_profile (overstock_excess) mutations -- the space-driven,
# profile-preserving overstock core. Each breaks one of the three proved
# guarantees and is killed by formal/diff/test_inventory_profile_diff.py.
INVENTORY_PROFILE_MUTATIONS = [
    # Drop the watermark gate: overstock fires regardless of space pressure
    # (resurrects the space-blind dump trigger — the bug). Killed by the
    # space-driven differential (16/20 below watermark must yield 0).
    ("inventory_profile: drop watermark gate (always under pressure)",
     "    if cap <= 0 or used * watermark_den < cap * watermark_num:\n"
     "        return 0",
     "    if cap <= 0:\n"
     "        return 0"),
    # Flip the pressure comparison < -> <= : a state exactly one unit below the
    # watermark wrongly reads as under pressure (off-by-one on the gate).
    ("inventory_profile: pressure comparison flip (< -> <=)",
     "    if cap <= 0 or used * watermark_den < cap * watermark_num:",
     "    if cap <= 0 or used * watermark_den <= cap * watermark_num:"),
    # Use min instead of max for the protected floor: the floor collapses to the
    # SMALLER of profile_target / useful_floor, so a profile item above the
    # useful floor can be shed below its target (breaks profile-protection).
    ("inventory_profile: protected floor max -> min",
     "    floor = profile_target if profile_target > useful_floor else useful_floor",
     "    floor = profile_target if profile_target < useful_floor else useful_floor"),
    # overstock off-by-one: shed held - floor + 1 (over-discards by one).
    ("inventory_profile: overstock off-by-one (+1)",
     "    if held > floor:\n"
     "        return held - floor",
     "    if held > floor:\n"
     "        return held - floor + 1"),
    # overstock floor-drop: shed held - floor + 1 via floor underflow — return
    # the full held instead of held - floor (sheds a profile item below its
    # target). Kills the protected-floor subtraction.
    ("inventory_profile: drop protected floor from excess (held - floor -> held)",
     "    if held > floor:\n"
     "        return held - floor\n"
     "    return 0",
     "    if held > floor:\n"
     "        return held\n"
     "    return 0"),
    # NOTE: a `held > floor -> held >= floor` mutant was considered and
    # REJECTED as an EQUIVALENT mutant: at `held == floor` the `>=` branch
    # returns `held - floor == 0`, identical to the original's `return 0`, and
    # both agree for every other `held`. Shipping an unkillable equivalent
    # mutant is proof-theater; the strict-vs-nonstrict boundary is instead
    # pinned by the Lean `overstock_pos_iff` (excess > 0 iff held > floor).
]


# predict_win mutations -- old strings matched to current combat.py text.
PREDICT_WIN_MUTATIONS = [
    # initiative tiebreak: flip the player-first `<=` to a strict `<` (combat.py:79).
    ("predict_win: tiebreak <= -> < (player-first)",
     "    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die",
     "    return rounds_to_kill < rounds_to_die if player_first else rounds_to_kill < rounds_to_die"),
    # drop the expected critical-strike contribution from the (exact-integer) kill rate.
    ("predict_win: drop crit term in killStep (200+crit -> 200)",
     "    kill_step = (50 * raw_player * (200 + p.critical_strike)",
     "    kill_step = (50 * raw_player * (200 + 0)"),
    # off-by-one in the half-up rounding (ceil-ish): + 0.5 -> + 1.5.
    ("predict_win: round_half_up off-by-one (+0.5 -> +1.5)",
     "    return math.floor(value + 0.5)",
     "    return math.floor(value + 1.5)"),
]

# Lifesteal terms (heal-on-crit) and poison term (per-turn DoT). Killed by the
# guard / flip tests in test_predict_win_diff.py + test_combat.py (drop a term ⇒
# the killStep≤0 / dieStep≤0 guard no longer fires, or a poison loss flips win).
PREDICT_WIN_LIFESTEAL_MUTATIONS = [
    ("predict_win: drop monster lifesteal term in killStep",
     "                 - m_crit * game_data.monster_lifesteal(monster_code) * m_atk_sum\n",
     "                 - 0 * game_data.monster_lifesteal(monster_code) * m_atk_sum\n"),
    ("predict_win: drop monster healing regen term in killStep",
     "                 - game_data.monster_healing(monster_code) * game_data.monster_hp(monster_code) * 100\n",
     "                 - game_data.monster_healing(monster_code) * game_data.monster_hp(monster_code) * 0\n"),
    ("predict_win: drop monster void_drain self-heal term in killStep",
     "                 - game_data.monster_void_drain(monster_code) * p.max_hp * 100\n",
     "                 - game_data.monster_void_drain(monster_code) * p.max_hp * 0\n"),
    ("predict_win: drop monster protective_bubble term in killStep",
     "                 - game_data.monster_protective_bubble(monster_code) * raw_player * (200 + p.critical_strike) // 2)",
     "                 - game_data.monster_protective_bubble(monster_code) * 0 * raw_player * (200 + p.critical_strike) // 2)"),
    ("predict_win: drop player lifesteal term in dieStep",
     "                - p.critical_strike * player_lifesteal * p_atk_sum",
     "                - 0 * player_lifesteal * p_atk_sum"),
    ("predict_win: drop monster poison term in dieStep",
     "                + max(0, game_data.monster_poison(monster_code) - player_antipoison) * 10000",
     "                + max(0, game_data.monster_poison(monster_code) - player_antipoison) * 0"),
    ("predict_win: ignore player antipoison (poison not capped)",
     "                + max(0, game_data.monster_poison(monster_code) - player_antipoison) * 10000",
     "                + max(0, game_data.monster_poison(monster_code) - 0) * 10000"),
    ("predict_win: drop monster burn term in dieStep",
     "                + game_data.monster_burn(monster_code) * p_atk_sum * 100\n",
     "                + game_data.monster_burn(monster_code) * p_atk_sum * 0\n"),
    ("predict_win: drop monster void_drain player-loss term in dieStep",
     "                + game_data.monster_void_drain(monster_code) * p.max_hp * 100\n",
     "                + game_data.monster_void_drain(monster_code) * p.max_hp * 0\n"),
    ("predict_win: drop monster berserker_rage boost term in dieStep",
     "                + game_data.monster_berserker_rage(monster_code) * raw_monster * (200 + m_crit) // 2\n",
     "                + game_data.monster_berserker_rage(monster_code) * 0 * raw_monster * (200 + m_crit) // 2\n"),
    ("predict_win: drop monster frenzy boost term in dieStep",
     "                + game_data.monster_frenzy(monster_code) * raw_monster * (200 + m_crit) // 2)",
     "                + game_data.monster_frenzy(monster_code) * 0 * raw_monster * (200 + m_crit) // 2)"),
    ("predict_win: drop monster barrier term in effective HP",
     "    effective_monster_hp = game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code)",
     "    effective_monster_hp = game_data.monster_hp(monster_code) + game_data.monster_barrier(monster_code) * 0"),
    ("predict_win: drop reconstitution turn-cap guard",
     "    if 0 < reconstitution <= rounds_to_kill:",
     "    if 0 < reconstitution <= 0:"),
]


# loadout_projection mutations -- old strings matched to current projection.py text.
PROJECTION_MUTATIONS = [
    # sign flip: new − old becomes old − new on the dmg field (negates the delta).
    ("loadout_projection: dmg delta sign flip (new-old -> old-new)",
     "        dmg += (new_s.dmg if new_s else 0) - (old_s.dmg if old_s else 0)",
     "        dmg += (old_s.dmg if old_s else 0) - (new_s.dmg if new_s else 0)"),
    # drop a slot's delta: critical_strike no longer accumulates (delta dropped).
    ("loadout_projection: drop critical_strike delta",
     "        critical_strike += (new_s.critical_strike if new_s else 0) - (old_s.critical_strike if old_s else 0)",
     "        critical_strike += 0"),
    # off-by-one: max_hp delta gains a spurious +1.
    ("loadout_projection: max_hp delta off-by-one (+1)",
     "        max_hp += (new_s.hp_bonus if new_s else 0) - (old_s.hp_bonus if old_s else 0)",
     "        max_hp += (new_s.hp_bonus if new_s else 0) - (old_s.hp_bonus if old_s else 0) + 1"),
]


# equipment_scoring mutations -- old strings matched to current scoring.py text.
SCORING_MUTATIONS = [
    # drop the level filter in _candidates_for_slot: below-level items become
    # eligible, so an above-level higher-score item can be (wrongly) picked.
    ("equipment_scoring: drop level filter in _candidates_for_slot",
     "        if stats is None or state.level < stats.level:",
     "        if stats is None:"),
    # drop the no-downgrade guard: force the swap branch so the selector
    # always swaps to the argmax candidate even when it is strictly WORSE than
    # the equipped item. 2026-06-11 re-anchor: the per-slot `improves` flag
    # collapsed into the shared `best_score > current_score` comparison when
    # pick_loadout moved to the one-slot-per-code projected-result rule.
    ("equipment_scoring: drop no-downgrade guard (swap forced True)",
     "        if best_score > current_score:\n"
     "            result[slot] = best.code",
     "        if True:\n"
     "            result[slot] = best.code"),
    # drop the weapon clamp: max(0, 100 - res) -> (100 - res), letting a
    # high-resistance monster make a strong weapon score NEGATIVE (so a weak weapon
    # could be preferred / scores go below 0). P4b re-anchor: the formula moved
    # into the extracted pure core `weapon_score_raw_pure`; the `weapon_score_raw`
    # wrapper delegates, so the mutant still flows into the diff comparison.
    ("equipment_scoring: drop weapon clamp max(0, 100 - res)",
     "        score = score + attack.get(elem, 0)"
     " * max(0, 100 - monster_resistance.get(elem, 0))",
     "        score = score + attack.get(elem, 0)"
     " * (100 - monster_resistance.get(elem, 0))"),
    # drop the crit factor: the expected critical-strike multiplier
    # (200 + crit) is what makes the loadout picker agree with predict_win's
    # damage model (run-18 2026-06-12: without it a crit-0 tool out-scored a
    # crit-35 weapon and Robby ground slimes with a pickaxe). Killed by the
    # crit-bearing Hypothesis cases in test_equipment_scoring_diff.py.
    ("equipment_scoring: drop crit factor (200 + critical_strike)",
     "    return score * (200 + critical_strike)",
     "    return score"),
    # Byte-equivalence kill: divide armor_score by 100, turning the exact integer
    # surrogate into a float that no longer matches the Lean integer model
    # byte-for-byte. The diff test asserts py_score == lean_score as integers;
    # this mutation makes py a float and breaks the int identity. P4b re-anchor:
    # the formula moved into the extracted pure core `armor_score_pure` (same
    # mutation intent; the `armor_score` wrapper delegates).
    ("equipment_scoring: armor_score float-rescale (breaks byte-equivalence)",
     "        score = score + monster_attack.get(elem, 0) * resistance.get(elem, 0)",
     "        score = score + monster_attack.get(elem, 0) * resistance.get(elem, 0) / 100.0"),
]


# realizable_loadout mutations -- target the per-code OCCUPANCY-CAP rule in
# scoring.pick_loadout (2026-06-14 re-anchor: the one-slot-per-code filter is
# now ownership-capped — cap=1 for non-dup codes, cap=ownership for
# duplicate-allowed types (rings), so a ring fills a 2nd slot only up to
# physical ownership). Each mutation breaks realizability, the dup-free-except
# property, the dual-ring / no-over-fill anchors, or the empty-fill/no-downgrade
# rules, killed by formal/diff/test_realizable_loadout_diff.py.
REALIZABLE_LOADOUT_MUTATIONS = [
    # THE CAP RULE, mutation 1: drop the feasibility filter entirely — every
    # type/level candidate is feasible. Resurrects the multi-slot duplicate
    # (one copy, two slots, unrealizable) and the non-ring 485 livelock (a
    # duplicate utility/non-dup code in a sibling slot). Killed by the
    # dup-free-except property + realizability.
    ("realizable_loadout: drop occupancy-cap feasibility filter",
     "        feasible: list[ItemStats] = [\n"
     "            cand for cand in candidates if not _forbidden(cand.code, slot)\n"
     "        ]",
     "        feasible: list[ItemStats] = list(candidates)"),
    # THE CAP RULE, mutation 2: scan the ORIGINAL equipment instead of the
    # projected result. Earlier slots' fresh assignments are no longer counted
    # for later slots, so two empty sibling slots can both take the same single
    # inventory copy. Killed by the dup-free-except property / realizability.
    ("realizable_loadout: occupancy scan uses equipment instead of projected result",
     "        worn_elsewhere = sum(\n"
     "            1 for s, worn in result.items() if s != slot and worn == code\n"
     "        )",
     "        worn_elsewhere = sum(\n"
     "            1 for s, worn in state.equipment.items() if s != slot and worn == code\n"
     "        )"),
    # CARVE-OUT mutation A: dup-allowed is ALWAYS true — every type gets the
    # ownership cap, so a non-ring code owned twice (e.g. a utility) fills two
    # sibling slots, resurrecting the 485 bug for non-dup types. Killed by the
    # dup-free-except property (non-ring codes must stay strictly one-slot).
    ("realizable_loadout: dup-allowed carve-out over-broad (always True)",
     "        return stats is not None and stats.type_ in DUPLICATE_SLOT_TYPES",
     "        return True"),
    # CARVE-OUT mutation B: rings UNCAPPED (cap 99 ignores ownership) — a single
    # owned ring fills BOTH ring slots, an unrealizable double-equip. Killed by
    # the single-ring-no-spare boundary anchor + realizability.
    ("realizable_loadout: ring cap ignores ownership (uncapped)",
     "        cap = (ownership(code, state.inventory, state.equipment)\n"
     "               if _dup_allowed(code) else 1)",
     "        cap = (99\n"
     "               if _dup_allowed(code) else 1)"),
    # CARVE-OUT mutation C: cap comparison off-by-one (>= -> >) — a non-dup code
    # already worn once (count 1, cap 1) is no longer forbidden, so it takes a
    # 2nd slot. Killed by the dup-free-except property.
    ("realizable_loadout: occupancy-cap off-by-one (>= -> >)",
     "        return worn_elsewhere >= cap",
     "        return worn_elsewhere > cap"),
    # Zero-score empty-fill suppression off-by-strictness: `<= 0` -> `< 0`
    # fills an empty slot with a zero-score item, burning the code's one legal
    # slot for no benefit. Killed by the empty-fill strict-positivity property
    # and its deterministic dual fixture.
    ("realizable_loadout: zero-score empty-fill suppression (<= 0 -> < 0)",
     "            if current_code is None and best_score <= 0:",
     "            if current_code is None and best_score < 0:"),
    # No-downgrade strictness: `>` -> `>=` swaps on a plain score TIE,
    # violating Property 2 (a filled slot swaps ONLY on a STRICT improvement;
    # Lean `pickSlotStep_no_downgrade`). Killed by the deterministic tie-keep
    # fixture and the strict no-downgrade property.
    ("realizable_loadout: no-downgrade strictness (> -> >=)",
     "        if best_score > current_score:\n"
     "            result[slot] = best.code",
     "        if best_score >= current_score:\n"
     "            result[slot] = best.code"),
    # Swap weapon_score and armor_score per slot: weapon_slot uses armor_score
    # (defense-oriented) and the rest use weapon_score (offense-oriented).
    # Violates Property 3 (per-slot argmax under the SLOT-CORRECT score
    # function; Lean `pickSlotStep_optimal` is parameterised by the score).
    # 2026-06-11 re-anchor: the `if slot == "weapon_slot":` dispatch became
    # the hoisted `weapon` flag.
    ("realizable_loadout: swap weapon_score and armor_score per slot",
     "        if weapon:\n"
     "            best = max(feasible, key=lambda s: weapon_score(s, monster_res))\n"
     "        else:\n"
     "            best = max(feasible, key=lambda s: armor_score(s, monster_atk))",
     "        if weapon:\n"
     "            best = max(feasible, key=lambda s: armor_score(s, monster_atk))\n"
     "        else:\n"
     "            best = max(feasible, key=lambda s: weapon_score(s, monster_res))"),
]


# skill_xp_curve mutations -- old strings matched to current skill_xp_curve.py text.
SKILL_XP_CURVE_MUTATIONS = [
    # confidence off-by-one: inflate the observed-gap count by 1.
    ("skill_xp_curve: confidence off-by-one (observed + 1)",
     "        observed = sum(1 for lvl in levels if lvl in self.observed)\n"
     "        return observed / len(levels)",
     "        observed = sum(1 for lvl in levels if lvl in self.observed)\n"
     "        return (observed + 1) / len(levels)"),
    # cycles guard flip: target_level <= current_level -> target_level < current_level
    # (so target == current no longer returns 0.0 / takes the wrong branch).
    ("skill_xp_curve: cycles guard flip (<= -> <)",
     "        if target_level <= current_level:\n            return 0.0",
     "        if target_level < current_level:\n            return 0.0"),
    # total non-monotone: drop the last term of the range (range stops one short).
    ("skill_xp_curve: total drops last term (range -1)",
     "        return sum(self.required_xp(lvl) for lvl in range(current_level, target_level))",
     "        return sum(self.required_xp(lvl) for lvl in range(current_level, target_level - 1))"),
]


# skill_target_curve mutations -- pure-core anchors for skill_curve_target_pure.
# Each substring is copied verbatim from skill_target_curve.py (indentation
# included) so the mutation applies unambiguously; killed by the differential
# test formal/diff/test_skill_target_curve_diff.py (mirrors the equipment_scoring
# pure-core anchors).
SKILL_TARGET_CURVE_MUTATIONS = [
    # drop the lookahead window widening -- items that should be in range are
    # excluded, lowering targets the diff test catches.
    ("skill_target_curve: drop +lookahead window",
     "                and it.item_level <= char_level + lookahead\n",
     "                and it.item_level <= char_level\n"),
    # drop the max-skill clamp -- a malformed craft_level > max leaks through;
    # diff catches the unclamped value.
    ("skill_target_curve: drop max_skill clamp",
     "    if best > max_skill_level:\n        return max_skill_level\n",
     "    if False:\n        return max_skill_level\n"),
    # flip the running-max compare to <, under-targeting.
    ("skill_target_curve: running max becomes running min",
     "                and it.craft_level > best):\n",
     "                and it.craft_level < best):\n"),
]


# skill_grind_selection mutations -- pure-core anchors for
# skill_grind_selection_pure (the recipe-aware skill-grind target selector).
# Each substring is copied verbatim from skill_grind_selection.py (indentation
# included) so the mutation applies unambiguously; killed by the differential
# test formal/diff/test_skill_grind_selection_diff.py, which encodes the four
# role theorems (grind_same_skill / grind_in_level / grind_obtainable /
# grind_actionable) from formal/Formal/SkillGrindSelection.lean.
SKILL_GRIND_SELECTION_MUTATIONS = [
    # THE LOAD-BEARING ONE: drop the same-skill guard -- selection may return a
    # CROSS-SKILL item, the exact failure grind_same_skill forbids. The diff
    # MUST kill this.
    ("skill_grind_selection: drop same-skill guard",
     "        if c.craft_skill != skill or c.craft_level > current_level or not c.obtainable:\n",
     "        if c.craft_level > current_level or not c.obtainable:\n"),
    # drop the obtainable guard -- an unobtainable item can win, violating
    # grind_obtainable (the live weaponcrafting bug).
    ("skill_grind_selection: drop obtainable guard",
     "        if c.craft_skill != skill or c.craft_level > current_level or not c.obtainable:\n",
     "        if c.craft_skill != skill or c.craft_level > current_level:\n"),
    # drop the in-level guard -- an over-level item can win, violating
    # grind_in_level.
    ("skill_grind_selection: drop in-level guard",
     "        if c.craft_skill != skill or c.craft_level > current_level or not c.obtainable:\n",
     "        if c.craft_skill != skill or not c.obtainable:\n"),
    # flip the fewest-missing ordering in _beats -- breaks the (-mats_missing,
    # craft_level) selection order; killed by the diff's tie/ordering cases.
    ("skill_grind_selection: _beats fewest-missing flip",
     "        return c.mats_missing < best.mats_missing\n",
     "        return c.mats_missing > best.mats_missing\n"),
    # neuter the wanted-first clause -- a WANTED keeper no longer beats a cheaper
    # throwaway, reviving the apprentice_gloves-over-copper_dagger inversion.
    # Killed by test_wanted_beats_cheaper_throwaway_diff.
    ("skill_grind_selection: _beats drop wanted preference",
     "    if c.wanted and not best.wanted:\n        return True\n",
     "    if c.wanted and not best.wanted:\n        return False\n"),
    # invert the wanted-shield clause -- an UNWANTED candidate displaces a wanted
    # incumbent. Killed by the wanted-first scenarios (winner flips off the keeper).
    ("skill_grind_selection: _beats invert wanted shield",
     "    if best.wanted and not c.wanted:\n        return False\n",
     "    if best.wanted and not c.wanted:\n        return True\n"),
]


# skill_step_dispatch mutations -- anchors for the EXTRACTED combine_dispatch_pure
# (the reservation-aware grind/suppress/no-grind combiner). Killed by the
# differential test formal/diff/test_skill_step_dispatch_diff.py, which encodes
# the role theorems (suppress_correct / full_preference / forward_progress /
# grind_valid) from formal/Formal/SkillStepDispatch.lean. The combine-direct case
# feeds BOTH picks non-empty so the full-preference branch is exercised (the
# pipeline wrapper short-circuits it).
SKILL_STEP_DISPATCH_MUTATIONS = [
    # drop the suppress guard -- never suppresses, violating suppress_correct.
    ("skill_step_dispatch: drop suppress guard",
     "    if committed_skill == skill and committed_level <= current_level:\n",
     "    if False:\n"),
    # suppress boundary <= -> < -- a craftable-now committed item at the exact
    # current level no longer suppresses; violates suppress_correct.
    ("skill_step_dispatch: suppress boundary <= to <",
     "    if committed_skill == skill and committed_level <= current_level:\n",
     "    if committed_skill == skill and committed_level < current_level:\n"),
    # flip the full/relaxed preference -- prefers the relaxed pick, violating
    # full_preference (reservation honored only when forced to relax).
    ("skill_step_dispatch: full-preference flip",
     '    pick = full_pick if full_pick != "" else relaxed_pick\n',
     '    pick = relaxed_pick if relaxed_pick != "" else full_pick\n'),
    # always-grind -- returns ("grind", "") when both passes are empty, violating
    # the NO_GRIND contract (grind_valid would have no candidate).
    ("skill_step_dispatch: drop no-grind guard",
     '    if pick != "":\n',
     "    if True:\n"),
]

STRATEGIC_VALUE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "strategic_value.py"

# strategic_value mutations -- anchors for the EXTRACTED strategic_value_pure
# (efficiency-weighted cross-slot scorer, #16). Killed by the differential test
# formal/diff/test_strategic_value_diff.py, which asserts exact-integer agreement
# with the proved Lean core Extracted.StrategicValue.strategic_value_pure plus
# the nonneg + per-stat monotonicity contracts (Bridges9). Each substring is
# code-unique (the docstring deliberately avoids the `stat * weight` tokens).
STRATEGIC_VALUE_MUTATIONS = [
    # drop the haste contribution -- diverges whenever haste>0 and haste_weight>0.
    ("strategic_value: drop haste term",
     "        + haste * haste_weight",
     "        + haste * 0"),
    # drop the prospecting contribution.
    ("strategic_value: drop prospecting term",
     "        + prospecting * prospecting_weight",
     "        + prospecting * 0"),
    # swap the inventory weight for the combat weight -- diverges when the two
    # derived rates differ (they always do: combat dominates).
    ("strategic_value: inventory weight becomes combat weight",
     "        + inventory_space * inventory_weight",
     "        + inventory_space * combat_weight"),
    # flip the wisdom term's sign -- diverges and breaks nonneg under wisdom>0.
    ("strategic_value: negate wisdom term",
     "        + wisdom * wisdom_weight",
     "        - wisdom * wisdom_weight"),
    # combat product becomes a sum -- diverges unless combat_raw or weight is 0/1.
    ("strategic_value: combat product becomes sum",
     "        combat_raw * combat_weight",
     "        combat_raw + combat_weight"),
]


# grind_ladder mutations -- anchors for dispatch_candidate_flags / cannibalize_pure
# (the reservation-flag hoisting). Killed by formal/diff/test_grind_ladder_diff.py,
# which binds them to Formal.GrindLadder.flagsFor / cannibalizeModel -- the SAME
# defs the liveness theorems (grind_when_unowned_target / grind_when_all_owned)
# are proved over. Same source file as the combine mutations above.
GRIND_LADDER_MUTATIONS = [
    # drop the target exemption -- a target's mats are no longer freed, so the
    # grind freezes (the 2026-06-14 230824 regression); flags diverge from Lean.
    ("grind_ladder: drop exempt guard",
     "    exempt = c.is_target and c.craft_level <= current_level and not c.owned\n",
     "    exempt = False\n"),
    # exempt OWNED instead of unowned -- re-grinds owned targets (over-craft) and
    # withholds the exemption from unowned ones.
    ("grind_ladder: exempt owned instead of unowned",
     "    exempt = c.is_target and c.craft_level <= current_level and not c.owned\n",
     "    exempt = c.is_target and c.craft_level <= current_level and c.owned\n"),
    # relaxed pass ignores cannibalize -- never frees the relaxed reservation, so
    # the all-owned corner freezes instead of cannibalizing.
    ("grind_ladder: relaxed ignores cannibalize",
     "    uses_relaxed = ((not exempt) and (not cannibalize)\n",
     "    uses_relaxed = ((not exempt) and (True)\n"),
    # flip the cannibalize ownership test -- fires cannibalization while unowned
    # items remain (and withholds it when all owned).
    ("grind_ladder: cannibalize ownership flip",
     "    return len(feasible) > 0 and not any(not c.owned for c in feasible)\n",
     "    return len(feasible) > 0 and any(not c.owned for c in feasible)\n"),
    # drop the obtainable filter in the feasible set -- an unobtainable item wrongly
    # counts toward the all-owned cannibalize decision.
    ("grind_ladder: cannibalize drop obtainable filter",
     "                if c.craft_level <= current_level and c.obtainable]\n",
     "                if c.craft_level <= current_level]\n"),
]


# recipe_closure mutations -- old strings matched to current recipe_closure.py text
# (P3a re-anchor: the cores are the fueled pure functions `_closure_visited` /
# `_raw_units`. The closure DFS's own visited guard became OUTPUT-equivalent
# under the fuel bound — every original call-tree path still runs with the same
# per-path fuel, so dropping it only re-explores — a genuinely equivalent
# mutant; the cyclic-safety-guard mutation therefore targets `_raw_units`,
# where the revisit short-circuit IS value-bearing: revisit -> 1).
RECIPE_CLOSURE_MUTATIONS = [
    # drop the visited guard in _raw_units: revisits no longer cost 1, so cyclic
    # recipes multiply around the loop until the fuel truncates (wrong totals;
    # the pinned cyclic case yields 12 instead of 6).
    ("recipe_closure: drop visited guard (no revisit short-circuit)",
     "    if visited.get(item, 0) == 1:\n        return 1\n    recipe = recipes.get(item, {})",
     "    recipe = recipes.get(item, {})"),
    # omit a recipe edge: recurse only into the FIRST sub-material, missing the
    # rest of the closure (incomplete craftable_mats / needed_resources).
    ("recipe_closure: omit recipe edges (recurse first sub only)",
     "    for sub_mat, _qty in recipe.items():\n"
     "        visited = _closure_visited(fuel - 1, sub_mat, recipes, visited)",
     "    for sub_mat, _qty in list(recipe.items())[:1]:\n"
     "        visited = _closure_visited(fuel - 1, sub_mat, recipes, visited)"),
    # alter the qty factor in _raw_units: drop the qty multiplier so quantities
    # no longer multiply down the tree (wrong units total).
    ("raw_material_units: drop qty factor (qty * units -> units)",
     "        total = total + qty * _raw_units(fuel - 1, sub, recipes, deeper)",
     "        total = total + _raw_units(fuel - 1, sub, recipes, deeper)"),
]


# root_progress mutations -- the deepened gear-root progress witness `_obtain_progress`.
# Each breaks the faithfulness the proved `obtainProgress` theorems guarantee and is killed
# by formal/diff/test_obtain_progress_diff.py (binds the live function to the Lean def).
ROOT_PROGRESS_MUTATIONS = [
    # drop the bank term: banked material no longer counts toward progress, so the
    # witness undercounts whenever the bot has deposited intermediates (random bank
    # counts in the diff make py != lean).
    ("root_progress: drop bank term (inventory only)",
     "        owned = state.inventory.get(node, 0) + bank.get(node, 0)",
     "        owned = state.inventory.get(node, 0)"),
    # drop the raw_material_units weight: unweighted owned count, so a craft conversion
    # (10 ore -> 1 bar) no longer conserves and gathering registers the wrong magnitude.
    ("root_progress: drop raw-unit weight (owned * units -> owned)",
     "            total += owned * raw_material_units(game_data, node)",
     "            total += owned"),
    # shallow regression: skip the transitive closure so only the target itself counts
    # (the original copper_boots never-crafted bug — ore-gathering reads as no progress).
    ("root_progress: skip transitive closure (target only)",
     "    closure_demand(code, 1, game_data, demand, frozenset())",
     "    demand.clear()"),
]


# task_feasibility mutations -- old strings matched to current task_feasibility.py text.
TASK_FEASIBILITY_MUTATIONS = [
    # worst -> min instead of max: pick the SMALLEST gap rather than the highest
    # required_level (flip the comparison so a smaller sub replaces worst).
    ("task_feasibility: worst max -> min (> becomes <)",
     "        if sub is not None and (worst is None or sub.required_level > worst.required_level):",
     "        if sub is not None and (worst is None or sub.required_level < worst.required_level):"),
    # drop the closure recursion: only consider the FIRST ingredient, missing the
    # rest of the craft closure (incomplete worst gap).
    ("task_feasibility: closure recurse first ingredient only",
     "    for ingredient in recipe:\n"
     "        sub = _item_skill_gap(ingredient, state, game_data, seen)",
     "    for ingredient in list(recipe)[:1]:\n"
     "        sub = _item_skill_gap(ingredient, state, game_data, seen)"),
    # monster margin off-by-one: > MARGIN becomes >= MARGIN, so a monster EXACTLY
    # at char_level + 2 (the boundary) would wrongly gate.
    ("task_feasibility: monster margin off-by-one (> -> >=)",
     "        if monster_level > 0 and monster_level > state.level + MONSTER_LEVEL_MARGIN:",
     "        if monster_level > 0 and monster_level >= state.level + MONSTER_LEVEL_MARGIN:"),
]


# prerequisite_graph mutations -- old strings matched to current prerequisite_graph.py text.
PREREQUISITE_GRAPH_MUTATIONS = [
    # drop the crafting-skill prerequisite edge: a craftable item no longer gates
    # on ReachSkillLevel(crafting_skill) (wrong edge set, skill edge missing).
    ("prerequisite_graph: drop crafting-skill prereq edge",
     "                prereqs.append(ReachSkillLevel(stats.crafting_skill, stats.crafting_level))",
     "                pass"),
    # drop the ingredient edges: a craftable item produces no ObtainItem(mat)
    # edges (wrong edge set, material edges missing).
    ("prerequisite_graph: drop ingredient ObtainItem edges",
     "            prereqs.extend(ObtainItem(mat, qty) for mat, qty in recipe.items())",
     "            prereqs.extend([])"),
    # drop the resource-skill prereq edge: a resource-drop item becomes a leaf
    # instead of gating on its gather skill (wrong edge set on the resource branch).
    ("prerequisite_graph: drop resource-skill prereq edge",
     "                    return [ReachSkillLevel(skill_level[0], skill_level[1])]",
     "                    return []"),
    # combat_capable any -> all: requires EVERY monster beatable rather than SOME
    # (the anti-gaming aggregation flip the De Morgan contract catches).
    ("prerequisite_graph: combat_capable any -> all",
     "    return any(predict_win(state, game_data, code) for code in game_data.monster_levels)",
     "    return all(predict_win(state, game_data, code) for code in game_data.monster_levels)"),
]


# objective mutations -- old strings matched to current objective.py text.
OBJECTIVE_MUTATIONS = [
    # drop the attainability filter in gear selection: a non-attainable (higher
    # equip_value) item can be wrongly chosen for the slot.
    ("objective: drop attainability filter in gear selection",
     "            attainable = [(value, code) for (value, code) in ranked\n"
     "                          if is_attainable(code, game_data)]",
     "            attainable = [(value, code) for (value, code) in ranked]"),
    # char_level_gap sign flip: state.level - target instead of target - level
    # (negates the deficit; max(0, ...) then masks real gaps as 0).
    ("objective: char_level_gap sign flip (target-level -> level-target)",
     "        char_level_gap = max(0, self.target_char_level - state.level)",
     "        char_level_gap = max(0, state.level - self.target_char_level)"),
    # drop the monster-drop leaf branch: reverts is_attainable to the old
    # gathering-ONLY bug that silently dropped body/leg/amulet from target_gear.
    # A craft chain bottoming out in a (spawning) monster drop is wrongly
    # rejected -> killed by test_attainable_spawning_monster_drop_accepted.
    # Updated (C4): leaf_ok now calls leaf_attainable_pure; the mutation targets
    # the _drops_from_spawning_monster argument directly.
    ("objective: drop monster-drop leaf branch (gathering-only regression)",
     "            _drops_from_spawning_monster(leaf, game_data),\n"
     "            game_data.is_task_earnable(leaf),",
     "            False,\n"
     "            game_data.is_task_earnable(leaf),"),
    # drop the known-spawn gate: accept ANY monster drop even from a monster the
    # bot can never reach. Killed by test_attainable_spawnless_monster_drop_rejected
    # and the random graph (spawn-less droppers must not ground their item).
    ("objective: drop known-spawn gate in monster-drop leaf",
     "    return any(game_data.monster_locations(monster_code)\n"
     "               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))",
     "    return any(True\n"
     "               for monster_code, _rate, _mn, _mx in game_data.monsters_dropping(code))"),
    # drop the entire NPC purchase edge in the perfect-sheet leaf: reverts task
    # #12, so an NPC-only item (rune/artifact/bag) is wrongly unattainable.
    # Killed by the gold-purchase + item-currency differential tests.
    # Updated (C4): leaf_ok now computes `buyable` as a local variable; the
    # mutation collapses it to False (equivalent to dropping the whole buy edge).
    ("objective: drop NPC purchase edge in is_attainable leaf",
     "        buyable = leaf not in path and any(\n"
     "            currency == GOLD\n"
     "            or _attainable_closure(currency, game_data, leaf_ok, path | {leaf})\n"
     "            for _price, currency in _permanent_vendor_purchases(leaf, game_data))",
     "        buyable = False"),
    # drop the gold-currency acceptance: a gold purchase must recurse on the
    # literal 'gold' (which grounds in nothing) and wrongly fails. Killed by the
    # gold-purchase differential test.
    # Updated (C4): the `currency == GOLD` check is now inside the `any(...)` for
    # `buyable`; drop just the gold branch, keeping the recursive currency path.
    ("objective: drop gold-currency acceptance in buy edge",
     "        buyable = leaf not in path and any(\n"
     "            currency == GOLD\n"
     "            or _attainable_closure(currency, game_data, leaf_ok, path | {leaf})\n"
     "            for _price, currency in _permanent_vendor_purchases(leaf, game_data))",
     "        buyable = leaf not in path and any(\n"
     "            _attainable_closure(currency, game_data, leaf_ok, path | {leaf})\n"
     "            for _price, currency in _permanent_vendor_purchases(leaf, game_data))"),
    # drop the permanent/reachable vendor gate: event and unlocated vendors are
    # wrongly counted. Killed by test_attainable_event_vendor_excluded_matches_lean
    # (and the random graph's non-permanent edges).
    ("objective: drop permanent-vendor gate",
     "            if not game_data.is_event_npc(npc) and game_data.npc_location(npc) is not None]",
     "            ]"),
    # NOTE: the historical `is_complete` weakening mutation (and -> or) MOVED to
    # `objective_completion.py` after the pure-core extraction (the property
    # `ObjectiveGap.is_complete` now delegates to `is_complete_pure`). The
    # equivalent mutation lives in WEIGHTED_REMAINING_MUTATIONS
    # ("is_complete == flipped to !="), killed by test_weighted_remaining_diff.py.
]


# strategy_traversal mutations -- old strings matched to current strategy.py text.
STRATEGY_MUTATIONS = [
    # cycle-guard flip in is_reachable: a node on the current path becomes wrongly
    # "reachable" (return True) instead of being rejected — cyclic chains read as
    # bottoming out (the anti-gaming cycle guard the grounding-fixpoint proof pins).
    ("strategy: is_reachable cycle-guard flip (return False -> True)",
     "    if root in path:\n        return False",
     "    if root in path:\n        return True"),
    # closure off-by-one: inflate the unmet-closure count by 1 (wrong root_cost /
    # ranking; the min-1 floor would mask only the empty case).
    ("strategy: unmet_closure_size off-by-one (max(count, 1) -> max(count + 1, 1))",
     "    return max(count, 1)",
     "    return max(count + 1, 1)"),
    # actionable predicate weakening: drop the producible check, so a NON-producible
    # obtain leaf is wrongly returned as the actionable step (a node with no real
    # action). The actionable-correctness contract (obtain ⇒ producible) catches it.
    ("strategy: actionable_step drop producible check",
     "            if isinstance(node, ObtainItem) and not _producible(node.code, state, game_data):\n"
     "                return None\n"
     "            return node",
     "            return node"),
    # closure descends SATISFIED interior nodes too (drop the satisfied-interior
    # pruning): count would include satisfied nodes / descend their prereqs — the
    # historical TLA+-era gap. Push prereqs unconditionally and count regardless.
    ("strategy: unmet_closure_size drop satisfied-interior pruning",
     "        if not node.is_satisfied(state, game_data):\n"
     "            count += 1\n"
     "            stack.extend(prerequisites(node, state, game_data))",
     "        count += 1\n"
     "        stack.extend(prerequisites(node, state, game_data))"),
]


# reachability-invariant mutations: both is_reachable AND actionable_step now use
# per-DFS-path frozenset cycle-tracking (Phase 13 refactor — Python byte-equivalent
# to the proved Lean `actStep`). Each mutation breaks
# `is_reachable ⇒ actionable_step ≠ None` or the oracle agreement and is caught by
# test_reachability_diff.py.
REACHABILITY_MUTATIONS = [
    # flip actionable_step's cycle-guard membership test: a FRESH node is wrongly
    # treated as already-on-path (returns None) — actionable nodes get dropped, so
    # a reachable root yields no step (the production-assert crash) and the oracle
    # none/some agreement breaks.
    ("reachability: actionable_step cycle-guard membership flip (in -> not in)",
     "        if node in path:\n            return None",
     "        if node not in path:\n            return None"),
    # drop actionable_step's per-path extension: on a cyclic graph the DFS no longer
    # extends the path, so the cycle guard never fires and the DFS recurses
    # forever (RecursionError) — the cyclic test graphs catch it.
    ("reachability: actionable_step drop sub_path extension (no cycle termination)",
     "        sub_path = path | {node}\n"
     "        for prereq in sorted(unmet, key=repr):\n"
     "            step = _step(prereq, sub_path)",
     "        for prereq in sorted(unmet, key=repr):\n"
     "            step = _step(prereq, path)"),
    # is_reachable bottoms out a cyclic node as reachable: drop the per-path cycle
    # guard so a node on its own path reads reachable. Then is_reachable=True on a
    # cycle while actionable_step (still guarded) returns None — the EXACT divergence
    # the invariant forbids; test_reachability_diff's well-formed invariant fires.
    ("reachability: is_reachable drop path cycle guard (cyclic node reads reachable)",
     "    if root in path:\n        return False\n",
     ""),
]
# Phase 13 note: a "revert to shared-`visited`" mutant on `actionable_step` was
# considered (re-introducing the pre-refactor mutable-set shape). The shared and
# per-path trackers are OBSERVATIONALLY EQUIVALENT on the Some/None verdict for
# every graph generated by the diff test's hypothesis stratum AND for the entire
# 200k brute force — the refactor is a clarity / proof-bridge change, not a
# behavioral one. The three reachability mutants above pin the load-bearing
# invariants of the per-path tracker; an unkillable mutant would be proof-theater
# and was not added.


# bank_selection mutations -- old strings matched to current bank_selection.py text.
BANK_SELECTION_MUTATIONS = [
    # drop task-input protection: no longer protect the items-task item's recipe
    # materials, so banking the task's own inputs becomes possible (the freeze bug).
    ("bank_selection: drop items-task recipe-material protection",
     '    if state.task_type == "items" and state.task_code:\n'
     "        recipe_roots.append(state.task_code)",
     '    if state.task_type == "items" and state.task_code:\n'
     "        pass"),
    # drop HP-consumable protection: HP-restore items become depositable (wrong keep).
    ("bank_selection: drop HP-restore protection",
     "        if stats is not None and stats.hp_restore > 0:\n"
     "            keep.add(code)",
     "        if stats is not None and stats.hp_restore > 0:\n"
     "            pass"),
    # drop best-fighting-weapon protection: the combat weapon becomes depositable.
    ("bank_selection: drop best-weapon protection",
     "    weapon = _best_fighting_weapon(state, game_data)\n"
     "    if weapon is not None:\n"
     "        keep.add(weapon)",
     "    weapon = _best_fighting_weapon(state, game_data)\n"
     "    if weapon is not None:\n"
     "        pass"),
    # wrong deposit filter: deposit kept items too (drop the `not in keep` guard),
    # so protected items get banked — the freeze invariant the proof pins.
    ("bank_selection: deposit filter includes kept items",
     "        if qty > 0 and code not in keep",
     "        if qty > 0"),
    # weapon tie/argmax flip: prefer LOWER attack (> becomes <), wrong best weapon.
    ("bank_selection: best-weapon argmax flip (attack > -> <)",
     "        if best is None or attack > best[0] or (attack == best[0] and code < best[1]):",
     "        if best is None or attack < best[0] or (attack == best[0] and code < best[1]):"),
]


# stuck_detector mutations -- old strings matched to current recovery.py text.
STUCK_DETECTOR_MUTATIONS = [
    # detect precedence swap: check NO_PROGRESS before STATE_FROZEN, so a window
    # that is simultaneously frozen AND noprog reports noprog (wrong precedence).
    ("stuck_detector: detect precedence swap (noprog before frozen)",
     "        if self._check_state_frozen():\n"
     "            return StuckSignal.STATE_FROZEN\n"
     "        if self._check_goal_oscillation():\n"
     "            return StuckSignal.GOAL_OSCILLATION\n"
     "        if self._check_no_progress():\n"
     "            return StuckSignal.NO_PROGRESS",
     "        if self._check_no_progress():\n"
     "            return StuckSignal.NO_PROGRESS\n"
     "        if self._check_state_frozen():\n"
     "            return StuckSignal.STATE_FROZEN\n"
     "        if self._check_goal_oscillation():\n"
     "            return StuckSignal.GOAL_OSCILLATION"),
    # threshold off-by-one: frozen window requires len < 10 -> len < 9, so a 9-record
    # window wrongly satisfies the length gate (fires one record early).
    ("stuck_detector: frozen threshold off-by-one (count=10 -> 9)",
     "        window = self._recent_since(cutoff, count=STATE_FROZEN_WINDOW)\n"
     "        if len(window) < STATE_FROZEN_WINDOW:",
     "        window = self._recent_since(cutoff, count=STATE_FROZEN_WINDOW - 1)\n"
     "        if len(window) < STATE_FROZEN_WINDOW - 1:"),
    # drop the round-trip requirement: the switch gate goes vacuous, so a single
    # clean goal switch (7xA+1xB, the 2026-06-10 false-positive trace) wrongly
    # fires osc again whenever the failure gate also passes.
    ("stuck_detector: osc drop round-trip requirement (switches < min -> < 0)",
     "        if switches < OSC_MIN_SWITCHES:\n"
     "            return False",
     "        if switches < 0:\n"
     "            return False"),
    # drop the failure requirement: productive alternation (e.g. gather/deposit
    # loops, or a failure-free A/B flap) wrongly fires osc again.
    ("stuck_detector: osc drop failure requirement (failures >= min -> >= 0)",
     "        failures = sum(1 for r in window if not r.succeeded)\n"
     "        return failures >= OSC_MIN_FAILURES",
     "        failures = sum(1 for r in window if not r.succeeded)\n"
     "        return failures >= 0"),
    # _recent_since index off-by-one: start_idx + i becomes start_idx + i + 1, so a
    # boundary record at exactly the cutoff is wrongly excluded (the window-boundary
    # case lands the kept length on 10/4/8, so this flips the verdict). Pins the math.
    ("stuck_detector: _recent_since index off-by-one (start_idx + i -> + i + 1)",
     "            if start_idx + i >= cutoff_cycle",
     "            if start_idx + i + 1 >= cutoff_cycle"),
    # _recent_since index off-by-one the OTHER way: start_idx + i - 1, wrongly
    # INCLUDES an at-cutoff record (over-counts the window on the boundary).
    ("stuck_detector: _recent_since index off-by-one (start_idx + i -> + i - 1)",
     "            if start_idx + i >= cutoff_cycle",
     "            if start_idx + i - 1 >= cutoff_cycle"),
    # REPEATED_ACTION_FAILURE threshold off-by-one: >= K -> >= K-1, so a 9-failure
    # window (one below threshold) wrongly fires (kills via the one-short test).
    ("stuck_detector: repeated threshold off-by-one (>= K -> >= K-1)",
     "        return any(c >= REPEATED_ACTION_FAILURE_THRESHOLD for c in counts.values())",
     "        return any(c >= REPEATED_ACTION_FAILURE_THRESHOLD - 1 for c in counts.values())"),
    # drop the <no_plan> exclusion: a no-plan flood (which NO_PROGRESS owns) is
    # also counted as a repeated action (kills via the no_plan-flood test).
    ("stuck_detector: repeated drop no_plan guard",
     '            if not rec.succeeded and rec.action_name != "<no_plan>":\n'
     "                counts[rec.action_name] = counts.get(rec.action_name, 0) + 1",
     "            if not rec.succeeded:\n"
     "                counts[rec.action_name] = counts.get(rec.action_name, 0) + 1"),
    # flip the failure sense: count SUCCESSES instead of failures, so a wedged
    # all-failing action reports 0 and never fires (kills via the flip-sense test).
    ("stuck_detector: repeated flip failure sense (not succeeded -> succeeded)",
     '            if not rec.succeeded and rec.action_name != "<no_plan>":\n'
     "                counts[rec.action_name] = counts.get(rec.action_name, 0) + 1",
     '            if rec.succeeded and rec.action_name != "<no_plan>":\n'
     "                counts[rec.action_name] = counts.get(rec.action_name, 0) + 1"),
    # repeated window off-by-one: count=W -> W-1 drops the oldest record, so a
    # 10-failure window spanning exactly the last 20 falls to 9 (kills via the
    # window-boundary test).
    ("stuck_detector: repeated window off-by-one (count=W -> W-1)",
     "        window = self._recent_since(cutoff, count=REPEATED_ACTION_WINDOW)\n"
     "        counts: dict[str, int] = {}",
     "        window = self._recent_since(cutoff, count=REPEATED_ACTION_WINDOW - 1)\n"
     "        counts: dict[str, int] = {}"),
    # detect precedence: check REPEATED before NO_PROGRESS, so a window that is
    # simultaneously noprog AND repeated wrongly reports repeated (kills via the
    # noprog-beats-repeated test).
    ("stuck_detector: detect precedence swap (repeated before noprog)",
     "        if self._check_no_progress():\n"
     "            return StuckSignal.NO_PROGRESS\n"
     "        if self._check_repeated_action_failure():\n"
     "            return StuckSignal.REPEATED_ACTION_FAILURE",
     "        if self._check_repeated_action_failure():\n"
     "            return StuckSignal.REPEATED_ACTION_FAILURE\n"
     "        if self._check_no_progress():\n"
     "            return StuckSignal.NO_PROGRESS"),
]


# priority_band mutations -- old strings matched to current priority_band.py text.
PRIORITY_BAND_MUTATIONS = [
    # min/max swap: the clamp inverts, so the result can escape the band entirely
    # (a positive bonus would yield floor, a negative bonus would overshoot).
    ("priority_band: min/max swap",
     "    return min(ceiling, max(floor, floor + bonus))",
     "    return max(ceiling, min(floor, floor + bonus))"),
    # bonus sign flip: floor + bonus -> floor - bonus (wrong direction of the bonus).
    ("priority_band: bonus sign flip (floor + bonus -> floor - bonus)",
     "    return min(ceiling, max(floor, floor + bonus))",
     "    return min(ceiling, max(floor, floor - bonus))"),
    # drop the outer ceiling clamp: a large bonus can now exceed the ceiling (and
    # thus could reach the survival floor) — the survival-safety violation.
    ("priority_band: drop outer min ceiling clamp",
     "    return min(ceiling, max(floor, floor + bonus))",
     "    return max(floor, floor + bonus)"),
    # Byte-equivalence kill: coerce to float internally. Loses exactness on
    # fractional inputs whose denominators are not powers of two (e.g. 1/3) —
    # the differential test asserts the result is a Fraction equal bit-for-bit
    # to the Lean Rat oracle, so a float result either fails the type check or
    # disagrees bit-for-bit on at least one input.
    ("priority_band: float coercion (breaks byte-equivalence)",
     "    return min(ceiling, max(floor, floor + bonus))",
     "    return min(float(ceiling), max(float(floor), float(floor) + float(bonus)))"),
]


# owned_count mutations -- old strings matched to current owned_count.py text.
OWNED_COUNT_MUTATIONS = [
    # drop the bank branch entirely: bank contents no longer counted.
    ("owned_count: drop bank branch",
     "    if bank is not None:\n        total += bank.get(code, 0)",
     "    if bank is not None:\n        pass"),
    # equipped contributes +2 instead of +1: over-counts an equipped item.
    ("owned_count: equipped +1 -> +2",
     "    if code in equipped_codes:\n        total += 1",
     "    if code in equipped_codes:\n        total += 2"),
    # drop the equipped membership guard: ALWAYS add 1, even when not equipped.
    ("owned_count: drop `code in equipped_codes` guard (always +1)",
     "    if code in equipped_codes:\n        total += 1",
     "    if True:\n        total += 1"),
]


# upgrade_selection mutations -- old strings matched to current upgrade_selection.py text.
UPGRADE_SELECTION_MUTATIONS = [
    # best_by_value tie flip: >= -> >, so a TIE no longer prefers the (cheaper)
    # inventory pick and wrongly returns the craftable instead.
    ("upgrade_selection: best_by_value tie flip (>= -> >)",
     "    return inv if inv.value >= craft.value else craft",
     "    return inv if inv.value > craft.value else craft"),
    # craftable_key field swap: swap fills_empty and value, so the lexicographic
    # priority is wrong (value would outrank the empty-slot bonus).
    ("upgrade_selection: craftable_key swap fills_empty/value",
     "    return (int(c.relevant), int(c.fills_empty), c.value, -c.craft_level, c.item_code)",
     "    return (int(c.relevant), c.value, int(c.fills_empty), -c.craft_level, c.item_code)"),
    # craftable_key craft_level sign flip: -craft_level -> craft_level, so the
    # tiebreak prefers the HIGHER crafting level (breaks linear skill progression).
    ("upgrade_selection: craftable_key craft_level sign flip (-craft_level -> craft_level)",
     "    return (int(c.relevant), int(c.fills_empty), c.value, -c.craft_level, c.item_code)",
     "    return (int(c.relevant), int(c.fills_empty), c.value, c.craft_level, c.item_code)"),
    # best_by_key argmax flip: k > best_key -> k < best_key, so the WORST candidate
    # is selected instead of the best.
    ("upgrade_selection: best_by_key argmax flip (> -> <)",
     "        if best_key is None or k > best_key:",
     "        if best_key is None or k < best_key:"),
    # best_by_key tie-resolution flip: > -> >=, so a later equal-key candidate
    # DISPLACES the running best (last-wins instead of first-wins). Killed by the
    # same-code/equal-key tie cases in the diff test.
    ("upgrade_selection: best_by_key tie flip (> -> >=, first-wins -> last-wins)",
     "        if best_key is None or k > best_key:",
     "        if best_key is None or k >= best_key:"),
]


# scalar_core mutations -- old strings matched to current scalar_core.py text.
SCALAR_CORE_MUTATIONS = [
    # coins_spent sign flip: received - delta -> delta - received (the inversion
    # identity received - coins_spent == delta breaks).
    ("scalar_core: coins_spent sign flip (received - delta -> delta - received)",
     "    return received - delta_inv_used",
     "    return delta_inv_used - received"),
    # swap relevant/baseline weights: active skills now weighted 0.2 and inactive
    # 2.0, inverting the weight-dominance the scalar relies on (P3c: the
    # selection moved inline into the exact core's fold).
    ("scalar_core: swap relevant/baseline weight",
     "        skill_xp_component = skill_xp_component + delta * (\n"
     "            relevant_w if skill_name in active_skills else baseline_w)",
     "        skill_xp_component = skill_xp_component + delta * (\n"
     "            baseline_w if skill_name in active_skills else relevant_w)"),
    # gold sign flip: gold component subtracted instead of added (+gold -> -gold).
    ("scalar_core: gold component sign flip (+ -> -)",
     "    gold_component = gold / gold_per_xp",
     "    gold_component = -gold / gold_per_xp"),
    # coin component dropped: tasks_coins no longer contribute to the scalar.
    ("scalar_core: drop coin component (coin_value -> 0)",
     "    coin_component = tasks_coins * coin_value / gold_per_xp",
     "    coin_component = tasks_coins * 0 / gold_per_xp"),
    # Byte-equivalence kill: seed the skill-xp accumulator with float 0.0
    # instead of Fraction(0), contaminating the exact core into float
    # arithmetic. The diff test pins the EXACT Fraction identity against the
    # Lean Rat oracle (and asserts the result IS a Fraction), so any input
    # with a non-dyadic denominator (1/3, 1/5, ...) kills it.
    ("scalar_core: float-seed skill_xp_component (breaks the exact-Fraction core)",
     "    skill_xp_component = Fraction(0)\n"
     "    for skill_name, delta in skill_xp.items():",
     "    skill_xp_component = 0.0\n"
     "    for skill_name, delta in skill_xp.items():"),
]


# planner mutations -- old strings matched to the post-fix planner.py text.
# NOTE (affirmation context): planner.py now uses `h = 0.0` (Dijkstra), and the
# diff test pins the OPTIMAL plan ([Move, EatAtTile], cost 7). Each mutation
# here perturbs the search so the planner returns something other than the
# optimal plan (cost 7), so the affirmative test fails -> the mutant is killed.
PLANNER_MUTATIONS = [
    # Re-introduce the historical bug: per-node heuristic becomes `goal.value`
    # (urgency, inadmissible). With h huge at non-goal HP-50 states, the
    # Move-prefix node sinks to the back of the heap and [Rest] (cost 10) pops
    # before [Move, Eat] — the now-affirmative optimality test fails.
    ("planner: re-introduce urgency heuristic (h = 0.0 -> goal.value)",
     "                    # h ≡ 0 (Dijkstra): see h0 above.  `goal.value` remains used\n"
     "                    # by goal *selection* (StrategyArbiter, learning) — only the\n"
     "                    # planner's heuristic role is zeroed for provable optimality.\n"
     "                    h = 0.0",
     "                    h = goal.value(next_state, game_data, history)"),
    # Negate `g` in the priority: `f_score=g + h` -> `f_score=-g + h`. With h=0
    # this orders the heap by -g (largest g first), so deep / expensive plans
    # pop first and the planner returns something other than the cheap optimum.
    ("planner: negate g in f (g + h -> -g + h)",
     "                            f_score=g + h,",
     "                            f_score=-g + h,"),
    # Skip the `is_applicable` filter: useless / inapplicable actions get
    # expanded into the heap with no state change but accumulating cost,
    # corrupting g and the returned plan. The optimality assertion fails.
    ("planner: skip is_applicable filter (always expand)",
     "                    if not action.is_applicable(node.state, game_data):\n"
     "                        continue",
     "                    if False:\n"
     "                        continue"),
]


# arbiter_select mutations -- old strings matched to current arbiter_select.py text.
ARBITER_SELECT_MUTATIONS = [
    # drop the guard_precedes check: sticky-committed means survives a firing
    # plannable guard. This is the bug-likely safety-violation the proof pins.
    ("arbiter_select: drop guard_precedes check (sticky wins over guard)",
     "            if not guard_precedes:\n"
     "                plan = try_plan(committed_cand.goal)\n"
     "                tried_repr = committed_repr\n"
     "                if len(plan) > 0:\n"
     "                    return committed_cand.goal, plan, committed_repr",
     "            if True:\n"
     "                plan = try_plan(committed_cand.goal)\n"
     "                tried_repr = committed_repr\n"
     "                if len(plan) > 0:\n"
     "                    return committed_cand.goal, plan, committed_repr"),
    # sticky always wins: skip the walk entirely if committed is found. Even
    # when committed is not plannable, the function returns None instead of
    # falling through.
    ("arbiter_select: sticky always wins (return committed unconditionally)",
     "            if not guard_precedes:\n"
     "                plan = try_plan(committed_cand.goal)\n"
     "                tried_repr = committed_repr\n"
     "                if len(plan) > 0:\n"
     "                    return committed_cand.goal, plan, committed_repr",
     "            plan = try_plan(committed_cand.goal)\n"
     "            return committed_cand.goal, plan, committed_repr"),
    # reverse the precedes comparison: a_idx < b_idx -> a_idx > b_idx, so a
    # guard at index 0 no longer "precedes" a means at index ≥ 1. guard_precedes
    # becomes false when it should be true, and sticky can override a guard.
    ("arbiter_select: precedes comparison flip (< -> >)",
     "    return a_idx < b_idx",
     "    return a_idx > b_idx"),
    # walk's plannable check inverted: returns first NON-plannable goal,
    # corrupting the band-order first-plannable contract.
    ("arbiter_select: walk plannable check inverted (if plan -> if not plan)",
     "        plan = try_plan(cand.goal)\n        if len(plan) > 0:\n",
     "        plan = try_plan(cand.goal)\n        if len(plan) == 0:\n"),
    # drop the is_means commitment guard: a guard win wrongly sets new_committed
    # to the guard's repr (commitment should clear on guard wins).
    ("arbiter_select: commit on guard win (drop is_means guard)",
     "            new_committed = cand.repr_ if cand.is_means else None",
     "            new_committed = cand.repr_"),
]


# sticky_select_core mutations -- anchors for sticky_choose / next_last (Lean-proved
# StickySelect.stickyChoose / nextLast). The differential
# (test_sticky_select_diff.py) kills each.
STICKY_SELECT_MUTATIONS = [
    # sticky never wins: keep top even when it fails to dominate the sticky root.
    ("sticky_select: sticky never kept (return top instead of sticky)",
     "    if top.score <= ratio * sticky.score:\n        return sticky",
     "    if top.score <= ratio * sticky.score:\n        return top"),
    # dominance comparison flipped: <= -> >. Sticky kept exactly when it should lose.
    ("sticky_select: dominance comparison flip (<= -> >)",
     "    if top.score <= ratio * sticky.score:",
     "    if top.score > ratio * sticky.score:"),
    # drop the dominance ratio: threshold becomes sticky.score, so a top that should
    # be kept (ratio*sticky < top <= ... ) wrongly yields to sticky.
    ("sticky_select: drop dominance ratio",
     "    if top.score <= ratio * sticky.score:",
     "    if top.score <= sticky.score:"),
    # vanished-sticky fallback returns None instead of top -> bot stalls.
    ("sticky_select: vanished sticky returns None",
     "    if sticky is None:\n        return top",
     "    if sticky is None:\n        return None"),
    # progress gate dropped: feed the anchor back even without progress (the zombie).
    ("sticky_select: next_last ignores progressed (always feeds anchor)",
     "    return chosen_repr if progressed else None",
     "    return chosen_repr"),
]


# servable_filter mutations -- anchors for keep_servable (Lean-proved
# ServableFilter.keepServable). The differential (test_servable_filter_diff.py) kills each.
SERVABLE_FILTER_MUTATIONS = [
    # never filter: keep all items even when some are servable.
    ("servable_filter: never drops unservable (return all)",
     "    kept = [it for it, ok in zip(items, servable, strict=True) if ok]\n"
     "    return kept if kept else list(items)",
     "    kept = [it for it, ok in zip(items, servable, strict=True) if ok]\n"
     "    return list(items)"),
    # invert servable test: keep the UNservable ones.
    ("servable_filter: servable test inverted (if ok -> if not ok)",
     "    kept = [it for it, ok in zip(items, servable, strict=True) if ok]",
     "    kept = [it for it, ok in zip(items, servable, strict=True) if not ok]"),
    # drop the graceful fallback: return empty when nothing is servable (strands the bot).
    ("servable_filter: drop graceful fallback (return kept, may be empty)",
     "    return kept if kept else list(items)",
     "    return kept"),
]


# task_decision_core mutations -- old strings matched to actual task_decision_core.py text.
TASK_DECISION_MUTATIONS = [
    # Flip the comparator: `>=` → `>`. At equality (vpc == required) decision flips
    # PURSUE → PIVOT. The boundary test (vpc=20, conf=0, threshold=20) catches it.
    ("task_decision: >= -> > (boundary flip)",
     "    return PURSUE if skill_up_vpc >= required_vpc(\n"
     "        baseline_vpc, confidence_margin, confidence) else PIVOT",
     "    return PURSUE if skill_up_vpc > required_vpc(\n"
     "        baseline_vpc, confidence_margin, confidence) else PIVOT"),
    # Reverse the confidence direction inside required_vpc: `(1 - confidence)` → `confidence`.
    # At confidence=0 threshold drops to baseline (=5) instead of 4*baseline (=20);
    # at confidence=1 threshold becomes 4*baseline (=20) instead of baseline (=5).
    # The confidence-boundary tests catch both flips.
    ("task_decision: (1 - confidence) -> confidence (reverse antitone)",
     "    return baseline_vpc * (1.0 + confidence_margin * (1.0 - confidence))",
     "    return baseline_vpc * (1.0 + confidence_margin * confidence)"),
    # Drop the combat / no-history short-circuit entirely.
    ("task_decision: drop PIVOT short-circuit (combat / no-history)",
     "    if req_is_combat or not history_present:\n"
     "        return PIVOT\n"
     "    return PURSUE if skill_up_vpc >= required_vpc(",
     "    return PURSUE if skill_up_vpc >= required_vpc("),
    # Drop the req_is_none short-circuit (return PIVOT for already-feasible tasks).
    ("task_decision: drop req_is_none -> PURSUE short-circuit",
     "    if req_is_none:\n        return PURSUE\n",
     ""),
]


# objective_completion mutations -- old strings matched to current objective_completion.py text.
WEIGHTED_REMAINING_MUTATIONS = [
    # Drop the third weight*fraction summand: the gear-category contribution
    # is silently zeroed, so any partial gear gap is invisible to the scalar.
    # The exact-rational diff with positive weights catches the missing term;
    # the bug-teeth diff also catches it (the zeroed third category mimics
    # the latent zero-weight defect in a way the equivalence forbids).
    ("objective_completion: drop third weight*fraction summand",
     "    return (weights[0] * fractions[0]\n"
     "            + weights[1] * fractions[1]\n"
     "            + weights[2] * fractions[2])",
     "    return (weights[0] * fractions[0]\n"
     "            + weights[1] * fractions[1])"),
    # is_complete `==` flipped to `!=`: an all-zero objective wrongly reports
    # INCOMPLETE (and vice versa). The positive-equivalence diff catches it
    # via the is_complete agreement check at a complete triple.
    ("objective_completion: is_complete == flipped to !=",
     "    return (fractions[0] == 0.0\n"
     "            and fractions[1] == 0.0\n"
     "            and fractions[2] == 0.0)",
     "    return (fractions[0] != 0.0\n"
     "            and fractions[1] != 0.0\n"
     "            and fractions[2] != 0.0)"),
    # weighted_remaining substitutes `max` for the sum: the scalar becomes the
    # largest weight*fraction term, not the sum. Three weight*fraction terms
    # produce different totals between sum and max whenever ≥ 2 are nonzero,
    # which the diff exercises broadly.
    ("objective_completion: weighted_remaining sum -> max",
     "    return (weights[0] * fractions[0]\n"
     "            + weights[1] * fractions[1]\n"
     "            + weights[2] * fractions[2])",
     "    return max(weights[0] * fractions[0],\n"
     "               weights[1] * fractions[1],\n"
     "               weights[2] * fractions[2])"),
]


# low_yield_boundary mutations -- old strings matched to current low_yield_boundary.py text.
LOW_YIELD_MUTATIONS = [
    # Flip the confidence comparator `<` → `<=`. At the exact 0.5 boundary the
    # rule should fire (gate is `>=`); flipping to `<=` makes 0.5 reject.
    # The `test_confidence_boundary_at` test pins this.
    ("low_yield: confidence < -> <= (boundary flip)",
     "    if confidence < min_confidence:\n        return False",
     "    if confidence <= min_confidence:\n        return False"),
    # Flip the margin comparator `>=` → `>`. At the exact margin boundary
    # (`alt = current * margin`) the rule should fire; flipping to `>` makes
    # it reject. The `test_margin_boundary_at` test (alt=3 == 2*1.5) catches
    # this — strict `>` would reject equality.
    ("low_yield: alt >= current*margin -> > (boundary flip)",
     "    return alt_xp >= current_xp * margin",
     "    return alt_xp > current_xp * margin"),
    # Drop the zero-fast-path entirely. Then the Robby gudgeon scenario (and
    # the `test_zero_fast_path_witness`, `test_zero_fast_path_fires_when_alt_positive`)
    # would no longer fire because confidence=0 < 0.5 gate blocks.
    ("low_yield: drop zero-fast-path",
     "    # Zero-char-XP fast-path: any positive alternative dominates.\n"
     "    if current_xp == 0 and alt_xp > 0:\n"
     "        return True\n",
     ""),
]


# strategy_blend mutations -- old strings matched to current strategy_blend.py text.
STRATEGY_BLEND_MUTATIONS = [
    # flip the slope sign: + BALANCE_K -> - BALANCE_K. The monotonicity in
    # (leader - current) breaks; at gap = 4 the python is < 1 and the lean is
    # > 1 — the diff fires for any gap ≠ 2.
    ("strategy_blend: balancing slope sign flip (+ K -> - K)",
     "    raw = 1 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)",
     "    raw = 1 - BALANCE_K * (leader - current - BALANCE_THRESHOLD)"),
    # drop the lower band clamp: max(BALANCE_MIN, ...) -> the inner min only.
    # A skill far ahead of the leader now produces a multiplier below 0.5 (and
    # possibly negative). The proved lower bound + threshold tests both fire.
    ("strategy_blend: drop lower band clamp (max -> bare inner min)",
     "    return max(BALANCE_MIN, min(BALANCE_MAX, raw))",
     "    return min(BALANCE_MAX, raw)"),
    # swap BALANCE_K 1/4 -> 1: multiplier amplification per gap-unit is 4x
    # too strong; clamp kicks in much sooner (essentially everywhere) and the
    # threshold identity (gap=2 ⇒ 1.0) is preserved BUT the gap=4 → 1.5 test
    # and the hypothesis-driven mid-band values fail. (P4a re-anchor: the
    # constant is an exact Fraction now; same semantic intent as 0.25 -> 1.0.)
    ("strategy_blend: BALANCE_K 1/4 -> 1",
     "BALANCE_K = Fraction(1, 4)",
     "BALANCE_K = Fraction(1)"),
    # P4a byte-equivalence kill: contaminate the exact-Fraction core with a
    # float literal seed (1 -> 1.0). `1.0 + Fraction` is a float, so mid-band
    # (unclamped) results stop being Fractions — the diff test asserts the
    # production result IS a Fraction equal bit-for-bit to the Lean Rat.
    ("strategy_blend: float-seed balancing (breaks the exact-Fraction core)",
     "    raw = 1 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)",
     "    raw = 1.0 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)"),
    # learned_blend: flip (1 - w) to w. Now blend = w*value + w*normalized,
    # destroying the convex combination. The convex-bound / warm-up tests fire.
    ("strategy_blend: learned_blend (1 - w) -> w (drop the complement)",
     "    return (1 - w) * value + w * normalized",
     "    return w * value + w * normalized"),
    # learned_blend: + -> - between the two terms (subtract normalized rather
    # than blend toward it). The convex bound + monotonicity tests fire.
    ("strategy_blend: learned_blend + -> - between terms",
     "    return (1 - w) * value + w * normalized",
     "    return (1 - w) * value - w * normalized"),
    # learned_blend: drop the w cap on `normalized` (multiply by w*2): the
    # blend can exceed `max(value, normalized)` — the anti-Phase-1 unbounded
    # bonus property breaks. The convex-bound assertion fires.
    ("strategy_blend: learned_blend doubles the normalized contribution",
     "    return (1 - w) * value + w * normalized",
     "    return (1 - w) * value + 2 * w * normalized"),
]


# decide_key mutations -- old strings matched to current decide_key.py text.
DECIDE_KEY_MUTATIONS = [
    # swap negFinal and effort in the tuple: the lex order flips priority;
    # for any inputs with distinct effort the comparator returns a different
    # ordering vs the Lean oracle (which sorts by negFinal first). The
    # Hypothesis driver finds a counterexample quickly.
    ("decide_key: swap negFinal/effort in the sort tuple",
     "    return (neg_final, effort, neg_protection, root_repr)",
     "    return (effort, neg_final, neg_protection, root_repr)"),
    # drop the protection tiebreak: two same-(negFinal, effort) empty-slot gear
    # keys with different computed equip value now collapse to a CONSTANT third
    # field, violating the proved `eq_imp_negProtect` lemma at the tuple level.
    # `test_decide_key_protection_tiebreak_matches_lean` fires: with negProtect
    # constant, the body-armor key no longer sorts ahead of the amulet (the repr
    # tiebreak then favours 'air...' < 'feather...').
    ("decide_key: drop protection tiebreak (constant third field)",
     "    return (neg_final, effort, neg_protection, root_repr)",
     "    return (neg_final, effort, 0, root_repr)"),
    # drop the rootRepr tiebreak: RETURN the fourth field as a CONSTANT, which
    # violates the proved `eq_imp_repr` lemma at the tuple level. The test fires
    # when two distinct reprs collide on equal leading fields.
    ("decide_key: drop rootRepr tiebreak (constant fourth field)",
     "    return (neg_final, effort, neg_protection, root_repr)",
     '    return (neg_final, effort, neg_protection, "")'),
    # GuardKind dispatch: drop one variant entirely (KeyError at runtime, but
    # the parametrized exhaustiveness test fires immediately). We swap one
    # mapping to wrong text so the diff-against-Lean fires.
    ("decide_key: HP_CRITICAL repr corrupted",
     "    GuardKind.HP_CRITICAL: \"RestoreHP\",",
     "    GuardKind.HP_CRITICAL: \"WRONG\","),
    # MeansKind dispatch: similar — corrupt the PURSUE_TASK mapping.
    ("decide_key: PURSUE_TASK repr corrupted",
     "    MeansKind.PURSUE_TASK: \"PursueTask\",",
     "    MeansKind.PURSUE_TASK: \"WRONG\","),
    # PLAN #6a: the MAINTAIN_CONSUMABLES repr must match the Lean mirror.
    ("decide_key: MAINTAIN_CONSUMABLES repr corrupted",
     "    MeansKind.MAINTAIN_CONSUMABLES: \"MaintainConsumables\",",
     "    MeansKind.MAINTAIN_CONSUMABLES: \"WRONG\","),
]


# progression_reserve_core mutations -- each breaks the deduction-accounting
# floor so the Python decision diverges from the proved Lean oracle. Killed by
# formal/diff/test_progression_reserve_diff.py.
PROGRESSION_RESERVE_MUTATIONS = [
    # Drop the deduction: a reserved item's own cost no longer credited, so its
    # purchase is wrongly blocked by its own reservation.
    ("progression_reserve: drop deduction (floor = full total)",
     "    return reserve_total(reserved) - reserved.get(buying or \"\", 0)",
     "    return reserve_total(reserved)"),
    # Flip the affordability comparison: spends below the floor.
    ("progression_reserve: invert affordability (>= -> <)",
     "    return gold >= price + effective_floor(reserved, buying)",
     "    return gold < price + effective_floor(reserved, buying)"),
    # Ignore price in affordability -> overspends by the item's price.
    ("progression_reserve: drop price from affordability",
     "    return gold >= price + effective_floor(reserved, buying)",
     "    return gold >= effective_floor(reserved, buying)"),
]


# bank_expansion mutations (REAL BUG #15: BuyBankExpansionAction.apply must
# project +BANK_EXPANSION_SLOTS into state.bank_capacity, otherwise the
# planner cannot ever reach ExpandBankGoal.is_satisfied).
BANK_EXPANSION_MUTATIONS = [
    # Mutation 1: REVERT to pre-fix (drop the bank_capacity update). This
    # restores the BLOCKED projection gap.
    ("bank_expansion: drop the capacity update entirely (pre-fix revert)",
     "        return dataclasses.replace(\n"
     "            state,\n"
     "            gold=state.gold - game_data.next_expansion_cost,\n"
     "            x=dest[0],\n"
     "            y=dest[1],\n"
     "            cooldown_expires=None,\n"
     "            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,\n"
     "        )",
     "        return dataclasses.replace(\n"
     "            state,\n"
     "            gold=state.gold - game_data.next_expansion_cost,\n"
     "            x=dest[0],\n"
     "            y=dest[1],\n"
     "            cooldown_expires=None,\n"
     "        )"),
    # Mutation 2: off-by-one on the expansion size (wrong slot count).
    ("bank_expansion: BANK_EXPANSION_SLOTS off-by-one (20 → 19)",
     "BANK_EXPANSION_SLOTS = 20",
     "BANK_EXPANSION_SLOTS = 19"),
]

# expand_bank goal mutations (REAL BUG #15 sibling: reverting the goal to read
# game_data instead of state.bank_capacity defeats the projection).
EXPAND_BANK_GOAL_MUTATIONS = [
    ("expand_bank: is_satisfied reverts to reading game_data._bank_capacity only",
     "        if state.bank_capacity is not None:\n"
     "            capacity = state.bank_capacity\n"
     "        elif self._game_data is not None:\n"
     "            capacity = self._game_data.bank_capacity\n"
     "        else:\n"
     "            capacity = 0",
     "        capacity = self._game_data.bank_capacity if self._game_data is not None else 0"),
]


# winnable_cascade mutations (Phase 11 Target A: 3-tier combat-target
# precedence cascade extracted from Player._winnable_farm_target). The
# differential test must kill every reordering of the tiers.
WINNABLE_CASCADE_MUTATIONS = [
    # Mutation 1: ignore task_monster (drop tier 1 entirely).
    ("winnable_cascade: skip task tier (drop early-return)",
     "    if inputs.task_monster is not None:\n        return inputs.task_monster\n",
     ""),
    # Mutation 2: invert the winnable check on the path tier so a NON-winnable
    # path monster gets returned (the load-bearing safety violation).
    ("winnable_cascade: invert path winnable check",
     "    if inputs.path_monster is not None and inputs.path_winnable:\n        return inputs.path_monster\n",
     "    if inputs.path_monster is not None and not inputs.path_winnable:\n        return inputs.path_monster\n"),
    # Mutation 3: swap tier 2 and tier 3 — return pick_winnable first,
    # demoting the path projection. Violates the documented precedence.
    ("winnable_cascade: swap path and pick tiers",
     "    if inputs.path_monster is not None and inputs.path_winnable:\n        return inputs.path_monster\n    return inputs.pick_winnable\n",
     "    if inputs.pick_winnable is not None:\n        return inputs.pick_winnable\n    if inputs.path_monster is not None and inputs.path_winnable:\n        return inputs.path_monster\n    return None\n"),
]


# combat_picker mutations (P0 2026-06-09: window-preferred picker with the
# xp>0 liveness fallback, extracted from Player._pick_winnable_monster).
# The differential test must kill every weakening of the fallback tier.
COMBAT_PICKER_MUTATIONS = [
    # Mutation 1: drop the liveness fallback entirely — revert to the
    # window-only picker (re-introduces the P0 no-combat deadlock).
    ("combat_picker: drop liveness fallback (window-only picker)",
     "    if best is not None:\n"
     "        return best[0]\n"
     "    for code, level in monsters:\n",
     "    if best is not None:\n"
     "        return best[0]\n"
     "    for code, level in ():\n"),
    # Mutation 2: invert the xp>0 gate — the fallback targets ONLY zero-xp
    # monsters (no leveling value) and skips xp-positive ones.
    ("combat_picker: invert xp_positive gate in fallback",
     "        if level > max_level or not xp_positive(code) or not is_winnable(code):\n",
     "        if level > max_level or xp_positive(code) or not is_winnable(code):\n"),
    # Mutation 3: drop the suicide-guard upper bound from the fallback — an
    # overleveled winnable monster gets picked, which FightAction's level+2
    # bound would reject (dead-target → empty-plan cascade).
    ("combat_picker: drop suicide guard from fallback",
     "        if level > max_level or not xp_positive(code) or not is_winnable(code):\n",
     "        if not xp_positive(code) or not is_winnable(code):\n"),
]


# task_reservation mutations (P0 2026-06-09: items-task material reservation —
# the predicate deferring a step-tier goal whose craft would eat the task's
# pooled materials). The differential test must kill every weakening.
TASK_RESERVATION_MUTATIONS = [
    # Mutation 1: flip <= to < on the surplus boundary — owned == demand would
    # count as surplus and the step eats the exact remaining task need.
    # (P3a re-anchor: the comparison lives in the pure core, reading the demand
    # through dict.get — values are >= 1 on present keys, so get == subscript.)
    ("task_reservation: surplus boundary <= becomes <",
     "        if 0 < owned <= demand.get(item, 0):\n",
     "        if 0 < owned < demand.get(item, 0):\n"),
    # Mutation 2: drop the remaining-multiplication — demand = closure x 1, so
    # any pooled stock above ONE unit reads as surplus and gets eaten.
    ("task_reservation: demand = closure x 1 (drop remaining scaling)",
     "    demand = _closure_demand(len(recipes) + 1, task_code, remaining, recipes,\n",
     "    demand = _closure_demand(len(recipes) + 1, task_code, 1, recipes,\n"),
    # Mutation 3: ignore the items-task gate — monster/skill tasks would
    # reserve materials they never consume, starving the gear chain.
    ("task_reservation: ignore task_type gate",
     "    if task_type != \"items\" or task_code == \"\":\n",
     "    if task_code == \"\":\n"),
]


# --- per-mutant test runner ------------------------------------------------
# "parallel" (default) fans mutants across worker threads, each owning a PRIVATE
# copy of src/artifactsmmo_cli. A worker mutates only its copy and runs the
# kill-test with PYTHONPATH pointed at that copy (the editable install is a
# plain-path .pth, so a prepended PYTHONPATH shadows it). The production tree is
# NEVER mutated in parallel mode — strictly safer than serial, and ~Nx faster
# since the cost is the Hypothesis test body, which is CPU-bound and embarrassingly
# parallel. "serial" is the original in-place `uv run pytest` per mutant against
# the real tree — slower, fully isolated, and the parity oracle for "parallel".
_RUNNER = "parallel"
# Worker count for parallel mode. Capped at 16; leaves headroom on the box.
_WORKERS = min(16, (os.cpu_count() or 2) - 2)
# Group filter: a group runs only when one of these substrings appears in its
# src path or test path. None = run every group (the gate's full sweep).
_ONLY: list[str] | None = None
_SRC_PKG = "artifactsmmo_cli"
_SRC_ROOT = ROOT / "src"
_PYTEST_ARGS = ["-q", "--no-cov", "-x"]

# One mutation unit: (target src file, description, old text, new text, test path).
_Unit = tuple[Path, str, str, str, str]
# Collected units, populated by run_group and drained by the executor. Module-
# global so the ~80 run_group call sites need no signature change.
_UNITS: list[_Unit] = []
_PRINT_LOCK = threading.Lock()


def _run_pytest(test_path: str, pythonpath: str | None) -> int:
    """Run one kill-test in a subprocess. Return code 0 == passed == SURVIVED.
    Uses the venv interpreter directly (sys.executable is the venv python under
    `uv run`), skipping uv's per-call resolve. `pythonpath` shadows the editable
    install with a worker's private src copy (parallel mode); None = real tree."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    if pythonpath is not None:
        env["PYTHONPATH"] = pythonpath + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "pytest", test_path, *_PYTEST_ARGS],
        cwd=ROOT, env=env,
    ).returncode


def _probe(target_file: Path, desc: str, old: str, new: str, test_path: str,
           pythonpath: str | None, survivors: list[str]) -> None:
    """Apply one mutation to target_file, run its kill-test, restore. Records a
    survivor (or stale) exactly as the original serial run_group did."""
    orig = target_file.read_text()
    if old not in orig:
        with _PRINT_LOCK:
            print(f"STALE MUTATION (text not found): {desc}")
        survivors.append(desc + " (stale)")
        return
    target_file.write_text(orig.replace(old, new, 1))
    try:
        survived = _run_pytest(test_path, pythonpath) == 0
    finally:
        target_file.write_text(orig)
    with _PRINT_LOCK:
        if survived:
            print(f"SURVIVED: {desc}")
            survivors.append(desc)
        else:
            print(f"killed: {desc}")


def _execute(units: list[_Unit], survivors: list[str]) -> None:
    """Dispatch collected units. In parallel mode, src/artifactsmmo_cli targets
    run copy-isolated across workers (main tree untouched); the handful of
    formal/sim targets — outside the editable package, so not PYTHONPATH-
    shadowable — run serially in-place AFTER the parallel phase finishes, so the
    two phases never race on the production tree."""
    if _RUNNER == "serial":
        _execute_serial(units, survivors)
        return
    parallel = [u for u in units if _SRC_ROOT in u[0].parents]
    serial = [u for u in units if _SRC_ROOT not in u[0].parents]
    if parallel:
        _execute_parallel(parallel, survivors)
    _execute_serial(serial, survivors)


def _execute_serial(units: list[_Unit], survivors: list[str]) -> None:
    for src, desc, old, new, test_path in units:
        _probe(src, desc, old, new, test_path, None, survivors)


def _execute_parallel(units: list[_Unit], survivors: list[str]) -> None:
    """Fan units across _WORKERS threads, each leasing a private src copy."""
    n = max(1, min(_WORKERS, len(units)))
    tmp = Path(tempfile.mkdtemp(prefix="mutate-workers-"))
    lease: queue.Queue[Path] = queue.Queue()
    try:
        for k in range(n):
            copy_root = tmp / f"w{k}"
            shutil.copytree(_SRC_ROOT / _SRC_PKG, copy_root / _SRC_PKG,
                            ignore=shutil.ignore_patterns("__pycache__"))
            lease.put(copy_root)

        def task(unit: _Unit) -> None:
            src, desc, old, new, test_path = unit
            copy_root = lease.get()
            try:
                target = copy_root / src.relative_to(_SRC_ROOT)
                _probe(target, desc, old, new, test_path, str(copy_root), survivors)
            finally:
                lease.put(copy_root)

        with ThreadPoolExecutor(max_workers=n) as pool:
            list(pool.map(task, units))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# Killed by formal/diff/test_skill_gate_fastfail_diff.py (binds gather_plannable_pure
# to the proved Formal.SkillGateFastFail.isPlannable).
GATHER_PLANNABLE_MUTATIONS = [
    ("gather_plannable: drop the owned-fallback (always plannable when gated)",
     "    return owned >= needed",
     "    return True"),
    ("gather_plannable: skill gate off-by-one (>= becomes >)",
     "    if not has_craft_gate or cur_level >= craft_level:",
     "    if not has_craft_gate or cur_level > craft_level:"),
    ("gather_plannable: owned-fallback off-by-one (>= becomes >)",
     "    return owned >= needed",
     "    return owned > needed"),
]

# Killed by formal/diff/test_leaf_attainable_diff.py (binds leaf_attainable_pure
# to the proved Formal.LeafAttainable.leafAttainable).
LEAF_ATTAINABLE_MUTATIONS = [
    ("leaf_attainable: drop the task-earnable disjunct",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return (gatherable or known_spawn_drop\n            or buyable_with_attainable_currency)"),
    ("leaf_attainable: drop the currency-buy disjunct",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return (gatherable or known_spawn_drop or task_earnable)"),
    ("leaf_attainable: collapse to always-True",
     "    return (gatherable or known_spawn_drop or task_earnable\n            or buyable_with_attainable_currency)",
     "    return True"),
]

# Killed by formal/diff/test_complete_task_income_diff.py (binds complete_task_apply_pure
# to the proved Formal.CompleteTaskIncome.applyComplete).
COMPLETE_TASK_MUTATIONS = [
    ("complete_task: mint zero instead of coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0)"),
    ("complete_task: subtract instead of add the reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) + coin_reward",
     "    new_inventory[TASKS_COIN_CODE] = new_inventory.get(TASKS_COIN_CODE, 0) - coin_reward"),
]

# Killed by formal/diff/test_currency_funding_diff.py (binds funding_cycles_pure
# to the proved Formal.Liveness.CurrencyFunding.fundingCycles).
FUNDING_MUTATIONS = [
    ("funding_cycles: drop the ceil rounding (floor-div understates cycles)",
     "    return (deficit + per_task_floor - 1) // per_task_floor",
     "    return deficit // per_task_floor"),
    ("funding_cycles: ignore on_hand (always full target)",
     "    deficit = target - on_hand",
     "    deficit = target"),
    ("funding_cycles: drop already-funded short-circuit",
     "    if on_hand >= target:\n        return 0",
     "    if False:\n        return 0"),
]

# Killed by formal/diff/test_currency_afford_diff.py (binds
# currency_afford_plannable_pure to the proved Formal.CurrencyAffordFastFail.isPlannable).
# The three mutants cover: dropping the `affordable` disjunct (always
# False when unaffordable+unowned), dropping the `owned >= needed`
# fallback (already-owned leaf wrongly pruned), and collapsing to
# always-True (fast-fail never fires — the original node-burn bug).
CURRENCY_AFFORD_MUTATIONS = [
    ("currency_afford: drop affordable disjunct",
     "    return (not target_in_closure) or affordable or owned >= needed",
     "    return (not target_in_closure) or owned >= needed"),
    ("currency_afford: drop owned-fallback disjunct",
     "    return (not target_in_closure) or affordable or owned >= needed",
     "    return (not target_in_closure) or affordable"),
    ("currency_afford: collapse to always-True",
     "    return (not target_in_closure) or affordable or owned >= needed",
     "    return True"),
]

# Killed by formal/diff/test_doomed_memo_diff.py (binds DoomedMemo._ttl / is_doomed
# to the proved Formal.DoomedMemo.ttl / isDoomed).
DOOMED_MEMO_MUTATIONS = [
    ("doomed_memo: drop exponential backoff (window stays at base)",
     "        return min(self._base_retry << (failures - 1), self._max_retry)",
     "        return min(self._base_retry, self._max_retry)"),
    ("doomed_memo: ttl shift off-by-one (failures-1 becomes failures)",
     "        return min(self._base_retry << (failures - 1), self._max_retry)",
     "        return min(self._base_retry << failures, self._max_retry)"),
    ("doomed_memo: drop signature invalidation (skip even when plannability moved)",
     "        if sig != plannability_signature(state):\n            return False",
     "        if False:\n            return False"),
    ("doomed_memo: window off-by-one (< becomes <=)",
     "        return cycle - set_at < self._ttl(failures)",
     "        return cycle - set_at <= self._ttl(failures)"),
]

# Killed by tests/test_ai/test_combat.py — the learned-veto threshold that stops the
# bot grinding marginal monsters (blue_slime 13%-loss trace 2026-06-15).
COMBAT_VETO_MUTATIONS = [
    ("combat: weaken learned-veto threshold 0.9 -> 0.5 (re-admits marginal monsters)",
     "WIN_RATE_THRESHOLD = 0.9",
     "WIN_RATE_THRESHOLD = 0.5"),
]


# Killed by tests/test_ai/test_strategy_driver_tiered.py (the cheap-pass conclusive
# marking policy — the feather_coat re-explosion fix).
STRATEGY_DRIVER_MUTATIONS = [
    ("strategy_driver: cheap pass marks on timeout too (drops the conclusive gate)",
     "        elif mark_on_timeout or not timed_out:",
     "        elif mark_on_timeout or timed_out:"),
    ("strategy_driver: clear requires BOTH guard and plan (drops plan-clears)",
     "        if r in guard_reprs or plan:",
     "        if r in guard_reprs and plan:"),
]


# Utility-stat valuation (2026-06-15 novice_guide discard fix). hp_bonus/wisdom/
# prospecting must count so artifacts are scored, equipped, and not discarded.
ARMOR_UTILITY_MUTATIONS = [
    ("armor_score: drop whole flat utility (hp_bonus+wisdom+prospecting+inventory_space+haste+lifesteal+combat_buff) score 0",
     "    return (score + hp_bonus + wisdom + prospecting + inventory_space + haste\n"
     "            + lifesteal + combat_buff)",
     "    return score"),
    ("armor_score: drop lifesteal — lifesteal gear undervalued",
     "            + lifesteal + combat_buff)",
     "            + combat_buff)"),
    ("armor_score: drop combat_buff — buff potions undervalued",
     "            + lifesteal + combat_buff)",
     "            + lifesteal)"),
]
EQUIP_VALUE_UTILITY_MUTATIONS = [
    ("equip_value: drop whole utility tail from raw — utility/bags/haste/lifesteal/combat_buff undervalued",
     "           + hp_bonus + dmg + critical_strike + wisdom + prospecting + inventory_space + haste\n"
     "           + lifesteal + combat_buff)",
     "           + hp_bonus + dmg + critical_strike)"),
    ("equip_value: drop lifesteal from raw — lifesteal gear undervalued",
     "           + lifesteal + combat_buff)",
     "           + combat_buff)"),
    ("equip_value: drop combat_buff from raw — buff potions undervalued",
     "           + lifesteal + combat_buff)",
     "           + lifesteal)"),
]
EQUIP_VALUE_DOMINANCE_MUTATIONS = [
    ("dominance _equip_value: drop whole utility — artifact/bag/haste/lifesteal/combat_buff valued 0",
     "    return (attack + resistance + hp + stats.hp_bonus + stats.wisdom\n"
     "            + stats.prospecting + stats.inventory_space + stats.haste + stats.lifesteal\n"
     "            + stats.combat_buff)",
     "    return attack + resistance + hp"),
    ("dominance _equip_value: drop lifesteal — lifesteal gear valued 0",
     "            + stats.prospecting + stats.inventory_space + stats.haste + stats.lifesteal\n"
     "            + stats.combat_buff)",
     "            + stats.prospecting + stats.inventory_space + stats.haste\n"
     "            + stats.combat_buff)"),
    ("dominance _equip_value: drop combat_buff — buff potions valued 0",
     "+ stats.lifesteal\n"
     "            + stats.combat_buff)",
     "+ stats.lifesteal)"),
]


def run_group(src: Path, mutations: list[tuple[str, str, str]], test_path: str,
              survivors: list[str]) -> None:
    """Collect this group's mutation units into _UNITS (filtered by _ONLY).
    Execution is deferred to _execute so units can be fanned across workers. The
    `survivors` param is retained for call-site compatibility and unused here."""
    if _ONLY is not None and not any(
            tok in str(src) or tok in test_path for tok in _ONLY):
        return
    for desc, old, new in mutations:
        _UNITS.append((src, desc, old, new, test_path))


_ALL_SRCS = [
    GATHER_PLANNABLE_CORE_SRC, DOOMED_MEMO_SRC, STRATEGY_DRIVER_SRC, EQUIP_VALUE_SRC,
    GAME_DATA_PARSE_SRC, LOCATION_CATALOG_SRC,
    SRC, TASK_BATCH_SRC, INVENTORY_CAPS_SRC, COMBAT_SRC, PROJECTION_SRC, SCORING_SRC,
    SKILL_XP_CURVE_SRC, RECIPE_CLOSURE_SRC, TASK_FEASIBILITY_SRC, PREREQUISITE_GRAPH_SRC,
    OBJECTIVE_SRC, STRATEGY_SRC, BANK_SELECTION_SRC, STUCK_DETECTOR_SRC,
    PRIORITY_BAND_SRC, OWNED_COUNT_SRC, ROOT_PROGRESS_SRC, UPGRADE_SELECTION_SRC, SCALAR_CORE_SRC,
    PLANNER_SRC, ARBITER_SELECT_SRC, TASK_DECISION_CORE_SRC, OBJECTIVE_COMPLETION_SRC,
    LOW_YIELD_BOUNDARY_SRC, STRATEGY_BLEND_SRC, DECIDE_KEY_SRC,
    CYCLES_FOR_PROGRESS_SRC,
    GATHER_APPLY_SRC,
    GATHER_SELECTION_SRC,
    MONSTER_DROP_SELECTION_SRC,
    CRAFT_VS_BUY_SRC,
    NEAREST_TILE_SRC,
    CONSUMABLE_SELECTION_SRC,
    BANK_EXPANSION_TIMING_SRC,
    EVENT_WINDOW_SRC,
    COST_CORE_SRC,
    NPC_BUY_CORE_SRC,
    TASK_TRADE_CORE_SRC,
    APPLY_MOVE_SRC, APPLY_EQUIP_SRC, APPLY_CLAIM_SRC,
    APPLY_REST_SRC, APPLY_FIGHT_SRC, APPLY_BANK_EXPANSION_SRC, APPLY_TELEPORT_SRC,
    CONSUMABLE_SUPPLY_SRC, MEANS_SRC, GUARDS_SRC,
    WITHDRAW_ITEM_SRC, UNEQUIP_SRC, TASK_EXCHANGE_SRC, TASK_CANCEL_SRC,
    GATHERING_APPLY_SRC, LEVEL_SKILL_GOAL_SRC,
    MONSTER_CATALOG_SRC,
    WINNABLE_CASCADE_SRC,
    COMBAT_PICKER_SRC,
    PROJECTIONS_SRC,
    # Phase-17 — scalar_yield wired through clamp_into_band into discretionary goals.
    GATHERING_GOAL_SRC, PURSUE_TASK_GOAL_SRC, SCALAR_PRIORITY_SRC,
    # Phase-18 — value-range theorems for the remaining goals.
    ACCEPT_TASK_GOAL_SRC, CLAIM_PENDING_GOAL_SRC, TASK_EXCHANGE_GOAL_SRC,
    TASK_CANCEL_GOAL_SRC, COMPLETE_TASK_GOAL_SRC, REACH_UNLOCK_LEVEL_GOAL_SRC,
    LOW_YIELD_CANCEL_GOAL_SRC, UNLOCK_BANK_GOAL_SRC, DISCARD_OVERSTOCK_GOAL_SRC,
    PROGRESSION_GOAL_SRC, RESTORE_HP_GOAL_SRC, DEPOSIT_INVENTORY_GOAL_SRC,
    SELL_INVENTORY_GOAL_SRC,
    # Phase-19d — Tier-1 liveness measure port.
    MEASURE_SRC,
    # Phase 21d-2 — Tier-3 plan-exists differential against real planner.
    # (The `_build_actions` body now lives in actions/factory.py — `GamePlayer.
    # _build_actions` delegates to `build_actions`; mutations target the factory.)
    ACTION_FACTORY_SRC,
    # Phase-22b — cycle-loop mirror.
    CYCLE_STEP_SRC,
    # Piece-C — feasibility router for depth-unreachable equippable roots.
    GATHER_STEP_TARGET_SRC,
    # #16 — efficiency-weighted strategic_value scorer.
    STRATEGIC_VALUE_SRC,
    # C1 — acquisition-leaf attainability (task-earnable + currency-buy disjuncts).
    LEAF_ATTAINABLE_CORE_SRC,
    # C2 — complete_task coin-minting pure core.
    COMPLETE_TASK_CORE_SRC,
    # C3 — funding_cycles_pure: cycles to reach a currency target.
    FUNDING_CORE_SRC,
    # C4 — currency_afford_plannable_pure: fast-fail for unaffordable currency-buy leaves.
    CURRENCY_AFFORD_CORE_SRC,
    # C5 — next_craft_target_pure: churn fix (replaces 52K-node A* re-run).
    NEXT_CRAFT_CORE_SRC,
]


# Phase 12 Target A: cheapest_path_to_level greedy contract. Mutants test
# (a) the +1 beatability margin, (b) strict-> tie-break, (c) the
# `best_xp_per_cycle <= 0` blocked branch, (d) the is_winnable beatability
# filter. The diff test must kill all four.
CHEAPEST_PATH_MUTATIONS = [
    # Mutation 1: shrink the beatability bound from `lvl <= sim_level + 1` to
    # `lvl <= sim_level`. test_plus_one_boundary_beatable now blocks (Python)
    # but Lean still picks the +1 monster — divergence.
    ("cheapest_path: drop the +1 beatability margin",
     "            if 1 <= lvl <= sim_level + 1",
     "            if 1 <= lvl <= sim_level"),
    # Mutation 2: invert tie-break — use `>=` so the LAST tying monster wins.
    # test_tie_first_wins flips (Python now picks beta, Lean still alpha).
    ("cheapest_path: tie-break inversion (> -> >=)",
     "            if xp_per_cycle > best_xp_per_cycle:",
     "            if xp_per_cycle >= best_xp_per_cycle:"),
    # Mutation 3: invert the comparison sign so the WORST monster wins
    # (pick the minimum xp_per_cycle instead of maximum). Caught by
    # test_strict_greater_replaces and test_greedy_picks_higher_xp_per_kill.
    ("cheapest_path: invert greedy direction (> -> <)",
     "            if xp_per_cycle > best_xp_per_cycle:",
     "            if xp_per_cycle < best_xp_per_cycle:"),
    # Mutation 4: drop the is_winnable beatability filter so unwinnable monsters
    # are included as candidates. test_winnable_false_skips_to_winnable fires:
    # Python picks the unwinnable 'hard' monster while Lean (still filtering via
    # winnable=0) picks 'easy' — divergence kills this mutant.
    ("cheapest_path: drop is_winnable beatability filter",
     "            and is_winnable(state, game_data, code, store)",
     ""),
]


# cycles_for_progress mutations -- old strings matched to current cycles_for_progress_core.py text.
CYCLES_FOR_PROGRESS_MUTATIONS = [
    # Drop the SATISFY append loop entirely: only strict-increase intervals
    # contribute. The verdict-(b) intentional-both-signal contract breaks;
    # `test_satisfy_only_branch` and `test_both_on_single_cycle_intentional_double_signal`
    # fire (the satisfy interval would no longer appear in the median).
    ("cycles_for_progress: drop the satisfy append loop",
     "    for cycle in chrono:\n"
     "        intervals = _satisfy_step(intervals, cycle)\n",
     ""),
    # Flip the satisfy gate's None check: the recorded `cycles_to_satisfy`
    # values are SKIPPED (returned untouched) and the (sparse) None-rows fall
    # through to the `<= 0` comparison (TypeError). Hypothesis quickly
    # produces a row with `cycles_to_satisfy = None` AND a positive reading.
    ("cycles_for_progress: satisfy gate is None -> is not None",
     "    cts = cycle.cycles_to_satisfy\n"
     "    if cts is None:\n"
     "        return intervals",
     "    cts = cycle.cycles_to_satisfy\n"
     "    if cts is not None:\n"
     "        return intervals"),
    # Off-by-one on the strict-increase predicate (P3c: the inverted early
    # return `tp <= prev` weakens to `tp < prev`, the same semantic mutant as
    # the historical `>` -> `>=`). A flat `task_progress` row now also counts
    # as a strict increase, inflating the interval count. The general diff
    # test fires whenever progress holds steady for any chronological pair.
    ("cycles_for_progress: strict-increase > -> >= (off-by-one predicate)",
     "    if tp <= prev_progress:\n"
     "        return (intervals, last_progress_at, tp)",
     "    if tp < prev_progress:\n"
     "        return (intervals, last_progress_at, tp)"),
]


# gather_apply mutations -- old strings matched to current gather_apply_core.py text.
GATHER_APPLY_MUTATIONS = [
    # Drop the slot precondition: apply is now unguarded by free-slot count.
    # The is_applicable diff (with k = MIN_FREE_SLOTS at boundary) catches it.
    ("gather_apply: is_applicable always-true (drop slot check)",
     "    return (inv.cap - inv.used) >= min_free",
     "    return True"),
    # Off-by-one on the mint: +1 becomes +2 (apply mints two items, blowing the cap
    # boundary). The diff test pins post.used == used + 1 against the Lean oracle.
    ("gather_apply: mint +1 -> +2 (off-by-one)",
     "    return replace(inv, used=inv.used + 1, item_count=new_counts)",
     "    return replace(inv, used=inv.used + 2, item_count=new_counts)"),
    # Tighten >= to > on the slot check: at exactly k free slots the precondition
    # should hold, but now it spuriously refuses. The boundary test
    # `test_boundary_exactly_three_free_is_applicable_against_lean` fires.
    ("gather_apply: is_applicable >= -> > (off-by-one on slot floor)",
     "    return (inv.cap - inv.used) >= min_free",
     "    return (inv.cap - inv.used) > min_free"),
]


# monster_drop_apply mutations -- the Fight.apply drop loop in gather_apply_core.py.
# Killed by formal/diff/test_monster_drop_apply_diff.py, which binds
# apply_monster_drops_pure to Formal.MonsterDropApply.applyDrops -- the SAME def
# the reachability theorems (applyDrops_monotone / fight_drop_reachable) prove.
MONSTER_DROP_APPLY_MUTATIONS = [
    # Drop the cap-break: drops mint past inventory_max, breaking the
    # never-exceed-cap projection. The diff's used-near-cap cases catch it.
    ("monster_drop_apply: drop cap-break",
     "        if inv.used >= inv.cap:\n            break\n",
     "        if False:\n            break\n"),
    # Break boundary >= -> >: at exactly full (used == cap) the loop should stop
    # but now mints one more.
    ("monster_drop_apply: break boundary >= to >",
     "        if inv.used >= inv.cap:\n",
     "        if inv.used > inv.cap:\n"),
    # Skip the mint: the kill yields no loot, so a needed drop's count never
    # rises -- violates fight_drop_reachable (the goal becomes unreachable).
    ("monster_drop_apply: skip the mint",
     "        inv = gather_apply_pure(inv, drop_item)\n",
     "        inv = inv\n"),
]


# task_trade_core mutations -- old strings matched to current task_trade_core.py.
# Each perturbs the live held↔progress trade transition so the Python result
# diverges from the proven `quantity`-fold `ItemsTaskRun.trade` oracle. Killed by
# formal/diff/test_items_task_run_diff.py.
TASK_TRADE_CORE_MUTATIONS = [
    # Drop the held decrement: progress advances but inventory is not consumed
    # (the exact "free progress" hole the coupled model forbids). The diff pins
    # new_held == held - quantity against the oracle.
    ("task_trade_core: drop held decrement (held unchanged)",
     "    return (held - quantity, progress + quantity)",
     "    return (held, progress + quantity)"),
    # Drop the progress increment: inventory is consumed but progress stalls.
    # The diff pins new_progress == progress + quantity.
    ("task_trade_core: drop progress increment (progress unchanged)",
     "    return (held - quantity, progress + quantity)",
     "    return (held - quantity, progress)"),
    # Swap +/- on the transition: held grows, progress shrinks (sign inversion).
    ("task_trade_core: swap +/- (held + quantity, progress - quantity)",
     "    return (held - quantity, progress + quantity)",
     "    return (held + quantity, progress - quantity)"),
    # Weaken the action guard: drop the held >= quantity check (always-true held
    # side). The held-below-quantity boundary test fires.
    ("task_trade_core: drop held>=quantity guard",
     "    if held < quantity:\n        return False",
     "    if held < quantity:\n        return True"),
    # Drop the goal stop guard: progress < total becomes always-true, so the
    # action would over-trade past total. The progress-at-total test fires.
    ("task_trade_core: drop progress<total goal guard",
     "    return progress < total",
     "    return True"),
]


# gather_selection mutations -- old strings matched to current gather_selection.py
# text. Each perturbs the lex-argmin metric / tie-break so the Python winner
# diverges from the Lean `selectGatherSource` oracle. Killed by
# formal/diff/test_gather_selection_diff.py.
GATHER_SELECTION_MUTATIONS = [
    # Drop the average-yield divisor: the metric degenerates to bare `rate`,
    # ignoring min/max quantity. A high-yield high-rate source then loses to a
    # low-yield low-rate one — the avg-quantity cases in the diff fire.
    ("gather_selection: drop avg_quantity divisor (metric = rate only)",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)\n"
     "    return Fraction(c.rate) / avg_quantity",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)\n"
     "    return Fraction(c.rate)"),
    # avg_quantity uses `*` instead of `+`: wrong average (min*max not min+max),
    # so the expected-gathers ordering changes whenever min != max.
    ("gather_selection: avg_quantity + -> * (wrong average)",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)",
     "    avg_quantity = Fraction(c.min_quantity * c.max_quantity, 2)"),
    # Argmin -> argmax: pick the WORST (most expensive) source. Any list with two
    # distinct keys diverges from the Lean lex-min.
    ("gather_selection: min -> max (argmin becomes argmax)",
     "    return min(candidates, key=_key).resource_code",
     "    return max(candidates, key=_key).resource_code"),
    # Swap distance and expected_gathers in the lex key: distance now dominates the
    # metric, inverting the primary objective on any expected-gathers-vs-distance
    # tension.
    ("gather_selection: lex key swap (distance before expected_gathers)",
     "    return (_expected_gathers(c), c.distance, c.resource_code)",
     "    return (c.distance, _expected_gathers(c), c.resource_code)"),
    # Drop the code tie-break (constant third field): two candidates tying on
    # (expected_gathers, distance) become order-ambiguous; Python `min` first-wins
    # by list position, diverging from the Lean code-ordered tie-break.
    ("gather_selection: drop code tie-break (third field constant)",
     "    return (_expected_gathers(c), c.distance, c.resource_code)",
     "    return (_expected_gathers(c), c.distance, \"\")"),
]


# shopping_list mutations -- old strings matched to current shopping_list.py
# text. Each breaks the bank-aware credit / short-circuit / recursion so the
# total raw work the Python net implies diverges from the Lean `rawReq` oracle.
# Killed by formal/diff/test_shopping_list_diff.py.
SHOPPING_LIST_MUTATIONS = [
    # Drop the holdings credit: `used = 0` so the bank is never credited; the net
    # becomes the full naive requirement and any owned>0 case diverges.
    ("shopping_list: drop holdings credit (used = 0)",
     "    used = min(held, qty)",
     "    used = 0"),
    # Wrong-sign deficit: `qty + used` instead of `qty - used` over-counts work.
    ("shopping_list: deficit qty - used -> qty + used",
     "    deficit = qty - used",
     "    deficit = qty + used"),
    # Remove the short-circuit: recurse into the subtree even when fully covered
    # (deficit <= 0). A bank-covered intermediate then still expands its sub-recipe
    # work instead of being withdrawn, over-counting.
    ("shopping_list: drop short-circuit (always expand subtree)",
     "    if deficit <= 0:\n"
     "        # Fully covered by holdings: SHORT-CIRCUIT — do not expand the subtree.\n"
     "        # The banked copies are withdrawn, so no sub-material work is needed.\n"
     "        return (owned, net)",
     "    if False:\n"
     "        return (owned, net)"),
    # Ignore the credit in the recursion: expand at `per_unit * qty` instead of
    # `per_unit * deficit`, so partial-bank cases over-count the sub-material work.
    ("shopping_list: recurse on qty not deficit (ignore credit downstream)",
     "        state = _expand(fuel - 1, material, per_unit * deficit, recipes, state)",
     "        state = _expand(fuel - 1, material, per_unit * qty, recipes, state)"),
]


# min_gathers mutations (P3d) -- each breaks the threaded-CONSUME gather
# lower bound so the routed (code, qty) diverges from the Lean `gatherTarget`
# oracle (which calls the proved `minGathersCount`).
# Killed by formal/diff/test_gather_step_target_diff.py.
MIN_GATHERS_MUTATIONS = [
    # Never credit holdings: every node pays its full quantity -> a covered
    # chain looks unreachable. Killed by test_reachable_root_keeps_root
    # (cost 480 instead of 0 would route to the step).
    ("min_gathers: never credit holdings (used = 0)",
     "    used = min(held, qty)",
     "    used = 0"),
    # Never CONSUME the credited stock -- the pre-P3d constant-credit hand
    # model regression: shared stock double-credited under every parent on a
    # DAG. Killed by test_dag_double_credit_witness_routes_to_step (cost 0
    # instead of 1 would keep the root).
    ("min_gathers: never consume credited stock (constant credit)",
     "    owned[item] = held - used",
     "    owned[item] = held"),
    # Recurse at the UNCREDITED quantity: the node's own credit is ignored
    # below it. Killed by test_partial_credit_keeps_root (cost 80 instead of
    # 50 would route to the step).
    ("min_gathers: recurse at uncredited quantity (per_unit * qty)",
     "        state = _min_gathers(fuel - 1, material, per_unit * remaining, recipes, state)",
     "        state = _min_gathers(fuel - 1, material, per_unit * qty, recipes, state)"),
    # A raw leaf contributes nothing: every chain costs 0 -> everything looks
    # reachable. Killed by test_unreachable_root_routes_to_step (cost 0
    # instead of 480 would keep the root).
    ("min_gathers: raw leaf contributes nothing",
     "        return (total + remaining, owned)",
     "        return (total, owned)"),
]


# gather_step_target mutations -- each breaks the budget-feasibility routing so
# the Python (code, qty) diverges from the Lean `gatherTarget` oracle.
# Killed by formal/diff/test_gather_step_target_diff.py.
GATHER_STEP_TARGET_MUTATIONS = [
    # Invert the feasibility gate: route to the deep root when OVER budget and to
    # the step when UNDER — the exact opposite of the sound decision.
    ("gather_step_target: invert budget gate (<= -> >)",
     "    if root_cost <= equip_max_depth:",
     "    if root_cost > equip_max_depth:"),
    # Always keep the root target (never route to the step) -> the deep root goal
    # that explodes the planner is built for every unreachable chain.
    ("gather_step_target: always root (drop step routing)",
     "    if root_cost <= equip_max_depth:\n        return (root_item, 1)\n    return (step_item, step_qty)",
     "    return (root_item, 1)"),
    # Always route to the step (never keep a reachable root) -> a reachable root's
    # one-commit craft+equip is wrongly abandoned for a bare gather.
    ("gather_step_target: always step (ignore reachable root)",
     "    if root_cost <= equip_max_depth:\n        return (root_item, 1)\n    return (step_item, step_qty)",
     "    return (step_item, step_qty)"),
    # Drop the multi-yield divisor (max_yield -> 1): raw UNITS are mistaken for
    # gather ACTIONS, so a multi-drop chain is over-counted into a false skip.
    # Killed by test_multi_yield_divides_cost_keeps_root (yield 2: 16 units would
    # route to the step instead of keeping the root at ceil(16/2)=8 <= 15).
    ("gather_step_target: drop yield divisor (max_yield := 1)",
     "    root_cost = ceil_gathers(min_gathers(root_item, 1, recipes, owned), max_yield)",
     "    root_cost = ceil_gathers(min_gathers(root_item, 1, recipes, owned), 1)"),
]


# monster_drop_selection mutations -- old strings matched to current
# monster_drop_selection.py text. Each perturbs the lex-argmin metric / tie-break
# so the Python winner diverges from the Lean `selectMonsterForDrop` oracle.
# Killed by formal/diff/test_monster_drop_selection_diff.py. The distance
# tie-break drop and the argmin->argmax flip are the two the task pins.
MONSTER_DROP_SELECTION_MUTATIONS = [
    # Drop the average-yield divisor: the metric degenerates to bare `rate`,
    # ignoring min/max quantity; high-yield high-rate loses to low-yield low-rate.
    ("monster_drop_selection: drop avg_quantity divisor (metric = rate only)",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)\n"
     "    return Fraction(c.rate) / avg_quantity",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)\n"
     "    return Fraction(c.rate)"),
    # avg_quantity uses `*` instead of `+`: wrong average, ordering changes when
    # min != max.
    ("monster_drop_selection: avg_quantity + -> * (wrong average)",
     "    avg_quantity = Fraction(c.min_quantity + c.max_quantity, 2)",
     "    avg_quantity = Fraction(c.min_quantity * c.max_quantity, 2)"),
    # Argmin -> argmax: pick the WORST (most kills) monster. Any list with two
    # distinct keys diverges from the Lean lex-min (flips the `<` direction).
    ("monster_drop_selection: min -> max (argmin becomes argmax)",
     "    return min(candidates, key=_key).monster_code",
     "    return max(candidates, key=_key).monster_code"),
    # Swap distance and expected_kills in the lex key: distance dominates, inverting
    # the primary objective on any kills-vs-distance tension.
    ("monster_drop_selection: lex key swap (distance before expected_kills)",
     "    return (_expected_kills(c), c.distance, c.monster_code)",
     "    return (c.distance, _expected_kills(c), c.monster_code)"),
    # Drop the distance tie-break (constant second field): candidates tying on
    # expected_kills become distance-ambiguous; Python `min` first-wins by list
    # position, diverging from the Lean distance-ordered tie-break.
    ("monster_drop_selection: drop distance tie-break (second field constant)",
     "    return (_expected_kills(c), c.distance, c.monster_code)",
     "    return (_expected_kills(c), 0, c.monster_code)"),
    # Drop the code tie-break (constant third field): candidates tying on
    # (expected_kills, distance) become order-ambiguous; Python `min` first-wins,
    # diverging from the Lean code-ordered tie-break.
    ("monster_drop_selection: drop code tie-break (third field constant)",
     "    return (_expected_kills(c), c.distance, c.monster_code)",
     "    return (_expected_kills(c), c.distance, \"\")"),
]


# craft_vs_buy mutations -- old strings matched to current craft_vs_buy.py text.
# Each perturbs the affordability test or the strict-cheaper test so the Python
# BUY/CRAFT verdict diverges from the Lean `cheaperAcquisition` oracle. Killed by
# formal/diff/test_craft_vs_buy_diff.py.
CRAFT_VS_BUY_MUTATIONS = [
    # Flip the affordability boundary `>=` to `>`: at exactly gold-price == reserve
    # the buy should be affordable (reserve preserved), but now it spuriously
    # refuses. The affordability-boundary cases in the diff fire.
    ("craft_vs_buy: affordability >= -> > (off-by-one on reserve floor)",
     "    affordable = gold - total_price >= reserve",
     "    affordable = gold - total_price > reserve"),
    # Invert the strict-cheaper comparison `<` to `>`: buy now fires when it is
    # MORE expensive than craft, exactly inverting the optimization objective.
    ("craft_vs_buy: strict-cheaper < -> > (inverted objective)",
     "buy_cooldowns < craft_cooldowns",
     "buy_cooldowns > craft_cooldowns"),
    # `<` -> `<=`: a buy that merely TIES craft now fires, violating the
    # strictly-fewer-cooldowns dominance rule. The equal-cooldown cases diverge.
    ("craft_vs_buy: strict-cheaper < -> <= (non-strict)",
     "buy_cooldowns < craft_cooldowns",
     "buy_cooldowns <= craft_cooldowns"),
    # Replace the `and` with `or`: buy fires when EITHER affordable OR cheaper,
    # dropping the conjunction so unaffordable-but-cheaper (and affordable-but-
    # pricier) cases now wrongly BUY.
    ("craft_vs_buy: and -> or (conjunction dropped)",
     "affordable and buy_cooldowns < craft_cooldowns",
     "affordable or buy_cooldowns < craft_cooldowns"),
    # `gold - total_price` -> `gold + total_price`: the affordability test now
    # ADDS the price instead of subtracting it, so the reserve check is computed
    # from the wrong post-buy gold. Any nonzero price diverges.
    ("craft_vs_buy: affordability - -> + (wrong post-buy gold)",
     "    affordable = gold - total_price >= reserve",
     "    affordable = gold + total_price >= reserve"),
]

# liquidation_venue mutations -- old strings matched to current
# liquidation_venue.py text. Each perturbs the immediate-fill venue decision so the
# Python venue/realized verdict diverges from the Lean `chooseVenue`/
# `realizedProceeds` oracle. Killed by formal/diff/test_liquidation_venue_diff.py.
LIQUIDATION_VENUE_MUTATIONS = [
    # Flip the strict `>` to `>=`: a standing order that merely TIES the NPC
    # sell-back now spuriously wins GE, violating the strict-dominance rule. The
    # tie cases in the diff fire.
    ("liquidation_venue: strict > -> >= (GE wins on a tie)",
     "if ge_proceeds is not None and ge_proceeds > npc_pay:",
     "if ge_proceeds is not None and ge_proceeds >= npc_pay:"),
    # Drop the `is not None` guard: GE can now be chosen on a phantom (absent)
    # order — exactly the anti-surrogate violation. (A `None > int` comparison
    # raises in Python, so the diff's None cases diverge by erroring/branching.)
    ("liquidation_venue: drop isSome guard (GE on phantom order)",
     "if ge_proceeds is not None and ge_proceeds > npc_pay:",
     "if ge_proceeds is not None or ge_proceeds > npc_pay:"),
    # Invert the comparison `>` to `<`: GE now fires when the order pays LESS than
    # the NPC sell-back, inverting the value objective.
    ("liquidation_venue: > -> < (inverted proceeds objective)",
     "if ge_proceeds is not None and ge_proceeds > npc_pay:",
     "if ge_proceeds is not None and ge_proceeds < npc_pay:"),
    # Break the realized-gold coupling: realize the NPC price even when GE is
    # chosen, so the proceeds no longer reflect the actual venue. The realized
    # field in the diff diverges on every GE win.
    ("liquidation_venue: realized decouple (GE realizes npc_pay)",
     "    if venue is Venue.GE and ge_proceeds is not None:\n        return ge_proceeds\n    return npc_pay",
     "    if venue is Venue.GE and ge_proceeds is not None:\n        return npc_pay\n    return npc_pay"),
]

# buy_source_venue mutations (DUAL of liquidation_venue) -- old strings matched to
# current buy_source_venue.py text. Each perturbs the immediate-fill BUY source
# decision so the Python venue/realized verdict diverges from the Lean
# `chooseBuyVenue`/`realizedCost` oracle. Killed by
# formal/diff/test_buy_source_venue_diff.py.
BUY_SOURCE_VENUE_MUTATIONS = [
    # Flip the strict `<` to `<=`: a standing order that merely TIES the NPC buy
    # price now spuriously wins GE, violating the strict-dominance rule. The tie
    # cases in the diff fire.
    ("buy_source_venue: strict < -> <= (GE wins on a tie)",
     "if ge_price is not None and ge_price < npc_price:",
     "if ge_price is not None and ge_price <= npc_price:"),
    # Drop the `is not None` guard: GE can now be chosen on a phantom (absent)
    # order — exactly the anti-surrogate violation. (A `None < int` comparison
    # raises in Python, so the diff's None cases diverge by erroring/branching.)
    ("buy_source_venue: drop isSome guard (GE on phantom order)",
     "if ge_price is not None and ge_price < npc_price:",
     "if ge_price is not None or ge_price < npc_price:"),
    # Invert the comparison `<` to `>`: GE now fires when the order costs MORE than
    # the NPC buy price, inverting the cost objective.
    ("buy_source_venue: < -> > (inverted cost objective)",
     "if ge_price is not None and ge_price < npc_price:",
     "if ge_price is not None and ge_price > npc_price:"),
    # Break the realized-gold coupling: realize the NPC price even when GE is
    # chosen, so the cost no longer reflects the actual venue. The realized field
    # in the diff diverges on every GE win.
    ("buy_source_venue: realized decouple (GE realizes npc_price)",
     "    if venue is BuyVenue.GE and ge_price is not None:\n        return ge_price\n    return npc_price",
     "    if venue is BuyVenue.GE and ge_price is not None:\n        return npc_price\n    return npc_price"),
]

# nearest_tile mutations -- old strings matched to current nearest_tile.py text.
# Each perturbs the Manhattan metric or the lex (manhattan, x, y) tie-break so the
# Python winner diverges from the Lean `nearestTile` oracle. Killed by
# formal/diff/test_nearest_tile_diff.py.
NEAREST_TILE_MUTATIONS = [
    # Argmin -> argmax: pick the FARTHEST tile. Any list with two distinct keys
    # diverges from the Lean lex-min.
    ("nearest_tile: min -> max (argmin becomes argmax)",
     "    return min(",
     "    return max("),
    # Drop the y-axis distance term: the metric ignores vertical distance, so two
    # tiles equal in x-distance but differing in y now mis-rank.
    ("nearest_tile: drop y-axis distance term",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[0], t[1]),",
     "        key=lambda t: (abs(t[0] - origin_x), t[0], t[1]),"),
    # Distance + -> -: subtract the y-distance instead of adding it, breaking the
    # Manhattan metric whenever the y term is nonzero.
    ("nearest_tile: distance + -> - (broken manhattan)",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[0], t[1]),",
     "        key=lambda t: (abs(t[0] - origin_x) - abs(t[1] - origin_y), t[0], t[1]),"),
    # Swap the x and y tie-break fields: on a distance tie the lex order now compares
    # y before x, inverting the deterministic winner whenever x and y disagree.
    ("nearest_tile: lex tie-break swap (y before x)",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[0], t[1]),",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[1], t[0]),"),
    # Drop the lex tie-break entirely (constant second/third fields): two tiles tying
    # on distance become order-ambiguous; Python `min` first-wins by list position,
    # diverging from the Lean (x, y)-ordered tie-break — the apply/execute divergence.
    ("nearest_tile: drop lex tie-break (constant fields)",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), t[0], t[1]),",
     "        key=lambda t: (abs(t[0] - origin_x) + abs(t[1] - origin_y), 0, 0),"),
]


# consumable_selection mutations -- old strings matched to current
# consumable_selection.py text. Each perturbs the overheal-aware lex key or the
# usability filter so the Python pick diverges from the Lean `selectConsumable`
# oracle. Killed by formal/diff/test_consumable_selection_diff.py.
CONSUMABLE_SELECTION_MUTATIONS = [
    # overheal-flag direction flip: `restore > deficit` -> `restore < deficit`, so a
    # FITTING item is wrongly flagged as overheal (and vice versa); the fit-preference
    # inverts and a big overhealer can beat a small fitter — the original bug.
    ("consumable_selection: overheal flag direction flip (> -> <)",
     "    overheal = restore > deficit",
     "    overheal = restore < deficit"),
    # waste sign flip: `restore - deficit` -> `deficit - restore`, so among
    # overhealers the LARGEST overshoot is preferred (negative waste sorts first).
    ("consumable_selection: waste sign flip (restore - deficit -> deficit - restore)",
     "    waste = (restore - deficit) if overheal else 0",
     "    waste = (deficit - restore) if overheal else 0"),
    # coverage sign flip: `-restore` -> `restore`, so among fitters the SMALLEST
    # restore is chosen (argmin over +restore) instead of the largest coverage.
    ("consumable_selection: coverage sign flip (-restore -> restore)",
     "    return (overheal_flag, waste, -restore, code)",
     "    return (overheal_flag, waste, restore, code)"),
    # drop the code tiebreak (constant third-from-key field): ties resolve by
    # list order instead of code, so a smaller-code candidate appearing later loses.
    ("consumable_selection: drop code tiebreak (constant key)",
     "    return (overheal_flag, waste, -restore, code)",
     '    return (overheal_flag, waste, -restore, "")'),
    # usability filter weakening: `qty <= 0` -> `qty < 0`, so a qty==0 item becomes
    # usable and can be (wrongly) selected — the empty-stack item the filter must skip.
    ("consumable_selection: usability filter qty <= 0 -> < 0 (admits qty==0)",
     "        if qty <= 0:\n            continue",
     "        if qty < 0:\n            continue"),
]

# bank_expansion_timing mutations -- old strings matched to current
# bank_expansion_timing.py text. Each perturbs the fill-threshold cross-multiply
# or the reserve-safety gate so the Python verdict diverges from the Lean
# `shouldExpandBank` oracle. Killed by
# formal/diff/test_bank_expansion_timing_diff.py.
BANK_EXPANSION_TIMING_MUTATIONS = [
    # Flip the fill-threshold boundary `>=` to `>`: at an exact fill tie
    # (used*den == cap*num) the bank should be eligible, but now it spuriously
    # refuses. The cross-multiply boundary cases in the diff fire.
    ("bank_expansion_timing: threshold >= -> > (off-by-one on fill boundary)",
     "    at_threshold = used * trigger_den >= capacity * trigger_num",
     "    at_threshold = used * trigger_den > capacity * trigger_num"),
    # Drop the cross-multiply: compare used*den against capacity (no trigger_num),
    # so the fill threshold is computed against the wrong rational. Any
    # trigger_num != 1 with a capacity that disagrees diverges.
    ("bank_expansion_timing: drop trigger_num factor in cross-multiply",
     "    at_threshold = used * trigger_den >= capacity * trigger_num",
     "    at_threshold = used * trigger_den >= capacity"),
    # Flip the reserve boundary `>=` to `>`: at exactly gold-cost == reserve the
    # buy preserves the reserve and should fire, but now it refuses. The
    # reserve-boundary cases (reserve in {0,500}) fire.
    ("bank_expansion_timing: reserve >= -> > (off-by-one on reserve floor)",
     "    reserve_safe = gold - cost >= reserve",
     "    reserve_safe = gold - cost > reserve"),
    # `gold - cost` -> `gold + cost`: the reserve test ADDS the cost instead of
    # subtracting it, so the SAFETY gate is computed from the wrong post-buy gold.
    # Any nonzero cost diverges (the SAFETY-HOLE the fix closes).
    ("bank_expansion_timing: reserve - -> + (wrong post-buy gold)",
     "    reserve_safe = gold - cost >= reserve",
     "    reserve_safe = gold + cost >= reserve"),
    # Replace the `and` with `or`: fires when EITHER at-threshold OR reserve-safe,
    # dropping the conjunction so below-threshold-but-affordable (and
    # at-threshold-but-unaffordable, the SAFETY hole) cases now wrongly fire.
    ("bank_expansion_timing: and -> or (conjunction dropped)",
     "    return at_threshold and reserve_safe",
     "    return at_threshold or reserve_safe"),
    # Drop the reserve gate entirely: regress to the bare fill check, ignoring the
    # reserve floor — the exact pre-fix SAFETY-HOLE bug. The reserve=500 cases
    # where gold-cost < 500 but at threshold now wrongly fire.
    ("bank_expansion_timing: drop reserve gate (regress to bare fill check)",
     "    return at_threshold and reserve_safe",
     "    return at_threshold"),
]


EVENT_WINDOW_MUTATIONS = [
    # Flip the window check `>` to `>=`: at exactly remaining == travel+margin the
    # window is too tight (no slack to arrive), but now it spuriously trades. The
    # boundary cases in the diff fire.
    ("event_window: window > -> >= (off-by-one on arrival margin)",
     "return remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS",
     "return remaining >= travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS"),
    # Invert the window check `>` to `<`: the bot now trades EXACTLY when the
    # window has too little time, inverting the reachability gate.
    ("event_window: window > -> < (inverted reachability)",
     "return remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS",
     "return remaining < travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS"),
    # Drop the arrival margin: the safety buffer disappears, so trips that can't
    # actually finish before expiry now fire. Cases near the margin diverge.
    ("event_window: drop arrival margin (+ -> -)",
     "return remaining > travel_seconds + EVENT_ARRIVAL_MARGIN_SECONDS",
     "return remaining > travel_seconds - EVENT_ARRIVAL_MARGIN_SECONDS"),
    # Flip the inactive-event guard to return True: an event with no active
    # window is now wrongly treated as tradeable. Inactive cases diverge.
    ("event_window: inactive guard False -> True",
     "        return False  # event not active",
     "        return True  # event not active"),
    # Drop the travel cost: distance no longer matters, so far merchants with a
    # short window now spuriously trade. Nonzero-distance cases diverge.
    ("event_window: drop travel cost (* -> * 0)",
     "    travel_seconds = distance * EVENT_TRAVEL_SECONDS_PER_TILE",
     "    travel_seconds = distance * 0"),
]


# npc_buy mutations -- REAL BUG #6. Each resurrects the inventory overflow
# by dropping the slot floor, flipping the boundary, or minting too many items.
# Killed by formal/diff/test_npc_buy_inventory_diff.py.
NPC_BUY_MUTATIONS = [
    # Drop the slot-free check: resurrects the original bug — apply mints past
    # inventory_max. The regression-pin (used=9, cap=10, quantity=5) fires.
    ("npc_buy: drop inventory_free check in is_applicable",
     "    free = inv_max - inv_used\n"
     "    if free < quantity:\n"
     "        return False\n"
     "    return not gold < price * quantity",
     "    return not gold < price * quantity"),
    # Flip the slot-floor inequality: `free < quantity` -> `free <= quantity`.
    # Off-by-one — quantity exactly at free is now wrongly refused. The
    # boundary test (used=5, cap=10, quantity=5) fires.
    ("npc_buy: flip < to <= on slot floor (off-by-one)",
     "    free = inv_max - inv_used\n"
     "    if free < quantity:\n"
     "        return False",
     "    free = inv_max - inv_used\n"
     "    if free <= quantity:\n"
     "        return False"),
    # Apply mints +quantity+1 instead of +quantity: even with the precondition
    # satisfied, the post-state overflows the cap by 1. The diff's
    # `test_apply_matches_lean` Lean-oracle agreement fires.
    ("npc_buy: apply mints +quantity+1 instead of +quantity",
     "    new_inventory[item_code] = new_inventory.get(item_code, 0) + quantity\n"
     "    return new_inventory",
     "    new_inventory[item_code] = new_inventory.get(item_code, 0) + quantity + 1\n"
     "    return new_inventory"),
    # Item-currency path (task #13b). Drop the currency-on-hand gate: an
    # unaffordable currency purchase is wrongly accepted. Killed by
    # test_currency_insufficient_on_hand_blocked + the random currency diff.
    ("npc_buy: drop currency-on-hand check in currency is_applicable",
     "    return not currency_on_hand < total_spent",
     "    return True"),
    # Drop the slot floor on the currency path: apply could mint past cap.
    # Killed by the free-slot currency differential.
    ("npc_buy: drop slot floor in currency is_applicable",
     "    free = inv_max - inv_used\n"
     "    if free < quantity:\n"
     "        return False\n"
     "    return not currency_on_hand < total_spent",
     "    return not currency_on_hand < total_spent"),
    # Drop the currency consumption in apply: the currency stack is never drawn
    # down (resurrects the phase-5 gold-only bug). Killed by
    # test_currency_apply_matches_lean (post[coin] mismatch) +
    # test_currency_consumption_frees_net_space.
    ("npc_buy: drop currency consumption in currency apply",
     "    new_inventory[currency] = new_inventory.get(currency, 0) - total_spent\n"
     "    return new_inventory",
     "    return new_inventory"),
]


# apply-baseline mutations -- each resurrects REAL BUG #5 (the silent drop of
# all 8 server-snapshot stat-baseline fields by reverting an action's apply()
# to an explicit `WorldState(...)` construction that omits them). The
# differential test's `_assert_preserved` fires on every dropped field.
APPLY_MOVE_MUTATIONS = [
    (
        "apply-baseline-move: revert MoveAction.apply to explicit WorldState(...) dropping baseline",
        "    def apply(self, state: WorldState, game_data: GameData) -> WorldState:\n"
        "        return dataclasses.replace(state, x=self.x, y=self.y, cooldown_expires=None)",
        "    def apply(self, state: WorldState, game_data: GameData) -> WorldState:\n"
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=self.x, y=self.y,\n"
        "            inventory=state.inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "        )",
    ),
]


APPLY_EQUIP_MUTATIONS = [
    (
        "apply-baseline-equip: revert EquipAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            inventory=new_inventory,\n"
        "            equipment=new_equipment,\n"
        "            cooldown_expires=None,\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=state.x, y=state.y,\n"
        "            inventory=new_inventory, inventory_max=state.inventory_max,\n"
        "            equipment=new_equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "        )",
    ),
]


# Phase-14: per-family kill-witness mutations. Each resurrects REAL BUG #5 in
# a structurally DISTINCT family (Family 6 misc — Rest; Family 7 Fight;
# Family 6 misc — BuyBankExpansion with bank_capacity) to demonstrate the
# extended ApplyBaseline Lean proofs match the Python differential test for
# every modeled action — not just the original 3 representatives.
APPLY_REST_MUTATIONS = [
    (
        "apply-baseline-rest: revert RestAction.apply to explicit WorldState(...) dropping baseline",
        "    def apply(self, state: WorldState, game_data: GameData) -> WorldState:\n"
        "        return dataclasses.replace(state, hp=state.max_hp, cooldown_expires=None)",
        "    def apply(self, state: WorldState, game_data: GameData) -> WorldState:\n"
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.max_hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=state.x, y=state.y,\n"
        "            inventory=state.inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "        )",
    ),
]


APPLY_TELEPORT_MUTATIONS = [
    (
        "apply-baseline-teleport: revert TeleportAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            x=self.dest_x,\n"
        "            y=self.dest_y,\n"
        "            inventory=new_inventory,\n"
        "            cooldown_expires=None,\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=self.dest_x, y=self.dest_y,\n"
        "            inventory=new_inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "        )",
    ),
]


# PLAN #6b: teleport cost is a flat constant mirroring Lean teleportCost=20. The
# cost differential test pins TeleportAction.cost == 20.0; perturbing the constant
# flips that assertion (gives the const-cost contract teeth on the new action).
TELEPORT_COST_MUTATIONS = [
    (
        "teleport-cost: perturb flat warp cost (20.0 -> 21.0)",
        "TELEPORT_COST: float = 20.0",
        "TELEPORT_COST: float = 21.0",
    ),
]


# PLAN #6a: heal-supply maintenance. The floor comparison and the combat-active
# gate are the load-bearing predicates; each mutation flips a unit-test verdict.
CONSUMABLE_SUPPLY_MUTATIONS = [
    (
        "consumable_supply: stock floor >= becomes > (stock == floor wrongly re-fires)",
        "    if heal_stock(state, game_data) >= HEAL_STOCK_FLOOR:\n        return False",
        "    if heal_stock(state, game_data) > HEAL_STOCK_FLOOR:\n        return False",
    ),
    (
        "consumable_supply: weaker-heal filter < becomes <= (drops an equal-strength restock)",
        "        if stats.hp_restore < floor_restore:\n            continue",
        "        if stats.hp_restore <= floor_restore:\n            continue",
    ),
]


MEANS_MAINTAIN_MUTATIONS = [
    (
        "means: MAINTAIN_CONSUMABLES drops the combat-active gate (fires when idle)",
        "        if ctx.combat_monster is None:\n            return False\n        return maintain_consumables_fires(state, game_data)",
        "        return maintain_consumables_fires(state, game_data)",
    ),
]


# O5.4 Brick 5 — ladder firing-predicate mutations. These perturb the NUMERIC
# thresholds / comparators / structural conjuncts of the guard- and means-tier
# `_fires` predicates (tiers/guards.py + tiers/means.py). They are killed by
# formal/diff/test_ladder_fires_diff.py, which binds the Lean
# `Formal.Liveness.ProductionLadder.fires`/`productionLadder` (via the
# `ladder_fires` oracle) to these SAME `_fires` predicates through the
# real-import bridge formal/sim/production_ladder.py — the exact defs the
# liveness theorems (NoDeadlock, FightFairness, BootstrapReach, the level-50
# capstone) reason over. A surviving mutant here means the Brick-4 differential
# is vacuous on that predicate (the boundary witnesses don't pin the threshold).
#
# Only mutation-MEANINGFUL slots are targeted: the opaque passthrough slots
# (craftRelief/gearReview/maintainConsumables/recycleSurplus and the
# history-gated phase slots) carry no threshold in the firing predicate itself —
# their firing is computed by separate machinery (craft_relief_candidates,
# task_decision, low_yield_cancel_fires, …) already anchored elsewhere.
LADDER_GUARD_FIRES_MUTATIONS = [
    (
        "ladder/guards: HP_CRITICAL comparator < -> <= (boundary 25/100 leaks)",
        "        return state.hp_percent < CRITICAL_HP_FRACTION",
        "        return state.hp_percent <= CRITICAL_HP_FRACTION",
    ),
    (
        "ladder/guards: HP_CRITICAL threshold 0.25 -> 0.50 (widens critical band)",
        "CRITICAL_HP_FRACTION = 0.25",
        "CRITICAL_HP_FRACTION = 0.50",
    ),
    (
        "ladder/guards: BANK_UNLOCK xp-gate > -> >= (fires when xp == initial_xp)",
        "        if state.xp > ctx.initial_xp:",
        "        if state.xp >= ctx.initial_xp:",
    ),
    (
        "ladder/guards: BANK_UNLOCK level-margin -1 dropped (level >= target)",
        "        return target_level == 0 or state.level >= target_level - 1",
        "        return target_level == 0 or state.level >= target_level",
    ),
    (
        "ladder/guards: REACH_UNLOCK_LEVEL gap comparator <= -> < (boundary gap 5 leaks)",
        "                and ctx.bank_required_level - state.level <= MAX_ACHIEVABLE_GAP)",
        "                and ctx.bank_required_level - state.level < MAX_ACHIEVABLE_GAP)",
    ),
    (
        "ladder/guards: REACH_UNLOCK_LEVEL gap constant 5 -> 50 (always achievable)",
        "MAX_ACHIEVABLE_GAP = 5",
        "MAX_ACHIEVABLE_GAP = 50",
    ),
    (
        "ladder/guards: DISCARD_CRITICAL fill comparator >= -> > (boundary 0.95 leaks)",
        "                and _used_fraction(state) >= DISCARD_CRITICAL_FRACTION)",
        "                and _used_fraction(state) > DISCARD_CRITICAL_FRACTION)",
    ),
    (
        "ladder/guards: DISCARD_CRITICAL threshold 0.95 -> 0.85 (fires too early)",
        "DISCARD_CRITICAL_FRACTION = 0.95",
        "DISCARD_CRITICAL_FRACTION = 0.85",
    ),
    (
        "ladder/guards: DEPOSIT_FULL fill comparator >= -> > (boundary 0.90 leaks)",
        "                and _used_fraction(state) >= DEPOSIT_FULL_FRACTION\n"
        "                and bool(select_bank_deposits(",
        "                and _used_fraction(state) > DEPOSIT_FULL_FRACTION\n"
        "                and bool(select_bank_deposits(",
    ),
    (
        "ladder/guards: DEPOSIT_FULL threshold 0.90 -> 0.85 (fires at discard ramp)",
        "DEPOSIT_FULL_FRACTION = 0.90",
        "DEPOSIT_FULL_FRACTION = 0.85",
    ),
    (
        "ladder/guards: DISCARD_HIGH fill comparator >= -> > (boundary 0.85 leaks)",
        "                and _used_fraction(state) >= DISCARD_HIGH_FRACTION)",
        "                and _used_fraction(state) > DISCARD_HIGH_FRACTION)",
    ),
    (
        "ladder/guards: DISCARD_HIGH threshold 0.85 -> 0.95 (fires too late)",
        "DISCARD_HIGH_FRACTION = 0.85",
        "DISCARD_HIGH_FRACTION = 0.95",
    ),
]


LADDER_MEANS_FIRES_MUTATIONS = [
    (
        "ladder/means: COMPLETE_TASK progress comparator >= -> > (boundary progress==total leaks)",
        "                and state.task_progress >= state.task_total)",
        "                and state.task_progress > state.task_total)",
    ),
    (
        "ladder/means: SELL_PRESSURED fill comparator >= -> > (boundary 0.85 leaks)",
        "        return _used_fraction(state) >= SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)",
        "        return _used_fraction(state) > SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)",
    ),
    (
        "ladder/means: SELL_PRESSURE_FRACTION 0.85 -> 0.95 (pressure boundary shifts)",
        "SELL_PRESSURE_FRACTION = 0.85",
        "SELL_PRESSURE_FRACTION = 0.95",
    ),
    (
        "ladder/means: TASK_EXCHANGE coin comparator >= -> > (boundary coins==min leaks)",
        "        return _tasks_coin_total(state) >= ctx.task_exchange_min_coins",
        "        return _tasks_coin_total(state) > ctx.task_exchange_min_coins",
    ),
    (
        "ladder/means: SELL_IDLE fill comparator < -> <= (boundary 0.85 leaks vs sellPressured)",
        "        return _used_fraction(state) < SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)",
        "        return _used_fraction(state) <= SELL_PRESSURE_FRACTION and _has_sellable(state, game_data)",
    ),
    (
        "ladder/means: BANK_EXPAND fill comparator < -> <= (boundary 0.95 leaks)",
        "        if fill < BANK_EXPAND_FILL:",
        "        if fill <= BANK_EXPAND_FILL:",
    ),
    (
        "ladder/means: BANK_EXPAND_FILL 0.95 -> 0.85 (fires too early)",
        "BANK_EXPAND_FILL = 0.95",
        "BANK_EXPAND_FILL = 0.85",
    ),
    (
        "ladder/means: BANK_EXPAND gold-gate >= -> > (boundary gold==cost leaks)",
        "        return state.gold >= game_data.next_expansion_cost",
        "        return state.gold > game_data.next_expansion_cost",
    ),
    (
        "ladder/means: DRAIN_BANK_JUNK fill comparator < -> <= (boundary 0.85 leaks)",
        "        return (_used_fraction(state) < SELL_PRESSURE_FRACTION\n"
        "                and bool(bank_drain_excess(",
        "        return (_used_fraction(state) <= SELL_PRESSURE_FRACTION\n"
        "                and bool(bank_drain_excess(",
    ),
    (
        "ladder/means: DRAIN_BANK_JUNK drop bank_drain_excess conjunct (fires on empty bank)",
        "                and bool(bank_drain_excess(\n"
        "                    state, game_data, ctx.target_gear | ctx.target_tools)))",
        "                and True)",
    ),
]


APPLY_FIGHT_MUTATIONS = [
    (
        "apply-baseline-fight: revert FightAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            xp=state.xp + 10,\n"
        "            hp=new_hp,\n"
        "            x=dest[0],\n"
        "            y=dest[1],\n"
        "            inventory=dict(inv.item_count),\n"
        "            cooldown_expires=None,\n"
        "            task_progress=new_progress,\n"
        "            task_lifecycle_phase=derive_task_lifecycle_phase(\n"
        "                state.task_code, new_progress, state.task_total\n"
        "            ),\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp + 10, max_xp=state.max_xp,\n"
        "            hp=new_hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=dest[0], y=dest[1],\n"
        "            inventory=state.inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=new_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "        )",
    ),
]


APPLY_BANK_EXPANSION_MUTATIONS = [
    (
        "apply-baseline-bank-expansion: revert BuyBankExpansionAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            gold=state.gold - game_data.next_expansion_cost,\n"
        "            x=dest[0],\n"
        "            y=dest[1],\n"
        "            cooldown_expires=None,\n"
        "            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp,\n"
        "            gold=state.gold - game_data.next_expansion_cost,\n"
        "            skills=state.skills, x=dest[0], y=dest[1],\n"
        "            inventory=state.inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=state.pending_items, active_events=state.active_events,\n"
        "            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,\n"
        "        )",
    ),
]


APPLY_CLAIM_MUTATIONS = [
    (
        "apply-baseline-claim: revert ClaimPendingItemAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            inventory=new_inventory,\n"
        "            cooldown_expires=None,\n"
        "            pending_items=remaining if remaining else None,\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp, gold=state.gold,\n"
        "            skills=state.skills, x=state.x, y=state.y,\n"
        "            inventory=new_inventory, inventory_max=state.inventory_max,\n"
        "            equipment=state.equipment, cooldown_expires=None,\n"
        "            task_code=state.task_code, task_type=state.task_type,\n"
        "            task_progress=state.task_progress, task_total=state.task_total,\n"
        "            bank_items=state.bank_items, bank_gold=state.bank_gold,\n"
        "            pending_items=remaining if remaining else None,\n"
        "            active_events=state.active_events,\n"
        "        )",
    ),
]


# projected_skill_xp_delta mutations -- the Phase-4 LevelSkillGoal predictability
# fix. Each mutant either (a) drops the GatherAction.apply delta update so the
# projected accumulator stays at 0 (LevelSkillGoal can never see plan-projected
# satisfaction), (b) flips the += into a -= (corrupts the delta), or (c) drops
# the projected-delta check in LevelSkillGoal.is_satisfied. Each killed by
# `formal/diff/test_apply_baseline_diff.py::test_gather_increments_projected_skill_xp_delta`
# (for a/b) or by the test_level_skill_goal projection tests (for c).
GATHERING_APPLY_MUTATIONS = [
    (
        "gathering.apply: drop projected_skill_xp_delta update (no XP accumulation)",
        "        new_delta = dict(state.projected_skill_xp_delta)\n"
        "        skill_req = game_data.resource_skill_level(self.resource_code)\n"
        "        if skill_req is not None:\n"
        "            skill_name, _ = skill_req\n"
        "            new_delta[skill_name] = new_delta.get(skill_name, 0) + 1",
        "        new_delta = dict(state.projected_skill_xp_delta)",
    ),
    (
        "gathering.apply: flip += to -= on projected delta",
        "            new_delta[skill_name] = new_delta.get(skill_name, 0) + 1",
        "            new_delta[skill_name] = new_delta.get(skill_name, 0) - 1",
    ),
]


LEVEL_SKILL_GOAL_MUTATIONS = [
    (
        "level_skill_goal.is_satisfied: drop projected-delta check (only skills snapshot path)",
        "        current_level = state.skills.get(self._skill_name, 0)\n"
        "        required = self._xp_curve.required_xp(current_level)\n"
        "        if required <= 0:\n"
        "            return False\n"
        "        current_xp = state.skill_xp.get(self._skill_name, 0)\n"
        "        projected = state.projected_skill_xp_delta.get(self._skill_name, 0)\n"
        "        return current_xp + projected >= required",
        "        return False",
    ),
]


# cost_core mutations -- old strings matched to current cost_core.py text.
# These attack the Phase-2 Dijkstra-optimality precondition: every
# Action.cost(...) must return ≥ 0. Each mutation breaks the non-negativity
# contract on at least one branch; the diff test kills them.
COST_CORE_MUTATIONS = [
    # distance_cost: flip the additive base + dist to subtraction. Any
    # `dist > base` produces a negative cost, breaking ≥ 0.
    ("cost_core: distance_cost_pure + -> -",
     "    return base + dist",
     "    return base - dist"),
    # qty_cost: flip the per_unit*qty term to subtraction. With base=0 and
    # qty >= 1, the result is negative.
    ("cost_core: qty_cost_pure base + per_unit*qty + dist -> base - per_unit*qty + dist",
     "    return base + per_unit * qty + dist",
     "    return base - per_unit * qty + dist"),
    # learned_cost: drop the max(rate, rate_floor) clamp. When rate <= 0 (a
    # writer-invariant corner), the divisor is zero or negative — the
    # learned-fraction branch returns NaN/-inf, breaking the assertion in
    # `test_learned_cost_pure_nonneg`.
    ("cost_core: learned_cost_pure drop max() rate_floor clamp",
     "        return learned / max(rate, rate_floor)",
     "        return learned / rate if rate != 0 else float('-inf')"),
]


# inventory_chain_safe mutations — REAL BUGS #7-#11. Each resurrects the bug
# by dropping the precondition, flipping the boundary, or dropping the apply
# assert / coin decrement. Killed by
# `formal/diff/test_inventory_chain_safe_diff.py`.
WITHDRAW_ITEM_MUTATIONS = [
    # Drop the slot-floor check: resurrects REAL BUG #7 (pre-fix >0). The
    # regression-pin (used=9 cap=10 qty=5) fires.
    ("withdraw_item: drop inventory_free check",
     "        return (\n"
     "            state.bank_items.get(self.code, 0) >= self.quantity\n"
     "            and state.inventory_free >= self.quantity\n"
     "        )",
     "        return state.bank_items.get(self.code, 0) >= self.quantity"),
    # Off-by-one: flip >= to > on the slot floor.
    ("withdraw_item: flip >= to > on inventory_free check",
     "            and state.inventory_free >= self.quantity",
     "            and state.inventory_free > self.quantity"),
    # Drop the apply assert: even if is_applicable is correct, the planner
    # could (incorrectly) call apply without going through it; the assert is
    # the chain_safe defense. The diff test exercises apply via is_applicable,
    # so dropping the assert alone wouldn't fail an oracle-agreement test
    # — but the diff's `post.inventory_used <= post.inventory_max` invariant
    # still holds because is_applicable is unchanged. We instead loosen the
    # is_applicable AND drop the assert in one mutation, mirroring NpcBuy.
    ("withdraw_item: weaken is_applicable to >= 1 only",
     "            and state.inventory_free >= self.quantity",
     "            and state.inventory_free >= 1"),
]

CLAIM_MUTATIONS = [
    # Drop the slot-floor check: resurrects REAL BUG #8.
    ("claim: drop inventory_free >= 1 check",
     "        if not state.pending_items:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return bool(state.pending_items)"),
    # Flip >= to > on the slot floor (off-by-one): full bag still rejected,
    # but exactly-one-free slot is now wrongly refused. The boundary test
    # `test_claim_boundary_one_free_slot_accepted` fires.
    ("claim: flip >= to > on inventory_free check",
     "        return state.inventory_free >= 1",
     "        return state.inventory_free > 1"),
    # Drop the apply assert. The diff test's post-state invariant on apply
    # passes under the unchanged is_applicable, so we couple this with a
    # loosened precondition: drop the pending-items guard too.
    ("claim: drop pending_items guard",
     "        if not state.pending_items:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return state.inventory_free >= 1"),
]

UNEQUIP_MUTATIONS = [
    # Drop the slot-floor check: resurrects REAL BUG #9.
    ("unequip: drop inventory_free >= 1 check",
     "        if state.equipment.get(self.slot) is None:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return state.equipment.get(self.slot) is not None"),
    # Flip >= to > on the slot floor (off-by-one).
    ("unequip: flip >= to > on inventory_free check",
     "        return state.inventory_free >= 1",
     "        return state.inventory_free > 1"),
    # Drop the slot-non-empty guard: empty slot now wrongly applicable.
    ("unequip: drop slot-non-empty guard",
     "        if state.equipment.get(self.slot) is None:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return state.inventory_free >= 1"),
]

TASK_EXCHANGE_MUTATIONS = [
    # Drop the slot-floor check: resurrects REAL BUG #10.
    ("task_exchange: drop inventory_free >= 1 check",
     "        if state.inventory.get(TASKS_COIN_CODE, 0) < self.min_coins:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return state.inventory.get(TASKS_COIN_CODE, 0) >= self.min_coins"),
    # Flip >= to > on the slot floor (off-by-one).
    ("task_exchange: flip >= to > on inventory_free check",
     "        return state.inventory_free >= 1",
     "        return state.inventory_free > 1"),
    # Drop the coin gate.
    ("task_exchange: drop coin gate",
     "        if state.inventory.get(TASKS_COIN_CODE, 0) < self.min_coins:\n"
     "            return False\n"
     "        return state.inventory_free >= 1",
     "        return state.inventory_free >= 1"),
]

TASK_CANCEL_MUTATIONS = [
    # Drop the coin check: resurrects REAL BUG #11 (pre-fix is_applicable).
    ("task_cancel: drop coin check in is_applicable",
     "        if not state.task_code or state.task_total <= 0:\n"
     "            return False\n"
     "        return state.inventory.get(TASKS_COIN_CODE, 0) >= 1",
     "        return bool(state.task_code) and state.task_total > 0"),
    # Off-by-one: require 2 coins instead of 1.
    ("task_cancel: require 2 coins instead of 1",
     "        return state.inventory.get(TASKS_COIN_CODE, 0) >= 1",
     "        return state.inventory.get(TASKS_COIN_CODE, 0) >= 2"),
    # Drop the coin decrement in apply: post-state still shows full coin count.
    ("task_cancel: drop coin decrement in apply",
     "        new_inventory = dict(state.inventory)\n"
     "        remaining = new_inventory.get(TASKS_COIN_CODE, 0) - 1\n"
     "        if remaining <= 0:\n"
     "            new_inventory.pop(TASKS_COIN_CODE, None)\n"
     "        else:\n"
     "            new_inventory[TASKS_COIN_CODE] = remaining\n"
     "        return dataclasses.replace(\n"
     "            state,\n"
     "            x=dest[0],\n"
     "            y=dest[1],\n"
     "            inventory=new_inventory,\n"
     "            cooldown_expires=None,\n"
     "            task_code=None,\n"
     "            task_type=None,\n"
     "            task_progress=0,\n"
     "            task_total=0,\n"
     "            task_lifecycle_phase=TaskLifecyclePhase.NONE,\n"
     "        )",
     "        return dataclasses.replace(\n"
     "            state,\n"
     "            x=dest[0],\n"
     "            y=dest[1],\n"
     "            cooldown_expires=None,\n"
     "            task_code=None,\n"
     "            task_type=None,\n"
     "            task_progress=0,\n"
     "            task_total=0,\n"
     "            task_lifecycle_phase=TaskLifecyclePhase.NONE,\n"
     "        )"),
]


# Phase-17 mutations — scalar_yield wired through clamp_into_band.
# Each mutant violates a band-safety property that test_goal_value_band_safety_diff
# pins (survival-floor strict-below, band inclusion, or warm-path lift).
PURSUE_TASK_MUTATIONS = [
    # Removing clamp_into_band: returns floor + raw bonus (unclamped). Kills via
    # `test_pursue_task_high_yield_clamps_at_ceiling` (bonus from char_xp=10000,
    # level=40 lifts the result well above SURVIVAL_FLOOR=70).
    ("pursue_task: drop clamp_into_band (returns raw floor + bonus)",
     "        clamped = clamp_into_band(Fraction(PRIORITY_FLOOR), Fraction(PRIORITY_CEILING), bonus)\n"
     "        return float(clamped)",
     "        return float(Fraction(PRIORITY_FLOOR) + bonus)"),
    # Lifting the ceiling above the survival floor — Phase-1 invariant violation.
    # `test_pursue_task_constants_match_lean` asserts PRIORITY_CEILING == 50.0,
    # which this mutation flips. Also caught by the high-yield survival test.
    ("pursue_task: PRIORITY_CEILING = 100 (above survival floor 70)",
     "PRIORITY_CEILING = 50.0",
     "PRIORITY_CEILING = 100.0"),
]
GATHER_MATERIALS_BAND_MUTATIONS = [
    # Removing clamp_into_band: returns the un-clamped bonus + floor, which at
    # extreme yields exceeds the survival floor. Caught by
    # `test_gather_materials_high_yield_clamps_below_survival`.
    ("gathering: drop clamp_into_band on Phase-17 wiring",
     "        clamped = clamp_into_band(\n"
     "            Fraction(PRIORITY_FLOOR), Fraction(PRIORITY_CEILING), total_bonus,\n"
     "        )\n"
     "        return float(clamped)",
     "        return float(Fraction(PRIORITY_FLOOR) + total_bonus)"),
    # Lifting the ceiling above the survival floor — caught by the constants
    # test and the extreme-yield test.
    ("gathering: PRIORITY_CEILING = 100 (above survival floor 70)",
     "PRIORITY_CEILING = 50.0",
     "PRIORITY_CEILING = 100.0"),
]
SCALAR_PRIORITY_MUTATIONS = [
    # Negating the bonus: a positive yield becomes a negative bonus, suppressing
    # priority below the floor (and after clamp, glueing it to the floor). The
    # warm-path-lift test (yield should lift above floor) kills this.
    ("scalar_priority: negate the yield bonus (flip sign)",
     "    return Fraction(lifted) * Fraction(BAND_GAIN)",
     "    return -(Fraction(lifted) * Fraction(BAND_GAIN))"),
]


# Phase-7 mutations.
# Target A: GatherMaterialsGoal._compute_base_value div-by-zero guard.
GATHERING_GOAL_MUTATIONS = [
    ("gathering: drop totalNeeded<=0 guard (resurrects div-by-zero)",
     "        if total_needed <= 0:\n"
     "            return 0.0\n",
     ""),
    ("gathering: flip <= to < on totalNeeded guard (off-by-one)",
     "        if total_needed <= 0:",
     "        if total_needed < 0:"),
]
# Target D: EquipAction.is_applicable slot/type gate.
EQUIP_MUTATIONS = [
    ("equip: drop slot/type membership check (resurrects mismatch bug)",
     "        if self.slot not in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):\n"
     "            return False\n",
     ""),
    ("equip: invert slot/type check (use 'in' instead of 'not in')",
     "        if self.slot not in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):",
     "        if self.slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, []):"),
    # Drop the code-already-worn gate: resurrects the 2026-06-10 Robby
    # utility2 livelock (second copy of a worn consumable plans into the
    # empty sibling slot, the server 485s, the plan re-derives forever).
    # Killed by test_equip_code_worn_elsewhere_refused (utility).
    ("equip: drop code-already-worn gate (resurrects 485 utility2 livelock)",
     "        if stats.type_ not in DUPLICATE_SLOT_TYPES and any(\n"
     "            equipped == self.code\n"
     "            for slot, equipped in state.equipment.items()\n"
     "            if slot != self.slot\n"
     "        ):\n"
     "            return False\n",
     ""),
    # Key the gate on sibling-slot OCCUPANCY instead of item code: any worn
    # item in another slot would block the equip, outlawing the legal
    # two-different-consumables loadout the gate's comment promises.
    # Killed by test_equip_different_code_sibling_accepted.
    ("equip: worn gate keys on slot occupancy instead of code",
     "            equipped == self.code\n"
     "            for slot, equipped in state.equipment.items()",
     "            equipped is not None\n"
     "            for slot, equipped in state.equipment.items()"),
    # Drop the RINGS carve-out: re-apply the worn gate to ALL types, so a
    # legal 2nd ring (server HTTP 200) is wrongly refused — resurrects the
    # inert dual-ring bug. Killed by test_equip_ring_worn_elsewhere_with_spare_accepted.
    ("equip: drop rings carve-out (worn gate fires for all types)",
     "        if stats.type_ not in DUPLICATE_SLOT_TYPES and any(\n"
     "            equipped == self.code\n",
     "        if any(\n"
     "            equipped == self.code\n"),
]
# Target F: store_warmup_core warmup gates.
STORE_WARMUP_MUTATIONS = [
    ("store_warmup: drop median warmup gate (< 5 ⇒ should return None)",
     "    if len(samples) < WARMUP_MIN_SAMPLES:\n"
     "        return None\n",
     ""),
    ("store_warmup: flip < to <= on median gate (off-by-one)",
     "    if len(samples) < WARMUP_MIN_SAMPLES:",
     "    if len(samples) <= WARMUP_MIN_SAMPLES:"),
    ("store_warmup: drop success_rate warmup gate (< 5 ⇒ should return 1.0)",
     "    if len(outcomes) < WARMUP_MIN_SAMPLES:\n"
     "        return 1.0\n",
     ""),
    ("store_warmup: change default to 0.0 on success_rate gate",
     "    if len(outcomes) < WARMUP_MIN_SAMPLES:\n"
     "        return 1.0",
     "    if len(outcomes) < WARMUP_MIN_SAMPLES:\n"
     "        return 0.0"),
]


# game_data accessor mutations -- REAL BUG #16. Each resurrects the
# silent-default pattern on one of the five raise-accessors, or inverts the
# raise/return logic. Killed by formal/diff/test_game_data_accessors_diff.py.
GAME_DATA_MUTATIONS = [
    # The accessors moved to MonsterCatalog (game_data.py delegates); the
    # silent-default resurrections now target monster_catalog.py and remain
    # observable through the GameData facade the diff test exercises.
    # Mutation 1: resurrect silent {} default on monster_attack.
    ("game_data: monster_attack silent {} default resurrected",
     "        return self.attack[code]",
     "        return self.attack.get(code, {})"),
    # Mutation 2: resurrect silent 0 default on monster_hp.
    ("game_data: monster_hp silent 0 default resurrected",
     "        return self.hp[code]",
     "        return self.hp.get(code, 0)"),
    # Mutation 3: invert monster_initiative — silently return absent codes as 9999.
    ("game_data: monster_initiative inverted (silent 9999 default)",
     "        return self.initiative[code]",
     "        return self.initiative.get(code, 9999)"),
]


def _assert_sources_clean() -> None:
    """Abort if any mutation target is already dirty in git. The runner mutates
    production source in place and restores it in `finally`; a previous run killed
    mid-mutation could leave a target mutated. Refusing to start on a dirty target
    prevents compounding a leaked mutation (or letting one ship unnoticed)."""
    rels = [str(p.relative_to(ROOT)) for p in _ALL_SRCS]
    rc = subprocess.run(["git", "diff", "--quiet", "--", *rels], cwd=ROOT).returncode
    if rc != 0:
        dirty = subprocess.run(["git", "diff", "--name-only", "--", *rels],
                               cwd=ROOT, capture_output=True, text=True).stdout.strip()
        print("MUTATION GATE ABORT: target source(s) already dirty — a prior "
              f"mutation run may have left a mutation in place:\n{dirty}\n"
              "Run `git checkout -- <files>` and retry.")
        sys.exit(2)


def _lock_pid_alive(pid: int) -> bool:
    """Signal-0 probe: ProcessLookupError = dead, PermissionError = alive
    (exists, owned by someone else)."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _acquire_mutation_lock() -> None:
    """Take the repo-root mutation lock (pid + ISO timestamp) for this run.

    An existing lock with a live pid means a second concurrent mutation run —
    abort (runs must be serialized: racing runs leak mutations into production
    source). A lock whose pid is dead or unreadable is stale debris from a
    killed run: warn, remove, continue.
    """
    if MUTATION_LOCKFILE.exists():
        tokens = MUTATION_LOCKFILE.read_text().split()
        pid = int(tokens[0]) if tokens and tokens[0].isdigit() and int(tokens[0]) > 0 else None
        if pid is not None and _lock_pid_alive(pid):
            print(f"MUTATION GATE ABORT: another mutation run is active (pid {pid}, "
                  f"lock {MUTATION_LOCKFILE}). Mutation runs must be serialized — "
                  "retry after it finishes.")
            sys.exit(2)
        print(f"WARNING: stale mutation lockfile {MUTATION_LOCKFILE} (pid={pid}, "
              "not running) — removing and continuing.")
        MUTATION_LOCKFILE.unlink()
    MUTATION_LOCKFILE.write_text(f"{os.getpid()}\n{datetime.now(UTC).isoformat()}\n")


# Phase-18 mutations — each must be killed by formal/diff/test_goal_system_value_diff.py.

ACCEPT_TASK_GOAL_MUTATIONS = [
    # 20 -> 200 (breaks discretionary band claim — value would escape its band).
    ("accept_task: return 20.0 -> 200.0",
     "        return 20.0",
     "        return 200.0"),
]

CLAIM_PENDING_GOAL_MUTATIONS = [
    ("claim_pending: return 25.0 -> 250.0",
     "        return 25.0",
     "        return 250.0"),
]

TASK_EXCHANGE_GOAL_MUTATIONS = [
    ("task_exchange: return 22.0 -> 220.0",
     "        return 22.0",
     "        return 220.0"),
    # Revert one-batch satisfaction to the pre-fix drain-ALL-coins reading —
    # resurrects the P1 planner-timeout storm (killed by
    # test_task_exchange_one_batch_boundary_matches_model).
    ("task_exchange: revert one-batch is_satisfied to drain-all",
     "        return tasks_coin_total(state) <= max(0, self._initial_total - self._min_coins)",
     "        return tasks_coin_total(state) < self._min_coins"),
    # Off-by-one on the one-batch boundary: exactly min_coins spent would no
    # longer satisfy (killed by the s_exact boundary case in
    # test_task_exchange_one_batch_boundary_matches_model).
    ("task_exchange: flip <= to < on one-batch satisfaction",
     "        return tasks_coin_total(state) <= max(0, self._initial_total - self._min_coins)",
     "        return tasks_coin_total(state) < max(0, self._initial_total - self._min_coins)"),
]

TASK_CANCEL_GOAL_MUTATIONS = [
    ("task_cancel: return 12.0 if PIVOT -> 120.0",
     "        return 12.0 if task_decision(state, game_data, history) == PIVOT else 0.0",
     "        return 120.0 if task_decision(state, game_data, history) == PIVOT else 0.0"),
]

COMPLETE_TASK_GOAL_MUTATIONS = [
    ("complete_task: return 90.0 -> 900.0",
     "        return 90.0",
     "        return 900.0"),
]

REACH_UNLOCK_LEVEL_GOAL_MUTATIONS = [
    # Drop the MAX_ACHIEVABLE_GAP unreachable-gap guard — goal fires on any gap.
    ("reach_unlock_level: drop MAX_ACHIEVABLE_GAP guard",
     "        if self._target_level - state.level > MAX_ACHIEVABLE_GAP:\n"
     "            return 0.0\n",
     ""),
]

LOW_YIELD_CANCEL_GOAL_MUTATIONS = [
    # 70 -> 700: breaks the priority band claim.
    ("low_yield_cancel: LOW_YIELD_CANCEL = 70.0 -> 700.0",
     "LOW_YIELD_CANCEL = 70.0",
     "LOW_YIELD_CANCEL = 700.0"),
]

UNLOCK_BANK_GOAL_MUTATIONS = [
    # 90 -> 900 active-branch return.
    ("unlock_bank: return 90.0 -> 900.0",
     "        return 90.0",
     "        return 900.0"),
]

DISCARD_OVERSTOCK_GOAL_MUTATIONS = [
    # Swap CRITICAL and BASE constants (reorders pressure tiers).
    ("discard_overstock: swap CRITICAL and BASE constants",
     "_DISCARD_OVERSTOCK_BASE = 40.0\n"
     "# High-pressure tier (inventory > 85%): above GATHER_MATERIALS so we preempt gather.\n"
     "_DISCARD_OVERSTOCK_HIGH_PRESSURE = 55.0\n"
     "# Critical tier (inventory > 95%): above DEPOSIT_FULL (80), below COMPLETE_TASK (90).\n"
     "_DISCARD_OVERSTOCK_CRITICAL = 85.0",
     "_DISCARD_OVERSTOCK_BASE = 85.0\n"
     "# High-pressure tier (inventory > 85%): above GATHER_MATERIALS so we preempt gather.\n"
     "_DISCARD_OVERSTOCK_HIGH_PRESSURE = 55.0\n"
     "# Critical tier (inventory > 95%): above DEPOSIT_FULL (80), below COMPLETE_TASK (90).\n"
     "_DISCARD_OVERSTOCK_CRITICAL = 40.0"),
]

PROGRESSION_GOAL_MUTATIONS = [
    # Relevant-tool branch returns 500 (over-priority — breaks 51 band claim).
    ("progression: _UPGRADE_EQUIPMENT_RELEVANT_TOOL = 51.0 -> 500.0",
     "_UPGRADE_EQUIPMENT_RELEVANT_TOOL = 51.0",
     "_UPGRADE_EQUIPMENT_RELEVANT_TOOL = 500.0"),
]

RESTORE_HP_GOAL_MUTATIONS = [
    # Drop the (1 - hp_percent) translation: raw hp_percent * 100 — wrong direction.
    ("restore_hp: drop (1 - hp_percent) translation",
     "        return (1.0 - state.hp_percent) * 100.0",
     "        return state.hp_percent * 100.0"),
]

DEPOSIT_INVENTORY_GOAL_MUTATIONS = [
    # _MAX_VALUE 80 -> 800 (overshoots the [0,80] band).
    ("deposit_inventory: _MAX_VALUE = 80.0 -> 800.0",
     "    _MAX_VALUE = 80.0   # value at 100% used; outranks FarmItems(35) once near cap",
     "    _MAX_VALUE = 800.0   # value at 100% used; outranks FarmItems(35) once near cap"),
]

SELL_INVENTORY_GOAL_MUTATIONS = [
    # SEIZE_WINDOW_VALUE 60 -> 600 (breaks band claim).
    ("sell_inventory: SEIZE_WINDOW_VALUE = 60.0 -> 600.0",
     "SEIZE_WINDOW_VALUE = 60.0",
     "SEIZE_WINDOW_VALUE = 600.0"),
]


LIVENESS_MEASURE_MUTATIONS = [
    # Drop the hpDeficit slot from the lex tuple — slot 6 vanishes, so Rest
    # (which only moves slot 6) is no longer detectable as a strict decrease,
    # and the Rest-after-Fight cycles in the differential surface as "equal"
    # (regression: a Rest cycle that should decrease no longer does).
    ("liveness measure: drop hpDeficit slot from lex tuple",
     "        return (self.level_deficit, self.xp_deficit, self.task_cycles,\n"
     "                self.skill_xp_deficit_projected, self.bank_pressure,\n"
     "                self.hp_deficit)",
     "        return (self.level_deficit, self.xp_deficit, self.task_cycles,\n"
     "                self.skill_xp_deficit_projected, self.bank_pressure)"),
    # Invert lex direction — `<` becomes `>`. Every productive cycle then
    # registers as a REGRESSION because the comparator is reversed.
    ("liveness measure: invert lex direction (< -> >)",
     "    return a.as_tuple() < b.as_tuple()",
     "    return a.as_tuple() > b.as_tuple()"),
]

LIVENESS_GATHERING_MUTATIONS = [
    # Negate the projected_skill_xp_delta increment: +1 -> 0. Gather no
    # longer advances slot 4, so a productive Gather cycle (when no other
    # slot moves) registers as "equal", and the planner-side state diverges
    # from FakeServer's measure tuple — the differential fires twice.
    ("liveness gathering: skill-delta +1 -> +0",
     "            new_delta[skill_name] = new_delta.get(skill_name, 0) + 1",
     "            new_delta[skill_name] = new_delta.get(skill_name, 0) + 0"),
]

# Phase 21d-2 — `_build_actions` mutations. Each drops a specific Action
# class from the canonical action menu. The body moved verbatim to
# `actions/factory.py::build_actions` (GamePlayer._build_actions delegates),
# so the mutations target the factory; the plan-exists differential
# (formal/diff/test_plan_exists_diff.py) must kill each by reporting a
# real production bug (planner returns empty plan for a firing means).
PLAN_EXISTS_BUILD_ACTIONS_MUTATIONS = [
    # Drop RestAction from the menu — HP_CRITICAL case loses its single-step
    # witness; planner returns []; test_planner_finds_plan_for_firing_means[
    # HP_CRITICAL] fires.
    ("plan_exists: drop RestAction from _build_actions",
     "    actions: list[Action] = [\n"
     "        RestAction(),",
     "    actions: list[Action] = [\n"
     "        # RestAction(),  # mutation: dropped",),
    # Drop DepositAllAction — DEPOSIT_FULL case has no actuator; planner
    # returns []; test_planner_finds_plan_for_firing_means[DEPOSIT_FULL] fires.
    ("plan_exists: drop DepositAllAction from _build_actions",
     "        DepositAllAction(bank_location=bank, accessible=bank_accessible, game_data=game_data),",
     "        # DepositAllAction(...),  # mutation: dropped"),
    # Drop FightAction construction — BANK_UNLOCK case has no combat
    # actuator; planner returns []; test_planner_finds_plan_for_firing_means[
    # BANK_UNLOCK] fires (the only fight-rooted in-scope means).
    ("plan_exists: drop FightAction from _build_actions",
     "        actions.append(FightAction(monster_code=monster_code, locations=frozenset(locs)))",
     "        pass  # mutation: dropped FightAction append"),
    # Disable the items-task TaskTradeAction insertion block (BOTH the
    # quantity=k primary and the quantity=1 fallback). PURSUE_TASK then has
    # no trade actuator; planner returns []; test_planner_finds_plan_for_firing_means[
    # PURSUE_TASK] fires. The shorter mutation (dropping only the quantity=k
    # line) was a SURVIVOR — the quantity=1 fallback alone is enough for the
    # planner to find a TaskTrade plan, so the mutation must remove both.
    ("plan_exists: disable items-task TaskTradeAction block",
     '    if state is not None and state.task_type == "items" and state.task_code:',
     '    if False and state is not None and state.task_type == "items" and state.task_code:'),
]


CYCLE_STEP_MUTATIONS = [
    # M1: swap .rest for .fight in planFor for HP_CRITICAL.
    # The mirror would now apply FightAction's projection (xp +=10) where
    # production correctly applies RestAction (hp := max_hp). The projection
    # differential on HP_CRITICAL diverges on `xp` AND on `hp` (we don't
    # track hp; xp suffices). test_cycle_step_projection_matches_production[
    # HP_CRITICAL] fires.
    ("cycle_step: swap .rest for .fight in planFor[HP_CRITICAL]",
     '    LadderMeans.HP_CRITICAL:        "rest",',
     '    LadderMeans.HP_CRITICAL:        "fight",'),
    # M2: drop the WAIT handling in apply_action_kind_mirror — make wait
    # advance xp by 10 (steal the .fight branch's xp grant). On WAIT, the
    # mirror now thinks xp went up; production WaitAction.apply is identity.
    # test_hypothesis_wait_cycle_byte_equivalent fires (300 Hypothesis-
    # sampled WAIT states see mirror_proj.xp = prod_proj.xp + 10).
    ("cycle_step: wait advances xp (mirror drops WAIT identity)",
     '    if action == "wait":\n        return s\n',
     '    if action == "wait":\n        return dataclasses.replace(s, xp=s.xp + 10)\n'),
    # M3: skip a tier in MIRROR_LADDER_ORDER — drop HP_CRITICAL. On the
    # HP_CRITICAL fixture the mirror now falls through to ACCEPT_TASK
    # (no task in fixture) instead of HP_CRITICAL. Production still picks
    # HP_CRITICAL. test_mirror_picks_same_means_as_production[HP_CRITICAL]
    # fires.
    ("cycle_step: skip HP_CRITICAL in MIRROR_LADDER_ORDER",
     "    LadderMeans.HP_CRITICAL,\n    LadderMeans.BANK_UNLOCK,",
     "    # LadderMeans.HP_CRITICAL,  # mutation: skipped tier\n    LadderMeans.BANK_UNLOCK,"),
    # M4: reverse MIRROR_LADDER_ORDER — WAIT now fires first on every state.
    # On HP_CRITICAL (and every other in-scope fixture) the mirror picks
    # WAIT; production picks the expected tier. The `is` check fires on
    # the very first fixture (HP_CRITICAL).
    ("cycle_step: reverse MIRROR_LADDER_ORDER (WAIT fires first)",
     "    for k in MIRROR_LADDER_ORDER:",
     "    for k in tuple(reversed(MIRROR_LADDER_ORDER)):"),
]


LIVENESS_REST_MUTATIONS = [
    # Drop the HP restoration entirely: `hp=state.max_hp` -> `hp=state.hp`.
    # Rest is then a no-op on slot 6; Fight cycles drain HP without it ever
    # being restored, and FakeServer's `rest` still heals to max — the
    # differential sees the measure mismatch + lex non-decrease.
    ("liveness rest: drop hp restoration (max_hp -> hp)",
     "        return dataclasses.replace(state, hp=state.max_hp, cooldown_expires=None)",
     "        return dataclasses.replace(state, hp=state.hp, cooldown_expires=None)"),
]


def main() -> int:
    _assert_sources_clean()
    _acquire_mutation_lock()
    try:
        return _run_all_groups()
    finally:
        # Always release the interlock, even on a crashed/killed-with-traceback
        # run, so a dead lock never wedges `artifactsmmo play` startups.
        MUTATION_LOCKFILE.unlink(missing_ok=True)


def _run_all_groups() -> int:
    survivors: list[str] = []
    _UNITS.clear()
    run_group(SRC, MUTATIONS, "formal/diff/test_calculate_path_diff.py", survivors)
    run_group(TASK_BATCH_SRC, TASK_BATCH_MUTATIONS, "formal/diff/test_task_batch_diff.py", survivors)
    run_group(INVENTORY_CAPS_SRC, INVENTORY_CAPS_MUTATIONS,
              "formal/diff/test_inventory_caps_diff.py", survivors)
    run_group(INVENTORY_CAPS_SRC, INVENTORY_PROFILE_MUTATIONS,
              "formal/diff/test_inventory_profile_diff.py", survivors)
    run_group(ACCUMULATION_SELL_SRC, ACCUMULATION_SELL_MUTATIONS,
              "formal/diff/test_accumulation_sell_diff.py", survivors)
    run_group(DOMINANCE_PARETO_SRC, DOMINANCE_PARETO_MUTATIONS,
              "formal/diff/test_dominance_pareto_diff.py", survivors)
    run_group(COMBAT_SRC, PREDICT_WIN_MUTATIONS,
              "formal/diff/test_predict_win_diff.py", survivors)
    run_group(COMBAT_SRC, PREDICT_WIN_LIFESTEAL_MUTATIONS,
              "tests/test_ai/test_combat.py", survivors)
    run_group(PROJECTION_SRC, PROJECTION_MUTATIONS,
              "formal/diff/test_loadout_projection_diff.py", survivors)
    run_group(SCORING_SRC, SCORING_MUTATIONS,
              "formal/diff/test_equipment_scoring_diff.py", survivors)
    run_group(SCORING_SRC, REALIZABLE_LOADOUT_MUTATIONS,
              "formal/diff/test_realizable_loadout_diff.py", survivors)
    run_group(SKILL_XP_CURVE_SRC, SKILL_XP_CURVE_MUTATIONS,
              "formal/diff/test_skill_xp_curve_diff.py", survivors)
    run_group(SKILL_TARGET_CURVE_SRC, SKILL_TARGET_CURVE_MUTATIONS,
              "formal/diff/test_skill_target_curve_diff.py", survivors)
    run_group(SKILL_GRIND_SELECTION_SRC, SKILL_GRIND_SELECTION_MUTATIONS,
              "formal/diff/test_skill_grind_selection_diff.py", survivors)
    run_group(SKILL_STEP_DISPATCH_SRC, SKILL_STEP_DISPATCH_MUTATIONS,
              "formal/diff/test_skill_step_dispatch_diff.py", survivors)
    run_group(STRATEGIC_VALUE_SRC, STRATEGIC_VALUE_MUTATIONS,
              "formal/diff/test_strategic_value_diff.py", survivors)
    run_group(SKILL_STEP_DISPATCH_SRC, GRIND_LADDER_MUTATIONS,
              "formal/diff/test_grind_ladder_diff.py", survivors)
    run_group(RECIPE_CLOSURE_SRC, RECIPE_CLOSURE_MUTATIONS,
              "formal/diff/test_recipe_closure_diff.py", survivors)
    run_group(TASK_FEASIBILITY_SRC, TASK_FEASIBILITY_MUTATIONS,
              "formal/diff/test_task_feasibility_diff.py", survivors)
    run_group(PREREQUISITE_GRAPH_SRC, PREREQUISITE_GRAPH_MUTATIONS,
              "formal/diff/test_prerequisite_graph_diff.py", survivors)
    run_group(OBJECTIVE_SRC, OBJECTIVE_MUTATIONS,
              "formal/diff/test_objective_diff.py", survivors)
    run_group(STRATEGY_SRC, STRATEGY_MUTATIONS,
              "formal/diff/test_strategy_traversal_diff.py", survivors)
    run_group(STRATEGY_SRC, REACHABILITY_MUTATIONS,
              "formal/diff/test_reachability_diff.py", survivors)
    run_group(BANK_SELECTION_SRC, BANK_SELECTION_MUTATIONS,
              "formal/diff/test_bank_selection_diff.py", survivors)
    run_group(STUCK_DETECTOR_SRC, STUCK_DETECTOR_MUTATIONS,
              "formal/diff/test_stuck_detector_diff.py", survivors)
    run_group(PRIORITY_BAND_SRC, PRIORITY_BAND_MUTATIONS,
              "formal/diff/test_priority_band_diff.py", survivors)
    run_group(OWNED_COUNT_SRC, OWNED_COUNT_MUTATIONS,
              "formal/diff/test_owned_count_diff.py", survivors)
    run_group(UPGRADE_SELECTION_SRC, UPGRADE_SELECTION_MUTATIONS,
              "formal/diff/test_upgrade_selection_diff.py", survivors)
    run_group(SCALAR_CORE_SRC, SCALAR_CORE_MUTATIONS,
              "formal/diff/test_scalarizer_diff.py", survivors)
    run_group(PLANNER_SRC, PLANNER_MUTATIONS,
              "formal/diff/test_planner_admissibility_diff.py", survivors)
    run_group(ARBITER_SELECT_SRC, ARBITER_SELECT_MUTATIONS,
              "formal/diff/test_arbiter_select_diff.py", survivors)
    run_group(STICKY_SELECT_SRC, STICKY_SELECT_MUTATIONS,
              "formal/diff/test_sticky_select_diff.py", survivors)
    run_group(SERVABLE_FILTER_SRC, SERVABLE_FILTER_MUTATIONS,
              "formal/diff/test_servable_filter_diff.py", survivors)
    run_group(TASK_DECISION_CORE_SRC, TASK_DECISION_MUTATIONS,
              "formal/diff/test_task_decision_diff.py", survivors)
    run_group(OBJECTIVE_COMPLETION_SRC, WEIGHTED_REMAINING_MUTATIONS,
              "formal/diff/test_weighted_remaining_diff.py", survivors)
    run_group(LOW_YIELD_BOUNDARY_SRC, LOW_YIELD_MUTATIONS,
              "formal/diff/test_low_yield_cancel_diff.py", survivors)
    run_group(STRATEGY_BLEND_SRC, STRATEGY_BLEND_MUTATIONS,
              "formal/diff/test_strategy_blend_diff.py", survivors)
    run_group(DECIDE_KEY_SRC, DECIDE_KEY_MUTATIONS,
              "formal/diff/test_decide_key_diff.py", survivors)
    run_group(ROOT_PROGRESS_SRC, ROOT_PROGRESS_MUTATIONS,
              "formal/diff/test_obtain_progress_diff.py", survivors)
    run_group(PROGRESSION_RESERVE_CORE_SRC, PROGRESSION_RESERVE_MUTATIONS,
              "formal/diff/test_progression_reserve_diff.py", survivors)
    run_group(CYCLES_FOR_PROGRESS_SRC, CYCLES_FOR_PROGRESS_MUTATIONS,
              "formal/diff/test_cycles_for_progress_diff.py", survivors)
    run_group(GATHER_APPLY_SRC, GATHER_APPLY_MUTATIONS,
              "formal/diff/test_gather_apply_diff.py", survivors)
    run_group(GATHER_APPLY_SRC, MONSTER_DROP_APPLY_MUTATIONS,
              "formal/diff/test_monster_drop_apply_diff.py", survivors)
    run_group(GATHER_SELECTION_SRC, GATHER_SELECTION_MUTATIONS,
              "formal/diff/test_gather_selection_diff.py", survivors)
    run_group(SHOPPING_LIST_SRC, SHOPPING_LIST_MUTATIONS,
              "formal/diff/test_shopping_list_diff.py", survivors)
    run_group(MIN_GATHERS_SRC, MIN_GATHERS_MUTATIONS,
              "formal/diff/test_gather_step_target_diff.py", survivors)
    run_group(GATHER_STEP_TARGET_SRC, GATHER_STEP_TARGET_MUTATIONS,
              "formal/diff/test_gather_step_target_diff.py", survivors)
    run_group(MONSTER_DROP_SELECTION_SRC, MONSTER_DROP_SELECTION_MUTATIONS,
              "formal/diff/test_monster_drop_selection_diff.py", survivors)
    run_group(CRAFT_VS_BUY_SRC, CRAFT_VS_BUY_MUTATIONS,
              "formal/diff/test_craft_vs_buy_diff.py", survivors)
    run_group(LIQUIDATION_VENUE_SRC, LIQUIDATION_VENUE_MUTATIONS,
              "formal/diff/test_liquidation_venue_diff.py", survivors)
    run_group(BUY_SOURCE_VENUE_SRC, BUY_SOURCE_VENUE_MUTATIONS,
              "formal/diff/test_buy_source_venue_diff.py", survivors)
    run_group(NEAREST_TILE_SRC, NEAREST_TILE_MUTATIONS,
              "formal/diff/test_nearest_tile_diff.py", survivors)
    run_group(CONSUMABLE_SELECTION_SRC, CONSUMABLE_SELECTION_MUTATIONS,
              "formal/diff/test_consumable_selection_diff.py", survivors)
    run_group(BANK_EXPANSION_TIMING_SRC, BANK_EXPANSION_TIMING_MUTATIONS,
              "formal/diff/test_bank_expansion_timing_diff.py", survivors)
    run_group(EVENT_WINDOW_SRC, EVENT_WINDOW_MUTATIONS,
              "formal/diff/test_event_window_diff.py", survivors)
    run_group(COST_CORE_SRC, COST_CORE_MUTATIONS,
              "formal/diff/test_action_cost_nonneg_diff.py", survivors)
    run_group(NPC_BUY_CORE_SRC, NPC_BUY_MUTATIONS,
              "formal/diff/test_npc_buy_inventory_diff.py", survivors)
    run_group(TASK_TRADE_CORE_SRC, TASK_TRADE_CORE_MUTATIONS,
              "formal/diff/test_items_task_run_diff.py", survivors)
    run_group(APPLY_MOVE_SRC, APPLY_MOVE_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_EQUIP_SRC, APPLY_EQUIP_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_CLAIM_SRC, APPLY_CLAIM_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_REST_SRC, APPLY_REST_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_FIGHT_SRC, APPLY_FIGHT_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_BANK_EXPANSION_SRC, APPLY_BANK_EXPANSION_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_TELEPORT_SRC, APPLY_TELEPORT_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(APPLY_TELEPORT_SRC, TELEPORT_COST_MUTATIONS,
              "formal/diff/test_action_cost_nonneg_diff.py", survivors)
    run_group(CONSUMABLE_SUPPLY_SRC, CONSUMABLE_SUPPLY_MUTATIONS,
              "tests/test_ai/test_maintain_consumables.py", survivors)
    run_group(MEANS_SRC, MEANS_MAINTAIN_MUTATIONS,
              "tests/test_ai/test_maintain_consumables.py", survivors)
    # O5.4 Brick 5 — ladder firing-predicate threshold/comparator/conjunct
    # mutations, killed by the SELECT-side differential (binds the Lean ladder
    # to these `_fires` predicates through the ladder_fires oracle).
    run_group(GUARDS_SRC, LADDER_GUARD_FIRES_MUTATIONS,
              "formal/diff/test_ladder_fires_diff.py", survivors)
    run_group(MEANS_SRC, LADDER_MEANS_FIRES_MUTATIONS,
              "formal/diff/test_ladder_fires_diff.py", survivors)
    run_group(GATHERING_APPLY_SRC, GATHERING_APPLY_MUTATIONS,
              "formal/diff/test_apply_baseline_diff.py", survivors)
    run_group(LEVEL_SKILL_GOAL_SRC, LEVEL_SKILL_GOAL_MUTATIONS,
              "tests/test_ai/test_level_skill_goal.py", survivors)
    run_group(WITHDRAW_ITEM_SRC, WITHDRAW_ITEM_MUTATIONS,
              "formal/diff/test_inventory_chain_safe_diff.py", survivors)
    run_group(APPLY_CLAIM_SRC, CLAIM_MUTATIONS,
              "formal/diff/test_inventory_chain_safe_diff.py", survivors)
    run_group(UNEQUIP_SRC, UNEQUIP_MUTATIONS,
              "formal/diff/test_inventory_chain_safe_diff.py", survivors)
    run_group(TASK_EXCHANGE_SRC, TASK_EXCHANGE_MUTATIONS,
              "formal/diff/test_inventory_chain_safe_diff.py", survivors)
    run_group(TASK_CANCEL_SRC, TASK_CANCEL_MUTATIONS,
              "formal/diff/test_inventory_chain_safe_diff.py", survivors)
    run_group(GATHERING_GOAL_SRC, GATHERING_GOAL_MUTATIONS,
              "formal/diff/test_phase7_invariants_diff.py", survivors)
    run_group(EQUIP_SRC, EQUIP_MUTATIONS,
              "formal/diff/test_phase7_invariants_diff.py", survivors)
    run_group(STORE_WARMUP_SRC, STORE_WARMUP_MUTATIONS,
              "formal/diff/test_store_warmup_diff.py", survivors)
    run_group(BANK_EXPANSION_SRC, BANK_EXPANSION_MUTATIONS,
              "formal/diff/test_bank_expansion_diff.py", survivors)
    run_group(EXPAND_BANK_GOAL_SRC, EXPAND_BANK_GOAL_MUTATIONS,
              "tests/test_ai/test_goals_expand_bank.py", survivors)
    run_group(MONSTER_CATALOG_SRC, GAME_DATA_MUTATIONS,
              "formal/diff/test_game_data_accessors_diff.py", survivors)
    run_group(WINNABLE_CASCADE_SRC, WINNABLE_CASCADE_MUTATIONS,
              "formal/diff/test_winnable_cascade_diff.py", survivors)
    run_group(COMBAT_PICKER_SRC, COMBAT_PICKER_MUTATIONS,
              "formal/diff/test_combat_picker_diff.py", survivors)
    run_group(PROJECTIONS_SRC, CHEAPEST_PATH_MUTATIONS,
              "formal/diff/test_cheapest_path_diff.py", survivors)
    # Phase-17 — scalar_yield wired through clamp_into_band into discretionary goals.
    run_group(PURSUE_TASK_GOAL_SRC, PURSUE_TASK_MUTATIONS,
              "formal/diff/test_goal_value_band_safety_diff.py", survivors)
    run_group(GATHERING_GOAL_SRC, GATHER_MATERIALS_BAND_MUTATIONS,
              "formal/diff/test_goal_value_band_safety_diff.py", survivors)
    run_group(SCALAR_PRIORITY_SRC, SCALAR_PRIORITY_MUTATIONS,
              "formal/diff/test_goal_value_band_safety_diff.py", survivors)
    # Phase-18 mutation runs.
    run_group(ACCEPT_TASK_GOAL_SRC, ACCEPT_TASK_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(CLAIM_PENDING_GOAL_SRC, CLAIM_PENDING_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(TASK_EXCHANGE_GOAL_SRC, TASK_EXCHANGE_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(TASK_CANCEL_GOAL_SRC, TASK_CANCEL_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(COMPLETE_TASK_GOAL_SRC, COMPLETE_TASK_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(REACH_UNLOCK_LEVEL_GOAL_SRC, REACH_UNLOCK_LEVEL_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(LOW_YIELD_CANCEL_GOAL_SRC, LOW_YIELD_CANCEL_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(UNLOCK_BANK_GOAL_SRC, UNLOCK_BANK_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(DISCARD_OVERSTOCK_GOAL_SRC, DISCARD_OVERSTOCK_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(PROGRESSION_GOAL_SRC, PROGRESSION_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(RESTORE_HP_GOAL_SRC, RESTORE_HP_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(DEPOSIT_INVENTORY_GOAL_SRC, DEPOSIT_INVENTORY_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    run_group(SELL_INVENTORY_GOAL_SRC, SELL_INVENTORY_GOAL_MUTATIONS,
              "formal/diff/test_goal_system_value_diff.py", survivors)
    # Phase-19d — Tier-1 liveness differential.
    run_group(MEASURE_SRC, LIVENESS_MEASURE_MUTATIONS,
              "formal/diff/test_local_progress_diff.py", survivors)
    run_group(GATHERING_APPLY_SRC, LIVENESS_GATHERING_MUTATIONS,
              "formal/diff/test_local_progress_diff.py", survivors)
    run_group(APPLY_REST_SRC, LIVENESS_REST_MUTATIONS,
              "formal/diff/test_local_progress_diff.py", survivors)
    # Phase 21d-2 — Tier-3 plan-exists differential.
    run_group(ACTION_FACTORY_SRC, PLAN_EXISTS_BUILD_ACTIONS_MUTATIONS,
              "formal/diff/test_plan_exists_diff.py", survivors)
    # Phase-22b — cycle-loop differential.
    run_group(CYCLE_STEP_SRC, CYCLE_STEP_MUTATIONS,
              "formal/diff/test_cycle_step_diff.py", survivors)
    # P0 2026-06-09 — items-task material reservation differential.
    run_group(TASK_RESERVATION_SRC, TASK_RESERVATION_MUTATIONS,
              "formal/diff/test_task_reservation_diff.py", survivors)
    run_group(GATHER_PLANNABLE_CORE_SRC, GATHER_PLANNABLE_MUTATIONS,
              "formal/diff/test_skill_gate_fastfail_diff.py", survivors)
    run_group(LEAF_ATTAINABLE_CORE_SRC, LEAF_ATTAINABLE_MUTATIONS,
              "formal/diff/test_leaf_attainable_diff.py", survivors)
    run_group(COMPLETE_TASK_CORE_SRC, COMPLETE_TASK_MUTATIONS,
              "formal/diff/test_complete_task_income_diff.py", survivors)
    run_group(FUNDING_CORE_SRC, FUNDING_MUTATIONS,
              "formal/diff/test_currency_funding_diff.py", survivors)
    run_group(CURRENCY_AFFORD_CORE_SRC, CURRENCY_AFFORD_MUTATIONS,
              "formal/diff/test_currency_afford_diff.py", survivors)
    run_group(DOOMED_MEMO_SRC, DOOMED_MEMO_MUTATIONS,
              "formal/diff/test_doomed_memo_diff.py", survivors)
    run_group(STRATEGY_DRIVER_SRC, STRATEGY_DRIVER_MUTATIONS,
              "tests/test_ai/test_strategy_driver_tiered.py", survivors)
    run_group(COMBAT_SRC, COMBAT_VETO_MUTATIONS,
              "tests/test_ai/test_combat.py", survivors)
    run_group(SCORING_SRC, ARMOR_UTILITY_MUTATIONS,
              "formal/diff/test_equipment_scoring_diff.py", survivors)
    run_group(EQUIP_VALUE_SRC, EQUIP_VALUE_UTILITY_MUTATIONS,
              "tests/test_ai/test_tiers_equip_value.py", survivors)
    run_group(INVENTORY_CAPS_SRC, EQUIP_VALUE_DOMINANCE_MUTATIONS,
              "tests/test_ai/test_overstock.py", survivors)
    run_group(GAME_DATA_PARSE_SRC, RESTORE_FAMILY_MUTATIONS,
              "tests/test_ai/test_game_data.py", survivors)
    run_group(LOCATION_CATALOG_SRC, EVENT_VISIBILITY_MUTATIONS,
              "tests/test_ai/test_event_content_visibility.py", survivors)
    # C5 — next_craft_target_pure: churn fix differential.
    run_group(NEXT_CRAFT_CORE_SRC, NEXT_CRAFT_MUTATIONS,
              "formal/diff/test_next_craft_diff.py", survivors)
    # B2 — craft_plan_full full-plan driver (consuming model) differential.
    run_group(CRAFT_PLAN_DRIVER_SRC, CRAFT_PLAN_DRIVER_MUTATIONS,
              "formal/diff/test_craft_plan_driver_diff.py", survivors)
    _execute(_UNITS, survivors)
    if survivors:
        print(f"GATE FAIL: survivors={survivors}")
        return 1
    print("mutation gate OK")
    return 0


def _parse_args(argv: list[str]) -> None:
    global _RUNNER, _ONLY, _WORKERS
    parser = argparse.ArgumentParser(description="Mutation runner for the formal gate.")
    parser.add_argument("--runner", choices=("parallel", "serial"), default=_RUNNER,
                        help="parallel (private-copy worker threads, default) or "
                             "serial (in-place per-mutant subprocess, parity oracle)")
    parser.add_argument("--workers", type=int, default=_WORKERS,
                        help=f"parallel worker count (default: {_WORKERS})")
    parser.add_argument("--only", default=None,
                        help="comma-separated substrings; run only groups whose "
                             "src or test path matches one (default: all groups)")
    ns = parser.parse_args(argv)
    _RUNNER = ns.runner
    _WORKERS = max(1, ns.workers)
    if ns.only:
        _ONLY = [tok.strip() for tok in ns.only.split(",") if tok.strip()]


if __name__ == "__main__":
    _parse_args(sys.argv[1:])
    sys.exit(main())
