/-
Formal model of `predict_win` from `src/artifactsmmo_cli/ai/combat.py`.

The Python routine decides whether the player beats a monster under the
documented fight formula
(https://docs.artifactsmmo.com/concepts/stats_and_fights). It uses Python
floats; we model it EXACTLY in integers. Every float reduction below was
verified against the Python over the full game range (see
`formal/diff/test_predict_win_diff.py`, 200k+ random tuples, zero mismatch).

## Exact-integer reductions

* `_round_half_up(value) = floor(value + 0.5)`. For `value = x*pct/100` with
  integer `x, pct`, this equals `(x*pct + 50) // 100` (floor), modelled by
  `Int.fdiv (x*pct + 50) 100`. Verified ∀ `x ∈ [0,2000], pct ∈ [0,200]`.

* `_element_damage(attack, dmg_pct, resist_pct)`:
      output  = attack + roundHalfUp(attack*dmg_pct)
      blocked = roundHalfUp(output*resist_pct)
      return max(0, output - blocked)
  all exact integers.

* `_expected_hit = raw * (1 + (crit/100)*0.5)` where `raw = Σ element damages`.
  The expected hit is the rational `raw*(200+crit)/200`. `predict_win` only
  compares it via `ceil(hp / hit)`:
      rounds_to_kill = ceil(monster_hp / player_hit)
                     = ceil(monster_hp*200 / (raw*(200+crit)))
  an exact integer ceil-division (guard `raw > 0`, so the denominator
  `raw*(200+crit) > 0`).

## Verdict

* `player_hit ≤ 0`  (raw = 0)            ⇒ False
* `rounds_to_kill > MAX_TURNS` (= 100)   ⇒ False
* `monster_hit ≤ 0` (monster raw = 0)    ⇒ True
* otherwise: `rounds_to_kill ≤ rounds_to_die` if the player goes first
  (initiative tiebreak `player_init ≥ monster_init`), else strict `<`.

We abstract `pick_loadout`/`project_loadout_stats`/monster getters as INPUT
stat tuples — those resolve to the integers fed to this arithmetic and are
separate components. `predict_win`'s own arithmetic is modelled from the
resolved player/monster stats, expressed as the per-element raw sums
`rawPlayer` and `rawMonster` plus the scalar stats.

Lean core only — no mathlib. Integer arithmetic via `omega` / `Int` lemmas.
-/

namespace Formal.PredictWin

/-- Documented combat turn cap (mirrors `MAX_TURNS`). -/
def maxTurns : Int := 100

/-- `_round_half_up(x*pct/100)` as an exact integer: `(x*pct + 50) // 100`
floored. Verified equal to Python `math.floor(x*pct/100 + 0.5)`. -/
def roundHalfUp (x pct : Int) : Int := Int.fdiv (x * pct + 50) 100

/-- `_element_damage(attack, dmgPct, resistPct)` — net damage for one element. -/
def elementDamage (attack dmgPct resistPct : Int) : Int :=
  let output := attack + roundHalfUp attack dmgPct
  let blocked := roundHalfUp output resistPct
  max 0 (output - blocked)

/-- `Int.fdiv` is monotone in its numerator for a positive divisor, on the
nonnegative-numerator domain (the only domain `roundsTo` uses). -/
theorem fdiv_le_fdiv_of_le (a b d : Int) (hd : 0 < d) (ha0 : 0 ≤ a) (hab : a ≤ b) :
    Int.fdiv a d ≤ Int.fdiv b d := by
  have ha := Int.mul_fdiv_add_fmod a d
  have hb := Int.mul_fdiv_add_fmod b d
  have hmb_lt : Int.fmod b d < d := Int.fmod_lt_of_pos _ hd
  -- 0 ≤ ra (a ≥ 0), rb < d. Suppose qa ≥ qb+1 ⇒ d*qa ≥ d*qb+d ⇒ contradiction.
  rcases Int.lt_or_le (Int.fdiv b d) (Int.fdiv a d) with hcon | hcon
  · exfalso
    have hstep : Int.fdiv b d + 1 ≤ Int.fdiv a d := by omega
    have h1 : d * (Int.fdiv b d + 1) ≤ d * Int.fdiv a d :=
      Int.mul_le_mul_of_nonneg_left hstep (Int.le_of_lt hd)
    have hexp : d * (Int.fdiv b d + 1) = d * Int.fdiv b d + d := by
      rw [Int.mul_add, Int.mul_one]
    have hma_nn : 0 ≤ Int.fmod a d := Int.fmod_nonneg ha0 (Int.le_of_lt hd)
    omega
  · exact hcon

/-- `raw = Σ element damages` over the four documented elements
(`fire, earth, water, air`), exactly as Python's `_expected_hit` sums
`_element_damage(attack, dmg_global + dmg_elem, resist)` per element. Each
element is `(attack, dmgPct, resistPct)` where `dmgPct = dmg_global + dmg_elem`
is the already-combined per-element damage percent. -/
def rawHit
    (a0 d0 r0 a1 d1 r1 a2 d2 r2 a3 d3 r3 : Int) : Int :=
  elementDamage a0 d0 r0 + elementDamage a1 d1 r1
    + elementDamage a2 d2 r2 + elementDamage a3 d3 r3

/-- The integer ceil-division `ceil(n / d)` for `d > 0`, modelled by
`(n + d - 1) // d` floored — `Int.fdiv (n + d - 1) d`. Used for
`rounds_to_kill` / `rounds_to_die`. -/
def ceilDiv (n d : Int) : Int := Int.fdiv (n + d - 1) d

/-- `rounds_to_kill = ceil(hp / hit)` where the expected hit is the rational
`raw*(200+crit)/200`, so
`rounds_to_kill = ceil(hp*200 / (raw*(200+crit)))`. Requires the denominator
`raw*(200+crit) > 0` (the caller guards `raw > 0`). -/
def roundsTo (hp raw crit : Int) : Int :=
  ceilDiv (hp * 200) (raw * (200 + crit))

/-- Per-round net HP removed from the MONSTER, in the ×10000 integer space: the
player's expected per-turn damage `50*rawPlayer*(200+pCrit)` MINUS the monster's
expected heal-on-crit `mCrit*mLifesteal*mAtkSum` (the monster sustains itself with
lifesteal). With `mLifesteal = 0` this is `50*rawPlayer*(200+pCrit)`, and
`ceilDiv (hp*10000) (50*r*(200+c)) = ceilDiv (hp*200) (r*(200+c))` (a common 50×
scale, ceilDiv being scale-invariant), so the lifesteal-free verdict is exactly the
old one. `mAtkSum`/`pAtkSum` are the raw summed attack stats (the lifesteal heal is
`crit% × lifesteal% × Σattack`, kept exact by the ×10000 = ×200 ×100 ×100 scale). -/
def killStep (rawPlayer pCrit mCrit mLifesteal mAtkSum : Int) : Int :=
  50 * rawPlayer * (200 + pCrit) - mCrit * mLifesteal * mAtkSum

/-- Per-round net HP removed from the PLAYER (×10000): monster damage MINUS the
player's heal-on-crit `pCrit*pLifesteal*pAtkSum`, PLUS the monster's flat
per-turn `monsterPoison` damage-over-time (applied once turn 1, ticks every turn). -/
def dieStep (rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison : Int) : Int :=
  50 * rawMonster * (200 + mCrit) - pCrit * pLifesteal * pAtkSum + monsterPoison * 10000

def predictWin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier : Int)
    (playerFirst : Bool) : Bool :=
  if rawPlayer ≤ 0 then false
  else
    let ks := killStep rawPlayer pCrit mCrit mLifesteal mAtkSum
    if ks ≤ 0 then false                         -- monster out-heals our damage
    else
      -- Barrier is an absorbing shield: model it conservatively as extra effective
      -- monster HP the player must chew through before the kill (per-5-turn refresh
      -- deferred — first cut is a flat add).
      let roundsToKill := ceilDiv ((monsterHp + monsterBarrier) * 10000) ks
      if roundsToKill > maxTurns then false
      else
        let ds := dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison
        if ds ≤ 0 then true                       -- we out-sustain the monster (poison-inclusive)
        else
          let roundsToDie := ceilDiv (playerMaxHp * 10000) ds
          if playerFirst then roundsToKill ≤ roundsToDie
          else roundsToKill < roundsToDie

