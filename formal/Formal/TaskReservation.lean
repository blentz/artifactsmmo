-- @concept: tasks, crafting, items @property: safety
/-
Formal model of the task-material reservation core
(`src/artifactsmmo_cli/ai/task_reservation.py`) — the P0 2026-06-09 fix for
the items-task material-theft livelock: while PursueTask(copper_bar 0/11)
pools crafted bars, the skill-grind step GatherMaterials(copper_helmet)
becomes plannable the instant bars exist, wins the step tier, and
Craft(copper_helmet) eats 6 bars — the task restarts from zero, forever.

The Python core:

    task_reserved_demand(state, gd):
        {} unless task_type == "items" and remaining = total - progress > 0;
        else closure_demand(task_code, remaining)   # task item + transitive
                                                    # recipe inputs, scaled
    consumes_reserved(needed, state, gd):
        some r in closure(needed keys) has r in demand, owned(r) > 0,
        owned(r) <= demand[r]

We model the recipe table as `Recipe := Nat → List (Nat × Nat)` (item →
(material, qty-per) list, mirroring the Python dict walk in insertion order)
and the demand map as an assoc list read through `lookup` (first match,
default 0) / `hasKey`. `closureDemand` mirrors the shared Python
`closure_demand` (recipe_closure.py): per-path visited set (cycle-safe),
max-merge across contributing paths, fuel-bounded for Lean termination (the
differential feeds fuel ≥ the item universe so the bound never binds).
Structural recursion on fuel keeps every definition kernel-reducible (the
pinned trace witnesses are proved by `decide`, no native evaluation).

Contracts (the three design guarantees):
1. `remaining_zero_no_reserve` — task done ⇒ nothing reserved, nothing
   suppressed (the reservation cannot outlive the task).
2. `surplus_passes` — owned strictly above demand on every reserved item ⇒
   not suppressed (surplus above the remaining need is free).
3. `demand_monotone` — task progress↑ ⇒ reserved demand pointwise ≤ (the
   reservation only ever shrinks as the task advances; no ratchet).

Lean core only — no Mathlib (safety namespace). Arithmetic via `omega`.
-/

namespace Formal.TaskReservation

/-- Recipe table: item → list of (material, quantity-per-unit). -/
abbrev Recipe := Nat → List (Nat × Nat)

/-- Demand map: assoc list item → quantity, read through `lookup`/`hasKey`. -/
abbrev Demand := List (Nat × Nat)

/-- First-match lookup, default 0 (mirrors Python `dict.get(k, 0)`). -/
def lookup : Demand → Nat → Nat
  | [], _ => 0
  | (k, v) :: rest, i => if i = k then v else lookup rest i

/-- Key-presence (mirrors Python `k in dict`). -/
def hasKey : Demand → Nat → Bool
  | [], _ => false
  | (k, _) :: rest, i => decide (i = k) || hasKey rest i

/-- Record `k` at `Nat.max (lookup out k) v` — the max-merge write of the
Python `if multiplier > out.get(root, 0): out[root] = multiplier`. Over the
reachable domain (`v ≥ 1`, guaranteed by the multiplier invariant: the
initial multiplier is ≥ 1 and zero-qty edges are skipped) the key sets
agree with Python's; the `lookup` values agree everywhere. -/
def record (out : Demand) (k v : Nat) : Demand :=
  (k, Nat.max (lookup out k) v) :: out

theorem lookup_record (out : Demand) (k v i : Nat) :
    lookup (record out k v) i
      = if i = k then Nat.max (lookup out i) v else lookup out i := by
  by_cases h : i = k
  · subst h; simp [record, lookup]
  · simp [record, lookup, h]

/-- Ceil-division `⌈a / b⌉` on `Nat` (the batch-yield arithmetic). Mirrors the
Python `-(-a // b)` / extracted `-(Int.fdiv (-a) b)`. Identity at `b = 1`. -/
def ceilDiv (a b : Nat) : Nat := (a + b - 1) / b

/-- `ceilDiv` is monotone in the numerator (Nat division is). -/
theorem ceilDiv_mono {a b : Nat} (c : Nat) (h : a ≤ b) : ceilDiv a c ≤ ceilDiv b c := by
  unfold ceilDiv
  apply Nat.div_le_div_right
  omega

