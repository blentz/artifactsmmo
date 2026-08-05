-- @concept: items, gear @property: validity, dominance
/-
Formal model of `pick_loadout` (per-slot pick) from
`src/artifactsmmo_cli/ai/equipment/scoring.py`.

The Python routine optimizes each equipment slot INDEPENDENTLY. For a slot it:
1. gathers the owned items that FIT the slot and are LEVEL-FEASIBLE
   (`_candidates_for_slot`: `state.level < stats.level` is filtered out, and the
   item's type must map to the slot via `ITEM_TYPE_TO_SLOTS`),
2. takes the argmax-score candidate (`max(candidates, key=score)`), and
3. swaps to it ONLY on a STRICT score improvement over the currently-equipped
   item (`weapon_score(best) > weapon_score(current)` / armor analogue). Ties and
   downgrades keep the current item.

SCORES. **Byte-equivalent integer model.** The Python `weapon_score` and
`armor_score` now return EXACT integers computed via the same surrogate formula
the Lean oracle uses:
  * `WScore = Σ_elem atk * max(0, 100 - res)`   (Python `weapon_score` returns
    this integer DIRECTLY; the inner `max(0, 100 - res)` is the integer clamp.)
  * `AScore = rulerScale * (200 * Σ_elem mon_atk * armor_res + Σ_elem oTerm +
    200 * flatUtil)` (Python `armor_score` returns this integer directly; the
    defense sum has NO clamp — armor scoring has none — while the offense sum
    reuses the weapon clamp `max(0, 100 - monRes)` because it prices the
    WEARER's output. `rulerScale` is the ruler's quantum, carried by EVERY term
    on every slot — see `rulerScale` below.)
Production Python uses pure integer arithmetic — there is no floating-point step
anywhere in the score computation, so the Python value is BIT-EQUAL to the Lean
`WScore`/`AScore` for every input. The previous float surrogate caveat is closed:
this is no longer "order-preserving over an abstraction" but bit-equality.
We model `score` as a single abstract integer function on items, instantiated to
`WScore`/`AScore` at the call site; the pick theorems hold for ANY integer score,
and `weapon_score_nonneg` is the one theorem that EARNS the weapon clamp
(`WScore ≥ 0`; a non-clamped surrogate could go negative when `res > 100`).

Lean core only — no mathlib. Integer arithmetic via `omega`; argmax via `List.foldr`
and induction.
-/

namespace Formal.EquipmentScoring

/-- A per-element integer stat (attack or resistance), as an association list over
the 4 elements (fire/earth/water/air). Absent element ⇒ 0 (Python `.get(elem, 0)`). -/
abbrev ElemStats := List (Int × Int)

/-- Look up one element's value, defaulting to 0 (Python `dict.get(elem, 0)`). -/
def elemGet (s : ElemStats) (e : Int) : Int :=
  match s.find? (fun kv => kv.1 == e) with
  | some kv => kv.2
  | none => 0

/-- A model item: integer code, level, per-element attack and resistance, the
critical-strike percentage, and a `fits` flag that abstracts "this item's type
maps to the slot under study"
(Python `slot in ITEM_TYPE_TO_SLOTS.get(stats.type_, [])`). -/
structure Item where
  code : Int
  level : Int
  attack : ElemStats
  resistance : ElemStats
  crit : Int
  fits : Bool
  flatUtil : Int := 0   -- monster-independent utility = hp_bonus + wisdom + prospecting
  isUtilityFill : Bool := false  -- artifact-type utility-fill: Gather scores it by flatUtil
  dmg : Int := 0        -- global damage % the piece adds to the WEARER's output
  dmgElem : ElemStats := []  -- per-element damage % (armor's element-specialization signal)
deriving Repr, DecidableEq

/-- The 4 game elements as integer keys (fire, earth, water, air). -/
def elements : List Int := [0, 1, 2, 3]

/-- **THE RULER'S QUANTUM.** Every term of the gear ruler — the weapon slot's
combat term (`PurposeRouting.combatScore`), the armor slots' combat term
(`ACombat`), and the shared efficiency term both slots read (`AEfficiency`) — is
carried at this multiple of its NATURAL unit, and nothing else in the ruler is.
Mirrors the Python `equipment/scoring.RULER_SCALE`.

It buys two things AT ONCE, which is why it is one constant and not two:

* **the tie-break stays safe.** `PurposeRouting.nonToolBonus ∈ {0, 1}` is the
  only sub-quantum quantity in the ruler; since every other term is a MULTIPLE
  of `rulerScale = 2`, two distinct terms differ by at least 2 and a `+1` can
  never flip a strict inequality (`nonToolBonus_lt_rulerScale`).
* **the slots are commensurable.** The factor used to multiply ONLY the weapon
  term, leaving weapons at twice armor's magnitude for the same real swing —
  live witness `copper_dagger` (7.05 HP of swing per turn) tying `steel_armor`
  (14.10) at 282_000. Applying it to every term makes commensurability a
  property of the definition rather than of the numbers lining up
  (`ruler_commensurate`). -/
def rulerScale : Int := 2

/-- Per-element weapon surrogate term: `atk * max(0, 100 - res)`. The clamp mirrors
the Python float `max(0.0, 1 - res/100)`; here `res` is the MONSTER's resistance. -/
def wTerm (atk monRes : Int) : Int := atk * max 0 (100 - monRes)

/-- `WScore = (Σ_elem atk(elem) * max(0, 100 - monsterRes(elem))) * (200 + crit)`
— the order-preserving integer surrogate of predict_win's expected per-hit
damage. The `(200 + crit)` factor is the expected critical-strike multiplier
`1 + crit/100 * 0.5 = (200 + crit)/200` (combat._expected_hit) scaled by 200 to
stay in ℤ. Without it the loadout picker and the win predictor disagreed about
the same quantity (run-18 2026-06-12: crit-0 tool out-scored a crit-35 weapon
against a resisting monster). -/
def WScore (item : Item) (monsterRes : ElemStats) : Int :=
  (elements.map (fun e => wTerm (elemGet item.attack e) (elemGet monsterRes e))).sum
    * (200 + item.crit)

/-- Per-element armor DEFENSE term: `monAtk * armorRes` (NO clamp — the Python
`armor_score` has none). `100x` the HP-per-turn the piece stops. -/
def aTerm (monAtk armorRes : Int) : Int := monAtk * armorRes

/-- Per-element armor OFFENSE term: the wearer's own per-element output
`wTerm playerAtk monRes` (the SAME clamped form the weapon score uses) scaled by
the boost the piece adds to it, `2 * dmgPct + crit`.

The `2 *` and the crit are one common denominator: the piece's damage percentage
adds `dmgPct/100` of the wearer's output and its crit adds `crit/200` (the
expected `1 + crit/100 * 0.5` multiplier of `combat._expected_hit`, the same one
`WScore`'s `(200 + crit)` factor encodes). Over the denominator 20000 those are
`2 * dmgPct` and `crit` exactly — no division, no rounding. -/
def oTerm (playerAtk monRes dmgPct crit : Int) : Int :=
  wTerm playerAtk monRes * (2 * dmgPct + crit)

/-- `AScore = 200 * Σ_elem defense + Σ_elem offense + 200 * flatUtil`.

UNIT: the two monster-relative sums are BOTH `20000x` HP of damage swing per
combat turn — the piece's DEFENSE (damage it stops, weighted by the monster's
attack) and its OFFENSE (damage its `dmg`/`dmgElem`/`crit` percentages add to the
WEARER's output, weighted by the wearer's attack through the monster's
resistance). `200 *` on the defense sum is what puts `Σ monAtk * armorRes`
(`100x` damage) on the offense sum's `20000x` denominator.

The offense sum is why `AScore` takes `monsterRes` and `playerAtk`: a damage
PERCENTAGE has no value independent of the attack it multiplies. Without it the
score of two resistance-free body armors collapsed to `hp + wisdom`, and the live
bot swapped mushmush_jacket (hp 60, dmg 10, crit 3, wisdom 10) for
adventurer_vest (hp 60, dmg 6, wisdom 20) — buying 10 wisdom with 4 damage and
3 crit that the formula could not see.

`flatUtil` is monster-INDEPENDENT utility (hp_bonus + wisdom + prospecting + …)
and is NOT in that unit — it is carried unconverted on the same `200 *` scale as
the defense sum, so its weight relative to defense is exactly what it was before
the offense sum existed. Its load-bearing role is the empty-slot gate: it makes a
utility-only artifact (no resistance, no damage %) score > 0 so pick_loadout
fills its slot (novice_guide: defense 0 + offense 0 + `200 * 75`). -/
def AScore (item : Item) (monsterAtk monsterRes playerAtk : ElemStats) : Int :=
  rulerScale *
    (200 * (elements.map (fun e => aTerm (elemGet monsterAtk e) (elemGet item.resistance e))).sum
      + (elements.map (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
            (item.dmg + elemGet item.dmgElem e) item.crit)).sum
      + 200 * item.flatUtil)

/-- `AScore` against NO monster and NO wearer attack is exactly
`rulerScale * (200 * flatUtil)`: both monster-relative sums vanish
(`aTerm 0 _ = 0`, and `oTerm 0 _ _ _ = 0` because `wTerm 0 _ = 0`). This is the
Gather utility-fill benefit the live `loadout_picker._benefit` computes as
`armor_score(stats, {}, {}, {})` — pinned here so the two cannot drift. -/
theorem AScore_no_monster (item : Item) :
    AScore item [] [] [] = rulerScale * (200 * item.flatUtil) := by
  simp [AScore, aTerm, oTerm, wTerm, elemGet, elements]

/-! ### Splitting `AScore` into its COMBAT and EFFICIENCY slices.

The ECONOMICS layer (`Formal.StrategicValue`, live `tiers/pursuit_value`) must
let combat DOMINATE utility when ranking what to acquire cross-slot. It used to
do that with a scalar of its own — a flat 8-stat sum `combatRaw` that added a
resistance PERCENTAGE to an HP amount to a damage figure 1:1 — which is a second
ruler, free to disagree with this one about the same slot.

Instead it now reads THIS score's own two halves. `flatUtil` is the piece's
`hp_restore + hp_bonus + wisdom + prospecting + inventorySpace + haste +
lifesteal + combatBuff` sum; splitting it at the four TIME-buying stats
(wisdom / prospecting / inventorySpace / haste) splits `AScore` itself, and
`AScore_decomp` below is the statement that the two halves PARTITION it — every
stat lands in exactly one, so nothing is dropped and nothing is counted twice.
Mirrors the Python `armor_score_combat_pure` / `armor_score_efficiency_pure`,
whose sum IS `armor_score_pure`. -/

/-- The EFFICIENCY slice: the four time-buying stats on the same `200 *` scale
`AScore` already carries its flat-utility block at, times the ruler's quantum.
Mirrors the Python `gear_score_efficiency_pure`.

SLOT-INDEPENDENT. `PurposeRouting.weaponScore` adds THIS SAME term, so the ruler
prices a point of wisdom / prospecting / inventory space / haste identically
whichever slot carries it (`PurposeRouting.weaponScore_efficiency_eq_AEfficiency`).
It used to be armor-only, which is why a weapon's efficiency stats reached no
purpose at all — the four voidstone tools' 100 prospecting and
obsidian_battleaxe's `inventory_space = -25` were both free. -/
def AEfficiency (wisdom prospecting inventorySpace haste : Int) : Int :=
  rulerScale * 200 * (wisdom + prospecting + inventorySpace + haste)

/-- The COMBAT slice: `AScore` with only the IN-FIGHT part of the flat block —
both monster-relative sums unchanged, plus `200 * flatCombat` where `flatCombat`
is `hp_restore + hp_bonus + lifesteal + combatBuff`.

It takes no efficiency stat as an argument, which is the structural reason the
pursuit ruler's combat term cannot contain utility: there is no parameter
through which utility could reach it. Mirrors `armor_score_combat_pure`. -/
def ACombat (item : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (flatCombat : Int) : Int :=
  rulerScale *
    (200 * (elements.map (fun e => aTerm (elemGet monsterAtk e) (elemGet item.resistance e))).sum
      + (elements.map (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
            (item.dmg + elemGet item.dmgElem e) item.crit)).sum
      + 200 * flatCombat)

/-- **THE PARTITION.** Whenever the piece's flat block splits into its in-fight
part and its four efficiency stats, the score splits the same way — the two
slices sum to `AScore` exactly, for every item, every adversary and every
wearer. This is what lets the economics layer re-weight combat against utility
without recomputing either on a scale of its own. -/
theorem AScore_decomp (item : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (flatCombat wisdom prospecting inventorySpace haste : Int)
    (hflat : item.flatUtil
      = flatCombat + wisdom + prospecting + inventorySpace + haste) :
    AScore item monsterAtk monsterRes playerAtk
      = ACombat item monsterAtk monsterRes playerAtk flatCombat
        + AEfficiency wisdom prospecting inventorySpace haste := by
  unfold AScore ACombat AEfficiency rulerScale
  rw [hflat]
  omega

/-! ### Cross-slot commensurability.

The armor combat term and the weapon combat term are both `rulerScale` times a
value in the SAME natural unit (`1/20000` of one HP of damage swing per turn), so
they can be compared directly. `PurposeRouting.ruler_commensurate` states the
consequence on the two live score functions; here is the arithmetic fact it
rides — the armor combat term of a piece with no offense boost and no in-fight
flat stats is exactly `rulerScale` times its `200 *` defense sum. -/

/-- The armor COMBAT term of a piece whose offense sum and in-fight flat block
are zero is exactly `rulerScale * (200 * defenseSum)` — the same shape
`PurposeRouting.combatScore` has around `WScore`. Not vacuous: any armor with
`dmg = 0`, `dmgElem = []` and `crit = 0` has offense sum 0. -/
theorem ACombat_defense_only (item : Item) (monsterAtk monsterRes playerAtk : ElemStats)
    (hoff : (elements.map (fun e => oTerm (elemGet playerAtk e) (elemGet monsterRes e)
              (item.dmg + elemGet item.dmgElem e) item.crit)).sum = 0) :
    ACombat item monsterAtk monsterRes playerAtk 0
      = rulerScale * (200 *
          (elements.map (fun e => aTerm (elemGet monsterAtk e)
            (elemGet item.resistance e))).sum) := by
  unfold ACombat rulerScale
  rw [hoff]
  omega

/-! ### Feasibility and the per-slot pick. -/

/-- A candidate is FEASIBLE for the slot iff it is level-feasible
(`playerLevel ≥ item.level`, i.e. Python NOT `state.level < stats.level`) AND its
type fits the slot. `_candidates_for_slot` returns exactly the feasible items. -/
def feasible (playerLevel : Int) (item : Item) : Bool :=
  decide (item.level ≤ playerLevel) && item.fits

/-- The feasible candidate sublist (`_candidates_for_slot`). -/
def candidates (playerLevel : Int) (items : List Item) : List Item :=
  items.filter (feasible playerLevel)

/-- Argmax of a nonempty list under integer `score`, mirroring Python's
`max(candidates, key=score)` left-fold semantics: scan left→right, keep the
current best unless a strictly-greater score appears (ties keep the EARLIER item,
matching CPython `max`). We fold over the tail starting from the head. -/
def argmaxBy (score : Item → Int) : Item → List Item → Item
  | best, [] => best
  | best, x :: xs =>
      if score x > score best then argmaxBy score x xs else argmaxBy score best xs

/-- The picked item for a slot, OPTION-typed (`none` = leave slot as-is because no
feasible candidate exists, Python `if not candidates: continue`). Otherwise we run
the no-downgrade rule against `current`:
* if `current = none` (empty slot), take the argmax candidate;
* else swap to the argmax ONLY on a STRICT score improvement, keeping `current`
  on ties / downgrades. -/
def pickSlot (score : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item) : Option Item :=
  match candidates playerLevel items with
  | [] => current
  | c :: cs =>
      let best := argmaxBy score c cs
      match current with
      | none => some best
      | some cur => if score best > score cur then some best else some cur

/-- The score of an option, treating `none` as the LOWEST: an empty slot scores
below any real item, so any feasible candidate is a strict improvement (Python:
`current_stats is None ⇒ result[slot] = best.code` unconditionally). We use this
only to STATE no-downgrade uniformly; the pick logic itself handles `none`
specially as above. -/
def optScore (score : Item → Int) : Option Item → Option Int
  | none => none
  | some i => some (score i)

/-! ### Argmax lemmas. -/

/-- The argmax is a member of `best :: xs`. -/
theorem argmaxBy_mem (score : Item → Int) (best : Item) (xs : List Item) :
    argmaxBy score best xs ∈ best :: xs := by
  induction xs generalizing best with
  | nil => simp [argmaxBy]
  | cons x xs ih =>
    unfold argmaxBy
    by_cases h : score x > score best
    · simp only [h, if_true]
      have := ih x
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inl he)))
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))
    · simp only [h, if_false]
      have := ih best
      rcases List.mem_cons.mp this with he | hm
      · exact List.mem_cons.mpr (Or.inl he)
      · exact List.mem_cons.mpr (Or.inr (List.mem_cons.mpr (Or.inr hm)))

