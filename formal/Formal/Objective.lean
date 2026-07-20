-- @concept: crafting, items, characters @property: reachability, dominance
/-
Formal model of `is_attainable`, `CharacterObjective.from_game_data` (gear
selection), `gap`, and `ObjectiveGap.is_complete` from
`src/artifactsmmo_cli/ai/tiers/objective.py`.

## `is_attainable(code, game_data, _path) -> bool`  (objective.py:15)

An item is producible "in principle" iff its craft chain bottoms out in
gatherables, with no drop-only/unknown component:

* if the item HAS a crafting recipe: it is attainable iff it is NOT on the
  current `_path` (cycle guard) AND every material is attainable;
* else (no recipe): it is attainable iff it is a resource-drop item
  (`code in game_data._resource_drops.values()`).

A CYCLIC recipe (`a -> b -> a`) is NOT attainable (the `_path` guard makes the
recursive call return `False`). A no-recipe item that is not a resource drop is
NOT attainable. This is exactly the LEAST FIXPOINT of a grounding operator: an
item is GROUNDED iff it is a resource-drop leaf, or it has a recipe and all its
materials are grounded. We define `Grounded` inductively (the least fixpoint),
an independent fuel-bounded saturation `groundedByN` mirroring the DFS, and
prove the recursive cycle-safe `isAttainable` EQUALS membership in the fixpoint
(soundness + completeness), in the spirit of RecipeClosure.

## `CharacterObjective.from_game_data` gear selection  (objective.py:57)

Per equipment type, the items are ranked by `(-equip_value, code)` (highest
value first, ties by ascending code), filtered to the ATTAINABLE ones, then
zipped to the type's slots. The first slot gets the highest-equip_value
ATTAINABLE item. We model `equip_value` as an `Int` (attack + resistance +
hp_restore — all integers) and prove the best-per-slot selection is the argmax
over attainable items, ties by code ascending.

## `gap(state)` and `ObjectiveGap.is_complete`  (objective.py:86)

`char_level_gap = max(0, target - level)`, each `skill_gap = max(0, target -
skill)`, each `gear_gap = max(0, target_val - have_val)`. The three FRACTIONS
are `gap / denom`.

FLOAT DISCLOSURE: the three fractions are the only floats. We do NOT compute the
float; we model each numerator (gap sum) and denominator as `Int` and prove
`0 ≤ gap ≤ denom`, so the float `gap/denom ∈ [0,1]` by the integer bound —
verified integer-only.

`is_complete` is `char_fraction == 0 ∧ skills_fraction == 0 ∧ gear_fraction ==
0`. Since each fraction is `gap/denom` with `denom > 0`, fraction = 0 ⟺ gap = 0.
We prove `is_complete` (modeled on the integer gaps) is equivalent to an
INDEPENDENT raw-target form: char_level = target ∧ every skill = its max ∧ every
gear deficit is 0 — NOT a restatement of `is_complete`'s own body.

`equip_value` modeled as `Int`. Lean core only — no mathlib.
-/

namespace Formal.Objective

/-! ### Recipe / drop relations for attainability. -/

/-- A recipe environment: item → its material codes (`recipe.keys()` —
quantities are irrelevant to attainability). -/
abbrev Recipe := Nat → List Nat

/-- `hasRecipe item` : the item has a crafting recipe (`crafting_recipe is not
None`). Carried separately so `recipe is not None` is mirrored exactly. -/
abbrev HasRecipe := Nat → Bool

/-- `isDrop item` : the item is a resource-drop item
(`code in _resource_drops.values()`). The distinguished `gold` currency is
modeled as a drop-leaf (always grounded) — see `Buys`. -/
abbrev IsDrop := Nat → Bool

/-- `buys item` : the currency codes for which a PERMANENT, reachable vendor
sells `item` (`_permanent_vendor_purchases`, projected to currencies). An item
is buyable iff ANY of its currencies is itself attainable; `gold` is encoded as a
member of `drop` so a gold purchase grounds in one step. The Python buy edge is
tried ONLY at no-recipe items (inside `leaf_ok`), so the `buy` grounding
constructor and the `attainAux` buy branch are both gated on `hasRec = false`. -/
abbrev Buys := Nat → List Nat