/-! ### Operational fight simulation (refinement target).

A turn-by-turn fight: starting HP totals, alternating attacks by initiative,
each attacker removes its integer per-turn expected hit
`floor(raw*(200+crit)/200)` from the defender's HP. We model the **closed-form
expected** per-turn damage as the integer `floor(hit)`; but `predict_win`
compares via the *rational* `ceil(hp/hit)`, which counts the number of
rational-valued hits to reach 0. The operational sim that EXACTLY matches the
closed form is therefore "how many rational hits of size `raw*(200+crit)/200`
to bring `hp` to ≤ 0", i.e. the least `k` with `k * hit ≥ hp`. We model that
sim as a fuel-bounded recursive accumulator over the rational hit, comparing
when each side reaches 0, and prove the closed form equals it. -/

/-- Least number of rational hits of magnitude `raw*(200+crit)/200` to bring
`hp` to ≤ 0, computed operationally: count turns, accumulating damage, until
`accumulated ≥ hp`. `fuel` bounds the recursion. Returns the turn count, or
`fuel`'s base if exhausted. We accumulate in the common-denominator integer
space (`* 200`): one hit removes `raw*(200+crit)` units from `hp*200`. -/
def simRoundsAux (target step : Int) (acc : Int) (turn : Int) : Nat → Int
  | 0 => turn
  | Nat.succ f =>
    if acc ≥ target then turn
    else simRoundsAux target step (acc + step) (turn + 1) f

