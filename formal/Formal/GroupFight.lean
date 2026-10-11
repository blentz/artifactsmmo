-- @concept: combat @property: validity, monotonicity, safety
/-
A party boss fight's expected-value outcome (`docs/PLAN_group_fights.md`
increment 1; `src/artifactsmmo_cli/ai/group_fight_core.py`).

## The inputs

A `Member` carries its share of the kill rate (`net`), what one monster hit
costs it (`hit`), what every round costs it targeted or not (`area`), its HP,
initiative, threat and restore potions. The `Boss` carries its effective HP,
its reconstitution period and `drain`, the kill-rate terms charged once per
monster turn. For one member `net - drain` is the solo kill step and
`hit + area` the solo die step (`FightOutcome.Terms`).

## The round

Members with initiative drink (`FightOutcome.drink`); in the kill round, if
every member moves first, the party wins before the monster acts. The monster
hits its target — highest threat, ties by lowest pool, then lowest index — for
`hit - hit / 10`, and the lowest-pool member for `hit / 10`; every member takes
`area` (a negative total heals, capped at max HP). Any pool at or below 0 loses
the fight. Members without initiative then drink; the kill round ends in a win.

## Results

* `groupOutcome_single` — one member IS `FightOutcome.fightOutcome` on the solo terms.
* `killRounds_antitone` — a member adding damage never delays the kill round.
* `used_le_stock` — no member drinks more than it holds.
* `win_alive` — a walked win leaves every member's pool positive.

Lean core only — no Mathlib.
-/
import Formal.FightOutcome

namespace Formal.GroupFight

open Formal.PredictWin (ceilDiv maxTurns ceilDiv_antitone_divisor)
open Formal.FightOutcome (scale effHp drink Exit Terms)

/-- One party member's resolved integers (×10000 scale for the steps). -/
structure Member where
  rawPlayer : Int
  net : Int
  hit : Int
  area : Int
  hp : Int
  maxHp : Int
  first : Bool
  threat : Int
  restore : Nat
  stock : Nat

/-- The boss's side: effective HP (barrier included), reconstitution, and the
kill-rate terms charged once per monster turn. -/
structure Boss where
  hp : Int
  recon : Int
  drain : Int

/-- The party's summed kill rate per round. -/
def killRate (b : Boss) (ms : List Member) : Int := (ms.map (·.net)).sum - b.drain

/-- Rounds until the boss dies. -/
def killRounds (b : Boss) (ms : List Member) : Int := ceilDiv (b.hp * scale) (killRate b ms)

/-- The guard ladder over the party; actor turns per round are `N + 1`. -/
def gate (b : Boss) (ms : List Member) : Exit :=
  if ms.all (fun m => decide (m.rawPlayer ≤ 0)) then .noDamage
  else if killRate b ms ≤ 0 then .unkillable
  else if killRounds b ms * ((ms.length : Int) + 1) > 2 * maxTurns then .overCap
  else if 0 < b.recon ∧ 2 * b.recon ≤ killRounds b ms * ((ms.length : Int) + 1) then .reconstituted
  else if ms.all (fun m => decide (m.hit + m.area ≤ 0)) then .outSustain
  else .none

/-- A member's pool and potions left. -/
abbrev Slot := Int × Nat

/-- Drink for every member whose initiative matches `pf`. -/
def drinkAll (pf : Bool) : List Member → List Slot → List Slot
  | m :: ms, (p, k) :: st =>
    (if m.first = pf then drink p (m.maxHp * scale) ((m.restore : Int) * scale) k else (p, k))
      :: drinkAll pf ms st
  | _, _ => []

/-- The boss's target: highest threat, ties by lowest pool, then lowest index.
Folds left, keeping the incumbent unless strictly beaten. -/
def target : List Member → List Slot → Nat → Nat → Int → Int → Nat
  | m :: ms, (p, _) :: st, i, best, bt, bp =>
    if bt < m.threat ∨ (bt = m.threat ∧ p < bp) then target ms st (i + 1) i m.threat p
    else target ms st (i + 1) best bt bp
  | _, _, _, best, _, _ => best

/-- The lowest pool, ties by lowest index. -/
def lowest : List Slot → Nat → Nat → Int → Nat
  | (p, _) :: st, i, best, bp => if p < bp then lowest st (i + 1) i p else lowest st (i + 1) best bp
  | _, _, best, _ => best

/-- A member's round damage: `area`, the target's 90 %, the lowest's 10 %. -/
def damage (m : Member) (i t l : Nat) : Int :=
  m.area + (if i = t then m.hit - m.hit / 10 else 0) + (if i = l then m.hit / 10 else 0)

