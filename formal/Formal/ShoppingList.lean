-- @concept: resources @property: dominance, monotonicity, safety, totality
/-
Formal model of the bank-aware recipe shopping list extracted from
`src/artifactsmmo_cli/ai/shopping_list.py` (`shopping_list`, `_expand`,
`fully_covered_materials`).

`shopping_list(item, qty, recipes, owned)` recurses an item's recipe tree; at
each node it credits the held copies of THAT item (`owned`, = inventory + bank)
before expanding the sub-recipe, and stock at any level SHORT-CIRCUITS the
subtree below it. The NET result per item is the remaining acquisition work after
crediting holdings. The planner uses a 0-net item as "withdraw, don't gather",
pruning the gather subtree — so the proofs establish that the bank credit never
INCREASES work (dominance), is exactly accounted (reconstruction), and is
monotone in holdings.

We model items as `Nat` and a recipe environment `Recipe := Nat → List (Nat ×
Nat)` (item → its `(sub_mat, per_unit)` list; an empty list = raw/unknown, the
`get(...) or {}` case). `owned : Nat → Nat` gives the held quantity per item.

The load-bearing quantity is the per-node DEFICIT — `deficit qty have = qty -
have` over `Nat` (truncated subtraction). The Python
`used = min(have, qty); deficit = qty - used` equals `qty - have` over `Nat`
because `qty - min have qty = qty - have`. All three proof obligations reduce to
facts about this `Nat.sub` credit, proved honestly with `omega` and structural
induction over the recipe tree's fuel-bounded raw-requirement function.

`rawReq fuel r item qty owned` mirrors the TOTAL gather work the net list implies:
credit `owned item`, and for the deficit either gather it (raw) or recurse into
the sub-recipe at `per_unit * deficit` — exactly the `min_gathers`/`_expand`
shape, with `owned` for the CURRENT item credited at this node (matching the
per-node short-circuit decision the planner prunes on).

Lean core only — no mathlib (safety-module convention; `Nat.sub` facts via
`omega`, structural recursion via fuel).
-/

namespace Formal.ShoppingList

/-- A recipe environment: item → its `(sub_mat, per_unit)` ingredient list. An
empty list models `get(...) or {}` (a raw or unknown item). -/
abbrev Recipe := Nat → List (Nat × Nat)

/-- Per-node deficit: the remaining quantity after crediting `have` held copies
of an item needed in quantity `qty`. Mirrors Python
`used = min(have, qty); deficit = qty - used`, which equals `qty - have` over
`Nat` (truncated subtraction collapses the `min`). -/
def deficit (qty «have» : Nat) : Nat := qty - «have»

/-- The Python `used = min(have, qty)` credit equals `qty - deficit`: nothing is
over- or under-credited at a node (RECONSTRUCTION, per node):
`min have qty + deficit qty have = qty`. -/
theorem credit_plus_deficit (qty «have» : Nat) :
    min «have» qty + deficit qty «have» = qty := by
  unfold deficit; omega

/-- DOMINANCE (per node): the deficit never exceeds the uncredited requirement.
With `have = 0` (empty bank) the deficit is the full `qty`; any `have` only
reduces it. -/
theorem deficit_le_qty (qty «have» : Nat) : deficit qty «have» ≤ qty := by
  unfold deficit; omega

/-- MONOTONICITY (per node): more held copies ⇒ deficit non-increasing. -/
theorem deficit_antitone (qty h₁ h₂ : Nat) (hle : h₁ ≤ h₂) :
    deficit qty h₂ ≤ deficit qty h₁ := by
  unfold deficit; omega

/-- A 0 deficit is exactly "holdings fully cover the need" — the planner's
short-circuit / withdraw-don't-gather predicate (`fully_covered_materials`). -/
theorem deficit_zero_iff_covered (qty «have» : Nat) :
    deficit qty «have» = 0 ↔ qty ≤ «have» := by
  unfold deficit; omega

/-! ### Total raw requirement: the gather work the net list implies.

`rawReq` mirrors the recursion of `shopping_list`/`min_gathers`: credit the
current item's holdings, then for the remaining deficit either gather it (raw
item: empty recipe) or expand the sub-recipe at `per_unit * deficit`. Fuel bounds
the structural recursion over cyclic recipes (out of fuel → account the deficit
as raw), mirroring the Python `visited`/recipe-tree termination. -/