/-- Operational rounds-to-zero: number of hits (each `step = raw*(200+crit)`)
to accumulate `≥ target = hp*200`. -/
def simRounds (hp raw crit : Int) (fuel : Nat) : Int :=
  simRoundsAux (hp * 200) (raw * (200 + crit)) 0 0 fuel

/-! ### Theorems. -/

/-- Helper: `ceilDiv n d` for `d > 0`, `n ≥ 0` is the least `k ≥ 0` with
`k * d ≥ n`. We prove the two defining bounds. -/
theorem ceilDiv_mul_ge (n d : Int) (hd : 0 < d) (hn : 0 ≤ n) :
    n ≤ ceilDiv n d * d := by
  unfold ceilDiv
  have hdm := Int.mul_fdiv_add_fmod (n + d - 1) d
  have hmod_lt : Int.fmod (n + d - 1) d < d := Int.fmod_lt_of_pos _ hd
  have hmod_nonneg : 0 ≤ Int.fmod (n + d - 1) d :=
    Int.fmod_nonneg (by omega) (by omega)
  have hcomm : d * Int.fdiv (n + d - 1) d = Int.fdiv (n + d - 1) d * d :=
    Int.mul_comm _ _
  omega

/-- `ceilDiv` is the *least* such `k`: `(ceilDiv n d - 1) * d < n` for `d>0`,
`n ≥ 1`. Together with `ceilDiv_mul_ge` this pins `ceilDiv = ⌈n/d⌉`. -/
theorem ceilDiv_pred_mul_lt (n d : Int) (hd : 0 < d) (hn : 1 ≤ n) :
    (ceilDiv n d - 1) * d < n := by
  unfold ceilDiv
  have hdm := Int.mul_fdiv_add_fmod (n + d - 1) d
  have hmod_lt : Int.fmod (n + d - 1) d < d := Int.fmod_lt_of_pos _ hd
  have hmod_nonneg : 0 ≤ Int.fmod (n + d - 1) d :=
    Int.fmod_nonneg (by omega) (by omega)
  have hcomm : d * Int.fdiv (n + d - 1) d = Int.fdiv (n + d - 1) d * d :=
    Int.mul_comm _ _
  have hsub : (Int.fdiv (n + d - 1) d - 1) * d
      = Int.fdiv (n + d - 1) d * d - d := by
    rw [Int.sub_mul, Int.one_mul]
  omega
