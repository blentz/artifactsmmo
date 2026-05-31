"""Mutation runner: each mutant the diff test fails to kill is a survivor -> gate fails."""
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src" / "artifactsmmo_cli" / "utils" / "pathfinding.py"
TASK_BATCH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_batch.py"
INVENTORY_CAPS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "inventory_caps.py"
COMBAT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "combat.py"
PROJECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "equipment" / "projection.py"
GATHERING_APPLY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "gathering.py"
LEVEL_SKILL_GOAL_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "level_skill.py"
SCORING_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "equipment" / "scoring.py"
SKILL_XP_CURVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "skill_xp_curve.py"
PLAYER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "player.py"
RECIPE_CLOSURE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "recipe_closure.py"
TASK_FEASIBILITY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_feasibility.py"
PREREQUISITE_GRAPH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "prerequisite_graph.py"
OBJECTIVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "objective.py"
STRATEGY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "strategy.py"
BANK_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "bank_selection.py"
STUCK_DETECTOR_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "recovery.py"
PRIORITY_BAND_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "priority_band.py"
OWNED_COUNT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "owned_count.py"
UPGRADE_SELECTION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "goals" / "upgrade_selection.py"
SCALAR_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "scalar_core.py"
PLANNER_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "planner.py"
ARBITER_SELECT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "arbiter_select.py"
TASK_DECISION_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_decision_core.py"
OBJECTIVE_COMPLETION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "objective_completion.py"
LOW_YIELD_BOUNDARY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "low_yield_boundary.py"
STRATEGY_BLEND_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "strategy_blend.py"
DECIDE_KEY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "decide_key.py"
CYCLES_FOR_PROGRESS_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "cycles_for_progress_core.py"
GATHER_APPLY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "gather_apply_core.py"
COST_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "cost_core.py"
NPC_BUY_CORE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "npc_buy_core.py"
APPLY_MOVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "movement.py"
APPLY_EQUIP_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "equip.py"
APPLY_CLAIM_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "claim.py"
APPLY_REST_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "rest.py"
APPLY_FIGHT_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "combat.py"
APPLY_BANK_EXPANSION_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "actions" / "bank_expansion.py"
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
GAME_DATA_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "game_data.py"
WINNABLE_CASCADE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "winnable_cascade.py"
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
    ("task_batch: off-by-one remaining (+1)",
     "    remaining = state.task_total - state.task_progress",
     "    remaining = state.task_total - state.task_progress + 1"),
]


# inventory_caps mutations -- old strings matched to current inventory_caps.py text.
INVENTORY_CAPS_MUTATIONS = [
    # drop the equipped floor: equipped items no longer guaranteed >= 1.
    ("inventory_caps: drop equipped max(1, ...) floor",
     "        return max(1, useful_quantity_cap_excl_equipped(item_code, state, game_data,\n"
     "                                                          batch_buffer, safety_floor))",
     "        return useful_quantity_cap_excl_equipped(item_code, state, game_data,\n"
     "                                                          batch_buffer, safety_floor)"),
    # drop the safety-floor clamp: demanded items can fall below safety_floor.
    ("inventory_caps: drop safety-floor clamp",
     "        recipe_cap = max(recipe_cap, safety_floor)",
     "        recipe_cap = recipe_cap"),
    # overstock off-by-one: record qty - cap + 1 instead of qty - cap.
    ("inventory_caps: overstock off-by-one (+1)",
     "            excess[code] = qty - cap",
     "            excess[code] = qty - cap + 1"),
]


