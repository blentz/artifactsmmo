import Formal.NextTierCap
import Formal.Extracted.NextTierCap

/-!
# Extracted bridges, part 10: the next-tier skill-grind dampener.

`tiers/next_tier_cap.py` → `Extracted.NextTierCap.next_tier_cap_pure` is
String-keyed on the craft skill (its `SkillItem` is imported from
`skill_target_curve`, emitted here as a namespaced copy); the hand model
`Formal.NextTierCap.nextTierCap` keys it by `Int`. As in `Bridges8`, the bridge
is UNIVERSAL over an arbitrary INJECTIVE skill embedding `enc : Int → String`:
the extracted cap over the `enc`-encoded items equals the hand cap over the
original `Item`s, for EVERY input. Only `craftSkill` is re-keyed; all other
fields pass through unchanged.

The one arithmetic subtlety over `Bridges8`: the extracted next-tier floor uses
Python floor division `Int.fdiv char_level 10`, while the hand `nextTierFloor`
uses Lean's `char_level / 10`. Divisor `10 > 0` ⇒ `Int.fdiv · 10 = · / 10` for
EVERY `char_level` (no sign hypothesis needed), so the floors coincide.

Transferred hand contracts (restated on the extracted def): `cap_le_max` (the
clamp ceiling) and `dampened_safety` (the gate fires only when the skill genuinely
covers the whole next tier).

No sorry/admit, no new axioms; core-only (safety-module convention).
-/

namespace Formal.Extracted.Bridges10

/-- Encode a hand `Item` (Int skill key) into the extracted String-keyed
`SkillItem`, re-keying only `craftSkill` through `enc`. -/
def encItem (enc : Int → String) (it : Formal.NextTierCap.Item) :
    Extracted.NextTierCap.SkillItem :=
  { craft_skill := enc it.craftSkill, craft_level := it.craftLevel,
    item_level := it.itemLevel, gear_relevant := it.gearRelevant }

/-- BRIDGE (universal over injective skill embeddings): the extracted
`next_tier_cap_pure` over the encoded items equals the hand `nextTierCap`, for
EVERY input. The floors coincide (`Int.fdiv · 10 = · / 10`, divisor positive);
the band foldls agree pointwise (the only differing test, `decide (enc · = enc
skill)` vs the hand `· == skill`, is settled by injectivity); the clamp is
identical. -/
theorem next_tier_cap_bridge (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel maxSkill : Int)
    (items : List Formal.NextTierCap.Item) :
    Extracted.NextTierCap.next_tier_cap_pure
        (enc skill) charLevel (items.map (encItem enc)) maxSkill
      = Formal.NextTierCap.nextTierCap skill charLevel maxSkill items := by
  -- Python floor division equals Lean division at a positive divisor.
  have hfloor : Int.fdiv charLevel 10 = charLevel / 10 := by
    rw [Int.fdiv_eq_ediv]; simp
  simp only [Extracted.NextTierCap.next_tier_cap_pure,
    Formal.NextTierCap.nextTierCap, Formal.NextTierCap.rawCap,
    Formal.NextTierCap.nextTierFloor, hfloor]
  -- Both foldls now use the SAME next-tier floor `(charLevel / 10 + 1) * 10`.
  -- Step equality (∀ floor): the extracted step (over an encoded item) equals
  -- the hand step; the only difference, `decide (enc · = enc skill)` vs `· ==
  -- skill`, is settled by injectivity.
  have hstep : ∀ (floor best : Int) (it : Formal.NextTierCap.Item),
      (if ((encItem enc it).gear_relevant && decide ((encItem enc it).craft_skill = enc skill)
          && decide (floor ≤ (encItem enc it).item_level)
          && decide ((encItem enc it).item_level ≤ floor + 9)
          && decide ((encItem enc it).craft_level > best))
        then (encItem enc it).craft_level else best)
      = (if (it.gearRelevant && (it.craftSkill == skill)
          && decide (floor ≤ it.itemLevel) && decide (it.itemLevel ≤ floor + 9)
          && decide (it.craftLevel > best))
        then it.craftLevel else best) := by
    intro floor best it
    simp only [encItem]
    by_cases hc : it.craftSkill = skill
    · simp [hc]
    · have hne : enc it.craftSkill ≠ enc skill := fun hcontra => hc (hinj _ _ hcontra)
      simp [hc, hne]
  -- Lift the step equality to the whole foldl by induction on the item list,
  -- stated over the *encoded* list directly (matching the extracted def before
  -- any `foldl_map` rewriting).
  have hfold : ∀ (floor init : Int),
      List.foldl (fun best (it : Extracted.NextTierCap.SkillItem) =>
        let best :=
          (if (it.gear_relevant && decide (it.craft_skill = enc skill)
              && decide (floor ≤ it.item_level) && decide (it.item_level ≤ floor + 9)
              && decide (it.craft_level > best)) then it.craft_level else best)
        best) init (items.map (encItem enc))
      = List.foldl (fun best it =>
        if it.gearRelevant && (it.craftSkill == skill)
            && decide (floor ≤ it.itemLevel) && decide (it.itemLevel ≤ floor + 9)
            && decide (it.craftLevel > best)
          then it.craftLevel else best) init items := by
    intro floor
    induction items with
    | nil => intro init; rfl
    | cons it rest ih =>
      intro init
      simp only [List.map_cons, List.foldl_cons]
      rw [hstep floor init it, ih]
  -- The clamp is the same total function on both sides, `if (decide P)` (extracted)
  -- vs `if P` (hand); they agree on every value by a case split.
  have hclamp : ∀ v : Int,
      (if (decide (v ≤ 0)) then 0
       else if (decide (v > maxSkill)) then maxSkill else v)
      = (if v ≤ 0 then 0 else if v > maxSkill then maxSkill else v) := by
    intro v
    by_cases h1 : v ≤ 0
    · simp [h1]
    · by_cases h2 : v > maxSkill <;> simp [h1, h2]
  rw [hfold ((charLevel / 10 + 1) * 10) 0]
  exact hclamp _