/-- `ceilDiv n d ≥ 1` when `d > 0` and `n ≥ 1`. -/
theorem ceilDiv_pos (n d : Int) (hd : 0 < d) (hn : 1 ≤ n) :
    1 ≤ ceilDiv n d := by
  have h := ceilDiv_mul_ge n d hd (by omega)
  -- if ceilDiv ≤ 0 then ceilDiv*d ≤ 0 < n, contradiction
  rcases Int.lt_or_le (ceilDiv n d) 1 with hc | hc
  · exfalso
    have hle : ceilDiv n d ≤ 0 := by omega
    have : ceilDiv n d * d ≤ 0 :=
      Int.mul_nonpos_of_nonpos_of_nonneg hle (by omega)
    omega
  · exact hc

/-! #### Operational sim refinement.

We prove `simRounds hp raw crit fuel = roundsTo hp raw crit` whenever `fuel`
is large enough (≥ the closed-form answer). This is the closed-form = sim
refinement: the fuel-bounded turn-by-turn fight reaches zero in exactly
`roundsTo` turns. -/

/-- Core sim lemma: with `step > 0`, starting from accumulator `acc` at `turn`,
the sim returns `turn + ⌈(target - acc)/step⌉` provided enough fuel and
`acc < target`; if `acc ≥ target` it returns `turn` immediately. We phrase the
"enough fuel" hypothesis as `fuel ≥ k` where `k` is the remaining ceil count. -/
theorem simRoundsAux_eq (target step : Int) (hstep : 0 < step) :
    ∀ (fuel : Nat) (acc turn : Int),
      acc < target →
      (ceilDiv (target - acc) step).toNat ≤ fuel →
      simRoundsAux target step acc turn fuel
        = turn + ceilDiv (target - acc) step := by
  intro fuel
  induction fuel with
  | zero =>
    intro acc turn hlt hfuel
    -- fuel = 0 but ceilDiv (target-acc) step ≥ 1 (since target-acc ≥ 1), so
    -- toNat ≥ 1 > 0 = fuel, contradiction.
    exfalso
    have hpos : 1 ≤ ceilDiv (target - acc) step :=
      ceilDiv_pos (target - acc) step hstep (by omega)
    have : 1 ≤ (ceilDiv (target - acc) step).toNat := by
      omega
    omega
  | succ f ih =>
    intro acc turn hlt hfuel
    unfold simRoundsAux
    have hnotge : ¬ (acc ≥ target) := by omega
    simp only [hnotge, if_false]
    -- one step: acc' = acc + step, turn' = turn + 1
    by_cases hdone : acc + step ≥ target
    · -- after this hit we reach the target: remaining ceil = 1
      have hc1 : ceilDiv (target - acc) step = 1 := by
        have hge : target - acc ≤ step := by omega
        have hlb := ceilDiv_pred_mul_lt (target - acc) step hstep (by omega)
        -- 1 ≤ cd, and (cd-1)*step < target-acc ≤ step ⇒ cd-1 < 1 ⇒ cd ≤ 1
        have hpos : 1 ≤ ceilDiv (target - acc) step :=
          ceilDiv_pos (target - acc) step hstep (by omega)
        -- (cd-1)*step < step. If cd ≥ 2 then (cd-1) ≥ 1 so (cd-1)*step ≥ step. Contradiction.
        rcases Int.lt_or_le (ceilDiv (target - acc) step) 2 with hlt2 | hge2
        · omega
        · exfalso
          have h1 : (1 : Int) ≤ ceilDiv (target - acc) step - 1 := by omega
          have hmul := Int.mul_le_mul_of_nonneg_right h1 (Int.le_of_lt hstep)
          rw [Int.one_mul] at hmul
          omega
      -- recursion hits acc+step ≥ target ⇒ base returns turn+1
      have : simRoundsAux target step (acc + step) (turn + 1) f = turn + 1 := by
        cases f with
        | zero => unfold simRoundsAux; rfl
        | succ f' =>
          unfold simRoundsAux
          simp only [hdone, if_true]
      rw [this, hc1]
    · -- not done: recurse with acc+step
      have hlt' : acc + step < target := by omega
      -- remaining ceil decreases by 1
      have hc : ceilDiv (target - acc) step = ceilDiv (target - (acc + step)) step + 1 := by
        unfold ceilDiv
        have hrw : target - acc + step - 1
            = (target - (acc + step) + step - 1) + 1 * step := by
          rw [Int.one_mul]; omega
        rw [hrw, Int.add_mul_fdiv_right _ _ (by omega : step ≠ 0)]
      have hfuel' : (ceilDiv (target - (acc + step)) step).toNat ≤ f := by
        have : (ceilDiv (target - acc) step).toNat
            = (ceilDiv (target - (acc + step)) step).toNat + 1 := by
          rw [hc]
          have hge0 : 0 ≤ ceilDiv (target - (acc + step)) step := by
            have := ceilDiv_pos (target - (acc + step)) step hstep (by omega)
            omega
          omega
        omega
      rw [ih (acc + step) (turn + 1) hlt' hfuel', hc]
      omega

