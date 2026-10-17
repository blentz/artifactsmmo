-- @concept: combat @property: validity, monotonicity
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
* `rounds_to_kill > MAX_TURNS` (= 100)   ⇒ False, where `rounds_to_kill` is
  `killRounds`: the monster's barrier absorbs hits and is refreshed every 5
  monster turns ("The barrier" below); without one it is `⌈hp / hit⌉`
* `monster_hit ≤ 0` (monster raw = 0)    ⇒ True
* otherwise: `rounds_to_kill ≤ rounds_to_die` if the player goes first
  (`playerFirst`, an input: higher initiative, a tie to the higher HP — server
  logs 2026-10-16, Python `combat.moves_first`), else strict `<`.

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

/-- One CRITICAL turn's damage over the four elements: each element's net hit
×1.5, rounded half up per element (`(3d + 1) / 2`) — the server's rule, read off
2026-10-15 fight logs (77 → 116, 83 → 125, 64 → 96). Mirrors `combat._crit_hit`. -/
def critHit (a0 d0 r0 a1 d1 r1 a2 d2 r2 a3 d3 r3 : Int) : Int :=
  (3 * elementDamage a0 d0 r0 + 1) / 2 + (3 * elementDamage a1 d1 r1 + 1) / 2
    + (3 * elementDamage a2 d2 r2 + 1) / 2 + (3 * elementDamage a3 d3 r3 + 1) / 2

/-- The HP a lifesteal of `lifesteal`% heals on a crit turn dealing `critHit`:
the share rounded half up. Server logs 2026-10-17 (2,327 heals, three
characters): 15% of 165 heals 25, of 196 heals 29, of 152 heals 23. A crit that
kills heals nothing (the fight is over); the walk models that, this mean does not. -/
def lifestealHeal (lifesteal critHit : Int) : Int := (2 * lifesteal * critHit + 100) / 200

/-- Per-round net HP removed from the MONSTER, in the ×10000 integer space: the
player's expected per-turn damage `50*rawPlayer*(200+pCrit)` MINUS the monster's
expected heal-on-crit `mCrit% × lifestealHeal mLifesteal mCritHit` (the monster
sustains itself with lifesteal; ×10000 = crit% × heal × 100). With
`mLifesteal = 0` this is `50*rawPlayer*(200+pCrit)`, and
`ceilDiv (hp*10000) (50*r*(200+c)) = ceilDiv (hp*200) (r*(200+c))` (a common 50×
scale, ceilDiv being scale-invariant), so the lifesteal-free verdict is exactly the
old one. `mCritHit` is the monster's crit-turn damage (`critHit`). -/
def killStep (rawPlayer pCrit mCrit mLifesteal mCritHit : Int) : Int :=
  50 * rawPlayer * (200 + pCrit) - mCrit * lifestealHeal mLifesteal mCritHit * 100