/-- `ceilDiv a 1 = a` — the all-`Y=1` no-op (used by the extracted↔hand bridge). -/
theorem ceilDiv_one (a : Nat) : ceilDiv a 1 = a := by unfold ceilDiv; omega

/-- A positive multiplier over a positive yield needs at least one craft run. -/
theorem one_le_ceilDiv {mult c : Nat} (hm : 1 ≤ mult) (hc : 1 ≤ c) : 1 ≤ ceilDiv mult c := by
  unfold ceilDiv
  rw [Nat.one_le_div_iff (by omega)]
  omega

/-- Closure demand of `root` x `mult` accumulated into `out`: the root and
every transitive recipe material at its cumulative required quantity
(max-merged across contributing paths). The foldl over `r root` is the
Python `for mat, qty_per in recipe.items()` walk (zero-qty edges skipped,
mirroring `if qty_per <= 0: continue`); the per-path `visited` makes cyclic
recipes terminate exactly like the Python frozenset guard; `fuel` only
bounds Lean recursion (never binding when fuel ≥ #items).

`y` is the per-item yield map (default 1). To produce `mult` of a yield-`y root`
node needs `⌈mult / y root⌉` craft runs (`ceilDiv mult (y root)`), each
consuming `qty_per` of each ingredient — so children scale by
`ceilDiv mult (y root) * qty_per` (the Python `batches * qty_per`). The root is
still recorded at `mult` (the demanded item count). At `y root = 1`,
`ceilDiv mult 1 = mult`, recovering the original `mult * qty_per`. -/
def closureDemand (r : Recipe) (y : Nat → Nat) : Nat → Nat → Nat → List Nat → Demand → Demand
  | 0, _, _, _, out => out
  | fuel + 1, root, mult, visited, out =>
    if visited.contains root then out
    else
      (r root).foldl
        (fun acc p =>
          if p.2 = 0 then acc
          else closureDemand r y fuel p.1 (ceilDiv mult (y root) * p.2) (root :: visited) acc)
        (record out root mult)

/-- Children-walk monotonicity, GIVEN node-level monotonicity at the same
fuel (the induction is on fuel outside, on the child list here). -/
theorem foldl_children_mono (r : Recipe) (y : Nat → Nat) (fuel : Nat)
    (hcd : ∀ (root m₁ m₂ : Nat) (visited : List Nat) (out₁ out₂ : Demand),
      m₁ ≤ m₂ → (∀ j, lookup out₁ j ≤ lookup out₂ j) →
      ∀ i, lookup (closureDemand r y fuel root m₁ visited out₁) i
            ≤ lookup (closureDemand r y fuel root m₂ visited out₂) i) :
    ∀ (l : List (Nat × Nat)) (m₁ m₂ : Nat) (visited : List Nat)
      (out₁ out₂ : Demand),
      m₁ ≤ m₂ → (∀ j, lookup out₁ j ≤ lookup out₂ j) →
      ∀ i, lookup (l.foldl
              (fun acc p => if p.2 = 0 then acc
                else closureDemand r y fuel p.1 (m₁ * p.2) visited acc) out₁) i
            ≤ lookup (l.foldl
              (fun acc p => if p.2 = 0 then acc
                else closureDemand r y fuel p.1 (m₂ * p.2) visited acc) out₂) i := by
  intro l
  induction l with
  | nil =>
    intro m₁ m₂ visited out₁ out₂ _hm hout i
    simpa using hout i
  | cons p rest ihl =>
    intro m₁ m₂ visited out₁ out₂ hm hout i
    simp only [List.foldl_cons]
    by_cases hq : p.2 = 0
    · rw [if_pos hq, if_pos hq]
      exact ihl m₁ m₂ visited out₁ out₂ hm hout i
    · rw [if_neg hq, if_neg hq]
      exact ihl m₁ m₂ visited _ _ hm
        (fun j => hcd p.1 (m₁ * p.2) (m₂ * p.2) visited out₁ out₂
          (Nat.mul_le_mul hm (Nat.le_refl p.2)) hout j) i

/-- KEY LEMMA: `closureDemand` is pointwise monotone in the multiplier (and
the accumulator). Same recipe/root/visited/fuel ⇒ same traversal; a smaller
multiplier never yields a larger demand anywhere. -/
theorem closureDemand_mono (r : Recipe) (y : Nat → Nat) :
    ∀ (fuel root m₁ m₂ : Nat) (visited : List Nat) (out₁ out₂ : Demand),
      m₁ ≤ m₂ → (∀ j, lookup out₁ j ≤ lookup out₂ j) →
      ∀ i, lookup (closureDemand r y fuel root m₁ visited out₁) i
            ≤ lookup (closureDemand r y fuel root m₂ visited out₂) i := by
  intro fuel
  induction fuel with
  | zero =>
    intro root m₁ m₂ visited out₁ out₂ _hm hout i
    simpa [closureDemand] using hout i
  | succ fuel ih =>
    intro root m₁ m₂ visited out₁ out₂ hm hout i
    by_cases hv : visited.contains root = true
    · simp only [closureDemand]
      rw [if_pos hv, if_pos hv]
      exact hout i
    · have hrec : ∀ j, lookup (record out₁ root m₁) j
            ≤ lookup (record out₂ root m₂) j := by
        intro j
        rw [lookup_record, lookup_record]
        by_cases hj : j = root
        · rw [if_pos hj, if_pos hj]
          exact Nat.max_le.mpr
            ⟨Nat.le_trans (hout j) (Nat.le_max_left _ _),
             Nat.le_trans hm (Nat.le_max_right _ _)⟩
        · rw [if_neg hj, if_neg hj]
          exact hout j
      simp only [closureDemand]
      rw [if_neg hv, if_neg hv]
      exact foldl_children_mono r y fuel ih (r root) (ceilDiv m₁ (y root)) (ceilDiv m₂ (y root))
        (root :: visited) (record out₁ root m₁) (record out₂ root m₂)
        (ceilDiv_mono (y root) hm) hrec i

/-- The active-task context (the slice of WorldState the reservation reads). -/
structure TaskCtx where
  taskIsItems : Bool
  taskCode : Nat
  taskTotal : Nat
  taskProgress : Nat

/-- Units the task still needs (Nat subtraction: over-progress clamps to 0). -/
def remaining (t : TaskCtx) : Nat := t.taskTotal - t.taskProgress

/-- `task_reserved_demand`: {} unless an items task is active with
remaining > 0; else the closure demand of the task item x remaining. `y` is the
per-item yield map (default 1). -/
def reservedDemand (r : Recipe) (y : Nat → Nat) (fuel : Nat) (t : TaskCtx) : Demand :=
  if t.taskIsItems = true ∧ 0 < remaining t then
    closureDemand r y fuel t.taskCode (remaining t) [] []
  else []

/-- The conflict set of a goal's `needed` keys: each key's own closure
(keys(needed) ∪ closure_inputs(needed); the multiplier is irrelevant — only
key membership is read — and the Python uses 1). -/
def conflictClosure (r : Recipe) (y : Nat → Nat) (fuel : Nat) (needed : List Nat) : Demand :=
  needed.foldl (fun acc root => closureDemand r y fuel root 1 [] acc) []

/-- `consumes_reserved`: some conflict item is reserved, owned, and owned at
or below its reserved demand (no surplus). -/
def consumesReserved (r : Recipe) (y : Nat → Nat) (fuel : Nat) (t : TaskCtx)
    (owned : Nat → Nat) (needed : List Nat) : Bool :=
  (conflictClosure r y fuel needed).any (fun p =>
    hasKey (reservedDemand r y fuel t) p.1
      && decide (0 < owned p.1)
      && decide (owned p.1 ≤ lookup (reservedDemand r y fuel t) p.1))

/-- `List.any` is false when the predicate is false on every element
(core-only helper; avoids a Mathlib dependency). -/
theorem any_false {α : Type} (l : List α) (p : α → Bool)
    (h : ∀ x ∈ l, p x = false) : l.any p = false := by
  induction l with
  | nil => rfl
  | cons hd tl ihl =>
    have h1 : p hd = false := h hd (by simp)
    have h2 : tl.any p = false := ihl (fun x hx => h x (by simp [hx]))
    simp [List.any_cons, h1, h2]

/-! ### (1) Task done ⇒ nothing reserved, nothing suppressed. -/

theorem remaining_zero_no_reserve (r : Recipe) (y : Nat → Nat) (fuel : Nat) (t : TaskCtx)
    (owned : Nat → Nat) (needed : List Nat) (h : remaining t = 0) :
    reservedDemand r y fuel t = []
      ∧ consumesReserved r y fuel t owned needed = false := by
  have hres : reservedDemand r y fuel t = [] := by
    unfold reservedDemand
    have hng : ¬ (t.taskIsItems = true ∧ 0 < remaining t) :=
      fun hc => absurd hc.2 (by omega)
    rw [if_neg hng]
  refine ⟨hres, ?_⟩
  unfold consumesReserved
  apply any_false
  intro p _hp
  simp [hres, hasKey]

/-! ### (2) Surplus passes: strictly above demand everywhere ⇒ free. -/

theorem surplus_passes (r : Recipe) (y : Nat → Nat) (fuel : Nat) (t : TaskCtx)
    (owned : Nat → Nat) (needed : List Nat)
    (h : ∀ i, hasKey (reservedDemand r y fuel t) i = true →
          lookup (reservedDemand r y fuel t) i < owned i) :
    consumesReserved r y fuel t owned needed = false := by
  unfold consumesReserved
  apply any_false
  intro p _hp
  by_cases hk : hasKey (reservedDemand r y fuel t) p.1 = true
  · have hlt := h p.1 hk
    have hle : ¬ (owned p.1 ≤ lookup (reservedDemand r y fuel t) p.1) := by omega
    simp [hle]
  · simp only [Bool.not_eq_true] at hk
    simp [hk]

/-! ### (3) Demand is monotone: progress↑ ⇒ reservation pointwise ≤. -/

theorem demand_monotone (r : Recipe) (y : Nat → Nat) (fuel : Nat) (t₁ t₂ : TaskCtx)
    (hitems : t₁.taskIsItems = t₂.taskIsItems)
    (hcode : t₁.taskCode = t₂.taskCode)
    (htotal : t₁.taskTotal = t₂.taskTotal)
    (hprog : t₁.taskProgress ≤ t₂.taskProgress) :
    ∀ i, lookup (reservedDemand r y fuel t₂) i
          ≤ lookup (reservedDemand r y fuel t₁) i := by
  intro i
  have hrem : remaining t₂ ≤ remaining t₁ := by
    unfold remaining
    omega
  unfold reservedDemand
  by_cases h2 : t₂.taskIsItems = true ∧ 0 < remaining t₂
  · have h1 : t₁.taskIsItems = true ∧ 0 < remaining t₁ :=
      ⟨by rw [hitems]; exact h2.1, by omega⟩
    rw [if_pos h1, if_pos h2, hcode]
    exact closureDemand_mono r y fuel t₂.taskCode (remaining t₂) (remaining t₁)
      [] [] [] hrem (fun _ => Nat.le_refl 0) i
  · rw [if_neg h2]
    exact Nat.zero_le _

/-! ### Pinned trace witnesses (non-vacuity; the 2026-06-09 production case).
Recipe: helmet (2) ← 6 x bar (1) ← 10 x ore (0); items task = bar, 0/11. -/

/-- helmet (2) ← 6 x bar (1) ← 10 x ore (0). -/
def traceRecipe : Recipe := fun i =>
  if i = 2 then [(1, 6)] else if i = 1 then [(0, 10)] else []

/-- 5 bars held, task 0/11 → the helmet step IS deferred (5 ≤ demand 11).
All-`Y=1` (`fun _ => 1`): the ceil-batch reduces to the original demand. -/
theorem trace_helmet_deferred :
    consumesReserved traceRecipe (fun _ => 1) 8 ⟨true, 1, 11, 0⟩
      (fun i => if i = 1 then 5 else 0) [2] = true := by decide

/-- 17 bars held (surplus over demand 11) → the helmet step is allowed. -/
theorem trace_surplus_allowed :
    consumesReserved traceRecipe (fun _ => 1) 8 ⟨true, 1, 11, 0⟩
      (fun i => if i = 1 then 17 else 0) [2] = false := by decide

/-- Task complete (11/11) → nothing reserved, the helmet step is allowed. -/
theorem trace_done_allowed :
    consumesReserved traceRecipe (fun _ => 1) 8 ⟨true, 1, 11, 11⟩
      (fun i => if i = 1 then 5 else 0) [2] = false := by decide

end Formal.TaskReservation