/-- `simRounds hp raw crit fuel = roundsTo hp raw crit` when `raw > 0`,
`crit ≥ 0`, `hp ≥ 1`, and fuel is at least the closed-form answer. This is the
operational-sim refinement of `roundsTo`. -/
theorem simRounds_eq_roundsTo (hp raw crit : Int)
    (hraw : 0 < raw) (hcrit : 0 ≤ crit) (hhp : 1 ≤ hp)
    (fuel : Nat) (hfuel : (roundsTo hp raw crit).toNat ≤ fuel) :
    simRounds hp raw crit fuel = roundsTo hp raw crit := by
  unfold simRounds roundsTo at *
  have hstep : 0 < raw * (200 + crit) := by
    apply Int.mul_pos hraw; omega
  have htarget : (0 : Int) < hp * 200 :=
    Int.mul_pos (by omega) (by omega)
  have h := simRoundsAux_eq (hp * 200) (raw * (200 + crit)) hstep fuel 0 0
    (by omega)
    (by simpa using hfuel)
  simpa using h

/-- Operational net-step sim: hits of size `step` against `target = hp*10000`. -/
def simRoundsNet (hp step : Int) (fuel : Nat) : Int :=
  simRoundsAux (hp * 10000) step 0 0 fuel

/-- `simRoundsNet hp step fuel = ceilDiv (hp*10000) step` when `step > 0`,
`hp ≥ 1`, fuel sufficient — generalizes `simRounds_eq_roundsTo` to an arbitrary
positive per-round step (which is what the lifesteal NET step produces). -/
theorem simRoundsNet_eq (hp step : Int) (hstep : 0 < step) (hhp : 1 ≤ hp)
    (fuel : Nat) (hfuel : (ceilDiv (hp * 10000) step).toNat ≤ fuel) :
    simRoundsNet hp step fuel = ceilDiv (hp * 10000) step := by
  unfold simRoundsNet
  have htarget : (0:Int) < hp * 10000 := Int.mul_pos (by omega) (by omega)
  have h := simRoundsAux_eq (hp * 10000) step hstep fuel 0 0 (by omega) (by simpa using hfuel)
  simpa using h

/-! #### `predict_win` verdict properties. -/

/-- `maxturns_sound`: `rounds_to_kill > MAX_TURNS ⇒ ¬win` (when the player can
damage the monster net of its lifesteal, `killStep > 0`). -/
theorem maxturns_sound (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier : Int)
    (playerFirst : Bool)
    (hraw : 0 < rawPlayer)
    (hks : 0 < killStep rawPlayer pCrit mCrit mLifesteal mAtkSum)
    (hover : ceilDiv ((monsterHp + monsterBarrier) * 10000)
              (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) > maxTurns) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst = false := by
  unfold predictWin
  rw [if_neg (Int.not_le.mpr hraw)]
  simp only [Int.not_le.mpr hks, if_false]
  rw [if_pos hover]

