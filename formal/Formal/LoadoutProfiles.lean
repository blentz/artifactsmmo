-- @concept: gear @property: dedup, monotonicity, totality, safety
/-
Formal model of the pure loadout-profile cores extracted from
`src/artifactsmmo_cli/ai/loadout_profiles_core.py` (`gear_demand`,
`bank_space_cost`).

A loadout is the list of gear CODES it equips (the slot→code map's values). One
loadout is worn at a time, so the bank only ever needs to hold, for each code,
the MAX over active loadouts of how many slots that loadout fills with it — NOT
the sum. Two loadouts that both wear `copper_dagger` ⇒ demand 1 (held once); a
single loadout wearing `copper_ring` in both ring slots ⇒ demand 2.

  gearDemand loadouts c  = max over loadouts of (count of c in that loadout)
  bankSpaceCost loadouts equipped
                         = |{distinct code in any active loadout} \ equipped|

The floor lemma `shouldExpandBank_floor_preserves` connects this core to
`Formal/BankExpansionTiming.lean`: raising the modelled bank-fill `used` to the
floor `max used cost` (cost = bankSpaceCost) never flips an already-firing
expansion off. It RIDES the existing `expand_stable_under_more_fill`
monotonicity (a fuller bank stays eligible when `0 ≤ triggerDen`, supplied by
the production trigger 95/100); BankExpansionTiming.lean is NOT modified.

Lean core only — no mathlib. (`distinctCodes` uses a self-contained `dedup`
rather than `List.eraseDups`, whose `Nodup` lemma is absent from both core and
mathlib.)
-/

import Formal.BankExpansionTiming

namespace Formal.LoadoutProfiles

/-! ### gearDemand — per-code MAX over loadouts (dedup, NOT sum). -/

/-- `gearDemand loadouts c`: the maximum over active loadouts of the number of
slots that loadout fills with code `c`. Mirrors the Python
`max(_counts(loadout)[c] for loadout in active_loadouts)`. The `foldl max 0`
gives 0 for a code worn by no loadout. -/
def gearDemand (loadouts : List (List String)) (c : String) : Nat :=
  (loadouts.map (fun l => l.count c)).foldl max 0

/-- `foldl max` is monotone in its initial accumulator. The engine behind
`gearDemand_mono` (adding a loadout). -/
theorem foldl_max_mono_init :
    ∀ (xs : List Nat) (a b : Nat), a ≤ b → xs.foldl max a ≤ xs.foldl max b
  | [], _, _, h => h
  | x :: xs, a, b, h => by
    simp only [List.foldl_cons]
    exact foldl_max_mono_init xs (max a x) (max b x) (by omega)

/-- CHARACTERIZATION: `gearDemand` IS the max over loadouts of the per-loadout
count of `c` — the exact dedup semantics (one loadout at a time ⇒ per-code max,
never the cross-loadout sum). -/
theorem gearDemand_eq_max (loadouts : List (List String)) (c : String) :
    gearDemand loadouts c = (loadouts.map (fun l => l.count c)).foldl max 0 := rfl

/-- MONOTONICITY: adding a loadout never decreases a code's demand (more active
profiles ⇒ at least as much bank room needed for `c`). -/
theorem gearDemand_mono (loadouts : List (List String)) (l : List String) (c : String) :
    gearDemand loadouts c ≤ gearDemand (l :: loadouts) c := by
  unfold gearDemand
  simp only [List.map_cons, List.foldl_cons]
  exact foldl_max_mono_init (loadouts.map (fun l => l.count c)) 0 (max 0 (l.count c))
    (Nat.zero_le _)

/-! ### bankSpaceCost — distinct codes not currently equipped. -/

/-- A self-contained deduplication: drop a code if an equal code already survives
to its right. `Nodup` and membership are proven below. -/
def dedup : List String → List String
  | [] => []
  | a :: as => if a ∈ dedup as then dedup as else a :: dedup as

/-- `dedup` preserves membership exactly (the SET of codes is unchanged). -/
theorem mem_dedup (x : String) (l : List String) : x ∈ dedup l ↔ x ∈ l := by
  induction l with
  | nil => simp [dedup]
  | cons a as ih =>
    simp only [dedup]
    by_cases h : a ∈ dedup as
    · rw [if_pos h]
      constructor
      · intro hx; exact List.mem_cons_of_mem a (ih.mp hx)
      · intro hx
        rcases List.mem_cons.mp hx with rfl | hxa
        · exact h
        · exact ih.mpr hxa
    · rw [if_neg h, List.mem_cons, List.mem_cons, ih]

/-- `dedup` produces a duplicate-free list. -/
theorem nodup_dedup (l : List String) : (dedup l).Nodup := by
  induction l with
  | nil => simp [dedup]
  | cons a as ih =>
    simp only [dedup]
    by_cases h : a ∈ dedup as
    · rw [if_pos h]; exact ih
    · rw [if_neg h, List.nodup_cons]; exact ⟨h, ih⟩

/-- The deduplicated list of every gear code appearing in any active loadout.
Mirrors the Python set-comprehension `{code for loadout in ... for code in
loadout.values()}`. -/
def distinctCodes (loadouts : List (List String)) : List String :=
  dedup loadouts.flatten

