-- @concept: combat, consumables @property: validity, monotonicity
/-
Fight odds (spec docs/superpowers/specs/2026-10-15-fight-odds-design.md §1).
The exact ending distribution of a fight over per-turn crit rolls, as an
UNMERGED tree; `ai/fight_odds_core.fight_odds` merges identical states.

## Results

* `fightOdds_sum_one` — the endings' probabilities sum to 1.
* `fightOdds_noCrit` — with both crit chances 0 and no burn the tree is the
  single ending of `Formal.FightOutcome.fightOutcome` (for a monster with
  positive HP; that walk charges burn as a flat bound, the tree as ticks).
* `fightOdds_win_mono_stock` — more restore stock never lowers P(win).
* `fightOdds_win_mono_hp` — with no restore stock, more starting HP never
  lowers P(win). (With stock it is FALSE: see the theorem's comment.)
* `winProb_eq_one_of_worst` — a fight won with no stock on the worst-case path
  (no player crit, every monster turn a crit) is won with probability 1 at any stock.
* `winProb_ge_critBound` — the counted-crit floor: if the no-stock path on which
  the player never crits and the monster crits its first `c` turns wins, P(win)
  at any stock is at least P(at most `c` of that path's monster turns crit)
  (`critBound`, a single path plus a binomial table, cheap for the kernel).

Lean core only — no Mathlib.
-/
import Formal.FightOutcome

namespace Formal.FightOdds

open Formal.FightOutcome (Terms scale gate roundsToKill effHp drink fightOutcome Exit walk
  coupled coupled_le coupled_sub gate_none_dieStep)
open Formal.PredictWin (maxTurns ceilDiv ceilDiv_mul_ge ceilDiv_pred_mul_lt ceilDiv_pos)

/-- One round's charges ×10000 and the crit chances in percent. -/
structure Damage where
  monsterHp : Int
  killNormal : Int
  killCrit : Int
  pCrit : Nat
  dieNormal : Int
  dieCrit : Int
  mCrit : Nat
  /-- The burn ticks in order, ×10000; `[]` without burn. -/
  burn : List Int

structure Ending where
  win : Bool
  turns : Int
  hpEnd : Int
  used : Nat
  deriving DecidableEq, Repr

/-- The outcomes of one crit roll: `(probability, amount)`, no zero branch. -/
def roll (pct : Nat) (normal crit : Int) : List (Rat × Int) :=
  [(((100 - pct : Nat) : Rat) / 100, normal), (((pct : Nat) : Rat) / 100, crit)].filter
    (fun b => b.1 ≠ 0)

/-- The burn tick of the player's turn in round `r`: the monster burns on its
first turn, so tick `i` lands in round `i + 2` when the player moves first and
in round `i + 1` when the monster does; past the last tick it is 0. -/
def tick (d : Damage) (pf : Bool) (r : Int) : Int :=
  let i := if pf then r - 2 else r - 1
  if i < 0 then 0 else d.burn.getD i.toNat 0

/-- Scale every probability of a list. -/
def scaleBy (w : Rat) (xs : List (Rat × Ending)) : List (Rat × Ending) :=
  xs.map fun e => (w * e.1, e.2)

/-- The tree from round `r` with `fuel` rounds left. A player turn takes its
burn tick, a loss if it empties the pool, then drinks (`q := drink …`)
before it hits. -/
def tree (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat) :
    Nat → Int → Int → Int → Nat → List (Rat × Ending)
  | 0, r, _, _, k => [(1, ⟨false, r - 1, 0, stock - k⟩)]
  | fuel + 1, r, m, p, k =>
    if pf then
      if 0 < tick d pf r ∧ p - tick d pf r ≤ 0 then [(1, ⟨false, r, 0, stock - k⟩)]
      else
        let q := drink (p - tick d pf r) maxPool rPool k
        (roll d.pCrit d.killNormal d.killCrit).flatMap fun (wk, kill) =>
          if m - kill ≤ 0 then [(wk, ⟨true, r, q.1, stock - q.2⟩)]
          else scaleBy wk ((roll d.mCrit d.dieNormal d.dieCrit).flatMap fun (wh, hit) =>
            if q.1 - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - q.2⟩)]
            else scaleBy wh (tree d pf maxPool rPool stock fuel (r + 1) (m - kill) (q.1 - hit) q.2))
    else
      (roll d.mCrit d.dieNormal d.dieCrit).flatMap fun (wh, hit) =>
        if p - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - k⟩)]
        else if 0 < tick d pf r ∧ p - hit - tick d pf r ≤ 0 then [(wh, ⟨false, r, 0, stock - k⟩)]
        else
          let q := drink (p - hit - tick d pf r) maxPool rPool k
          scaleBy wh ((roll d.pCrit d.killNormal d.killCrit).flatMap fun (wk, kill) =>
            if m - kill ≤ 0 then [(wk, ⟨true, r, q.1, stock - q.2⟩)]
            else scaleBy wk (tree d pf maxPool rPool stock fuel (r + 1) (m - kill) q.1 q.2))

/-- `fight_odds_core.fight_odds`, unmerged. -/
def fightOdds (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat) :
    List (Rat × Ending) :=
  match gate t with
  | .outSustain => [(1, ⟨true, roundsToKill t, effHp hp maxHp * scale, 0⟩)]
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then [(1, ⟨false, 0, 0, 0⟩)]
    else tree d t.playerFirst (maxHp * scale) ((restore : Int) * scale) stock
      maxTurns.toNat 1 (d.monsterHp * scale) (effHp hp maxHp * scale) stock
  | _ => [(1, ⟨false, 0, 0, 0⟩)]

/-- P(win). -/
def winProb (xs : List (Rat × Ending)) : Rat :=
  (xs.filter (·.2.win)).foldr (fun e acc => e.1 + acc) 0

/-! ### Sums over lists. -/

/-- The summed probability of a list. -/
def mass (xs : List (Rat × Ending)) : Rat := (xs.map (·.1)).foldr (· + ·) 0

/-- The sum of `g` over a list. -/
def lsum {α : Type} (g : α → Rat) (xs : List α) : Rat := (xs.map g).foldr (· + ·) 0

theorem lsum_le {α : Type} (g h : α → Rat) :
    ∀ xs : List α, (∀ x ∈ xs, g x ≤ h x) → lsum g xs ≤ lsum h xs := by
  intro xs
  induction xs with
  | nil => intro _; exact Rat.le_refl
  | cons x xs ih =>
    intro hx
    have h1 := hx x (List.mem_cons_self ..)
    have h2 := ih fun y hy => hx y (List.mem_cons_of_mem _ hy)
    simp only [lsum, List.map_cons, List.foldr_cons] at h2 ⊢
    grind

theorem lsum_congr {α : Type} (g h : α → Rat) :
    ∀ xs : List α, (∀ x ∈ xs, g x = h x) → lsum g xs = lsum h xs := by
  intro xs
  induction xs with
  | nil => intro _; rfl
  | cons x xs ih =>
    intro hx
    have h1 := hx x (List.mem_cons_self ..)
    have h2 := ih fun y hy => hx y (List.mem_cons_of_mem _ hy)
    simp only [lsum, List.map_cons, List.foldr_cons] at h2 ⊢
    rw [h1, h2]

theorem lsum_nonneg {α : Type} (g : α → Rat) :
    ∀ xs : List α, (∀ x ∈ xs, 0 ≤ g x) → 0 ≤ lsum g xs := by
  intro xs
  induction xs with
  | nil => intro _; exact Rat.le_refl
  | cons x xs ih =>
    intro hx
    have h1 := hx x (List.mem_cons_self ..)
    have h2 := ih fun y hy => hx y (List.mem_cons_of_mem _ hy)
    simp only [lsum, List.map_cons, List.foldr_cons] at h2 ⊢
    grind

theorem mass_append (xs ys : List (Rat × Ending)) : mass (xs ++ ys) = mass xs + mass ys := by
  induction xs with
  | nil => simp [mass, Rat.zero_add]
  | cons x xs ih =>
    simp only [mass, List.cons_append, List.map_cons, List.foldr_cons] at ih ⊢
    rw [ih]; grind

theorem mass_scaleBy (w : Rat) (xs : List (Rat × Ending)) : mass (scaleBy w xs) = w * mass xs := by
  induction xs with
  | nil => simp [mass, scaleBy]
  | cons x xs ih =>
    simp only [mass, scaleBy, List.map_cons, List.foldr_cons] at ih ⊢
    rw [ih, Rat.mul_add]

theorem mass_flatMap {α : Type} (f : α → List (Rat × Ending)) :
    ∀ xs : List α, mass (xs.flatMap f) = lsum (fun x => mass (f x)) xs := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    rw [List.flatMap_cons, mass_append, ih]
    rfl