/-- `predict_win_eq_sim`: the closed-form verdict equals the operational
net-step fight simulation verdict. Same guard ladder: `rawPlayer ≤ 0`,
`killStep ≤ 0` (monster out-heals our damage), max-turns cap, monster-can't-hit,
`dieStep ≤ 0` (we out-sustain), initiative tiebreak. The two `ceilDiv` rounds
are replaced by `simRoundsNet` with sufficient fuel. -/
theorem predict_win_eq_sim (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier : Int)
    (playerFirst : Bool)
    (hmhp : 1 ≤ monsterHp + monsterBarrier) (hphp : 1 ≤ playerMaxHp)
    (fk fd : Nat)
    (hfk : (ceilDiv ((monsterHp + monsterBarrier)*10000)
              (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum)).toNat ≤ fk)
    (hfd : (ceilDiv (playerMaxHp*10000)
              (dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison)).toNat ≤ fd) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst
      = (if rawPlayer ≤ 0 then false
         else
           let ks := killStep rawPlayer pCrit mCrit mLifesteal mAtkSum
           if ks ≤ 0 then false
           else
             let rtk := simRoundsNet (monsterHp + monsterBarrier) ks fk
             if rtk > maxTurns then false
             else
               let ds := dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison
               if ds ≤ 0 then true
               else
                 let rtd := simRoundsNet playerMaxHp ds fd
                 if playerFirst then rtk ≤ rtd else rtk < rtd) := by
  unfold predictWin
  by_cases hrp : rawPlayer ≤ 0
  · simp only [hrp, if_true]
  · simp only [hrp, if_false]
    by_cases hks : killStep rawPlayer pCrit mCrit mLifesteal mAtkSum ≤ 0
    · simp only [hks, if_true]
    · simp only [hks, if_false]
      have hksp : 0 < killStep rawPlayer pCrit mCrit mLifesteal mAtkSum :=
        Int.not_le.mp hks
      have hrtk : simRoundsNet (monsterHp + monsterBarrier)
          (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) fk
          = ceilDiv ((monsterHp + monsterBarrier) * 10000)
              (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) :=
        simRoundsNet_eq (monsterHp + monsterBarrier) _ hksp hmhp fk hfk
      rw [hrtk]
      by_cases hover : ceilDiv ((monsterHp + monsterBarrier) * 10000)
          (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) > maxTurns
      · simp only [hover, if_true]
      · simp only [hover, if_false]
        by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison ≤ 0
        · simp only [hds, if_true]
        · simp only [hds, if_false]
          have hdsp : 0 < dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison :=
            Int.not_le.mp hds
          have hrtd : simRoundsNet playerMaxHp
              (dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison) fd
              = ceilDiv (playerMaxHp * 10000)
                  (dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison) :=
            simRoundsNet_eq playerMaxHp _ hdsp hphp fd hfd
          rw [hrtd]

/-- `ceilDiv` is antitone in its divisor on the nonnegative-numerator domain:
a larger positive divisor never increases the ceil. -/
theorem ceilDiv_antitone_divisor (n d1 d2 : Int)
    (hn : 0 ≤ n) (hd1 : 0 < d1) (hdle : d1 ≤ d2) :
    ceilDiv n d2 ≤ ceilDiv n d1 := by
  have hd2 : 0 < d2 := by omega
  -- c1 = ceilDiv n d1: c1*d1 ≥ n and c1 ≥ 0. Then c1*d2 ≥ c1*d1 ≥ n, so the
  -- least k with k*d2 ≥ n (= ceilDiv n d2) is ≤ c1.
  have hc1ge : n ≤ ceilDiv n d1 * d1 := ceilDiv_mul_ge n d1 hd1 hn
  have hc1nonneg : 0 ≤ ceilDiv n d1 := by
    by_cases hn0 : n = 0
    · unfold ceilDiv
      have h1 : 0 ≤ n + d1 - 1 := by omega
      have h2 : n + d1 - 1 < d1 := by omega
      rw [Int.fdiv_eq_zero_of_lt h1 h2]
      omega
    · have := ceilDiv_pos n d1 hd1 (by omega); omega
  have hc1d2 : n ≤ ceilDiv n d1 * d2 := by
    have : ceilDiv n d1 * d1 ≤ ceilDiv n d1 * d2 := by
      have e1 : ceilDiv n d1 * d1 = d1 * ceilDiv n d1 := Int.mul_comm _ _
      have e2 : ceilDiv n d1 * d2 = d2 * ceilDiv n d1 := Int.mul_comm _ _
      rw [e1, e2]
      exact Int.mul_le_mul_of_nonneg_right hdle hc1nonneg
    omega
  rcases Int.lt_or_le (ceilDiv n d1) (ceilDiv n d2) with hcon | hcon
  case inr => exact hcon
  exfalso
  have hc2_lt : (ceilDiv n d2 - 1) * d2 < n := by
    by_cases hn0 : n = 0
    · have hc2z : ceilDiv n d2 = 0 := by
        unfold ceilDiv
        have h1 : 0 ≤ n + d2 - 1 := by omega
        have h2 : n + d2 - 1 < d2 := by omega
        rw [Int.fdiv_eq_zero_of_lt h1 h2]
      rw [hc2z]
      have hmone : ((0 : Int) - 1) * d2 = -d2 := by
        have : ((0 : Int) - 1) = -1 := by omega
        rw [this, Int.neg_one_mul]
      omega
    · exact ceilDiv_pred_mul_lt n d2 hd2 (by omega)
  have hge : ceilDiv n d1 ≤ ceilDiv n d2 - 1 := by omega
  have hmul : ceilDiv n d1 * d2 ≤ (ceilDiv n d2 - 1) * d2 :=
    Int.mul_le_mul_of_nonneg_right hge (by omega)
  omega