/-- `bankSpaceCost loadouts equipped`: the count of distinct active-loadout codes
that are NOT currently equipped — the bank room the active profiles demand.
Mirrors the Python `len(distinct - set(equipped))`. -/
def bankSpaceCost (loadouts : List (List String)) (equipped : List String) : Nat :=
  ((distinctCodes loadouts).filter (fun c => decide (c ∉ equipped))).length

/-- NON-NEGATIVITY: the bank-space cost is always ≥ 0 (a count). Stated for
parity with the role matrix; trivial over `Nat`. -/
theorem bankSpaceCost_nonneg (loadouts : List (List String)) (equipped : List String) :
    0 ≤ bankSpaceCost loadouts equipped := Nat.zero_le _

/-- BOUND: the bank-space cost never exceeds the number of distinct active codes —
filtering out equipped codes can only shrink the set (equipped gear needs no bank
room). -/
theorem bankSpaceCost_le_distinct (loadouts : List (List String)) (equipped : List String) :
    bankSpaceCost loadouts equipped ≤ (distinctCodes loadouts).length :=
  List.length_filter_le _ _

/-- A `Nodup` list whose membership is contained in another list is no longer
than that list — the engine behind `bankSpaceCost_mono`. Core-only, by induction
removing the head from the superset. -/
theorem nodup_subset_length_le :
    ∀ {A B : List String}, A.Nodup → A ⊆ B → A.length ≤ B.length
  | [], _, _, _ => Nat.zero_le _
  | a :: A', B, hA, hsub => by
    have ha_mem : a ∈ B := hsub List.mem_cons_self
    rw [List.nodup_cons] at hA
    have hsub' : A' ⊆ B.erase a := by
      intro x hx
      have hxB : x ∈ B := hsub (List.mem_cons_of_mem a hx)
      have hxa : x ≠ a := fun h => hA.1 (h ▸ hx)
      exact (List.mem_erase_of_ne hxa).mpr hxB
    have hlen_erase : (B.erase a).length = B.length - 1 := List.length_erase_of_mem ha_mem
    have ih := nodup_subset_length_le hA.2 hsub'
    have hBpos : 0 < B.length := List.length_pos_of_mem ha_mem
    simp only [List.length_cons]
    omega

/-- MONOTONICITY: adding a loadout never decreases the bank-space cost (more
active profiles can only widen the distinct-code set that must be banked). -/
theorem bankSpaceCost_mono (loadouts : List (List String)) (l : List String)
    (equipped : List String) :
    bankSpaceCost loadouts equipped ≤ bankSpaceCost (l :: loadouts) equipped := by
  unfold bankSpaceCost
  apply nodup_subset_length_le
  · exact List.Pairwise.filter _ (nodup_dedup _)
  · intro x hx
    rw [List.mem_filter] at hx ⊢
    refine ⟨?_, hx.2⟩
    have hxd : x ∈ distinctCodes loadouts := hx.1
    unfold distinctCodes at hxd ⊢
    rw [mem_dedup] at hxd ⊢
    simp only [List.flatten_cons, List.mem_append]
    exact Or.inr hxd

/-! ### Floor preserves the ExpandBank firing decision. -/

/-- FLOOR PRESERVATION: flooring the modelled bank-fill `used` up to
`max used cost` (where `cost = bankSpaceCost`) never flips an already-firing
ExpandBank decision off. RIDES `expand_stable_under_more_fill` (raising `used`
keeps the fill gate satisfied when `0 ≤ triggerDen`); the trivial
`used ≤ max used cost` is the "more fill" precondition. BankExpansionTiming.lean
is unchanged. -/
theorem shouldExpandBank_floor_preserves
    (used cost capacity gold k r tn td : Int) (htd : 0 ≤ td)
    (hle : used ≤ max used cost) :
    Formal.BankExpansionTiming.shouldExpandBank used capacity gold k r tn td = true →
    Formal.BankExpansionTiming.shouldExpandBank (max used cost) capacity gold k r tn td = true := by
  intro hfire
  exact Formal.BankExpansionTiming.expand_stable_under_more_fill
    used (max used cost) capacity gold k r tn td htd hfire hle

/-! ### Non-vacuity witnesses (anchor the Python test vectors). -/

/-- Witness: two loadouts sharing `copper_dagger` ⇒ demand 1 (held once). -/
theorem gearDemand_shared_witness :
    gearDemand [["copper_dagger", "copper_ring"], ["copper_dagger", "iron_helmet"]]
      "copper_dagger" = 1 := by decide

/-- Witness: one loadout wearing `copper_ring` in both ring slots ⇒ demand 2. -/
theorem gearDemand_ring_witness :
    gearDemand [["copper_ring", "copper_ring"]] "copper_ring" = 2 := by decide

/-- Witness: demand is the MAX (2), not the SUM (3), across loadouts. -/
theorem gearDemand_max_not_sum_witness :
    gearDemand [["copper_ring", "copper_ring"], ["copper_ring"]] "copper_ring" = 2 := by decide

/-- Witness: distinct {copper_dagger, iron_helmet, leather_boots} minus the
equipped copper_dagger ⇒ cost 2. -/
theorem bankSpaceCost_witness :
    bankSpaceCost [["copper_dagger", "iron_helmet"], ["copper_dagger", "leather_boots"]]
      ["copper_dagger"] = 2 := by decide

end Formal.LoadoutProfiles
