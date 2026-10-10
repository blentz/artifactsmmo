-- @concept: consumables, combat, cost @property: monotonicity, dominance, validity
/-
The fight loop's recovery and XP rate (`docs/PLAN_consumable_utility.md`
increments 3-4, `src/artifactsmmo_cli/ai/loop_rate_core.py`).

## The model

All seconds are on ONE common scale `scale` (the Python passes every price and
the eat cooldown multiplied by the lcm of their denominators, so each is a
`Nat`); a Rest's whole seconds are multiplied by `scale` here. Recovery is a
minimum and a sum of these, so the scaled value is exactly `scale ×` the
Python `Fraction`.

* `restPart m maxHp` — 0 when nothing is missing, else the published Rest:
  `max 3 ⌈min m maxHp × 100 / maxHp⌉` (`rest_cooldown_core.rest_cooldown_seconds`;
  the Nat ceil is the same one `Formal.ActionCostNonneg.restCost` uses);
* a food is `(restore, price, held)` (USER 2026-10-09, "free until used up"):
  the first `held` units are free, every further unit costs `price` (its
  replacement); `price = none` means it has no replacement, so at most `held`
  units can be eaten. Eating `k` units is one use:
  `eatCost k = (k = 0 ? 0 : eat) + (k - held) × price` (the flat consumable
  cooldown; Nat subtraction is the `max 0`);
* `recovery` — per food, the minimum over `k ≤ foodBound` (`⌈m / restore⌉`, and
  no more than `held` for a food with no replacement) of eating `k` and
  recovering the rest with the remaining foods; with no food left, rest. The
  count bound loses no optimum: `recovery_le_planCost` — recovery is at most
  the cost of EVERY feasible count vector.
* a potion the fight drank is `(used, price, held)`: `potionCost = (used −
  held) × price`, and with no replacement it is priceable only while `used ≤
  held`; `consumedPrice` sums them (`none`: some drink cannot be paid for).
* `xpRate xp scale f r c = (xp × scale, f + r + c)` — XP per second as a
  `(num, den)` pair over the same scale, compared by
  `Formal.ConsumablePrice.qle`.

The increment-3 model is the `held = 0`, always-priced case
(`eatCost_held_zero`, `potionCost_held_zero`).
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

/-- A food: `(restore, price, held)`; a `none` price has no replacement. -/
abbrev Food := Nat × Option Nat × Nat

/-- The most units of a food the search tries: `⌈m / r⌉`, capped at `held`
when the food has no replacement. -/
def foodBound (m r : Nat) : Option Nat → Nat → Nat
  | some _, _ => countBound m r
  | none, h => min (countBound m r) h

/-- One use of `k` units: the flat cooldown once, plus the price of every unit
past the held ones. -/
def eatCost (k eat : Nat) : Option Nat → Nat → Nat
  | some p, h => (if k = 0 then 0 else eat) + (k - h) * p
  | none, _ => if k = 0 then 0 else eat

/-- The cheapest recovery of `m` missing HP (scaled seconds). -/
def recovery (scale eat maxHp : Nat) : List Food → Nat → Nat
  | [], m => scale * restPart m maxHp
  | (r, p, h) :: fs, m =>
    minUpTo (foodBound m r p h) (fun k => eatCost k eat p h + recovery scale eat maxHp fs (m - k * r))

/-- A count vector the foods can be eaten with: a food with no replacement is
eaten at most `held` times. Counts missing at the end are 0. -/
def feasible : List Food → List Nat → Prop
  | [], _ => True
  | _ :: fs, [] => feasible fs []
  | (_, p, h) :: fs, k :: ks => (p = none → k ≤ h) ∧ feasible fs ks

/-- What eating the count vector `ks` and resting the remainder costs. -/
def planCost (scale eat maxHp : Nat) : List Food → List Nat → Nat → Nat
  | [], _, m => scale * restPart m maxHp
  | _ :: fs, [], m => planCost scale eat maxHp fs [] m
  | (r, p, h) :: fs, k :: ks, m => eatCost k eat p h + planCost scale eat maxHp fs ks (m - k * r)