/-- Monotonicity: a larger `raw` (player attack) yields a `roundsTo` that does
not increase. -/
theorem roundsTo_antitone_raw (hp raw1 raw2 crit : Int)
    (hcrit : 0 ≤ crit) (hr1 : 0 < raw1) (hle : raw1 ≤ raw2) (hhp : 0 ≤ hp) :
    roundsTo hp raw2 crit ≤ roundsTo hp raw1 crit := by
  unfold roundsTo
  apply ceilDiv_antitone_divisor
  · exact Int.mul_nonneg hhp (by omega)
  · exact Int.mul_pos hr1 (by omega)
  · exact Int.mul_le_mul_of_nonneg_right hle (by omega)

/-- `predict_win_mono_player`: increasing the player's per-turn raw damage never
flips a win into a loss. -/
theorem predict_win_mono_player
    (raw1 raw2 pCrit monsterHp rawMonster mCrit playerMaxHp
     pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr1 : 0 < raw1) (hle : raw1 ≤ raw2) (hhp : 0 ≤ monsterHp)
    (hbar : 0 ≤ monsterBarrier)
    (hwin : predictWin raw1 pCrit monsterHp rawMonster mCrit playerMaxHp
              pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst = true) :
    predictWin raw2 pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst = true := by
  have hr2 : 0 < raw2 := by omega
  -- killStep is monotone in rawPlayer: ks1 ≤ ks2.
  have hksle : killStep raw1 pCrit mCrit mLifesteal mAtkSum
      ≤ killStep raw2 pCrit mCrit mLifesteal mAtkSum := by
    unfold killStep
    have h50 : 50 * raw1 ≤ 50 * raw2 := by omega
    have hmul : 50 * raw1 * (200 + pCrit) ≤ 50 * raw2 * (200 + pCrit) :=
      Int.mul_le_mul_of_nonneg_right h50 (by omega)
    omega
  unfold predictWin at hwin ⊢
  rw [if_neg (Int.not_le.mpr hr1)] at hwin
  rw [if_neg (Int.not_le.mpr hr2)]
  -- ks1 > 0 (else hwin false).
  by_cases hks1 : killStep raw1 pCrit mCrit mLifesteal mAtkSum ≤ 0
  · rw [if_pos hks1] at hwin; exact absurd hwin (by decide)
  · rw [if_neg hks1] at hwin
    have hks1p : 0 < killStep raw1 pCrit mCrit mLifesteal mAtkSum :=
      Int.not_le.mp hks1
    have hks2p : 0 < killStep raw2 pCrit mCrit mLifesteal mAtkSum := by omega
    rw [if_neg (Int.not_le.mpr hks2p)]
    -- rounds-to-kill antitone in the divisor: rtk2 ≤ rtk1 (effective HP = hp+barrier).
    have hrtkle : ceilDiv ((monsterHp + monsterBarrier) * 10000)
          (killStep raw2 pCrit mCrit mLifesteal mAtkSum)
        ≤ ceilDiv ((monsterHp + monsterBarrier) * 10000)
          (killStep raw1 pCrit mCrit mLifesteal mAtkSum) :=
      ceilDiv_antitone_divisor _ _ _ (Int.mul_nonneg (by omega) (by omega)) hks1p hksle
    -- not over cap (else hwin false).
    by_cases hover1 : ceilDiv ((monsterHp + monsterBarrier) * 10000)
        (killStep raw1 pCrit mCrit mLifesteal mAtkSum) > maxTurns
    · rw [if_pos hover1] at hwin; exact absurd hwin (by decide)
    · rw [if_neg hover1] at hwin
      have hover2 : ¬ ceilDiv ((monsterHp + monsterBarrier) * 10000)
          (killStep raw2 pCrit mCrit mLifesteal mAtkSum) > maxTurns := by
        omega
      rw [if_neg hover2]
      -- the remaining branches are independent of rawPlayer.
      by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison ≤ 0
      · rw [if_pos hds]
      · rw [if_neg hds] at hwin ⊢
        cases playerFirst with
        | true =>
          simp only [if_true] at hwin ⊢
          have := of_decide_eq_true hwin
          exact decide_eq_true (by omega)
        | false =>
          simp only [Bool.false_eq_true, if_false] at hwin ⊢
          have := of_decide_eq_true hwin
          exact decide_eq_true (by omega)

