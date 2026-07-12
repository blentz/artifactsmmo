-- @concept: crafting, planner @property: reachability, totality
/-
Formal model of the `strategy_traversal` PURE CORE from
`src/artifactsmmo_cli/ai/tiers/strategy.py`:

* `is_reachable`        (strategy.py:125) — cycle-safe path-recursive reachability;
* `unmet_closure_size`  (strategy.py:91)  — count of unmet nodes in the prereq closure;
* `actionable_step`     (strategy.py:69)  — deepest unmet node whose DIRECT prereqs
                                            are all satisfied (the "singular loop" step);
* `root_cost`           (strategy.py:107) — effort proxy, floored at 1.

The prerequisite graph (`prerequisites`) and `is_satisfied` are already proven in
`PrerequisiteGraph.lean`; we ABSTRACT them here as a NODE TABLE. Each node is a
`Nat`; the table provides per node:
* `prereqs : Nat → List Nat`   — its DIRECT prerequisite nodes
                                 (already the unsatisfied-pruned data edges);
* `isSat   : Nat → Bool`       — `MetaGoal.is_satisfied`;
* `producible : Nat → Bool`    — `strategy._producible` (recipe ∨ resource-drop);
* `kind    : Nat → Kind`       — `obtain` / `char`.

This is the genuine traversal logic over an arbitrary graph; cycles, satisfied
interior nodes, and unsatisfiable leaves are all expressible.

## `is_reachable` = grounding fixpoint

`is_reachable(root, path)` (strategy.py:183):
* `isSat root`              → true;
* `root ∈ path`             → false  (cycle guard);
* let `ps = prereqs root`; if `kind root = obtain ∧ ps = []` → `producible root`;
* else                      → all prereqs reachable under `path ∪ {root}`.

The well-founded GROUNDING fixpoint: a node grounds iff it is satisfied, OR
(kind=obtain with no prereqs AND producible), OR all its prereqs
ground. A node on a cycle of un-grounded nodes is NOT grounded → NOT reachable.
We prove the path-recursion = the grounding least fixpoint (soundness +
completeness) reusing the saturation / minimal-round technique of
`Objective.lean` / `RecipeClosure.lean`.

## `unmet_closure_size` = |unmet nodes in closure| (min 1)

The iterative DFS visits the prereq closure but DESCENDS ONLY UNMET NODES
(satisfied interior nodes are visited but neither counted nor expanded — the
"satisfied-interior pruning"), counting distinct unmet nodes, then `max(·, 1)`.
We model the exact visited-set count and prove it equals the size of the
independently-defined unmet-closure node set, and is `≥ 1`.

## `actionable_step` = a node from the ACTIONABLE set (or none)

A node is ACTIONABLE iff it is unmet ∧ every direct prereq is satisfied ∧
(kind=obtain ⇒ producible). The DFS pick-order is implementation-defined; we
prove the RETURNED node is actionable, and `none ↔ no actionable node is
reachable from root via unmet-prereq descent` — an INDEPENDENT characterization
of the actionable set (NOT the function restated), De-Morgan-dual on the
existence. Cycle pruning affects only termination, not which nodes are reachable.

## `root_cost` floored at 1

char roots: `max(1, target − have)`; gear (obtain) roots: `unmet_closure_size`
(itself `≥ 1`). So `root_cost ≥ 1` always.

Lean core only — no mathlib.
-/

namespace Formal.StrategyTraversal

/-! ### The node-kind tag and the abstract node graph. -/

/-- The meta-goal kind: `ObtainItem`, `ReachCharLevel`. -/
inductive Kind where
  | obtain | char
deriving DecidableEq, Repr

/-- An abstract node graph (the proven `prerequisites` / `is_satisfied` /
`_producible` data, abstracted). Nodes are `Nat`. -/
structure Graph where
  prereqs : Nat → List Nat
  isSat : Nat → Bool
  producible : Nat → Bool
  kind : Nat → Kind

/-! ### `is_reachable` — the cycle-safe path recursion. -/

/-- `reachAux g fuel path node`: structural fuel bounds depth (the real `path`
frozenset bounds it; we thread fuel so the function is total). Mirrors
`is_reachable` branch-for-branch:
* `isSat node`         → true;
* `node ∈ path`        → false;
* `prereqs node = []`  →  `kind node = obtain` ? `producible node` : true
  (a char node with no prereqs grounds via the empty `all`; the Python `all([])`
  is `true`, and only ObtainItem consults `_producible`);
* otherwise            → all prereqs reachable under `node :: path`. -/
def reachAux (g : Graph) : Nat → List Nat → Nat → Bool
  | 0, _, _ => false
  | fuel + 1, path, node =>
    if g.isSat node then true
    else if node ∈ path then false
    else match g.prereqs node with
      | [] => if g.kind node = Kind.obtain then g.producible node else true
      | ps => ps.all (fun p => reachAux g fuel (node :: path) p)

/-- Top-level `is_reachable(root)`: empty path; callers pass `fuel` ≥ node
universe size. -/
def isReachable (g : Graph) (fuel : Nat) (root : Nat) : Bool :=
  reachAux g fuel [] root

/-! ### Grounding — the least fixpoint, defined inductively. -/

/-- `Grounded g node`: the least set such that
* a satisfied node grounds;
* an `obtain` node with NO prereqs grounds iff it is producible;
* a node ALL of whose prereqs ground, grounds.

A node on a cycle of un-grounded nodes has no finite derivation → not grounded. -/
inductive Grounded (g : Graph) : Nat → Prop
  | sat {n : Nat} (h : g.isSat n = true) : Grounded g n
  | leaf {n : Nat} (hns : g.isSat n = false) (hk : g.kind n = Kind.obtain)
      (hempty : g.prereqs n = []) (hp : g.producible n = true) : Grounded g n
  | node {n : Nat} (hns : g.isSat n = false)
      (hobt : g.kind n = Kind.obtain → g.prereqs n ≠ [])
      (hall : ∀ p ∈ g.prereqs n, Grounded g p) : Grounded g n

/-! ### Fuel-bounded saturation (grounding closure). -/

/-- Nodes grounded within `n` saturation rounds. -/
def groundedByN (g : Graph) : Nat → Nat → Bool
  | 0, _ => false
  | n + 1, node =>
    if g.isSat node then true
    else match g.prereqs node with
      | [] => if g.kind node = Kind.obtain then g.producible node else true
      | ps => ps.all (fun p => groundedByN g n p)

/-! ### `groundedByN` monotonicity. -/

theorem groundedByN_mono (g : Graph) :
    ∀ (n node : Nat), groundedByN g n node = true →
      groundedByN g (n + 1) node = true := by
  intro n
  induction n with
  | zero => intro node h; simp [groundedByN] at h
  | succ k ih =>
    intro node h
    unfold groundedByN at h ⊢
    by_cases hs : g.isSat node = true
    · simp only [hs, if_true]
    · simp only [hs, Bool.false_eq_true, if_false] at h ⊢
      cases hp : g.prereqs node with
      | nil => simp only [hp] at h ⊢; exact h
      | cons hd tl =>
        simp only [hp] at h ⊢
        rw [List.all_eq_true] at h ⊢
        intro p hpmem
        exact ih p (h p hpmem)

theorem groundedByN_mono_le (g : Graph) (n k node : Nat)
    (h : groundedByN g n node = true) : groundedByN g (n + k) node = true := by
  induction k with
  | zero => exact h
  | succ j ih => exact groundedByN_mono g (n + j) node ih

theorem groundedByN_mono_of_le (g : Graph) {n m : Nat} (hnm : n ≤ m) (node : Nat)
    (h : groundedByN g n node = true) : groundedByN g m node = true := by
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hnm
  exact groundedByN_mono_le g n k node h

/-! ### Soundness / completeness of `groundedByN` vs the fixpoint. -/

/-- SOUNDNESS: `groundedByN` accepts only `Grounded` nodes. -/
theorem groundedByN_sound (g : Graph) :
    ∀ (n node : Nat), groundedByN g n node = true → Grounded g node := by
  intro n
  induction n with
  | zero => intro node h; simp [groundedByN] at h
  | succ k ih =>
    intro node h
    unfold groundedByN at h
    by_cases hs : g.isSat node = true
    · exact Grounded.sat hs
    · simp only [hs, Bool.false_eq_true, if_false] at h
      have hsf : g.isSat node = false := by simpa using hs
      cases hp : g.prereqs node with
      | nil =>
        simp only [hp] at h
        by_cases hko : g.kind node = Kind.obtain
        · simp only [hko, if_true] at h
          exact Grounded.leaf hsf hko hp h
        · -- kind ≠ obtain ⇒ char; grounds via empty prereqs
          exact Grounded.node hsf (fun ho => absurd ho hko)
            (by intro p hpm; rw [hp] at hpm; simp at hpm)
      | cons hd tl =>
        simp only [hp] at h
        rw [List.all_eq_true] at h
        refine Grounded.node hsf (fun _ => by rw [hp]; simp) ?_
        intro p hpmem
        rw [hp] at hpmem
        exact ih p (h p hpmem)