/-! ### Grounding — the least fixpoint, defined inductively. -/

/-- `Grounded`: the least set such that a drop-leaf is grounded, an item with a
recipe is grounded when all its materials are, and a NO-RECIPE item is grounded
when some currency it is bought with is grounded. A cyclic recipe (or a pure
buy-cycle) never bottoms out, so its items are NOT grounded. The `buy`
constructor is gated on `hasRec = false` to mirror Python (the purchase edge
lives in the no-recipe `leaf_ok` branch). -/
inductive Grounded (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) : Nat → Prop
  | leaf {m : Nat} (hnr : hasRec m = false) (hd : drop m = true) : Grounded r hasRec drop buys m
  | craft {m : Nat} (hr : hasRec m = true)
      (hmats : ∀ mat ∈ r m, Grounded r hasRec drop buys mat) : Grounded r hasRec drop buys m
  | buy {m c : Nat} (hnr : hasRec m = false) (hc : c ∈ buys m)
      (hg : Grounded r hasRec drop buys c) : Grounded r hasRec drop buys m

/-! ### Fuel-bounded saturation (grounding closure). -/

/-- Items grounded within `n` saturation rounds. Round 0 grounds nothing; round
`n+1` grounds drop-leaves and recipe items whose materials are grounded by round
`n`. -/
def groundedByN (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    Nat → Nat → Bool
  | 0, _ => false
  | n + 1, item =>
    if hasRec item then (r item).all (fun mat => groundedByN r hasRec drop buys n mat)
    else drop item || (buys item).any (fun c => groundedByN r hasRec drop buys n c)

/-! ### The recursive cycle-safe `isAttainable` (mirrors objective.py:15). -/

/-- `attainAux fuel path item`: structural fuel bounds depth (the real `_path`
set bounds it; we thread fuel = universe size so the function is total). At fuel
`fuel+1` with a recipe: `false` when `item ∈ path` (cycle guard), else all
materials attainable under `item :: path`. Without a recipe: `item` is a drop. -/
def attainAux (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    Nat → List Nat → Nat → Bool
  | 0, _, _ => false
  | fuel + 1, path, item =>
    if hasRec item then
      if item ∈ path then false
      else (r item).all (fun mat => attainAux r hasRec drop buys fuel (item :: path) mat)
    else
      if drop item then true
      else if item ∈ path then false
      else (buys item).any (fun c => attainAux r hasRec drop buys fuel (item :: path) c)

/-- Top-level `is_attainable(code)`: empty path; callers pass `fuel` ≥ universe
size. -/
def isAttainable (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    (fuel : Nat) (item : Nat) : Bool :=
  attainAux r hasRec drop buys fuel [] item

/-! ### `groundedByN` monotonicity. -/

theorem groundedByN_mono (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    ∀ (n : Nat) (item : Nat), groundedByN r hasRec drop buys n item = true →
      groundedByN r hasRec drop buys (n + 1) item = true := by
  intro n
  induction n with
  | zero => intro item h; simp [groundedByN] at h
  | succ k ih =>
    intro item h
    unfold groundedByN at h ⊢
    by_cases hr : hasRec item = true
    · simp only [hr, if_true] at h ⊢
      rw [List.all_eq_true] at h ⊢
      intro mat hmat
      exact ih mat (h mat hmat)
    · simp only [hr, Bool.false_eq_true, if_false, Bool.or_eq_true] at h ⊢
      rcases h with hd | hany
      · exact Or.inl hd
      · refine Or.inr ?_
        rw [List.any_eq_true] at hany ⊢
        obtain ⟨c, hc, hgc⟩ := hany
        exact ⟨c, hc, ih c hgc⟩

theorem groundedByN_mono_le (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    (n k : Nat) (item : Nat) (h : groundedByN r hasRec drop buys n item = true) :
    groundedByN r hasRec drop buys (n + k) item = true := by
  induction k with
  | zero => exact h
  | succ j ih => exact groundedByN_mono r hasRec drop buys (n + j) item ih

/-- Monotone for any `n ≤ m`. -/
theorem groundedByN_mono_of_le (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    {n m : Nat} (hnm : n ≤ m) (item : Nat)
    (h : groundedByN r hasRec drop buys n item = true) :
    groundedByN r hasRec drop buys m item = true := by
  obtain ⟨k, rfl⟩ := Nat.exists_eq_add_of_le hnm
  exact groundedByN_mono_le r hasRec drop buys n k item h

/-! ### Soundness / completeness of `groundedByN` vs the fixpoint. -/

/-- SOUNDNESS: `groundedByN` accepts only `Grounded` items. -/
theorem groundedByN_sound (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    ∀ (n : Nat) (item : Nat), groundedByN r hasRec drop buys n item = true →
      Grounded r hasRec drop buys item := by
  intro n
  induction n with
  | zero => intro item h; simp [groundedByN] at h
  | succ k ih =>
    intro item h
    unfold groundedByN at h
    by_cases hr : hasRec item = true
    · simp only [hr, if_true] at h
      rw [List.all_eq_true] at h
      exact Grounded.craft hr (fun mat hmat => ih mat (h mat hmat))
    · simp only [hr, Bool.false_eq_true, if_false, Bool.or_eq_true] at h
      rcases h with hd | hany
      · exact Grounded.leaf (by simpa using hr) hd
      · rw [List.any_eq_true] at hany
        obtain ⟨c, hc, hgc⟩ := hany
        exact Grounded.buy (by simpa using hr) hc (ih c hgc)

/-- COMPLETENESS: every `Grounded` item is accepted by some saturation round. -/
theorem grounded_groundedByN (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    {item : Nat} (h : Grounded r hasRec drop buys item) :
    ∃ n, groundedByN r hasRec drop buys n item = true := by
  induction h with
  | @leaf m hnr hd =>
    refine ⟨1, ?_⟩
    unfold groundedByN
    simp only [hnr, Bool.false_eq_true, if_false, Bool.or_eq_true]
    exact Or.inl hd
  | @craft m hr hmats ih =>
    -- common round bounding all materials, via a generic list lemma
    have hbound : ∀ (l : List Nat),
        (∀ mat ∈ l, ∃ n, groundedByN r hasRec drop buys n mat = true) →
        ∃ N, ∀ mat ∈ l, groundedByN r hasRec drop buys N mat = true := by
      intro l
      induction l with
      | nil => intro _; exact ⟨0, by intro mat hmat; simp at hmat⟩
      | cons hd tl ihtl =>
        intro hall
        obtain ⟨Ntl, htl⟩ := ihtl (fun mat hmat => hall mat (List.mem_cons_of_mem _ hmat))
        obtain ⟨Nhd, hhd⟩ := hall hd (List.mem_cons_self)
        refine ⟨Nhd + Ntl, ?_⟩
        intro mat hmat
        rcases List.mem_cons.mp hmat with he | hm
        · subst he
          exact groundedByN_mono_le r hasRec drop buys Nhd Ntl mat hhd
        · have := groundedByN_mono_le r hasRec drop buys Ntl Nhd mat (htl mat hm)
          rwa [Nat.add_comm] at this
    obtain ⟨N, hN⟩ := hbound (r m) ih
    refine ⟨N + 1, ?_⟩
    unfold groundedByN
    simp only [hr, if_true]
    rw [List.all_eq_true]
    intro mat hmat
    exact hN mat (by simpa using hmat)
  | @buy m c hnr hc _hg ihc =>
    -- m has no recipe; its grounded currency c is bought one round earlier.
    obtain ⟨n, hn⟩ := ihc
    refine ⟨n + 1, ?_⟩
    unfold groundedByN
    simp only [hnr, Bool.false_eq_true, if_false, Bool.or_eq_true]
    exact Or.inr (List.any_eq_true.mpr ⟨c, hc, hn⟩)

/-! ### `attainAux` (cycle-safe recursion) = grounding fixpoint. -/

/-- SOUNDNESS of `attainAux`: under any path and fuel, accept ⇒ `Grounded`. The
cycle guard only ever REJECTS, so an accepted item has a real derivation. -/
theorem attainAux_sound (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    ∀ (fuel : Nat) (path : List Nat) (item : Nat),
      attainAux r hasRec drop buys fuel path item = true → Grounded r hasRec drop buys item := by
  intro fuel
  induction fuel with
  | zero => intro path item h; simp [attainAux] at h
  | succ k ih =>
    intro path item h
    unfold attainAux at h
    by_cases hr : hasRec item = true
    · simp only [hr, if_true] at h
      by_cases hp : item ∈ path
      · simp only [hp, if_true] at h; exact absurd h (by simp)
      · simp only [hp, if_false] at h
        rw [List.all_eq_true] at h
        exact Grounded.craft hr (fun mat hmat => ih (item :: path) mat (h mat hmat))
    · simp only [hr, Bool.false_eq_true, if_false] at h
      by_cases hd : drop item = true
      · exact Grounded.leaf (by simpa using hr) hd
      · rw [if_neg hd] at h
        by_cases hp : item ∈ path
        · rw [if_pos hp] at h; exact absurd h (by simp)
        · rw [if_neg hp] at h
          rw [List.any_eq_true] at h
          obtain ⟨c, hc, hgc⟩ := h
          exact Grounded.buy (by simpa using hr) hc (ih (item :: path) c hgc)

/-! ### Completeness via the MINIMAL grounding round (strict measure).

The acceptance proof's only subtlety is the cycle guard `item ∈ path`. We process
each item at its MINIMAL grounding round; minimality gives `item ∉ path`. The
invariant carried down: every path member is grounded ONLY at rounds `> m`, where
`m` is the current item's minimal round. Materials have a minimal round `< m+1`
i.e. `≤ m`, hence `< (m+1)`; when `item` (minimal round `m+1`) joins the path it
satisfies `m+1 > (child budget) = the material's minimal round`. So no path
member is ever grounded at a round `≤` the next item's minimal round → the next
item is not on the path. This is the formal "cycle guard never blocks a genuine
acyclic derivation". We bundle minimality as `IsMinRound`. -/

/-- `IsMinRound m item`: `item` is grounded at round `m` but NOT at round `m-1`
(its minimal grounding round is exactly `m`). For `m = 0` this is vacuously
false (nothing is grounded at round 0), so all uses have `m ≥ 1`. -/
def IsMinRound (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) (m item : Nat) : Prop :=
  groundedByN r hasRec drop buys m item = true ∧
    ∀ j, j < m → groundedByN r hasRec drop buys j item = false

/-- Every grounded item HAS a minimal grounding round. We minimize by strong
induction on a witness round (Lean core, no `Nat.find`): given any round `n`
that grounds `item`, either no smaller round does (then `n` is minimal) or some
strictly smaller round does (recurse). -/
theorem exists_minRound (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    {item : Nat} (h : ∃ n, groundedByN r hasRec drop buys n item = true) :
    ∃ m, IsMinRound r hasRec drop buys m item := by
  obtain ⟨n, hn⟩ := h
  induction n using Nat.strongRecOn with
  | ind n ih =>
    by_cases hsmaller : ∃ j, j < n ∧ groundedByN r hasRec drop buys j item = true
    · obtain ⟨j, hjlt, hjg⟩ := hsmaller
      exact ih j hjlt hjg
    · refine ⟨n, hn, ?_⟩
      intro j hj
      cases hc : groundedByN r hasRec drop buys j item with
      | false => rfl
      | true => exact absurd ⟨j, hj, hc⟩ hsmaller

/-- If a recipe item has minimal round `m+1`, every material is grounded by round
`m` (one round earlier). -/
theorem materials_grounded_pred (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    (n item : Nat) (hr : hasRec item = true)
    (h : groundedByN r hasRec drop buys (n + 1) item = true) :
    ∀ mat ∈ r item, groundedByN r hasRec drop buys n mat = true := by
  unfold groundedByN at h
  simp only [hr, if_true] at h
  rw [List.all_eq_true] at h
  exact h

/-- The minimal grounding round is unique. -/
theorem minRound_unique (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    (item m1 m2 : Nat) (h1 : IsMinRound r hasRec drop buys m1 item)
    (h2 : IsMinRound r hasRec drop buys m2 item) : m1 = m2 := by
  obtain ⟨hg1, hl1⟩ := h1
  obtain ⟨hg2, hl2⟩ := h2
  rcases Nat.lt_trichotomy m1 m2 with hlt | heq | hgt
  · exact absurd hg1 (by rw [hl2 m1 hlt]; simp)
  · exact heq
  · exact absurd hg2 (by rw [hl1 m2 hgt]; simp)

/-- COMPLETENESS, path-general, parameterised by the item's minimal round `m`.
`attainAux` accepts `item` (minimal round `m`) under ANY `path` whose every
member's minimal round exceeds `m`, given fuel `≥ m`. -/
theorem attainAux_complete_min (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys) :
    ∀ (m : Nat) (item : Nat) (path : List Nat),
      IsMinRound r hasRec drop buys m item →
      (∀ a ∈ path, ∀ ma, IsMinRound r hasRec drop buys ma a → m < ma) →
      ∀ fuel, m ≤ fuel → attainAux r hasRec drop buys fuel path item = true := by
  intro m
  induction m using Nat.strongRecOn with
  | ind m ih =>
    intro item path hmin hpath fuel hfuel
    obtain ⟨hg, hmin'⟩ := hmin
    -- m ≥ 1 (nothing grounded at round 0)
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
    unfold attainAux
    by_cases hr : hasRec item = true
    · simp only [hr, if_true]
      -- item ∉ path: any path member's minimal round > k+1; item's is k+1.
      have hnp : item ∉ path := by
        intro hin
        have := hpath item hin (k + 1) ⟨hg, hmin'⟩
        omega
      simp only [hnp, if_false]
      rw [List.all_eq_true]
      intro mat hmat
      have hmatg : groundedByN r hasRec drop buys k mat = true :=
        materials_grounded_pred r hasRec drop buys k item hr hg mat hmat
      -- mat has a minimal round mm ≤ k < k+1.
      obtain ⟨mm, hmm⟩ := exists_minRound r hasRec drop buys ⟨k, hmatg⟩
      have hmmk : mm ≤ k := by
        rcases Nat.lt_or_ge k mm with hkm | hge
        · exact absurd hmatg (by rw [hmm.2 k hkm]; simp)
        · exact hge
      refine ih mm (by omega) mat (item :: path) hmm ?_ f' (by omega)
      intro a ha ma hma
      rcases List.mem_cons.mp ha with he | hold
      · -- a = item, its minimal round is k+1 (uniqueness of minimal round).
        have hma' : IsMinRound r hasRec drop buys ma item := he ▸ hma
        have : ma = k + 1 := minRound_unique r hasRec drop buys item ma (k + 1) hma' ⟨hg, hmin'⟩
        omega
      · have := hpath a hold ma hma; omega
    · -- no recipe: item grounded via a drop-leaf or a bought (grounded) currency.
      simp only [hr, Bool.false_eq_true, if_false]
      by_cases hd : drop item = true
      · rw [if_pos hd]
      · rw [if_neg hd]
        -- item ∉ path (its minimal round is k+1; every path member's exceeds it)
        have hnp : item ∉ path := by
          intro hin
          have := hpath item hin (k + 1) ⟨hg, hmin'⟩
          omega
        rw [if_neg hnp]
        -- drop item = false, so the buy disjunct of `hg` must hold
        have hany : (buys item).any (fun c => groundedByN r hasRec drop buys k c) = true := by
          have hg' := hg
          unfold groundedByN at hg'
          simp only [hr, Bool.false_eq_true, if_false, Bool.or_eq_true] at hg'
          rcases hg' with h' | h'
          · exact absurd h' hd
          · exact h'
        rw [List.any_eq_true] at hany ⊢
        obtain ⟨c, hc, hgc⟩ := hany
        refine ⟨c, hc, ?_⟩
        -- c has a minimal round mm ≤ k < k+1; recurse with item joining the path.
        obtain ⟨mm, hmm⟩ := exists_minRound r hasRec drop buys ⟨k, hgc⟩
        have hmmk : mm ≤ k := by
          rcases Nat.lt_or_ge k mm with hkm | hge
          · exact absurd hgc (by rw [hmm.2 k hkm]; simp)
          · exact hge
        refine ih mm (by omega) c (item :: path) hmm ?_ f' (by omega)
        intro a ha ma hma
        rcases List.mem_cons.mp ha with he | hold
        · have hma' : IsMinRound r hasRec drop buys ma item := he ▸ hma
          have : ma = k + 1 := minRound_unique r hasRec drop buys item ma (k + 1) hma' ⟨hg, hmin'⟩
          omega
        · have := hpath a hold ma hma; omega

/-- COMPLETENESS at the top level: a grounded item is accepted by `isAttainable`
with the EMPTY path, for any fuel ≥ its minimal grounding round. The empty path
trivially satisfies the path invariant. -/
theorem grounded_isAttainable (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    {item : Nat} (h : Grounded r hasRec drop buys item) :
    ∃ N, ∀ fuel, N ≤ fuel → isAttainable r hasRec drop buys fuel item = true := by
  obtain ⟨n, hn⟩ := grounded_groundedByN r hasRec drop buys h
  obtain ⟨m, hm⟩ := exists_minRound r hasRec drop buys ⟨n, hn⟩
  refine ⟨m, fun fuel hfuel => ?_⟩
  unfold isAttainable
  exact attainAux_complete_min r hasRec drop buys m item [] hm (by intro a ha; simp at ha) fuel hfuel

/-! ### The headline equivalence: `is_attainable` = grounding fixpoint. -/

/-- `is_attainable_eq_grounding` (the headline). For ANY fuel, `isAttainable`
accepting implies `Grounded` (SOUNDNESS); and a `Grounded` item is accepted for
all sufficiently large fuel (COMPLETENESS). Combined: with adequate fuel,
`isAttainable item = true ↔ Grounded item`. A cyclic recipe and a drop-only-but-
not-recipe-grounded item are NOT `Grounded`, hence NOT attainable. -/
theorem is_attainable_eq_grounding (r : Recipe) (hasRec : HasRecipe) (drop : IsDrop) (buys : Buys)
    (item : Nat) :
    (∀ fuel, isAttainable r hasRec drop buys fuel item = true → Grounded r hasRec drop buys item) ∧
    (Grounded r hasRec drop buys item →
      ∃ N, ∀ fuel, N ≤ fuel → isAttainable r hasRec drop buys fuel item = true) := by
  refine ⟨?_, grounded_isAttainable r hasRec drop buys⟩
  intro fuel h
  exact attainAux_sound r hasRec drop buys fuel [] item h

/-- A CYCLIC recipe `a → b → a` (both have recipes, neither is a drop) is NOT
grounded — so `isAttainable` returns `false` for any fuel (the `_path` guard
rejects). Concretely with item 0 ↔ 1: neither is attainable. -/
example :
    let r : Recipe := fun n => if n = 0 then [1] else if n = 1 then [0] else []
    let hasRec : HasRecipe := fun n => n = 0 ∨ n = 1
    let drop : IsDrop := fun _ => false
    let buys : Buys := fun _ => []
    isAttainable r hasRec drop buys 8 0 = false := by decide

/-- A DROP-ONLY component that is NOT a resource drop and has NO recipe is NOT
grounded — `isAttainable` returns `false`. Item 0 has a recipe needing item 1;
item 1 has no recipe and is not a drop. So 0 is not attainable. -/
example :
    let r : Recipe := fun n => if n = 0 then [1] else []
    let hasRec : HasRecipe := fun n => n = 0
    let drop : IsDrop := fun _ => false
    let buys : Buys := fun _ => []
    isAttainable r hasRec drop buys 8 0 = false := by decide

/-- A genuine chain DOES ground: item 0 crafts from drop-leaf 1. -/
example :
    let r : Recipe := fun n => if n = 0 then [1] else []
    let hasRec : HasRecipe := fun n => n = 0
    let drop : IsDrop := fun n => n = 1
    let buys : Buys := fun _ => []
    isAttainable r hasRec drop buys 8 0 = true := by decide

/-- BUY EDGE: a no-recipe item 0 is bought with currency 1, which is a drop-leaf.
So 0 grounds via the purchase edge. -/
example :
    let r : Recipe := fun _ => []
    let hasRec : HasRecipe := fun _ => false
    let drop : IsDrop := fun n => n = 1
    let buys : Buys := fun n => if n = 0 then [1] else []
    isAttainable r hasRec drop buys 8 0 = true := by decide

/-- BUY with `gold` (modeled as drop-leaf 9, always grounded): item 0 has no
recipe and is not itself a drop, but a vendor sells it for gold → attainable. -/
example :
    let r : Recipe := fun _ => []
    let hasRec : HasRecipe := fun _ => false
    let drop : IsDrop := fun n => n = 9
    let buys : Buys := fun n => if n = 0 then [9] else []
    isAttainable r hasRec drop buys 8 0 = true := by decide

/-- A BUY-CYCLE (0 bought with 1, 1 bought with 0), neither a drop, is NOT
grounded — the path guard rejects it. -/
example :
    let r : Recipe := fun _ => []
    let hasRec : HasRecipe := fun _ => false
    let drop : IsDrop := fun _ => false
    let buys : Buys := fun n => if n = 0 then [1] else if n = 1 then [0] else []
    isAttainable r hasRec drop buys 8 0 = false := by decide

/-! ### Gear selection: argmax over ATTAINABLE items, ties by code ascending.

`from_game_data` ranks a type's items by `(-equip_value, code)`, filters to the
ATTAINABLE ones, and takes the head for the first slot. We model `equip_value` as
an `Int` (`attack + resistance + hp_restore`) and the per-type item set as a list
of `(equip_value, code)`. The best item for the first slot is the argmax: highest
`equip_value`, ties broken by SMALLEST code. -/

/-- A modeled gear item: its integer code and integer equip_value. -/
structure Gear where
  code : Int
  value : Int
deriving Repr, DecidableEq

/-- `equip_value` as the integer sum of attack, resistance, and hp_restore. The
real Python returns a `float`, but the summands are integers; the only use is
RANKING, which a float of an integer preserves exactly. We work in `Int`. -/
def equipValue (attack resistance hpRestore : Int) : Int := attack + resistance + hpRestore

/-- `g1` ranks strictly before `g2` under `(-value, code)`: higher value, or equal
value with smaller code (Python `sorted(..., key=lambda vc: (-vc[0], vc[1]))`). -/
def rankBefore (g1 g2 : Gear) : Prop :=
  g1.value > g2.value ∨ (g1.value = g2.value ∧ g1.code < g2.code)

/-- The best gear among `best :: rest` by the ranking, as a left-fold keeping the
ranked-earlier item (ties to the smaller code). Mirrors taking the head of the
`(-value, code)`-sorted list. -/
def bestGear : Gear → List Gear → Gear
  | best, [] => best
  | best, g :: gs =>
      if g.value > best.value ∨ (g.value = best.value ∧ g.code < best.code)
      then bestGear g gs else bestGear best gs

/-- The chosen item for the FIRST slot of a type: the best ATTAINABLE item. We
filter the candidate list to attainable items, then take the best. -/
def bestAttainableGear (attain : Gear → Bool) : List Gear → Option Gear
  | [] => none
  | g :: gs =>
      match (g :: gs).filter attain with
      | [] => none
      | a :: as => some (bestGear a as)

/-- `bestGear` is a member of `best :: rest`. -/
theorem bestGear_mem (best : Gear) (rest : List Gear) :
    bestGear best rest ∈ best :: rest := by
  induction rest generalizing best with
  | nil => simp [bestGear]
  | cons g gs ih =>
    unfold bestGear
    by_cases h : g.value > best.value ∨ (g.value = best.value ∧ g.code < best.code)
    · simp only [h, if_true]
      rcases List.mem_cons.mp (ih g) with he | hm
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inl he)))
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))
    · simp only [h, if_false]
      rcases List.mem_cons.mp (ih best) with he | hm
      · exact List.mem_cons.mpr (Or.inl he)
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))

/-- `bestGear` dominates every member under the `(-value, code)` ranking: for any
member `y`, the chosen best is NOT ranked strictly after `y` — equivalently the
best's `(value, -code)` is ≥ `y`'s. We state it as: best.value ≥ y.value, and on
a value tie best.code ≤ y.code. So `bestGear` is the genuine `(-value, code)`
argmax. -/
theorem bestGear_optimal (best : Gear) (rest : List Gear) :
    ∀ y ∈ best :: rest,
      (bestGear best rest).value > y.value ∨
      ((bestGear best rest).value = y.value ∧ (bestGear best rest).code ≤ y.code) := by
  induction rest generalizing best with
  | nil =>
    intro y hy
    simp only [bestGear]
    rcases List.mem_cons.mp hy with he | hm
    · subst he; exact Or.inr ⟨rfl, Int.le_refl _⟩
    · exact absurd hm (List.not_mem_nil)
  | cons g gs ih =>
    intro y hy
    unfold bestGear
    by_cases h : g.value > best.value ∨ (g.value = best.value ∧ g.code < best.code)
    · simp only [h, if_true]
      rcases List.mem_cons.mp hy with he | hm
      · -- y = best; g ranks before best, and bestGear g gs ranks ≥ g
        subst he
        have hg := ih g g (List.mem_cons_self)
        rcases h with hv | ⟨hve, hce⟩
        · rcases hg with h1 | ⟨h2a, h2b⟩
          · exact Or.inl (by omega)
          · exact Or.inl (by omega)
        · rcases hg with h1 | ⟨h2a, h2b⟩
          · exact Or.inl (by omega)
          · exact Or.inr ⟨by omega, by omega⟩
      · exact ih g y hm
    · simp only [h, if_false]
      -- ¬(g ranks before best) ⇒ best.value ≥ g.value, and on tie best.code ≤ g.code
      have hge : best.value ≥ g.value := by
        by_cases hc : g.value ≤ best.value
        · exact hc
        · exact absurd (Or.inl (by omega)) h
      have htie : g.value = best.value → best.code ≤ g.code := by
        intro heqv
        by_cases hc : best.code ≤ g.code
        · exact hc
        · exact absurd (Or.inr ⟨heqv, by omega⟩) h
      rcases List.mem_cons.mp hy with he | hm
      · subst he; exact ih y y (List.mem_cons_self)
      · rcases List.mem_cons.mp hm with hgy | hrest
        · -- y = g
          have hb := ih best best (List.mem_cons_self)
          have hyv : y.value = g.value := by rw [hgy]
          have hyc : y.code = g.code := by rw [hgy]
          rcases hb with h1 | ⟨h2a, h2b⟩
          · exact Or.inl (by omega)
          · by_cases hgv : g.value < best.value
            · exact Or.inl (by omega)
            · have heqv : g.value = best.value := by omega
              have hcle : best.code ≤ g.code := htie heqv
              exact Or.inr ⟨by omega, by omega⟩
        · exact ih best y (List.mem_cons_of_mem _ hrest)

/-- `best_gear_argmax`: the item chosen for the first slot of a type is the argmax
over the ATTAINABLE items — it IS attainable, it IS one of the candidates, and it
ranks at least as high as every attainable candidate under `(-value, code)` (so it
has the maximum equip_value, ties broken by smallest code). -/
theorem best_gear_argmax (attain : Gear → Bool) (items : List Gear) (chosen : Gear)
    (h : bestAttainableGear attain items = some chosen) :
    attain chosen = true ∧ chosen ∈ items ∧
    (∀ y ∈ items, attain y = true →
      chosen.value > y.value ∨ (chosen.value = y.value ∧ chosen.code ≤ y.code)) := by
  cases items with
  | nil => simp [bestAttainableGear] at h
  | cons g gs =>
    cases hf : (g :: gs).filter attain with
    | nil => simp only [bestAttainableGear, hf] at h; exact absurd h (by simp)
    | cons a as =>
      simp only [bestAttainableGear, hf, Option.some.injEq] at h
      subst h
      -- chosen = bestGear a as. It is a member of a::as = filter, so attainable + in items.
      have hmem : bestGear a as ∈ a :: as := bestGear_mem a as
      have hmem_filter : bestGear a as ∈ (g :: gs).filter attain := by rw [hf]; exact hmem
      have hmf := List.mem_filter.mp hmem_filter
      have hin : bestGear a as ∈ g :: gs := hmf.1
      have hatt : attain (bestGear a as) = true := by simpa using hmf.2
      refine ⟨hatt, hin, ?_⟩
      intro y hy hya
      have hyf : y ∈ a :: as := by
        rw [← hf]; exact List.mem_filter.mpr ⟨hy, by simpa using hya⟩
      exact bestGear_optimal a as y hyf

end Formal.Objective
