-- @concept: combat, consumables @property: validity, monotonicity
/-
Fight odds (spec docs/superpowers/specs/2026-10-15-fight-odds-design.md §1).
The exact ending distribution of a fight over per-turn crit rolls, as an
UNMERGED tree; `ai/fight_odds_core.fight_odds` merges identical states.

LIFESTEAL rides the crit branch (server logs 2026-10-17, 2,327 heals): a crit
that does not kill heals its attacker `pHeal` / `mHeal`, capped at the
attacker's max (`cure`). It used to be a mean folded into every hit, which
cleared HP breakpoints the real heal does not (C3P0 v cyclops: 0.896 modelled,
0.807 observed over 161 fights, 0.816 exact).

BARRIER. The effect text: "At the start of the fight and every 5 played turns,
gain a protective barrier of {value} HP. All attacks are redirected to this
barrier until it is destroyed." Lor v king_slime, 2026-10-17: the barrier is set
back to full at the start of the monster's 5th and 10th turns, and a hit's
excess goes through ("36 absorbed, 15 through"). The tree carries the barrier
left: a player hit `absorb`s, and the monster's turn in every 5th round
`refresh`es it before the monster hits (a ruling for a monster moving first: no
such fight is on record). A monster's lifesteal heals its HP, never the barrier.

## Results

* `fightOdds_sum_one` — the endings' probabilities sum to 1.
* `fightOdds_noCrit` — with both crit chances 0 and no burn the tree is the
  single ending of `Formal.FightOutcome.fightOutcome` (for a monster with
  positive HP and a non-negative barrier; that walk charges burn as a flat
  bound, the tree as ticks; its kill round `PredictWin.killRounds` is the
  tree's barrier walk, `PredictWin.killRounds_killsAt`).
* `fightOdds_win_mono_stock` — more restore stock never lowers P(win).
* `fightOdds_win_mono_hp` — with no restore stock, more starting HP never
  lowers P(win). (With stock it is FALSE: see the theorem's comment.)
* `winProb_eq_one_of_worst` — a fight won with no stock on the worst-case path
  (no player crit, every monster turn a crit) is won with probability 1 at any
  stock (a non-negative barrier: a smaller hit then leaves no less barrier).
* `winProb_ge_critBound` — the counted-crit floor: if the no-stock path on which
  the player never crits and the monster crits its first `c` turns wins, P(win)
  at any stock is at least P(at most `c` of that path's monster turns crit)
  (`critBound`, a single path plus a binomial table, cheap for the kernel). The
  path heals the monster `mUp` on EVERY monster turn, uncapped, so it bounds
  every real monster pool whichever turns crit (its barrier, hit by the normal
  kill only, bounds every real barrier).

Lean core only — no Mathlib.
-/
import Formal.FightOutcome

namespace Formal.FightOdds

open Formal.FightOutcome (Terms scale gate roundsToKill effHp drink fightOutcome Exit walk
  coupled coupled_le coupled_sub gate_none_dieStep)
open Formal.PredictWin (maxTurns ceilDiv ceilDiv_mul_ge ceilDiv_pred_mul_lt ceilDiv_pos absorb refresh
  preShield postShield killsAt killRounds_killsAt not_walled_of_le)

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
  /-- The player's lifesteal heal on a crit turn, ×10000 (`PredictWin.lifestealHeal`
  of its crit-turn damage); 0 without lifesteal. -/
  pHeal : Int := 0
  /-- The monster's lifesteal heal on its crit turn, ×10000; 0 without lifesteal. -/
  mHeal : Int := 0
  /-- The monster's barrier HP, raised at the start and refreshed every 5
  monster turns (`PredictWin.refresh`); 0 without one. -/
  barrier : Int := 0

structure Ending where
  win : Bool
  turns : Int
  hpEnd : Int
  used : Nat
  deriving DecidableEq, Repr

/-- The outcomes of one crit roll: `(probability, amount, heal)`, no zero
branch. Only a crit heals: lifesteal fires on the attacker's crit turn. -/
def roll (pct : Nat) (normal crit heal : Int) : List (Rat × Int × Int) :=
  [(((100 - pct : Nat) : Rat) / 100, normal, 0), (((pct : Nat) : Rat) / 100, crit, heal)].filter
    (fun b => b.1 ≠ 0)

/-- A lifesteal heal of `h` on a pool `p` capped at `cap`: the pool rises by
`h` but not past `cap`, and a heal never lowers a pool (a pool above `cap`,
which a mean-modelled negative hit can produce, stays where it is). Server logs
2026-10-17: a heal at 717/725 restores 8 of its 25. -/
def cure (p h cap : Int) : Int := max p (min (p + h) cap)

/-- The burn tick of the player's turn in round `r`: the monster burns on its
first turn, so tick `i` lands in round `i + 2` when the player moves first and
in round `i + 1` when the monster does; past the last tick it is 0. -/
def tick (d : Damage) (pf : Bool) (r : Int) : Int :=
  let i := if pf then r - 2 else r - 1
  if i < 0 then 0 else d.burn.getD i.toNat 0

/-- Scale every probability of a list. -/
def scaleBy (w : Rat) (xs : List (Rat × Ending)) : List (Rat × Ending) :=
  xs.map fun e => (w * e.1, e.2)

/-- The tree from round `r` with `fuel` rounds left, the monster's pool `m`
behind `s` of barrier. A player turn takes its burn tick, a loss if it empties
the pool, then drinks (`q := drink …`) before it hits; the hit is `absorb`ed by
the barrier and what passes through kills or not. A crit that does not kill
heals the player (`cure`, capped at `maxPool`). A monster crit heals the
monster's HP (capped at its HP, never the barrier). The monster's turn in every
5th round refreshes the barrier first (`refresh`): after the player's hit when
the player moves first, before it when the monster does. A killing blow heals
nobody: the fight is over. -/
def tree (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat) :
    Nat → Int → Int → Int → Int → Nat → List (Rat × Ending)
  | 0, r, _, _, _, k => [(1, ⟨false, r - 1, 0, stock - k⟩)]
  | fuel + 1, r, m, s, p, k =>
    if pf then
      if 0 < tick d pf r ∧ p - tick d pf r ≤ 0 then [(1, ⟨false, r, 0, stock - k⟩)]
      else
        let q := drink (p - tick d pf r) maxPool rPool k
        (roll d.pCrit d.killNormal d.killCrit d.pHeal).flatMap fun (wk, kill, ph) =>
          if m - (absorb s kill).1 ≤ 0 then [(wk, ⟨true, r, q.1, stock - q.2⟩)]
          else scaleBy wk ((roll d.mCrit d.dieNormal d.dieCrit d.mHeal).flatMap fun (wh, hit, mh) =>
            if cure q.1 ph maxPool - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - q.2⟩)]
            else scaleBy wh (tree d pf maxPool rPool stock fuel (r + 1)
              (cure (m - (absorb s kill).1) mh (d.monsterHp * scale))
              (refresh (absorb s kill).2 (d.barrier * scale) r) (cure q.1 ph maxPool - hit) q.2))
    else
      (roll d.mCrit d.dieNormal d.dieCrit d.mHeal).flatMap fun (wh, hit, mh) =>
        if p - hit ≤ 0 then [(wh, ⟨false, r, 0, stock - k⟩)]
        else if 0 < tick d pf r ∧ p - hit - tick d pf r ≤ 0 then [(wh, ⟨false, r, 0, stock - k⟩)]
        else
          let q := drink (p - hit - tick d pf r) maxPool rPool k
          scaleBy wh ((roll d.pCrit d.killNormal d.killCrit d.pHeal).flatMap fun (wk, kill, ph) =>
            if cure m mh (d.monsterHp * scale) - (absorb (refresh s (d.barrier * scale) r) kill).1 ≤ 0
            then [(wk, ⟨true, r, q.1, stock - q.2⟩)]
            else scaleBy wk (tree d pf maxPool rPool stock fuel (r + 1)
              (cure m mh (d.monsterHp * scale) - (absorb (refresh s (d.barrier * scale) r) kill).1)
              (absorb (refresh s (d.barrier * scale) r) kill).2 (cure q.1 ph maxPool) q.2))