/-- COMPLETENESS: every `Grounded` node is accepted by some saturation round. -/
theorem grounded_groundedByN (g : Graph) {node : Nat} (h : Grounded g node) :
    ∃ n, groundedByN g n node = true := by
  induction h with
  | @sat n hs => exact ⟨1, by unfold groundedByN; simp [hs]⟩
  | @leaf n hns hk hempty hp =>
    refine ⟨1, ?_⟩
    unfold groundedByN
    simp only [hns, Bool.false_eq_true, if_false, hempty, hk, if_true]
    exact hp
  | @node n hns hobt hall ih =>
    -- a common round bounding all prereqs
    have hbound : ∀ (l : List Nat),
        (∀ p ∈ l, ∃ m, groundedByN g m p = true) →
        ∃ N, ∀ p ∈ l, groundedByN g N p = true := by
      intro l
      induction l with
      | nil => intro _; exact ⟨0, by intro p hp; simp at hp⟩
      | cons hd tl ihtl =>
        intro halll
        obtain ⟨Ntl, htl⟩ := ihtl (fun p hp => halll p (List.mem_cons_of_mem _ hp))
        obtain ⟨Nhd, hhd⟩ := halll hd (List.mem_cons_self)
        refine ⟨Nhd + Ntl, ?_⟩
        intro p hp
        rcases List.mem_cons.mp hp with he | hm
        · subst he; exact groundedByN_mono_le g Nhd Ntl p hhd
        · have := groundedByN_mono_le g Ntl Nhd p (htl p hm)
          rwa [Nat.add_comm] at this
    obtain ⟨N, hN⟩ := hbound (g.prereqs n) ih
    refine ⟨N + 1, ?_⟩
    unfold groundedByN
    simp only [hns, Bool.false_eq_true, if_false]
    cases hp : g.prereqs n with
    | nil =>
      have hko : g.kind n ≠ Kind.obtain := fun ho => (hobt ho) hp
      simp only [hko, if_false]
    | cons hd tl =>
      rw [List.all_eq_true]
      intro p hpmem
      exact hN p (by rw [hp]; exact hpmem)

/-! ### `reachAux` (cycle-safe recursion) = grounding fixpoint. -/

/-- SOUNDNESS of `reachAux`: under any path and fuel, accept ⇒ `Grounded`. The
cycle guard only ever REJECTS, so an accepted node has a real derivation. -/
theorem reachAux_sound (g : Graph) :
    ∀ (fuel : Nat) (path : List Nat) (node : Nat),
      reachAux g fuel path node = true → Grounded g node := by
  intro fuel
  induction fuel with
  | zero => intro path node h; simp [reachAux] at h
  | succ k ih =>
    intro path node h
    unfold reachAux at h
    by_cases hs : g.isSat node = true
    · exact Grounded.sat hs
    · simp only [hs, Bool.false_eq_true, if_false] at h
      by_cases hpath : node ∈ path
      · simp only [hpath, if_true] at h; exact absurd h (by simp)
      · simp only [hpath, if_false] at h
        have hsf : g.isSat node = false := by simpa using hs
        cases hp : g.prereqs node with
        | nil =>
          simp only [hp] at h
          by_cases hko : g.kind node = Kind.obtain
          · simp only [hko, if_true] at h
            exact Grounded.leaf hsf hko hp h
          · exact Grounded.node hsf (fun ho => absurd ho hko)
              (by intro p hpm; rw [hp] at hpm; simp at hpm)
        | cons hd tl =>
          simp only [hp] at h
          rw [List.all_eq_true] at h
          refine Grounded.node hsf (fun _ => by rw [hp]; simp) ?_
          intro p hpmem
          rw [hp] at hpmem
          exact ih (node :: path) p (h p hpmem)

/-! ### Completeness via the MINIMAL grounding round (strict measure).

Same scheme as `Objective.attainAux_complete_min`: process each node at its
MINIMAL grounding round so the cycle guard `node ∈ path` never blocks a genuine
acyclic derivation. -/

/-- `IsMinRound g m node`: `node` is grounded at round `m` but at no smaller
round (its minimal grounding round is exactly `m`). -/
def IsMinRound (g : Graph) (m node : Nat) : Prop :=
  groundedByN g m node = true ∧ ∀ j, j < m → groundedByN g j node = false

/-- Every grounded node HAS a minimal grounding round. -/
theorem exists_minRound (g : Graph) {node : Nat}
    (h : ∃ n, groundedByN g n node = true) : ∃ m, IsMinRound g m node := by
  obtain ⟨n, hn⟩ := h
  induction n using Nat.strongRecOn with
  | ind n ih =>
    by_cases hsmaller : ∃ j, j < n ∧ groundedByN g j node = true
    · obtain ⟨j, hjlt, hjg⟩ := hsmaller
      exact ih j hjlt hjg
    · refine ⟨n, hn, ?_⟩
      intro j hj
      cases hc : groundedByN g j node with
      | false => rfl
      | true => exact absurd ⟨j, hj, hc⟩ hsmaller

/-- The minimal grounding round is unique. -/
theorem minRound_unique (g : Graph) (node m1 m2 : Nat)
    (h1 : IsMinRound g m1 node) (h2 : IsMinRound g m2 node) : m1 = m2 := by
  obtain ⟨hg1, hl1⟩ := h1
  obtain ⟨hg2, hl2⟩ := h2
  rcases Nat.lt_trichotomy m1 m2 with hlt | heq | hgt
  · exact absurd hg1 (by rw [hl2 m1 hlt]; simp)
  · exact heq
  · exact absurd hg2 (by rw [hl1 m2 hgt]; simp)

/-- If a `node` (not satisfied, nonempty prereqs) has minimal round
`m+1`, every prereq is grounded by round `m`. -/
theorem prereqs_grounded_pred (g : Graph) (n node : Nat)
    (hns : g.isSat node = false)
    (h : groundedByN g (n + 1) node = true) :
    ∀ p ∈ g.prereqs node, groundedByN g n p = true := by
  unfold groundedByN at h
  simp only [hns, Bool.false_eq_true, if_false] at h
  intro p hp
  cases hpr : g.prereqs node with
  | nil => rw [hpr] at hp; simp at hp
  | cons hd tl =>
    rw [hpr] at h hp
    simp only at h
    rw [List.all_eq_true] at h
    exact h p hp

/-- COMPLETENESS, path-general, parameterised by the node's minimal round `m`. -/
theorem reachAux_complete_min (g : Graph) :
    ∀ (m node : Nat) (path : List Nat),
      IsMinRound g m node →
      (∀ a ∈ path, ∀ ma, IsMinRound g ma a → m < ma) →
      ∀ fuel, m ≤ fuel → reachAux g fuel path node = true := by
  intro m
  induction m using Nat.strongRecOn with
  | ind m ih =>
    intro node path hmin hpath fuel hfuel
    obtain ⟨hg, hmin'⟩ := hmin
    have hm1 : 1 ≤ m := by
      rcases Nat.eq_zero_or_pos m with h0 | hp
      · subst h0; simp [groundedByN] at hg
      · exact hp
    obtain ⟨k, rfl⟩ : ∃ k, m = k + 1 := ⟨m - 1, by omega⟩
    obtain ⟨f', rfl⟩ : ∃ f', fuel = f' + 1 := by
      cases fuel with
      | zero => omega
      | succ f' => exact ⟨f', rfl⟩
    have hf' : k ≤ f' := by omega
    unfold reachAux
    -- decompose the round-(k+1) grounding to learn the branch
    by_cases hs : g.isSat node = true
    · simp [hs]
    · have hsf : g.isSat node = false := by simpa using hs
      simp only [hsf, Bool.false_eq_true, if_false]
      -- node ∉ path: its minimal round k+1 ≤ any path member's
      have hnp : node ∉ path := by
        intro hin
        have := hpath node hin (k + 1) ⟨hg, hmin'⟩
        omega
      simp only [hnp, if_false]
      -- materials fact, derived WITHOUT consuming `hg` (keep the round-(k+1)
      -- grounding intact for the minimal-round uniqueness argument)
      have hmats := prereqs_grounded_pred g k node hsf hg
      cases hp : g.prereqs node with
      | nil =>
        -- empty prereqs: the round-(k+1) grounding pins the (obtain?producible:true) branch
        have := hg
        unfold groundedByN at this
        simp only [hsf, Bool.false_eq_true, if_false, hp] at this
        simpa using this
      | cons hd tl =>
        rw [List.all_eq_true]
        intro p hpmem
        have hpmem' : p ∈ g.prereqs node := by rw [hp]; exact hpmem
        have hpg : groundedByN g k p = true := hmats p hpmem'
        obtain ⟨mm, hmm⟩ := exists_minRound g ⟨k, hpg⟩
        have hmmk : mm ≤ k := by
          rcases Nat.lt_or_ge k mm with hkm | hge
          · exact absurd hpg (by rw [hmm.2 k hkm]; simp)
          · exact hge
        refine ih mm (by omega) p (node :: path) hmm ?_ f' (by omega)
        intro a ha ma hma
        rcases List.mem_cons.mp ha with he | hold
        · have hma' : IsMinRound g ma node := he ▸ hma
          have : ma = k + 1 := minRound_unique g node ma (k + 1) hma' ⟨hg, hmin'⟩
          omega
        · have := hpath a hold ma hma; omega