/-- Net per-round monster HP loss (×10000): the base `killStep` MINUS the monster's
per-turn healing regen. `monsterHealing` is the regen percent (of the monster's HP)
applied every 3 turns; we model it conservatively as the FULL per-3-turn amount
applied EVERY turn — a 3× upper bound that keeps the arithmetic exact-integer:
`monsterHealing% × monsterHp × 10000 = monsterHealing * monsterHp * 100`. A healing
monster we cannot out-damage has `killStepNet ≤ 0` ⇒ unkillable (the existing
`ks ≤ 0` guard). With `monsterHealing = 0` this is exactly `killStep`. -/
def killStepNet (rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
    playerMaxHp monsterVoidDrain monsterBubble monsterSunShield : Int) : Int :=
  killStep rawPlayer pCrit mCrit mLifesteal mCritHit - monsterHealing * monsterHp * 100
    - monsterVoidDrain * playerMaxHp * 100
    - (monsterBubble + monsterSunShield) * rawPlayer * (200 + pCrit) / 2

/-- Per-round net HP removed from the PLAYER (×10000): monster damage MINUS the
player's expected heal-on-crit `pCrit% × lifestealHeal pLifesteal pCritHit`
(`pCritHit` the player's crit-turn damage, `critHit`), PLUS the monster's flat per-turn
`monsterPoison` DoT, PLUS the monster's `monsterBurn` DoT — a percent of the
MONSTER's total attack `mAtkSum`, the first tick unrounded, charged every round
(the real ticks decay by a tenth each turn, so this bounds each one).
`monsterBurn*mAtkSum*100` = the percent (÷100) × mAtkSum × 10000. -/
def dieStep (rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
    playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison
    rawPlayer monsterGreed monsterEnchantedMirror mAtkSum : Int) : Int :=
  50 * rawMonster * (200 + mCrit) - pCrit * lifestealHeal pLifesteal pCritHit * 100
    + max 0 (monsterPoison - playerAntipoison) * 10000
    + monsterBurn * mAtkSum * 100 + monsterVoidDrain * playerMaxHp * 100
    + monsterBerserk * rawMonster * (200 + mCrit) / 2
    + monsterFrenzy * rawMonster * (200 + mCrit) / 2
    + 9 * monsterGreed * rawMonster * (200 + mCrit) / 2
    + monsterEnchantedMirror * rawPlayer * (200 + pCrit) / 2

/-! ### The barrier.

The effect text (`GET /effects/barrier`): "At the start of the fight and every 5
played turns, gain a protective barrier of {value} HP. All attacks are
redirected to this barrier until it is destroyed." Lor v king_slime,
2026-10-17: the barrier is raised at the start and SET back to full at the
start of the monster's 5th and 10th turns, and a hit's excess passes through
("36 absorbed, 15 through"). Ruling (no monster-first barrier fight is on
record): the refresh is on the monster's OWN 5th turn whoever moves first. So
the player's hits come in blocks against one barrier each: the first
`firstLen` hits (5 when the player moves first, the refresh following its 5th
hit; 4 when the monster does, the refresh coming before the player's 5th hit),
then blocks of 5. The flat add this replaced (HP + barrier, no refresh) gave
Lor 10 hits to kill and P(win) 0.999 at 546 HP; the slime needs 12.

`killRounds` is the closed form (`fight_terms_core.kill_rounds`); `killSim` is
the round-by-round walk (`absorb` + `refresh`, `fight_odds_core`) it is proved
equal to (`killSim_eq_killRounds`). -/

/-- The monster's turns between barrier refreshes (`fight_terms_core.BARRIER_PERIOD`;
the `5` in `refresh` and `killRoundsCore`). -/
def barrierPeriod : Int := 5

/-- A hit of `a` against a barrier of `s` (`fight_odds_core.absorb`): what goes
through to HP and the barrier left. A non-positive amount (a mean-modelled heal
past the hit) goes to HP and leaves the barrier alone. -/
def absorb (s a : Int) : Int × Int :=
  if a ≤ 0 then (a, s) else (max 0 (a - s), max 0 (s - a))

/-- The barrier after the monster's turn of round `r` starts (`fight_odds_core._refresh`):
SET to `full` every `barrierPeriod`-th round. -/
def refresh (s full r : Int) : Int := if r % 5 = 0 then full else s

/-- The barrier a player hit of round `r` meets: the monster moving first has
refreshed it already. -/
def preShield (pf : Bool) (s full r : Int) : Int := if pf then s else refresh s full r

/-- The barrier carried into round `r + 1` from what a hit of round `r` left:
the monster moving second refreshes it after the player's hit. -/
def postShield (pf : Bool) (s full r : Int) : Int := if pf then refresh s full r else s

/-- The hits before the first refresh: 5 when the player moves first, 4 when the
monster does. -/
def firstLen (pf : Bool) : Int := if pf then 5 else 4

/-- What is left of the HP after the first block (×10000). -/
def kLeft (H B ks : Int) (pf : Bool) : Int := H - max 0 (firstLen pf * ks - B)

/-- What a full later block of 5 hits gets through the barrier (×10000). -/
def kGap (B ks : Int) : Int := 5 * ks - B

/-- The full later blocks before the last one. -/
def kBlocks (H B ks : Int) (pf : Bool) : Int := ceilDiv (kLeft H B ks pf) (kGap B ks) - 1

/-- The closed form over the ×10000 HP `H` and barrier `B` (`fight_terms_core.kill_rounds`):
`H + B ≤ firstLen·ks` dies in the first block; `5·ks ≤ B` never gets a block
through (`maxTurns + 1`, over the cap); else the first block, `kBlocks` full
blocks of `kGap` each, and the hits of the last block. With `B = 0` it is
`⌈H / ks⌉` (`killRounds_zero_barrier`). -/
def killRoundsCore (H B ks : Int) (pf : Bool) : Int :=
  if H + B ≤ firstLen pf * ks then ceilDiv (H + B) ks
  else if kGap B ks ≤ 0 then maxTurns + 1
  else firstLen pf + kBlocks H B ks pf * 5
    + ceilDiv (kLeft H B ks pf - kBlocks H B ks pf * kGap B ks + B) ks

/-- Rounds until a monster of `hp` behind a `barrier` dies at a positive kill
step `ks` (×10000) a round, the player moving first iff `pf`. -/
def killRounds (hp barrier ks : Int) (pf : Bool) : Int :=
  killRoundsCore (hp * 10000) (barrier * 10000) ks pf

/-- The barrier never lets a block through: `killRoundsCore` is the `maxTurns + 1` sentinel. -/
def walledCore (H B ks : Int) (pf : Bool) : Prop :=
  ¬ H + B ≤ firstLen pf * ks ∧ kGap B ks ≤ 0

/-- `walledCore` at the unscaled HP and barrier. -/
def walled (hp barrier ks : Int) (pf : Bool) : Prop :=
  walledCore (hp * 10000) (barrier * 10000) ks pf

/-- The round-by-round kill walk from round `r`, monster pool `m`, barrier left
`s`, refreshing to `full`: the round the monster dies in, or the round reached
when `fuel` runs out. -/
def killSim (ks full : Int) (pf : Bool) : Nat → Int → Int → Int → Int
  | 0, r, _, _ => r
  | f + 1, r, m, s =>
    if m - (absorb (preShield pf s full r) ks).1 ≤ 0 then r
    else killSim ks full pf f (r + 1) (m - (absorb (preShield pf s full r) ks).1)
      (postShield pf (absorb (preShield pf s full r) ks).2 full r)

/-- The walk kills the monster with exactly its `n + 1`-th hit from round `r`. -/
def killsAt (ks full : Int) (pf : Bool) : Nat → Int → Int → Int → Prop
  | 0, r, m, s => m - (absorb (preShield pf s full r) ks).1 ≤ 0
  | n + 1, r, m, s => ¬ m - (absorb (preShield pf s full r) ks).1 ≤ 0 ∧
      killsAt ks full pf n (r + 1) (m - (absorb (preShield pf s full r) ks).1)
        (postShield pf (absorb (preShield pf s full r) ks).2 full r)

/-- `firstLen` as a hit count. -/
def firstBlock (pf : Bool) : Nat := if pf then 5 else 4

/-- Hits since the last refresh before hit `i + 1`. -/
def blockPos (pf : Bool) (i : Nat) : Nat :=
  if i < firstBlock pf then i else (i - firstBlock pf) % 5

/-- What `c` hits of `ks` get through a full barrier `B`. -/
def bthrough (ks B : Int) (c : Nat) : Int := max 0 ((c : Int) * ks - B)

/-- The walk's total damage through the barrier after `i` hits, in closed form:
the first block, the full blocks of 5, the partial block. -/
def cumThrough (ks B : Int) (pf : Bool) (i : Nat) : Int :=
  if i < firstBlock pf then bthrough ks B i
  else bthrough ks B (firstBlock pf) + (((i - firstBlock pf) / 5 : Nat) : Int) * bthrough ks B 5
    + bthrough ks B ((i - firstBlock pf) % 5)

/-- The barrier hit `i + 1` meets. -/
def effShield (ks B : Int) (pf : Bool) (i : Nat) : Int := max 0 (B - (blockPos pf i : Int) * ks)

/-- The barrier the walk carries after `i` hits. -/
def stShield (ks B : Int) (pf : Bool) : Nat → Int
  | 0 => B
  | i + 1 => if pf then effShield ks B pf (i + 1) else max 0 (effShield ks B pf i - ks)

def predictWin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn
    monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
    monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool) : Bool :=
  if rawPlayer ≤ 0 then false
  else
    let ks := killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp monsterVoidDrain monsterBubble monsterSunShield
    if ks ≤ 0 then false                         -- monster out-damages/out-heals us
    else
      -- Barrier: an absorbing shield refreshed every 5 monster turns (`killRounds`).
      let roundsToKill := killRounds monsterHp monsterBarrier ks playerFirst
      if roundsToKill > maxTurns then false
      -- Reconstitution: the monster regains ALL HP every `monsterReconstitution`
      -- turns. If we cannot kill it strictly faster than that period, it fully heals
      -- before dying ⇒ unwinnable (conservative: win needs roundsToKill < period).
      else if 0 < monsterReconstitution ∧ monsterReconstitution ≤ roundsToKill then false
      else
        let ds := dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer monsterGreed monsterEnchantedMirror mAtkSum
        if ds ≤ 0 then true                       -- we out-sustain the monster (poison+burn-inclusive)
        else
          let roundsToDie := ceilDiv (playerMaxHp * 10000) ds
          if playerFirst then roundsToKill ≤ roundsToDie
          else roundsToKill < roundsToDie

/-- Sentinel for the `dieStep ≤ 0` (out-sustain) win branch of `combatMargin`.
Always positive: `0 < winMargin`. -/
def winMargin : Int := maxTurns + 1

/-- Sentinel for all losing / unkillable branches of `combatMargin`.
Always negative: `loseMargin < 0`. -/
def loseMargin : Int := -(maxTurns + 1)

/-- Signed margin whose sign equals the `predictWin` verdict.

Invariant: `predictWin ... playerFirst = (combatMargin ... playerFirst > 0)`.

Mirrors `predictWin`'s exact branch structure, returning `loseMargin` / `winMargin`
at the boolean exits and `roundsToDie - roundsToKill + (if playerFirst then 1 else 0)`
in the numeric regime (so win ⟺ value > 0, matching `roundsToKill ≤ roundsToDie`
when `playerFirst` and strict `<` otherwise). -/
def combatMargin (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn
    monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
    monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool) : Int :=
  if rawPlayer ≤ 0 then loseMargin
  else
    let ks := killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield
    if ks ≤ 0 then loseMargin
    else
      let roundsToKill := killRounds monsterHp monsterBarrier ks playerFirst
      if roundsToKill > maxTurns then loseMargin
      else if 0 < monsterReconstitution ∧ monsterReconstitution ≤ roundsToKill then loseMargin
      else
        let ds := dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
            playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison
            rawPlayer monsterGreed monsterEnchantedMirror mAtkSum
        if ds ≤ 0 then winMargin
        else
          let roundsToDie := ceilDiv (playerMaxHp * 10000) ds
          roundsToDie - roundsToKill + (if playerFirst then 1 else 0)

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

/-! #### The barrier walk and its closed form.

`cumThrough i` is the walk's total damage through the barrier after `i` hits in
closed form; the walk's state after `i` hits is `(H - cumThrough i, stShield i)`
(`hitThrough`, `hitShield`), so it kills with the least `n` whose `cumThrough n`
reaches `H`, and `killRoundsCore` is that `n` (`killRoundsCore_spec`). -/

theorem natCast_succ_mul (c : Nat) (k : Int) : ((c + 1 : Nat) : Int) * k = (c : Int) * k + k := by
  rw [Int.natCast_add, Int.add_mul, Int.natCast_one, Int.one_mul]

theorem firstBlock_cast (pf : Bool) : ((firstBlock pf : Nat) : Int) = firstLen pf := by
  cases pf <;> rfl

theorem firstBlock_bounds (pf : Bool) : 4 ≤ firstBlock pf ∧ firstBlock pf ≤ 5 := by
  cases pf <;> decide

theorem firstLen_bounds (pf : Bool) : 4 ≤ firstLen pf ∧ firstLen pf ≤ 5 := by
  cases pf <;> decide

theorem bthrough_zero (ks B : Int) (hB : 0 ≤ B) : bthrough ks B 0 = 0 := by
  unfold bthrough; simp only [Int.natCast_zero, Int.zero_mul]; omega

theorem bthrough_succ (ks B : Int) (c : Nat) :
    bthrough ks B (c + 1) = max 0 ((c : Int) * ks + ks - B) := by
  unfold bthrough; rw [natCast_succ_mul]

theorem bthrough_nonneg (ks B : Int) (c : Nat) : 0 ≤ bthrough ks B c := by
  unfold bthrough; omega

theorem cumThrough_first (ks B : Int) (pf : Bool) (i : Nat) (h : i < firstBlock pf) :
    cumThrough ks B pf i = bthrough ks B i := by
  unfold cumThrough; rw [if_pos h]

theorem cumThrough_block (ks B : Int) (pf : Bool) (q r : Nat) (hr : r < 5) :
    cumThrough ks B pf (firstBlock pf + 5 * q + r)
      = bthrough ks B (firstBlock pf) + (q : Int) * bthrough ks B 5 + bthrough ks B r := by
  unfold cumThrough
  rw [if_neg (by omega)]
  have h1 : (firstBlock pf + 5 * q + r - firstBlock pf) / 5 = q := by omega
  have h2 : (firstBlock pf + 5 * q + r - firstBlock pf) % 5 = r := by omega
  rw [h1, h2]

theorem cumThrough_le_first (ks B : Int) (pf : Bool) (i : Nat) (h : i ≤ firstBlock pf)
    (hB : 0 ≤ B) : cumThrough ks B pf i = bthrough ks B i := by
  by_cases hi : i < firstBlock pf
  · exact cumThrough_first ks B pf i hi
  · obtain rfl : i = firstBlock pf := by omega
    have := cumThrough_block ks B pf 0 0 (by omega)
    simp only [Nat.mul_zero, Nat.add_zero, Int.natCast_zero, Int.zero_mul, Int.add_zero] at this
    rw [this, bthrough_zero _ _ hB, Int.add_zero]

theorem cumThrough_zero (ks B : Int) (pf : Bool) (hB : 0 ≤ B) : cumThrough ks B pf 0 = 0 := by
  rw [cumThrough_le_first ks B pf 0 (by have := firstBlock_bounds pf; omega) hB,
    bthrough_zero _ _ hB]

/-- One more hit adds what the block's next hit gets through. -/
theorem cumThrough_step (ks B : Int) (pf : Bool) (hB : 0 ≤ B) (i : Nat) :
    cumThrough ks B pf (i + 1)
      = cumThrough ks B pf i + bthrough ks B (blockPos pf i + 1) - bthrough ks B (blockPos pf i) := by
  by_cases h1 : i + 1 < firstBlock pf
  · rw [cumThrough_first _ _ _ _ h1, cumThrough_first _ _ _ _ (by omega)]
    unfold blockPos; rw [if_pos (by omega)]; omega
  by_cases h2 : i < firstBlock pf
  · rw [cumThrough_le_first _ _ _ _ (by omega) hB, cumThrough_first _ _ _ _ h2]
    unfold blockPos; rw [if_pos h2]; omega
  obtain ⟨q, r, hr, rfl⟩ : ∃ q r : Nat, r < 5 ∧ i = firstBlock pf + 5 * q + r :=
    ⟨(i - firstBlock pf) / 5, (i - firstBlock pf) % 5, by omega, by omega⟩
  have hbp : blockPos pf (firstBlock pf + 5 * q + r) = r := by
    unfold blockPos; rw [if_neg (by omega)]; omega
  rw [hbp]
  by_cases hr4 : r < 4
  · have e : firstBlock pf + 5 * q + r + 1 = firstBlock pf + 5 * q + (r + 1) := by omega
    rw [e, cumThrough_block _ _ _ _ _ (by omega), cumThrough_block _ _ _ _ _ hr]; omega
  · obtain rfl : r = 4 := by omega
    have e : firstBlock pf + 5 * q + 4 + 1 = firstBlock pf + 5 * (q + 1) + 0 := by omega
    rw [e, cumThrough_block _ _ _ _ _ (by omega), cumThrough_block _ _ _ _ _ hr,
      bthrough_zero _ _ hB, natCast_succ_mul]
    simp only [Nat.reduceAdd]; omega

theorem cumThrough_succ_ge (ks B : Int) (pf : Bool) (hk : 0 ≤ ks) (hB : 0 ≤ B) (i : Nat) :
    cumThrough ks B pf i ≤ cumThrough ks B pf (i + 1) := by
  rw [cumThrough_step ks B pf hB, bthrough_succ]; unfold bthrough; omega

/-- The walk's total through the barrier never falls as hits land. -/
theorem cumThrough_mono (ks B : Int) (pf : Bool) (hk : 0 ≤ ks) (hB : 0 ≤ B) (i j : Nat)
    (h : i ≤ j) : cumThrough ks B pf i ≤ cumThrough ks B pf j := by
  induction j with
  | zero => obtain rfl : i = 0 := by omega
            exact Int.le_refl _
  | succ j ih =>
    by_cases hij : i ≤ j
    · exact Int.le_trans (ih hij) (cumThrough_succ_ge ks B pf hk hB j)
    · obtain rfl : i = j + 1 := by omega
      exact Int.le_refl _

/-- A larger kill step gets no less through. -/
theorem cumThrough_mono_ks (k1 k2 B : Int) (pf : Bool) (hle : k1 ≤ k2) (i : Nat) :
    cumThrough k1 B pf i ≤ cumThrough k2 B pf i := by
  have hb : ∀ c : Nat, bthrough k1 B c ≤ bthrough k2 B c := by
    intro c; unfold bthrough
    have : (c : Int) * k1 ≤ (c : Int) * k2 := Int.mul_le_mul_of_nonneg_left hle (Int.natCast_nonneg c)
    omega
  unfold cumThrough; split
  · exact hb _
  · have hq : (((i - firstBlock pf) / 5 : Nat) : Int) * bthrough k1 B 5
        ≤ (((i - firstBlock pf) / 5 : Nat) : Int) * bthrough k2 B 5 :=
      Int.mul_le_mul_of_nonneg_left (hb 5) (Int.natCast_nonneg _)
    have := hb (firstBlock pf); have := hb ((i - firstBlock pf) % 5); omega

/-- A larger barrier lets no more through. -/
theorem cumThrough_anti_barrier (ks B1 B2 : Int) (pf : Bool) (hle : B1 ≤ B2) (i : Nat) :
    cumThrough ks B2 pf i ≤ cumThrough ks B1 pf i := by
  have hb : ∀ c : Nat, bthrough ks B2 c ≤ bthrough ks B1 c := by
    intro c; unfold bthrough; omega
  unfold cumThrough; split
  · exact hb _
  · have hq : (((i - firstBlock pf) / 5 : Nat) : Int) * bthrough ks B2 5
        ≤ (((i - firstBlock pf) / 5 : Nat) : Int) * bthrough ks B1 5 :=
      Int.mul_le_mul_of_nonneg_left (hb 5) (Int.natCast_nonneg _)
    have := hb (firstBlock pf); have := hb ((i - firstBlock pf) % 5); omega

theorem effShield_next (ks B : Int) (pf : Bool) (hk : 0 ≤ ks) (i : Nat)
    (h : blockPos pf (i + 1) = blockPos pf i + 1) :
    max 0 (effShield ks B pf i - ks) = effShield ks B pf (i + 1) := by
  unfold effShield; rw [h, natCast_succ_mul]; omega

/-- The barrier hit `i + 1` meets is the one the walk carries, refreshed first
when the monster moves first. -/
theorem hitPre (ks B : Int) (pf : Bool) (hk : 0 ≤ ks) (hB : 0 ≤ B) (i : Nat) :
    preShield pf (stShield ks B pf i) B ((i : Int) + 1) = effShield ks B pf i := by
  cases pf
  · unfold preShield refresh
    simp only [Bool.false_eq_true, if_false]
    by_cases hr : ((i : Int) + 1) % 5 = 0
    · rw [if_pos hr]
      have : blockPos false i = 0 := by unfold blockPos firstBlock; simp only [Bool.false_eq_true, if_false]; split <;> omega
      unfold effShield; rw [this]; simp only [Int.natCast_zero, Int.zero_mul]; omega
    · rw [if_neg hr]
      cases i with
      | zero => simp [stShield, effShield, blockPos, firstBlock]; omega
      | succ j =>
        simp only [stShield, Bool.false_eq_true, if_false]
        apply effShield_next _ _ _ hk
        unfold blockPos firstBlock; simp only [Bool.false_eq_true, if_false]
        push_cast at hr
        split <;> split <;> omega
  · cases i with
    | zero => simp [preShield, stShield, effShield, blockPos, firstBlock]; omega
    | succ j => simp [preShield, stShield]

/-- What hit `i + 1` gets through is the closed form's increment. -/
theorem hitThrough (ks B : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) (i : Nat) :
    (absorb (preShield pf (stShield ks B pf i) B ((i : Int) + 1)) ks).1
      = cumThrough ks B pf (i + 1) - cumThrough ks B pf i := by
  rw [hitPre ks B pf (by omega) hB, cumThrough_step ks B pf hB, bthrough_succ]
  unfold absorb effShield bthrough
  rw [if_neg (by omega)]
  simp only
  omega

/-- The barrier carried out of hit `i + 1` is the walk's state after it. -/
theorem hitShield (ks B : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) (i : Nat) :
    postShield pf (absorb (preShield pf (stShield ks B pf i) B ((i : Int) + 1)) ks).2 B ((i : Int) + 1)
      = stShield ks B pf (i + 1) := by
  rw [hitPre ks B pf (by omega) hB]
  have ha : (absorb (effShield ks B pf i) ks).2 = max 0 (effShield ks B pf i - ks) := by
    unfold absorb; rw [if_neg (by omega)]
  rw [ha]
  cases pf
  · simp [postShield, stShield]
  · simp only [postShield, refresh, if_true, stShield]
    by_cases hr : ((i : Int) + 1) % 5 = 0
    · rw [if_pos hr]
      have : blockPos true (i + 1) = 0 := by
        unfold blockPos firstBlock; simp only [if_true]; push_cast at hr; split <;> omega
      unfold effShield; rw [this]; simp only [Int.natCast_zero, Int.zero_mul]; omega
    · rw [if_neg hr]
      apply effShield_next _ _ _ (by omega)
      unfold blockPos firstBlock; simp only [if_true]
      push_cast at hr
      split <;> split <;> omega

/-- From the state after `i` hits, the walk kills with hit `i + n + 1` when the
closed form first reaches `H` there. -/
theorem killsAt_of_cum (ks B H : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) :
    ∀ (n i : Nat), cumThrough ks B pf (i + n) < H → H ≤ cumThrough ks B pf (i + n + 1) →
      killsAt ks B pf n ((i : Int) + 1) (H - cumThrough ks B pf i) (stShield ks B pf i) := by
  intro n
  induction n with
  | zero =>
    intro i _ h2
    simp only [killsAt]
    rw [hitThrough ks B pf hk hB]
    simp only [Nat.add_zero] at h2
    omega
  | succ n ih =>
    intro i h1 h2
    simp only [killsAt]
    rw [hitThrough ks B pf hk hB, hitShield ks B pf hk hB]
    have hm := cumThrough_mono ks B pf (by omega) hB (i + 1) (i + (n + 1)) (by omega)
    refine ⟨by omega, ?_⟩
    have e1 : (i : Int) + 1 + 1 = ((i + 1 : Nat) : Int) + 1 := by push_cast; omega
    have e2 : H - cumThrough ks B pf i - (cumThrough ks B pf (i + 1) - cumThrough ks B pf i)
        = H - cumThrough ks B pf (i + 1) := by omega
    rw [e1, e2]
    exact ih (i + 1) (by rw [show i + 1 + n = i + (n + 1) by omega]; exact h1)
      (by rw [show i + 1 + n + 1 = i + (n + 1) + 1 by omega]; exact h2)

/-- From the state after `i` hits, the walk does not kill within `f` more hits
while the closed form stays below `H`. -/
theorem killSim_of_cum (ks B H : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) :
    ∀ (f i : Nat), cumThrough ks B pf (i + f) < H →
      killSim ks B pf f ((i : Int) + 1) (H - cumThrough ks B pf i) (stShield ks B pf i)
        = (i : Int) + 1 + f := by
  intro f
  induction f with
  | zero => intro i _; simp [killSim]
  | succ f ih =>
    intro i h
    have hm := cumThrough_mono ks B pf (by omega) hB (i + 1) (i + (f + 1)) (by omega)
    simp only [killSim]
    rw [hitThrough ks B pf hk hB, hitShield ks B pf hk hB, if_neg (by omega)]
    have e1 : (i : Int) + 1 + 1 = ((i + 1 : Nat) : Int) + 1 := by push_cast; omega
    have e2 : H - cumThrough ks B pf i - (cumThrough ks B pf (i + 1) - cumThrough ks B pf i)
        = H - cumThrough ks B pf (i + 1) := by omega
    rw [e1, e2, ih (i + 1) (by rw [show i + 1 + f = i + (f + 1) by omega]; exact h)]
    push_cast; omega

/-- A kill with exactly the `n + 1`-th hit is the round `killSim` reports. -/
theorem killSim_of_killsAt (ks full : Int) (pf : Bool) :
    ∀ (n f : Nat) (r m s : Int), killsAt ks full pf n r m s → n < f →
      killSim ks full pf f r m s = r + n := by
  intro n
  induction n with
  | zero =>
    intro f r m s h hf
    obtain ⟨f, rfl⟩ : ∃ g, f = g + 1 := ⟨f - 1, by omega⟩
    simp only [killsAt] at h
    simp [killSim, h]
  | succ n ih =>
    intro f r m s h hf
    obtain ⟨f, rfl⟩ : ∃ g, f = g + 1 := ⟨f - 1, by omega⟩
    simp only [killsAt] at h
    simp only [killSim, if_neg h.1]
    rw [ih f _ _ _ h.2 (by omega)]
    push_cast; omega

/-! #### The closed form is the walk's first kill. -/

theorem ceilDiv_le_of_le_mul (n d m : Int) (hd : 0 < d) (hn : 0 ≤ n) (h : n ≤ m * d) :
    ceilDiv n d ≤ m := by
  by_cases h0 : n = 0
  · subst h0
    have hz : ceilDiv 0 d = 0 := by
      unfold ceilDiv; exact Int.fdiv_eq_zero_of_lt (by omega) (by omega)
    rw [hz]
    rcases Int.lt_or_le m 0 with hm | hm
    · have : m * d < 0 := Int.mul_neg_of_neg_of_pos hm hd
      omega
    · exact hm
  · have h2 := ceilDiv_pred_mul_lt n d hd (by omega)
    have : (ceilDiv n d - 1) * d < m * d := by omega
    have := Int.lt_of_mul_lt_mul_right this (by omega)
    omega

theorem ceilDiv_mono_num (n1 n2 d : Int) (hd : 0 < d) (hn : 0 ≤ n1) (h : n1 ≤ n2) :
    ceilDiv n1 d ≤ ceilDiv n2 d := by
  unfold ceilDiv; exact fdiv_le_fdiv_of_le _ _ _ hd (by omega) (by omega)

/-- The closed form's last-blocks branch, opened up: `q ≥ 0` full later blocks,
the last block's `j ∈ [1, 5]` hits for the `R ∈ [1, kGap]` HP left. -/
theorem killRoundsCore_open (H B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) (hH : 1 ≤ H)
    (h1 : ¬ H + B ≤ firstLen pf * ks) (h2 : ¬ kGap B ks ≤ 0) :
    ∃ q j R : Int, 0 ≤ q ∧ 1 ≤ j ∧ j ≤ 5 ∧ 1 ≤ R ∧ R ≤ kGap B ks ∧ R + B ≤ j * ks ∧
      (j - 1) * ks < R + B ∧ H = max 0 (firstLen pf * ks - B) + q * kGap B ks + R ∧
      killRoundsCore H B ks pf = firstLen pf + q * 5 + j := by
  have hg : 0 < kGap B ks := by omega
  have hleft : 1 ≤ kLeft H B ks pf := by unfold kLeft; omega
  have hc1 := ceilDiv_mul_ge (kLeft H B ks pf) (kGap B ks) hg (by omega)
  have hc2 := ceilDiv_pred_mul_lt (kLeft H B ks pf) (kGap B ks) hg hleft
  have hcpos := ceilDiv_pos (kLeft H B ks pf) (kGap B ks) hg hleft
  have hq : kBlocks H B ks pf = ceilDiv (kLeft H B ks pf) (kGap B ks) - 1 := rfl
  have hqg : kBlocks H B ks pf * kGap B ks
      = ceilDiv (kLeft H B ks pf) (kGap B ks) * kGap B ks - kGap B ks := by
    rw [hq, Int.sub_mul, Int.one_mul]
  have hR1 : 1 ≤ kLeft H B ks pf - kBlocks H B ks pf * kGap B ks := by
    rw [hq]; omega
  have hR2 : kLeft H B ks pf - kBlocks H B ks pf * kGap B ks ≤ kGap B ks := by omega
  have hleftdef : kLeft H B ks pf = H - max 0 (firstLen pf * ks - B) := rfl
  have hq0 : 0 ≤ kBlocks H B ks pf := by omega
  have hN : killRoundsCore H B ks pf = firstLen pf + kBlocks H B ks pf * 5
      + ceilDiv (kLeft H B ks pf - kBlocks H B ks pf * kGap B ks + B) ks := by
    unfold killRoundsCore; rw [if_neg h1, if_neg h2]
  generalize hRdef : kLeft H B ks pf - kBlocks H B ks pf * kGap B ks = R at hR1 hR2 hN
  have hj1 := ceilDiv_mul_ge (R + B) ks hk (by omega)
  have hj2 := ceilDiv_pred_mul_lt (R + B) ks hk (by omega)
  have hjpos := ceilDiv_pos (R + B) ks hk (by omega)
  have hj5 : ceilDiv (R + B) ks ≤ 5 := by
    have : (ceilDiv (R + B) ks - 1) * ks < 5 * ks := by unfold kGap at hR2; omega
    have := Int.lt_of_mul_lt_mul_right this (by omega); omega
  exact ⟨kBlocks H B ks pf, ceilDiv (R + B) ks, R, hq0, hjpos, hj5, hR1, hR2, hj1, hj2,
    by omega, hN⟩

/-- The walled branch is the over-cap sentinel. -/
theorem killRoundsCore_walled (H B ks : Int) (pf : Bool) (hw : walledCore H B ks pf) :
    killRoundsCore H B ks pf = maxTurns + 1 := by
  unfold killRoundsCore; rw [if_neg hw.1, if_pos hw.2]

/-- Under the cap the barrier is not a wall. -/
theorem not_walledCore_of_le (H B ks : Int) (pf : Bool) (h : killRoundsCore H B ks pf ≤ maxTurns) :
    ¬ walledCore H B ks pf := by
  intro hw; rw [killRoundsCore_walled H B ks pf hw] at h; simp [maxTurns] at h

/-- **The closed form is the walk's first kill**: `killRoundsCore` hits reach
`H` through the barrier, one fewer does not. -/
theorem killRoundsCore_spec (H B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) (hH : 1 ≤ H)
    (hw : ¬ walledCore H B ks pf) :
    1 ≤ killRoundsCore H B ks pf ∧
      H ≤ cumThrough ks B pf (killRoundsCore H B ks pf).toNat ∧
      cumThrough ks B pf ((killRoundsCore H B ks pf).toNat - 1) < H := by
  have hL := firstBlock_cast pf
  have hLb := firstBlock_bounds pf
  by_cases h1 : H + B ≤ firstLen pf * ks
  · have hN : killRoundsCore H B ks pf = ceilDiv (H + B) ks := by
      unfold killRoundsCore; rw [if_pos h1]
    rw [hN]
    have hc1 := ceilDiv_mul_ge (H + B) ks hk (by omega)
    have hc2 := ceilDiv_pred_mul_lt (H + B) ks hk (by omega)
    have hcpos := ceilDiv_pos (H + B) ks hk (by omega)
    generalize ceilDiv (H + B) ks = N at hc1 hc2 hcpos ⊢
    have hNL : N ≤ firstLen pf := by
      have : (N - 1) * ks < firstLen pf * ks := by omega
      have := Int.lt_of_mul_lt_mul_right this (by omega); omega
    obtain ⟨n, rfl⟩ : ∃ n : Nat, N = (n : Int) := ⟨N.toNat, by omega⟩
    simp only [Int.toNat_natCast]
    rw [cumThrough_le_first ks B pf n (by omega) hB,
      cumThrough_le_first ks B pf (n - 1) (by omega) hB]
    unfold bthrough
    have e : ((n - 1 : Nat) : Int) = (n : Int) - 1 := by omega
    rw [e]
    exact ⟨hcpos, by omega, by omega⟩
  · have h2 : ¬ kGap B ks ≤ 0 := fun h => hw ⟨h1, h⟩
    have h2' : 0 < 5 * ks - B := by unfold kGap at h2; omega
    obtain ⟨q, j, R, hq, hj1, hj5, hR1, hR2, hjk1, hjk2, hH', hN⟩ :=
      killRoundsCore_open H B ks pf hk hB (by omega) h1 h2
    rw [hN]
    obtain ⟨qn, rfl⟩ : ∃ n : Nat, q = (n : Int) := ⟨q.toNat, by omega⟩
    obtain ⟨jn, rfl⟩ : ∃ n : Nat, j = (n : Int) := ⟨j.toNat, by omega⟩
    have hbt5 : bthrough ks B 5 = kGap B ks := by
      unfold bthrough kGap; rw [show ((5 : Nat) : Int) = 5 from rfl]; omega
    have hbtL : bthrough ks B (firstBlock pf) = max 0 (firstLen pf * ks - B) := by
      unfold bthrough; rw [hL]
    have e1 : (firstLen pf + (qn : Int) * 5 + (jn : Int)).toNat = firstBlock pf + 5 * qn + jn := by
      omega
    rw [e1]
    refine ⟨by omega, ?_, ?_⟩
    · by_cases hj : jn < 5
      · rw [cumThrough_block ks B pf qn jn hj, hbt5, hbtL]; unfold bthrough; omega
      · have e2 : firstBlock pf + 5 * qn + jn = firstBlock pf + 5 * (qn + 1) + 0 := by omega
        rw [e2, cumThrough_block ks B pf (qn + 1) 0 (by omega), hbt5, hbtL, bthrough_zero _ _ hB,
          natCast_succ_mul]
        omega
    · have e2 : firstBlock pf + 5 * qn + jn - 1 = firstBlock pf + 5 * qn + (jn - 1) := by omega
      rw [e2, cumThrough_block ks B pf qn (jn - 1) (by omega), hbt5, hbtL]
      unfold bthrough
      have e3 : ((jn - 1 : Nat) : Int) = (jn : Int) - 1 := by omega
      rw [e3]; omega

/-- The least hit count reaching `H` bounds the closed form. -/
theorem killRoundsCore_le (H B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B) (hH : 1 ≤ H)
    (hw : ¬ walledCore H B ks pf) (n : Nat) (hn : H ≤ cumThrough ks B pf n) :
    killRoundsCore H B ks pf ≤ n := by
  obtain ⟨h1, _, h3⟩ := killRoundsCore_spec H B ks pf hk hB hH hw
  rcases Nat.lt_or_ge n (killRoundsCore H B ks pf).toNat with hlt | hge
  · have := cumThrough_mono ks B pf (by omega) hB n ((killRoundsCore H B ks pf).toNat - 1) (by omega)
    omega
  · omega

/-- At no HP (a degenerate monster) the closed form reads off the barrier alone. -/
theorem killRoundsCore_zero (B ks : Int) (pf : Bool) (hk : 0 < ks) :
    killRoundsCore 0 B ks pf =
      if B ≤ firstLen pf * ks then ceilDiv B ks
      else if kGap B ks ≤ 0 then maxTurns + 1 else firstLen pf := by
  unfold killRoundsCore
  simp only [Int.zero_add]
  split
  · rfl
  · rename_i h1
    split
    · rfl
    · rename_i h2
      have hl : kLeft 0 B ks pf = 0 := by unfold kLeft; omega
      have hz : ceilDiv 0 (kGap B ks) = 0 := by
        unfold ceilDiv; exact Int.fdiv_eq_zero_of_lt (by omega) (by omega)
      have hb : kBlocks 0 B ks pf = -1 := by unfold kBlocks; rw [hl, hz]; rfl
      rw [hb, hl]
      have e : 0 - -1 * kGap B ks + B = 5 * ks := by unfold kGap; omega
      rw [e]
      have h5 : ceilDiv (5 * ks) ks = 5 := by
        unfold ceilDiv
        have : 5 * ks + ks - 1 = (ks - 1) + 5 * ks := by omega
        rw [this, Int.add_mul_fdiv_right _ _ (by omega), Int.fdiv_eq_zero_of_lt (by omega) (by omega)]
        rfl
      rw [h5]; omega

/-- A living monster not dead in the first block takes more than the first block. -/
theorem killRoundsCore_gt_first (H B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B)
    (hH : 1 ≤ H) (h1 : ¬ H + B ≤ firstLen pf * ks) :
    firstLen pf < killRoundsCore H B ks pf := by
  by_cases h2 : kGap B ks ≤ 0
  · rw [killRoundsCore_walled H B ks pf ⟨h1, h2⟩]
    have := firstLen_bounds pf; simp only [maxTurns]; omega
  · obtain ⟨q, j, R, hq, hj1, _, _, _, _, _, _, hN⟩ := killRoundsCore_open H B ks pf hk hB hH h1 h2
    omega

theorem ceilDiv_le_firstLen (B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B)
    (h : B ≤ firstLen pf * ks) : ceilDiv B ks ≤ firstLen pf :=
  ceilDiv_le_of_le_mul B ks _ hk hB h

/-- The closed form never rises with the kill step, where the barrier is no wall. -/
theorem killRoundsCore_antitone_ks (H B k1 k2 : Int) (pf : Bool) (hH : 0 ≤ H) (hB : 0 ≤ B)
    (hk : 0 < k1) (hle : k1 ≤ k2) (hw : ¬ walledCore H B k1 pf) :
    killRoundsCore H B k2 pf ≤ killRoundsCore H B k1 pf := by
  have hL := firstLen_bounds pf
  have hLk : firstLen pf * k1 ≤ firstLen pf * k2 := Int.mul_le_mul_of_nonneg_left hle (by omega)
  have hw2 : ¬ walledCore H B k2 pf := by
    unfold walledCore kGap at *; omega
  by_cases hH1 : 1 ≤ H
  · obtain ⟨h1, h2, _⟩ := killRoundsCore_spec H B k1 pf hk hB hH1 hw
    have := cumThrough_mono_ks k1 k2 B pf hle (killRoundsCore H B k1 pf).toNat
    have := killRoundsCore_le H B k2 pf (by omega) hB hH1 hw2 (killRoundsCore H B k1 pf).toNat
      (by omega)
    omega
  · obtain rfl : H = 0 := by omega
    rw [killRoundsCore_zero B k1 pf hk, killRoundsCore_zero B k2 pf (by omega)]
    unfold walledCore at hw; simp only [Int.zero_add] at hw
    by_cases b1 : B ≤ firstLen pf * k1
    · rw [if_pos b1, if_pos (by omega)]
      exact ceilDiv_antitone_divisor B k1 k2 hB hk hle
    · have g1 : ¬ kGap B k1 ≤ 0 := fun h => hw ⟨b1, h⟩
      rw [if_neg b1, if_neg g1]
      split
      · exact ceilDiv_le_firstLen B k2 pf (by omega) hB (by assumption)
      · rw [if_neg (by unfold kGap at *; omega)]; exact Int.le_refl _

/-- The closed form never falls as the monster's HP rises. -/
theorem killRoundsCore_mono_hp (H1 H2 B ks : Int) (pf : Bool) (hk : 0 < ks) (hB : 0 ≤ B)
    (hH : 0 ≤ H1) (hle : H1 ≤ H2) :
    killRoundsCore H1 B ks pf ≤ killRoundsCore H2 B ks pf := by
  have hL := firstLen_bounds pf
  by_cases hw2 : walledCore H2 B ks pf
  · rw [killRoundsCore_walled H2 B ks pf hw2]
    by_cases hw1 : walledCore H1 B ks pf
    · rw [killRoundsCore_walled H1 B ks pf hw1]; exact Int.le_refl _
    · have h1 : H1 + B ≤ firstLen pf * ks := by
        by_cases h : H1 + B ≤ firstLen pf * ks
        · exact h
        · exact absurd ⟨h, hw2.2⟩ hw1
      unfold killRoundsCore; rw [if_pos h1]
      have := ceilDiv_le_of_le_mul (H1 + B) ks (firstLen pf) hk (by omega) h1
      simp only [maxTurns]; omega
  have hw1 : ¬ walledCore H1 B ks pf := by
    unfold walledCore at *; omega
  by_cases hH1 : 1 ≤ H1
  · obtain ⟨_, h2, _⟩ := killRoundsCore_spec H2 B ks pf hk hB (by omega) hw2
    have := killRoundsCore_le H1 B ks pf hk hB hH1 hw1 (killRoundsCore H2 B ks pf).toNat (by omega)
    have := (killRoundsCore_spec H2 B ks pf hk hB (by omega) hw2).1
    omega
  · obtain rfl : H1 = 0 := by omega
    rw [killRoundsCore_zero B ks pf hk]
    unfold walledCore at hw1; simp only [Int.zero_add] at hw1
    by_cases b1 : B ≤ firstLen pf * ks
    · rw [if_pos b1]
      by_cases h2 : H2 + B ≤ firstLen pf * ks
      · unfold killRoundsCore; rw [if_pos h2]
        exact ceilDiv_mono_num B (H2 + B) ks hk hB (by omega)
      · have := killRoundsCore_gt_first H2 B ks pf hk hB (by omega) h2
        have := ceilDiv_le_firstLen B ks pf hk hB b1
        omega
    · have g1 : ¬ kGap B ks ≤ 0 := fun h => hw1 ⟨b1, h⟩
      rw [if_neg b1, if_neg g1]
      by_cases hH2 : H2 = 0
      · subst hH2; rw [killRoundsCore_zero B ks pf hk, if_neg b1, if_neg g1]; exact Int.le_refl _
      · have := killRoundsCore_gt_first H2 B ks pf hk hB (by omega) (by omega)
        omega

/-- The closed form never falls as the barrier rises, where the larger one is no wall. -/
theorem killRoundsCore_mono_barrier (H B1 B2 ks : Int) (pf : Bool) (hk : 0 < ks) (hH : 0 ≤ H)
    (hB : 0 ≤ B1) (hle : B1 ≤ B2) (hw : ¬ walledCore H B2 ks pf) :
    killRoundsCore H B1 ks pf ≤ killRoundsCore H B2 ks pf := by
  have hL := firstLen_bounds pf
  have hw1 : ¬ walledCore H B1 ks pf := by
    unfold walledCore kGap at *; omega
  by_cases hH1 : 1 ≤ H
  · obtain ⟨_, h2, _⟩ := killRoundsCore_spec H B2 ks pf hk (by omega) hH1 hw
    have := cumThrough_anti_barrier ks B1 B2 pf hle (killRoundsCore H B2 ks pf).toNat
    have := killRoundsCore_le H B1 ks pf hk hB hH1 hw1 (killRoundsCore H B2 ks pf).toNat (by omega)
    have := (killRoundsCore_spec H B2 ks pf hk (by omega) hH1 hw).1
    omega
  · obtain rfl : H = 0 := by omega
    rw [killRoundsCore_zero B1 ks pf hk, killRoundsCore_zero B2 ks pf hk]
    unfold walledCore at hw; simp only [Int.zero_add] at hw
    by_cases b2 : B2 ≤ firstLen pf * ks
    · rw [if_pos b2, if_pos (by omega)]
      exact ceilDiv_mono_num B1 B2 ks hk hB hle
    · have g2 : ¬ kGap B2 ks ≤ 0 := fun h => hw ⟨b2, h⟩
      rw [if_neg b2, if_neg g2]
      split
      · exact ceilDiv_le_firstLen B1 ks pf hk hB (by assumption)
      · rw [if_neg (by unfold kGap at *; omega)]; exact Int.le_refl _

/-- With no barrier the closed form is `⌈H / ks⌉`, whoever moves first. -/
theorem killRoundsCore_zero_barrier (H ks : Int) (pf : Bool) (hk : 0 < ks) :
    killRoundsCore H 0 ks pf = ceilDiv H ks := by
  have hL := firstLen_bounds pf
  unfold killRoundsCore
  by_cases h1 : H + 0 ≤ firstLen pf * ks
  · rw [if_pos h1, Int.add_zero]
  · rw [if_neg h1, if_neg (by unfold kGap; omega)]
    generalize kBlocks H 0 ks pf = q
    have hLk : 0 ≤ firstLen pf * ks := Int.mul_nonneg (by omega) (by omega)
    have hl : kLeft H 0 ks pf = H - firstLen pf * ks := by unfold kLeft; omega
    have hg : q * kGap 0 ks = q * 5 * ks := by
      unfold kGap; rw [Int.sub_zero, Int.mul_assoc]
    rw [hl, hg]
    unfold ceilDiv
    have e : H + ks - 1 = (H - firstLen pf * ks - q * 5 * ks + 0 + ks - 1) + (firstLen pf + q * 5) * ks := by
      rw [Int.add_mul]; omega
    rw [e, Int.add_mul_fdiv_right _ _ (by omega : ks ≠ 0)]
    omega

/-! #### The closed form at the unscaled HP and barrier. -/

theorem killRounds_walled (hp barrier ks : Int) (pf : Bool) (hw : walled hp barrier ks pf) :
    killRounds hp barrier ks pf = maxTurns + 1 :=
  killRoundsCore_walled _ _ _ _ hw

theorem not_walled_of_le (hp barrier ks : Int) (pf : Bool)
    (h : killRounds hp barrier ks pf ≤ maxTurns) : ¬ walled hp barrier ks pf :=
  not_walledCore_of_le _ _ _ _ h

/-- A living monster takes at least one round. -/
theorem killRounds_pos (hp barrier ks : Int) (pf : Bool) (hk : 0 < ks) (hhp : 1 ≤ hp)
    (hb : 0 ≤ barrier) : 1 ≤ killRounds hp barrier ks pf := by
  by_cases hw : walled hp barrier ks pf
  · rw [killRounds_walled _ _ _ _ hw]; simp [maxTurns]
  · exact (killRoundsCore_spec _ _ _ _ hk (by omega) (by omega) hw).1

/-- A larger kill step never delays the kill (where the barrier is no wall:
past the wall the sentinel `maxTurns + 1` can sit below a long finite count). -/
theorem killRounds_antitone_ks (hp barrier k1 k2 : Int) (pf : Bool) (hhp : 0 ≤ hp)
    (hb : 0 ≤ barrier) (hk : 0 < k1) (hle : k1 ≤ k2) (hw : ¬ walled hp barrier k1 pf) :
    killRounds hp barrier k2 pf ≤ killRounds hp barrier k1 pf :=
  killRoundsCore_antitone_ks _ _ _ _ _ (by omega) (by omega) hk hle hw

/-- More monster HP never speeds the kill. -/
theorem killRounds_mono_hp (hp1 hp2 barrier ks : Int) (pf : Bool) (hk : 0 < ks)
    (hb : 0 ≤ barrier) (hhp : 0 ≤ hp1) (hle : hp1 ≤ hp2) :
    killRounds hp1 barrier ks pf ≤ killRounds hp2 barrier ks pf :=
  killRoundsCore_mono_hp _ _ _ _ _ hk (by omega) (by omega) (by omega)

/-- A larger barrier never speeds the kill (where it is no wall). -/
theorem killRounds_mono_barrier (hp b1 b2 ks : Int) (pf : Bool) (hk : 0 < ks) (hhp : 0 ≤ hp)
    (hb : 0 ≤ b1) (hle : b1 ≤ b2) (hw : ¬ walled hp b2 ks pf) :
    killRounds hp b1 ks pf ≤ killRounds hp b2 ks pf :=
  killRoundsCore_mono_barrier _ _ _ _ _ hk (by omega) (by omega) (by omega) hw

/-- With no barrier the closed form is the old `⌈hp × 10000 / ks⌉`. -/
theorem killRounds_zero_barrier (hp ks : Int) (pf : Bool) (hk : 0 < ks) :
    killRounds hp 0 ks pf = ceilDiv (hp * 10000) ks := by
  unfold killRounds; rw [Int.zero_mul]; exact killRoundsCore_zero_barrier _ _ _ hk

/-- Under the cap the walk kills with exactly the `killRounds`-th hit. -/
theorem killRounds_killsAt (hp barrier ks : Int) (pf : Bool) (hk : 0 < ks) (hhp : 1 ≤ hp)
    (hb : 0 ≤ barrier) (hw : ¬ walled hp barrier ks pf) :
    ∃ n : Nat, killRounds hp barrier ks pf = (n : Int) + 1 ∧
      killsAt ks (barrier * 10000) pf n 1 (hp * 10000) (barrier * 10000) := by
  obtain ⟨h1, h2, h3⟩ := killRoundsCore_spec _ _ _ _ hk (by omega) (by omega) hw
  refine ⟨(killRounds hp barrier ks pf).toNat - 1, by unfold killRounds; omega, ?_⟩
  have h := killsAt_of_cum ks (barrier * 10000) (hp * 10000) pf hk (by omega)
    ((killRounds hp barrier ks pf).toNat - 1) 0
    (by rw [Nat.zero_add]; exact h3)
    (by rw [Nat.zero_add, Nat.sub_add_cancel (by unfold killRounds; omega)]; exact h2)
  rw [cumThrough_zero _ _ _ (by omega)] at h
  simpa [stShield] using h

/-- **The walk is the closed form**: with fuel for `killRounds` rounds, the
round-by-round barrier walk kills in exactly `killRounds` rounds. -/
theorem killSim_eq_killRounds (hp barrier ks : Int) (pf : Bool) (hk : 0 < ks) (hhp : 1 ≤ hp)
    (hb : 0 ≤ barrier) (hw : ¬ walled hp barrier ks pf) (fuel : Nat)
    (hf : (killRounds hp barrier ks pf).toNat ≤ fuel) :
    killSim ks (barrier * 10000) pf fuel 1 (hp * 10000) (barrier * 10000)
      = killRounds hp barrier ks pf := by
  obtain ⟨n, hn, h⟩ := killRounds_killsAt hp barrier ks pf hk hhp hb hw
  rw [killSim_of_killsAt _ _ _ n fuel _ _ _ h (by omega), hn]; omega

/-- **Behind a wall the walk never kills**: it runs out of fuel. -/
theorem killSim_walled (hp barrier ks : Int) (pf : Bool) (hk : 0 < ks) (hhp : 1 ≤ hp)
    (hb : 0 ≤ barrier) (hw : walled hp barrier ks pf) (fuel : Nat) :
    killSim ks (barrier * 10000) pf fuel 1 (hp * 10000) (barrier * 10000) = 1 + fuel := by
  have hz : ∀ c : Nat, c ≤ 5 → bthrough ks (barrier * 10000) c = 0 := by
    intro c hc; unfold bthrough
    have : (c : Int) * ks ≤ 5 * ks := Int.mul_le_mul_of_nonneg_right (by omega) (by omega)
    have := hw.2; unfold kGap at this; omega
  have hT : ∀ i, cumThrough ks (barrier * 10000) pf i = 0 := by
    intro i
    have hLb := firstBlock_bounds pf
    unfold cumThrough; split
    · exact hz _ (by omega)
    · rw [hz _ hLb.2, hz 5 (by omega), hz _ (by omega)]; simp
  have h := killSim_of_cum ks (barrier * 10000) (hp * 10000) pf hk (by omega) fuel 0
    (by rw [hT]; omega)
  rw [hT] at h
  simpa [stShield] using h

/-! #### `predict_win` verdict properties. -/

/-- `maxturns_sound`: `rounds_to_kill > MAX_TURNS ⇒ ¬win` (when the player can
damage the monster net of its lifesteal, `killStep > 0`). -/
theorem maxturns_sound (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn
    monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
    monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool)
    (hraw : 0 < rawPlayer)
    (hks : 0 < killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
        monsterVoidDrain monsterBubble monsterSunShield)
    (hover : killRounds monsterHp monsterBarrier
              (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
                monsterVoidDrain monsterBubble monsterSunShield) playerFirst > maxTurns) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn
      monsterHealing monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
      monsterSunShield monsterGreed monsterEnchantedMirror playerFirst = false := by
  unfold predictWin
  rw [if_neg (Int.not_le.mpr hraw)]
  simp only [Int.not_le.mpr hks, if_false]
  rw [if_pos hover]

/-- `predict_win_eq_sim`: the closed-form verdict equals the operational
fight-simulation verdict. Same guard ladder: `rawPlayer ≤ 0`, `killStep ≤ 0`
(monster out-heals our damage), max-turns cap, reconstitution, `dieStep ≤ 0`
(we out-sustain), initiative tiebreak. The closed-form rounds are replaced by
the round-by-round walks: `killSim` (the barrier absorbed and refreshed every 5
monster turns; behind a wall it never kills and runs past the cap) and
`simRoundsNet`, each with enough fuel. -/
theorem predict_win_eq_sim (rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
    pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
    monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
    monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool)
    (hmhp : 1 ≤ monsterHp) (hbar : 0 ≤ monsterBarrier) (hphp : 1 ≤ playerMaxHp)
    (fk fd : Nat)
    (hfk : (killRounds monsterHp monsterBarrier
              (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
                monsterVoidDrain monsterBubble monsterSunShield) playerFirst).toNat ≤ fk)
    (hfd : (ceilDiv (playerMaxHp*10000)
              (dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn playerMaxHp
                monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer monsterGreed
                monsterEnchantedMirror mAtkSum)).toNat ≤ fd) :
    predictWin rawPlayer pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
      monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
      monsterSunShield monsterGreed monsterEnchantedMirror playerFirst
      = (if rawPlayer ≤ 0 then false
         else
           let ks := killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
               playerMaxHp monsterVoidDrain monsterBubble monsterSunShield
           if ks ≤ 0 then false
           else
             let rtk := killSim ks (monsterBarrier * 10000) playerFirst fk 1 (monsterHp * 10000)
               (monsterBarrier * 10000)
             if rtk > maxTurns then false
             else if 0 < monsterReconstitution ∧ monsterReconstitution ≤ rtk then false
             else
               let ds := dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
                   playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer
                   monsterGreed monsterEnchantedMirror mAtkSum
               if ds ≤ 0 then true
               else
                 let rtd := simRoundsNet playerMaxHp ds fd
                 if playerFirst then rtk ≤ rtd else rtk < rtd) := by
  unfold predictWin
  by_cases hrp : rawPlayer ≤ 0
  · simp only [hrp, if_true]
  · simp only [hrp, if_false]
    generalize hksd : killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield = ks at hfk ⊢
    by_cases hks : ks ≤ 0
    · simp only [hks, if_true]
    · simp only [hks, if_false]
      have hksp : 0 < ks := Int.not_le.mp hks
      by_cases hw : walled monsterHp monsterBarrier ks playerFirst
      · rw [killRounds_walled _ _ _ _ hw] at hfk ⊢
        rw [killSim_walled _ _ _ _ hksp hmhp hbar hw fk]
        have hfk' : 101 ≤ fk := by simp [maxTurns] at hfk; omega
        rw [if_pos (by simp [maxTurns]), if_pos (by simp [maxTurns]; omega)]
      · rw [killSim_eq_killRounds _ _ _ _ hksp hmhp hbar hw fk hfk]
        generalize killRounds monsterHp monsterBarrier ks playerFirst = rtk
        by_cases hover : rtk > maxTurns
        · simp only [hover, if_true]
        · simp only [hover, if_false]
          by_cases hrec : 0 < monsterReconstitution ∧ monsterReconstitution ≤ rtk
          · rw [if_pos hrec, if_pos hrec]
          · rw [if_neg hrec, if_neg hrec]
            by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
                playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer
                monsterGreed monsterEnchantedMirror mAtkSum ≤ 0
            · simp only [hds, if_true]
            · simp only [hds, if_false]
              have hdsp : 0 < dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
                  playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer
                  monsterGreed monsterEnchantedMirror mAtkSum :=
                Int.not_le.mp hds
              have hrtd : simRoundsNet playerMaxHp
                  (dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn playerMaxHp
                    monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer monsterGreed
                    monsterEnchantedMirror mAtkSum) fd
                  = ceilDiv (playerMaxHp * 10000)
                      (dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
                        playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer
                        monsterGreed monsterEnchantedMirror mAtkSum) :=
                simRoundsNet_eq playerMaxHp _ hdsp hphp fd hfd
              rw [hrtd]
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
     pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
     monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
     monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr1 : 0 < raw1) (hle : raw1 ≤ raw2) (hhp : 0 ≤ monsterHp)
    (hbar : 0 ≤ monsterBarrier) (hbub0 : 0 ≤ monsterBubble) (hss0 : 0 ≤ monsterSunShield)
    (hbub : monsterBubble + monsterSunShield ≤ 100)
    (hmirror : monsterEnchantedMirror = 0)
    (hwin : predictWin raw1 pCrit monsterHp rawMonster mCrit playerMaxHp
              pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
              monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
              monsterSunShield monsterGreed monsterEnchantedMirror playerFirst = true) :
    predictWin raw2 pCrit monsterHp rawMonster mCrit playerMaxHp
      pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
      monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
      monsterSunShield monsterGreed monsterEnchantedMirror playerFirst = true := by
  have hr2 : 0 < raw2 := by omega
  -- killStepNet is monotone in rawPlayer: the merged (bubble+sunShield) coefficient ≤ 100 = 2·50.
  have hksle : killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
      monsterVoidDrain monsterBubble monsterSunShield
      ≤ killStepNet raw2 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
      monsterVoidDrain monsterBubble monsterSunShield := by
    unfold killStepNet killStep
    have hK : 0 ≤ (200 + pCrit) := by omega
    have hcomb0 : 0 ≤ monsterBubble + monsterSunShield := by omega
    -- merged coefficient is monotone in raw.
    have hcm : (monsterBubble + monsterSunShield) * raw1 * (200 + pCrit)
        ≤ (monsterBubble + monsterSunShield) * raw2 * (200 + pCrit) :=
      Int.mul_le_mul_of_nonneg_right (Int.mul_le_mul_of_nonneg_left hle hcomb0) hK
    have hnn1 : 0 ≤ (monsterBubble + monsterSunShield) * raw1 * (200 + pCrit) :=
      Int.mul_nonneg (Int.mul_nonneg hcomb0 (Int.le_of_lt hr1)) hK
    have hnn2 : 0 ≤ (monsterBubble + monsterSunShield) * raw2 * (200 + pCrit) :=
      Int.mul_nonneg (Int.mul_nonneg hcomb0 (Int.le_of_lt hr2)) hK
    -- KEY: the merged per-raw increase is at most twice the damage increase. Factor through (raw2-raw1).
    have hsplitC : (monsterBubble + monsterSunShield) * raw2 * (200 + pCrit)
        = (monsterBubble + monsterSunShield) * raw1 * (200 + pCrit)
          + (monsterBubble + monsterSunShield) * (raw2 - raw1) * (200 + pCrit) := by
      rw [← Int.add_mul, ← Int.mul_add]
      have : raw1 + (raw2 - raw1) = raw2 := by omega
      rw [this]
    have hsplitD : 50 * raw2 * (200 + pCrit)
        = 50 * raw1 * (200 + pCrit) + 50 * (raw2 - raw1) * (200 + pCrit) := by
      rw [← Int.add_mul, ← Int.mul_add]
      have : raw1 + (raw2 - raw1) = raw2 := by omega
      rw [this]
    have hdK : 0 ≤ (raw2 - raw1) := by omega
    -- Merged increment ≤ 100·(raw2-raw1)·K = 2·(50·(raw2-raw1)·K).
    have hincr : (monsterBubble + monsterSunShield) * (raw2 - raw1) * (200 + pCrit)
        ≤ 100 * (raw2 - raw1) * (200 + pCrit) :=
      Int.mul_le_mul_of_nonneg_right (Int.mul_le_mul_of_nonneg_right hbub hdK) hK
    have hcoef : 100 * (raw2 - raw1) * (200 + pCrit)
        = 2 * (50 * (raw2 - raw1) * (200 + pCrit)) := by
      have h1 : (100 : Int) * (raw2 - raw1) = 2 * (50 * (raw2 - raw1)) := by omega
      rw [h1, Int.mul_assoc]
    omega
  -- dieStep is independent of rawPlayer when monsterEnchantedMirror = 0.
  -- Unfold first so predictWin is transparent, then prove dieStep equality and rewrite hwin.
  subst hmirror
  unfold predictWin at hwin ⊢
  have hmirror_ds : dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
      playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison raw1 monsterGreed 0 mAtkSum
      = dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
      playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison raw2 monsterGreed 0 mAtkSum := by
    unfold dieStep
    have h0a : (0 : Int) * raw1 * (200 + pCrit) = 0 := by simp [Int.zero_mul]
    have h0b : (0 : Int) * raw2 * (200 + pCrit) = 0 := by simp [Int.zero_mul]
    rw [h0a, h0b]
  rw [hmirror_ds] at hwin
  rw [if_neg (Int.not_le.mpr hr1)] at hwin
  rw [if_neg (Int.not_le.mpr hr2)]
  -- ks1 > 0 (else hwin false).
  by_cases hks1 : killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
      playerMaxHp monsterVoidDrain monsterBubble monsterSunShield ≤ 0
  · rw [if_pos hks1] at hwin; exact absurd hwin (by decide)
  · rw [if_neg hks1] at hwin
    have hks1p : 0 < killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield :=
      Int.not_le.mp hks1
    have hks2p : 0 < killStepNet raw2 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield := by omega
    rw [if_neg (Int.not_le.mpr hks2p)]
    -- not over cap (else hwin false).
    by_cases hover1 : killRounds monsterHp monsterBarrier
        (killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
          monsterVoidDrain monsterBubble monsterSunShield) playerFirst > maxTurns
    · rw [if_pos hover1] at hwin; exact absurd hwin (by decide)
    · rw [if_neg hover1] at hwin
      -- rounds-to-kill antitone in the kill step: rtk2 ≤ rtk1 (the barrier is no wall at ks1).
      have hrtkle : killRounds monsterHp monsterBarrier
            (killStepNet raw2 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
              monsterVoidDrain monsterBubble monsterSunShield) playerFirst
          ≤ killRounds monsterHp monsterBarrier
            (killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
              monsterVoidDrain monsterBubble monsterSunShield) playerFirst :=
        killRounds_antitone_ks _ _ _ _ _ hhp hbar hks1p hksle
          (not_walled_of_le _ _ _ _ (by omega))
      have hover2 : ¬ killRounds monsterHp monsterBarrier
          (killStepNet raw2 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
            monsterVoidDrain monsterBubble monsterSunShield) playerFirst > maxTurns := by omega
      rw [if_neg hover2]
      -- reconstitution branch: win-side must be in the else (else hwin false).
      by_cases hrec : 0 < monsterReconstitution ∧ monsterReconstitution ≤
          killRounds monsterHp monsterBarrier
            (killStepNet raw1 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
              monsterVoidDrain monsterBubble monsterSunShield) playerFirst
      · rw [if_pos hrec] at hwin; exact absurd hwin (by decide)
      · rw [if_neg hrec] at hwin
        have hrec2 : ¬ (0 < monsterReconstitution ∧ monsterReconstitution ≤
            killRounds monsterHp monsterBarrier
              (killStepNet raw2 pCrit mCrit mLifesteal mCritHit monsterHp monsterHealing playerMaxHp
                monsterVoidDrain monsterBubble monsterSunShield) playerFirst) := by omega
        rw [if_neg hrec2]
        -- the remaining branches are independent of rawPlayer (mirror=0 proved above).
        by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
            playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison raw2
            monsterGreed 0 mAtkSum ≤ 0
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
into a loss. (A smaller HP heals less, so the kill step does not fall; the kill
rounds fall with both the HP and a larger kill step, `killRounds_mono_hp`,
`killRounds_antitone_ks`.) -/
theorem predict_win_mono_monsterhp
    (rawPlayer pCrit monsterHp1 monsterHp2 rawMonster mCrit playerMaxHp
     pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
     monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
     monsterSunShield monsterGreed monsterEnchantedMirror : Int)
    (playerFirst : Bool)
    (hpc : 0 ≤ pCrit) (hr : 0 < rawPlayer)
    (hhp2 : 0 ≤ monsterHp2) (hle : monsterHp2 ≤ monsterHp1) (hbar : 0 ≤ monsterBarrier)
    (hheal : 0 ≤ monsterHealing)
    (hwin : predictWin rawPlayer pCrit monsterHp1 rawMonster mCrit playerMaxHp
              pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
              monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
              monsterSunShield monsterGreed monsterEnchantedMirror playerFirst = true) :
    predictWin rawPlayer pCrit monsterHp2 rawMonster mCrit playerMaxHp
      pLifesteal pCritHit mLifesteal mCritHit mAtkSum monsterPoison monsterBarrier monsterBurn monsterHealing
      monsterReconstitution monsterVoidDrain monsterBerserk monsterFrenzy monsterBubble playerAntipoison
      monsterSunShield monsterGreed monsterEnchantedMirror playerFirst = true := by
  -- killStepNet is antitone in monsterHp: smaller HP ⇒ less heal subtracted ⇒ ks2 ≥ ks1.
  -- The sunShield term is constant w.r.t. monsterHp, so it cancels on both sides.
  have hksle : killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing playerMaxHp
      monsterVoidDrain monsterBubble monsterSunShield
      ≤ killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp2 monsterHealing playerMaxHp
      monsterVoidDrain monsterBubble monsterSunShield := by
    unfold killStepNet killStep
    have hhmul : monsterHealing * monsterHp2 ≤ monsterHealing * monsterHp1 :=
      Int.mul_le_mul_of_nonneg_left hle hheal
    omega
  unfold predictWin at hwin ⊢
  rw [if_neg (Int.not_le.mpr hr)] at hwin
  rw [if_neg (Int.not_le.mpr hr)]
  -- ks1 > 0 (else hwin false).
  by_cases hks1 : killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing
      playerMaxHp monsterVoidDrain monsterBubble monsterSunShield ≤ 0
  · rw [if_pos hks1] at hwin; exact absurd hwin (by decide)
  · rw [if_neg hks1] at hwin
    have hks1p : 0 < killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield :=
      Int.not_le.mp hks1
    have hks2p : 0 < killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp2 monsterHealing
        playerMaxHp monsterVoidDrain monsterBubble monsterSunShield := by omega
    rw [if_neg (Int.not_le.mpr hks2p)]
    -- not over cap (else hwin false).
    by_cases hover1 : killRounds monsterHp1 monsterBarrier
        (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing playerMaxHp
          monsterVoidDrain monsterBubble monsterSunShield) playerFirst > maxTurns
    · rw [if_pos hover1] at hwin; exact absurd hwin (by decide)
    · rw [if_neg hover1] at hwin
      -- rounds-to-kill: rtk2 = KR hp2 ks2 ≤ KR hp2 ks1 ≤ KR hp1 ks1 = rtk1.
      have hw1 := not_walled_of_le _ _ _ _ (show killRounds monsterHp1 monsterBarrier
        (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing playerMaxHp
          monsterVoidDrain monsterBubble monsterSunShield) playerFirst ≤ maxTurns by omega)
      have hw2 : ¬ walled monsterHp2 monsterBarrier
          (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing playerMaxHp
            monsterVoidDrain monsterBubble monsterSunShield) playerFirst := by
        unfold walled walledCore at *; omega
      have hstep1 := killRounds_antitone_ks monsterHp2 monsterBarrier _ _ playerFirst hhp2 hbar hks1p
        hksle hw2
      have hstep2 := killRounds_mono_hp monsterHp2 monsterHp1 monsterBarrier _ playerFirst hks1p hbar
        hhp2 hle
      have hover2 : ¬ killRounds monsterHp2 monsterBarrier
          (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp2 monsterHealing playerMaxHp
            monsterVoidDrain monsterBubble monsterSunShield) playerFirst > maxTurns := by
        omega
      rw [if_neg hover2]
      -- reconstitution branch: win-side must be in the else (else hwin false).
      by_cases hrec : 0 < monsterReconstitution ∧ monsterReconstitution ≤
          killRounds monsterHp1 monsterBarrier
            (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp1 monsterHealing playerMaxHp
              monsterVoidDrain monsterBubble monsterSunShield) playerFirst
      · rw [if_pos hrec] at hwin; exact absurd hwin (by decide)
      · rw [if_neg hrec] at hwin
        have hrec2 : ¬ (0 < monsterReconstitution ∧ monsterReconstitution ≤
            killRounds monsterHp2 monsterBarrier
              (killStepNet rawPlayer pCrit mCrit mLifesteal mCritHit monsterHp2 monsterHealing playerMaxHp
                monsterVoidDrain monsterBubble monsterSunShield) playerFirst) := by
          omega
        rw [if_neg hrec2]
        -- the remaining branches are independent of monsterHp.
        by_cases hds : dieStep rawMonster mCrit pCrit pLifesteal pCritHit monsterPoison monsterBurn
            playerMaxHp monsterVoidDrain monsterBerserk monsterFrenzy playerAntipoison rawPlayer
            monsterGreed monsterEnchantedMirror mAtkSum ≤ 0
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
