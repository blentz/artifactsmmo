-- @concept: planner, core @property: safety, reachability
/-
Formal model of the GOAP planner's DEPTH BOUND, from
`src/artifactsmmo_cli/ai/planner.py`.

THE CODE FACTS this mirrors (planner.py):
  * L118  `if node.depth >= max_depth: continue`
          — a node at depth ≥ max_depth is NOT expanded (produces no children).
  * L131-139 each expansion pushes a child with
          `depth = node.depth + 1` and `plan = [*node.plan, action]`
          — depth and plan length advance in lockstep, so for every node
          `len(plan) == depth`.
  * L108-116 a satisfied node is RETURNED as `node.plan`.

CONSEQUENCE: the planner can never return a plan longer than `max_depth`.
The pre-plan skip this once justified (`is_plannable` refusing a goal whose
lower bound exceeded `max_depth`, with the copper_boots arithmetic as its
witness) was deleted in Phase 3-2 of docs/PLAN_decision_architecture_redesign.md,
and its two theorems with it.

This module proves:
  * `reachable_planLen_eq_depth`   — the lockstep invariant `planLen = depth`,
  * `reachable_depth_le_maxDepth`  — every reachable node has `depth ≤ maxDepth`,
  * `plan_length_le_max_depth`     — SAFETY INVARIANT: any plan the search can
                                     return has length ≤ maxDepth.

Lean core only — no mathlib.
-/

namespace Formal.PlannerDepthBound

/-- A search node, mirroring planner.py `_Node`: the `depth` and the length of
the `plan` that reached it. We track only what the depth bound needs. -/
structure Node where
  depth   : Nat
  planLen : Nat
deriving Repr, DecidableEq

/-- Nodes the search can actually reach, mirroring the planner loop precisely:

* `root` — the start node `_Node(depth=0, plan=[])` (planner.py:92).
* `step` — expanding a reachable node `n` produces a child ONLY when
  `n.depth < maxDepth` (the `if node.depth >= max_depth: continue` guard,
  planner.py:118), and the child has `depth = n.depth + 1`,
  `planLen = n.planLen + 1` (planner.py:131-139). Branching WIDTH is irrelevant
  to the depth bound — any number of children all share this depth/planLen shape,
  so one representative successor faithfully captures the reachable-node shape. -/
inductive Reachable (maxDepth : Nat) : Node → Prop where
  | root : Reachable maxDepth ⟨0, 0⟩
  | step : ∀ n, Reachable maxDepth n → n.depth < maxDepth →
      Reachable maxDepth ⟨n.depth + 1, n.planLen + 1⟩

/-- **Lockstep invariant.** Every reachable node has `planLen = depth`: each
expansion appends exactly one action while incrementing depth by one. -/
theorem reachable_planLen_eq_depth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.planLen = n.depth := by
  induction h with
  | root => rfl
  | step n _ _ ih => simp [ih]

/-- Every reachable node has `depth ≤ maxDepth`: the root is at depth 0, and a
child is created only from a parent strictly below `maxDepth`, so its depth
(parent + 1) is at most `maxDepth`. -/
theorem reachable_depth_le_maxDepth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.depth ≤ maxDepth := by
  induction h with
  | root => exact Nat.zero_le _
  | step n _ hlt _ => exact hlt

/-- **SAFETY INVARIANT.** Any plan the planner can return has length ≤
`max_depth`. (A returned plan is the `planLen` of some reachable, satisfied
node; combine the two invariants above.) -/
theorem plan_length_le_max_depth (maxDepth : Nat) (n : Node)
    (h : Reachable maxDepth n) : n.planLen ≤ maxDepth := by
  rw [reachable_planLen_eq_depth maxDepth n h]
  exact reachable_depth_le_maxDepth maxDepth n h

end Formal.PlannerDepthBound