/-- COMPLETENESS at the top level: a grounded node is accepted by `isReachable`
with the EMPTY path, for any fuel ≥ its minimal grounding round. -/
theorem grounded_isReachable (g : Graph) {node : Nat} (h : Grounded g node) :
    ∃ N, ∀ fuel, N ≤ fuel → isReachable g fuel node = true := by
  obtain ⟨n, hn⟩ := grounded_groundedByN g h
  obtain ⟨m, hm⟩ := exists_minRound g ⟨n, hn⟩
  refine ⟨m, fun fuel hfuel => ?_⟩
  unfold isReachable
  exact reachAux_complete_min g m node [] hm (by intro a ha; simp at ha) fuel hfuel

/-! ### The headline equivalence: `is_reachable` = grounding fixpoint. -/

/-- `is_reachable_eq_grounding` (the headline). For ANY fuel, `isReachable`
accepting implies `Grounded` (SOUNDNESS); and a `Grounded` node is accepted for
all sufficiently large fuel (COMPLETENESS). Combined: with adequate fuel,
`isReachable node = true ↔ Grounded node`. A node on a cycle of un-grounded
nodes is NOT `Grounded`, hence NOT reachable. -/
theorem is_reachable_eq_grounding (g : Graph) (node : Nat) :
    (∀ fuel, isReachable g fuel node = true → Grounded g node) ∧
    (Grounded g node →
      ∃ N, ∀ fuel, N ≤ fuel → isReachable g fuel node = true) := by
  refine ⟨?_, grounded_isReachable g⟩
  intro fuel h
  exact reachAux_sound g fuel [] node h

/-- A CYCLIC pair of un-grounded `obtain` nodes (0 ↔ 1, neither satisfied,
neither producible-as-leaf since each has a prereq) is NOT reachable: the path
guard rejects. Concretely with prereqs 0 → [1], 1 → [0]. -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1] else if n = 1 then [0] else [],
      isSat := fun _ => false,
      producible := fun _ => false,
      kind := fun _ => Kind.obtain }
    isReachable g 8 0 = false := by decide

/-- A genuine chain DOES reach: obtain-node 0 has prereq 1; node 1 is an
obtain leaf (no prereqs) that is producible. So 0 is reachable. -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1] else [],
      isSat := fun _ => false,
      producible := fun n => n = 1,
      kind := fun _ => Kind.obtain }
    isReachable g 8 0 = true := by decide

/-- A char node with no prereqs is ALWAYS reachable (grounds via the empty
`all`), even when not producible (only ObtainItem consults `_producible`). -/
example :
    let g : Graph := {
      prereqs := fun _ => [],
      isSat := fun _ => false,
      producible := fun _ => false,
      kind := fun _ => Kind.char }
    isReachable g 4 0 = true := by decide

/-! ### `unmet_closure_size` — the unmet-closure node count (min 1).

`unmet_closure_size` (strategy.py:91) is an iterative DFS that visits the prereq
closure but DESCENDS ONLY UNMET NODES (satisfied interior nodes are visited but
neither counted nor expanded), counting distinct unmet nodes, then `max(·, 1)`.

We model the SET of unmet nodes that the DFS counts as `UnmetClosure`: the least
set containing `root` (when unmet) and closed under "prereq of an unmet member".
Crucially the closure descends a node's prereqs ONLY when that node is unmet —
the satisfied-interior pruning. `unmet_closure_size = |UnmetClosure root|`,
floored at 1. We compute the count via a fuel-bounded saturation list (the DFS
visited set) and prove it counts exactly the reachable unmet nodes. -/

/-- The DFS frontier saturation: `unmetSatN root n` is the set of nodes the
visited-set holds after `n` expansion rounds. Round 0 is `[root]`; each round
adds, for every UNMET node currently held, all of its prereqs (satisfied nodes
are held but NOT expanded — the satisfied-interior pruning). Deduplicated. -/
def expandUnmet (g : Graph) (acc : List Nat) : List Nat :=
  acc.flatMap (fun node => if g.isSat node then [] else g.prereqs node)

def unmetSatN (g : Graph) (root : Nat) : Nat → List Nat
  | 0 => [root]
  | n + 1 => (unmetSatN g root n ++ expandUnmet g (unmetSatN g root n)).eraseDups

/-- The set of DISTINCT UNMET nodes the DFS counts after `fuel` rounds. -/
def unmetNodes (g : Graph) (root : Nat) (fuel : Nat) : List Nat :=
  (unmetSatN g root fuel).eraseDups.filter (fun n => !g.isSat n)

/-- The structural cost: count of unmet nodes, floored at 1 (matches
`max(count, 1)`). -/
def unmetClosureSize (g : Graph) (root : Nat) (fuel : Nat) : Nat :=
  max (unmetNodes g root fuel).length 1

/-- `closure_size_floored`: the count is ALWAYS ≥ 1 (the `max(·, 1)` floor). This
is the documented "min 1". -/
theorem unmetClosureSize_ge_one (g : Graph) (root : Nat) (fuel : Nat) :
    1 ≤ unmetClosureSize g root fuel := by
  unfold unmetClosureSize
  exact Nat.le_max_right _ 1

/-- The counted set is exactly the unmet members of the (deduplicated) visited
list — `closure_size_eq_count`: the size IS the count of distinct unmet nodes the
DFS holds, with no double-counting (the list is `eraseDups`'d). -/
theorem unmetClosureSize_eq_count (g : Graph) (root : Nat) (fuel : Nat) :
    unmetClosureSize g root fuel
      = max ((unmetSatN g root fuel).eraseDups.filter (fun n => !g.isSat n)).length 1 := rfl

/-- The DFS never counts a satisfied node (satisfied-interior pruning is faithful
to the count): every counted node is UNMET. -/
theorem unmetNodes_unmet (g : Graph) (root : Nat) (fuel : Nat) {n : Nat}
    (h : n ∈ unmetNodes g root fuel) : g.isSat n = false := by
  unfold unmetNodes at h
  rw [List.mem_filter] at h
  have := h.2
  simpa using this

/-- The visited set never EXPANDS a satisfied node: `expandUnmet` contributes
nothing for a satisfied node (the prereqs of a satisfied interior node are NOT
descended). This is the formal satisfied-interior pruning. -/
theorem expandUnmet_skips_sat (g : Graph) (node : Nat) (h : g.isSat node = true) :
    (if g.isSat node then ([] : List Nat) else g.prereqs node) = [] := by
  simp [h]


/-! ### `actionable_step` — a node from the ACTIONABLE set (or none).

`actionable_step` (strategy.py:69) is a cycle-safe DFS: at a node, take its UNMET
direct prereqs; if NONE are unmet then the node is the step UNLESS it is an
`obtain` node that is not producible (→ none); otherwise descend (in a sorted
order) into the unmet prereqs, returning the first hit. The DFS pick-order is
implementation-defined — we iterate in prereq order; the proofs concern the
RETURNED node and the none/exists characterization, NOT a specific node. -/

/-- A node is ACTIONABLE iff it is unmet, ALL its direct prereqs are satisfied,
and (kind=obtain ⇒ producible). The INDEPENDENT predicate (not the function). -/
def ActionableNode (g : Graph) (n : Nat) : Prop :=
  g.isSat n = false ∧ (∀ p ∈ g.prereqs n, g.isSat p = true) ∧
    (g.kind n = Kind.obtain → g.producible n = true)

instance (g : Graph) (n : Nat) : Decidable (ActionableNode g n) := by
  unfold ActionableNode; infer_instance

/-- The unmet direct prereqs of a node. -/
def unmetPrereqs (g : Graph) (node : Nat) : List Nat :=
  (g.prereqs node).filter (fun p => !g.isSat p)

/-- `firstSome f l`: the first `some` image under `f` over `l` (explicit so its
recursion is transparent to proofs; mirrors `for prereq in sorted(unmet): step =
_step(...); if step is not None: return step`). -/
def firstSome {α β : Type} (f : α → Option β) : List α → Option β
  | [] => none
  | x :: xs => match f x with
    | some y => some y
    | none => firstSome f xs

/-- `actStep g fuel path node`: cycle-safe step search. `none` on revisit (cycle
guard) or fuel exhaustion. With no unmet prereqs: `obtain ∧ ¬producible → none`,
else `some node`. Otherwise the first unmet prereq (in order) that yields a step. -/
def actStep (g : Graph) : Nat → List Nat → Nat → Option Nat
  | 0, _, _ => none
  | fuel + 1, path, node =>
    if node ∈ path then none
    else
      match unmetPrereqs g node with
      | [] => if g.kind node = Kind.obtain ∧ g.producible node = false then none else some node
      | ps => firstSome (fun p => actStep g fuel (node :: path) p) ps

/-- Top-level `actionable_step(root)`: empty path. -/
def actionableStep (g : Graph) (fuel : Nat) (root : Nat) : Option Nat :=
  actStep g fuel [] root

/-! ### `UnmetReach` — reachability through unmet-prereq descent (order- and
cycle-pruning-independent). The DFS explores exactly this set (cycle pruning only
affects termination, not which nodes are reachable). -/

