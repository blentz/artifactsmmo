# TUI backlog (deferred — address AFTER the level-50 #2-6 work)

Raised 2026-06-18 while diagnosing the copper_ring/copper_armor cannibalization
wobble (the scoring/ranking was hard to follow from the live UI). Both are
observability/UX, not correctness — explicitly queued behind the formal
level-50 work (#2-6 of the level-50 todo).

## 1. BUG — scoring not visible in the log
The per-cycle strategy `ranking` (root_repr / category / score / step_repr) and
the chosen_root vs selected_goal relationship are recorded in the trace jsonl but
are NOT surfaced in the live TUI log pane. Diagnosing the wobble required parsing
the raw trace. Surface the ranking (at least top-N roots with scores + the
chosen root/step) in the log so the operator can see WHY the bot chose a goal in
real time. Source of truth already exists: the `strategy` block per cycle
(`chosen_root`, `chosen_step`, `ranking[]`) in the cycle snapshot.

## 2. FEATURE — deeper plan-view tree
The plan view (`tui/screens/plan_screen.py` / `tui/plan_summary.py`) shows a
shallow summary. Expand it into a deeper tree exposing more of the AI's thought
process: the objective roots ranked with scores, the chosen root → step →
GOAP plan (path_next_action / plan_len), guards/means considered, and
suppressed_goals — so the reasoning chain (strategy → arbiter → planner) is
legible without reading the trace. Reuse the cycle snapshot fields the trace
already carries.

## Notes
- Both read from data that already exists in the cycle snapshot / trace; no new
  decision logic, so no formal-gate impact — pure presentation.
- Do these together (shared snapshot plumbing into the TUI).