# predict_win mutations -- old strings matched to current combat.py text.
PREDICT_WIN_MUTATIONS = [
    # initiative tiebreak: flip the player-first `<=` to a strict `<` (combat.py:79).
    ("predict_win: tiebreak <= -> < (player-first)",
     "    return rounds_to_kill <= rounds_to_die if player_first else rounds_to_kill < rounds_to_die",
     "    return rounds_to_kill < rounds_to_die if player_first else rounds_to_kill < rounds_to_die"),
    # drop the expected critical-strike contribution entirely.
    ("predict_win: drop crit term in _expected_hit",
     "    return raw * (1 + (crit / 100) * 0.5)",
     "    return raw * 1"),
    # off-by-one in the half-up rounding (ceil-ish): + 0.5 -> + 1.5.
    ("predict_win: round_half_up off-by-one (+0.5 -> +1.5)",
     "    return math.floor(value + 0.5)",
     "    return math.floor(value + 1.5)"),
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
    # drop the no-downgrade guard: force `improves = True` so the selector
    # always swaps to the argmax candidate even when it is strictly WORSE than
    # the equipped item. After the multi-slot claim refactor the same property
    # lives in the shared `improves` flag used by both weapon and armor slots.
    ("equipment_scoring: drop no-downgrade guard (improves forced True)",
     "        if slot == \"weapon_slot\":\n"
     "            improves = weapon_score(best, monster_res) > weapon_score(current_stats, monster_res)\n"
     "        else:\n"
     "            improves = armor_score(best, monster_atk) > armor_score(current_stats, monster_atk)",
     "        improves = True"),
    # drop the weapon clamp: max(0, 100 - res) -> (100 - res), letting a
    # high-resistance monster make a strong weapon score NEGATIVE (so a weak weapon
    # could be preferred / scores go below 0).
    ("equipment_scoring: drop weapon clamp max(0, 100 - res_pct)",
     "        score += atk * max(0, 100 - res_pct)",
     "        score += atk * (100 - res_pct)"),
    # Byte-equivalence kill: divide armor_score by 100, turning the exact integer
    # surrogate into a float that no longer matches the Lean integer model
    # byte-for-byte. The diff test asserts py_score == lean_score as integers;
    # this mutation makes py a float and breaks the int identity.
    ("equipment_scoring: armor_score float-rescale (breaks byte-equivalence)",
     "        score += mon_atk * armor_res_pct",
     "        score += mon_atk * armor_res_pct / 100.0"),
]