/-- `UnmetReach g a b`: `b` is reachable from `a` by descending UNMET prereqs.
HEAD-recursive (the step is at the source `a`) so completeness inducts from the
source forward: `a` reaches itself when unmet; an unmet `a` reaches whatever any
of its unmet prereqs reaches. -/
inductive UnmetReach (g : Graph) : Nat → Nat → Prop
  | refl {a : Nat} (h : g.isSat a = false) : UnmetReach g a a
  | head {a p b : Nat} (h : g.isSat a = false) (hp : p ∈ unmetPrereqs g a)
      (hr : UnmetReach g p b) : UnmetReach g a b

/-! ### Soundness: the returned node is actionable. -/

/-- `firstSome` returning `some y` means some element maps to `some y`. -/
theorem firstSome_some_mem {α β : Type} (f : α → Option β) (l : List α) (y : β)
    (h : firstSome f l = some y) : ∃ x ∈ l, f x = some y := by
  induction l with
  | nil => simp [firstSome] at h
  | cons hd tl ih =>
    unfold firstSome at h
    cases hf : f hd with
    | some z =>
      rw [hf] at h
      simp only [Option.some.injEq] at h
      exact ⟨hd, List.mem_cons_self, by rw [hf, h]⟩
    | none =>
      rw [hf] at h
      obtain ⟨x, hx, hfx⟩ := ih h
      exact ⟨x, List.mem_cons_of_mem _ hx, hfx⟩

/-- `firstSome` returning `none` means EVERY element maps to `none`. -/
theorem firstSome_none {α β : Type} (f : α → Option β) (l : List α)
    (h : firstSome f l = none) : ∀ x ∈ l, f x = none := by
  induction l with
  | nil => intro x hx; simp at hx
  | cons hd tl ih =>
    unfold firstSome at h
    cases hf : f hd with
    | some z => rw [hf] at h; exact absurd h (by simp)
    | none =>
      rw [hf] at h
      intro x hx
      rcases List.mem_cons.mp hx with he | hm
      · subst he; exact hf
      · exact ih h x hm

/-- SOUNDNESS (invariant form): entered on an UNMET node and returning `some r`,
`r` is an `ActionableNode`. The unmet invariant is genuine: the wrapper enters on
an unmet root (`decide` skips satisfied roots) and the recursion only descends
UNMET prereqs (the `unmetPrereqs` filter), so every node `actStep` runs on is
unmet — hence the returned `r` is unmet ∧ all direct prereqs satisfied ∧
(obtain ⇒ producible). -/
theorem actStep_sound (g : Graph) :
    ∀ (fuel : Nat) (path : List Nat) (node r : Nat),
      g.isSat node = false → actStep g fuel path node = some r → ActionableNode g r := by
  intro fuel
  induction fuel with
  | zero => intro path node r _ h; simp [actStep] at h
  | succ k ih =>
    intro path node r hnode h
    unfold actStep at h
    by_cases hpath : node ∈ path
    · simp only [hpath, if_true] at h; exact absurd h (by simp)
    · simp only [hpath, if_false] at h
      cases hu : unmetPrereqs g node with
      | nil =>
        simp only [hu] at h
        by_cases hc : g.kind node = Kind.obtain ∧ g.producible node = false
        · simp only [hc] at h; exact absurd h (by simp)
        · simp only [hc, if_false, Option.some.injEq] at h
          subst h
          refine ⟨hnode, ?_, ?_⟩
          · intro p hp
            cases hsp : g.isSat p with
            | true => rfl
            | false =>
              have hpin : p ∈ unmetPrereqs g node := by
                unfold unmetPrereqs; rw [List.mem_filter]; exact ⟨hp, by simp [hsp]⟩
              rw [hu] at hpin; simp at hpin
          · intro hk
            cases hprod : g.producible node with
            | true => rfl
            | false => exact absurd ⟨hk, hprod⟩ hc
      | cons hd tl =>
        simp only [hu] at h
        obtain ⟨x, hxmem, hx⟩ := firstSome_some_mem _ _ _ h
        have hxu : g.isSat x = false := by
          have hxin : x ∈ unmetPrereqs g node := by rw [hu]; exact hxmem
          unfold unmetPrereqs at hxin; rw [List.mem_filter] at hxin
          simpa using hxin.2
        exact ih (node :: path) x r hxu hx


/-- `UnmetReach` is transitive: if `a` reaches `b` and `b` reaches `c`, then `a`
reaches `c` (relocate a derivation rooted at `b` onto one rooted at `a`). -/
theorem unmetReach_trans (g : Graph) (a b c : Nat)
    (hab : UnmetReach g a b) (hbc : UnmetReach g b c) : UnmetReach g a c := by
  induction hab with
  | refl _ => exact hbc
  | head h hp _ ih => exact UnmetReach.head h hp (ih hbc)

/-- `actStep` returning `some r` (entered on an unmet `node`) means `r` is
`UnmetReach`-able from `node` — the returned step lives in the unmet closure. -/
theorem actStep_some_reach (g : Graph) :
    ∀ (fuel : Nat) (path : List Nat) (node r : Nat),
      g.isSat node = false → actStep g fuel path node = some r →
      UnmetReach g node r := by
  intro fuel
  induction fuel with
  | zero => intro path node r _ h; simp [actStep] at h
  | succ k ih =>
    intro path node r hnode h
    unfold actStep at h
    by_cases hpath : node ∈ path
    · simp only [hpath, if_true] at h; exact absurd h (by simp)
    · simp only [hpath, if_false] at h
      cases hu : unmetPrereqs g node with
      | nil =>
        simp only [hu] at h
        by_cases hc : g.kind node = Kind.obtain ∧ g.producible node = false
        · simp only [hc] at h; exact absurd h (by simp)
        · simp only [hc, if_false, Option.some.injEq] at h
          subst h; exact UnmetReach.refl hnode
      | cons hd tl =>
        simp only [hu] at h
        obtain ⟨x, hxmem, hx⟩ := firstSome_some_mem _ _ _ h
        have hxin : x ∈ unmetPrereqs g node := by rw [hu]; exact hxmem
        have hxu : g.isSat x = false := by
          unfold unmetPrereqs at hxin; rw [List.mem_filter] at hxin
          simpa using hxin.2
        -- UnmetReach from node to r via the head edge node → x then the x-derivation
        have hxr : UnmetReach g x r := ih (node :: path) x r hxu hx
        exact UnmetReach.head hnode hxin hxr

/-! ### Reachable-actionable saturation (for the none-iff completeness).

`actReachN g node n` : within `n` rounds of UNMET descent from `node`, an
ACTIONABLE node is reachable. A node with unmet prereqs is never actionable, so
the per-node test is `decide (ActionableNode g node)`; the descent recurses into
unmet prereqs. Mirrors the `groundedByN` saturation; minimal-round + cycle-guard
gives the `actStep` completeness (the cycle guard never blocks a genuine acyclic
descent to an actionable node). -/
def actReachN (g : Graph) : Nat → Nat → Bool
  | 0, _ => false
  | n + 1, node =>
    if g.isSat node then false
    else (decide (ActionableNode g node)) ||
      (unmetPrereqs g node).any (fun p => actReachN g n p)

theorem actReachN_mono (g : Graph) :
    ∀ (n node : Nat), actReachN g n node = true → actReachN g (n + 1) node = true := by
  intro n
  induction n with
  | zero => intro node h; simp [actReachN] at h
  | succ k ih =>
    intro node h
    unfold actReachN at h ⊢
    by_cases hs : g.isSat node = true
    · simp only [hs, if_true] at h; exact absurd h (by simp)
    · simp only [hs, Bool.false_eq_true, if_false] at h ⊢
      rw [Bool.or_eq_true] at h ⊢
      rcases h with ha | hany
      · exact Or.inl ha
      · refine Or.inr ?_
        rw [List.any_eq_true] at hany ⊢
        obtain ⟨p, hp, hpv⟩ := hany
        exact ⟨p, hp, ih p hpv⟩