mutual
  /-- Raw gather work to obtain `qty` of `item` crediting `owned`. -/
  def rawReq (owned : Nat → Nat) (r : Recipe) : Nat → Nat → Nat → Nat
    | 0, _, qty => qty
    | fuel + 1, item, qty =>
      match r item with
      | []   => deficit qty (owned item)
      | mats => sumReq owned r fuel mats (deficit qty (owned item))
  /-- Sum the sub-material requirements at `per_unit * d`. -/
  def sumReq (owned : Nat → Nat) (r : Recipe) (fuel : Nat) :
      List (Nat × Nat) → Nat → Nat
    | [], _ => 0
    | (sub, per) :: rest, d => rawReq owned r fuel sub (per * d) + sumReq owned r fuel rest d
end

/-- With nothing owned the credit is a no-op, so the raw requirement is the
NAIVE full requirement — the baseline the bank-credited version is compared to. -/
def naiveReq (r : Recipe) : Nat → Nat → Nat → Nat := rawReq (fun _ => 0) r

/-- MONOTONICITY in requested quantity: `rawReq` is non-decreasing in `qty`
(needing more never costs less work). -/
theorem rawReq_mono_qty (owned : Nat → Nat) (r : Recipe) :
    ∀ fuel item q₁ q₂, q₁ ≤ q₂ → rawReq owned r fuel item q₁ ≤ rawReq owned r fuel item q₂ := by
  intro fuel
  induction fuel with
  | zero => intro item q₁ q₂ h; simpa [rawReq] using h
  | succ n ih =>
    intro item q₁ q₂ h
    have hd : deficit q₁ (owned item) ≤ deficit q₂ (owned item) := by unfold deficit; omega
    cases hr : r item with
    | nil => simp only [rawReq, hr]; exact hd
    | cons p rest =>
      simp only [rawReq, hr]
      -- sumReq is monotone in the deficit argument (via ih on each sub).
      have key : ∀ (mats : List (Nat × Nat)) (d₁ d₂ : Nat), d₁ ≤ d₂ →
          sumReq owned r n mats d₁ ≤ sumReq owned r n mats d₂ := by
        intro mats
        induction mats with
        | nil => intro d₁ d₂ _; simp [sumReq]
        | cons q qs ihm =>
          obtain ⟨sub, per⟩ := q
          intro d₁ d₂ hdd
          simp only [sumReq]
          exact Nat.add_le_add (ih sub _ _ (Nat.mul_le_mul_left per hdd)) (ihm d₁ d₂ hdd)
      exact key (p :: rest) _ _ hd