/-- The argmax score is ≥ the score of every element of `best :: xs`. -/
theorem argmaxBy_ge (score : Item → Int) (best : Item) (xs : List Item) :
    ∀ y ∈ best :: xs, score y ≤ score (argmaxBy score best xs) := by
  induction xs generalizing best with
  | nil =>
    intro y hy
    simp only [argmaxBy]
    rcases List.mem_cons.mp hy with he | hm
    · subst he; exact Int.le_refl _
    · exact absurd hm (List.not_mem_nil)
  | cons x xs ih =>
    intro y hy
    unfold argmaxBy
    by_cases h : score x > score best
    · simp only [h, if_true]
      rcases List.mem_cons.mp hy with he | hm
      · subst he
        have hx : score x ≤ score (argmaxBy score x xs) := ih x x (List.mem_cons_self)
        omega
      · exact ih x y hm
    · simp only [h, if_false]
      have h' : score x ≤ score best := Int.not_lt.mp h
      rcases List.mem_cons.mp hy with he | hm
      · subst he; exact ih y y (List.mem_cons_self)
      · rcases List.mem_cons.mp hm with hx | hrest
        · subst hx
          have hb : score best ≤ score (argmaxBy score best xs) := ih best best (List.mem_cons_self)
          omega
        · exact ih best y (List.mem_cons_of_mem _ hrest)

