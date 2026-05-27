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

/-- The closed-form `predict_win` verdict from the resolved stat tuple.

* `rawPlayer`  = Σ player element damages vs monster resistances (≥ 0).
* `pCrit`      = player critical strike %.
* `monsterHp`  = monster HP.
* `rawMonster` = Σ monster element damages vs player resistances (≥ 0).
* `mCrit`      = monster critical strike %.
* `playerMaxHp`= player max HP.
* `playerFirst`= `player_initiative ≥ monster_initiative`.

The crit guard `200 + crit > 0` holds since crit ≥ 0 in the game API, but the
denominator positivity we actually need is `raw*(200+crit) > 0`, established
from `raw > 0 ∧ crit ≥ 0` at the call site / in the theorems. -/
def predictWin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool) : Bool :=
  if rawPlayer ≤ 0 then false
  else
    let roundsToKill := roundsTo monsterHp rawPlayer pCrit
    if roundsToKill > maxTurns then false
    else if rawMonster ≤ 0 then true
    else
      let roundsToDie := roundsTo playerMaxHp rawMonster mCrit
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

/-! #### `predict_win` verdict properties. -/

/-- `maxturns_sound`: `rounds_to_kill > MAX_TURNS ⇒ ¬win`. -/
theorem maxturns_sound (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool)
    (hraw : 0 < rawPlayer)
    (hover : roundsTo monsterHp rawPlayer pCrit > maxTurns) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = false := by
  unfold predictWin
  have hnle : ¬ (rawPlayer ≤ 0) := by omega
  simp only [hnle, if_false, hover, if_true]

/-- `predict_win_eq_sim`: the closed-form verdict equals the verdict of the
operational fight simulation. The sim computes both sides' rounds-to-zero by
the alternating-attack turn count (`simRounds`), then applies the SAME
verdict logic the Python uses (max-turns cap, monster-can't-hit short-circuit,
initiative tiebreak). With enough fuel on each `simRounds` call to reach the
closed-form answer, the two coincide. This is the refinement theorem
∀ stat tuples in the modeled domain (`rawPlayer > 0` when reached, crit ≥ 0,
HP ≥ 1). -/
theorem predict_win_eq_sim (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hmc : 0 ≤ mCrit)
    (hmhp : 1 ≤ monsterHp) (hphp : 1 ≤ playerMaxHp)
    (fk fd : Nat)
    (hfk : (roundsTo monsterHp rawPlayer pCrit).toNat ≤ fk)
    (hfd : (roundsTo playerMaxHp rawMonster mCrit).toNat ≤ fd) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst
      = (if rawPlayer ≤ 0 then false
         else
           let rtk := simRounds monsterHp rawPlayer pCrit fk
           if rtk > maxTurns then false
           else if rawMonster ≤ 0 then true
           else
             let rtd := simRounds playerMaxHp rawMonster mCrit fd
             if playerFirst then rtk ≤ rtd else rtk < rtd) := by
  unfold predictWin
  by_cases hrp : rawPlayer ≤ 0
  · simp only [hrp, if_true]
  · have hrpp : 0 < rawPlayer := by omega
    have hkill : simRounds monsterHp rawPlayer pCrit fk = roundsTo monsterHp rawPlayer pCrit :=
      simRounds_eq_roundsTo monsterHp rawPlayer pCrit hrpp hpc hmhp fk hfk
    simp only [hrp, if_false]
    rw [hkill]
    by_cases hover : roundsTo monsterHp rawPlayer pCrit > maxTurns
    · simp only [hover, if_true]
    · simp only [hover, if_false]
      by_cases hrm : rawMonster ≤ 0
      · simp only [hrm, if_true]
      · have hrmp : 0 < rawMonster := by omega
        have hdie : simRounds playerMaxHp rawMonster mCrit fd = roundsTo playerMaxHp rawMonster mCrit :=
          simRounds_eq_roundsTo playerMaxHp rawMonster mCrit hrmp hmc hphp fd hfd
        simp only [hrm, if_false]
        rw [hdie]

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
    (raw1 raw2 pCrit monsterHp rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr1 : 0 < raw1) (hle : raw1 ≤ raw2) (hhp : 0 ≤ monsterHp)
    (hwin : predictWin raw1 pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = true) :
    predictWin raw2 pCrit monsterHp rawMonster mCrit playerMaxHp playerFirst = true := by
  have hr2 : 0 < raw2 := by omega
  unfold predictWin at hwin ⊢
  rw [if_neg (by omega : ¬ raw1 ≤ 0)] at hwin
  rw [if_neg (by omega : ¬ raw2 ≤ 0)]
  simp only at hwin ⊢
  -- roundsTo with raw2 ≤ roundsTo with raw1 (antitone)
  have hmono := roundsTo_antitone_raw monsterHp raw1 raw2 pCrit hpc hr1 hle hhp
  by_cases hover1 : roundsTo monsterHp raw1 pCrit > maxTurns
  · -- raw1 already over cap ⇒ hwin = false, contradiction
    rw [if_pos hover1] at hwin
    exact absurd hwin (by simp)
  · rw [if_neg hover1] at hwin
    have hover2 : ¬ roundsTo monsterHp raw2 pCrit > maxTurns := by omega
    rw [if_neg hover2]
    by_cases hrm : rawMonster ≤ 0
    · rw [if_pos hrm]
    · rw [if_neg hrm] at hwin ⊢
      -- verdict compares roundsToKill against roundsToDie; smaller kill helps
      cases playerFirst <;>
        simp only [Bool.false_eq_true, if_false, if_true, decide_eq_true_eq] at hwin ⊢ <;>
        omega

