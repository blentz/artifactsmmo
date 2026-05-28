#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"; ROOT="$(cd "$HERE/.." && pwd)"
. "$HOME/.elan/env" 2>/dev/null || true
echo "== (a) kernel build =="; ( cd "$HERE" && lake build )
echo "== (b) axiom lint =="; bash "$HERE/gate/check_axioms.sh"
echo "== (b') role manifest =="; ( cd "$HERE" && lake env lean Formal/Manifest.lean >/dev/null && echo "manifest OK" )
echo "== (d) differential =="; ( cd "$HERE" && lake build oracle ); ( cd "$ROOT" && uv run pytest formal/diff/test_calculate_path_diff.py formal/diff/test_task_batch_diff.py formal/diff/test_inventory_caps_diff.py formal/diff/test_predict_win_diff.py formal/diff/test_loadout_projection_diff.py formal/diff/test_equipment_scoring_diff.py formal/diff/test_skill_xp_curve_diff.py formal/diff/test_recipe_closure_diff.py formal/diff/test_task_feasibility_diff.py formal/diff/test_prerequisite_graph_diff.py formal/diff/test_objective_diff.py formal/diff/test_strategy_traversal_diff.py formal/diff/test_reachability_diff.py formal/diff/test_bank_selection_diff.py formal/diff/test_stuck_detector_diff.py formal/diff/test_priority_band_diff.py formal/diff/test_owned_count_diff.py formal/diff/test_upgrade_selection_diff.py formal/diff/test_scalarizer_diff.py formal/diff/test_planner_admissibility_diff.py formal/diff/test_arbiter_select_diff.py formal/diff/test_task_decision_diff.py formal/diff/test_weighted_remaining_diff.py formal/diff/test_low_yield_cancel_diff.py formal/diff/test_strategy_blend_diff.py formal/diff/test_decide_key_diff.py formal/diff/test_cycles_for_progress_diff.py -q --no-cov )
echo "== (c) mutation =="; ( cd "$ROOT" && uv run python formal/diff/mutate.py )
echo "ALL GATE PARTS PASSED"
