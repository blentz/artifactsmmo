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

The walk tracks the boss's pool. Living members with initiative drink
(`FightOutcome.drink`); if every living member moves first and their damage
finishes the boss, the party wins before it acts. The boss hits its target
among the living — highest threat, ties by lowest pool, then lowest index — for
`hit - hit / 10`, and the lowest living pool for `hit / 10`; every living member
takes `area` (a negative total heals, capped at max HP). A pool at or below 0 is
dead: it no longer acts, drinks, is targeted or pays `area` (the 2026-10-11
probe: a 1-HP member died on turn 3 and its partner won alone). The fight is
lost only when every member is dead. The round's damage is each first mover
alive before the boss's turn and each late mover alive after it, less `drain`;
late movers then drink. The turn cap and reconstitution count actor turns
(`N + 1` a round, the full party's: conservative once a member dies).

## Results

* `groupOutcome_single` — one member IS `FightOutcome.fightOutcome` on the solo terms.
* `killRounds_antitone` — a member adding damage never delays the full party's kill round.
* `win_survivor` — a walked win leaves some member alive (`win_survivor_witness`:
  one dies, the other wins).

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

/-- A member's pool and potions left; a pool at or below 0 is dead. -/
abbrev Slot := Int × Nat

/-- Drink for every LIVING member whose initiative matches `pf`. -/
def drinkAll (pf : Bool) : List Member → List Slot → List Slot
  | m :: ms, (p, k) :: st =>
    (if m.first = pf ∧ 0 < p then drink p (m.maxHp * scale) ((m.restore : Int) * scale) k
     else (p, k)) :: drinkAll pf ms st
  | _, _ => []

/-- The boss's target among the living: highest threat, ties by lowest pool,
then lowest index (`cur` is the incumbent `(index, threat, pool)`). -/
def target : List Member → List Slot → Nat → Option (Nat × Int × Int) → Option Nat
  | m :: ms, (p, _) :: st, i, cur =>
    if p ≤ 0 then target ms st (i + 1) cur
    else match cur with
      | none => target ms st (i + 1) (some (i, m.threat, p))
      | some (j, bt, bp) =>
        if bt < m.threat ∨ (bt = m.threat ∧ p < bp) then target ms st (i + 1) (some (i, m.threat, p))
        else target ms st (i + 1) (some (j, bt, bp))
  | _, _, _, cur => cur.map (·.1)

/-- The lowest living pool, ties by lowest index. -/
def lowest : List Slot → Nat → Option (Nat × Int) → Option Nat
  | (p, _) :: st, i, cur =>
    if p ≤ 0 then lowest st (i + 1) cur
    else match cur with
      | none => lowest st (i + 1) (some (i, p))
      | some (j, bp) => if p < bp then lowest st (i + 1) (some (i, p)) else lowest st (i + 1) (some (j, bp))
  | _, _, cur => cur.map (·.1)

/-- A member's round damage: `area`, the target's 90 %, the lowest's 10 %. -/
def damage (m : Member) (i : Nat) (t l : Option Nat) : Int :=
  m.area + (if t = some i then m.hit - m.hit / 10 else 0) + (if l = some i then m.hit / 10 else 0)

/-- Apply a round's damage to the living; a negative total heals, capped at max HP. -/
def strike (t l : Option Nat) : List Member → List Slot → Nat → List Slot
  | m :: ms, (p, k) :: st, i =>
    (if p ≤ 0 then (p, k)
     else if damage m i t l < 0 then (min (p - damage m i t l) (m.maxHp * scale), k)
     else (p - damage m i t l, k)) :: strike t l ms st (i + 1)
  | _, _, _ => []

/-- The boss's turn over the pools. -/
def bossTurn (ms : List Member) (st : List Slot) : List Slot :=
  strike (target ms st 0 none) (lowest st 0 none) ms st 0

/-- A member's damage this round: a first mover acts if alive before the
boss's turn (`pre`), a late mover if alive after it (`post`). -/
def netSum : List Member → List Slot → List Slot → Int
  | m :: ms, a :: as, c :: cs =>
    (if (if m.first then 0 < a.1 else 0 < c.1) then m.net else 0) + netSum ms as cs
  | _, _, _ => 0

/-- Every living member moves before the boss. -/
def allAliveFirst : List Member → List Slot → Bool
  | m :: ms, (p, _) :: st => (m.first || decide (p ≤ 0)) && allAliveFirst ms st
  | _, _ => true

/-- Every member is dead. -/
def allDead (st : List Slot) : Bool := st.all fun s => decide (s.1 ≤ 0)

/-- The fight cannot reach round `r`: past the 100-turn cap, or the boss
reconstitutes first (actor turns `N + 1` a round). -/
def deadline (b : Boss) (ms : List Member) (r : Int) : Prop :=
  r * ((ms.length : Int) + 1) > 2 * maxTurns ∨ (0 < b.recon ∧ 2 * b.recon ≤ r * ((ms.length : Int) + 1))

instance (b : Boss) (ms : List Member) (r : Int) : Decidable (deadline b ms r) := by
  unfold deadline; infer_instance

/-- A dead member reports 0. -/
def clamp (st : List Slot) : List Slot := st.map fun (p, k) => (max p 0, k)

/-- The walk's result: verdict, resolving round, slots. -/
structure Walk where
  win : Bool
  turns : Int
  slots : List Slot

/-- The fight from round `r` with the boss's pool at `hp` (`f` bounds the rounds). -/
def walk (b : Boss) (ms : List Member) : Nat → Int → Int → List Slot → Walk
  | 0, r, _, st => ⟨false, r - 1, clamp st⟩
  | f + 1, r, hp, st =>
    if deadline b ms r then ⟨false, r - 1, clamp st⟩
    else if allAliveFirst ms (drinkAll true ms st) = true ∧
        hp - (netSum ms (drinkAll true ms st) (drinkAll true ms st) - b.drain) ≤ 0 then
      ⟨true, r, clamp (drinkAll true ms st)⟩
    else if allDead (bossTurn ms (drinkAll true ms st)) = true then
      ⟨false, r, clamp (bossTurn ms (drinkAll true ms st))⟩
    else if hp - (netSum ms (drinkAll true ms st) (bossTurn ms (drinkAll true ms st)) - b.drain) ≤ 0
    then ⟨true, r, clamp (drinkAll false ms (bossTurn ms (drinkAll true ms st)))⟩
    else walk b ms f (r + 1)
      (hp - (netSum ms (drinkAll true ms st) (bossTurn ms (drinkAll true ms st)) - b.drain))
      (drinkAll false ms (bossTurn ms (drinkAll true ms st)))

/-- A party fight's expected-value outcome (`hpEnd` ×10000, per member). -/
structure Outcome where
  win : Bool
  turns : Int
  hpEnd : List Int
  used : List Nat

/-- Every member's starting slot. -/
def start (ms : List Member) : List Slot := ms.map fun m => (effHp m.hp m.maxHp * scale, m.stock)

/-- The rounds the walk may take: the turn cap is reached by then. -/
def fuel : Nat := (2 * maxTurns).toNat

/-- `group_fight_core.group_outcome`. -/
def groupOutcome (b : Boss) (ms : List Member) : Outcome :=
  match gate b ms with
  | .outSustain =>
    ⟨true, killRounds b ms, ms.map (fun m => effHp m.hp m.maxHp * scale), ms.map fun _ => 0⟩
  | .none =>
    if ms.any (fun m => decide (effHp m.hp m.maxHp * scale ≤ 0)) then
      ⟨false, 0, ms.map fun _ => 0, ms.map fun _ => 0⟩
    else if b.hp * scale ≤ 0 then
      ⟨true, 0, ms.map (fun m => effHp m.hp m.maxHp * scale), ms.map fun _ => 0⟩
    else
      let w := walk b ms fuel 1 (b.hp * scale) (start ms)
      ⟨w.win, w.turns, w.slots.map (·.1), (ms.zip w.slots).map fun (m, s) => m.stock - s.2⟩
  | _ => ⟨false, 0, ms.map fun _ => 0, ms.map fun _ => 0⟩

/-! ### One member is the solo fight. -/

/-- The solo terms of a one-member party. -/
def soloTerms (b : Boss) (m : Member) : Terms :=
  ⟨m.rawPlayer, m.net - b.drain, b.hp, b.recon, m.hit + m.area, m.first⟩

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

theorem drink_pos (p maxPool rPool : Int) (k : Nat) (hp : 0 < p) (hr : 0 ≤ rPool) :
    0 < (drink p maxPool rPool k).1 := by
  unfold drink; split
  · rename_i h; simp only; rw [Int.min_def]; split <;> omega
  · exact hp

/-- `ceilDiv` steps down by one per kill step. -/
theorem ceilDiv_sub (B K : Int) (hK : 0 < K) : ceilDiv (B - K) K = ceilDiv B K - 1 := by
  unfold ceilDiv
  have : B - K + K - 1 = (B + K - 1) + (-1) * K := by omega
  rw [this, Int.add_mul_fdiv_right _ _ (by omega)]; omega

theorem ceilDiv_le_one_iff (B K : Int) (hK : 0 < K) (hB : 0 < B) :
    ceilDiv B K ≤ 1 ↔ B - K ≤ 0 := by
  have h1 := Formal.PredictWin.ceilDiv_mul_ge B K hK (by omega)
  have h2 := Formal.PredictWin.ceilDiv_pred_mul_lt B K hK (by omega)
  constructor
  · intro h
    have : ceilDiv B K * K ≤ 1 * K := Int.mul_le_mul_of_nonneg_right h (by omega)
    omega
  · intro h
    rcases Int.lt_or_le 1 (ceilDiv B K) with hc | hc
    · have : 1 * K ≤ (ceilDiv B K - 1) * K := Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
      omega
    · exact hc

theorem bossTurn_single (m : Member) (p : Int) (k : Nat) (hp : 0 < p) (hd : 0 ≤ m.hit + m.area) :
    bossTurn [m] [(p, k)] = [(p - (m.hit + m.area), k)] := by
  have hdmg : damage m 0 (some 0) (some 0) = m.hit + m.area := by unfold damage; simp; omega
  simp [bossTurn, target, lowest, strike, show ¬ p ≤ 0 by omega, hdmg,
    show ¬ m.hit + m.area < 0 by omega]

theorem netSum_single (m : Member) (a c : Slot) :
    netSum [m] [a] [c] = if (if m.first then 0 < a.1 else 0 < c.1) then m.net else 0 := by
  simp [netSum]

theorem drinkAll_single (pf : Bool) (m : Member) (p : Int) (k : Nat) :
    drinkAll pf [m] [(p, k)] =
      [if m.first = pf ∧ 0 < p then drink p (m.maxHp * scale) ((m.restore : Int) * scale) k else (p, k)] := by
  simp [drinkAll]

theorem allAliveFirst_single (m : Member) (s : Slot) :
    allAliveFirst [m] [s] = (m.first || decide (s.1 ≤ 0)) := by
  obtain ⟨p, k⟩ := s; simp [allAliveFirst]

theorem allDead_single (s : Slot) : allDead [s] = decide (s.1 ≤ 0) := by simp [allDead]

/-- The singleton walk is the solo walk while the boss's pool is `n` kill
steps from 0 and no deadline falls inside those rounds. -/
theorem walk_single (b : Boss) (m : Member) (hds : 0 < m.hit + m.area)
    (hK : 0 < m.net - b.drain) :
    ∀ (n f : Nat) (r B pool : Int) (k : Nat), 1 ≤ n → n ≤ f → 0 < B →
      ceilDiv B (m.net - b.drain) = n → 0 < pool → 1 ≤ r →
      ¬ deadline b [m] (r + n - 1) →
      walk b [m] f r B [(pool, k)] =
        let w := Formal.FightOutcome.walk m.first (m.hit + m.area) (m.maxHp * scale)
          ((m.restore : Int) * scale) n r pool k
        ⟨w.win, w.turns, [(max w.pool 0, w.left)]⟩ := by
  intro n
  induction n with
  | zero => intro f r B pool k h; omega
  | succ n ih =>
    intro f r B pool k _ hf hB hc hp hr hd
    obtain ⟨f, rfl⟩ : ∃ f', f = f' + 1 := ⟨f - 1, by omega⟩
    have hr0 : (0 : Int) ≤ (m.restore : Int) * scale :=
      Int.mul_nonneg (Int.natCast_nonneg _) (by decide)
    have hnd : ¬ deadline b [m] r := by
      unfold deadline at hd ⊢; simp only [List.length_singleton] at hd ⊢
      intro h; apply hd; rcases h with h | h
      · left; have : r * ((1 : Nat) + 1 : Int) ≤ (r + (n + 1 : Nat) - 1) * ((1 : Nat) + 1 : Int) :=
          Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
        omega
      · right; refine ⟨h.1, ?_⟩
        have : r * ((1 : Nat) + 1 : Int) ≤ (r + (n + 1 : Nat) - 1) * ((1 : Nat) + 1 : Int) :=
          Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
        omega
    have hdk : 0 < m.hit + m.area := hds
    have hdmg : damage m 0 (some 0) (some 0) = m.hit + m.area := by
      unfold damage; simp; omega
    have hkill : (n = 0) ↔ B - (m.net - b.drain) ≤ 0 := by
      rw [← ceilDiv_le_one_iff B _ hK hB]; omega
    have hkd : ¬ B - (m.net - b.drain) ≤ 0 → 0 < B - (m.net - b.drain) := by omega
    cases hfst : m.first
    · -- the boss moves first
      have hpos := fun (h : ¬ pool - (m.hit + m.area) ≤ 0) =>
        drink_pos (pool - (m.hit + m.area)) (m.maxHp * scale) _ k (by omega) hr0
      rw [walk, if_neg hnd]
      simp only [drinkAll_single, hfst, Bool.false_eq_true, false_and, if_false,
        allAliveFirst_single, Bool.false_or, bossTurn_single m pool k hp (by omega), allDead_single,
        netSum_single, Formal.FightOutcome.walk]
      by_cases hl : pool - (m.hit + m.area) ≤ 0
      · simp [hl, clamp, show ¬ pool ≤ 0 by omega, Int.max_eq_right hl]
      · have hp2 : 0 < pool - (m.hit + m.area) := by omega
        simp only [hl, decide_false, Bool.false_eq_true, if_false, hp2, if_true,
          show ¬ (pool ≤ 0) by omega, false_and, decide_false, and_self]
        by_cases hn : n = 0
        · simp [hn, hkill.mp hn, clamp, Int.max_eq_left (Int.le_of_lt (hpos hl))]
        · have hnk : ¬ B - (m.net - b.drain) ≤ 0 := fun h => hn (hkill.mpr h)
          simp only [hn, hnk, if_false]
          rw [ih f (r + 1) (B - (m.net - b.drain)) _ _ (by omega) (by omega) (hkd hnk)
            (by rw [ceilDiv_sub _ _ hK]; omega) (hpos hl) (by omega)
            (by have : r + 1 + (n : Int) - 1 = r + ((n + 1 : Nat) : Int) - 1 := by omega
                rw [this]; exact hd)]
          simp [hfst]
    · -- the member moves first
      have hdp := drink_pos pool (m.maxHp * scale) _ k hp hr0
      rw [walk, if_neg hnd]
      simp only [drinkAll_single, hfst, true_and, if_pos hp, Formal.FightOutcome.walk]
      generalize hdr : drink pool (m.maxHp * scale) ((m.restore : Int) * scale) k = d at hdp ⊢
      obtain ⟨p1, k1⟩ := d
      simp only at hdp
      simp only [allAliveFirst_single, hfst, Bool.true_or, netSum_single, if_true, hdp,
        bossTurn_single m _ k1 hdp (by omega), allDead_single]
      by_cases hn : n = 0
      · simp [hn, hkill.mp hn, clamp, Int.max_eq_left (Int.le_of_lt hdp)]
      · have hnk : ¬ B - (m.net - b.drain) ≤ 0 := fun h => hn (hkill.mpr h)
        simp only [hn, hnk, and_false, if_false, decide_eq_true_eq]
        by_cases hl : p1 - (m.hit + m.area) ≤ 0
        · simp [hl, clamp, Int.max_eq_right hl]
        · have hp2 : 0 < p1 - (m.hit + m.area) := by omega
          simp only [hl, if_false]
          have hw := ih f (r + 1) (B - (m.net - b.drain)) _ k1 (by omega) (by omega) (hkd hnk)
            (by rw [ceilDiv_sub _ _ hK]; omega) hp2 (by omega)
            (by have : r + 1 + (n : Int) - 1 = r + ((n + 1 : Nat) : Int) - 1 := by omega
                rw [this]; exact hd)
          simp [drinkAll_single, hfst, hw]

theorem gate_none_facts (t : Terms) (h : Formal.FightOutcome.gate t = .none) :
    0 < t.killStep ∧ Formal.FightOutcome.roundsToKill t ≤ maxTurns ∧
      ¬ (0 < t.recon ∧ t.recon ≤ Formal.FightOutcome.roundsToKill t) ∧ 0 < t.dieStep := by
  unfold Formal.FightOutcome.gate at h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  split at h; · cases h
  refine ⟨by omega, by omega, by assumption, by omega⟩

theorem ceilDiv_nonpos (n d : Int) (hn : n ≤ 0) (hd : 0 < d) : ceilDiv n d ≤ 0 := by
  unfold ceilDiv
  have h1 := Int.mul_fdiv_add_fmod (n + d - 1) d
  have h2 := Int.fmod_nonneg_of_pos (n + d - 1) hd
  rcases Int.lt_or_le 0 (Int.fdiv (n + d - 1) d) with hq | hq
  · have : d * 1 ≤ d * Int.fdiv (n + d - 1) d := Int.mul_le_mul_of_nonneg_left (by omega) (by omega)
    omega
  · exact hq

/-- One member IS the solo fight: verdict, turns, ending HP and potions. -/
theorem groupOutcome_single (b : Boss) (m : Member) :
    groupOutcome b [m] =
      let s := Formal.FightOutcome.fightOutcome (soloTerms b m) m.hp m.maxHp m.restore m.stock
      ⟨s.win, s.turns, [s.hpEnd], [s.used]⟩ := by
  unfold groupOutcome Formal.FightOutcome.fightOutcome
  rw [gate_single, killRounds_single]
  cases hg : Formal.FightOutcome.gate (soloTerms b m) with
  | none =>
    obtain ⟨hK, hR, hrc, hds⟩ := gate_none_facts _ hg
    simp only [soloTerms] at hK hds
    have hRdef : Formal.FightOutcome.roundsToKill (soloTerms b m) = ceilDiv (b.hp * scale) (m.net - b.drain) := rfl
    by_cases h0 : effHp m.hp m.maxHp * scale ≤ 0
    · simp [h0]
    by_cases hb : b.hp * scale ≤ 0
    · have hz : (Formal.FightOutcome.roundsToKill (soloTerms b m)).toNat = 0 := by
        rw [hRdef]; have := ceilDiv_nonpos _ _ hb hK; omega
      simp [h0, hb, hz, Formal.FightOutcome.walk]
    · have hpos := Formal.PredictWin.ceilDiv_pos (b.hp * scale) (m.net - b.drain) hK (by omega)
      have hw := walk_single b m hds hK (Formal.FightOutcome.roundsToKill (soloTerms b m)).toNat fuel 1
        (b.hp * scale) (effHp m.hp m.maxHp * scale) m.stock (by rw [hRdef]; omega)
        (by rw [hRdef]; unfold fuel; simp only [hRdef] at hR; simp [Formal.PredictWin.maxTurns] at hR ⊢; omega)
        (by omega) (by rw [hRdef]; omega) (by omega) (by omega)
        (by
          unfold deadline; simp only [List.length_singleton, hRdef] at hrc hR ⊢
          simp only [soloTerms] at hrc
          have := hpos
          generalize ceilDiv (b.hp * scale) (m.net - b.drain) = R at *
          have hRn : ((R.toNat : Nat) : Int) = R := by omega
          rw [hRn]; simp only [Formal.PredictWin.maxTurns] at hR ⊢; omega)
      have hmax : 0 < effHp m.hp m.maxHp * scale := by omega
      simp only [h0, hb, if_false, List.any_cons, List.any_nil, Bool.or_false, decide_eq_true_eq,
        start, List.map_cons, List.map_nil, hw]
      have hmaxHp : 0 ≤ m.maxHp := by
        unfold effHp at hmax; split at hmax
        · have := Int.min_le_right m.hp m.maxHp; simp only [scale] at hmax; omega
        · simp at hmax
      have hle : effHp m.hp m.maxHp * scale ≤ m.maxHp * scale := by
        have := Formal.FightOutcome.effHp_le m.hp m.maxHp hmaxHp; simp only [scale]; omega
      have hnn := Formal.FightOutcome.walk_pool_nonneg m.first (m.hit + m.area) (m.maxHp * scale)
        ((m.restore : Int) * scale) hds (Int.mul_nonneg (Int.natCast_nonneg _) (by decide))
        (Formal.FightOutcome.roundsToKill (soloTerms b m)).toNat 1 _ m.stock hmax hle
      simp only [soloTerms] at hnn ⊢
      simp [Int.max_eq_left hnn]
  | _ => simp

/-! ### The kill round. -/

/-- A member adding damage never delays the kill round (the full party's). -/
theorem killRounds_antitone (b : Boss) (ms : List Member) (m : Member)
    (hk : 0 < killRate b ms) (hn : 0 ≤ m.net) (hhp : 0 ≤ b.hp) :
    killRounds b (m :: ms) ≤ killRounds b ms := by
  have h : killRate b (m :: ms) = m.net + killRate b ms := by
    simp [killRate, List.sum_cons]; omega
  unfold killRounds
  rw [h]
  exact ceilDiv_antitone_divisor _ _ _ (Int.mul_nonneg hhp (by decide)) hk (by omega)

/-! ### A won fight leaves a member alive. -/

/-- Some member is alive. -/
def anyAlive (st : List Slot) : Bool := st.any fun s => decide (0 < s.1)

theorem drinkAll_anyAlive (pf : Bool) :
    ∀ (ms : List Member) (st : List Slot), anyAlive st = true → st.length ≤ ms.length →
      anyAlive (drinkAll pf ms st) = true
  | m :: ms, (p, k) :: st, ha, hl => by
    simp only [anyAlive, List.any_cons, Bool.or_eq_true, decide_eq_true_eq] at ha
    simp only [drinkAll, anyAlive, List.any_cons, Bool.or_eq_true, decide_eq_true_eq]
    rcases ha with hp | ht
    · left
      split
      · exact drink_pos _ _ _ _ hp (Int.mul_nonneg (Int.natCast_nonneg _) (by decide))
      · exact hp
    · right
      have := drinkAll_anyAlive pf ms st (by simpa [anyAlive] using ht) (by simp at hl; omega)
      simpa [anyAlive] using this
  | [], _ :: _, _, hl => by simp at hl
  | _, [], ha, _ => by simp [anyAlive] at ha

theorem drinkAll_length (pf : Bool) :
    ∀ (ms : List Member) (st : List Slot), (drinkAll pf ms st).length ≤ ms.length
  | m :: ms, _ :: st => by simp [drinkAll]; exact drinkAll_length pf ms st
  | [], _ => by simp [drinkAll]
  | _ :: _, [] => by simp [drinkAll]

theorem strike_length (t l : Option Nat) :
    ∀ (ms : List Member) (st : List Slot) (i : Nat), (strike t l ms st i).length ≤ ms.length
  | m :: ms, _ :: st, i => by simp [strike]; exact strike_length t l ms st (i + 1)
  | [], _, _ => by simp [strike]
  | _ :: _, [], _ => by simp [strike]

theorem clamp_anyAlive (st : List Slot) (h : anyAlive st = true) : anyAlive (clamp st) = true := by
  simp only [anyAlive, List.any_eq_true, decide_eq_true_eq] at h ⊢
  obtain ⟨⟨p, k⟩, hs, hp⟩ := h
  exact ⟨(max p 0, k), List.mem_map.mpr ⟨(p, k), hs, rfl⟩, by simp only at hp ⊢; omega⟩

theorem not_allDead (st : List Slot) (h : ¬ allDead st = true) : anyAlive st = true := by
  simp only [anyAlive, List.any_eq_true, decide_eq_true_eq]
  by_cases hx : ∃ s ∈ st, 0 < s.1
  · exact hx
  · exfalso; apply h
    simp only [allDead, List.all_eq_true, decide_eq_true_eq]
    intro s hs
    by_cases hs' : s.1 ≤ 0
    · exact hs'
    · exact absurd ⟨s, hs, by omega⟩ hx

/-- A won walk leaves some member alive. -/
theorem walk_win_anyAlive (b : Boss) (ms : List Member) :
    ∀ (f : Nat) (r hp : Int) (st : List Slot), anyAlive st = true → st.length ≤ ms.length →
      (walk b ms f r hp st).win = true → anyAlive (walk b ms f r hp st).slots = true := by
  intro f
  induction f with
  | zero => intro r hp st _ _ hw; simp [walk] at hw
  | succ f ih =>
    intro r hp st ha hl hw
    have a1 := drinkAll_anyAlive true ms st ha hl
    by_cases hd : deadline b ms r
    · simp [walk, hd] at hw
    by_cases he : allAliveFirst ms (drinkAll true ms st) = true ∧
        hp - (netSum ms (drinkAll true ms st) (drinkAll true ms st) - b.drain) ≤ 0
    · simp only [walk, if_neg hd, if_pos he]; exact clamp_anyAlive _ a1
    by_cases hdead : allDead (bossTurn ms (drinkAll true ms st)) = true
    · simp [walk, hd, he, hdead] at hw
    have a2 := not_allDead _ hdead
    have l2 : (bossTurn ms (drinkAll true ms st)).length ≤ ms.length := strike_length _ _ _ _ _
    have a3 := drinkAll_anyAlive false ms _ a2 l2
    by_cases hk : hp - (netSum ms (drinkAll true ms st) (bossTurn ms (drinkAll true ms st)) - b.drain) ≤ 0
    · simp only [walk, if_neg hd, if_neg he, if_neg hdead, if_pos hk]; exact clamp_anyAlive _ a3
    · simp only [walk, if_neg hd, if_neg he, if_neg hdead, if_neg hk] at hw ⊢
      exact ih _ _ _ a3 (drinkAll_length _ _ _) hw

/-- A walked win (no out-sustain exit) leaves some member alive. -/
theorem win_survivor (b : Boss) (ms : List Member) (hg : gate b ms = .none)
    (hw : (groupOutcome b ms).win = true) : ∃ x ∈ (groupOutcome b ms).hpEnd, 0 < x := by
  have hne : ms ≠ [] := by
    intro h; subst h; simp [gate] at hg
  unfold groupOutcome at hw ⊢
  rw [hg] at hw ⊢
  simp only at hw ⊢
  by_cases h0 : ms.any (fun m => decide (effHp m.hp m.maxHp * scale ≤ 0)) = true
  · simp [h0] at hw
  have hall : ∀ m ∈ ms, 0 < effHp m.hp m.maxHp * scale := by
    intro m hm
    by_cases hle : effHp m.hp m.maxHp * scale ≤ 0
    · exact absurd (List.any_eq_true.mpr ⟨m, hm, by simp [hle]⟩) h0
    · omega
  by_cases hb : b.hp * scale ≤ 0
  · simp only [h0, hb, if_false, if_true, Bool.false_eq_true]
    obtain ⟨m, hm⟩ := List.exists_mem_of_ne_nil ms hne
    exact ⟨_, List.mem_map_of_mem hm, hall m hm⟩
  · simp only [h0, hb, if_false, Bool.false_eq_true] at hw ⊢
    have hs : anyAlive (start ms) = true := by
      obtain ⟨m, hm⟩ := List.exists_mem_of_ne_nil ms hne
      simp only [anyAlive, start, List.any_map, List.any_eq_true, decide_eq_true_eq, Function.comp]
      exact ⟨m, hm, hall m hm⟩
    have := walk_win_anyAlive b ms fuel 1 _ (start ms) hs (by simp [start]) hw
    simp only [anyAlive, List.any_eq_true, decide_eq_true_eq] at this
    obtain ⟨s, hs, hp⟩ := this
    exact ⟨s.1, List.mem_map_of_mem hs, hp⟩

/-- `win_survivor`'s hypotheses hold together, and the walk is the new rule's:
the weak member dies in round 1 and the strong one wins alone (the 2026-10-11
probe's shape). -/
theorem win_survivor_witness : ∃ (b : Boss) (ms : List Member),
    gate b ms = .none ∧ (groupOutcome b ms).win = true ∧ (groupOutcome b ms).hpEnd.head? = some 0 :=
  ⟨⟨20, 0, 0⟩,
   [⟨10, 20000, 400000, 0, 1, 100, false, 0, 0, 0⟩, ⟨10, 20000, 100000, 0, 200, 200, true, 0, 0, 0⟩],
   by decide, by decide, by decide⟩

end Formal.GroupFight