theorem winProb_cons (e : Rat × Ending) (xs : List (Rat × Ending)) :
    winProb (e :: xs) = (if e.2.win then e.1 else 0) + winProb xs := by
  unfold winProb
  cases h : e.2.win
  · simp [h, Rat.zero_add]
  · simp [h]

theorem winProb_append (xs ys : List (Rat × Ending)) :
    winProb (xs ++ ys) = winProb xs + winProb ys := by
  induction xs with
  | nil => simp [winProb, Rat.zero_add]
  | cons x xs ih => rw [List.cons_append, winProb_cons, winProb_cons, ih]; grind

theorem winProb_scaleBy (w : Rat) (xs : List (Rat × Ending)) :
    winProb (scaleBy w xs) = w * winProb xs := by
  induction xs with
  | nil => simp [winProb, scaleBy]
  | cons x xs ih =>
    have hc : scaleBy w (x :: xs) = (w * x.1, x.2) :: scaleBy w xs := rfl
    rw [hc, winProb_cons, winProb_cons, ih, Rat.mul_add]
    split <;> simp

theorem winProb_flatMap {α : Type} (f : α → List (Rat × Ending)) :
    ∀ xs : List α, winProb (xs.flatMap f) = lsum (fun x => winProb (f x)) xs := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    rw [List.flatMap_cons, winProb_append, ih]
    rfl

theorem winProb_single (w : Rat) (e : Ending) :
    winProb [(w, e)] = if e.win then w else 0 := by
  rw [winProb_cons]; simp [winProb, Rat.add_zero]

/-! ### The crit roll. -/

theorem lsum_filter_ne_zero :
    ∀ xs : List (Rat × Int),
      lsum (·.1) (xs.filter (fun b => b.1 ≠ 0)) = lsum (·.1) xs := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    by_cases h : x.1 = 0
    · rw [List.filter_cons_of_neg (by simp [h]), ih]
      simp only [lsum, List.map_cons, List.foldr_cons, h]; grind
    · rw [List.filter_cons_of_pos (by simp [h])]
      simp only [lsum, List.map_cons, List.foldr_cons] at ih ⊢
      rw [ih]