# realizable_loadout mutations -- target the claimed-codes accumulator in
# scoring.pick_loadout (the multi-slot bug fix). Each mutation breaks the
# realizability invariant `is_realizable(pick_loadout(...), inv, equip)`,
# killed by formal/diff/test_realizable_loadout_diff.py.
REALIZABLE_LOADOUT_MUTATIONS = [
    # Drop the claimed-codes feasibility filter: every candidate is feasible
    # regardless of how many copies have already been claimed by peer slots.
    # Resurrects the original bug — multi-slot peers (ring1/ring2, etc.) all
    # pick the same scarce code.
    ("realizable_loadout: drop claimed-codes feasibility filter",
     "        feasible: list[ItemStats] = [\n"
     "            cand for cand in candidates if _effective_available(cand.code) >= 1\n"
     "        ]",
     "        feasible: list[ItemStats] = list(candidates)"),
    # Drop the claim increment on a SWAP-TO-BEST decision: a code can be
    # selected by every slot in sequence because no slot ever records its
    # claim. The is_applicable / first slot still sees `>= 1` feasibility,
    # but downstream peers see the same `>= 1` because nothing was claimed.
    ("realizable_loadout: drop _claim(best.code) on improve-swap",
     "        if improves:\n"
     "            result[slot] = best.code\n"
     "            _claim(best.code)",
     "        if improves:\n"
     "            result[slot] = best.code"),
    # Make `_effective_available` ignore the claim count entirely: the
    # feasibility check degenerates to raw ownership, so peer slots see
    # the same physical item as available again. (Bypasses the accumulator.)
    ("realizable_loadout: _effective_available ignores claimed_codes",
     "    def _effective_available(code: str) -> int:\n"
     "        return ownership(code, state.inventory, state.equipment) - claimed_codes.get(code, 0)",
     "    def _effective_available(code: str) -> int:\n"
     "        return ownership(code, state.inventory, state.equipment)"),
    # Phase-15 new mutation A: drop the no-downgrade strict-improvement check
    # in pick_loadout. Swap to best regardless of whether it beats current,
    # violating Property 2 (no-downgrade). The Lean theorem
    # `pickSlotStep_no_downgrade` forbids this except via the stolen-current
    # branch; an unconditional swap fires on plain ties / regressions.
    ("realizable_loadout: drop no-downgrade strict-improvement check",
     "        if slot == \"weapon_slot\":\n"
     "            improves = weapon_score(best, monster_res) > weapon_score(current_stats, monster_res)\n"
     "        else:\n"
     "            improves = armor_score(best, monster_atk) > armor_score(current_stats, monster_atk)\n"
     "        if improves:",
     "        if slot == \"weapon_slot\":\n"
     "            improves = weapon_score(best, monster_res) > weapon_score(current_stats, monster_res)\n"
     "        else:\n"
     "            improves = armor_score(best, monster_atk) > armor_score(current_stats, monster_atk)\n"
     "        if True:"),
    # Phase-15 new mutation B: drop the _claim(current_code) on the keep-current
    # branch (when current ties or beats best and is still available). Peer
    # slots then see the current code as physically unspoken-for and can
    # duplicate it, violating Property 1 (output realizability).
    ("realizable_loadout: drop _claim(current_code) on keep-current",
     "        elif _effective_available(current_code) >= 1:\n"
     "            _claim(current_code)",
     "        elif _effective_available(current_code) >= 1:\n"
     "            pass"),
    # Phase-15 new mutation C: swap weapon_score and armor_score per slot.
    # weapon_slot uses armor_score (defense-oriented) and the rest use
    # weapon_score (offense-oriented). Violates Property 3 (per-slot
    # argmax under the SLOT-CORRECT score function); the Lean `pickSlotStep_optimal`
    # is parameterised by a score function, so this mutation flips the
    # operational meaning of the choice on multi-element monsters.
    ("realizable_loadout: swap weapon_score and armor_score per slot",
     "        if slot == \"weapon_slot\":\n"
     "            best = max(feasible, key=lambda s: weapon_score(s, monster_res))\n"
     "        else:\n"
     "            best = max(feasible, key=lambda s: armor_score(s, monster_atk))",
     "        if slot == \"weapon_slot\":\n"
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


# recipe_closure mutations -- old strings matched to current recipe_closure.py text.
RECIPE_CLOSURE_MUTATIONS = [
    # drop the visited guard in recipe_closure: revisits no longer short-circuit
    # (cyclic graphs would loop forever / over-collect). Replace the early return
    # with a no-op so the function over-explores (and diverges on cycles).
    ("recipe_closure: drop visited guard (no early return on revisit)",
     "        if material in visited:\n            return\n        visited.add(material)",
     "        visited.add(material)"),
    # omit a recipe edge: recurse only into the FIRST sub-material, missing the
    # rest of the closure (incomplete craftable_mats / needed_resources).
    ("recipe_closure: omit recipe edges (recurse first sub only)",
     "            for sub_mat in recipe:\n                collect(sub_mat)",
     "            for sub_mat in list(recipe)[:1]:\n                collect(sub_mat)"),
    # alter the qty factor in raw_material_units: drop the qty multiplier so
    # quantities no longer multiply down the tree (wrong units total).
    ("raw_material_units: drop qty factor (qty * units -> units)",
     "    return sum(qty * raw_material_units(game_data, sub, deeper) for sub, qty in recipe.items())",
     "    return sum(raw_material_units(game_data, sub, deeper) for sub, qty in recipe.items())"),
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
     "    return any(predict_win(state, game_data, code) for code in game_data._monster_level)",
     "    return all(predict_win(state, game_data, code) for code in game_data._monster_level)"),
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
     "            if isinstance(node, ObtainItem) and not _producible(node.code, game_data):\n"
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
     "        window = self._recent_since(cutoff, count=10)\n"
     "        if len(window) < 10:",
     "        window = self._recent_since(cutoff, count=9)\n"
     "        if len(window) < 9:"),
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
    # 2.0, inverting the weight-dominance the scalar relies on.
    ("scalar_core: swap relevant/baseline weight",
     "        weight = relevant_w if skill_name in active_skills else baseline_w",
     "        weight = baseline_w if skill_name in active_skills else relevant_w"),
    # gold sign flip: gold component subtracted instead of added (+gold -> -gold).
    ("scalar_core: gold component sign flip (+ -> -)",
     "    gold_component = gold / gold_per_xp",
     "    gold_component = -gold / gold_per_xp"),
    # coin component dropped: tasks_coins no longer contribute to the scalar.
    ("scalar_core: drop coin component (coin_value -> 0)",
     "    coin_component = tasks_coins * coin_value / gold_per_xp",
     "    coin_component = tasks_coins * 0 / gold_per_xp"),
    # Byte-equivalence kill: seed the skill-xp accumulator with 0.0 instead of
    # integer 0, forcing every subsequent term into float and breaking the
    # exact-Fraction identity the diff test pins (Fraction + float -> TypeError
    # under strict isinstance(val, Fraction) assertion, or a float result that
    # disagrees bit-for-bit with the Lean Rat oracle on inputs with denominators
    # that aren't powers of two).
    ("scalar_core: float-seed skill_xp_component (breaks byte-equivalence on Fraction inputs)",
     "    skill_xp_component = 0\n"
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
     "                if plan:\n"
     "                    return committed_cand.goal, plan, committed_repr",
     "            if True:\n"
     "                plan = try_plan(committed_cand.goal)\n"
     "                tried_repr = committed_repr\n"
     "                if plan:\n"
     "                    return committed_cand.goal, plan, committed_repr"),
    # sticky always wins: skip the walk entirely if committed is found. Even
    # when committed is not plannable, the function returns None instead of
    # falling through.
    ("arbiter_select: sticky always wins (return committed unconditionally)",
     "            if not guard_precedes:\n"
     "                plan = try_plan(committed_cand.goal)\n"
     "                tried_repr = committed_repr\n"
     "                if plan:\n"
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
     "        plan = try_plan(cand.goal)\n        if plan:\n",
     "        plan = try_plan(cand.goal)\n        if not plan:\n"),
    # drop the is_means commitment guard: a guard win wrongly sets new_committed
    # to the guard's repr (commitment should clear on guard wins).
    ("arbiter_select: commit on guard win (drop is_means guard)",
     "            new_committed = cand.repr_ if cand.is_means else None",
     "            new_committed = cand.repr_"),
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
     "    raw = 1.0 + BALANCE_K * (leader - current - BALANCE_THRESHOLD)",
     "    raw = 1.0 - BALANCE_K * (leader - current - BALANCE_THRESHOLD)"),
    # drop the lower band clamp: max(BALANCE_MIN, ...) -> the inner min only.
    # A skill far ahead of the leader now produces a multiplier below 0.5 (and
    # possibly negative). The proved lower bound + threshold tests both fire.
    ("strategy_blend: drop lower band clamp (max -> bare inner min)",
     "    return max(BALANCE_MIN, min(BALANCE_MAX, raw))",
     "    return min(BALANCE_MAX, raw)"),
    # swap BALANCE_K 0.25 -> 1.0: multiplier amplification per gap-unit is 4x
    # too strong; clamp kicks in much sooner (essentially everywhere) and the
    # threshold identity (gap=2 ⇒ 1.0) is preserved BUT the gap=4 → 1.5 test
    # and the hypothesis-driven mid-band values fail.
    ("strategy_blend: BALANCE_K 0.25 -> 1.0",
     "BALANCE_K = 0.25",
     "BALANCE_K = 1.0"),
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
     "    return (neg_final, effort, root_repr)",
     "    return (effort, neg_final, root_repr)"),
    # drop the rootRepr tiebreak: two same-(negFinal, effort) keys with
    # different reprs now compare equal — but Python's list.sort is stable, so
    # the repr-tiebreak assertion still passes via stability... we instead
    # break the assertion by RETURNING the third field as a CONSTANT (any
    # constant string), which violates the proved `eq_imp_repr` lemma at the
    # tuple level. The test fires when two distinct reprs collide.
    ("decide_key: drop rootRepr tiebreak (constant third field)",
     "    return (neg_final, effort, root_repr)",
     '    return (neg_final, effort, "")'),
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
     "            gold=state.gold - game_data._next_expansion_cost,\n"
     "            x=dest[0],\n"
     "            y=dest[1],\n"
     "            cooldown_expires=None,\n"
     "            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,\n"
     "        )",
     "        return dataclasses.replace(\n"
     "            state,\n"
     "            gold=state.gold - game_data._next_expansion_cost,\n"
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
     "            capacity = self._game_data._bank_capacity\n"
     "        else:\n"
     "            capacity = 0",
     "        capacity = self._game_data._bank_capacity if self._game_data is not None else 0"),
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