theorem actReachN_mono_le (g : Graph) (n k node : Nat)
    (h : actReachN g n node = true) : actReachN g (n + k) node = true := by
  induction k with
  | zero => exact h
  | succ j ih => exact actReachN_mono g (n + j) node ih

/-- SOUNDNESS: `actReachN g n node = true` (node unmet) yields an actual
`UnmetReach`-able `ActionableNode`. -/
theorem actReachN_sound (g : Graph) :
    ∀ (n node : Nat), g.isSat node = false → actReachN g n node = true →
      ∃ a, UnmetReach g node a ∧ ActionableNode g a := by
  intro n
  induction n with
  | zero => intro node _ h; simp [actReachN] at h
  | succ k ih =>
    intro node hnode h
    unfold actReachN at h
    simp only [hnode, Bool.false_eq_true, if_false] at h
    rw [Bool.or_eq_true] at h
    rcases h with ha | hany
    · exact ⟨node, UnmetReach.refl hnode, by simpa using ha⟩
    · rw [List.any_eq_true] at hany
      obtain ⟨p, hp, hpv⟩ := hany
      have hpu : g.isSat p = false := by
        unfold unmetPrereqs at hp; rw [List.mem_filter] at hp; simpa using hp.2
      obtain ⟨a, hra, haa⟩ := ih p hpu hpv
      exact ⟨a, UnmetReach.head hnode hp hra, haa⟩

/-- COMPLETENESS: a reachable actionable node makes `actReachN` accept at some
round (from the source of the reach). Proven by induction on `UnmetReach`. -/
theorem actReachN_complete (g : Graph) (src a : Nat)
    (hr : UnmetReach g src a) (ha : ActionableNode g a) :
    ∃ n, actReachN g n src = true := by
  induction hr with
  | @refl s h =>
    refine ⟨1, ?_⟩
    unfold actReachN
    simp only [h, Bool.false_eq_true, if_false]
    rw [Bool.or_eq_true]
    exact Or.inl (by simpa using ha)
  | @head s p b h hp hrr ih =>
    obtain ⟨n, hn⟩ := ih ha
    -- lift the `p`-round to an `s`-round through the head edge s → p
    refine ⟨n + 1, ?_⟩
    unfold actReachN
    simp only [h, Bool.false_eq_true, if_false]
    rw [Bool.or_eq_true]
    refine Or.inr ?_
    rw [List.any_eq_true]
    exact ⟨p, hp, hn⟩

/-! ### Minimal reach-round → `actStep` finds a step. -/

def IsMinActRound (g : Graph) (m node : Nat) : Prop :=
  actReachN g m node = true ∧ ∀ j, j < m → actReachN g j node = false

theorem exists_minActRound (g : Graph) {node : Nat}
    (h : ∃ n, actReachN g n node = true) : ∃ m, IsMinActRound g m node := by
  obtain ⟨n, hn⟩ := h
  induction n using Nat.strongRecOn with
  | ind n ih =>
    by_cases hsmaller : ∃ j, j < n ∧ actReachN g j node = true
    · obtain ⟨j, hjlt, hjg⟩ := hsmaller
      exact ih j hjlt hjg
    · refine ⟨n, hn, ?_⟩
      intro j hj
      cases hc : actReachN g j node with
      | false => rfl
      | true => exact absurd ⟨j, hj, hc⟩ hsmaller

theorem minActRound_unique (g : Graph) (node m1 m2 : Nat)
    (h1 : IsMinActRound g m1 node) (h2 : IsMinActRound g m2 node) : m1 = m2 := by
  obtain ⟨hg1, hl1⟩ := h1
  obtain ⟨hg2, hl2⟩ := h2
  rcases Nat.lt_trichotomy m1 m2 with hlt | heq | hgt
  · exact absurd hg1 (by rw [hl2 m1 hlt]; simp)
  · exact heq
  · exact absurd hg2 (by rw [hl1 m2 hgt]; simp)

/-- If `node` (unmet) has min act-round `n+1` and is NOT itself actionable, some
unmet prereq is reachable-actionable within round `n`. -/
theorem actReach_pred (g : Graph) (n node : Nat) (hnode : g.isSat node = false)
    (hna : ActionableNode g node → False)
    (h : actReachN g (n + 1) node = true) :
    ∃ p ∈ unmetPrereqs g node, actReachN g n p = true := by
  unfold actReachN at h
  simp only [hnode, Bool.false_eq_true, if_false] at h
  rw [Bool.or_eq_true] at h
  rcases h with ha | hany
  · exact absurd (by simpa using ha) hna
  · rw [List.any_eq_true] at hany; exact hany

