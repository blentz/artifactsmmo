-- @concept: combat, consumables @property: validity, monotonicity, boundedness
/-
A fight's expected-value outcome with in-fight restore potions
(`docs/PLAN_consumable_utility.md` increment 1;
`src/artifactsmmo_cli/ai/fight_terms_core.py`,
`src/artifactsmmo_cli/ai/fight_outcome_core.py`).

## The terms

`Terms` are the closed form's resolved integers: the player's raw damage, the
net per-round kill step and die step (×10000, `PredictWin.killStepNet` /
`PredictWin.dieStep`), the effective monster HP (barrier included), the
reconstitution period and the initiative tiebreak. `gate` is the closed form's
guard ladder over the monster side; `exitOf` adds the player's starting HP;
`closedWin` is the closed-form verdict over them. `closedWin_eq_predictWin`
ties it to `Formal.PredictWin.predictWin` (which models the player at full HP).

## The walk

The API's rule for a `restore` utility potion: "Restores X HP at the start of
the turn if the player has lost more than 50% of their health points". In the
×10000 scale: at the start of each player turn, if `2 * pool < maxHp * 10000`
and stock remains, `pool := min (pool + restore * 10000) (maxHp * 10000)` and
one potion is spent. The kill round is `roundsToKill` whatever the player's
HP, so the walk counts rounds; each monster turn removes `dieStep`, and the
pool reaching 0 loses the fight. The first mover acts first in every round.

## Results

* `fightOutcome_noStock_win` — with no stock the walk's verdict IS the closed form's.
* `used_le_stock`, `walk_left_le` — no more potions are drunk than held.
* `hpEnd_le_max` — the pool never exceeds max HP (hypothesis `0 ≤ maxHp`).
* `stock_mono` — more stock never turns a win into a loss, never lowers the
  ending HP and never shortens the fight.