def run_diff(test_path: str) -> int:
    return subprocess.run(
        ["uv", "run", "pytest", test_path, "-q", "--no-cov", "-x"],
        cwd=ROOT,
        env={**os.environ, "PYTHONDONTWRITEBYTECODE": "1"},
    ).returncode


def run_group(src: Path, mutations, test_path: str, survivors: list) -> None:
    orig = src.read_text()
    try:
        for desc, old, new in mutations:
            if old not in orig:
                print(f"STALE MUTATION (text not found): {desc}")
                survivors.append(desc + " (stale)")
                continue
            src.write_text(orig.replace(old, new, 1))
            if run_diff(test_path) == 0:
                print(f"SURVIVED: {desc}")
                survivors.append(desc)
            else:
                print(f"killed: {desc}")
    finally:
        src.write_text(orig)


_ALL_SRCS = [
    SRC, TASK_BATCH_SRC, INVENTORY_CAPS_SRC, COMBAT_SRC, PROJECTION_SRC, SCORING_SRC,
    SKILL_XP_CURVE_SRC, RECIPE_CLOSURE_SRC, TASK_FEASIBILITY_SRC, PREREQUISITE_GRAPH_SRC,
    OBJECTIVE_SRC, STRATEGY_SRC, BANK_SELECTION_SRC, STUCK_DETECTOR_SRC,
    PRIORITY_BAND_SRC, OWNED_COUNT_SRC, UPGRADE_SELECTION_SRC, SCALAR_CORE_SRC,
    PLANNER_SRC, ARBITER_SELECT_SRC, TASK_DECISION_CORE_SRC, OBJECTIVE_COMPLETION_SRC,
    LOW_YIELD_BOUNDARY_SRC, STRATEGY_BLEND_SRC, DECIDE_KEY_SRC,
    CYCLES_FOR_PROGRESS_SRC,
    GATHER_APPLY_SRC,
    COST_CORE_SRC,
    NPC_BUY_CORE_SRC,
    APPLY_MOVE_SRC, APPLY_EQUIP_SRC, APPLY_CLAIM_SRC,
    APPLY_REST_SRC, APPLY_FIGHT_SRC, APPLY_BANK_EXPANSION_SRC,
    WITHDRAW_ITEM_SRC, UNEQUIP_SRC, TASK_EXCHANGE_SRC, TASK_CANCEL_SRC,
    GATHERING_APPLY_SRC, LEVEL_SKILL_GOAL_SRC,
    GAME_DATA_SRC,
    WINNABLE_CASCADE_SRC,
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
    PLAYER_SRC,
]