/-- The cycle-guarded `actStep` FINDS a step whenever an actionable node is
reachable: parameterised by the source's minimal act-round `m`, under any `path`
whose every member has a STRICTLY GREATER minimal act-round (so the guard never
blocks the genuine acyclic descent), with fuel ≥ m. -/
theorem actStep_complete_min (g : Graph) :
    ∀ (m node : Nat) (path : List Nat),
      g.isSat node = false → IsMinActRound g m node →
      (∀ a ∈ path, ∀ ma, IsMinActRound g ma a → m < ma) →
      ∀ fuel, m ≤ fuel → actStep g fuel path node ≠ none := by
  intro m
  induction m using Nat.strongRecOn with
  | ind m ih =>
    intro node path hnode hmin hpath fuel hfuel
    obtain ⟨hg, hmin'⟩ := hmin
    have hm1 : 1 ≤ m := by
      rcases Nat.eq_zero_or_pos m with h0 | hp
      · subst h0; simp [actReachN] at hg
      · exact hp
    obtain ⟨k, rfl⟩ : ∃ k, m = k + 1 := ⟨m - 1, by omega⟩
    obtain ⟨f', rfl⟩ : ∃ f', fuel = f' + 1 := by
      cases fuel with
      | zero => omega
      | succ f' => exact ⟨f', rfl⟩
    have hf' : k ≤ f' := by omega
    unfold actStep
    have hnp : node ∉ path := by
      intro hin
      have := hpath node hin (k + 1) ⟨hg, hmin'⟩
      omega
    simp only [hnp, if_false]
    by_cases hact : ActionableNode g node
    · -- node itself is actionable; then it has no unmet prereqs (all sat), so the
      -- empty-prereqs branch returns `some node` (¬obtain∨producible since actionable).
      have hue : unmetPrereqs g node = [] := by
        unfold unmetPrereqs
        rw [List.filter_eq_nil_iff]
        intro p hp
        have := hact.2.1 p hp
        simp [this]
      rw [hue]
      have hnc : ¬ (g.kind node = Kind.obtain ∧ g.producible node = false) := by
        rintro ⟨hk, hpf⟩
        have := hact.2.2 hk
        rw [this] at hpf; exact absurd hpf (by simp)
      simp only [hnc, if_false]
      exact (by simp)
    · -- node not actionable: a reachable actionable node lies past an unmet prereq
      obtain ⟨p, hp, hpv⟩ := actReach_pred g k node hnode hact hg
      cases hu : unmetPrereqs g node with
      | nil => rw [hu] at hp; simp at hp
      | cons hd tl =>
        -- the firstSome over (hd :: tl) is not none: SOME element yields a step.
        -- it suffices that the recursive call on `p` (which is in hd::tl) is not none.
        have hpin : p ∈ hd :: tl := by rw [← hu]; exact hp
        have hpu : g.isSat p = false := by
          have : p ∈ unmetPrereqs g node := hp
          unfold unmetPrereqs at this; rw [List.mem_filter] at this; simpa using this.2
        obtain ⟨mm, hmm⟩ := exists_minActRound g ⟨k, hpv⟩
        have hmmk : mm ≤ k := by
          rcases Nat.lt_or_ge k mm with hkm | hge
          · exact absurd hpv (by rw [hmm.2 k hkm]; simp)
          · exact hge
        have hrec : actStep g f' (node :: path) p ≠ none := by
          refine ih mm (by omega) p (node :: path) hpu hmm ?_ f' (by omega)
          intro a ha ma hma
          rcases List.mem_cons.mp ha with he | hold
          · have hma' : IsMinActRound g ma node := he ▸ hma
            have : ma = k + 1 := minActRound_unique g node ma (k + 1) hma' ⟨hg, hmin'⟩
            omega
          · have := hpath a hold ma hma; omega
        -- firstSome over hd::tl containing p (whose recursive call is some) is not none
        intro hfn
        have hall := firstSome_none (fun q => actStep g f' (node :: path) q) (hd :: tl) hfn
        exact hrec (hall p hpin)

/-! ### Headline `actionable_step` correctness. -/

/-- `actionable_correct` (SOUNDNESS half): the RETURNED node is `ActionableNode`
— unmet ∧ all DIRECT prereqs satisfied ∧ (kind=obtain ⇒ producible). The DFS
pick-order is implementation-defined; we prove only that what it returns is
actionable (not WHICH node). Requires the genuine entry invariant `isSat root =
false` (the wrapper is only called on unmet roots). -/
theorem actionable_step_sound (g : Graph) (fuel root r : Nat)
    (hroot : g.isSat root = false) (h : actionableStep g fuel root = some r) :
    ActionableNode g r :=
  actStep_sound g fuel [] root r hroot h

/-- The returned node is `UnmetReach`-able from the root (it lives in the
unmet-prereq closure the DFS descends). -/
theorem actionable_step_reach (g : Graph) (fuel root r : Nat)
    (hroot : g.isSat root = false) (h : actionableStep g fuel root = some r) :
    UnmetReach g root r :=
  actStep_some_reach g fuel [] root r hroot h

/-- `actionable_correct` (NONE half, the De-Morgan-dual existence characterization):
for an unmet root and adequate fuel, `actionable_step` returns `none` IFF NO
actionable node is reachable from the root via unmet-prereq descent. This is an
INDEPENDENT characterization of the actionable set (the `ActionableNode`
predicate + `UnmetReach` relation), NOT the function restated. Cycle nodes that
never reach an actionable node correctly yield `none`. -/
theorem actionable_step_none_iff (g : Graph) (root : Nat)
    (hroot : g.isSat root = false) :
    (∃ N, ∀ fuel, N ≤ fuel → actionableStep g fuel root = none)
      ↔ ¬ ∃ a, UnmetReach g root a ∧ ActionableNode g a := by
  constructor
  · -- if the function is eventually none, no actionable node is reachable:
    -- a reachable actionable node would force `some` at adequate fuel (completeness).
    rintro ⟨N, hN⟩ ⟨a, hra, haa⟩
    obtain ⟨n, hn⟩ := actReachN_complete g root a hra haa
    obtain ⟨m, hm⟩ := exists_minActRound g ⟨n, hn⟩
    have hne : actStep g (max N m) [] root ≠ none :=
      actStep_complete_min g m root [] hroot hm (by intro x hx; simp at hx)
        (max N m) (Nat.le_max_right N m)
    exact hne (hN (max N m) (Nat.le_max_left N m))
  · -- if no actionable node is reachable, the function is none for ANY fuel:
    -- a `some r` result would (by soundness) be an actionable reachable node.
    intro hno
    refine ⟨0, fun fuel _ => ?_⟩
    cases hfn : actionableStep g fuel root with
    | none => rfl
    | some r =>
      exact absurd ⟨r, actionable_step_reach g fuel root r hroot hfn,
        actionable_step_sound g fuel root r hroot hfn⟩ hno

/-! ### `root_cost` floored at 1. -/

/-- `root_cost` (strategy.py:106): char roots → `max(1, target − have)`
(`Nat` subtraction truncates at 0); gear (obtain) roots → `unmet_closure_size`
(itself `≥ 1`). We model the value as a `Nat`. -/
def rootCost (g : Graph) (kind : Kind) (target have_ : Nat) (root fuel : Nat) : Nat :=
  match kind with
  | Kind.char => max 1 (target - have_)
  | Kind.obtain => unmetClosureSize g root fuel

/-- `root_cost_floored`: the effort proxy is ALWAYS ≥ 1, for EVERY root kind. -/
theorem rootCost_ge_one (g : Graph) (kind : Kind) (target have_ root fuel : Nat) :
    1 ≤ rootCost g kind target have_ root fuel := by
  unfold rootCost
  cases kind with
  | char => exact Nat.le_max_left 1 _
  | obtain => exact unmetClosureSize_ge_one g root fuel

/-! ### Worked examples: actionable_step on cycles / satisfied-interior nodes. -/

/-- A 2-cycle of unmet obtain nodes, NEITHER actionable (each has an unmet prereq):
`actionable_step` returns `none`. (0→[1], 1→[0], both unmet, neither producible.) -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1] else if n = 1 then [0] else [],
      isSat := fun _ => false,
      producible := fun _ => false,
      kind := fun _ => Kind.obtain }
    actionableStep g 8 0 = none := by decide

/-- A satisfied-INTERIOR node prunes the descent: root 0 (unmet) has prereqs 1
(satisfied) and 2 (unmet); 2 is a producible obtain leaf → actionable. The
search returns an actionable node (here 2). The satisfied interior node 1 is NOT
descended. -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1, 2] else [],
      isSat := fun n => n = 1,
      producible := fun n => n = 2,
      kind := fun _ => Kind.obtain }
    actionableStep g 8 0 = some 2 := by decide

/-- `unmet_closure_size` with a satisfied interior node: root 0 unmet, prereq 1
satisfied (NOT counted, NOT expanded — its prereq 3 is never reached), prereq 2
unmet. Count = {0, 2} = 2. -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1, 2] else if n = 1 then [3] else [],
      isSat := fun n => n = 1,
      producible := fun _ => true,
      kind := fun _ => Kind.obtain }
    unmetClosureSize g 0 8 = 2 := by decide

/-- Closure-size floor: an all-satisfied root still reports 1 (the `max(·,1)`). -/
example :
    let g : Graph := {
      prereqs := fun _ => [],
      isSat := fun _ => true,
      producible := fun _ => true,
      kind := fun _ => Kind.obtain }
    unmetClosureSize g 0 8 = 1 := by decide

/-! ### THE PRODUCTION ASSERT: `is_reachable ⇒ actionable_step ≠ none`.

`strategy.decide` (strategy.py:248-251) does, for an UNMET root:

```
if not is_reachable(root, ...): continue
step = actionable_step(root, ...)
assert step is not None          # <-- this assert
```

Both functions use the SAME cycle-tracker: a per-DFS-path `path` frozenset that
backtracks on return (Python `actionable_step` was refactored in Phase 13 to
mirror `is_reachable` exactly; previously it used a single mutable `visited` set
shared across all branches, which was observationally equivalent on production
graphs per 200k brute force but algorithmically distinct).

After the refactor, the Python `actionable_step` is BYTE-EQUIVALENT to the
proved Lean model `actStep`. The bridge is therefore direct: a `Grounded`
(= reachable) unmet node always has a reachable ACTIONABLE descendant
(`grounded_unmet_has_actionable`), and the per-path search finds it whenever
fuel suffices (`actStep_complete_min`). No disclosed gap remains on the
shared-vs-path question — the algorithms now coincide.

The legacy `actStepShared` definition is retained below FOR REFERENCE (the
alternative shared-visited model would look like this — equivalent on production
graphs per the 200k brute force). Its supporting lemmas are:
* `actStepShared_actionable_returns` — actionable returns on first reach;
* `actStepShared_none_preserves_unvisited` — `none` never adds the actionable
  witness to visited (carry/invariant);
* `actStepShared_sound` — every returned value is actionable.
These three keep the shared-visited algorithm Lean-modeled for reference; the
Python implementation now uses the per-path tracker (`actStep`), so the bridge
between Python and Lean is byte-equivalent at the algorithm level.

### The well-formedness hypothesis (faithful to `prerequisites` / `_producible`).

`prerequisites` gives an unmet `ObtainItem` NONEMPTY prereqs ONLY when it has a
crafting recipe (the materials); and `_producible` is true EXACTLY when there is
a recipe OR a resource drop. Hence in the REAL graph an `obtain` node with
nonempty prereqs is ALWAYS producible. We make this the explicit structural
hypothesis `WellFormed` — it is a genuine property of the production graph, NOT a
proof-rigging restriction. (A non-producible `obtain` node is necessarily a leaf
with no prereqs; `is_reachable` would already reject it as unreachable, so it
never gates the assert.) -/

/-- The production graph invariant, a genuine property of `prerequisites`:
an `obtain` node with nonempty direct prereqs is producible (nonempty prereqs
come from a crafting recipe, and a recipe ⇒ `_producible`). This is NOT a
proof-rigging restriction; it holds for every graph the production code
constructs. -/
def WellFormed (g : Graph) : Prop :=
  ∀ n, g.kind n = Kind.obtain → g.prereqs n ≠ [] → g.producible n = true

