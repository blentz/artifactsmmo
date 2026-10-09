-- @concept: consumables, combat, cost @property: monotonicity, dominance, validity
/-
The fight loop's recovery and XP rate (`docs/PLAN_consumable_utility.md`
increment 3, `src/artifactsmmo_cli/ai/loop_rate_core.py`).

## The model

All seconds are on ONE common scale `scale` (the Python passes every price and
the eat cooldown multiplied by the lcm of their denominators, so each is a
`Nat`); a Rest's whole seconds are multiplied by `scale` here. Recovery is a
minimum and a sum of these, so the scaled value is exactly `scale ×` the
Python `Fraction`.

* `restPart m maxHp` — 0 when nothing is missing, else the published Rest:
  `max 3 ⌈min m maxHp × 100 / maxHp⌉` (`rest_cooldown_core.rest_cooldown_seconds`;
  the Nat ceil is the same one `Formal.ActionCostNonneg.restCost` uses);
* a food is `(restore, price)`; eating `k` units of it is one use:
  `eatCost k = (k = 0 ? 0 : eat) + k × price` (the flat consumable cooldown);
* `recovery` — per food, the minimum over `k ≤ countBound m restore =
  ⌈m / restore⌉` of eating `k` and recovering the rest with the remaining foods;
  with no food left, rest. The count bound loses no optimum: past it the
  remainder is already 0 and the cost only grows (`recovery_mono_missing`'s
  proof uses exactly this).
* `xpRate xp scale f r c = (xp × scale, f + r + c)` — XP per second as a
  `(num, den)` pair over the same scale, compared by
  `Formal.ConsumablePrice.qle`.
-/

import Formal.ConsumablePrice

namespace Formal.LoopRate

open Formal.ConsumablePrice (qle)

/-- Seconds of resting `missing` HP off; 0 with nothing missing. -/
def restPart (missing maxHp : Nat) : Nat :=
  if missing = 0 then 0 else max 3 ((min missing maxHp * 100 + maxHp - 1) / maxHp)

/-- ⌈m / r⌉: the most units of an `r`-HP food worth eating for `m` HP. -/
def countBound (m r : Nat) : Nat := (m + r - 1) / r

/-- The minimum of `f 0, …, f n`. -/
def minUpTo : Nat → (Nat → Nat) → Nat
  | 0, f => f 0
  | n + 1, f => min (minUpTo n f) (f (n + 1))

/-- One use of `k` units: the flat cooldown once, plus the price per unit. -/
def eatCost (k eat price : Nat) : Nat := (if k = 0 then 0 else eat) + k * price

/-- The cheapest recovery of `m` missing HP (scaled seconds). -/
def recovery (scale eat maxHp : Nat) : List (Nat × Nat) → Nat → Nat
  | [], m => scale * restPart m maxHp
  | (r, p) :: fs, m =>
    minUpTo (countBound m r) (fun k => eatCost k eat p + recovery scale eat maxHp fs (m - k * r))

/-- XP per second as `(num, den)` over the common scale. -/
def xpRate (xp scale fight recov consumed : Nat) : Nat × Nat :=
  (xp * scale, fight + recov + consumed)

/-! ## Lemmas -/

theorem minUpTo_le (f : Nat → Nat) : ∀ (n k : Nat), k ≤ n → minUpTo n f ≤ f k
  | 0, k, h => by
    have : k = 0 := by omega
    subst this; exact Nat.le_refl _
  | n + 1, k, h => by
    show min (minUpTo n f) (f (n + 1)) ≤ f k
    by_cases hk : k ≤ n
    · exact Nat.le_trans (Nat.min_le_left _ _) (minUpTo_le f n k hk)
    · have : k = n + 1 := by omega
      subst this; exact Nat.min_le_right _ _

theorem le_minUpTo (f : Nat → Nat) (c : Nat) :
    ∀ (n : Nat), (∀ k, k ≤ n → c ≤ f k) → c ≤ minUpTo n f
  | 0, h => h 0 (Nat.le_refl _)
  | n + 1, h => by
    show c ≤ min (minUpTo n f) (f (n + 1))
    exact Nat.le_min.mpr ⟨le_minUpTo f c n (fun k hk => h k (by omega)),
      h (n + 1) (Nat.le_refl _)⟩

theorem minUpTo_mono (f g : Nat → Nat) (hfg : ∀ k, f k ≤ g k) :
    ∀ (n : Nat), minUpTo n f ≤ minUpTo n g
  | 0 => hfg 0
  | n + 1 => by
    show min (minUpTo n f) (f (n + 1)) ≤ min (minUpTo n g) (g (n + 1))
    exact Nat.le_min.mpr
      ⟨Nat.le_trans (Nat.min_le_left _ _) (minUpTo_mono f g hfg n),
       Nat.le_trans (Nat.min_le_right _ _) (hfg (n + 1))⟩