# Phase 12 Target A: cheapest_path_to_level greedy contract. Mutants test
# (a) the +1 beatability margin, (b) strict-> tie-break, (c) the
# `best_xp_per_cycle <= 0` blocked branch. The diff test must kill all three.
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
]


# cycles_for_progress mutations -- old strings matched to current cycles_for_progress_core.py text.
CYCLES_FOR_PROGRESS_MUTATIONS = [
    # Drop the SATISFY append loop entirely: only strict-increase intervals
    # contribute. The verdict-(b) intentional-both-signal contract breaks;
    # `test_satisfy_only_branch` and `test_both_on_single_cycle_intentional_double_signal`
    # fire (the satisfy interval would no longer appear in the median).
    ("cycles_for_progress: drop the satisfy append loop",
     "    for cycle in chrono:\n"
     "        if cycle.cycles_to_satisfy is not None and cycle.cycles_to_satisfy > 0:\n"
     "            intervals.append(cycle.cycles_to_satisfy)\n",
     ""),
    # Flip `is not None` to `is None` in the satisfy gate: the recorded
    # `cycles_to_satisfy` values are SKIPPED and the (sparse) None-rows would
    # blow up on the `> 0` check (TypeError). Hypothesis quickly produces a
    # row with `cycles_to_satisfy = None`.
    ("cycles_for_progress: satisfy gate is not None -> is None",
     "        if cycle.cycles_to_satisfy is not None and cycle.cycles_to_satisfy > 0:",
     "        if cycle.cycles_to_satisfy is None and cycle.cycles_to_satisfy > 0:"),
    # Off-by-one on the strict-increase predicate: `>` becomes `>=`. A flat
    # `task_progress` row now also counts as a strict increase, inflating the
    # interval count. The general diff test fires whenever progress holds
    # steady for any chronological pair.
    ("cycles_for_progress: strict-increase > -> >= (off-by-one predicate)",
     "            if cycle.task_progress > prev_progress:",
     "            if cycle.task_progress >= prev_progress:"),
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
     "    if gold < price * quantity:\n"
     "        return False\n"
     "    return True",
     "    if gold < price * quantity:\n"
     "        return False\n"
     "    return True"),
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