/-- The argmax score is the MAX over `best :: xs`: it is attained by a member and
dominates all members. (Combines `argmaxBy_mem` and `argmaxBy_ge`.) -/
theorem argmaxBy_is_max (score : Item → Int) (best : Item) (xs : List Item) :
    (argmaxBy score best xs ∈ best :: xs) ∧
    (∀ y ∈ best :: xs, score y ≤ score (argmaxBy score best xs)) :=
  ⟨argmaxBy_mem score best xs, argmaxBy_ge score best xs⟩

/-- `argmaxBy` depends on the score only through its values on `best :: xs`: two
scores agreeing on every element there select the SAME argmax. -/
theorem argmaxBy_congr (s1 s2 : Item → Int) :
    ∀ (best : Item) (xs : List Item),
      (∀ i ∈ best :: xs, s1 i = s2 i) →
      argmaxBy s1 best xs = argmaxBy s2 best xs := by
  intro best xs
  induction xs generalizing best with
  | nil => intro _; rfl
  | cons x xs ih =>
    intro h
    unfold argmaxBy
    have hx : s1 x = s2 x := h x (by simp)
    have hb : s1 best = s2 best := h best (by simp)
    by_cases hc : s2 x > s2 best
    · rw [hx, hb, if_pos hc, if_pos hc]
      exact ih x (fun i hi => h i (List.mem_cons_of_mem best hi))
    · rw [hx, hb, if_neg hc, if_neg hc]
      refine ih best (fun i hi => ?_)
      rcases List.mem_cons.mp hi with he | hm
      · exact he ▸ h best (by simp)
      · exact h i (List.mem_cons_of_mem best (List.mem_cons_of_mem x hm))