/-- Apply a round's damage; a negative total heals, capped at max HP. -/
def strike (t l : Nat) : List Member → List Slot → Nat → List Slot
  | m :: ms, (p, k) :: st, i =>
    (if damage m i t l < 0 then (min (p - damage m i t l) (m.maxHp * scale), k)
     else (p - damage m i t l, k)) :: strike t l ms st (i + 1)
  | _, _, _ => []

/-- The boss's turn over the pools. -/
def bossTurn (ms : List Member) (st : List Slot) : List Slot :=
  match ms, st with
  | m :: ms', (p, _) :: st' =>
    strike (target ms' st' 1 0 m.threat p) (lowest st' 1 0 p) ms st 0
  | _, _ => []

/-- A loss reports a dead member's pool as 0. -/
def clamp (st : List Slot) : List Slot := st.map fun (p, k) => (max p 0, k)

/-- The walk's result: verdict, resolving round, slots. -/
structure Walk where
  win : Bool
  turns : Int
  slots : List Slot

/-- The fight from round `r` with `n` rounds left until the kill. -/
def walk (ms : List Member) : Nat → Int → List Slot → Walk
  | 0, r, st => ⟨true, r - 1, st⟩
  | n + 1, r, st =>
    if ms.all (·.first) ∧ n = 0 then ⟨true, r, drinkAll true ms st⟩
    else if (bossTurn ms (drinkAll true ms st)).any (fun s => decide (s.1 ≤ 0)) then
      ⟨false, r, clamp (bossTurn ms (drinkAll true ms st))⟩
    else if n = 0 then ⟨true, r, drinkAll false ms (bossTurn ms (drinkAll true ms st))⟩
    else walk ms n (r + 1) (drinkAll false ms (bossTurn ms (drinkAll true ms st)))

/-- A party fight's expected-value outcome (`hpEnd` ×10000, per member). -/
structure Outcome where
  win : Bool
  turns : Int
  hpEnd : List Int
  used : List Nat

/-- Every member's starting slot. -/
def start (ms : List Member) : List Slot := ms.map fun m => (effHp m.hp m.maxHp * scale, m.stock)

/-- `group_fight_core.group_outcome`. -/
def groupOutcome (b : Boss) (ms : List Member) : Outcome :=
  match gate b ms with
  | .outSustain =>
    ⟨true, killRounds b ms, ms.map (fun m => effHp m.hp m.maxHp * scale), ms.map fun _ => 0⟩
  | .none =>
    if ms.any (fun m => decide (effHp m.hp m.maxHp * scale ≤ 0)) then
      ⟨false, 0, ms.map fun _ => 0, ms.map fun _ => 0⟩
    else
      let w := walk ms (killRounds b ms).toNat 1 (start ms)
      ⟨w.win, w.turns, w.slots.map (·.1), (ms.zip w.slots).map fun (m, s) => m.stock - s.2⟩
  | _ => ⟨false, 0, ms.map fun _ => 0, ms.map fun _ => 0⟩

/-! ### One member is the solo fight. -/

/-- The solo terms of a one-member party. -/
def soloTerms (b : Boss) (m : Member) : Terms :=
  ⟨m.rawPlayer, m.net - b.drain, b.hp, b.recon, m.hit + m.area, m.first⟩

theorem damage_single (m : Member) : damage m 0 0 0 = m.hit + m.area := by
  unfold damage; simp; omega

theorem killRounds_single (b : Boss) (m : Member) :
    killRounds b [m] = Formal.FightOutcome.roundsToKill (soloTerms b m) := by
  simp [killRounds, Formal.FightOutcome.roundsToKill, killRate, soloTerms]

theorem gate_single (b : Boss) (m : Member) :
    gate b [m] = Formal.FightOutcome.gate (soloTerms b m) := by
  have hk : killRate b [m] = m.net - b.drain := by simp [killRate]
  have hr := killRounds_single b m
  unfold gate Formal.FightOutcome.gate
  simp only [hr, hk, List.all_cons, List.all_nil, Bool.and_true, decide_eq_true_eq,
    List.length_singleton, soloTerms]
  generalize Formal.FightOutcome.roundsToKill _ = R
  by_cases h1 : m.rawPlayer ≤ 0
  · simp [h1]
  by_cases h2 : m.net - b.drain ≤ 0
  · simp [h1, h2]
  by_cases h3 : maxTurns < R
  · simp [h1, h2, h3, show 2 * maxTurns < R * 2 by omega]
  by_cases h4 : 0 < b.recon ∧ b.recon ≤ R
  · simp [h1, h2, h3, h4, show ¬ 2 * maxTurns < R * 2 by omega, show 2 * b.recon ≤ R * 2 by omega]
  have h5 : ¬ (0 < b.recon ∧ 2 * b.recon ≤ R * 2) := by omega
  simp [h1, h2, h3, h4, h5, show ¬ 2 * maxTurns < R * 2 by omega]

/-- The singleton walk with the solo walk's state. -/
theorem walk_single (m : Member) (hds : 0 < m.hit + m.area) :
    ∀ (n : Nat) (r pool : Int) (k : Nat),
      walk [m] n r [(pool, k)] =
        let w := Formal.FightOutcome.walk m.first (m.hit + m.area) (m.maxHp * scale)
          ((m.restore : Int) * scale) n r pool k
        ⟨w.win, w.turns, [(w.pool, w.left)]⟩ := by
  intro n
  induction n with
  | zero => intro r pool k; simp [walk, Formal.FightOutcome.walk]
  | succ n ih =>
    intro r pool k
    have hd := damage_single m
    have hnn : ¬ (m.hit + m.area < 0) := by omega
    cases hf : m.first <;>
      simp [walk, Formal.FightOutcome.walk, hf, drinkAll, bossTurn, target, lowest, strike, hd,
        hnn, clamp] <;>
      by_cases hn : n = 0 <;> simp [hn] <;>
      split <;> rename_i hp <;> simp [ih, hf] <;> omega

/-- One member IS the solo fight: verdict, turns, ending HP and potions. -/
theorem groupOutcome_single (b : Boss) (m : Member) :
    groupOutcome b [m] =
      let s := Formal.FightOutcome.fightOutcome (soloTerms b m) m.hp m.maxHp m.restore m.stock
      ⟨s.win, s.turns, [s.hpEnd], [s.used]⟩ := by
  unfold groupOutcome Formal.FightOutcome.fightOutcome
  rw [gate_single, killRounds_single]
  cases hg : Formal.FightOutcome.gate (soloTerms b m) with
  | none =>
    have hds := Formal.FightOutcome.gate_none_dieStep _ hg
    simp only [soloTerms] at hds
    by_cases h0 : effHp m.hp m.maxHp * scale ≤ 0
    · simp [h0]
    · simp [h0, start, walk_single m hds, soloTerms]
  | _ => simp

/-! ### The kill round. -/

/-- A member adding damage never delays the kill round. -/
theorem killRounds_antitone (b : Boss) (ms : List Member) (m : Member)
    (hk : 0 < killRate b ms) (hn : 0 ≤ m.net) (hhp : 0 ≤ b.hp) :
    killRounds b (m :: ms) ≤ killRounds b ms := by
  have h : killRate b (m :: ms) = m.net + killRate b ms := by
    simp [killRate, List.sum_cons]; omega
  unfold killRounds
  rw [h]
  exact ceilDiv_antitone_divisor _ _ _ (Int.mul_nonneg hhp (by decide)) hk (by omega)

/-! ### A won fight leaves every member alive. -/

/-- Each pool is at most its member's max (lists of equal length). -/
def capped : List Member → List Slot → Prop
  | m :: ms, s :: st => s.1 ≤ m.maxHp * scale ∧ capped ms st
  | [], [] => True
  | _, _ => False

/-- Every pool is positive. -/
def alive (st : List Slot) : Prop := ∀ s ∈ st, 0 < s.1

theorem drinkAll_capped (pf : Bool) :
    ∀ (ms : List Member) (st : List Slot), capped ms st → capped ms (drinkAll pf ms st)
  | m :: ms, (p, k) :: st, ⟨h, hc⟩ => by
    refine ⟨?_, drinkAll_capped pf ms st hc⟩
    split
    · exact Formal.FightOutcome.drink_le_max _ _ _ _ h
    · exact h
  | [], [], _ => by simp [drinkAll, capped]
  | [], _ :: _, h => h.elim
  | _ :: _, [], h => h.elim

theorem drinkAll_alive (pf : Bool) :
    ∀ (ms : List Member) (st : List Slot), capped ms st → alive st → alive (drinkAll pf ms st)
  | m :: ms, (p, k) :: st, ⟨h, hc⟩, ha => by
    intro s hs
    simp only [drinkAll, List.mem_cons] at hs
    rcases hs with rfl | hs
    · have hp : 0 < p := ha _ (List.mem_cons_self ..)
      split
      · exact Int.lt_of_lt_of_le hp
          (Formal.FightOutcome.drink_ge _ _ _ _ (Int.mul_nonneg (Int.natCast_nonneg _) (by decide)) h)
      · exact hp
    · exact drinkAll_alive pf ms st hc (fun s hs => ha s (List.mem_cons_of_mem _ hs)) s hs
  | [], [], _, _ => by simp [drinkAll, alive]
  | [], _ :: _, h, _ => h.elim
  | _ :: _, [], h, _ => h.elim

theorem strike_capped (t l : Nat) :
    ∀ (ms : List Member) (st : List Slot) (i : Nat), capped ms st → capped ms (strike t l ms st i)
  | m :: ms, (p, k) :: st, i, ⟨h, hc⟩ => by
    refine ⟨?_, strike_capped t l ms st (i + 1) hc⟩
    split
    · exact Int.min_le_right _ _
    · simp only; omega
  | [], [], _, _ => by simp [strike, capped]
  | [], _ :: _, _, h => h.elim
  | _ :: _, [], _, h => h.elim

theorem bossTurn_capped (ms : List Member) (st : List Slot) (h : capped ms st) :
    capped ms (bossTurn ms st) := by
  match ms, st, h with
  | m :: ms', (p, k) :: st', h => exact strike_capped _ _ _ _ _ h
  | [], [], _ => simp [bossTurn, capped]

theorem not_any_alive (st : List Slot) (h : ¬ st.any (fun s => decide (s.1 ≤ 0)) = true) :
    alive st := by
  intro s hs
  by_cases hle : s.1 ≤ 0
  · exact absurd (List.any_eq_true.mpr ⟨s, hs, by simp [hle]⟩) h
  · omega

/-- A won walk leaves every member alive and within its max HP. -/
theorem walk_win_alive (ms : List Member) :
    ∀ (n : Nat) (r : Int) (st : List Slot), capped ms st → alive st →
      (walk ms n r st).win = true →
      capped ms (walk ms n r st).slots ∧ alive (walk ms n r st).slots := by
  intro n
  induction n with
  | zero => intro r st hc ha _; exact ⟨hc, ha⟩
  | succ n ih =>
    intro r st hc ha hw
    have c1 := drinkAll_capped true ms st hc
    have a1 := drinkAll_alive true ms st hc ha
    have c2 := bossTurn_capped ms _ c1
    by_cases h0 : (ms.all (·.first) = true ∧ n = 0)
    · simp only [walk, if_pos h0]; exact ⟨c1, a1⟩
    by_cases hd : (bossTurn ms (drinkAll true ms st)).any (fun s => decide (s.1 ≤ 0)) = true
    · simp only [walk, if_neg h0, if_pos hd] at hw; simp at hw
    have a2 := not_any_alive _ hd
    have c3 := drinkAll_capped false ms _ c2
    have a3 := drinkAll_alive false ms _ c2 a2
    by_cases hn : n = 0
    · simp only [walk, if_neg h0, if_neg hd, if_pos hn]; exact ⟨c3, a3⟩
    · simp only [walk, if_neg h0, if_neg hd, if_neg hn] at hw ⊢
      exact ih _ _ c3 a3 hw

theorem start_capped : ∀ ms : List Member, (∀ m ∈ ms, 0 ≤ m.maxHp) → capped ms (start ms)
  | m :: ms, h => by
    refine ⟨?_, start_capped ms (fun x hx => h x (List.mem_cons_of_mem _ hx))⟩
    have := Formal.FightOutcome.effHp_le m.hp m.maxHp (h m (List.mem_cons_self ..))
    simp only [scale]; omega
  | [], _ => by simp [start, capped]

/-- A walked win (no out-sustain exit) leaves every member's pool positive. -/
theorem win_alive (b : Boss) (ms : List Member) (hmax : ∀ m ∈ ms, 0 ≤ m.maxHp)
    (hg : gate b ms = .none) (hw : (groupOutcome b ms).win = true) :
    ∀ x ∈ (groupOutcome b ms).hpEnd, 0 < x := by
  unfold groupOutcome at hw ⊢
  rw [hg] at hw ⊢
  simp only at hw ⊢
  split at hw
  · simp at hw
  · rename_i h0
    simp only [if_neg h0]
    have ha : alive (start ms) := by
      intro s hs
      simp only [start, List.mem_map] at hs
      obtain ⟨m, hm, rfl⟩ := hs
      by_cases hle : effHp m.hp m.maxHp * scale ≤ 0
      · exact absurd (List.any_eq_true.mpr ⟨m, hm, by simp [hle]⟩) h0
      · simp only; omega
    have := (walk_win_alive ms _ 1 _ (start_capped ms hmax) ha hw).2
    intro x hx
    simp only [List.mem_map] at hx
    obtain ⟨s, hs, rfl⟩ := hx
    exact this s hs

/-- `win_alive`'s hypotheses hold together: a walked two-member win (the
tank takes the 90 %, the weak member the 10 %). -/
theorem win_alive_witness : ∃ (b : Boss) (ms : List Member),
    (∀ m ∈ ms, 0 ≤ m.maxHp) ∧ gate b ms = .none ∧ (groupOutcome b ms).win = true :=
  ⟨⟨20, 0, 0⟩,
   [⟨10, 20000, 400000, 0, 100, 100, true, 0, 0, 0⟩, ⟨10, 20000, 400000, 0, 200, 200, true, 5, 0, 0⟩],
   by decide, by decide, by decide⟩

end Formal.GroupFight