APPLY_FIGHT_MUTATIONS = [
    (
        "apply-baseline-fight: revert FightAction.apply to explicit WorldState(...) dropping baseline",
        "        return dataclasses.replace(\n"
        "            state,\n"
        "            xp=state.xp + 10,\n"
        "            hp=new_hp,\n"
        "            x=dest[0],\n"
        "            y=dest[1],\n"
        "            cooldown_expires=None,\n"
        "            task_progress=new_progress,\n"
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
        "            gold=state.gold - game_data._next_expansion_cost,\n"
        "            x=dest[0],\n"
        "            y=dest[1],\n"
        "            cooldown_expires=None,\n"
        "            bank_capacity=pre_cap + BANK_EXPANSION_SLOTS,\n"
        "        )",
        "        return WorldState(\n"
        "            character=state.character,\n"
        "            level=state.level, xp=state.xp, max_xp=state.max_xp,\n"
        "            hp=state.hp, max_hp=state.max_hp,\n"
        "            gold=state.gold - game_data._next_expansion_cost,\n"
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
    # Mutation 1: resurrect silent {} default on monster_attack.
    ("game_data: monster_attack silent {} default resurrected",
     "        return self._monster_attack[code]",
     "        return self._monster_attack.get(code, {})"),
    # Mutation 2: resurrect silent 0 default on monster_hp.
    ("game_data: monster_hp silent 0 default resurrected",
     "        return self._monster_hp[code]",
     "        return self._monster_hp.get(code, 0)"),
    # Mutation 3: invert monster_initiative — silently return absent codes as 9999.
    ("game_data: monster_initiative inverted (silent 9999 default)",
     "        return self._monster_initiative[code]",
     "        return self._monster_initiative.get(code, 9999)"),
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
# class from the canonical action menu. The plan-exists differential
# (formal/diff/test_plan_exists_diff.py) must kill each by reporting a
# real production bug (planner returns empty plan for a firing means).
PLAN_EXISTS_BUILD_ACTIONS_MUTATIONS = [
    # Drop RestAction from the menu — HP_CRITICAL case loses its single-step
    # witness; planner returns []; test_planner_finds_plan_for_firing_means[
    # HP_CRITICAL] fires.
    ("plan_exists: drop RestAction from _build_actions",
     "        actions: list[Action] = [\n"
     "            RestAction(),",
     "        actions: list[Action] = [\n"
     "            # RestAction(),  # mutation: dropped",),
    # Drop DepositAllAction — DEPOSIT_FULL case has no actuator; planner
    # returns []; test_planner_finds_plan_for_firing_means[DEPOSIT_FULL] fires.
    ("plan_exists: drop DepositAllAction from _build_actions",
     "            DepositAllAction(bank_location=bank, accessible=self._bank_accessible, game_data=self.game_data),",
     "            # DepositAllAction(...),  # mutation: dropped"),
    # Drop FightAction construction — BANK_UNLOCK case has no combat
    # actuator; planner returns []; test_planner_finds_plan_for_firing_means[
    # BANK_UNLOCK] fires (the only fight-rooted in-scope means).
    ("plan_exists: drop FightAction from _build_actions",
     "            actions.append(FightAction(monster_code=monster_code, locations=frozenset(locs)))",
     "            pass  # mutation: dropped FightAction append"),
    # Disable the items-task TaskTradeAction insertion block (BOTH the
    # quantity=k primary and the quantity=1 fallback). PURSUE_TASK then has
    # no trade actuator; planner returns []; test_planner_finds_plan_for_firing_means[
    # PURSUE_TASK] fires. The shorter mutation (dropping only the quantity=k
    # line) was a SURVIVOR — the quantity=1 fallback alone is enough for the
    # planner to find a TaskTrade plan, so the mutation must remove both.
    ("plan_exists: disable items-task TaskTradeAction block",
     '        if self.state is not None and self.state.task_type == "items" and self.state.task_code:',
     '        if False and self.state is not None and self.state.task_type == "items" and self.state.task_code:'),
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
    survivors: list = []
    run_group(SRC, MUTATIONS, "formal/diff/test_calculate_path_diff.py", survivors)
    run_group(TASK_BATCH_SRC, TASK_BATCH_MUTATIONS, "formal/diff/test_task_batch_diff.py", survivors)
    run_group(INVENTORY_CAPS_SRC, INVENTORY_CAPS_MUTATIONS,
              "formal/diff/test_inventory_caps_diff.py", survivors)
    run_group(COMBAT_SRC, PREDICT_WIN_MUTATIONS,
              "formal/diff/test_predict_win_diff.py", survivors)
    run_group(PROJECTION_SRC, PROJECTION_MUTATIONS,
              "formal/diff/test_loadout_projection_diff.py", survivors)
    run_group(SCORING_SRC, SCORING_MUTATIONS,
              "formal/diff/test_equipment_scoring_diff.py", survivors)
    run_group(SCORING_SRC, REALIZABLE_LOADOUT_MUTATIONS,
              "formal/diff/test_realizable_loadout_diff.py", survivors)
    run_group(SKILL_XP_CURVE_SRC, SKILL_XP_CURVE_MUTATIONS,
              "formal/diff/test_skill_xp_curve_diff.py", survivors)
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
    run_group(CYCLES_FOR_PROGRESS_SRC, CYCLES_FOR_PROGRESS_MUTATIONS,
              "formal/diff/test_cycles_for_progress_diff.py", survivors)
    run_group(GATHER_APPLY_SRC, GATHER_APPLY_MUTATIONS,
              "formal/diff/test_gather_apply_diff.py", survivors)
    run_group(COST_CORE_SRC, COST_CORE_MUTATIONS,
              "formal/diff/test_action_cost_nonneg_diff.py", survivors)
    run_group(NPC_BUY_CORE_SRC, NPC_BUY_MUTATIONS,
              "formal/diff/test_npc_buy_inventory_diff.py", survivors)
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
    run_group(GAME_DATA_SRC, GAME_DATA_MUTATIONS,
              "formal/diff/test_game_data_accessors_diff.py", survivors)
    run_group(WINNABLE_CASCADE_SRC, WINNABLE_CASCADE_MUTATIONS,
              "formal/diff/test_winnable_cascade_diff.py", survivors)
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
    run_group(PLAYER_SRC, PLAN_EXISTS_BUILD_ACTIONS_MUTATIONS,
              "formal/diff/test_plan_exists_diff.py", survivors)
    if survivors:
        print(f"GATE FAIL: survivors={survivors}")
        return 1
    print("mutation gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