theorem roll_sum (pct : Nat) (normal crit : Int) (h : pct ≤ 100) :
    lsum (·.1) (roll pct normal crit) = 1 := by
  unfold roll
  rw [lsum_filter_ne_zero]
  have h2 : ((100 - pct : Nat) : Rat) + (pct : Rat) = 100 := by
    rw [← Rat.natCast_add, Nat.sub_add_cancel h]; rfl
  simp only [lsum, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
  grind

theorem roll_nonneg {pct : Nat} {normal crit : Int} {x : Rat × Int}
    (hx : x ∈ roll pct normal crit) : 0 ≤ x.1 := by
  unfold roll at hx
  have hm := (List.mem_filter.mp hx).1
  have h1 := @Rat.natCast_nonneg (100 - pct)
  have h2 := @Rat.natCast_nonneg pct
  simp only [List.mem_cons, List.not_mem_nil, or_false] at hm
  rcases hm with rfl | rfl <;> grind

theorem roll_zero (normal crit : Int) : roll 0 normal crit = [(1, normal)] := by
  have h1 : (((100 - 0 : Nat) : Rat) / 100) = 1 := by grind
  have h0 : (((0 : Nat) : Rat) / 100) = 0 := by grind
  unfold roll
  rw [h1, h0]; simp

theorem scaleBy_one (xs : List (Rat × Ending)) : scaleBy 1 xs = xs := by
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    have hc : scaleBy 1 (x :: xs) = (1 * x.1, x.2) :: scaleBy 1 xs := rfl
    rw [hc, ih, Rat.one_mul]

/-! ### (a) The probabilities sum to 1. -/

theorem mass_flatMap_roll (pct : Nat) (normal crit : Int) (h : pct ≤ 100)
    (f : Rat × Int → List (Rat × Ending))
    (hf : ∀ x ∈ roll pct normal crit, mass (f x) = x.1) :
    mass ((roll pct normal crit).flatMap f) = 1 := by
  rw [mass_flatMap, lsum_congr _ _ _ hf, roll_sum _ _ _ h]

theorem mass_single (w : Rat) (e : Ending) : mass [(w, e)] = w := by
  simp only [mass, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
  exact Rat.add_zero w

theorem tree_mass (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat)
    (hp : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    ∀ (fuel : Nat) (r m p : Int) (k : Nat),
      mass (tree d pf maxPool rPool stock fuel r m p k) = 1 := by
  intro fuel
  induction fuel with
  | zero => intro r m p k; simp only [tree]; exact mass_single _ _
  | succ fuel ih =>
    intro r m p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      apply mass_flatMap_roll _ _ _ hm
      rintro ⟨wh, hit⟩ _
      simp only
      split
      · exact mass_single _ _
      · split
        · exact mass_single _ _
        · rw [mass_scaleBy, mass_flatMap_roll _ _ _ hp, Rat.mul_one]
          rintro ⟨wk, kill⟩ _
          simp only
          split
          · exact mass_single _ _
          · rw [mass_scaleBy, ih, Rat.mul_one]
    · simp only [tree, if_true]
      split
      · exact mass_single _ _
      · apply mass_flatMap_roll _ _ _ hp
        rintro ⟨wk, kill⟩ _
        simp only
        split
        · exact mass_single _ _
        · rw [mass_scaleBy, mass_flatMap_roll _ _ _ hm, Rat.mul_one]
          rintro ⟨wh, hit⟩ _
          simp only
          split
          · exact mass_single _ _
          · rw [mass_scaleBy, ih, Rat.mul_one]

/-- (a) The endings' probabilities sum to 1. -/
theorem fightOdds_sum_one (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp' : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    ((fightOdds t d hp maxHp restore stock).map (·.1)).foldr (· + ·) 0 = 1 := by
  show mass (fightOdds t d hp maxHp restore stock) = 1
  unfold fightOdds
  split
  · exact mass_single _ _
  · split
    · exact mass_single _ _
    · exact tree_mass _ _ _ _ _ hp' hm _ _ _ _ _
  · exact mass_single _ _

/-! ### (b) With no crit the tree is the deterministic walk. -/

/-- Without burn every tick is 0. -/
theorem tick_nil (d : Damage) (pf : Bool) (r : Int) (h : d.burn = []) : tick d pf r = 0 := by
  simp [tick, h]

theorem tree_noCrit (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat)
    (hp0 : d.pCrit = 0) (hm0 : d.mCrit = 0) (hb : d.burn = []) :
    ∀ (n fuel : Nat) (r m p : Int) (k : Nat), n < fuel →
      (n : Int) * d.killNormal < m → m ≤ (n : Int) * d.killNormal + d.killNormal →
      tree d pf maxPool rPool stock fuel r m p k =
        [(1, ⟨(walk pf d.dieNormal maxPool rPool (n + 1) r p k).win,
              (walk pf d.dieNormal maxPool rPool (n + 1) r p k).turns,
              (walk pf d.dieNormal maxPool rPool (n + 1) r p k).pool,
              stock - (walk pf d.dieNormal maxPool rPool (n + 1) r p k).left⟩)] := by
  intro n
  induction n with
  | zero =>
    intro fuel r m p k hf hlo hhi
    obtain ⟨f, rfl⟩ : ∃ f, fuel = f + 1 := ⟨fuel - 1, by omega⟩
    have hk : m - d.killNormal ≤ 0 := by omega
    cases pf
    · simp only [tree, walk, hp0, hm0, roll_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, Bool.false_eq_true, if_false, if_true, scaleBy_one, hk]
      split <;> rfl
    · simp only [tree, walk, hp0, hm0, roll_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, if_true, hk]
  | succ n ih =>
    intro fuel r m p k hf hlo hhi
    obtain ⟨f, rfl⟩ : ∃ f, fuel = f + 1 := ⟨fuel - 1, by omega⟩
    have hs : ((n + 1 : Nat) : Int) * d.killNormal = (n : Int) * d.killNormal + d.killNormal := by
      rw [Int.natCast_add, Int.add_mul, Int.natCast_one, Int.one_mul]
    have hnn : 0 ≤ (n : Int) * d.killNormal := by
      by_cases hz : (n : Int) * d.killNormal < 0
      · exfalso
        have : (0 : Int) ≤ n := Int.natCast_nonneg n
        have hkn : d.killNormal < 0 ∨ 0 ≤ d.killNormal := by omega
        rcases hkn with hkn | hkn
        · omega
        · exact absurd hz (Int.not_lt.mpr (Int.mul_nonneg this hkn))
      · omega
    have hk : ¬ m - d.killNormal ≤ 0 := by omega
    have hih := fun p k => ih f (r + 1) (m - d.killNormal) p k (by omega) (by omega) (by omega)
    rw [walk]
    cases pf
    · simp only [tree, hp0, hm0, roll_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, Bool.false_eq_true, if_false, scaleBy_one, hk,
        Nat.add_one_ne_zero]
      split
      · rfl
      · rw [hih]
    · simp only [tree, hp0, hm0, roll_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, if_true, if_false, scaleBy_one, hk, Nat.add_one_ne_zero]
      split
      · rfl
      · rw [hih]

theorem gate_none_kill (t : Terms) (h : gate t = .none) :
    0 < t.killStep ∧ roundsToKill t ≤ maxTurns := by
  unfold gate at h
  split at h <;> try contradiction
  split at h <;> try contradiction
  · rename_i h2
    split at h
    · contradiction
    · rename_i h3; exact ⟨by omega, by omega⟩

/-- (b) With both crit chances 0 the tree is the one ending of `fightOutcome`.
A real monster has HP ≥ 1; at HP ≤ 0 the walk reports round 0 (`roundsToKill`
is 0) while the tree always plays round 1, hence `hm0hp`. -/
theorem fightOdds_noCrit (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp0 : d.pCrit = 0) (hm0 : d.mCrit = 0) (hb : d.burn = [])
    (hk : d.killNormal = t.killStep) (hd : d.dieNormal = t.dieStep)
    (hmhp : d.monsterHp = t.monsterHp) (hm0hp : 0 < t.monsterHp) :
    fightOdds t d hp maxHp restore stock =
      [(1, ⟨(fightOutcome t hp maxHp restore stock).win,
            (fightOutcome t hp maxHp restore stock).turns,
            (fightOutcome t hp maxHp restore stock).hpEnd,
            (fightOutcome t hp maxHp restore stock).used⟩)] := by
  unfold fightOdds fightOutcome
  cases hg : gate t with
  | none =>
    simp only
    split
    · rfl
    · obtain ⟨hks, hcap⟩ := gate_none_kill t hg
      have hN : 1 ≤ t.monsterHp * scale := by simp only [scale]; omega
      have hpos := ceilDiv_pos _ _ hks hN
      have hr : roundsToKill t = ceilDiv (t.monsterHp * scale) t.killStep := rfl
      have hge := ceilDiv_mul_ge (t.monsterHp * scale) t.killStep hks (by omega)
      have hlt := ceilDiv_pred_mul_lt (t.monsterHp * scale) t.killStep hks hN
      obtain ⟨n, hn⟩ : ∃ n : Nat, (roundsToKill t).toNat = n + 1 :=
        ⟨(roundsToKill t).toNat - 1, by omega⟩
      have hni : roundsToKill t = (n : Int) + 1 := by omega
      unfold roundsToKill at hni
      rw [hni] at hge hlt
      have hge' : t.monsterHp * scale ≤ (n : Int) * t.killStep + t.killStep := by
        rw [Int.add_mul, Int.one_mul] at hge; exact hge
      have hlt' : (n : Int) * t.killStep < t.monsterHp * scale := by
        rw [Int.add_sub_cancel] at hlt; exact hlt
      have hmt : (maxTurns.toNat) = 100 := rfl
      have hcap' : roundsToKill t ≤ 100 := hcap
      rw [hn, ← hd, tree_noCrit d _ _ _ _ hp0 hm0 hb n maxTurns.toNat _ _ _ _ (by omega)
        (by rw [hk, hmhp]; exact hlt') (by rw [hk, hmhp]; exact hge')]
  | _ => rfl

/-! ### (c) More stock, or more HP with no stock, never lowers P(win). -/

theorem drink_ge_nonneg (p maxPool rPool : Int) (k : Nat) (hM : 0 ≤ maxPool) (hr : 0 ≤ rPool) :
    p ≤ (drink p maxPool rPool k).1 := by
  unfold drink; split
  · rename_i h
    simp only
    rw [Int.min_def]; split <;> omega
  · exact Int.le_refl _

/-- `FightOutcome.drink_coupled` for pools that may exceed `maxPool` (a negative
hit raises a pool): `0 ≤ maxPool` is enough, since a drink fires only below half. -/
theorem drink_coupled_nonneg (maxPool rPool : Int) (hM : 0 ≤ maxPool) (hr : 0 ≤ rPool)
    (p p' : Int) (k k' : Nat) (hc : coupled p k p' k') :
    coupled (drink p maxPool rPool k).1 (drink p maxPool rPool k).2
      (drink p' maxPool rPool k').1 (drink p' maxPool rPool k').2 := by
  rcases hc with ⟨rfl, hk⟩ | ⟨rfl, hle⟩
  · by_cases hc : 2 * p < maxPool
    · by_cases h0 : 0 < k
      · left
        simp only [drink, hc, h0, true_and, if_true, show 0 < k' by omega]
        first | omega | exact ⟨rfl, by omega⟩
      · have hk0 : k = 0 := by omega
        subst hk0
        right
        exact ⟨by simp [drink], by
          rw [Formal.FightOutcome.drink_noStock]
          exact drink_ge_nonneg _ _ _ _ hM hr⟩
    · left
      simp [drink, hc]; exact hk
  · right
    exact ⟨by simp [drink], by
      rw [Formal.FightOutcome.drink_noStock]
      exact Int.le_trans hle (drink_ge_nonneg _ _ _ _ hM hr)⟩

theorem tree_wp_nonneg (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat) :
    ∀ (fuel : Nat) (r m p : Int) (k : Nat),
      0 ≤ winProb (tree d pf maxPool rPool stock fuel r m p k) := by
  intro fuel
  induction fuel with
  | zero => intro r m p k; simp only [tree, winProb_single]; exact Rat.le_refl
  | succ fuel ih =>
    intro r m p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap]
      apply lsum_nonneg
      rintro ⟨wh, hit⟩ hx
      have hw := roll_nonneg hx
      simp only at hw ⊢
      split
      · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · split
        · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
        · rw [winProb_scaleBy, winProb_flatMap]
          apply Rat.mul_nonneg hw
          apply lsum_nonneg
          rintro ⟨wk, kill⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · simp only [winProb_single, if_true]; exact hw'
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (ih _ _ _ _)
    · simp only [tree, if_true]
      split
      · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · rw [winProb_flatMap]
        apply lsum_nonneg
        rintro ⟨wk, kill⟩ hx
        have hw := roll_nonneg hx
        simp only at hw ⊢
        split
        · simp only [winProb_single, if_true]; exact hw
        · rw [winProb_scaleBy, winProb_flatMap]
          apply Rat.mul_nonneg hw
          apply lsum_nonneg
          rintro ⟨wh, hit⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (ih _ _ _ _)

/-- The coupled trees: the poorer state's P(win) never exceeds the richer one's
(the monster pool and round are shared; the stock base only labels `used`). -/
theorem tree_mono (d : Damage) (pf : Bool) (maxPool rPool : Int) (hM : 0 ≤ maxPool)
    (hr : 0 ≤ rPool) (st st' : Nat) :
    ∀ (fuel : Nat) (r m p p' : Int) (k k' : Nat), coupled p k p' k' →
      winProb (tree d pf maxPool rPool st fuel r m p k)
        ≤ winProb (tree d pf maxPool rPool st' fuel r m p' k') := by
  intro fuel
  induction fuel with
  | zero =>
    intro r m p p' k k' _
    simp only [tree, winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
  | succ fuel ih =>
    intro r m p p' k k' hc
    have hpp := coupled_le hc
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap, winProb_flatMap]
      apply lsum_le
      rintro ⟨wh, hit⟩ hx
      have hw := roll_nonneg hx
      simp only at hw ⊢
      by_cases h1 : p' - hit ≤ 0
      · have h0 : p - hit ≤ 0 := by omega
        rw [if_pos h0, if_pos h1]
        simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · rw [if_neg h1]
        by_cases h0 : p - hit ≤ 0
        · rw [if_pos h0]
          simp only [winProb_single, Bool.false_eq_true, if_false]
          split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy]
            apply Rat.mul_nonneg hw
            rw [winProb_flatMap]
            apply lsum_nonneg
            rintro ⟨wk, kill⟩ hy
            have hw' := roll_nonneg hy
            simp only at hw' ⊢
            split
            · simp only [winProb_single, if_true]; exact hw'
            · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _)
        · rw [if_neg h0]
          by_cases g1 : 0 < tick d false r ∧ p' - hit - tick d false r ≤ 0
          · have g0 : 0 < tick d false r ∧ p - hit - tick d false r ≤ 0 := ⟨g1.1, by omega⟩
            rw [if_pos g0, if_pos g1]
            simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [if_neg g1]
            by_cases g0 : 0 < tick d false r ∧ p - hit - tick d false r ≤ 0
            · rw [if_pos g0]
              simp only [winProb_single, Bool.false_eq_true, if_false]
              rw [winProb_scaleBy]
              apply Rat.mul_nonneg hw
              rw [winProb_flatMap]
              apply lsum_nonneg
              rintro ⟨wk, kill⟩ hy
              have hw' := roll_nonneg hy
              simp only at hw' ⊢
              split
              · simp only [winProb_single, if_true]; exact hw'
              · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _)
            · rw [if_neg g0, winProb_scaleBy, winProb_scaleBy]
              apply Rat.mul_le_mul_of_nonneg_left _ hw
              rw [winProb_flatMap, winProb_flatMap]
              apply lsum_le
              rintro ⟨wk, kill⟩ hy
              have hw' := roll_nonneg hy
              simp only at hw' ⊢
              split
              · simp only [winProb_single, if_true]; exact Rat.le_refl
              · rw [winProb_scaleBy, winProb_scaleBy]
                apply Rat.mul_le_mul_of_nonneg_left _ hw'
                exact ih _ _ _ _ _ _ (drink_coupled_nonneg _ _ hM hr _ _ _ _
                  (coupled_sub (tick d false r) (coupled_sub hit hc)))
    · by_cases g1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · have g0 : 0 < tick d true r ∧ p - tick d true r ≤ 0 := ⟨g1.1, by omega⟩
        simp only [tree, if_true, if_pos g0, if_pos g1, winProb_single, Bool.false_eq_true,
          if_false]
        exact Rat.le_refl
      · by_cases g0 : 0 < tick d true r ∧ p - tick d true r ≤ 0
        · have hz : winProb (tree d true maxPool rPool st (fuel + 1) r m p k) = 0 := by
            simp only [tree, if_true, if_pos g0, winProb_single, Bool.false_eq_true, if_false]
          rw [hz]; exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _
        · have hd := drink_coupled_nonneg _ _ hM hr _ _ _ _ (coupled_sub (tick d true r) hc)
          have hdd := coupled_le hd
          simp only [tree, if_true, if_neg g0, if_neg g1]
          rw [winProb_flatMap, winProb_flatMap]
          apply lsum_le
          rintro ⟨wk, kill⟩ hx
          have hw := roll_nonneg hx
          simp only at hw ⊢
          split
          · simp only [winProb_single, if_true]; exact Rat.le_refl
          · rw [winProb_scaleBy, winProb_scaleBy]
            apply Rat.mul_le_mul_of_nonneg_left _ hw
            rw [winProb_flatMap, winProb_flatMap]
            apply lsum_le
            rintro ⟨wh, hit⟩ hy
            have hw' := roll_nonneg hy
            simp only at hw' ⊢
            by_cases h1 : (drink (p' - tick d true r) maxPool rPool k').1 - hit ≤ 0
            · have h0 : (drink (p - tick d true r) maxPool rPool k).1 - hit ≤ 0 := by omega
              rw [if_pos h0, if_pos h1]
              simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
            · rw [if_neg h1]
              by_cases h0 : (drink (p - tick d true r) maxPool rPool k).1 - hit ≤ 0
              · rw [if_pos h0]
                simp only [winProb_single, Bool.false_eq_true, if_false]
                rw [winProb_scaleBy]
                exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _)
              · rw [if_neg h0, winProb_scaleBy, winProb_scaleBy]
                exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _ _ _ (coupled_sub hit hd)) hw'

theorem effHp_pos {hp maxHp : Int} (h : ¬ effHp hp maxHp * scale ≤ 0) :
    0 < hp ∧ 0 < maxHp ∧ 0 < effHp hp maxHp := by
  simp only [scale] at h
  unfold effHp at h ⊢
  split at h
  · rename_i hh
    rw [if_pos hh]
    rw [Int.min_def] at h ⊢
    split at h <;> omega
  · omega

/-- (c) More restore stock never lowers P(win). -/
theorem fightOdds_win_mono_stock (t : Terms) (d : Damage) (hp maxHp : Int) (restore s s' : Nat)
    (hs : s ≤ s') (_hp' : d.pCrit ≤ 100) (_hm : d.mCrit ≤ 100) :
    winProb (fightOdds t d hp maxHp restore s) ≤ winProb (fightOdds t d hp maxHp restore s') := by
  unfold fightOdds
  split
  · exact Rat.le_refl
  · split
    · exact Rat.le_refl
    · rename_i h
      obtain ⟨_, hmax, _⟩ := effHp_pos h
      exact tree_mono _ _ _ _ (by simp only [scale]; omega)
        (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) _ _ _ _ _ _ _ _ _
        (Or.inl ⟨rfl, hs⟩)
  · exact Rat.le_refl

/-- (c) With no restore stock, more starting HP never lowers P(win).

WITH stock this is FALSE, because of the 50% drink threshold. `t = ⟨1, 10000, 2,
0, 500000, true⟩`, `d = ⟨2, 10000, 10000, 0, 500000, 500000, 0⟩`, `maxHp 100`,
`restore 50`, `stock 1`: at hp 49 the first turn drinks to 99, survives the 50
hit and wins in round 2 (P(win) = 1); at hp 50 it does not drink and dies in
round 1 (P(win) = 0). Hence `hs0`. -/
theorem fightOdds_win_mono_hp (t : Terms) (d : Damage) (hp hp' maxHp : Int) (restore stock : Nat)
    (hh : hp ≤ hp') (_hp1 : d.pCrit ≤ 100) (_hm : d.mCrit ≤ 100) (hs0 : stock = 0) :
    winProb (fightOdds t d hp maxHp restore stock) ≤ winProb (fightOdds t d hp' maxHp restore stock) := by
  subst hs0
  unfold fightOdds
  split
  · simp only [winProb_single, if_true]; exact Rat.le_refl
  · by_cases h1 : effHp hp maxHp * scale ≤ 0
    · rw [if_pos h1]
      simp only [winProb_single, Bool.false_eq_true, if_false]
      split
      · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _
    · obtain ⟨hhp, hmax, he⟩ := effHp_pos h1
      have hle : effHp hp maxHp ≤ effHp hp' maxHp := by
        unfold effHp at he ⊢
        rw [if_pos hhp, if_pos (by omega)]
        rw [if_pos hhp] at he
        rw [Int.min_def, Int.min_def] at *
        split <;> split <;> omega
      have h1' : ¬ effHp hp' maxHp * scale ≤ 0 := by simp only [scale] at h1 ⊢; omega
      rw [if_neg h1, if_neg h1']
      exact tree_mono _ _ _ _ (by simp only [scale]; omega)
        (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) _ _ _ _ _ _ _ _ _
        (Or.inr ⟨rfl, by simp only [scale]; omega⟩)
  · exact Rat.le_refl

/-! ### (d) A worst-case win with no stock is a sure win. -/

theorem roll_hundred (normal crit : Int) : roll 100 normal crit = [(1, crit)] := by
  have h0 : (((100 - 100 : Nat) : Rat) / 100) = 0 := by grind
  have h1 : (((100 : Nat) : Rat) / 100) = 1 := by grind
  unfold roll
  rw [h0, h1]; simp

theorem roll_mem {pct : Nat} {normal crit : Int} {x : Rat × Int}
    (hx : x ∈ roll pct normal crit) : x.2 = normal ∨ x.2 = crit := by
  unfold roll at hx
  have hm := (List.mem_filter.mp hx).1
  simp only [List.mem_cons, List.not_mem_nil, or_false] at hm
  rcases hm with rfl | rfl <;> simp

theorem winProb_single_le (w : Rat) (e : Ending) (hw : 0 ≤ w) :
    winProb [(w, e)] ≤ mass [(w, e)] := by
  rw [winProb_single, mass_single]
  split
  · exact Rat.le_refl
  · exact hw

theorem tree_wp_le_mass (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat) :
    ∀ (fuel : Nat) (r m p : Int) (k : Nat),
      winProb (tree d pf maxPool rPool stock fuel r m p k)
        ≤ mass (tree d pf maxPool rPool stock fuel r m p k) := by
  intro fuel
  induction fuel with
  | zero => intro r m p k; simp only [tree]; exact winProb_single_le _ _ (by decide)
  | succ fuel ih =>
    intro r m p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_le
      rintro ⟨wh, hit⟩ hx
      have hw := roll_nonneg hx
      simp only at hw ⊢
      split
      · exact winProb_single_le _ _ hw
      · split
        · exact winProb_single_le _ _ hw
        · rw [winProb_scaleBy, mass_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hw
          rw [winProb_flatMap, mass_flatMap]
          apply lsum_le
          rintro ⟨wk, kill⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · exact winProb_single_le _ _ hw'
          · rw [winProb_scaleBy, mass_scaleBy]
            exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _) hw'
    · simp only [tree, if_true]
      split
      · exact winProb_single_le _ _ (by decide)
      · rw [winProb_flatMap, mass_flatMap]
        apply lsum_le
        rintro ⟨wk, kill⟩ hx
        have hw := roll_nonneg hx
        simp only at hw ⊢
        split
        · exact winProb_single_le _ _ hw
        · rw [winProb_scaleBy, mass_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hw
          rw [winProb_flatMap, mass_flatMap]
          apply lsum_le
          rintro ⟨wh, hit⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · exact winProb_single_le _ _ hw'
          · rw [winProb_scaleBy, mass_scaleBy]
            exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _) hw'

theorem fightOdds_wp_le_one (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp' : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    winProb (fightOdds t d hp maxHp restore stock) ≤ 1 := by
  unfold fightOdds
  split
  · simp only [winProb_single, if_true]; exact Rat.le_refl
  · split
    · simp only [winProb_single, Bool.false_eq_true, if_false]; decide
    · rw [← tree_mass d _ _ _ stock hp' hm maxTurns.toNat 1 (d.monsterHp * scale)
        (effHp hp maxHp * scale) stock]
      exact tree_wp_le_mass _ _ _ _ _ _ _ _ _ _
  · simp only [winProb_single, Bool.false_eq_true, if_false]; decide

/-- With no stock the real tree loses nowhere the worst-case tree `d'` (no player
crit, every monster turn a crit) wins: every real leaf wins, so P(win) is the mass. -/
theorem tree_worst (d d' : Damage) (pf : Bool) (maxPool rPool : Int) (st : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp0 : d'.pCrit = 0) (hm1 : d'.mCrit = 100) (hkn : d'.killNormal = d.killNormal)
    (hdc : d'.dieCrit = d.dieCrit) (htick : ∀ pf r, tick d' pf r = tick d pf r) :
    ∀ (fuel : Nat) (r m m' p p' : Int), m ≤ m' → p' ≤ p →
      winProb (tree d' pf maxPool rPool st fuel r m' p' 0) = 1 →
      winProb (tree d pf maxPool rPool st fuel r m p 0)
        = mass (tree d pf maxPool rPool st fuel r m p 0) := by
  intro fuel
  induction fuel with
  | zero =>
    intro r m m' p p' _ _ hw
    simp [tree, winProb_single] at hw
  | succ fuel ih =>
    intro r m m' p p' hm hp hw
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false, hp0, hm1, roll_zero, roll_hundred,
        List.flatMap_cons, List.flatMap_nil, List.append_nil, scaleBy_one,
        Formal.FightOutcome.drink_noStock,
        htick, hkn, hdc] at hw
      simp only [tree, Bool.false_eq_true, if_false, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_congr
      rintro ⟨wh, hit⟩ hx
      have hh := roll_mem hx
      simp only at hh ⊢
      have hhit : hit ≤ d.dieCrit := by omega
      by_cases w1 : p' - d.dieCrit ≤ 0
      · rw [if_pos w1] at hw; simp [winProb_single] at hw
      rw [if_neg w1] at hw
      by_cases w2 : 0 < tick d false r ∧ p' - d.dieCrit - tick d false r ≤ 0
      · rw [if_pos w2] at hw; simp [winProb_single] at hw
      rw [if_neg w2] at hw
      have h1 : ¬ p - hit ≤ 0 := by omega
      have g0 : ¬ (0 < tick d false r ∧ p - hit - tick d false r ≤ 0) :=
        fun h => w2 ⟨h.1, by omega⟩
      rw [if_neg h1, if_neg g0, winProb_scaleBy, mass_scaleBy, winProb_flatMap, mass_flatMap]
      congr 1
      apply lsum_congr
      rintro ⟨wk, kill⟩ hy
      have hh' := roll_mem hy
      simp only at hh' ⊢
      have hkill : d.killNormal ≤ kill := by omega
      split
      · rw [winProb_single, mass_single]; rfl
      · rename_i hmk
        have w3 : ¬ m' - d.killNormal ≤ 0 := by omega
        rw [if_neg w3] at hw
        rw [winProb_scaleBy, mass_scaleBy, ih _ _ _ _ _ (by omega) (by omega) hw]
    · simp only [tree, if_true, hp0, hm1, roll_zero, roll_hundred,
        List.flatMap_cons, List.flatMap_nil, List.append_nil, scaleBy_one,
        Formal.FightOutcome.drink_noStock,
        htick, hkn, hdc] at hw
      by_cases w1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · rw [if_pos w1] at hw; simp [winProb_single] at hw
      rw [if_neg w1] at hw
      have g0 : ¬ (0 < tick d true r ∧ p - tick d true r ≤ 0) :=
        fun h => w1 ⟨h.1, by omega⟩
      simp only [tree, if_true, if_neg g0, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_congr
      rintro ⟨wk, kill⟩ hx
      have hh := roll_mem hx
      simp only at hh ⊢
      have hkill : d.killNormal ≤ kill := by omega
      split
      · rw [winProb_single, mass_single]; rfl
      · rename_i hmk
        have w3 : ¬ m' - d.killNormal ≤ 0 := by omega
        rw [if_neg w3] at hw
        rw [winProb_scaleBy, mass_scaleBy, winProb_flatMap, mass_flatMap]
        congr 1
        apply lsum_congr
        rintro ⟨wh, hit⟩ hy
        have hh' := roll_mem hy
        simp only at hh' ⊢
        have hhit : hit ≤ d.dieCrit := by omega
        by_cases w2 : p' - tick d true r - d.dieCrit ≤ 0
        · rw [if_pos w2] at hw; simp [winProb_single] at hw
        rw [if_neg w2] at hw
        have h0 : ¬ p - tick d true r - hit ≤ 0 := by omega
        rw [if_neg h0, winProb_scaleBy, mass_scaleBy, ih _ _ _ _ _ (by omega) (by omega) hw]

/-- A fight won on the worst-case path (no player crit, every monster turn a
crit) with no restore stock is won with probability 1 — at any stock, since
more stock never lowers P(win) (`fightOdds_win_mono_stock`). With stock the
worst path alone is not enough: the 50% drink threshold can let the richer
pool skip a drink the worst pool takes (counterexample in the PR notes). -/
theorem winProb_eq_one_of_worst (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100)
    (hw : winProb (fightOdds t { d with pCrit := 0, mCrit := 100 } hp maxHp restore 0) = 1) :
    winProb (fightOdds t d hp maxHp restore stock) = 1 := by
  have h0 : winProb (fightOdds t d hp maxHp restore 0) = 1 := by
    unfold fightOdds at hw ⊢
    cases hg : gate t <;> simp only [hg] at hw ⊢
    case outSustain => simp only [winProb_single, if_true]
    case none =>
      by_cases he : effHp hp maxHp * scale ≤ 0
      · rw [if_pos he] at hw; simp [winProb_single] at hw
      rw [if_neg he] at hw ⊢
      rw [tree_worst d { d with pCrit := 0, mCrit := 100 } _ _ _ _ hk hd rfl rfl rfl rfl
        (fun _ _ => rfl) _ _ _ _ _ _ (Int.le_refl _) (Int.le_refl _) hw]
      exact tree_mass _ _ _ _ _ hp100 hm100 _ _ _ _ _
    all_goals simp [winProb_single] at hw
  have hge := fightOdds_win_mono_stock t d hp maxHp restore 0 stock (Nat.zero_le _) hp100 hm100
  rw [h0] at hge
  exact Rat.le_antisymm (fightOdds_wp_le_one t d hp maxHp restore stock hp100 hm100) hge

/-! ### (e) A counted-crit lower bound with no stock. -/

/-- The monster's hit on the counted-crit path: a crit while crits are left. -/
def khit (d : Damage) (c : Nat) : Int := if 0 < c then d.dieCrit else d.dieNormal

/-- The counted-crit path with no stock (`drink` is then the identity): the
player never crits, the monster crits its next `c` turns and then hits normal.
`true` iff that single path is won within `fuel` rounds. -/
def kpath (d : Damage) (pf : Bool) : Nat → Int → Int → Int → Nat → Bool
  | 0, _, _, _, _ => false
  | fuel + 1, r, m, p, c =>
    if pf then
      if 0 < tick d pf r ∧ p - tick d pf r ≤ 0 then false
      else if m - d.killNormal ≤ 0 then true
      else if p - tick d pf r - khit d c ≤ 0 then false
      else kpath d pf fuel (r + 1) (m - d.killNormal) (p - tick d pf r - khit d c) (c - 1)
    else
      if p - khit d c ≤ 0 then false
      else if 0 < tick d pf r ∧ p - khit d c - tick d pf r ≤ 0 then false
      else if m - d.killNormal ≤ 0 then true
      else kpath d pf fuel (r + 1) (m - d.killNormal) (p - khit d c - tick d pf r) (c - 1)

/-- The monster's turns before the never-critting player's kill, within `fuel`
rounds (the monster pool alone decides it). -/
def mturns (d : Damage) (pf : Bool) : Nat → Int → Nat
  | 0, _ => 0
  | fuel + 1, m =>
    if pf then (if m - d.killNormal ≤ 0 then 0 else mturns d pf fuel (m - d.killNormal) + 1)
    else (if m - d.killNormal ≤ 0 then 0 else mturns d pf fuel (m - d.killNormal)) + 1

/-- One row of the at-most-`c` binomial table from the previous one; an index
past the row reads 1 (at most `c ≥ n` crits of `n` turns is certain). -/
def bstep (wn wc : Rat) (row : List Rat) : List Rat :=
  (List.range (row.length + 1)).map fun c =>
    wn * row.getD c 1 + wc * (if c = 0 then 0 else row.getD (c - 1) 1)

def brow (wn wc : Rat) : Nat → List Rat
  | 0 => []
  | n + 1 => bstep wn wc (brow wn wc n)

/-- P(at most `c` of `n` turns crit), a turn normal with weight `wn` and a crit
with weight `wc`. -/
def binom (wn wc : Rat) (n c : Nat) : Rat := (brow wn wc n).getD c 1

/-- P(at most `c - 1` of `n` turns crit), 0 at `c = 0`. -/
def bcrit (wn wc : Rat) (n c : Nat) : Rat := if c = 0 then 0 else binom wn wc n (c - 1)

theorem brow_length (wn wc : Rat) : ∀ n, (brow wn wc n).length = n := by
  intro n; induction n with
  | zero => rfl
  | succ n ih => simp [brow, bstep, ih]

theorem binom_zero (wn wc : Rat) (c : Nat) : binom wn wc 0 c = 1 := by
  simp [binom, brow]

theorem binom_succ (wn wc : Rat) (h1 : wn + wc = 1) (n c : Nat) :
    binom wn wc (n + 1) c = wn * binom wn wc n c + wc * bcrit wn wc n c := by
  have hl := brow_length wn wc n
  by_cases hc : c < n + 1
  · simp [binom, bcrit, brow, bstep, hl, hc, List.getD_eq_getElem?_getD]
  · have h0 : c ≠ 0 := by omega
    have e1 : binom wn wc (n + 1) c = 1 := by
      simp [binom, List.getD_eq_getElem?_getD, brow_length, show n + 1 ≤ c by omega]
    have e2 : binom wn wc n c = 1 := by
      simp [binom, List.getD_eq_getElem?_getD, hl, show n ≤ c by omega]
    have e3 : binom wn wc n (c - 1) = 1 := by
      simp [binom, List.getD_eq_getElem?_getD, hl, show n ≤ c - 1 by omega]
    rw [e1, bcrit, if_neg h0, e2, e3]; grind

theorem binom_bounds (wn wc : Rat) (h1 : wn + wc = 1) (hn : 0 ≤ wn) (hc : 0 ≤ wc) :
    ∀ n c, 0 ≤ binom wn wc n c ∧ binom wn wc n c ≤ 1 := by
  intro n
  induction n with
  | zero => intro c; rw [binom_zero]; decide
  | succ n ih =>
    intro c
    rw [binom_succ _ _ h1]
    have ⟨a0, a1⟩ := ih c
    have hb : 0 ≤ bcrit wn wc n c ∧ bcrit wn wc n c ≤ 1 := by
      unfold bcrit; split
      · decide
      · exact ih _
    have m1 := Rat.mul_le_mul_of_nonneg_left a1 hn
    have m0 := Rat.mul_nonneg hn a0
    have m2 := Rat.mul_le_mul_of_nonneg_left hb.2 hc
    have m3 := Rat.mul_nonneg hc hb.1
    constructor <;> grind

theorem binom_nonneg (wn wc : Rat) (h1 : wn + wc = 1) (hn : 0 ≤ wn) (hc : 0 ≤ wc) (n c : Nat) :
    0 ≤ binom wn wc n c := (binom_bounds wn wc h1 hn hc n c).1

theorem binom_le_one (wn wc : Rat) (h1 : wn + wc = 1) (hn : 0 ≤ wn) (hc : 0 ≤ wc) (n c : Nat) :
    binom wn wc n c ≤ 1 := (binom_bounds wn wc h1 hn hc n c).2

theorem bcrit_le_binom (wn wc : Rat) (h1 : wn + wc = 1) (hn : 0 ≤ wn) (hc : 0 ≤ wc) :
    ∀ n c, bcrit wn wc n c ≤ binom wn wc n c := by
  intro n
  induction n with
  | zero => intro c; unfold bcrit; split <;> simp only [binom_zero] <;> decide
  | succ n ih =>
    intro c
    cases c with
    | zero => simp only [bcrit, if_true]; exact binom_nonneg _ _ h1 hn hc _ _
    | succ c =>
      have e : bcrit wn wc (n + 1) (c + 1) = binom wn wc (n + 1) c := by simp [bcrit]
      rw [e, binom_succ _ _ h1, binom_succ _ _ h1]
      have i1 := ih (c + 1)
      have e2 : bcrit wn wc n (c + 1) = binom wn wc n c := by simp [bcrit]
      rw [e2] at i1
      have i2 := ih c
      have m1 := Rat.mul_le_mul_of_nonneg_left i1 hn
      have m2 := Rat.mul_le_mul_of_nonneg_left (show bcrit wn wc n c ≤ binom wn wc n c from i2) hc
      rw [e2]
      grind

theorem bcrit_nonneg (wn wc : Rat) (h1 : wn + wc = 1) (hn : 0 ≤ wn) (hc : 0 ≤ wc) (n c : Nat) :
    0 ≤ bcrit wn wc n c := by
  unfold bcrit; split
  · exact Rat.le_refl
  · exact binom_nonneg _ _ h1 hn hc _ _

/-- The crit roll's two weights. -/
def critWn (d : Damage) : Rat := ((100 - d.mCrit : Nat) : Rat) / 100
def critWc (d : Damage) : Rat := ((d.mCrit : Nat) : Rat) / 100

theorem roll_weights (pct : Nat) (h : pct ≤ 100) :
    ((100 - pct : Nat) : Rat) / 100 + ((pct : Nat) : Rat) / 100 = 1 ∧
      0 ≤ ((100 - pct : Nat) : Rat) / 100 ∧ 0 ≤ ((pct : Nat) : Rat) / 100 := by
  have h2 : ((100 - pct : Nat) : Rat) + (pct : Rat) = 100 := by
    rw [← Rat.natCast_add, Nat.sub_add_cancel h]; rfl
  have h3 := @Rat.natCast_nonneg (100 - pct)
  have h4 := @Rat.natCast_nonneg pct
  refine ⟨?_, ?_, ?_⟩ <;> grind

theorem crit_weights (d : Damage) (hm100 : d.mCrit ≤ 100) :
    critWn d + critWc d = 1 ∧ 0 ≤ critWn d ∧ 0 ≤ critWc d := roll_weights d.mCrit hm100

theorem lsum_filter_ne_zero_mul (G : Int → Rat) :
    ∀ xs : List (Rat × Int),
      lsum (fun x => x.1 * G x.2) (xs.filter (fun b => b.1 ≠ 0))
        = lsum (fun x => x.1 * G x.2) xs := by
  intro xs
  induction xs with
  | nil => rfl
  | cons x xs ih =>
    by_cases h : x.1 = 0
    · rw [List.filter_cons_of_neg (by simp [h]), ih]
      simp only [lsum, List.map_cons, List.foldr_cons, h]; grind
    · rw [List.filter_cons_of_pos (by simp [h])]
      simp only [lsum, List.map_cons, List.foldr_cons] at ih ⊢
      rw [ih]

/-- A sum over a crit roll is at least its two weighted per-outcome bounds. -/
theorem lsum_roll_ge (pct : Nat) (a b : Int) (g : Rat × Int → Rat) (G : Int → Rat)
    (hg : ∀ x ∈ roll pct a b, x.1 * G x.2 ≤ g x) :
    ((100 - pct : Nat) : Rat) / 100 * G a + ((pct : Nat) : Rat) / 100 * G b
      ≤ lsum g (roll pct a b) := by
  have he : lsum (fun x => x.1 * G x.2) (roll pct a b)
      = ((100 - pct : Nat) : Rat) / 100 * G a + ((pct : Nat) : Rat) / 100 * G b := by
    unfold roll
    rw [lsum_filter_ne_zero_mul]
    simp only [lsum, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
    grind
  rw [← he]
  exact lsum_le _ _ _ hg

/-- A sum over a crit roll whose every branch is worth its weight times `T`. -/
theorem lsum_roll_ge_const (pct : Nat) (h : pct ≤ 100) (a b : Int) (g : Rat × Int → Rat) (T : Rat)
    (hg : ∀ x ∈ roll pct a b, x.1 * T ≤ g x) : T ≤ lsum g (roll pct a b) := by
  have h1 := lsum_roll_ge pct a b g (fun _ => T) hg
  have ⟨hw, _, _⟩ := roll_weights pct h
  simp only at h1
  rw [← Rat.add_mul, hw, Rat.one_mul] at h1
  exact h1

theorem khit_ge (d : Damage) (hd : d.dieNormal ≤ d.dieCrit) (c : Nat) : d.dieNormal ≤ khit d c := by
  unfold khit; split <;> omega

theorem khit_pos (d : Damage) {c : Nat} (h : 0 < c) : khit d c = d.dieCrit := by
  simp [khit, h]

theorem khit_zero (d : Damage) : khit d 0 = d.dieNormal := by simp [khit]

/-- Trading a normal hit now for one more crit later never helps the path: if
the path from `x - dieCrit` with `c` crits wins, so does the one from
`x - dieNormal` with `c + 1` (its pool is never lower at any check). -/
theorem kpath_shift (d : Damage) (pf : Bool) (hd : d.dieNormal ≤ d.dieCrit) :
    ∀ (fuel : Nat) (r m x : Int) (c : Nat),
      kpath d pf fuel r m (x - d.dieCrit) c = true →
      kpath d pf fuel r m (x - d.dieNormal) (c + 1) = true := by
  intro fuel
  induction fuel with
  | zero => intro r m x c hw; simp [kpath] at hw
  | succ fuel ih =>
    intro r m x c hw
    have hc1 : khit d (c + 1) = d.dieCrit := khit_pos d (by omega)
    have hkg := khit_ge d hd c
    cases pf
    · simp only [kpath, Bool.false_eq_true, if_false] at hw ⊢
      rw [hc1, Nat.add_sub_cancel]
      by_cases w1 : x - d.dieCrit - khit d c ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      by_cases w2 : 0 < tick d false r ∧ x - d.dieCrit - khit d c - tick d false r ≤ 0
      · rw [if_pos w2] at hw; exact absurd hw (by decide)
      rw [if_neg w2] at hw
      have g1 : ¬ x - d.dieNormal - d.dieCrit ≤ 0 := by omega
      have g2 : ¬ (0 < tick d false r ∧ x - d.dieNormal - d.dieCrit - tick d false r ≤ 0) :=
        fun h => w2 ⟨h.1, by omega⟩
      rw [if_neg g1, if_neg g2]
      by_cases w3 : m - d.killNormal ≤ 0
      · rw [if_pos w3]
      rw [if_neg w3] at hw ⊢
      cases c with
      | zero =>
        rw [khit_zero] at hw
        have e : x - d.dieNormal - d.dieCrit - tick d false r
            = x - d.dieCrit - d.dieNormal - tick d false r := by omega
        rw [e]; exact hw
      | succ c =>
        rw [khit_pos d (by omega), Nat.add_sub_cancel] at hw
        have e1 : x - d.dieCrit - d.dieCrit - tick d false r
            = (x - d.dieCrit - tick d false r) - d.dieCrit := by omega
        have e2 : x - d.dieNormal - d.dieCrit - tick d false r
            = (x - d.dieCrit - tick d false r) - d.dieNormal := by omega
        rw [e1] at hw; rw [e2]; exact ih _ _ _ _ hw
    · simp only [kpath, if_true] at hw ⊢
      rw [hc1, Nat.add_sub_cancel]
      by_cases w1 : 0 < tick d true r ∧ x - d.dieCrit - tick d true r ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      have g1 : ¬ (0 < tick d true r ∧ x - d.dieNormal - tick d true r ≤ 0) :=
        fun h => w1 ⟨h.1, by omega⟩
      rw [if_neg g1]
      by_cases w3 : m - d.killNormal ≤ 0
      · rw [if_pos w3]
      rw [if_neg w3] at hw ⊢
      by_cases w2 : x - d.dieCrit - tick d true r - khit d c ≤ 0
      · rw [if_pos w2] at hw; exact absurd hw (by decide)
      rw [if_neg w2] at hw
      have g2 : ¬ x - d.dieNormal - tick d true r - d.dieCrit ≤ 0 := by omega
      rw [if_neg g2]
      cases c with
      | zero =>
        rw [khit_zero] at hw
        have e : x - d.dieNormal - tick d true r - d.dieCrit
            = x - d.dieCrit - tick d true r - d.dieNormal := by omega
        rw [e]; exact hw
      | succ c =>
        rw [khit_pos d (by omega), Nat.add_sub_cancel] at hw
        have e1 : x - d.dieCrit - tick d true r - d.dieCrit
            = (x - tick d true r - d.dieCrit) - d.dieCrit := by omega
        have e2 : x - d.dieNormal - tick d true r - d.dieCrit
            = (x - tick d true r - d.dieCrit) - d.dieNormal := by omega
        rw [e1] at hw; rw [e2]; exact ih _ _ _ _ hw

/-- The hit roll's split of `binom (n + 1) c`: a normal hit keeps the budget, a
crit spends one (`bcrit`). -/
theorem hit_level (d : Damage) (hm100 : d.mCrit ≤ 100)
    (n c : Nat) (f : Rat × Int → List (Rat × Ending))
    (hf : ∀ x ∈ roll d.mCrit d.dieNormal d.dieCrit,
      x.1 * (if x.2 ≤ d.dieNormal then binom (critWn d) (critWc d) n c
        else bcrit (critWn d) (critWc d) n c) ≤ winProb (f x)) :
    binom (critWn d) (critWc d) (n + 1) c
      ≤ winProb ((roll d.mCrit d.dieNormal d.dieCrit).flatMap f) := by
  have ⟨h1, hn, hc⟩ := crit_weights d hm100
  rw [winProb_flatMap, binom_succ _ _ h1]
  refine Rat.le_trans ?_ (lsum_roll_ge _ _ _ _ (fun h => if h ≤ d.dieNormal then
    binom (critWn d) (critWc d) n c else bcrit (critWn d) (critWc d) n c) hf)
  simp only [Int.le_refl, if_true]
  have hb : bcrit (critWn d) (critWc d) n c ≤
      (if d.dieCrit ≤ d.dieNormal then binom (critWn d) (critWc d) n c
        else bcrit (critWn d) (critWc d) n c) := by
    split
    · exact bcrit_le_binom _ _ h1 hn hc _ _
    · exact Rat.le_refl
  have := Rat.mul_le_mul_of_nonneg_left hb hc
  unfold critWn critWc at *
  grind

theorem tree_critBound (d : Damage) (pf : Bool) (maxPool rPool : Int) (st : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100) :
    ∀ (fuel : Nat) (r m m' p p' : Int) (c : Nat), m ≤ m' → p' ≤ p →
      kpath d pf fuel r m' p' c = true →
      binom (critWn d) (critWc d) (mturns d pf fuel m') c
        ≤ winProb (tree d pf maxPool rPool st fuel r m p 0) := by
  have ⟨h1, hn, hc⟩ := crit_weights d hm100
  have hb0 := binom_nonneg _ _ h1 hn hc
  have hb1 := binom_le_one _ _ h1 hn hc
  intro fuel
  induction fuel with
  | zero => intro r m m' p p' c _ _ hw; simp [kpath] at hw
  | succ fuel ih =>
    intro r m m' p p' c hm hp hw
    have hkg := khit_ge d hd c
    cases pf
    · simp only [kpath, Bool.false_eq_true, if_false] at hw
      by_cases w1 : p' - khit d c ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      by_cases w2 : 0 < tick d false r ∧ p' - khit d c - tick d false r ≤ 0
      · rw [if_pos w2] at hw; exact absurd hw (by decide)
      rw [if_neg w2] at hw
      simp only [mturns, Bool.false_eq_true, if_false]
      simp only [tree, Bool.false_eq_true, if_false, Formal.FightOutcome.drink_noStock]
      generalize hn' : (if m' - d.killNormal ≤ 0 then 0 else mturns d false fuel (m' - d.killNormal))
        = n'
      apply hit_level d hm100
      rintro ⟨wh, h⟩ hx
      have hh := roll_mem hx
      have hwh := roll_nonneg hx
      simp only at hh hwh ⊢
      by_cases hgood : h ≤ d.dieNormal ∨ 0 < c
      · have hle : h ≤ khit d c := by
          rcases hgood with hg | hg
          · omega
          · rw [khit_pos d hg]; omega
        have g1 : ¬ p - h ≤ 0 := by omega
        have g2 : ¬ (0 < tick d false r ∧ p - h - tick d false r ≤ 0) :=
          fun h' => w2 ⟨h'.1, by omega⟩
        rw [if_neg g1, if_neg g2, winProb_scaleBy]
        apply Rat.mul_le_mul_of_nonneg_left _ hwh
        rw [winProb_flatMap]
        obtain ⟨c'', P', hV, hP', hkp⟩ : ∃ (c'' : Nat) (P' : Int),
            (if h ≤ d.dieNormal then binom (critWn d) (critWc d) n' c
              else bcrit (critWn d) (critWc d) n' c) = binom (critWn d) (critWc d) n' c'' ∧
            P' ≤ p - h - tick d false r ∧
            (¬ m' - d.killNormal ≤ 0 →
              kpath d false fuel (r + 1) (m' - d.killNormal) P' c'' = true) := by
          by_cases hhn : h ≤ d.dieNormal
          · refine ⟨c, p' - d.dieNormal - tick d false r, by rw [if_pos hhn], by omega, ?_⟩
            intro w3; rw [if_neg w3] at hw
            cases c with
            | zero => rw [khit_zero] at hw; exact hw
            | succ c =>
              rw [khit_pos d (by omega), Nat.add_sub_cancel] at hw
              have e1 : p' - d.dieCrit - tick d false r = (p' - tick d false r) - d.dieCrit := by
                omega
              have e2 : p' - d.dieNormal - tick d false r
                  = (p' - tick d false r) - d.dieNormal := by omega
              rw [e1] at hw; rw [e2]; exact kpath_shift d false hd _ _ _ _ _ hw
          · have hcpos : 0 < c := hgood.resolve_left hhn
            refine ⟨c - 1, p' - d.dieCrit - tick d false r,
              by rw [if_neg hhn, bcrit, if_neg (by omega)], by omega, ?_⟩
            intro w3; rw [if_neg w3, khit_pos d hcpos] at hw; exact hw
        rw [hV]
        apply lsum_roll_ge_const _ hp100
        rintro ⟨wk, kill⟩ hy
        have hkk := roll_mem hy
        have hwk := roll_nonneg hy
        simp only at hkk hwk ⊢
        split
        · simp only [winProb_single, if_true]
          have := Rat.mul_le_mul_of_nonneg_left (hb1 n' c'') hwk
          rwa [Rat.mul_one] at this
        · rename_i hmk
          have w3 : ¬ m' - d.killNormal ≤ 0 := by omega
          rw [winProb_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hwk
          have := ih (r + 1) (m - kill) (m' - d.killNormal) (p - h - tick d false r) P' c''
            (by omega) hP' (hkp w3)
          rw [← hn', if_neg w3]; exact this
      · have hc0 : c = 0 := by omega
        have hhn : ¬ h ≤ d.dieNormal := fun h' => hgood (Or.inl h')
        rw [if_neg hhn, bcrit, if_pos hc0, Rat.mul_zero]
        split
        · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
        · split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy, winProb_flatMap]
            apply Rat.mul_nonneg hwh
            apply lsum_nonneg
            rintro ⟨wk, kill⟩ hy
            have hwk := roll_nonneg hy
            simp only at hwk ⊢
            split
            · simp only [winProb_single, if_true]; exact hwk
            · rw [winProb_scaleBy]; exact Rat.mul_nonneg hwk (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _)
    · simp only [kpath, if_true] at hw
      by_cases w1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      have g0 : ¬ (0 < tick d true r ∧ p - tick d true r ≤ 0) := fun h => w1 ⟨h.1, by omega⟩
      simp only [mturns, if_true]
      simp only [tree, if_true, if_neg g0, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap]
      by_cases w3 : m' - d.killNormal ≤ 0
      · rw [if_pos w3, binom_zero]
        apply lsum_roll_ge_const _ hp100
        rintro ⟨wk, kill⟩ hy
        have hkk := roll_mem hy
        have hwk := roll_nonneg hy
        simp only at hkk hwk ⊢
        have hmk : m - kill ≤ 0 := by omega
        rw [if_pos hmk]
        simp only [winProb_single, if_true, Rat.mul_one]
        exact Rat.le_refl
      rw [if_neg w3] at hw ⊢
      by_cases w4 : p' - tick d true r - khit d c ≤ 0
      · rw [if_pos w4] at hw; exact absurd hw (by decide)
      rw [if_neg w4] at hw
      apply lsum_roll_ge_const _ hp100
      rintro ⟨wk, kill⟩ hy
      have hkk := roll_mem hy
      have hwk := roll_nonneg hy
      simp only at hkk hwk ⊢
      split
      · simp only [winProb_single, if_true]
        have := Rat.mul_le_mul_of_nonneg_left (hb1 (mturns d true fuel (m' - d.killNormal) + 1) c) hwk
        rwa [Rat.mul_one] at this
      · rename_i hmk
        rw [winProb_scaleBy]
        apply Rat.mul_le_mul_of_nonneg_left _ hwk
        apply hit_level d hm100
        rintro ⟨wh, h⟩ hx
        have hh := roll_mem hx
        have hwh := roll_nonneg hx
        simp only at hh hwh ⊢
        by_cases hgood : h ≤ d.dieNormal ∨ 0 < c
        · have hle : h ≤ khit d c := by
            rcases hgood with hg | hg
            · omega
            · rw [khit_pos d hg]; omega
          have g1 : ¬ p - tick d true r - h ≤ 0 := by omega
          rw [if_neg g1, winProb_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hwh
          obtain ⟨c'', P', hV, hP', hkp⟩ : ∃ (c'' : Nat) (P' : Int),
              (if h ≤ d.dieNormal then
                  binom (critWn d) (critWc d) (mturns d true fuel (m' - d.killNormal)) c
                else bcrit (critWn d) (critWc d) (mturns d true fuel (m' - d.killNormal)) c)
                = binom (critWn d) (critWc d) (mturns d true fuel (m' - d.killNormal)) c'' ∧
              P' ≤ p - tick d true r - h ∧
              kpath d true fuel (r + 1) (m' - d.killNormal) P' c'' = true := by
            by_cases hhn : h ≤ d.dieNormal
            · refine ⟨c, p' - tick d true r - d.dieNormal, by rw [if_pos hhn], by omega, ?_⟩
              cases c with
              | zero => rw [khit_zero] at hw; exact hw
              | succ c =>
                rw [khit_pos d (by omega), Nat.add_sub_cancel] at hw
                exact kpath_shift d true hd _ _ _ _ _ hw
            · have hcpos : 0 < c := hgood.resolve_left hhn
              refine ⟨c - 1, p' - tick d true r - d.dieCrit,
                by rw [if_neg hhn, bcrit, if_neg (by omega)], by omega, ?_⟩
              rw [khit_pos d hcpos] at hw; exact hw
          rw [hV]
          exact ih (r + 1) (m - kill) (m' - d.killNormal) (p - tick d true r - h) P' c''
            (by omega) hP' hkp
        · have hc0 : c = 0 := by omega
          have hhn : ¬ h ≤ d.dieNormal := fun h' => hgood (Or.inl h')
          rw [if_neg hhn, bcrit, if_pos hc0, Rat.mul_zero]
          split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hwh (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _)

/-- The proved P(win) floor of a fight at no stock (see `winProb_ge_critBound`):
if the counted-crit path from the fight's start with budget `c` wins, every path
with at most `c` monster crits wins, so P(win) is at least P(at most `c` of the
path's `mturns` monster turns crit). Follows `fightOdds`' gate. -/
def critBound (t : Terms) (d : Damage) (hp maxHp : Int) (c : Nat) : Rat :=
  match gate t with
  | .outSustain => 1
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then 0
    else if kpath d t.playerFirst maxTurns.toNat 1 (d.monsterHp * scale) (effHp hp maxHp * scale) c
    then binom (critWn d) (critWc d) (mturns d t.playerFirst maxTurns.toNat (d.monsterHp * scale)) c
    else 0
  | _ => 0

/-- **The counted-crit floor.** P(win) at any stock is at least `critBound` for
any crit budget `c`: with no stock `drink` is the identity, so a path's pool
after its monster turns depends only on how many of them crit (`kpath_shift`),
and a player crit only kills sooner; more stock never lowers P(win)
(`fightOdds_win_mono_stock`). `winProb_eq_one_of_worst` is the budget-`mturns`
case's cousin. -/
theorem winProb_ge_critBound (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock c : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100) :
    critBound t d hp maxHp c ≤ winProb (fightOdds t d hp maxHp restore stock) := by
  refine Rat.le_trans ?_
    (fightOdds_win_mono_stock t d hp maxHp restore 0 stock (Nat.zero_le _) hp100 hm100)
  unfold critBound fightOdds
  cases gate t <;> dsimp only
  case outSustain => simp only [winProb_single, if_true]; exact Rat.le_refl
  case none =>
    split
    · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
    · split
      · rename_i hw
        exact tree_critBound d _ _ _ 0 hk hd hp100 hm100 _ _ _ _ _ _ _
          (Int.le_refl _) (Int.le_refl _) hw
      · exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _
  all_goals simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl

end Formal.FightOdds