/-- TRANSFERRED (`cap_le_max`, the clamp ceiling): the extracted cap is bounded
by `maxSkill` (a game level, hence `0 ≤ maxSkill`). -/
theorem next_tier_cap_le_max_extracted (enc : Int → String)
    (hinj : ∀ a b : Int, enc a = enc b → a = b)
    (skill charLevel maxSkill : Int)
    (items : List Formal.NextTierCap.Item) (hmax : 0 ≤ maxSkill) :
    Extracted.NextTierCap.next_tier_cap_pure
        (enc skill) charLevel (items.map (encItem enc)) maxSkill ≤ maxSkill := by
  rw [next_tier_cap_bridge enc hinj]
  exact Formal.NextTierCap.cap_le_max skill charLevel maxSkill items hmax

/-- BRIDGE for the boolean gate (both args are `Int`, no encoding needed): the
extracted `next_tier_dampened_pure` equals the hand `nextTierDampened`. -/
theorem next_tier_dampened_bridge (currentSkill cap : Int) :
    Extracted.NextTierCap.next_tier_dampened_pure currentSkill cap
      = Formal.NextTierCap.nextTierDampened currentSkill cap := by
  simp only [Extracted.NextTierCap.next_tier_dampened_pure,
    Formal.NextTierCap.nextTierDampened]
  by_cases h1 : cap > 0 <;> by_cases h2 : currentSkill ≥ cap <;> simp [h1, h2]

/-- TRANSFERRED (`dampened_safety`): when the extracted gate fires the skill
genuinely covers the whole next tier (`cap > 0 ∧ currentSkill ≥ cap`). -/
theorem next_tier_dampened_safety_extracted (currentSkill cap : Int)
    (h : Extracted.NextTierCap.next_tier_dampened_pure currentSkill cap = true) :
    cap > 0 ∧ currentSkill ≥ cap := by
  rw [next_tier_dampened_bridge] at h
  exact Formal.NextTierCap.dampened_safety currentSkill cap h

end Formal.Extracted.Bridges10