/-! ### Pick theorems (the strong contracts). -/

/-- `pickslot_feasible`: a non-`none` result is a FEASIBLE candidate (level-feasible
AND its type fits the slot) — UNLESS it is just the retained `current` (which the
caller already had equipped). We state the substantive case: when the result is the
freshly-picked `best` (the argmax of the candidates), it satisfies `feasible`. This
is exactly what `_candidates_for_slot`'s filter guarantees: every element of
`candidates` is feasible, and `best` is one of them. -/
theorem pickslot_best_feasible (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    feasible playerLevel (argmaxBy score c cs) = true := by
  have hmem : argmaxBy score c cs ∈ c :: cs := argmaxBy_mem score c cs
  have : argmaxBy score c cs ∈ candidates playerLevel items := by
    rw [hcand]; exact hmem
  unfold candidates at this
  exact (List.mem_filter.mp this).2

/-- `pickslot_score_optimal`: when there IS a feasible candidate, the freshly-picked
`best` has the MAXIMUM score over all feasible candidates. (Pins the argmax to the
exact optimum the Python `max(candidates, key=score)` computes.) -/
theorem pickslot_score_optimal (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    ∀ y ∈ candidates playerLevel items,
      score y ≤ score (argmaxBy score c cs) := by
  intro y hy
  rw [hcand] at hy
  exact argmaxBy_ge score c cs y hy

/-- `pickslot_no_downgrade`: the result's score is ≥ the current item's score.
Stated over `optScore` with `none` as ⊥: an empty slot is improved by any pick, and
a filled slot is never downgraded (swap only on strict improvement, else keep).
We prove: when `current = some cur`, `score cur ≤ score (resulting item)`. -/
theorem pickslot_no_downgrade (score : Item → Int) (playerLevel : Int)
    (cur : Item) (items : List Item) :
    ∃ r, pickSlot score playerLevel (some cur) items = some r ∧ score cur ≤ score r := by
  unfold pickSlot
  cases hcand : candidates playerLevel items with
  | nil => exact ⟨cur, by simp, Int.le_refl _⟩
  | cons c cs =>
    simp only []
    by_cases h : score (argmaxBy score c cs) > score cur
    · refine ⟨argmaxBy score c cs, by simp [h], ?_⟩
      omega
    · have h' : score (argmaxBy score c cs) ≤ score cur := Int.not_lt.mp h
      exact ⟨cur, by simp [h], Int.le_refl _⟩

/-- `pickslot_ties_keep_current`: when `current = some cur` and `cur`'s score already
equals the max feasible score (so the argmax does NOT strictly beat it), the result
is EXACTLY `cur` — no swap on a tie. -/
theorem pickslot_ties_keep_current (score : Item → Int) (playerLevel : Int)
    (cur : Item) (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs)
    (htie : score (argmaxBy score c cs) = score cur) :
    pickSlot score playerLevel (some cur) items = some cur := by
  unfold pickSlot
  simp only [hcand]
  have : ¬ (score (argmaxBy score c cs) > score cur) := by omega
  simp [this]

/-- `pickslot_empty_fills`: an empty slot (`current = none`) with a feasible
candidate is filled with the argmax best (Python `current_stats is None ⇒
result[slot] = best.code`). -/
theorem pickslot_empty_fills (score : Item → Int) (playerLevel : Int)
    (items : List Item) (c : Item) (cs : List Item)
    (hcand : candidates playerLevel items = c :: cs) :
    pickSlot score playerLevel none items = some (argmaxBy score c cs) := by
  unfold pickSlot
  simp [hcand]

/-- `pickslot_no_candidates_keeps`: no feasible candidate ⇒ slot is left as-is
(Python `if not candidates: continue`). -/
theorem pickslot_no_candidates_keeps (score : Item → Int) (playerLevel : Int)
    (current : Option Item) (items : List Item)
    (hcand : candidates playerLevel items = []) :
    pickSlot score playerLevel current items = current := by
  unfold pickSlot
  simp [hcand]

/-! ### The weapon clamp theorem (what the `max(0, …)` earns). -/

/-- Each weapon term is nonnegative WHEN the attack is nonnegative: `atk ≥ 0 ⇒
atk * max(0, 100 - res) ≥ 0`. The `max 0` clamp guarantees the second factor is
`≥ 0` for ANY resistance (even `res > 100`); without it the factor `100 - res`
could be negative and flip the sign. -/
theorem wTerm_nonneg (atk monRes : Int) (h : 0 ≤ atk) : 0 ≤ wTerm atk monRes := by
  unfold wTerm
  have h2 : 0 ≤ max 0 (100 - monRes) := Int.le_max_left _ _
  exact Int.mul_nonneg h h2

/-- A list-sum of nonnegative integers is nonnegative. -/
theorem sum_nonneg_of_terms (l : List Int) (h : ∀ x ∈ l, 0 ≤ x) : 0 ≤ l.sum := by
  induction l with
  | nil => simp
  | cons a t ih =>
    simp only [List.sum_cons]
    have ha : 0 ≤ a := h a (List.mem_cons_self)
    have ht : 0 ≤ t.sum := ih (fun x hx => h x (List.mem_cons_of_mem _ hx))
    omega

/-- `weapon_score_nonneg`: `WScore ≥ 0` whenever every per-element attack is
nonnegative AND the crit percentage is nonnegative (which item stats always
are). This is THE theorem the clamp earns — a non-clamped surrogate
(`Σ atk * (100 - res)`) could go NEGATIVE when a monster's resistance exceeds
100, which would let `pick_loadout` prefer a strictly worse weapon. The
`max(0, …)` clamp makes the element sum monotone and nonnegative, and
`0 ≤ crit` keeps the `(200 + crit)` factor positive. -/
theorem weapon_score_nonneg (item : Item) (monsterRes : ElemStats)
    (hatk : ∀ e ∈ elements, 0 ≤ elemGet item.attack e)
    (hcrit : 0 ≤ item.crit) :
    0 ≤ WScore item monsterRes := by
  unfold WScore
  have hsum : 0 ≤ (elements.map
      (fun e => wTerm (elemGet item.attack e) (elemGet monsterRes e))).sum := by
    apply sum_nonneg_of_terms
    intro x hx
    rw [List.mem_map] at hx
    obtain ⟨e, he, hxe⟩ := hx
    rw [← hxe]
    exact wTerm_nonneg _ _ (hatk e he)
  exact Int.mul_nonneg hsum (by omega)

end Formal.EquipmentScoring