* `turns_le_roundsToKill`, `win_turns_stock_indep` — a restore never lengthens
  a fight past the closed form's kill round, and a won fight takes the same
  number of rounds whatever the stock. (The literal "a restore never raises the
  turn count" is FALSE: a restore can turn a round-2 loss into a round-5 win.)

Lean core only — no Mathlib.
-/
import Formal.PredictWin

namespace Formal.FightOutcome

open Formal.PredictWin (ceilDiv maxTurns killStepNet dieStep predictWin ceilDiv_mul_ge
  ceilDiv_pred_mul_lt ceilDiv_pos)

/-- The ×10000 scale of the per-round steps. -/
def scale : Int := 10000

/-- The guard of the closed-form ladder that decided a fight, in ladder order. -/
inductive Exit where
  | none | noDamage | unkillable | overCap | reconstituted | outSustain | dead
  deriving DecidableEq, Repr

/-- The closed form's resolved integers for one fight. -/
structure Terms where
  rawPlayer : Int
  killStep : Int
  monsterHp : Int
  recon : Int
  dieStep : Int
  playerFirst : Bool

def roundsToKill (t : Terms) : Int := ceilDiv (t.monsterHp * scale) t.killStep

/-- Player HP at fight start: current HP capped at max, or 0 if already dead. -/
def effHp (hp maxHp : Int) : Int := if 0 < hp then min hp maxHp else 0

/-- The monster-side guard ladder (everything the closed form tests before the
player's HP). -/
def gate (t : Terms) : Exit :=
  if t.rawPlayer ≤ 0 then .noDamage
  else if t.killStep ≤ 0 then .unkillable
  else if roundsToKill t > maxTurns then .overCap
  else if 0 < t.recon ∧ t.recon ≤ roundsToKill t then .reconstituted
  else if t.dieStep ≤ 0 then .outSustain
  else .none

/-- The full ladder: `gate`, then a fight that starts dead is lost. -/
def exitOf (t : Terms) (hp maxHp : Int) : Exit :=
  match gate t with
  | .none => if effHp hp maxHp ≤ 0 then .dead else .none
  | e => e

/-- The closed-form verdict over the terms (`fight_terms_core.terms_win`). -/
def closedWin (t : Terms) (hp maxHp : Int) : Bool :=
  match exitOf t hp maxHp with
  | .outSustain => true
  | .none =>
    if t.playerFirst then decide (roundsToKill t ≤ ceilDiv (effHp hp maxHp * scale) t.dieStep)
    else decide (roundsToKill t < ceilDiv (effHp hp maxHp * scale) t.dieStep)
  | _ => false

/-- The restore rule at the start of a player turn: below half, drink one. -/
def drink (pool maxPool rPool : Int) (k : Nat) : Int × Nat :=
  if 2 * pool < maxPool ∧ 0 < k then (min (pool + rPool) maxPool, k - 1) else (pool, k)

/-- The walk's result: verdict, resolving round, ending pool, stock left. -/
structure Walk where
  win : Bool
  turns : Int
  pool : Int
  left : Nat

/-- The fight from round `r` with `n` rounds left until the kill. -/
def walk (pf : Bool) (ds maxPool rPool : Int) : Nat → Int → Int → Nat → Walk
  | 0, r, pool, k => ⟨true, r - 1, pool, k⟩
  | n + 1, r, pool, k =>
    if pf then
      if n = 0 then ⟨true, r, (drink pool maxPool rPool k).1, (drink pool maxPool rPool k).2⟩
      else if (drink pool maxPool rPool k).1 - ds ≤ 0 then
        ⟨false, r, 0, (drink pool maxPool rPool k).2⟩
      else walk pf ds maxPool rPool n (r + 1) ((drink pool maxPool rPool k).1 - ds)
        (drink pool maxPool rPool k).2
    else
      if pool - ds ≤ 0 then ⟨false, r, 0, k⟩
      else if n = 0 then
        ⟨true, r, (drink (pool - ds) maxPool rPool k).1, (drink (pool - ds) maxPool rPool k).2⟩
      else walk pf ds maxPool rPool n (r + 1) (drink (pool - ds) maxPool rPool k).1
        (drink (pool - ds) maxPool rPool k).2

/-- One fight's expected-value outcome (`hpEnd` in the ×10000 scale). -/
structure Outcome where
  win : Bool
  turns : Int
  hpEnd : Int
  used : Nat

/-- `fight_outcome_core.fight_outcome`. -/
def fightOutcome (t : Terms) (hp maxHp : Int) (restore stock : Nat) : Outcome :=
  match gate t with
  | .outSustain => ⟨true, roundsToKill t, effHp hp maxHp * scale, 0⟩
  | .none =>
    if effHp hp maxHp * scale ≤ 0 then ⟨false, 0, 0, 0⟩
    else
      let w := walk t.playerFirst t.dieStep (maxHp * scale) ((restore : Int) * scale)
        (roundsToKill t).toNat 1 (effHp hp maxHp * scale) stock
      ⟨w.win, w.turns, w.pool, stock - w.left⟩
  | _ => ⟨false, 0, 0, 0⟩

/-! ### Helpers. -/

theorem gate_none_dieStep (t : Terms) (h : gate t = .none) : 0 < t.dieStep := by
  unfold gate at h
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> try contradiction
  split at h <;> first | contradiction | omega

theorem drink_noStock (pool maxPool rPool : Int) :
    drink pool maxPool rPool 0 = (pool, 0) := by
  simp [drink]

theorem drink_left_le (pool maxPool rPool : Int) (k : Nat) :
    (drink pool maxPool rPool k).2 ≤ k := by
  unfold drink; split <;> simp <;> omega

theorem drink_le_max (pool maxPool rPool : Int) (k : Nat) (h : pool ≤ maxPool) :
    (drink pool maxPool rPool k).1 ≤ maxPool := by
  unfold drink; split
  · exact Int.min_le_right _ _
  · exact h

theorem drink_ge (pool maxPool rPool : Int) (k : Nat) (hr : 0 ≤ rPool) (h : pool ≤ maxPool) :
    pool ≤ (drink pool maxPool rPool k).1 := by
  unfold drink; split
  · simp only
    rw [Int.min_def]; split <;> omega
  · exact Int.le_refl _

/-- `m * d < N ↔ m < ⌈N / d⌉` for a positive divisor and `N ≥ 1`. -/
theorem mul_lt_iff_lt_ceilDiv (m N d : Int) (hd : 0 < d) (hN : 1 ≤ N) :
    m * d < N ↔ m < ceilDiv N d := by
  have hge := ceilDiv_mul_ge N d hd (by omega)
  have hlt := ceilDiv_pred_mul_lt N d hd hN
  constructor
  · intro h
    refine Int.not_le.mp fun hc => ?_
    have : ceilDiv N d * d ≤ m * d := Int.mul_le_mul_of_nonneg_right hc (Int.le_of_lt hd)
    omega
  · intro h
    have hm : m ≤ ceilDiv N d - 1 := by omega
    have : m * d ≤ (ceilDiv N d - 1) * d := Int.mul_le_mul_of_nonneg_right hm (Int.le_of_lt hd)
    omega

theorem succ_mul (n : Nat) (d : Int) : ((n + 1 : Nat) : Int) * d = (n : Int) * d + d := by
  rw [Int.natCast_add, Int.add_mul, Int.natCast_one, Int.one_mul]

/-! ### (a) With no stock the walk is the closed form. -/

theorem walk_noStock_first (ds maxPool rPool : Int) (hds : 0 < ds) :
    ∀ (n : Nat) (r pool : Int), 0 < pool →
      (walk true ds maxPool rPool (n + 1) r pool 0).win = decide ((n : Int) * ds < pool) := by
  intro n
  induction n with
  | zero => intro r pool hp; simp [walk, drink_noStock, hp]
  | succ n ih =>
    intro r pool hp
    have hx : 0 ≤ (n : Int) * ds := Int.mul_nonneg (Int.natCast_nonneg n) (Int.le_of_lt hds)
    have hs := succ_mul n ds
    rw [walk]
    simp only [drink_noStock, if_true]
    rw [if_neg (Nat.succ_ne_zero n)]
    split
    · simp only [Bool.false_eq, decide_eq_false_iff_not]; omega
    · rw [ih (r + 1) (pool - ds) (by omega)]
      simp only [decide_eq_decide]; omega

theorem walk_noStock_second (ds maxPool rPool : Int) (hds : 0 < ds) :
    ∀ (n : Nat) (r pool : Int),
      (walk false ds maxPool rPool (n + 1) r pool 0).win
        = decide (((n : Int) + 1) * ds < pool) := by
  intro n
  induction n with
  | zero =>
    intro r pool
    simp only [walk, drink_noStock, Bool.false_eq_true, if_false, if_true]
    split
    · simp; omega
    · simp; omega
  | succ n ih =>
    intro r pool
    have hx : 0 ≤ ((n : Int) + 1) * ds :=
      Int.mul_nonneg (by omega) (Int.le_of_lt hds)
    have hs : ((n : Int) + 1 + 1) * ds = ((n : Int) + 1) * ds + ds := by
      rw [Int.add_mul, Int.one_mul]
    rw [walk]
    simp only [drink_noStock, Bool.false_eq_true, if_false]
    split
    · simp only [Bool.false_eq, decide_eq_false_iff_not]; push_cast; omega
    · rw [if_neg (Nat.succ_ne_zero n), ih (r + 1) (pool - ds)]
      simp only [decide_eq_decide]; push_cast; omega

/-- (a) With no stock the walk's verdict is the closed-form verdict. -/
theorem fightOutcome_noStock_win (t : Terms) (hp maxHp : Int) (restore : Nat) :
    (fightOutcome t hp maxHp restore 0).win = closedWin t hp maxHp := by
  unfold fightOutcome closedWin exitOf
  cases hg : gate t with
  | none =>
    have hds := gate_none_dieStep t hg
    simp only
    have hsc : (0 : Int) < scale := by decide
    by_cases he : effHp hp maxHp ≤ 0
    · have : effHp hp maxHp * scale ≤ 0 :=
        Int.mul_nonpos_of_nonpos_of_nonneg he (Int.le_of_lt hsc)
      simp [he, this]
    · have hpos : 0 < effHp hp maxHp * scale := Int.mul_pos (by omega) hsc
      simp only [he, if_false, Int.not_le.mpr hpos]
      have hN : 1 ≤ effHp hp maxHp * scale := hpos
      have hrtd := ceilDiv_pos (effHp hp maxHp * scale) t.dieStep hds hN
      by_cases hk : roundsToKill t ≤ 0
      · have h0 : (roundsToKill t).toNat = 0 := Int.toNat_of_nonpos hk
        rw [h0]
        cases t.playerFirst <;> simp [walk] <;> omega
      · obtain ⟨m, hm⟩ : ∃ m : Nat, (roundsToKill t).toNat = m + 1 :=
          ⟨(roundsToKill t).toNat - 1, by omega⟩
        have hmi : roundsToKill t = (m : Int) + 1 := by omega
        rw [hm]
        cases hpf : t.playerFirst
        · rw [walk_noStock_second _ _ _ hds]
          simp only [Bool.false_eq_true, if_false, decide_eq_decide, hmi]
          exact mul_lt_iff_lt_ceilDiv _ _ _ hds hN
        · rw [walk_noStock_first _ _ _ hds m 1 _ hpos]
          simp only [if_true, decide_eq_decide, hmi]
          rw [mul_lt_iff_lt_ceilDiv _ _ _ hds hN]; omega
  | _ => rfl

/-- The closed form over the terms IS `Formal.PredictWin.predictWin` (which
models the player at full HP): the extracted terms reproduce the verdict. -/
theorem closedWin_eq_predictWin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier monsterBurn
    monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy
    monsterBubble playerAntipoison monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool) (hmax : 1 ≤ playerMaxHp) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier monsterBurn
      monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy
      monsterBubble playerAntipoison monsterSunShield monsterGreed monsterEnchantedMirror
      playerFirst
    = closedWin ⟨rawPlayer,
        killStepNet rawPlayer pCrit mCrit mLifesteal mAtkSum monsterHp monsterHealing
          playerMaxHp monsterVoidDrain monsterBubble monsterSunShield,
        monsterHp + monsterBarrier, monsterReconstitution,
        dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison monsterBurn
          playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison
          rawPlayer monsterGreed monsterEnchantedMirror,
        playerFirst⟩ playerMaxHp playerMaxHp := by
  have heff : effHp playerMaxHp playerMaxHp = playerMaxHp := by
    simp [effHp, show 0 < playerMaxHp by omega]
  unfold predictWin closedWin exitOf gate roundsToKill
  simp only [heff, scale]
  generalize killStepNet rawPlayer pCrit mCrit mLifesteal mAtkSum monsterHp monsterHealing
    playerMaxHp monsterVoidDrain monsterBubble monsterSunShield = ks
  generalize dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison monsterBurn
    playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison
    rawPlayer monsterGreed monsterEnchantedMirror = ds
  by_cases h1 : rawPlayer ≤ 0
  · simp [h1]
  by_cases h2 : ks ≤ 0
  · simp [h1, h2]
  generalize ceilDiv ((monsterHp + monsterBarrier) * 10000) ks = rtk
  by_cases h3 : rtk > maxTurns
  · simp [h1, h2, h3]
  by_cases h4 : 0 < monsterReconstitution ∧ monsterReconstitution ≤ rtk
  · simp [h1, h2, h3, h4]
  by_cases h5 : ds ≤ 0
  · simp [h1, h2, h3, h4, h5]
  have h6 : ¬ playerMaxHp ≤ 0 := by omega
  cases playerFirst <;> simp [h1, h2, h3, h4, h5, h6]

/-! ### (b) No more potions are drunk than held. -/

theorem walk_left_le (pf : Bool) (ds maxPool rPool : Int) :
    ∀ (n : Nat) (r pool : Int) (k : Nat), (walk pf ds maxPool rPool n r pool k).left ≤ k := by
  intro n
  induction n with
  | zero => intro r pool k; simp [walk]
  | succ n ih =>
    intro r pool k
    unfold walk
    cases pf <;> simp only [Bool.false_eq_true, if_false, if_true]
    · split
      · simp
      · split
        · exact drink_left_le _ _ _ _
        · exact Nat.le_trans (ih _ _ _) (drink_left_le _ _ _ _)
    · split
      · exact drink_left_le _ _ _ _
      · split
        · exact drink_left_le _ _ _ _
        · exact Nat.le_trans (ih _ _ _) (drink_left_le _ _ _ _)

/-- (b) The potions used never exceed the stock. -/
theorem used_le_stock (t : Terms) (hp maxHp : Int) (restore stock : Nat) :
    (fightOutcome t hp maxHp restore stock).used ≤ stock := by
  unfold fightOutcome
  split
  · exact Nat.zero_le _
  · split
    · exact Nat.zero_le _
    · exact Nat.sub_le _ _
  · exact Nat.zero_le _

/-! ### (c) The ending HP never exceeds max HP. -/

theorem walk_pool_le (pf : Bool) (ds maxPool rPool : Int) (hds : 0 ≤ ds) (hmp : 0 ≤ maxPool) :
    ∀ (n : Nat) (r pool : Int) (k : Nat), pool ≤ maxPool →
      (walk pf ds maxPool rPool n r pool k).pool ≤ maxPool := by
  intro n
  induction n with
  | zero => intro r pool k h; simpa [walk] using h
  | succ n ih =>
    intro r pool k h
    unfold walk
    cases pf <;> simp only [Bool.false_eq_true, if_false, if_true]
    · split
      · simpa using hmp
      · split
        · exact drink_le_max _ _ _ _ (by omega)
        · exact ih _ _ _ (drink_le_max _ _ _ _ (by omega))
    · split
      · exact drink_le_max _ _ _ _ h
      · split
        · simpa using hmp
        · have := drink_le_max pool maxPool rPool k h
          exact ih _ _ _ (by omega)

theorem effHp_le (hp maxHp : Int) (h : 0 ≤ maxHp) : effHp hp maxHp ≤ maxHp := by
  unfold effHp; split
  · exact Int.min_le_right _ _
  · exact h

/-- (c) The ending pool never exceeds max HP (×10000). -/
theorem hpEnd_le_max (t : Terms) (hp maxHp : Int) (restore stock : Nat) (hmax : 0 ≤ maxHp) :
    (fightOutcome t hp maxHp restore stock).hpEnd ≤ maxHp * scale := by
  have hsc : (0 : Int) ≤ scale := by decide
  have hle : effHp hp maxHp * scale ≤ maxHp * scale :=
    Int.mul_le_mul_of_nonneg_right (effHp_le hp maxHp hmax) hsc
  have hmp : 0 ≤ maxHp * scale := Int.mul_nonneg hmax hsc
  unfold fightOutcome
  cases hg : gate t with
  | none =>
    simp only
    split
    · exact hmp
    · exact walk_pool_le _ _ _ _ (Int.le_of_lt (gate_none_dieStep t hg)) hmp _ _ _ _ hle
  | outSustain => exact hle
  | _ => exact hmp

/-! ### (d) More stock never hurts. -/

/-- The coupling between a walk with less stock and one with more: identical so
far with no less stock, or the poorer one is dry and no healthier. -/
def coupled (p : Int) (k : Nat) (p' : Int) (k' : Nat) : Prop :=
  (p = p' ∧ k ≤ k') ∨ (k = 0 ∧ p ≤ p')

theorem drink_coupled (maxPool rPool : Int) (hr : 0 ≤ rPool) (p p' : Int) (k k' : Nat)
    (hc : coupled p k p' k') (hp : p ≤ maxPool) (hp' : p' ≤ maxPool) :
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
        refine ⟨by simp [drink], ?_⟩
        rw [drink_noStock]
        exact drink_ge _ _ _ _ hr hp
    · left
      simp [drink, hc]; exact hk
  · right
    refine ⟨by simp [drink], ?_⟩
    rw [drink_noStock]
    exact Int.le_trans hle (drink_ge _ _ _ _ hr hp')

theorem walk_turns_ge (pf : Bool) (ds maxPool rPool : Int) :
    ∀ (n : Nat) (r pool : Int) (k : Nat),
      r ≤ (walk pf ds maxPool rPool (n + 1) r pool k).turns := by
  intro n
  induction n with
  | zero =>
    intro r pool k
    cases pf
    · rw [walk]; simp only [Bool.false_eq_true, if_false]
      split
      · exact Int.le_refl _
      · simp
    · rw [walk]; simp
  | succ n ih =>
    intro r pool k
    cases pf
    · rw [walk]; simp only [Bool.false_eq_true, if_false]
      rw [if_neg (Nat.succ_ne_zero n)]
      split
      · exact Int.le_refl _
      · have := ih (r + 1) (drink (pool - ds) maxPool rPool k).1 (drink (pool - ds) maxPool rPool k).2
        omega
    · rw [walk]; simp only [if_true]
      rw [if_neg (Nat.succ_ne_zero n)]
      split
      · exact Int.le_refl _
      · have := ih (r + 1) ((drink pool maxPool rPool k).1 - ds) (drink pool maxPool rPool k).2
        omega

theorem walk_pool_nonneg (pf : Bool) (ds maxPool rPool : Int) (hds : 0 < ds) (hr : 0 ≤ rPool) :
    ∀ (n : Nat) (r pool : Int) (k : Nat), 0 < pool → pool ≤ maxPool →
      0 ≤ (walk pf ds maxPool rPool n r pool k).pool := by
  intro n
  induction n with
  | zero => intro r pool k hp _; simp [walk]; omega
  | succ n ih =>
    intro r pool k hp hm
    cases pf
    · rw [walk]; simp only [Bool.false_eq_true, if_false]
      split
      · simp
      · have hg := drink_ge (pool - ds) maxPool rPool k hr (by omega)
        have hm' := drink_le_max (pool - ds) maxPool rPool k (by omega)
        split
        · simp only; omega
        · exact ih _ _ _ (by omega) hm'
    · rw [walk]; simp only [if_true]
      have hg := drink_ge pool maxPool rPool k hr hm
      have hm' := drink_le_max pool maxPool rPool k hm
      split
      · simp only; omega
      · split
        · simp
        · exact ih _ _ _ (by omega) (by omega)

theorem coupled_le {p p' : Int} {k k' : Nat} (hc : coupled p k p' k') : p ≤ p' := by
  rcases hc with ⟨h, _⟩ | ⟨_, h⟩ <;> omega

theorem coupled_sub {p p' : Int} {k k' : Nat} (ds : Int) (hc : coupled p k p' k') :
    coupled (p - ds) k (p' - ds) k' := by
  rcases hc with ⟨h1, h2⟩ | ⟨h1, h2⟩
  · left; exact ⟨by omega, h2⟩
  · right; exact ⟨h1, by omega⟩

/-- The coupled walks: the poorer one's win implies the richer one's, and the
richer one ends no lower and no sooner. -/
theorem walk_mono (pf : Bool) (ds maxPool rPool : Int) (hds : 0 < ds) (hr : 0 ≤ rPool) :
    ∀ (n : Nat) (r p p' : Int) (k k' : Nat), 0 < p → coupled p k p' k' →
      p ≤ maxPool → p' ≤ maxPool →
      ((walk pf ds maxPool rPool n r p k).win = true →
          (walk pf ds maxPool rPool n r p' k').win = true)
        ∧ (walk pf ds maxPool rPool n r p k).pool ≤ (walk pf ds maxPool rPool n r p' k').pool
        ∧ (walk pf ds maxPool rPool n r p k).turns
            ≤ (walk pf ds maxPool rPool n r p' k').turns := by
  intro n
  induction n with
  | zero =>
    intro r p p' k k' _ hc _ _
    have hpp := coupled_le hc
    simp [walk, hpp]
  | succ n ih =>
    intro r p p' k k' hpos hc hp hp'
    have hpp := coupled_le hc
    cases pf with
    | true =>
      have hd := drink_coupled maxPool rPool hr p p' k k' hc hp hp'
      have hdd := coupled_le hd
      have hg := drink_ge p maxPool rPool k hr hp
      have hm := drink_le_max p maxPool rPool k hp
      have hm' := drink_le_max p' maxPool rPool k' hp'
      rw [walk, walk]
      simp only [if_true]
      by_cases hn : n = 0
      · simp only [hn, if_true]; exact ⟨fun h => h, hdd, Int.le_refl _⟩
      · simp only [hn, if_false]
        obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by omega⟩
        by_cases hl : (drink p' maxPool rPool k').1 - ds ≤ 0
        · have hl0 : (drink p maxPool rPool k).1 - ds ≤ 0 := by omega
          simp only [hl, hl0, if_true]
          exact ⟨fun h => h, Int.le_refl _, Int.le_refl _⟩
        · simp only [hl, if_false]
          by_cases hl0 : (drink p maxPool rPool k).1 - ds ≤ 0
          · simp only [hl0, if_true]
            have ht := walk_turns_ge true ds maxPool rPool m (r + 1)
              ((drink p' maxPool rPool k').1 - ds) (drink p' maxPool rPool k').2
            have hn0 := walk_pool_nonneg true ds maxPool rPool hds hr (m + 1) (r + 1)
              ((drink p' maxPool rPool k').1 - ds) (drink p' maxPool rPool k').2
              (by omega) (by omega)
            refine ⟨fun h => by simp at h, hn0, by omega⟩
          · simp only [hl0, if_false]
            exact ih _ _ _ _ _ (by omega) (coupled_sub ds hd) (by omega) (by omega)
    | false =>
      rw [walk, walk]
      simp only [Bool.false_eq_true, if_false]
      by_cases hl : p' - ds ≤ 0
      · have hl0 : p - ds ≤ 0 := by omega
        simp only [hl, hl0, if_true]
        exact ⟨fun h => h, Int.le_refl _, Int.le_refl _⟩
      · simp only [hl, if_false]
        have hd := drink_coupled maxPool rPool hr (p - ds) (p' - ds) k k'
          (coupled_sub ds hc) (by omega) (by omega)
        have hdd := coupled_le hd
        have hm := drink_le_max (p - ds) maxPool rPool k (by omega)
        have hm' := drink_le_max (p' - ds) maxPool rPool k' (by omega)
        have hg' := drink_ge (p' - ds) maxPool rPool k' hr (by omega)
        by_cases hl0 : p - ds ≤ 0
        · simp only [hl0, if_true]
          by_cases hn : n = 0
          · simp only [hn, if_true]
            refine ⟨fun h => by simp at h, by omega, Int.le_refl _⟩
          · simp only [hn, if_false]
            obtain ⟨m, rfl⟩ : ∃ m, n = m + 1 := ⟨n - 1, by omega⟩
            have ht := walk_turns_ge false ds maxPool rPool m (r + 1)
              (drink (p' - ds) maxPool rPool k').1 (drink (p' - ds) maxPool rPool k').2
            have hn0 := walk_pool_nonneg false ds maxPool rPool hds hr (m + 1) (r + 1)
              (drink (p' - ds) maxPool rPool k').1 (drink (p' - ds) maxPool rPool k').2
              (by omega) hm'
            refine ⟨fun h => by simp at h, hn0, by omega⟩
        · simp only [hl0, if_false]
          have hg := drink_ge (p - ds) maxPool rPool k hr (by omega)
          by_cases hn : n = 0
          · simp only [hn, if_true]; exact ⟨fun h => h, hdd, Int.le_refl _⟩
          · simp only [hn, if_false]
            exact ih _ _ _ _ _ (by omega) hd hm hm'

/-- (d) More stock never turns a win into a loss, never lowers the ending HP
and never shortens the fight. -/
theorem stock_mono (t : Terms) (hp maxHp : Int) (restore s s' : Nat) (hs : s ≤ s') :
    ((fightOutcome t hp maxHp restore s).win = true →
        (fightOutcome t hp maxHp restore s').win = true)
      ∧ (fightOutcome t hp maxHp restore s).hpEnd ≤ (fightOutcome t hp maxHp restore s').hpEnd
      ∧ (fightOutcome t hp maxHp restore s).turns
          ≤ (fightOutcome t hp maxHp restore s').turns := by
  unfold fightOutcome
  cases hg : gate t with
  | none =>
    simp only
    split
    · exact ⟨fun h => h, Int.le_refl _, Int.le_refl _⟩
    · rename_i hpos
      have hp0 : 0 < effHp hp maxHp * scale := by omega
      have hle : effHp hp maxHp * scale ≤ maxHp * scale := by
        have hh : 0 < hp := by
          unfold effHp at hp0; split at hp0
          · assumption
          · simp at hp0
        have : effHp hp maxHp ≤ maxHp := by
          unfold effHp; rw [if_pos hh]; exact Int.min_le_right _ _
        exact Int.mul_le_mul_of_nonneg_right this (by decide)
      exact walk_mono _ _ _ _ (gate_none_dieStep t hg)
        (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) _ _ _ _ _ _ hp0
        (Or.inl ⟨rfl, hs⟩) hle hle
  | _ => exact ⟨fun h => h, Int.le_refl _, Int.le_refl _⟩

/-! ### (e) A restore never lengthens a fight past the kill round. -/

theorem walk_turns_le (pf : Bool) (ds maxPool rPool : Int) :
    ∀ (n : Nat) (r pool : Int) (k : Nat),
      (walk pf ds maxPool rPool n r pool k).turns ≤ r + n - 1 := by
  intro n
  induction n with
  | zero => intro r pool k; simp [walk]
  | succ n ih =>
    intro r pool k
    cases pf
    · rw [walk]; simp only [Bool.false_eq_true, if_false]
      split
      · simp only; omega
      · split
        · simp only; omega
        · have := ih (r + 1) (drink (pool - ds) maxPool rPool k).1
            (drink (pool - ds) maxPool rPool k).2
          omega
    · rw [walk]; simp only [if_true]
      split
      · simp only; omega
      · split
        · simp only; omega
        · have := ih (r + 1) ((drink pool maxPool rPool k).1 - ds) (drink pool maxPool rPool k).2
          omega

theorem walk_win_turns (pf : Bool) (ds maxPool rPool : Int) :
    ∀ (n : Nat) (r pool : Int) (k : Nat), (walk pf ds maxPool rPool n r pool k).win = true →
      (walk pf ds maxPool rPool n r pool k).turns = r + n - 1 := by
  intro n
  induction n with
  | zero => intro r pool k _; simp [walk]
  | succ n ih =>
    intro r pool k hw
    cases pf
    · rw [walk] at hw ⊢; simp only [Bool.false_eq_true, if_false] at hw ⊢
      split at hw
      · simp at hw
      · rename_i h1
        rw [if_neg h1]
        split at hw
        · rename_i h2; rw [if_pos h2]; simp only; omega
        · rename_i h2; rw [if_neg h2]
          have := ih _ _ _ hw
          omega
    · rw [walk] at hw ⊢; simp only [if_true] at hw ⊢
      split at hw
      · rename_i h1; rw [if_pos h1]; simp only; omega
      · rename_i h1; rw [if_neg h1]
        split at hw
        · simp at hw
        · rename_i h2; rw [if_neg h2]
          have := ih _ _ _ hw
          omega

/-- (e) The fight never runs past the closed form's kill round, whatever the stock. -/
theorem turns_le_roundsToKill (t : Terms) (hp maxHp : Int) (restore stock : Nat) :
    (fightOutcome t hp maxHp restore stock).turns ≤ (roundsToKill t).toNat := by
  unfold fightOutcome
  cases hg : gate t with
  | none =>
    simp only
    split
    · simp only; omega
    · have := walk_turns_le t.playerFirst t.dieStep (maxHp * scale) ((restore : Int) * scale)
        (roundsToKill t).toNat 1 (effHp hp maxHp * scale) stock
      simp only; omega
  | outSustain => simp only; omega
  | _ => simp only; omega

/-- (e) A won fight takes the same number of rounds whatever the stock: a
restore buys survival, never a longer or shorter win. -/
theorem win_turns_stock_indep (t : Terms) (hp maxHp : Int) (restore s s' : Nat)
    (hw : (fightOutcome t hp maxHp restore s).win = true)
    (hw' : (fightOutcome t hp maxHp restore s').win = true) :
    (fightOutcome t hp maxHp restore s).turns = (fightOutcome t hp maxHp restore s').turns := by
  unfold fightOutcome at hw hw' ⊢
  cases hg : gate t with
  | none =>
    rw [hg] at hw hw'
    simp only at hw hw' ⊢
    split at hw
    · simp at hw
    · rename_i h
      simp only [h, if_false] at hw' ⊢
      rw [walk_win_turns _ _ _ _ _ _ _ _ hw, walk_win_turns _ _ _ _ _ _ _ _ hw']
  | outSustain => rfl
  | _ => simp [hg] at hw

end Formal.FightOutcome
