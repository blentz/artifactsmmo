/-
Formal model of `project_loadout_stats` from
`src/artifactsmmo_cli/ai/equipment/projection.py`.

The server reports only TOTAL combat stats (base + currently-equipped gear),
never the base. So a hypothetical loadout's projected stats are computed as a
DELTA from the current totals:

    projected.field = current.field
                      + Σ_slot[ loadout[slot] ≠ equipment[slot] ]
                          ( contribution(loadout[slot]).field
                          - contribution(equipment[slot]).field )

per stat field. The Python code iterates the loadout's slots; for each slot
whose picked item differs from the equipped item (`new_code == old_code:
continue`), it adds the new item's contribution and subtracts the old item's
contribution to each field. An absent / `None` item contributes 0 to every field
(`new_s.X.get(...) if new_s else 0`).

MODEL.
* A fixed slot set `slots : List Slot` (the loadout's keys). We keep it as a
  generic `List` parametrised by an arbitrary slot type, so the theorems hold
  for ANY slot configuration (the real keys: weapon, helmet, body, ... — the
  proof is uniform over them).
* `Contrib` is the per-item contribution tuple of one stat field's worth of
  integers. We prove everything PER FIELD over `Int`, which is exactly what the
  Python loop does (each field accumulates independently). A "no item" / `None`
  is modelled as contribution 0 (the Python `if new_s else 0` fallback).
* `newC slot` / `oldC slot : Int` are the picked / equipped item's contribution
  for the field under study, at that slot.
* `changed slot : Bool` is `loadout[slot] ≠ equipment[slot]`. When a slot is
  unchanged Python `continue`s; we model that as the guard on the summand.

KEY THEOREMS.
* `proj_identity`: loadout = equipment (i.e. NOTHING changed) ⇒ projected =
  current, for every field. (The guarded sum is empty / all-zero.)
* `proj_additive` / `guarded_eq_unconditional`: the CHANGED-slot-guarded sum
  equals the UNCONDITIONAL all-slot `Σ (new − old)` sum — because an unchanged
  slot has `new = old`, so its `new − old = 0` contributes nothing whether
  guarded out or summed. This proves the `continue` guard is SOUND: the two
  independent formulations agree. `projected = current + Σ_all (new − old)`
  follows. Per field.

_drop_zeros HANDLING (disclosed): `_drop_zeros` is a pure OUTPUT-SHAPE filter on
the element dicts (drops keys whose accumulated value is exactly 0; keeps
negatives). It does not change any value — an absent key reads back as 0. The
differential test treats dropped-zero element keys as 0 (`dict.get(k, 0)`),
which is precisely the pre-drop accumulator value this model computes. So the
Lean model computes the PRE-DROP accumulator per field/element and the Python
side reads POST-DROP with a 0 default; they coincide. We additionally prove
`dropZeros_preserves` below: dropping zeros never alters a nonzero entry and a
dropped entry reads back as its original (zero) value.

Lean core only — no mathlib. Integer arithmetic via `omega`; sums via `List.sum`
and induction.
-/

namespace Formal.LoadoutProjection

/-- The per-item contribution to ONE stat field at ONE slot, as an integer.
`none`-modelled items contribute 0 (Python's `... if new_s else 0`). We carry
the already-resolved integer (the test constructs the `ItemStats` and resolves
`.field.get(elem, 0)` on the Python side; here it is the abstract summand). -/
abbrev Contrib := Int

/-- The signed per-slot delta for one field: picked contribution − equipped
contribution. This is exactly Python's `(new_s.X if new_s else 0) - (old_s.X if
old_s else 0)` for that field at that slot. -/
def slotDelta (newC oldC : Int) : Int := newC - oldC

/-- A slot is "changed" iff the picked item differs from the equipped item
(`loadout[slot] != equipment[slot]`). Python `continue`s when they are equal. -/
def changed (newCode oldCode : Int) : Bool := newCode != oldCode

/-- The GUARDED summand for one slot: the Python loop body. If the slot is
unchanged it is skipped (`continue`), contributing 0; otherwise it contributes
`newC − oldC`. We pass the slot's item CODES (to decide changed) and the field
contributions separately, mirroring that `change` is decided on codes while the
delta is on the resolved stat field. -/
def guardedDelta (newCode oldCode newC oldC : Int) : Int :=
  if changed newCode oldCode then slotDelta newC oldC else 0

/-- One slot's data for a single field: (newCode, oldCode, newC, oldC). -/
abbrev SlotData := Int × Int × Int × Int

/-- The guarded (Python `continue`-skipping) accumulated delta over all slots:
`Σ_slot [changed] (newC − oldC)`. This is the exact value the Python loop adds
to `current.field`. -/
def guardedSum (slots : List SlotData) : Int :=
  (slots.map (fun s => guardedDelta s.1 s.2.1 s.2.2.1 s.2.2.2)).sum

/-- The UNCONDITIONAL accumulated delta over all slots, with NO guard:
`Σ_slot (newC − oldC)`. An independent formulation. -/
def unconditionalSum (slots : List SlotData) : Int :=
  (slots.map (fun s => slotDelta s.2.2.1 s.2.2.2)).sum

/-- The projected field value: current totals plus the guarded loop sum. -/
def projectedField (current : Int) (slots : List SlotData) : Int :=
  current + guardedSum slots

/-! ### Well-formedness: a slot whose CODES are equal has equal CONTRIBUTIONS.

When `newCode == oldCode` the same item is in both loadout and equipment, so its
resolved contribution is identical: `newC = oldC`. The Python code relies on this
(it `continue`s precisely because the contributions would cancel). We capture it
as a predicate on slot data and require it for `guarded_eq_unconditional`. -/

/-- A slot is well-formed iff equal codes imply equal contributions
(same item ⇒ same stat field). -/
def slotWf (s : SlotData) : Prop :=
  s.1 = s.2.1 → s.2.2.1 = s.2.2.2

/-- All slots well-formed. -/
def slotsWf (slots : List SlotData) : Prop := ∀ s ∈ slots, slotWf s

/-! ### Theorems. -/

/-- For a single well-formed slot, the guarded summand equals the unconditional
summand: when changed, both are `newC − oldC`; when unchanged, the codes are
equal so (by well-formedness) `newC = oldC` and both are 0. -/
theorem guardedDelta_eq_slotDelta (s : SlotData) (h : slotWf s) :
    guardedDelta s.1 s.2.1 s.2.2.1 s.2.2.2 = slotDelta s.2.2.1 s.2.2.2 := by
  unfold guardedDelta changed slotDelta
  by_cases hc : s.1 = s.2.1
  · have : s.2.2.1 = s.2.2.2 := h hc
    simp [hc, this]
  · simp [hc]

/-- `guarded_eq_unconditional`: the changed-slot-guarded sum equals the
unconditional all-slot `Σ (newC − oldC)` sum (each unchanged slot contributes 0
either way). This proves the `continue` guard is SOUND — two independent
formulations agree. -/
theorem guarded_eq_unconditional (slots : List SlotData) (h : slotsWf slots) :
    guardedSum slots = unconditionalSum slots := by
  unfold guardedSum unconditionalSum
  induction slots with
  | nil => simp
  | cons s rest ih =>
    have hs : slotWf s := h s (List.mem_cons_self)
    have hrest : slotsWf rest := fun x hx => h x (List.mem_cons_of_mem _ hx)
    simp only [List.map_cons, List.sum_cons]
    rw [guardedDelta_eq_slotDelta s hs, ih hrest]

/-- `proj_additive` (per field): the projected field equals the current value
plus the UNCONDITIONAL all-slot delta sum. Combined with the loop definition
(`projectedField = current + guardedSum`) this pins the projection to the clean
additive law and certifies the guard rewrite. -/
theorem proj_additive (current : Int) (slots : List SlotData) (h : slotsWf slots) :
    projectedField current slots = current + unconditionalSum slots := by
  unfold projectedField
  rw [guarded_eq_unconditional slots h]

/-- A loadout that equals the equipment has every slot unchanged: each slot's
codes are equal. -/
def isIdentity (slots : List SlotData) : Prop := ∀ s ∈ slots, s.1 = s.2.1

/-- The guarded sum of an identity loadout is 0 (every slot skipped). -/
theorem guardedSum_identity (slots : List SlotData) (h : isIdentity slots) :
    guardedSum slots = 0 := by
  unfold guardedSum
  induction slots with
  | nil => simp
  | cons s rest ih =>
    have hs : s.1 = s.2.1 := h s (List.mem_cons_self)
    have hrest : isIdentity rest := fun x hx => h x (List.mem_cons_of_mem _ hx)
    simp only [List.map_cons, List.sum_cons]
    have hhead : guardedDelta s.1 s.2.1 s.2.2.1 s.2.2.2 = 0 := by
      unfold guardedDelta changed
      simp [hs]
    rw [hhead, ih hrest, Int.add_zero]

/-- `proj_identity` (per field): loadout = equipment ⇒ projected = current.
Every slot's codes match, so every guarded summand is skipped (0). -/
theorem proj_identity (current : Int) (slots : List SlotData)
    (h : isIdentity slots) :
    projectedField current slots = current := by
  unfold projectedField
  rw [guardedSum_identity slots h, Int.add_zero]

/-! ### _drop_zeros preservation (output-shape filter). -/

/-- Model of `_drop_zeros`: keep only the entries whose value is nonzero. We
model the element dict as an association list `List (key × Int)`. -/
def dropZeros (d : List (Int × Int)) : List (Int × Int) :=
  d.filter (fun kv => kv.2 != 0)

/-- Reading a key from an assoc list, defaulting to 0 when absent
(Python `dict.get(k, 0)`). -/
def lookupD (d : List (Int × Int)) (k : Int) : Int :=
  match d.find? (fun kv => kv.1 == k) with
  | some kv => kv.2
  | none => 0

/-- `dropZeros` preserves every NONZERO entry's read-back value, and a dropped
(zero) entry reads back as 0 — so the post-drop dict read with a 0 default equals
the pre-drop accumulator. We prove the value-preservation direction: any key
whose pre-drop value is nonzero survives with the same value; any key with
pre-drop value 0 reads back as 0 post-drop (since it is filtered out and absent
keys default to 0). This is exactly the differential treatment (dropped-zero
keys == 0). We state it as: for a well-formed (no duplicate keys) dict, the
post-drop lookup of a nonzero entry is unchanged. -/
theorem dropZeros_preserves_nonzero (d : List (Int × Int)) (k v : Int)
    (hmem : (k, v) ∈ d) (hv : v ≠ 0)
    (huniq : ∀ kv ∈ d, kv.1 = k → kv.2 = v) :
    lookupD (dropZeros d) k = v := by
  unfold lookupD dropZeros
  induction d with
  | nil => simp at hmem
  | cons hd tl ih =>
    rcases List.mem_cons.mp hmem with heq | htl
    · subst heq
      simp only [List.filter_cons]
      have hk0 : ((k, v).2 != 0) = true := by simp [hv]
      simp only [hk0, if_true, List.find?_cons]
      simp
    · have hunq' : ∀ kv ∈ tl, kv.1 = k → kv.2 = v :=
        fun kv hkv => huniq kv (List.mem_cons_of_mem _ hkv)
      simp only [List.filter_cons]
      by_cases hfilt : ((fun kv => kv.2 != 0) hd) = true
      · simp only [hfilt, if_true]
        rw [List.find?_cons]
        by_cases hk : (hd.1 == k) = true
        · have : hd.2 = v := huniq hd (List.mem_cons_self) (by simpa using hk)
          simp [hk, this]
        · simp only [Bool.not_eq_true] at hk
          simp only [hk]
          exact ih htl hunq'
      · simp only [hfilt, Bool.false_eq_true, if_false]
        exact ih htl hunq'

/-- A key whose accumulated value is exactly 0 is dropped, and reads back as 0 —
matching `dict.get(k, 0)` on the post-drop dict. (`lookupD` of an absent key.) -/
theorem dropZeros_zero_reads_zero (d : List (Int × Int)) (k : Int)
    (h : ∀ kv ∈ d, kv.1 = k → kv.2 = 0) :
    lookupD (dropZeros d) k = 0 := by
  unfold lookupD dropZeros
  induction d with
  | nil => simp
  | cons hd tl ih =>
    have htl : ∀ kv ∈ tl, kv.1 = k → kv.2 = 0 :=
      fun kv hkv => h kv (List.mem_cons_of_mem _ hkv)
    simp only [List.filter_cons]
    by_cases hfilt : ((fun kv => kv.2 != 0) hd) = true
    · -- the head survives the filter, so its value is nonzero; but if its key is
      -- `k` then `h` forces it to 0 — contradiction. So either the head is not
      -- key `k` (recurse) or we derive False.
      by_cases hk : (hd.1 == k) = true
      · have hz : hd.2 = 0 := h hd (List.mem_cons_self) (by simpa using hk)
        simp only [hz, bne_self_eq_false, Bool.false_eq_true] at hfilt
      · simp only [hfilt, if_true]
        rw [List.find?_cons]
        simp only [Bool.not_eq_true] at hk
        simp only [hk]
        exact ih htl
    · simp only [hfilt, Bool.false_eq_true, if_false]
      exact ih htl

end Formal.LoadoutProjection