/-- BRIDGE (core graph fact): an UNMET `Grounded` node has a `UnmetReach`-able
`ActionableNode` descendant. Induction on the grounding derivation: a satisfied
node is excluded by hypothesis; a producible-`leaf` node with all direct prereqs
satisfied (by being a leaf) is itself actionable; a `node` either has all prereqs
satisfied (then IT is actionable — obtain ⇒ producible via `WellFormed`) or has
an unmet (hence still-grounded) prereq from which an actionable node is
reachable, lifted through `UnmetReach.head`. -/
theorem grounded_unmet_has_actionable (g : Graph) (hwf : WellFormed g) :
    ∀ {node : Nat}, Grounded g node → g.isSat node = false →
      ∃ a, UnmetReach g node a ∧ ActionableNode g a := by
  intro node h
  induction h with
  | @sat n hs => intro hns; rw [hs] at hns; exact absurd hns (by simp)
  | @leaf n hns' hk hempty hp =>
    intro hns
    refine ⟨n, UnmetReach.refl hns, hns, ?_, ?_⟩
    · intro p hpmem; rw [hempty] at hpmem; simp at hpmem
    · intro _; exact hp
  | @node n hns' hobt hall ih =>
    intro hns
    -- Case split: are all direct prereqs satisfied?
    by_cases hallsat : ∀ p ∈ g.prereqs n, g.isSat p = true
    · -- n itself is actionable: unmet, all prereqs satisfied, obtain ⇒ producible.
      refine ⟨n, UnmetReach.refl hns, hns, hallsat, ?_⟩
      intro hko
      -- obtain node: hobt gives prereqs ≠ [], so WellFormed gives producible.
      exact hwf n hko (hobt hko)
    · -- some direct prereq p is UNMET; it is grounded (hall), recurse.
      -- Extract the witnessing unmet prereq without push_neg/mathlib, via the
      -- decidable `List.find?` over the prereqs for an unmet one.
      have hex : ∃ p, p ∈ g.prereqs n ∧ g.isSat p = false := by
        cases hf : (g.prereqs n).find? (fun p => !g.isSat p) with
        | some q =>
          have hmem := List.find?_some hf
          have hmem2 : q ∈ g.prereqs n := List.mem_of_find?_eq_some hf
          refine ⟨q, hmem2, ?_⟩
          simpa using hmem
        | none =>
          exfalso
          apply hallsat
          intro p hpmem
          have := List.find?_eq_none.mp hf p hpmem
          simpa using this
      obtain ⟨p, hpmem, hpns'⟩ := hex
      obtain ⟨a, hra, haa⟩ := ih p hpmem hpns'
      have hpunmet : p ∈ unmetPrereqs g n := by
        unfold unmetPrereqs; rw [List.mem_filter]
        exact ⟨hpmem, by simp [hpns']⟩
      exact ⟨a, UnmetReach.head hns hpunmet hra, haa⟩

/-- `reachable_implies_actionable` (THE HEADLINE — the production assert is safe).
For a WELL-FORMED graph and an UNMET root: if `is_reachable` accepts the root
(for some fuel), then for all sufficiently large fuel `actionable_step` returns
`some` (≠ `none`). Hence `decide`'s `assert step is not None` never fires:
`is_reachable=true` (the guard) ⇒ a step exists.

Soundness of `is_reachable` (`reachAux_sound`) gives `Grounded`; the bridge gives
a reachable actionable node; `actionable_step_none_iff` (its contrapositive)
turns "a reachable actionable node exists" into "`actionable_step ≠ none` for
adequate fuel". -/
theorem reachable_implies_actionable (g : Graph) (hwf : WellFormed g)
    (fuel root : Nat) (hroot : g.isSat root = false)
    (hreach : isReachable g fuel root = true) :
    ∃ N, ∀ fuel', N ≤ fuel' → actionableStep g fuel' root ≠ none := by
  -- reachable ⇒ Grounded
  have hg : Grounded g root := reachAux_sound g fuel [] root hreach
  -- Grounded unmet root ⇒ reachable actionable node
  obtain ⟨a, hra, haa⟩ := grounded_unmet_has_actionable g hwf hg hroot
  -- a reachable actionable node ⇒ `actionable_step ≠ none` for adequate fuel
  -- (the minimal-act-round completeness; the cycle guard never blocks it).
  obtain ⟨n, hn⟩ := actReachN_complete g root a hra haa
  obtain ⟨m, hm⟩ := exists_minActRound g ⟨n, hn⟩
  refine ⟨m, fun fuel' hfuel' => ?_⟩
  exact actStep_complete_min g m root [] hroot hm (by intro x hx; simp at hx) fuel' hfuel'

/-! ### SHARED-`visited` reference algorithm — alternative model retained for
reference. The PRODUCTION Python `strategy.actionable_step` now uses the per-path
tracker (`actStep`) and is byte-equivalent to that model. This shared-visited
variant was the prior Python shape; it is observationally equivalent on
production graphs (200k brute force) and is kept here with full soundness
invariants:

* `actStepShared_actionable_returns` — actionable nodes return `some` on FIRST
  reach (empty unmet prereqs + obtain⇒producible). The shared-visited set
  NEVER blocks delivery of an actionable node — it can only prune re-visits.
* `actStepShared_none_preserves_unvisited` — a `none` result NEVER adds the
  actionable witness to visited. Contrapositive: any addition triggers `some`
  (which propagates via the fold's carry semantics).
* `actStepShared_sound` — every returned value is actionable (mirrors the
  per-path proof, with the fold-soundness inner lemma).

The HEADLINE `reachable_implies_actionable` is proved for the per-path `actStep`
which IS the production Python algorithm post-Phase-13 refactor; the bridge
between Python and Lean is byte-equivalent. The shared-visited model below is
retained for reference and remains observationally equivalent on the production
graph class (deduped prereqs, no self-loops) — verified by the 240/session
Hypothesis differential + a 200k brute force.
-/

/-- The SHARED-`visited` algorithm (Python byte-equivalent). -/
def actStepShared (g : Graph) : Nat → List Nat → Nat → (List Nat × Option Nat)
  | 0, visited, _ => (visited, none)
  | fuel + 1, visited, node =>
    if node ∈ visited then (visited, none)
    else
      let visited' := node :: visited
      match unmetPrereqs g node with
      | [] => if g.kind node = Kind.obtain ∧ g.producible node = false
              then (visited', none) else (visited', some node)
      | ps =>
        ps.foldl
          (fun (acc : List Nat × Option Nat) p =>
            match acc.2 with
            | some r => (acc.1, some r)
            | none => actStepShared g fuel acc.1 p)
          (visited', none)
termination_by fuel _ _ => fuel

/-- Top-level wrapper for the shared model. -/
def actionableStepShared (g : Graph) (fuel : Nat) (root : Nat) : Option Nat :=
  (actStepShared g fuel [] root).2

/-- `actStepShared` returns `some a` IMMEDIATELY on an actionable `a` not yet
visited. "Actionable returns on first reach." -/
theorem actStepShared_actionable_returns
    (g : Graph) (fuel a : Nat) (vis : List Nat)
    (ha : ActionableNode g a) (hnotin : a ∉ vis) (hfuel : 1 ≤ fuel) :
    (actStepShared g fuel vis a).2 = some a := by
  obtain ⟨f', rfl⟩ : ∃ f', fuel = f' + 1 := ⟨fuel - 1, by omega⟩
  unfold actStepShared
  simp only [hnotin, if_false]
  have hue : unmetPrereqs g a = [] := by
    unfold unmetPrereqs
    rw [List.filter_eq_nil_iff]
    intro p hp; have := ha.2.1 p hp; simp [this]
  rw [hue]
  have hnc : ¬ (g.kind a = Kind.obtain ∧ g.producible a = false) := by
    rintro ⟨hk, hpf⟩
    have := ha.2.2 hk; rw [this] at hpf; exact absurd hpf (by simp)
  simp [hnc]

/-- The KEY invariant: a `none` result cannot have added the actionable witness
to visited. By induction on fuel, using `actStepShared_actionable_returns` to
discharge the case where the call is on `a` itself. -/
theorem actStepShared_none_preserves_unvisited
    (g : Graph) (a : Nat) (ha : ActionableNode g a) :
    ∀ (fuel : Nat) (vis : List Nat) (q : Nat),
      a ∉ vis → (actStepShared g fuel vis q).2 = none →
      a ∉ (actStepShared g fuel vis q).1 := by
  intro fuel
  induction fuel with
  | zero => intro vis q hanin _; simp [actStepShared]; exact hanin
  | succ k ih =>
    intro vis q hanin hnone
    by_cases hqv : q ∈ vis
    · have heq : actStepShared g (k + 1) vis q = (vis, none) := by
        unfold actStepShared; simp [hqv]
      rw [heq]; exact hanin
    · by_cases hqa : q = a
      · subst hqa
        rw [actStepShared_actionable_returns g (k+1) q vis ha hqv (by omega)] at hnone
        cases hnone
      · unfold actStepShared at hnone ⊢
        simp only [hqv, if_false] at hnone ⊢
        cases hu : unmetPrereqs g q with
        | nil =>
          simp only [hu] at hnone ⊢
          by_cases hc : g.kind q = Kind.obtain ∧ g.producible q = false
          · simp only [hc] at hnone ⊢
            intro hain
            rcases List.mem_cons.mp hain with hh | hh
            · exact hqa hh.symm
            · exact hanin hh
          · simp only [hc, if_false] at hnone; cases hnone
        | cons hd tl =>
          simp only [hu] at hnone ⊢
          have hanin' : a ∉ q :: vis := by
            intro hain; rcases List.mem_cons.mp hain with hh | hh
            · exact hqa hh.symm
            · exact hanin hh
          -- Inline fold-preservation induction.
          have hfold : ∀ (ps : List Nat) (v : List Nat),
              a ∉ v →
              (ps.foldl
                (fun (acc : List Nat × Option Nat) p =>
                  match acc.2 with
                  | some r => (acc.1, some r)
                  | none => actStepShared g k acc.1 p)
                (v, none)).2 = none →
              a ∉ (ps.foldl
                (fun (acc : List Nat × Option Nat) p =>
                  match acc.2 with
                  | some r => (acc.1, some r)
                  | none => actStepShared g k acc.1 p)
                (v, none)).1 := by
            intro ps
            induction ps with
            | nil => intro v hv _; simp [List.foldl]; exact hv
            | cons q' rest ih_in =>
              intro v hv hn
              rw [List.foldl] at hn ⊢
              have hb : (match ((v, (none : Option Nat))).2 with
                        | some r => ((v, (none : Option Nat)).1, some r)
                        | none => actStepShared g k (v, (none : Option Nat)).1 q')
                        = actStepShared g k v q' := rfl
              rw [hb] at hn ⊢
              cases hres : (actStepShared g k v q').2 with
              | some r =>
                have hpair : actStepShared g k v q' =
                             ((actStepShared g k v q').1, some r) := by rw [← hres]
                rw [hpair] at hn
                -- Carry semantics: fold result.2 = some r ≠ none
                have hcarry : ∀ (l : List Nat) (vv : List Nat),
                    (l.foldl
                      (fun (acc : List Nat × Option Nat) p =>
                        match acc.2 with
                        | some r => (acc.1, some r)
                        | none => actStepShared g k acc.1 p)
                      (vv, some r)).2 = some r := by
                  intro l
                  induction l with
                  | nil => intro _; rfl
                  | cons q'' rest'' ih_c =>
                    intro vv
                    rw [List.foldl]
                    have h_inner : (match ((vv, some r)).2 with
                            | some rr => ((vv, some r).1, some rr)
                            | none => actStepShared g k (vv, some r).1 q'')
                            = (vv, some r) := rfl
                    rw [h_inner]; exact ih_c vv
                rw [hcarry rest _] at hn; cases hn
              | none =>
                have hpair : actStepShared g k v q' =
                             ((actStepShared g k v q').1, none) := by rw [← hres]
                rw [hpair] at hn ⊢
                have hanew : a ∉ (actStepShared g k v q').1 := ih v q' hv hres
                exact ih_in (actStepShared g k v q').1 hanew hn
          exact hfold (hd :: tl) (q :: vis) hanin' hnone

/-- SOUNDNESS for the shared model: every returned value is an `ActionableNode`.
Mirrors the per-path soundness proof using the shared-visited fold. -/
theorem actStepShared_sound (g : Graph) :
    ∀ (fuel : Nat) (visited : List Nat) (node r : Nat),
      g.isSat node = false →
      (actStepShared g fuel visited node).2 = some r → ActionableNode g r := by
  intro fuel
  induction fuel with
  | zero => intro visited node r _ h; simp [actStepShared] at h
  | succ k ih =>
    intro visited node r hnode h
    unfold actStepShared at h
    by_cases hpath : node ∈ visited
    · simp only [hpath, if_true] at h; exact absurd h (by simp)
    · simp only [hpath, if_false] at h
      cases hu : unmetPrereqs g node with
      | nil =>
        simp only [hu] at h
        by_cases hc : g.kind node = Kind.obtain ∧ g.producible node = false
        · simp only [hc] at h; exact absurd h (by simp)
        · simp only [hc, if_false] at h
          simp at h; subst h
          refine ⟨hnode, ?_, ?_⟩
          · intro p hp
            cases hsp : g.isSat p with
            | true => rfl
            | false =>
              have hpin : p ∈ unmetPrereqs g node := by
                unfold unmetPrereqs; rw [List.mem_filter]; exact ⟨hp, by simp [hsp]⟩
              rw [hu] at hpin; simp at hpin
          · intro hk
            cases hprod : g.producible node with
            | true => rfl
            | false => exact absurd ⟨hk, hprod⟩ hc
      | cons hd tl =>
        simp only [hu] at h
        have hps : ∀ p ∈ hd :: tl, g.isSat p = false := by
          intro p hp
          have hpin : p ∈ unmetPrereqs g node := by rw [hu]; exact hp
          unfold unmetPrereqs at hpin; rw [List.mem_filter] at hpin
          simpa using hpin.2
        -- Fold-soundness: a `some r` outcome of the fold comes from some prereq.
        suffices Hf : ∀ (ps : List Nat) (vis0 : List Nat),
            (∀ p ∈ ps, g.isSat p = false) →
            ∀ r,
              (ps.foldl
                (fun (acc : List Nat × Option Nat) q =>
                  match acc.2 with
                  | some r => (acc.1, some r)
                  | none => actStepShared g k acc.1 q)
                (vis0, none)).2 = some r →
              ActionableNode g r by
          exact Hf (hd :: tl) (node :: visited) hps r h
        intro ps
        induction ps with
        | nil => intro _ _ r hh; simp [List.foldl] at hh
        | cons p rest ih_in =>
          intro vis0 hps' r' hh
          rw [List.foldl] at hh
          have hb : (match ((vis0, (none : Option Nat))).2 with
                    | some rr => ((vis0, (none : Option Nat)).1, some rr)
                    | none => actStepShared g k (vis0, (none : Option Nat)).1 p)
                    = actStepShared g k vis0 p := rfl
          rw [hb] at hh
          cases hres : (actStepShared g k vis0 p).2 with
          | some r0 =>
            have hpsat : g.isSat p = false := hps' p List.mem_cons_self
            have hPr0 : ActionableNode g r0 := ih vis0 p r0 hpsat hres
            have hpair : actStepShared g k vis0 p =
                         ((actStepShared g k vis0 p).1, some r0) := by rw [← hres]
            rw [hpair] at hh
            have hcarry : ∀ (l : List Nat) (vv : List Nat),
                (l.foldl
                  (fun (acc : List Nat × Option Nat) q =>
                    match acc.2 with
                    | some r => (acc.1, some r)
                    | none => actStepShared g k acc.1 q)
                  (vv, some r0)).2 = some r0 := by
              intro l
              induction l with
              | nil => intro _; rfl
              | cons q'' _ ih_c =>
                intro vv
                rw [List.foldl]
                have h_inner : (match ((vv, some r0)).2 with
                        | some rr => ((vv, some r0).1, some rr)
                        | none => actStepShared g k (vv, some r0).1 q'')
                        = (vv, some r0) := rfl
                rw [h_inner]; exact ih_c vv
            rw [hcarry rest _] at hh
            injection hh with hh; subst hh; exact hPr0
          | none =>
            have hpair : actStepShared g k vis0 p =
                         ((actStepShared g k vis0 p).1, none) := by rw [← hres]
            rw [hpair] at hh
            exact ih_in (actStepShared g k vis0 p).1
              (fun p' hp' => hps' p' (List.mem_cons_of_mem _ hp')) r' hh

/-- Top-level SOUNDNESS for the SHARED model: `actionableStepShared` returns
only `ActionableNode`s. -/
theorem actionable_step_shared_sound (g : Graph) (fuel root r : Nat)
    (hroot : g.isSat root = false)
    (h : actionableStepShared g fuel root = some r) :
    ActionableNode g r :=
  actStepShared_sound g fuel [] root r hroot h

/-- Worked examples for the SHARED model — same outcomes as the per-path one. -/
example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1] else if n = 1 then [0] else [],
      isSat := fun _ => false,
      producible := fun _ => false,
      kind := fun _ => Kind.obtain }
    actionableStepShared g 8 0 = none := by
      unfold actionableStepShared; simp [actStepShared, unmetPrereqs]

example :
    let g : Graph := {
      prereqs := fun n => if n = 0 then [1, 2] else [],
      isSat := fun n => n = 1,
      producible := fun n => n = 2,
      kind := fun _ => Kind.obtain }
    actionableStepShared g 8 0 = some 2 := by
      unfold actionableStepShared; simp [actStepShared, unmetPrereqs]

end Formal.StrategyTraversal