/-- `predict_win_mono_monsterhp`: decreasing the monster's HP never flips a win
into a loss. -/
theorem predict_win_mono_monsterhp
    (rawPlayer pCrit monsterHp1 monsterHp2 rawMonster mCrit playerMaxHp : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr : 0 < rawPlayer)
    (hhp2 : 0 ≤ monsterHp2) (hle : monsterHp2 ≤ monsterHp1)
    (hwin : predictWin rawPlayer pCrit monsterHp1 rawMonster mCrit playerMaxHp playerFirst = true) :
    predictWin rawPlayer pCrit monsterHp2 rawMonster mCrit playerMaxHp playerFirst = true := by
  unfold predictWin at hwin ⊢
  rw [if_neg (by omega : ¬ rawPlayer ≤ 0)] at hwin
  rw [if_neg (by omega : ¬ rawPlayer ≤ 0)]
  simp only at hwin ⊢
  -- monotonicity of roundsTo in the hp numerator (smaller hp ⇒ ≤ rounds)
  have hmono : roundsTo monsterHp2 rawPlayer pCrit ≤ roundsTo monsterHp1 rawPlayer pCrit := by
    unfold roundsTo ceilDiv
    have hd : 0 < rawPlayer * (200 + pCrit) := Int.mul_pos hr (by omega)
    have h200 : monsterHp2 * 200 ≤ monsterHp1 * 200 :=
      Int.mul_le_mul_of_nonneg_right hle (by omega)
    have ha0 : 0 ≤ monsterHp2 * 200 + rawPlayer * (200 + pCrit) - 1 := by
      have := Int.mul_nonneg hhp2 (by omega : (0:Int) ≤ 200)
      omega
    exact fdiv_le_fdiv_of_le _ _ _ hd ha0 (by omega)
  by_cases hover1 : roundsTo monsterHp1 rawPlayer pCrit > maxTurns
  · rw [if_pos hover1] at hwin
    exact absurd hwin (by simp)
  · rw [if_neg hover1] at hwin
    have hover2 : ¬ roundsTo monsterHp2 rawPlayer pCrit > maxTurns := by omega
    rw [if_neg hover2]
    by_cases hrm : rawMonster ≤ 0
    · rw [if_pos hrm]
    · rw [if_neg hrm] at hwin ⊢
      cases playerFirst <;>
        simp only [Bool.false_eq_true, if_false, if_true, decide_eq_true_eq] at hwin ⊢ <;>
        omega

end Formal.PredictWin