/-- DOMINANCE (tree level): the bank-credited raw requirement is never larger
than the naive (no-credit) requirement — crediting holdings at every node only
removes gather work, never adds it. The planner's bank-aware pruning is therefore
never MORE work than gathering everything (the spec's dominance obligation). -/
theorem rawReq_le_naive (owned : Nat → Nat) (r : Recipe) :
    ∀ fuel item qty, rawReq owned r fuel item qty ≤ naiveReq r fuel item qty := by
  unfold naiveReq
  intro fuel
  induction fuel with
  | zero => intro item qty; simp [rawReq]
  | succ n ih =>
    intro item qty
    have hd : deficit qty (owned item) ≤ deficit qty 0 :=
      deficit_antitone qty 0 (owned item) (Nat.zero_le _)
    cases hr : r item with
    | nil =>
      simp only [rawReq, hr]
      have : deficit qty 0 = qty := by unfold deficit; omega
      omega
    | cons p rest =>
      simp only [rawReq, hr]
      -- Each sub: credited ≤ naive (ih) AND mono in the smaller deficit (mono_qty).
      have key : ∀ (mats : List (Nat × Nat)) (d dn : Nat), d ≤ dn →
          sumReq owned r n mats d ≤ sumReq (fun _ => 0) r n mats dn := by
        intro mats
        induction mats with
        | nil => intro d dn _; simp [sumReq]
        | cons q qs ihm =>
          obtain ⟨sub, per⟩ := q
          intro d dn hdd
          simp only [sumReq]
          have h1 : rawReq owned r n sub (per * d) ≤ rawReq (fun _ => 0) r n sub (per * d) :=
            ih sub (per * d)
          have h2 : rawReq (fun _ => 0) r n sub (per * d) ≤ rawReq (fun _ => 0) r n sub (per * dn) :=
            rawReq_mono_qty (fun _ => 0) r n sub (per * d) (per * dn) (Nat.mul_le_mul_left per hdd)
          exact Nat.add_le_add (Nat.le_trans h1 h2) (ihm d dn hdd)
      exact key (p :: rest) _ _ hd

/-- MONOTONICITY in holdings (tree level): pointwise-more `owned` ⇒ the raw
requirement is non-increasing. More bank stock ⇒ net deficit non-increasing — the
spec's monotonicity obligation, at the total-work level. -/
theorem rawReq_antitone_owned (r : Recipe) (o₁ o₂ : Nat → Nat)
    (hle : ∀ i, o₁ i ≤ o₂ i) :
    ∀ fuel item qty, rawReq o₂ r fuel item qty ≤ rawReq o₁ r fuel item qty := by
  intro fuel
  induction fuel with
  | zero => intro item qty; simp [rawReq]
  | succ n ih =>
    intro item qty
    have hd : deficit qty (o₂ item) ≤ deficit qty (o₁ item) :=
      deficit_antitone qty (o₁ item) (o₂ item) (hle item)
    cases hr : r item with
    | nil => simp only [rawReq, hr]; exact hd
    | cons p rest =>
      simp only [rawReq, hr]
      have key : ∀ (mats : List (Nat × Nat)) (d₂ d₁ : Nat), d₂ ≤ d₁ →
          sumReq o₂ r n mats d₂ ≤ sumReq o₁ r n mats d₁ := by
        intro mats
        induction mats with
        | nil => intro d₂ d₁ _; simp [sumReq]
        | cons q qs ihm =>
          obtain ⟨sub, per⟩ := q
          intro d₂ d₁ hdd
          simp only [sumReq]
          have h1 : rawReq o₂ r n sub (per * d₂) ≤ rawReq o₁ r n sub (per * d₂) := ih sub (per * d₂)
          have h2 : rawReq o₁ r n sub (per * d₂) ≤ rawReq o₁ r n sub (per * d₁) :=
            rawReq_mono_qty o₁ r n sub (per * d₂) (per * d₁) (Nat.mul_le_mul_left per hdd)
          exact Nat.add_le_add (Nat.le_trans h1 h2) (ihm d₂ d₁ hdd)
      exact key (p :: rest) _ _ hd

/-- TOTALITY / honest baseline: the naive requirement of a RAW item (empty
recipe) at any positive fuel is exactly `qty` — the gather-it-all amount the
dominance bound is measured against (rules out a vacuous bound). -/
theorem naiveReq_raw (r : Recipe) (item qty fuel : Nat) (hraw : r item = []) :
    naiveReq r (fuel + 1) item qty = qty := by
  unfold naiveReq
  simp only [rawReq, hraw, deficit]
  omega

/-! ### Touched items: the keys the net dict records — the SHORT-CIRCUIT model.

`touched` mirrors `_expand`'s net-dict membership: it records the current `item`,
then — and ONLY when the deficit is positive (the SHORT-CIRCUIT) — recurses into
the sub-recipe. So a fully-covered intermediate (deficit 0) is recorded but its
sub-materials are NOT touched. Dropping the short-circuit (recursing regardless)
would spuriously add the covered subtree's items to the net keys; this list pins
that difference, which the raw-work metric cannot see (covered subtree contributes
0 work either way). -/

mutual
  /-- Items the net dict records for `qty` of `item` crediting `owned`. -/
  def touched (owned : Nat → Nat) (r : Recipe) : Nat → Nat → Nat → List Nat
    | 0, item, _ => [item]
    | fuel + 1, item, qty =>
      if deficit qty (owned item) = 0 then [item]            -- covered: SHORT-CIRCUIT
      else item :: touchedSubs owned r fuel (r item) (deficit qty (owned item))
  /-- Touched items across a `(sub, per)` list at deficit `d`. -/
  def touchedSubs (owned : Nat → Nat) (r : Recipe) (fuel : Nat) :
      List (Nat × Nat) → Nat → List Nat
    | [], _ => []
    | (sub, per) :: rest, d => touched owned r fuel sub (per * d) ++ touchedSubs owned r fuel rest d
end

/-- SHORT-CIRCUIT correctness: when holdings fully cover the item (deficit 0), the
ONLY touched item is the item itself — the covered subtree is pruned (not
expanded). This is exactly the planner's withdraw-don't-gather decision, and the
fact the no-short-circuit mutant violates. -/
theorem touched_covered_singleton (owned : Nat → Nat) (r : Recipe)
    (fuel item qty : Nat) (hcov : qty ≤ owned item) :
    touched owned r (fuel + 1) item qty = [item] := by
  have : deficit qty (owned item) = 0 := (deficit_zero_iff_covered qty (owned item)).2 hcov
  simp [touched, this]

end Formal.ShoppingList