/-- `fight_odds_core.fight_odds`, unmerged. -/
def fightOdds (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat) :
    List (Rat × Ending) :=
  match gate t with
  | .outSustain => [(1, ⟨true, roundsToKill t, effHp hp maxHp * scale, 0⟩)]
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then [(1, ⟨false, 0, 0, 0⟩)]
    else tree d t.playerFirst (maxHp * scale) ((restore : Int) * scale) stock
      maxTurns.toNat 1 (d.monsterHp * scale) (d.barrier * scale) (effHp hp maxHp * scale) stock
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

theorem lsum_filter_ne_zero {β : Type} :
    ∀ xs : List (Rat × β),
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

theorem roll_sum (pct : Nat) (normal crit heal : Int) (h : pct ≤ 100) :
    lsum (·.1) (roll pct normal crit heal) = 1 := by
  unfold roll
  rw [lsum_filter_ne_zero]
  have h2 : ((100 - pct : Nat) : Rat) + (pct : Rat) = 100 := by
    rw [← Rat.natCast_add, Nat.sub_add_cancel h]; rfl
  simp only [lsum, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
  grind

theorem roll_nonneg {pct : Nat} {normal crit heal : Int} {x : Rat × Int × Int}
    (hx : x ∈ roll pct normal crit heal) : 0 ≤ x.1 := by
  unfold roll at hx
  have hm := (List.mem_filter.mp hx).1
  have h1 := @Rat.natCast_nonneg (100 - pct)
  have h2 := @Rat.natCast_nonneg pct
  simp only [List.mem_cons, List.not_mem_nil, or_false] at hm
  rcases hm with rfl | rfl <;> grind

theorem roll_zero (normal crit heal : Int) : roll 0 normal crit heal = [(1, normal, 0)] := by
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

/-! ### The lifesteal heal. -/

theorem cure_ge (p h cap : Int) : p ≤ cure p h cap := by
  unfold cure; omega

theorem cure_mono {p p' : Int} (h cap : Int) (hp : p ≤ p') : cure p h cap ≤ cure p' h cap := by
  unfold cure; omega

theorem cure_zero (p cap : Int) : cure p 0 cap = p := by
  unfold cure; omega

/-- A heal raises a pool by at most its positive part. -/
theorem cure_le_up (p h cap : Int) : cure p h cap ≤ p + max 0 h := by
  unfold cure; omega

theorem coupled_cure {p p' : Int} {k k' : Nat} (h cap : Int) (hc : coupled p k p' k') :
    coupled (cure p h cap) k (cure p' h cap) k' := by
  rcases hc with ⟨rfl, hk⟩ | ⟨hk, hle⟩
  · exact Or.inl ⟨rfl, hk⟩
  · exact Or.inr ⟨hk, cure_mono h cap hle⟩

/-! ### (a) The probabilities sum to 1. -/

theorem mass_flatMap_roll (pct : Nat) (normal crit heal : Int) (h : pct ≤ 100)
    (f : Rat × Int × Int → List (Rat × Ending))
    (hf : ∀ x ∈ roll pct normal crit heal, mass (f x) = x.1) :
    mass ((roll pct normal crit heal).flatMap f) = 1 := by
  rw [mass_flatMap, lsum_congr _ _ _ hf, roll_sum _ _ _ _ h]

theorem mass_single (w : Rat) (e : Ending) : mass [(w, e)] = w := by
  simp only [mass, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
  exact Rat.add_zero w

theorem tree_mass (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat)
    (hp : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    ∀ (fuel : Nat) (r m s p : Int) (k : Nat),
      mass (tree d pf maxPool rPool stock fuel r m s p k) = 1 := by
  intro fuel
  induction fuel with
  | zero => intro r m s p k; simp only [tree]; exact mass_single _ _
  | succ fuel ih =>
    intro r m s p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      apply mass_flatMap_roll _ _ _ _ hm
      rintro ⟨wh, hit, mh⟩ _
      simp only
      split
      · exact mass_single _ _
      · split
        · exact mass_single _ _
        · rw [mass_scaleBy, mass_flatMap_roll _ _ _ _ hp, Rat.mul_one]
          rintro ⟨wk, kill, ph⟩ _
          simp only
          split
          · exact mass_single _ _
          · rw [mass_scaleBy, ih, Rat.mul_one]
    · simp only [tree, if_true]
      split
      · exact mass_single _ _
      · apply mass_flatMap_roll _ _ _ _ hp
        rintro ⟨wk, kill, ph⟩ _
        simp only
        split
        · exact mass_single _ _
        · rw [mass_scaleBy, mass_flatMap_roll _ _ _ _ hm, Rat.mul_one]
          rintro ⟨wh, hit, mh⟩ _
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
    · exact tree_mass _ _ _ _ _ hp' hm _ _ _ _ _ _
  · exact mass_single _ _

/-! ### (b) With no crit the tree is the deterministic walk. -/

/-- Without burn every tick is 0. -/
theorem tick_nil (d : Damage) (pf : Bool) (r : Int) (h : d.burn = []) : tick d pf r = 0 := by
  simp [tick, h]

theorem tree_noCrit (d : Damage) (pf : Bool) (maxPool rPool : Int) (stock : Nat)
    (hp0 : d.pCrit = 0) (hm0 : d.mCrit = 0) (hb : d.burn = []) :
    ∀ (n fuel : Nat) (r m s p : Int) (k : Nat), n < fuel →
      killsAt d.killNormal (d.barrier * scale) pf n r m s →
      tree d pf maxPool rPool stock fuel r m s p k =
        [(1, ⟨(walk pf d.dieNormal maxPool rPool (n + 1) r p k).win,
              (walk pf d.dieNormal maxPool rPool (n + 1) r p k).turns,
              (walk pf d.dieNormal maxPool rPool (n + 1) r p k).pool,
              stock - (walk pf d.dieNormal maxPool rPool (n + 1) r p k).left⟩)] := by
  intro n
  induction n with
  | zero =>
    intro fuel r m s p k hf hka
    obtain ⟨f, rfl⟩ : ∃ f, fuel = f + 1 := ⟨fuel - 1, by omega⟩
    cases pf
    · simp only [killsAt, preShield, Bool.false_eq_true, if_false] at hka
      simp only [tree, walk, hp0, hm0, roll_zero, cure_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, Bool.false_eq_true, if_false, if_true, scaleBy_one, hka]
      split <;> rfl
    · simp only [killsAt, preShield, if_true] at hka
      simp only [tree, walk, hp0, hm0, roll_zero, cure_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, if_true, hka]
  | succ n ih =>
    intro fuel r m s p k hf hka
    obtain ⟨f, rfl⟩ : ∃ f, fuel = f + 1 := ⟨fuel - 1, by omega⟩
    rw [walk]
    cases pf
    · simp only [killsAt, preShield, postShield, Bool.false_eq_true, if_false] at hka
      obtain ⟨hk, hrest⟩ := hka
      have hih := fun p k => ih f (r + 1) _ _ p k (by omega) hrest
      simp only [tree, hp0, hm0, roll_zero, cure_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
        Int.sub_zero, if_false, List.flatMap_cons, List.flatMap_nil,
        List.append_nil, Bool.false_eq_true, if_false, scaleBy_one, hk,
        Nat.add_one_ne_zero]
      split
      · rfl
      · rw [hih]
    · simp only [killsAt, preShield, postShield, if_true] at hka
      obtain ⟨hk, hrest⟩ := hka
      have hih := fun p k => ih f (r + 1) _ _ p k (by omega) hrest
      simp only [tree, hp0, hm0, roll_zero, cure_zero, tick_nil d _ _ hb, Int.lt_irrefl, false_and,
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

/-- (b) With both crit chances 0 the tree is the one ending of `fightOutcome`:
the tree's barrier walk kills in `roundsToKill` rounds
(`PredictWin.killRounds_killsAt`). A real monster has HP ≥ 1 and a barrier
≥ 0; at HP ≤ 0 the walk reports `roundsToKill` rounds while the tree's first
hit always kills, hence `hm0hp`. -/
theorem fightOdds_noCrit (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp0 : d.pCrit = 0) (hm0 : d.mCrit = 0) (hb : d.burn = [])
    (hk : d.killNormal = t.killStep) (hd : d.dieNormal = t.dieStep)
    (hmhp : d.monsterHp = t.monsterHp) (hbar : d.barrier = t.barrier)
    (hm0hp : 0 < t.monsterHp) (hb0 : 0 ≤ t.barrier) :
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
      obtain ⟨n, hn, hka⟩ := killRounds_killsAt t.monsterHp t.barrier t.killStep t.playerFirst hks
        (by omega) hb0 (not_walled_of_le _ _ _ _ hcap)
      have hn' : (roundsToKill t).toNat = n + 1 := by
        unfold roundsToKill; omega
      have hcap' : roundsToKill t ≤ 100 := hcap
      have hmt : (maxTurns.toNat) = 100 := rfl
      rw [hn', ← hd, tree_noCrit d _ _ _ _ hp0 hm0 hb n maxTurns.toNat _ _ _ _ _
        (by unfold roundsToKill at hcap'; omega) (by rw [hk, hbar, hmhp]; exact hka)]
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
    ∀ (fuel : Nat) (r m s p : Int) (k : Nat),
      0 ≤ winProb (tree d pf maxPool rPool stock fuel r m s p k) := by
  intro fuel
  induction fuel with
  | zero => intro r m s p k; simp only [tree, winProb_single]; exact Rat.le_refl
  | succ fuel ih =>
    intro r m s p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap]
      apply lsum_nonneg
      rintro ⟨wh, hit, mh⟩ hx
      have hw := roll_nonneg hx
      simp only at hw ⊢
      split
      · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · split
        · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
        · rw [winProb_scaleBy, winProb_flatMap]
          apply Rat.mul_nonneg hw
          apply lsum_nonneg
          rintro ⟨wk, kill, ph⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · simp only [winProb_single, if_true]; exact hw'
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (ih _ _ _ _ _)
    · simp only [tree, if_true]
      split
      · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
      · rw [winProb_flatMap]
        apply lsum_nonneg
        rintro ⟨wk, kill, ph⟩ hx
        have hw := roll_nonneg hx
        simp only at hw ⊢
        split
        · simp only [winProb_single, if_true]; exact hw
        · rw [winProb_scaleBy, winProb_flatMap]
          apply Rat.mul_nonneg hw
          apply lsum_nonneg
          rintro ⟨wh, hit, mh⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (ih _ _ _ _ _)

/-- The coupled trees: the poorer state's P(win) never exceeds the richer one's
(the monster pool and round are shared; the stock base only labels `used`). -/
theorem tree_mono (d : Damage) (pf : Bool) (maxPool rPool : Int) (hM : 0 ≤ maxPool)
    (hr : 0 ≤ rPool) (st st' : Nat) :
    ∀ (fuel : Nat) (r m s p p' : Int) (k k' : Nat), coupled p k p' k' →
      winProb (tree d pf maxPool rPool st fuel r m s p k)
        ≤ winProb (tree d pf maxPool rPool st' fuel r m s p' k') := by
  intro fuel
  induction fuel with
  | zero =>
    intro r m s p p' k k' _
    simp only [tree, winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
  | succ fuel ih =>
    intro r m s p p' k k' hc
    have hpp := coupled_le hc
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap, winProb_flatMap]
      apply lsum_le
      rintro ⟨wh, hit, mh⟩ hx
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
            rintro ⟨wk, kill, ph⟩ hy
            have hw' := roll_nonneg hy
            simp only at hw' ⊢
            split
            · simp only [winProb_single, if_true]; exact hw'
            · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _)
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
              rintro ⟨wk, kill, ph⟩ hy
              have hw' := roll_nonneg hy
              simp only at hw' ⊢
              split
              · simp only [winProb_single, if_true]; exact hw'
              · rw [winProb_scaleBy]; exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _)
            · rw [if_neg g0, winProb_scaleBy, winProb_scaleBy]
              apply Rat.mul_le_mul_of_nonneg_left _ hw
              rw [winProb_flatMap, winProb_flatMap]
              apply lsum_le
              rintro ⟨wk, kill, ph⟩ hy
              have hw' := roll_nonneg hy
              simp only at hw' ⊢
              split
              · simp only [winProb_single, if_true]; exact Rat.le_refl
              · rw [winProb_scaleBy, winProb_scaleBy]
                apply Rat.mul_le_mul_of_nonneg_left _ hw'
                exact ih _ _ _ _ _ _ _ (coupled_cure ph maxPool (drink_coupled_nonneg _ _ hM hr _ _ _ _
                  (coupled_sub (tick d false r) (coupled_sub hit hc))))
    · by_cases g1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · have g0 : 0 < tick d true r ∧ p - tick d true r ≤ 0 := ⟨g1.1, by omega⟩
        simp only [tree, if_true, if_pos g0, if_pos g1, winProb_single, Bool.false_eq_true,
          if_false]
        exact Rat.le_refl
      · by_cases g0 : 0 < tick d true r ∧ p - tick d true r ≤ 0
        · have hz : winProb (tree d true maxPool rPool st (fuel + 1) r m s p k) = 0 := by
            simp only [tree, if_true, if_pos g0, winProb_single, Bool.false_eq_true, if_false]
          rw [hz]; exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _
        · have hd := drink_coupled_nonneg _ _ hM hr _ _ _ _ (coupled_sub (tick d true r) hc)
          have hdd := coupled_le hd
          simp only [tree, if_true, if_neg g0, if_neg g1]
          rw [winProb_flatMap, winProb_flatMap]
          apply lsum_le
          rintro ⟨wk, kill, ph⟩ hx
          have hw := roll_nonneg hx
          simp only at hw ⊢
          split
          · simp only [winProb_single, if_true]; exact Rat.le_refl
          · rw [winProb_scaleBy, winProb_scaleBy]
            apply Rat.mul_le_mul_of_nonneg_left _ hw
            rw [winProb_flatMap, winProb_flatMap]
            apply lsum_le
            rintro ⟨wh, hit, mh⟩ hy
            have hw' := roll_nonneg hy
            simp only at hw' ⊢
            have hcu := coupled_cure ph maxPool hd
            have hcc := coupled_le hcu
            by_cases h1 : cure (drink (p' - tick d true r) maxPool rPool k').1 ph maxPool - hit ≤ 0
            · have h0 : cure (drink (p - tick d true r) maxPool rPool k).1 ph maxPool - hit ≤ 0 := by
                omega
              rw [if_pos h0, if_pos h1]
              simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
            · rw [if_neg h1]
              by_cases h0 : cure (drink (p - tick d true r) maxPool rPool k).1 ph maxPool - hit ≤ 0
              · rw [if_pos h0]
                simp only [winProb_single, Bool.false_eq_true, if_false]
                rw [winProb_scaleBy]
                exact Rat.mul_nonneg hw' (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _)
              · rw [if_neg h0, winProb_scaleBy, winProb_scaleBy]
                exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _ _ _ _ (coupled_sub hit hcu)) hw'

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
        (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) _ _ _ _ _ _ _ _ _ _
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
      · exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _
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
        (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) _ _ _ _ _ _ _ _ _ _
        (Or.inr ⟨rfl, by simp only [scale]; omega⟩)
  · exact Rat.le_refl

/-! ### (d) A worst-case win with no stock is a sure win. -/

theorem roll_hundred (normal crit heal : Int) : roll 100 normal crit heal = [(1, crit, heal)] := by
  have h0 : (((100 - 100 : Nat) : Rat) / 100) = 0 := by grind
  have h1 : (((100 : Nat) : Rat) / 100) = 1 := by grind
  unfold roll
  rw [h0, h1]; simp

theorem roll_mem {pct : Nat} {normal crit heal : Int} {x : Rat × Int × Int}
    (hx : x ∈ roll pct normal crit heal) : (x.2.1 = normal ∧ x.2.2 = 0) ∨ (x.2.1 = crit ∧ x.2.2 = heal) := by
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
    ∀ (fuel : Nat) (r m s p : Int) (k : Nat),
      winProb (tree d pf maxPool rPool stock fuel r m s p k)
        ≤ mass (tree d pf maxPool rPool stock fuel r m s p k) := by
  intro fuel
  induction fuel with
  | zero => intro r m s p k; simp only [tree]; exact winProb_single_le _ _ (by decide)
  | succ fuel ih =>
    intro r m s p k
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_le
      rintro ⟨wh, hit, mh⟩ hx
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
          rintro ⟨wk, kill, ph⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · exact winProb_single_le _ _ hw'
          · rw [winProb_scaleBy, mass_scaleBy]
            exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _ _) hw'
    · simp only [tree, if_true]
      split
      · exact winProb_single_le _ _ (by decide)
      · rw [winProb_flatMap, mass_flatMap]
        apply lsum_le
        rintro ⟨wk, kill, ph⟩ hx
        have hw := roll_nonneg hx
        simp only at hw ⊢
        split
        · exact winProb_single_le _ _ hw
        · rw [winProb_scaleBy, mass_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hw
          rw [winProb_flatMap, mass_flatMap]
          apply lsum_le
          rintro ⟨wh, hit, mh⟩ hy
          have hw' := roll_nonneg hy
          simp only at hw' ⊢
          split
          · exact winProb_single_le _ _ hw'
          · rw [winProb_scaleBy, mass_scaleBy]
            exact Rat.mul_le_mul_of_nonneg_left (ih _ _ _ _ _) hw'

theorem fightOdds_wp_le_one (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hp' : d.pCrit ≤ 100) (hm : d.mCrit ≤ 100) :
    winProb (fightOdds t d hp maxHp restore stock) ≤ 1 := by
  unfold fightOdds
  split
  · simp only [winProb_single, if_true]; exact Rat.le_refl
  · split
    · simp only [winProb_single, Bool.false_eq_true, if_false]; decide
    · rw [← tree_mass d _ _ _ stock hp' hm maxTurns.toNat 1 (d.monsterHp * scale)
        (d.barrier * scale) (effHp hp maxHp * scale) stock]
      exact tree_wp_le_mass _ _ _ _ _ _ _ _ _ _ _
  · simp only [winProb_single, Bool.false_eq_true, if_false]; decide

/-- A hit no smaller against a barrier no larger gets no less through and
leaves no more barrier (the larger barrier non-negative). -/
theorem absorb_couple {s s' a a' : Int} (ha : a' ≤ a) (hs : s ≤ s') (hs0 : 0 ≤ s') :
    (absorb s' a').1 ≤ (absorb s a).1 ∧ (absorb s a).2 ≤ (absorb s' a').2 := by
  unfold absorb
  by_cases h1 : a ≤ 0 <;> by_cases h2 : a' ≤ 0 <;> simp only [h1, h2, ↓reduceIte] <;> omega

theorem absorb_kept_nonneg {s : Int} (a : Int) (hs : 0 ≤ s) : 0 ≤ (absorb s a).2 := by
  unfold absorb
  by_cases h1 : a ≤ 0 <;> simp only [h1, ↓reduceIte] <;> omega

theorem refresh_mono {s s' : Int} (full r : Int) (h : s ≤ s') :
    refresh s full r ≤ refresh s' full r := by
  unfold refresh; split <;> omega

theorem refresh_nonneg {s full : Int} (r : Int) (hs : 0 ≤ s) (hf : 0 ≤ full) :
    0 ≤ refresh s full r := by
  unfold refresh; split <;> omega

/-- With no stock the real tree loses nowhere the worst-case tree `d'` (no player
crit, every monster turn a crit) wins: every real leaf wins, so P(win) is the mass.
The worst tree heals the monster on every turn (each is a crit) and the player on
none; the real tree's monster pool and barrier never exceed the worst's
(`cure_mono`, `cure_ge`, `absorb_couple`) and its player pool never falls below it. -/
theorem tree_worst (d d' : Damage) (pf : Bool) (maxPool rPool : Int) (st : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit) (hB : 0 ≤ d.barrier)
    (hp0 : d'.pCrit = 0) (hm1 : d'.mCrit = 100) (hkn : d'.killNormal = d.killNormal)
    (hdc : d'.dieCrit = d.dieCrit) (htick : ∀ pf r, tick d' pf r = tick d pf r)
    (hmh : d'.mHeal = d.mHeal) (hmhp : d'.monsterHp = d.monsterHp)
    (hbar : d'.barrier = d.barrier) :
    ∀ (fuel : Nat) (r m m' s s' p p' : Int), m ≤ m' → s ≤ s' → 0 ≤ s' → p' ≤ p →
      winProb (tree d' pf maxPool rPool st fuel r m' s' p' 0) = 1 →
      winProb (tree d pf maxPool rPool st fuel r m s p 0)
        = mass (tree d pf maxPool rPool st fuel r m s p 0) := by
  have hfull : 0 ≤ d.barrier * scale := Int.mul_nonneg hB (by decide)
  intro fuel
  induction fuel with
  | zero =>
    intro r m m' s s' p p' _ _ _ _ hw
    simp [tree, winProb_single] at hw
  | succ fuel ih =>
    intro r m m' s s' p p' hm hs hs0 hp hw
    cases pf
    · simp only [tree, Bool.false_eq_true, if_false, hp0, hm1, roll_zero, roll_hundred,
        List.flatMap_cons, List.flatMap_nil, List.append_nil, scaleBy_one,
        Formal.FightOutcome.drink_noStock, cure_zero,
        htick, hkn, hdc, hmh, hmhp, hbar] at hw
      simp only [tree, Bool.false_eq_true, if_false, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_congr
      rintro ⟨wh, hit, mh⟩ hx
      have hh := roll_mem hx
      simp only at hh ⊢
      have hhit : hit ≤ d.dieCrit := by omega
      have hcm : cure m mh (d.monsterHp * scale) ≤ cure m' d.mHeal (d.monsterHp * scale) := by
        rcases hh with ⟨_, rfl⟩ | ⟨_, rfl⟩
        · rw [cure_zero]; exact Int.le_trans hm (cure_ge _ _ _)
        · exact cure_mono _ _ hm
      have hrs := refresh_mono (d.barrier * scale) r hs
      have hrs0 := refresh_nonneg (s := s') (full := d.barrier * scale) r hs0 hfull
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
      rintro ⟨wk, kill, ph⟩ hy
      have hh' := roll_mem hy
      simp only at hh' ⊢
      have hkill : d.killNormal ≤ kill := by omega
      have hab := absorb_couple hkill hrs hrs0
      split
      · rw [winProb_single, mass_single]; rfl
      · rename_i hmk
        have w3 : ¬ cure m' d.mHeal (d.monsterHp * scale)
            - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1 ≤ 0 := by omega
        rw [if_neg w3] at hw
        rw [winProb_scaleBy, mass_scaleBy, ih _ _ _ _ _ _ _ (by omega) hab.2
          (absorb_kept_nonneg _ hrs0) (Int.le_trans (by omega) (cure_ge _ ph maxPool)) hw]
    · simp only [tree, if_true, hp0, hm1, roll_zero, roll_hundred,
        List.flatMap_cons, List.flatMap_nil, List.append_nil, scaleBy_one,
        Formal.FightOutcome.drink_noStock, cure_zero,
        htick, hkn, hdc, hmh, hmhp, hbar] at hw
      by_cases w1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · rw [if_pos w1] at hw; simp [winProb_single] at hw
      rw [if_neg w1] at hw
      have g0 : ¬ (0 < tick d true r ∧ p - tick d true r ≤ 0) :=
        fun h => w1 ⟨h.1, by omega⟩
      simp only [tree, if_true, if_neg g0, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap, mass_flatMap]
      apply lsum_congr
      rintro ⟨wk, kill, ph⟩ hx
      have hh := roll_mem hx
      simp only at hh ⊢
      have hkill : d.killNormal ≤ kill := by omega
      have hab := absorb_couple hkill hs hs0
      split
      · rw [winProb_single, mass_single]; rfl
      · rename_i hmk
        have w3 : ¬ m' - (absorb s' d.killNormal).1 ≤ 0 := by omega
        rw [if_neg w3] at hw
        rw [winProb_scaleBy, mass_scaleBy, winProb_flatMap, mass_flatMap]
        congr 1
        apply lsum_congr
        rintro ⟨wh, hit, mh⟩ hy
        have hh' := roll_mem hy
        simp only at hh' ⊢
        have hhit : hit ≤ d.dieCrit := by omega
        have hcp := cure_ge (p - tick d true r) ph maxPool
        have hcm : cure (m - (absorb s kill).1) mh (d.monsterHp * scale)
            ≤ cure (m' - (absorb s' d.killNormal).1) d.mHeal (d.monsterHp * scale) := by
          rcases hh' with ⟨_, rfl⟩ | ⟨_, rfl⟩
          · rw [cure_zero]; exact Int.le_trans (by omega) (cure_ge _ _ _)
          · exact cure_mono _ _ (by omega)
        by_cases w2 : p' - tick d true r - d.dieCrit ≤ 0
        · rw [if_pos w2] at hw; simp [winProb_single] at hw
        rw [if_neg w2] at hw
        have h0 : ¬ cure (p - tick d true r) ph maxPool - hit ≤ 0 := by omega
        rw [if_neg h0, winProb_scaleBy, mass_scaleBy, ih _ _ _ _ _ _ _ hcm
          (refresh_mono _ r hab.2) (refresh_nonneg r (absorb_kept_nonneg _ hs0) hfull) (by omega) hw]

/-- A fight won on the worst-case path (no player crit, every monster turn a
crit) with no restore stock is won with probability 1 — at any stock, since
more stock never lowers P(win) (`fightOdds_win_mono_stock`). With stock the
worst path alone is not enough: the 50% drink threshold can let the richer
pool skip a drink the worst pool takes (counterexample in the PR notes). -/
theorem winProb_eq_one_of_worst (t : Terms) (d : Damage) (hp maxHp : Int) (restore stock : Nat)
    (hk : d.killNormal ≤ d.killCrit) (hd : d.dieNormal ≤ d.dieCrit)
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100) (hB : 0 ≤ d.barrier)
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
      rw [tree_worst d { d with pCrit := 0, mCrit := 100 } _ _ _ _ hk hd hB rfl rfl rfl rfl
        (fun _ _ => rfl) rfl rfl rfl _ _ _ _ _ _ _ _ (Int.le_refl _) (Int.le_refl _)
        (Int.mul_nonneg hB (by decide)) (Int.le_refl _) hw]
      exact tree_mass _ _ _ _ _ hp100 hm100 _ _ _ _ _ _
    all_goals simp [winProb_single] at hw
  have hge := fightOdds_win_mono_stock t d hp maxHp restore 0 stock (Nat.zero_le _) hp100 hm100
  rw [h0] at hge
  exact Rat.le_antisymm (fightOdds_wp_le_one t d hp maxHp restore stock hp100 hm100) hge

/-! ### (e) A counted-crit lower bound with no stock. -/

/-- The monster's hit on the counted-crit path: a crit while crits are left. -/
def khit (d : Damage) (c : Nat) : Int := if 0 < c then d.dieCrit else d.dieNormal

/-- The most the monster's lifesteal can heal it in one turn (×10000): its crit
heal's positive part. The counted-crit path charges it on EVERY monster turn,
uncapped, so the path's monster pool bounds every real one whichever turns
crit (`cure_le_up`) and stays independent of where the crits fall. -/
def mUp (d : Damage) : Int := max 0 d.mHeal

/-- The counted-crit path with no stock (`drink` is then the identity): the
player never crits (so never heals), the monster crits its next `c` turns and
then hits normal, healing `mUp` every turn. The barrier `s` takes the normal
kill and is refreshed as in the tree. `true` iff that single path is won
within `fuel` rounds. -/
def kpath (d : Damage) (pf : Bool) : Nat → Int → Int → Int → Int → Nat → Bool
  | 0, _, _, _, _, _ => false
  | fuel + 1, r, m, s, p, c =>
    if pf then
      if 0 < tick d pf r ∧ p - tick d pf r ≤ 0 then false
      else if m - (absorb s d.killNormal).1 ≤ 0 then true
      else if p - tick d pf r - khit d c ≤ 0 then false
      else kpath d pf fuel (r + 1) (m - (absorb s d.killNormal).1 + mUp d)
        (refresh (absorb s d.killNormal).2 (d.barrier * scale) r) (p - tick d pf r - khit d c) (c - 1)
    else
      if p - khit d c ≤ 0 then false
      else if 0 < tick d pf r ∧ p - khit d c - tick d pf r ≤ 0 then false
      else if m + mUp d - (absorb (refresh s (d.barrier * scale) r) d.killNormal).1 ≤ 0 then true
      else kpath d pf fuel (r + 1) (m + mUp d - (absorb (refresh s (d.barrier * scale) r) d.killNormal).1)
        (absorb (refresh s (d.barrier * scale) r) d.killNormal).2 (p - khit d c - tick d pf r) (c - 1)

/-- The monster's turns before the never-critting player's kill, within `fuel`
rounds from round `r` (the monster pool and barrier alone decide it, healing
`mUp` every monster turn). -/
def mturns (d : Damage) (pf : Bool) : Nat → Int → Int → Int → Nat
  | 0, _, _, _ => 0
  | fuel + 1, r, m, s =>
    if pf then
      (if m - (absorb s d.killNormal).1 ≤ 0 then 0
       else mturns d pf fuel (r + 1) (m - (absorb s d.killNormal).1 + mUp d)
         (refresh (absorb s d.killNormal).2 (d.barrier * scale) r) + 1)
    else
      (if m + mUp d - (absorb (refresh s (d.barrier * scale) r) d.killNormal).1 ≤ 0 then 0
       else mturns d pf fuel (r + 1) (m + mUp d - (absorb (refresh s (d.barrier * scale) r) d.killNormal).1)
         (absorb (refresh s (d.barrier * scale) r) d.killNormal).2) + 1

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

theorem lsum_filter_ne_zero_mul {β : Type} (G : β → Rat) :
    ∀ xs : List (Rat × β),
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
theorem lsum_roll_ge (pct : Nat) (a b c : Int) (g : Rat × Int × Int → Rat) (G : Int → Rat)
    (hg : ∀ x ∈ roll pct a b c, x.1 * G x.2.1 ≤ g x) :
    ((100 - pct : Nat) : Rat) / 100 * G a + ((pct : Nat) : Rat) / 100 * G b
      ≤ lsum g (roll pct a b c) := by
  have he : lsum (fun x => x.1 * G x.2.1) (roll pct a b c)
      = ((100 - pct : Nat) : Rat) / 100 * G a + ((pct : Nat) : Rat) / 100 * G b := by
    unfold roll
    rw [lsum_filter_ne_zero_mul (fun y : Int × Int => G y.1)]
    simp only [lsum, List.map_cons, List.map_nil, List.foldr_cons, List.foldr_nil]
    grind
  rw [← he]
  exact lsum_le _ _ _ hg

/-- A sum over a crit roll whose every branch is worth its weight times `T`. -/
theorem lsum_roll_ge_const (pct : Nat) (h : pct ≤ 100) (a b c : Int) (g : Rat × Int × Int → Rat) (T : Rat)
    (hg : ∀ x ∈ roll pct a b c, x.1 * T ≤ g x) : T ≤ lsum g (roll pct a b c) := by
  have h1 := lsum_roll_ge pct a b c g (fun _ => T) hg
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
    ∀ (fuel : Nat) (r m s x : Int) (c : Nat),
      kpath d pf fuel r m s (x - d.dieCrit) c = true →
      kpath d pf fuel r m s (x - d.dieNormal) (c + 1) = true := by
  intro fuel
  induction fuel with
  | zero => intro r m s x c hw; simp [kpath] at hw
  | succ fuel ih =>
    intro r m s x c hw
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
      by_cases w3 : m + mUp d - (absorb (refresh s (d.barrier * scale) r) d.killNormal).1 ≤ 0
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
        rw [e1] at hw; rw [e2]; exact ih _ _ _ _ _ hw
    · simp only [kpath, if_true] at hw ⊢
      rw [hc1, Nat.add_sub_cancel]
      by_cases w1 : 0 < tick d true r ∧ x - d.dieCrit - tick d true r ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      have g1 : ¬ (0 < tick d true r ∧ x - d.dieNormal - tick d true r ≤ 0) :=
        fun h => w1 ⟨h.1, by omega⟩
      rw [if_neg g1]
      by_cases w3 : m - (absorb s d.killNormal).1 ≤ 0
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
        rw [e1] at hw; rw [e2]; exact ih _ _ _ _ _ hw

/-- A monster turn's heal never exceeds the path's per-turn charge `mUp`. -/
theorem cure_hit_le (d : Damage) {x : Rat × Int × Int}
    (hx : x ∈ roll d.mCrit d.dieNormal d.dieCrit d.mHeal) (m : Int) :
    cure m x.2.2 (d.monsterHp * scale) ≤ m + mUp d := by
  have h := cure_le_up m x.2.2 (d.monsterHp * scale)
  rcases roll_mem hx with ⟨_, h0⟩ | ⟨_, h0⟩ <;> rw [h0] at h ⊢ <;> unfold mUp <;> omega

/-- The hit roll's split of `binom (n + 1) c`: a normal hit keeps the budget, a
crit spends one (`bcrit`). -/
theorem hit_level (d : Damage) (hm100 : d.mCrit ≤ 100)
    (n c : Nat) (f : Rat × Int × Int → List (Rat × Ending))
    (hf : ∀ x ∈ roll d.mCrit d.dieNormal d.dieCrit d.mHeal,
      x.1 * (if x.2.1 ≤ d.dieNormal then binom (critWn d) (critWc d) n c
        else bcrit (critWn d) (critWc d) n c) ≤ winProb (f x)) :
    binom (critWn d) (critWc d) (n + 1) c
      ≤ winProb ((roll d.mCrit d.dieNormal d.dieCrit d.mHeal).flatMap f) := by
  have ⟨h1, hn, hc⟩ := crit_weights d hm100
  rw [winProb_flatMap, binom_succ _ _ h1]
  refine Rat.le_trans ?_ (lsum_roll_ge _ _ _ _ _ (fun h => if h ≤ d.dieNormal then
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
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100) (hB : 0 ≤ d.barrier) :
    ∀ (fuel : Nat) (r m m' s s' p p' : Int) (c : Nat), m ≤ m' → s ≤ s' → 0 ≤ s' → p' ≤ p →
      kpath d pf fuel r m' s' p' c = true →
      binom (critWn d) (critWc d) (mturns d pf fuel r m' s') c
        ≤ winProb (tree d pf maxPool rPool st fuel r m s p 0) := by
  have ⟨h1, hn, hc⟩ := crit_weights d hm100
  have hb0 := binom_nonneg _ _ h1 hn hc
  have hb1 := binom_le_one _ _ h1 hn hc
  have hfull : 0 ≤ d.barrier * scale := Int.mul_nonneg hB (by decide)
  intro fuel
  induction fuel with
  | zero => intro r m m' s s' p p' c _ _ _ _ hw; simp [kpath] at hw
  | succ fuel ih =>
    intro r m m' s s' p p' c hm hs hs0 hp hw
    have hkg := khit_ge d hd c
    cases pf
    · simp only [kpath, Bool.false_eq_true, if_false] at hw
      by_cases w1 : p' - khit d c ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      by_cases w2 : 0 < tick d false r ∧ p' - khit d c - tick d false r ≤ 0
      · rw [if_pos w2] at hw; exact absurd hw (by decide)
      rw [if_neg w2] at hw
      have hrs := refresh_mono (d.barrier * scale) r hs
      have hrs0 := refresh_nonneg (s := s') (full := d.barrier * scale) r hs0 hfull
      have hab := absorb_couple (Int.le_refl d.killNormal) hrs hrs0
      simp only [mturns, Bool.false_eq_true, if_false]
      simp only [tree, Bool.false_eq_true, if_false, Formal.FightOutcome.drink_noStock]
      generalize hn' : (if m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1 ≤ 0
        then 0
        else mturns d false fuel (r + 1)
          (m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1)
          (absorb (refresh s' (d.barrier * scale) r) d.killNormal).2) = n'
      apply hit_level d hm100
      rintro ⟨wh, h, mh⟩ hx
      have hh := roll_mem hx
      have hwh := roll_nonneg hx
      have hcm := cure_hit_le d hx m
      simp only at hh hwh hcm ⊢
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
            (¬ m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1 ≤ 0 →
              kpath d false fuel (r + 1)
                (m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1)
                (absorb (refresh s' (d.barrier * scale) r) d.killNormal).2 P' c'' = true) := by
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
              rw [e1] at hw; rw [e2]; exact kpath_shift d false hd _ _ _ _ _ _ hw
          · have hcpos : 0 < c := hgood.resolve_left hhn
            refine ⟨c - 1, p' - d.dieCrit - tick d false r,
              by rw [if_neg hhn, bcrit, if_neg (by omega)], by omega, ?_⟩
            intro w3; rw [if_neg w3, khit_pos d hcpos] at hw; exact hw
        rw [hV]
        apply lsum_roll_ge_const _ hp100
        rintro ⟨wk, kill, ph⟩ hy
        have hkk := roll_mem hy
        have hwk := roll_nonneg hy
        simp only at hkk hwk ⊢
        have hkill : d.killNormal ≤ kill := by omega
        have hab' := absorb_couple hkill hrs hrs0
        split
        · simp only [winProb_single, if_true]
          have := Rat.mul_le_mul_of_nonneg_left (hb1 n' c'') hwk
          rwa [Rat.mul_one] at this
        · rename_i hmk
          have w3 : ¬ m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1 ≤ 0 := by
            omega
          rw [winProb_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hwk
          have := ih (r + 1) (cure m mh (d.monsterHp * scale)
              - (absorb (refresh s (d.barrier * scale) r) kill).1)
            (m' + mUp d - (absorb (refresh s' (d.barrier * scale) r) d.killNormal).1)
            (absorb (refresh s (d.barrier * scale) r) kill).2
            (absorb (refresh s' (d.barrier * scale) r) d.killNormal).2
            (cure (p - h - tick d false r) ph maxPool) P' c''
            (by omega) hab'.2 (absorb_kept_nonneg _ hrs0) (Int.le_trans hP' (cure_ge _ _ _)) (hkp w3)
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
            rintro ⟨wk, kill, ph⟩ hy
            have hwk := roll_nonneg hy
            simp only at hwk ⊢
            split
            · simp only [winProb_single, if_true]; exact hwk
            · rw [winProb_scaleBy]; exact Rat.mul_nonneg hwk (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _)
    · simp only [kpath, if_true] at hw
      by_cases w1 : 0 < tick d true r ∧ p' - tick d true r ≤ 0
      · rw [if_pos w1] at hw; exact absurd hw (by decide)
      rw [if_neg w1] at hw
      have g0 : ¬ (0 < tick d true r ∧ p - tick d true r ≤ 0) := fun h => w1 ⟨h.1, by omega⟩
      simp only [mturns, if_true]
      simp only [tree, if_true, if_neg g0, Formal.FightOutcome.drink_noStock]
      rw [winProb_flatMap]
      by_cases w3 : m' - (absorb s' d.killNormal).1 ≤ 0
      · rw [if_pos w3, binom_zero]
        apply lsum_roll_ge_const _ hp100
        rintro ⟨wk, kill, ph⟩ hy
        have hkk := roll_mem hy
        have hwk := roll_nonneg hy
        simp only at hkk hwk ⊢
        have hab := absorb_couple (show d.killNormal ≤ kill by omega) hs hs0
        have hmk : m - (absorb s kill).1 ≤ 0 := by omega
        rw [if_pos hmk]
        simp only [winProb_single, if_true, Rat.mul_one]
        exact Rat.le_refl
      rw [if_neg w3] at hw ⊢
      by_cases w4 : p' - tick d true r - khit d c ≤ 0
      · rw [if_pos w4] at hw; exact absurd hw (by decide)
      rw [if_neg w4] at hw
      apply lsum_roll_ge_const _ hp100
      rintro ⟨wk, kill, ph⟩ hy
      have hkk := roll_mem hy
      have hwk := roll_nonneg hy
      simp only at hkk hwk ⊢
      have hab := absorb_couple (show d.killNormal ≤ kill by omega) hs hs0
      split
      · simp only [winProb_single, if_true]
        have := Rat.mul_le_mul_of_nonneg_left
          (hb1 (mturns d true fuel (r + 1) (m' - (absorb s' d.killNormal).1 + mUp d)
            (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r) + 1) c) hwk
        rwa [Rat.mul_one] at this
      · rename_i hmk
        rw [winProb_scaleBy]
        apply Rat.mul_le_mul_of_nonneg_left _ hwk
        apply hit_level d hm100
        rintro ⟨wh, h, mh⟩ hx
        have hh := roll_mem hx
        have hwh := roll_nonneg hx
        have hcm := cure_hit_le d hx (m - (absorb s kill).1)
        have hcp := cure_ge (p - tick d true r) ph maxPool
        simp only at hh hwh hcm ⊢
        by_cases hgood : h ≤ d.dieNormal ∨ 0 < c
        · have hle : h ≤ khit d c := by
            rcases hgood with hg | hg
            · omega
            · rw [khit_pos d hg]; omega
          have g1 : ¬ cure (p - tick d true r) ph maxPool - h ≤ 0 := by omega
          rw [if_neg g1, winProb_scaleBy]
          apply Rat.mul_le_mul_of_nonneg_left _ hwh
          obtain ⟨c'', P', hV, hP', hkp⟩ : ∃ (c'' : Nat) (P' : Int),
              (if h ≤ d.dieNormal then
                  binom (critWn d) (critWc d) (mturns d true fuel (r + 1)
                    (m' - (absorb s' d.killNormal).1 + mUp d)
                    (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r)) c
                else bcrit (critWn d) (critWc d) (mturns d true fuel (r + 1)
                    (m' - (absorb s' d.killNormal).1 + mUp d)
                    (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r)) c)
                = binom (critWn d) (critWc d) (mturns d true fuel (r + 1)
                    (m' - (absorb s' d.killNormal).1 + mUp d)
                    (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r)) c'' ∧
              P' ≤ p - tick d true r - h ∧
              kpath d true fuel (r + 1) (m' - (absorb s' d.killNormal).1 + mUp d)
                (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r) P' c'' = true := by
            by_cases hhn : h ≤ d.dieNormal
            · refine ⟨c, p' - tick d true r - d.dieNormal, by rw [if_pos hhn], by omega, ?_⟩
              cases c with
              | zero => rw [khit_zero] at hw; exact hw
              | succ c =>
                rw [khit_pos d (by omega), Nat.add_sub_cancel] at hw
                exact kpath_shift d true hd _ _ _ _ _ _ hw
            · have hcpos : 0 < c := hgood.resolve_left hhn
              refine ⟨c - 1, p' - tick d true r - d.dieCrit,
                by rw [if_neg hhn, bcrit, if_neg (by omega)], by omega, ?_⟩
              rw [khit_pos d hcpos] at hw; exact hw
          rw [hV]
          exact ih (r + 1) (cure (m - (absorb s kill).1) mh (d.monsterHp * scale))
            (m' - (absorb s' d.killNormal).1 + mUp d)
            (refresh (absorb s kill).2 (d.barrier * scale) r)
            (refresh (absorb s' d.killNormal).2 (d.barrier * scale) r)
            (cure (p - tick d true r) ph maxPool - h) P' c'' (by omega)
            (refresh_mono _ r hab.2) (refresh_nonneg r (absorb_kept_nonneg _ hs0) hfull)
            (by omega) hkp
        · have hc0 : c = 0 := by omega
          have hhn : ¬ h ≤ d.dieNormal := fun h' => hgood (Or.inl h')
          rw [if_neg hhn, bcrit, if_pos hc0, Rat.mul_zero]
          split
          · simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl
          · rw [winProb_scaleBy]; exact Rat.mul_nonneg hwh (tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _)

/-- The proved P(win) floor of a fight at no stock (see `winProb_ge_critBound`):
if the counted-crit path from the fight's start with budget `c` wins, every path
with at most `c` monster crits wins, so P(win) is at least P(at most `c` of the
path's `mturns` monster turns crit). Follows `fightOdds`' gate. -/
def critBound (t : Terms) (d : Damage) (hp maxHp : Int) (c : Nat) : Rat :=
  match gate t with
  | .outSustain => 1
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then 0
    else if kpath d t.playerFirst maxTurns.toNat 1 (d.monsterHp * scale) (d.barrier * scale)
      (effHp hp maxHp * scale) c
    then binom (critWn d) (critWc d)
      (mturns d t.playerFirst maxTurns.toNat 1 (d.monsterHp * scale) (d.barrier * scale)) c
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
    (hp100 : d.pCrit ≤ 100) (hm100 : d.mCrit ≤ 100) (hB : 0 ≤ d.barrier) :
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
        exact tree_critBound d _ _ _ 0 hk hd hp100 hm100 hB _ _ _ _ _ _ _ _ _
          (Int.le_refl _) (Int.le_refl _) (Int.mul_nonneg hB (by decide)) (Int.le_refl _) hw
      · exact tree_wp_nonneg _ _ _ _ _ _ _ _ _ _ _
  all_goals simp only [winProb_single, Bool.false_eq_true, if_false]; exact Rat.le_refl

end Formal.FightOdds