/-- The price of the `used` drinks of one potion past its `held` units. -/
def potionCost (u h : Nat) : Option Nat → Option Nat
  | some q => some ((u - h) * q)
  | none => if u ≤ h then some 0 else none

/-- The fight's consumed price over `(used, price, held)` potions; `none` when
some drink cannot be paid for. -/
def consumedPrice : List (Nat × Option Nat × Nat) → Option Nat
  | [] => some 0
  | (u, p, h) :: ps =>
    match potionCost u h p, consumedPrice ps with
    | some a, some b => some (a + b)
    | _, _ => none

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

/-- A wider search over pointwise cheaper values finds no more. -/
theorem minUpTo_le_of (f g : Nat → Nat) (n n' : Nat) (hn : n ≤ n')
    (hfg : ∀ k, k ≤ n → g k ≤ f k) : minUpTo n' g ≤ minUpTo n f :=
  le_minUpTo f _ n (fun k hk => Nat.le_trans (minUpTo_le g n' k (Nat.le_trans hk hn)) (hfg k hk))

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

theorem eatCost_zero (eat h : Nat) (p : Option Nat) : eatCost 0 eat p h = 0 := by
  cases p <;> simp [eatCost]

/-- The increment-3 cost: nothing held, every unit at its price. -/
theorem eatCost_held_zero (k eat q : Nat) :
    eatCost k eat (some q) 0 = (if k = 0 then 0 else eat) + k * q := by
  simp [eatCost]

theorem eatCost_mono (k k' eat h : Nat) (p : Option Nat) (hk : k ≤ k') :
    eatCost k eat p h ≤ eatCost k' eat p h := by
  have hc : (if k = 0 then 0 else eat) ≤ (if k' = 0 then 0 else eat) := by
    by_cases h0 : k = 0
    · simp [h0]
    · have : ¬ k' = 0 := by omega
      simp [h0, this]
  cases p with
  | none => exact hc
  | some q =>
    show (if k = 0 then 0 else eat) + (k - h) * q ≤ (if k' = 0 then 0 else eat) + (k' - h) * q
    exact Nat.add_le_add hc (Nat.mul_le_mul_right _ (by omega))

theorem eatCost_price_mono (k eat h p p' : Nat) (hp : p' ≤ p) :
    eatCost k eat (some p') h ≤ eatCost k eat (some p) h := by
  show (if k = 0 then 0 else eat) + (k - h) * p' ≤ (if k = 0 then 0 else eat) + (k - h) * p
  exact Nat.add_le_add_left (Nat.mul_le_mul_left _ hp) _

theorem eatCost_held_anti (k eat h h' : Nat) (p : Option Nat) (hh : h ≤ h') :
    eatCost k eat p h' ≤ eatCost k eat p h := by
  cases p with
  | none => exact Nat.le_refl _
  | some q =>
    show (if k = 0 then 0 else eat) + (k - h') * q ≤ (if k = 0 then 0 else eat) + (k - h) * q
    exact Nat.add_le_add_left (Nat.mul_le_mul_right _ (by omega)) _

theorem foodBound_held_mono (m r h h' : Nat) (p : Option Nat) (hh : h ≤ h') :
    foodBound m r p h ≤ foodBound m r p h' := by
  cases p with
  | none => show min (countBound m r) h ≤ min (countBound m r) h'; omega
  | some _ => exact Nat.le_refl _

/-- A count inside the search is feasible. -/
theorem foodBound_feasible (m r h k : Nat) (p : Option Nat) (hk : k ≤ foodBound m r p h) :
    p = none → k ≤ h := by
  intro hp; subst hp; simp only [foodBound] at hk; omega

/-- A feasible count past the search bound eats the whole deficit at the bound. -/
theorem foodBound_cover (m r h k : Nat) (p : Option Nat) (hr : 0 < r)
    (hk : foodBound m r p h < k) (hfeas : p = none → k ≤ h) :
    m - foodBound m r p h * r = 0 := by
  have hcov := countBound_covers m r hr
  cases p with
  | some q =>
    show m - countBound m r * r = 0
    omega
  | none =>
    have hkh := hfeas rfl
    simp only [foodBound] at hk ⊢
    have hb : min (countBound m r) h = countBound m r := by omega
    rw [hb]; omega

/-! ## Theorems -/

/-- NEVER WORSE THAN RESTING: recovery is at most resting the whole deficit. -/
theorem recovery_le_rest (scale eat maxHp : Nat) :
    ∀ (fs : List Food) (m : Nat),
      recovery scale eat maxHp fs m ≤ scale * restPart m maxHp
  | [], _ => Nat.le_refl _
  | (r, p, h) :: fs, m => by
    show minUpTo (foodBound m r p h)
        (fun k => eatCost k eat p h + recovery scale eat maxHp fs (m - k * r)) ≤ _
    refine Nat.le_trans (minUpTo_le _ _ 0 (Nat.zero_le _)) ?_
    simp only [eatCost_zero, Nat.zero_mul, Nat.zero_add, Nat.sub_zero]
    exact recovery_le_rest scale eat maxHp fs m

/-- MORE HP MISSING NEVER RECOVERS FASTER (every food restores something). -/
theorem recovery_mono_missing (scale eat maxHp : Nat) :
    ∀ (fs : List Food), (∀ f ∈ fs, 0 < f.1) → ∀ (m m' : Nat), m ≤ m' →
      recovery scale eat maxHp fs m ≤ recovery scale eat maxHp fs m'
  | [], _, m, m', h => Nat.mul_le_mul_left _ (restPart_mono m m' maxHp h)
  | (r, p, hd) :: fs, hpos, m, m', h => by
    have hr : 0 < r := hpos (r, p, hd) (List.mem_cons_self ..)
    have htail : ∀ f ∈ fs, 0 < f.1 := fun f hf => hpos f (List.mem_cons_of_mem _ hf)
    have ih := recovery_mono_missing scale eat maxHp fs htail
    show minUpTo (foodBound m r p hd)
        (fun j => eatCost j eat p hd + recovery scale eat maxHp fs (m - j * r))
      ≤ minUpTo (foodBound m' r p hd)
        (fun j => eatCost j eat p hd + recovery scale eat maxHp fs (m' - j * r))
    apply le_minUpTo
    intro k hk'
    by_cases hk : k ≤ foodBound m r p hd
    · refine Nat.le_trans (minUpTo_le _ _ k hk) ?_
      exact Nat.add_le_add_left (ih _ _ (Nat.sub_le_sub_right h _)) _
    · refine Nat.le_trans (minUpTo_le _ _ (foodBound m r p hd) (Nat.le_refl _)) ?_
      have hzero := foodBound_cover m r hd k p hr (by omega) (foodBound_feasible m' r hd k p hk')
      show eatCost (foodBound m r p hd) eat p hd
          + recovery scale eat maxHp fs (m - foodBound m r p hd * r) ≤ _
      rw [hzero]
      exact Nat.add_le_add (eatCost_mono _ _ _ _ _ (by omega)) (ih _ _ (Nat.zero_le _))

/-- ANOTHER FOOD NEVER SLOWS RECOVERY: eating none of it is always an option. -/
theorem add_food_le (scale eat maxHp r h : Nat) (p : Option Nat) (fs : List Food) (m : Nat) :
    recovery scale eat maxHp ((r, p, h) :: fs) m ≤ recovery scale eat maxHp fs m := by
  show minUpTo (foodBound m r p h)
      (fun k => eatCost k eat p h + recovery scale eat maxHp fs (m - k * r)) ≤ _
  refine Nat.le_trans (minUpTo_le _ _ 0 (Nat.zero_le _)) ?_
  simp [eatCost_zero]

/-- A cheaper menu stays cheaper with one more food in front of both. -/
theorem cons_mono (scale eat maxHp : Nat) (f : Food) (A B : List Food)
    (hAB : ∀ m, recovery scale eat maxHp A m ≤ recovery scale eat maxHp B m) (m : Nat) :
    recovery scale eat maxHp (f :: A) m ≤ recovery scale eat maxHp (f :: B) m := by
  obtain ⟨r, p, h⟩ := f
  exact minUpTo_mono _ _ (fun k => Nat.add_le_add_left (hAB _) _) _

/-- A food no dearer at the head of a menu is no dearer anywhere in it. -/
theorem replace_mono (scale eat maxHp : Nat) (f g : Food) (post : List Food)
    (hgf : ∀ m, recovery scale eat maxHp (g :: post) m ≤ recovery scale eat maxHp (f :: post) m) :
    ∀ (pre : List Food) (m : Nat),
      recovery scale eat maxHp (pre ++ g :: post) m ≤ recovery scale eat maxHp (pre ++ f :: post) m
  | [], m => hgf m
  | e :: pre, m => cons_mono scale eat maxHp e _ _ (replace_mono scale eat maxHp f g post hgf pre) m

/-- A CHEAPER FOOD NEVER SLOWS RECOVERY, wherever it sits in the list. -/
theorem price_mono (scale eat maxHp r h p p' : Nat) (post : List Food) (hp : p' ≤ p)
    (pre : List Food) (m : Nat) :
    recovery scale eat maxHp (pre ++ (r, some p', h) :: post) m
      ≤ recovery scale eat maxHp (pre ++ (r, some p, h) :: post) m :=
  replace_mono scale eat maxHp _ _ post (fun m => by
    show minUpTo (countBound m r)
        (fun k => eatCost k eat (some p') h + recovery scale eat maxHp post (m - k * r))
      ≤ minUpTo (countBound m r)
        (fun k => eatCost k eat (some p) h + recovery scale eat maxHp post (m - k * r))
    exact minUpTo_mono _ _
      (fun k => Nat.add_le_add_right (eatCost_price_mono k eat h p p' hp) _) _) pre m

/-- A FREE FOOD NEVER SLOWS RECOVERY: price 0 is the cheapest price. -/
theorem free_food_le (scale eat maxHp r h p : Nat) (pre post : List Food) (m : Nat) :
    recovery scale eat maxHp (pre ++ (r, some 0, h) :: post) m
      ≤ recovery scale eat maxHp (pre ++ (r, some p, h) :: post) m :=
  price_mono scale eat maxHp r h p 0 post (Nat.zero_le p) pre m

/-- MORE HELD NEVER SLOWS RECOVERY (USER "free until used up"): a held unit is
free, and a food with no replacement can be eaten up to its held count. -/
theorem held_free_le (scale eat maxHp r h h' : Nat) (p : Option Nat) (post : List Food)
    (hh : h ≤ h') (pre : List Food) (m : Nat) :
    recovery scale eat maxHp (pre ++ (r, p, h') :: post) m
      ≤ recovery scale eat maxHp (pre ++ (r, p, h) :: post) m :=
  replace_mono scale eat maxHp _ _ post (fun m => by
    show minUpTo (foodBound m r p h')
        (fun k => eatCost k eat p h' + recovery scale eat maxHp post (m - k * r))
      ≤ minUpTo (foodBound m r p h)
        (fun k => eatCost k eat p h + recovery scale eat maxHp post (m - k * r))
    exact minUpTo_le_of _ _ _ _ (foodBound_held_mono m r h h' p hh)
      (fun k _ => Nat.add_le_add_right (eatCost_held_anti k eat h h' p hh) _)) pre m

/-- A REPLACEMENT NEVER SLOWS RECOVERY: with a price, the held units are still
free and more can be bought past them. -/
theorem priced_le_unpriced (scale eat maxHp r h q : Nat) (pre post : List Food) (m : Nat) :
    recovery scale eat maxHp (pre ++ (r, some q, h) :: post) m
      ≤ recovery scale eat maxHp (pre ++ (r, none, h) :: post) m :=
  replace_mono scale eat maxHp _ _ post (fun m => by
    show minUpTo (countBound m r)
        (fun k => eatCost k eat (some q) h + recovery scale eat maxHp post (m - k * r))
      ≤ minUpTo (min (countBound m r) h)
        (fun k => eatCost k eat none h + recovery scale eat maxHp post (m - k * r))
    refine minUpTo_le_of _ _ _ _ (Nat.min_le_left _ _) (fun k hk => ?_)
    have hkh : k ≤ h := Nat.le_trans hk (Nat.min_le_right _ _)
    have hz : k - h = 0 := by omega
    show (if k = 0 then 0 else eat) + (k - h) * q + _ ≤ (if k = 0 then 0 else eat) + _
    rw [hz, Nat.zero_mul, Nat.add_zero]
    exact Nat.le_refl _) pre m

/-- OPTIMALITY: recovery is at most the cost of every feasible count vector, so
the bounded search loses no plan. -/
theorem recovery_le_planCost (scale eat maxHp : Nat) :
    ∀ (fs : List Food), (∀ f ∈ fs, 0 < f.1) → ∀ (ks : List Nat) (m : Nat), feasible fs ks →
      recovery scale eat maxHp fs m ≤ planCost scale eat maxHp fs ks m
  | [], _, _, _, _ => Nat.le_refl _
  | (r, p, h) :: fs, hpos, [], m, hf => by
    have htail : ∀ f ∈ fs, 0 < f.1 := fun f hf => hpos f (List.mem_cons_of_mem _ hf)
    refine Nat.le_trans (add_food_le scale eat maxHp r h p fs m) ?_
    exact recovery_le_planCost scale eat maxHp fs htail [] m hf
  | (r, p, h) :: fs, hpos, k :: ks, m, hf => by
    have hr : 0 < r := hpos (r, p, h) (List.mem_cons_self ..)
    have htail : ∀ f ∈ fs, 0 < f.1 := fun f hf => hpos f (List.mem_cons_of_mem _ hf)
    have ih := recovery_le_planCost scale eat maxHp fs htail ks
    obtain ⟨hk, hks⟩ : (p = none → k ≤ h) ∧ feasible fs ks := hf
    show minUpTo (foodBound m r p h)
        (fun j => eatCost j eat p h + recovery scale eat maxHp fs (m - j * r))
      ≤ eatCost k eat p h + planCost scale eat maxHp fs ks (m - k * r)
    by_cases hb : k ≤ foodBound m r p h
    · exact Nat.le_trans (minUpTo_le _ _ k hb) (Nat.add_le_add_left (ih _ hks) _)
    · refine Nat.le_trans (minUpTo_le _ _ (foodBound m r p h) (Nat.le_refl _)) ?_
      have hzero := foodBound_cover m r h k p hr (by omega) hk
      show eatCost (foodBound m r p h) eat p h
          + recovery scale eat maxHp fs (m - foodBound m r p h * r) ≤ _
      rw [hzero]
      exact Nat.add_le_add (eatCost_mono _ _ _ _ _ (by omega))
        (Nat.le_trans (recovery_mono_missing scale eat maxHp fs htail 0 _ (Nat.zero_le _))
          (ih _ hks))

/-- The increment-3 consumed price: nothing held, every drink at its price. -/
theorem potionCost_held_zero (u q : Nat) : potionCost u 0 (some q) = some (u * q) := by
  simp [potionCost]

theorem potionCost_held_le (u h h' c : Nat) (p : Option Nat) (hh : h ≤ h')
    (hc : potionCost u h p = some c) : ∃ c', potionCost u h' p = some c' ∧ c' ≤ c := by
  cases p with
  | some q =>
    simp only [potionCost, Option.some.injEq] at hc
    subst hc
    exact ⟨(u - h') * q, rfl, Nat.mul_le_mul_right _ (by omega)⟩
  | none =>
    by_cases hu : u ≤ h
    · have hu' : u ≤ h' := by omega
      exact ⟨0, by simp [potionCost, hu'], Nat.zero_le _⟩
    · simp [potionCost, hu] at hc

/-- MORE HELD NEVER RAISES THE CONSUMED PRICE (USER "free until used up"): a
payable fight stays payable, for no more, wherever the potion sits. -/
theorem consumed_held_free_le (u h h' : Nat) (p : Option Nat)
    (post : List (Nat × Option Nat × Nat)) (hh : h ≤ h') :
    ∀ (pre : List (Nat × Option Nat × Nat)) (c : Nat),
      consumedPrice (pre ++ (u, p, h) :: post) = some c →
      ∃ c', consumedPrice (pre ++ (u, p, h') :: post) = some c' ∧ c' ≤ c
  | [], c, hc => by
    simp only [List.nil_append, consumedPrice] at hc ⊢
    cases ha : potionCost u h p with
    | none => simp [ha] at hc
    | some a =>
      cases hb : consumedPrice post with
      | none => simp [ha, hb] at hc
      | some b =>
        simp only [ha, hb, Option.some.injEq] at hc
        obtain ⟨a', ha', hle⟩ := potionCost_held_le u h h' a p hh ha
        exact ⟨a' + b, by simp [ha'], by omega⟩
  | (u0, p0, h0) :: pre, c, hc => by
    simp only [List.cons_append, consumedPrice] at hc ⊢
    cases ha : potionCost u0 h0 p0 with
    | none => simp [ha] at hc
    | some a =>
      cases hb : consumedPrice (pre ++ (u, p, h) :: post) with
      | none => simp [ha, hb] at hc
      | some b =>
        simp only [ha, hb, Option.some.injEq] at hc
        obtain ⟨b', hb', hle⟩ := consumed_held_free_le u h h' p post hh pre b hb
        exact ⟨a + b', by simp [hb'], by omega⟩

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
theorem rate_antitone_missing (xp scale eat maxHp f c : Nat) (fs : List Food)
    (hpos : ∀ g ∈ fs, 0 < g.1) (m m' : Nat) (h : m ≤ m') :
    qle (xpRate xp scale f (recovery scale eat maxHp fs m') c)
        (xpRate xp scale f (recovery scale eat maxHp fs m) c) :=
  xpRate_antitone xp scale f f _ _ c c (Nat.le_refl _)
    (recovery_mono_missing scale eat maxHp fs hpos m m' h) (Nat.le_refl _)

/-! ## Witnesses -/

-- 60 of 100 HP missing: Rest is 60 s. One free 50-HP food (eat 3 s) then rest
-- 10 HP (10 s) = 13 s; two of them = 3 s.
example : recovery 1 3 100 [] 60 = 60 := by decide
example : recovery 1 3 100 [(50, some 0, 0)] 60 = 3 := by decide
-- A dear food (40 s a unit): one of them (43 s) then rest 10 HP = 53 s.
example : recovery 1 3 100 [(50, some 40, 0)] 60 = 53 := by decide
-- Dearer still (60 s a unit): never eaten, Rest wins.
example : recovery 1 3 100 [(50, some 60, 0)] 60 = 60 := by decide
-- ...unless two are held: both free, one use, 3 s.
example : recovery 1 3 100 [(50, some 60, 2)] 60 = 3 := by decide
-- One held, no replacement: eat it (3 s) and rest 10 HP (10 s).
example : recovery 1 3 100 [(50, none, 1)] 60 = 13 := by decide
-- Nothing missing: nothing to do (no three-second floor).
example : recovery 1 3 100 [(50, some 0, 0)] 0 = 0 := by decide
-- Five drinks, three held, 7 s each past them: 14 s; an unpriced sixth: none.
example : consumedPrice [(5, some 7, 3)] = some 14 := by decide
example : consumedPrice [(5, some 7, 3), (6, none, 5)] = none := by decide
example : consumedPrice [(2, none, 5)] = some 0 := by decide
-- 30 XP over a 30 s fight and 60 s of recovery: 1/3 XP per second.
example : xpRate 30 1 30 60 0 = (30, 90) := by decide

end Formal.LoopRate
