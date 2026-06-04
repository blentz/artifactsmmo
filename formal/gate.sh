#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
. "$HOME/.elan/env" 2>/dev/null || true
# Pull Mathlib's hosted prebuilt cache before compiling. Saves ~30 min
# of cold Lean+Mathlib compile per CI run. `|| true` because the command
# fails benignly when cache.lean isn't built yet (first invocation) —
# subsequent `lake build` still recompiles what's missing.
echo "== (pre) mathlib cache =="
( cd "$HERE" && lake exe cache get 2>&1 | tail -3 || echo "cache get skipped" )
echo "== (a) kernel build =="; ( cd "$HERE" && lake build )
echo "== (a') orphan modules =="; bash "$HERE/gate/check_no_orphan_modules.sh"
echo "== (a'') no sorry/admit =="; bash "$HERE/gate/check_no_sorry.sh"
echo "== (b) axiom lint =="; bash "$HERE/gate/check_axioms.sh"
echo "== (b') role manifest =="; ( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/test_calculate_path_diff.py formal/diff/test_task_batch_diff.py formal/diff/test_inventory_caps_diff.py formal/diff/test_predict_win_diff.py formal/diff/test_loadout_projection_diff.py formal/diff/test_equipment_scoring_diff.py formal/diff/test_skill_xp_curve_diff.py formal/diff/test_recipe_closure_diff.py formal/diff/test_task_feasibility_diff.py formal/diff/test_prerequisite_graph_diff.py formal/diff/test_objective_diff.py formal/diff/test_strategy_traversal_diff.py formal/diff/test_reachability_diff.py formal/diff/test_bank_selection_diff.py formal/diff/test_stuck_detector_diff.py formal/diff/test_priority_band_diff.py formal/diff/test_owned_count_diff.py formal/diff/test_upgrade_selection_diff.py formal/diff/test_scalarizer_diff.py formal/diff/test_planner_admissibility_diff.py formal/diff/test_arbiter_select_diff.py formal/diff/test_task_decision_diff.py formal/diff/test_weighted_remaining_diff.py formal/diff/test_low_yield_cancel_diff.py formal/diff/test_strategy_blend_diff.py formal/diff/test_decide_key_diff.py formal/diff/test_cycles_for_progress_diff.py formal/diff/test_gather_apply_diff.py formal/diff/test_action_cost_nonneg_diff.py formal/diff/test_realizable_loadout_diff.py formal/diff/test_apply_baseline_diff.py formal/diff/test_npc_buy_inventory_diff.py formal/diff/test_inventory_chain_safe_diff.py formal/diff/test_phase7_invariants_diff.py formal/diff/test_store_warmup_diff.py formal/diff/test_bank_expansion_diff.py formal/diff/test_game_data_accessors_diff.py formal/diff/test_goal_value_band_safety_diff.py formal/diff/test_goal_system_value_diff.py -q --no-cov )
echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
echo "ALL GATE PARTS PASSED"