/-- `predict_win_mono_monsterhp`: decreasing the monster's HP never flips a win
into a loss. (killStep does not depend on monsterHp, so the kill-rounds numerator
shrinks while the divisor is fixed.) -/
theorem predict_win_mono_monsterhp
    (rawPlayer pCrit monsterHp1 monsterHp2 rawMonster mCrit playerMaxHp
     pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr : 0 < rawPlayer)
    (hhp2 : 0 ≤ monsterHp2) (hle : monsterHp2 ≤ monsterHp1) (hbar : 0 ≤ monsterBarrier)
    (hwin : predictWin rawPlayer pCrit monsterHp1 rawMonster mCrit playerMaxHp
              pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst = true) :
    predictWin rawPlayer pCrit monsterHp2 rawMonster mCrit playerMaxHp
      pLifesteal pAtkSum mLifesteal mAtkSum monsterPoison monsterBarrier playerFirst = true := by
  unfold predictWin at hwin ⊢
  rw [if_neg (Int.not_le.mpr hr)] at hwin
  rw [if_neg (Int.not_le.mpr hr)]
  by_cases hks : killStep rawPlayer pCrit mCrit mLifesteal mAtkSum ≤ 0
  · rw [if_pos hks] at hwin; exact absurd hwin (by decide)
  · rw [if_neg hks] at hwin ⊢
    have hksp : 0 < killStep rawPlayer pCrit mCrit mLifesteal mAtkSum :=
      Int.not_le.mp hks
    -- rounds-to-kill monotone in the numerator (effective HP = hp+barrier): rtk2 ≤ rtk1.
    have hrtkle : ceilDiv ((monsterHp2 + monsterBarrier) * 10000)
          (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum)
        ≤ ceilDiv ((monsterHp1 + monsterBarrier) * 10000)
          (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) := by
      unfold ceilDiv
      apply fdiv_le_fdiv_of_le _ _ _ hksp
      · have : 0 ≤ (monsterHp2 + monsterBarrier) * 10000 :=
          Int.mul_nonneg (by omega) (by omega)
        omega
      · have : (monsterHp2 + monsterBarrier) * 10000 ≤ (monsterHp1 + monsterBarrier) * 10000 :=
          Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
        omega
    by_cases hover1 : ceilDiv ((monsterHp1 + monsterBarrier) * 10000)
        (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) > maxTurns
    · rw [if_pos hover1] at hwin; exact absurd hwin (by decide)
    · rw [if_neg hover1] at hwin
      have hover2 : ¬ ceilDiv ((monsterHp2 + monsterBarrier) * 10000)
          (killStep rawPlayer pCrit mCrit mLifesteal mAtkSum) > maxTurns := by
        omega
      rw [if_neg hover2]
      by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pAtkSum monsterPoison ≤ 0
      · rw [if_pos hds]
      · rw [if_neg hds] at hwin ⊢
        cases playerFirst with
        | true =>
          simp only [if_true] at hwin ⊢
          have := of_decide_eq_true hwin
          exact decide_eq_true (by omega)
        | false =>
          simp only [Bool.false_eq_true, if_false] at hwin ⊢
          have := of_decide_eq_true hwin
          exact decide_eq_true (by omega)

end Formal.PredictWin
