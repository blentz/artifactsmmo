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
SCORING_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "equipment" / "scoring.py"
SKILL_XP_CURVE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "learning" / "skill_xp_curve.py"
RECIPE_CLOSURE_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "recipe_closure.py"
TASK_FEASIBILITY_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "task_feasibility.py"
PREREQUISITE_GRAPH_SRC = ROOT / "src" / "artifactsmmo_cli" / "ai" / "tiers" / "prerequisite_graph.py"

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
    # drop the no-downgrade guard on the weapon branch: always swap to the argmax
    # candidate even when it is strictly WORSE than the equipped item.
    ("equipment_scoring: drop weapon no-downgrade guard (always swap)",
     "        if slot == \"weapon_slot\":\n"
     "            if weapon_score(best, monster_res) > weapon_score(current_stats, monster_res):\n"
     "                result[slot] = best.code",
     "        if slot == \"weapon_slot\":\n"
     "            result[slot] = best.code"),
    # drop the weapon clamp: max(0.0, 1 - res/100) -> (1 - res/100), letting a
    # high-resistance monster make a strong weapon score NEGATIVE (so a weak weapon
    # could be preferred / scores go below 0).
    ("equipment_scoring: drop weapon clamp max(0.0, ...)",
     "        score += atk * max(0.0, 1.0 - res_pct / 100.0)",
     "        score += atk * (1.0 - res_pct / 100.0)"),
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


def main() -> int:
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
    run_group(SKILL_XP_CURVE_SRC, SKILL_XP_CURVE_MUTATIONS,
              "formal/diff/test_skill_xp_curve_diff.py", survivors)
    run_group(RECIPE_CLOSURE_SRC, RECIPE_CLOSURE_MUTATIONS,
              "formal/diff/test_recipe_closure_diff.py", survivors)
    run_group(TASK_FEASIBILITY_SRC, TASK_FEASIBILITY_MUTATIONS,
              "formal/diff/test_task_feasibility_diff.py", survivors)
    run_group(PREREQUISITE_GRAPH_SRC, PREREQUISITE_GRAPH_MUTATIONS,
              "formal/diff/test_prerequisite_graph_diff.py", survivors)
    if survivors:
        print(f"GATE FAIL: survivors={survivors}")
        return 1
    print("mutation gate OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