theorem restPart_mono (m m' maxHp : Nat) (h : m ≤ m') :
    restPart m maxHp ≤ restPart m' maxHp := by
  unfold restPart
  by_cases hm : m = 0
  · simp [hm]
  · have hm' : ¬ m' = 0 := by omega
    simp only [hm, hm', if_false]
    have hmin : min m maxHp ≤ min m' maxHp := by omega
    have hnum : min m maxHp * 100 + maxHp - 1 ≤ min m' maxHp * 100 + maxHp - 1 := by
      have := Nat.mul_le_mul_right 100 hmin
      omega
    have hdiv := Nat.div_le_div_right (c := maxHp) hnum
    omega

theorem countBound_covers (m r : Nat) (hr : 0 < r) : m ≤ countBound m r * r := by
  unfold countBound
  have hd := Nat.div_add_mod (m + r - 1) r
  have hlt := Nat.mod_lt (m + r - 1) hr
  rw [Nat.mul_comm]
  omega

theorem eatCost_mono (k k' eat p : Nat) (h : k ≤ k') : eatCost k eat p ≤ eatCost k' eat p := by
  unfold eatCost
  have hm : k * p ≤ k' * p := Nat.mul_le_mul_right _ h
  by_cases hk : k = 0
  · subst hk; simp
  · have hk' : ¬ k' = 0 := by omega
    simp only [hk, hk', if_false]
    omega

theorem eatCost_price_mono (k eat p p' : Nat) (h : p' ≤ p) : eatCost k eat p' ≤ eatCost k eat p := by
  unfold eatCost
  have : k * p' ≤ k * p := Nat.mul_le_mul_left _ h
  omega

/-! ## Theorems -/

/-- NEVER WORSE THAN RESTING: recovery is at most resting the whole deficit. -/
theorem recovery_le_rest (scale eat maxHp : Nat) :
    ∀ (fs : List (Nat × Nat)) (m : Nat),
      recovery scale eat maxHp fs m ≤ scale * restPart m maxHp
  | [], _ => Nat.le_refl _
  | (r, p) :: fs, m => by
    show minUpTo (countBound m r)
        (fun k => eatCost k eat p + recovery scale eat maxHp fs (m - k * r)) ≤ _
    refine Nat.le_trans (minUpTo_le _ _ 0 (Nat.zero_le _)) ?_
    have h0 : eatCost 0 eat p = 0 := by simp [eatCost]
    simp only [h0, Nat.zero_mul, Nat.zero_add, Nat.sub_zero]
    exact recovery_le_rest scale eat maxHp fs m

/-- MORE HP MISSING NEVER RECOVERS FASTER (every food restores something). -/
theorem recovery_mono_missing (scale eat maxHp : Nat) :
    ∀ (fs : List (Nat × Nat)), (∀ f ∈ fs, 0 < f.1) → ∀ (m m' : Nat), m ≤ m' →
      recovery scale eat maxHp fs m ≤ recovery scale eat maxHp fs m'
  | [], _, m, m', h => Nat.mul_le_mul_left _ (restPart_mono m m' maxHp h)
  | (r, p) :: fs, hpos, m, m', h => by
    have hr : 0 < r := hpos (r, p) (List.mem_cons_self ..)
    have htail : ∀ f ∈ fs, 0 < f.1 := fun f hf => hpos f (List.mem_cons_of_mem _ hf)
    have ih := recovery_mono_missing scale eat maxHp fs htail
    show minUpTo (countBound m r)
        (fun k => eatCost k eat p + recovery scale eat maxHp fs (m - k * r))
      ≤ minUpTo (countBound m' r)
        (fun k => eatCost k eat p + recovery scale eat maxHp fs (m' - k * r))
    apply le_minUpTo
    intro k _
    by_cases hk : k ≤ countBound m r
    · refine Nat.le_trans (minUpTo_le _ _ k hk) ?_
      exact Nat.add_le_add_left (ih _ _ (Nat.sub_le_sub_right h _)) _
    · refine Nat.le_trans (minUpTo_le _ _ (countBound m r) (Nat.le_refl _)) ?_
      have hcov := countBound_covers m r hr
      have hzero : m - countBound m r * r = 0 := by omega
      show eatCost (countBound m r) eat p
          + recovery scale eat maxHp fs (m - countBound m r * r) ≤ _
      rw [hzero]
      exact Nat.add_le_add (eatCost_mono _ _ _ _ (by omega)) (ih _ _ (Nat.zero_le _))

/-- ANOTHER FOOD NEVER SLOWS RECOVERY: eating none of it is always an option. -/
theorem add_food_le (scale eat maxHp r p : Nat) (fs : List (Nat × Nat)) (m : Nat) :
    recovery scale eat maxHp ((r, p) :: fs) m ≤ recovery scale eat maxHp fs m := by
  show minUpTo (countBound m r)
      (fun k => eatCost k eat p + recovery scale eat maxHp fs (m - k * r)) ≤ _
  refine Nat.le_trans (minUpTo_le _ _ 0 (Nat.zero_le _)) ?_
  simp [eatCost]

/-- A cheaper menu stays cheaper with one more food in front of both. -/
theorem cons_mono (scale eat maxHp : Nat) (f : Nat × Nat) (A B : List (Nat × Nat))
    (h : ∀ m, recovery scale eat maxHp A m ≤ recovery scale eat maxHp B m) (m : Nat) :
    recovery scale eat maxHp (f :: A) m ≤ recovery scale eat maxHp (f :: B) m := by
  obtain ⟨r, p⟩ := f
  exact minUpTo_mono _ _ (fun k => Nat.add_le_add_left (h _) _) _

/-- A CHEAPER FOOD NEVER SLOWS RECOVERY, wherever it sits in the list. -/
theorem price_mono (scale eat maxHp r p p' : Nat) (post : List (Nat × Nat)) (h : p' ≤ p) :
    ∀ (pre : List (Nat × Nat)) (m : Nat),
      recovery scale eat maxHp (pre ++ (r, p') :: post) m
        ≤ recovery scale eat maxHp (pre ++ (r, p) :: post) m
  | [], _ => minUpTo_mono _ _ (fun k => Nat.add_le_add_right (eatCost_price_mono k eat p p' h) _) _
  | f :: pre, m => cons_mono scale eat maxHp f _ _ (price_mono scale eat maxHp r p p' post h pre) m

/-- A FREE FOOD NEVER SLOWS RECOVERY: price 0 is the cheapest price. -/
theorem free_food_le (scale eat maxHp r p : Nat) (pre post : List (Nat × Nat)) (m : Nat) :
    recovery scale eat maxHp (pre ++ (r, 0) :: post) m
      ≤ recovery scale eat maxHp (pre ++ (r, p) :: post) m :=
  price_mono scale eat maxHp r p 0 post (Nat.zero_le p) pre m

/-- NO XP, NO RATE. -/
theorem xpRate_zero (scale f r c : Nat) : (xpRate 0 scale f r c).1 = 0 := by
  simp [xpRate]

/-- A positive fight duration keeps the rate's denominator positive. -/
theorem xpRate_den_pos (xp scale f r c : Nat) (h : 0 < f) : 0 < (xpRate xp scale f r c).2 := by
  simp only [xpRate]; omega

/-- LONGER IS SLOWER: the rate is antitone in each seconds term. -/
theorem xpRate_antitone (xp scale f f' r r' c c' : Nat)
    (hf : f ≤ f') (hr : r ≤ r') (hc : c ≤ c') :
    qle (xpRate xp scale f' r' c') (xpRate xp scale f r c) := by
  show xp * scale * (f + r + c) ≤ xp * scale * (f' + r' + c')
  exact Nat.mul_le_mul_left _ (by omega)

/-- MORE HP LOST NEVER RAISES THE RATE: a fight that ends lower recovers no
faster, so the loop is no faster. -/
theorem rate_antitone_missing (xp scale eat maxHp f c : Nat) (fs : List (Nat × Nat))
    (hpos : ∀ g ∈ fs, 0 < g.1) (m m' : Nat) (h : m ≤ m') :
    qle (xpRate xp scale f (recovery scale eat maxHp fs m') c)
        (xpRate xp scale f (recovery scale eat maxHp fs m) c) :=
  xpRate_antitone xp scale f f _ _ c c (Nat.le_refl _)
    (recovery_mono_missing scale eat maxHp fs hpos m m' h) (Nat.le_refl _)

/-! ## Witnesses -/

-- 60 of 100 HP missing: Rest is 60 s. One free 50-HP food (eat 3 s) then rest
-- 10 HP (10 s) = 13 s; two of them = 3 s.
example : recovery 1 3 100 [] 60 = 60 := by decide
example : recovery 1 3 100 [(50, 0)] 60 = 3 := by decide
-- A dear food (40 s a unit): one of them (43 s) then rest 10 HP = 53 s.
example : recovery 1 3 100 [(50, 40)] 60 = 53 := by decide
-- Dearer still (60 s a unit): never eaten, Rest wins.
example : recovery 1 3 100 [(50, 60)] 60 = 60 := by decide
-- Nothing missing: nothing to do (no three-second floor).
example : recovery 1 3 100 [(50, 0)] 0 = 0 := by decide
-- 30 XP over a 30 s fight and 60 s of recovery: 1/3 XP per second.
example : xpRate 30 1 30 60 0 = (30, 90) := by decide

end Formal.LoopRate
